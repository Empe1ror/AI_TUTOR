"""Quiz mode engine.

    start(topic, quiz_type, source) -> [answering] -save_answer()...-> submit() -> [done]

quiz_type: "mcq"   -> 10 multiple-choice questions
           "short" -> 10 short-answer questions
           "mixed" -> 15 questions (8 multiple-choice + 7 short-answer)
source:    "knowledge" (the tutor's own knowledge) or "documents" (the learner's uploads)

Code owns counts, shuffling, de-duplication, grading of multiple-choice, scoring and mastery;
the LLM writes questions and grades short answers. If anything fails mid-step, nothing is
saved and the same call can simply be repeated.
"""
import logging
import math
import random
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Optional

from lesson import templates as lesson_templates
from lesson.errors import InvalidStateError, LessonError, LessonNotFound, LLMOutputError
from lesson.llm_utils import LLMGateway
from lesson.models import Grade, PublicQuestion, Question
from lesson.profile import student_brief
from lesson.progress import record_outcome, sync_to_profile, weak_topics

from . import config, templates
from .models import KindScore, QuizBatch, QuizItemResult, QuizResult, QuizView
from .store import QuizStore

log = logging.getLogger(__name__)
Retriever = Callable[[str], tuple]   # query -> (context_text, sources)

_KIND = {
    "mcq": (templates.MCQ_LABEL, templates.MCQ_RULES),
    "short": (templates.SHORT_LABEL, templates.SHORT_RULES),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


class QuizEngine:
    def __init__(self, db, user_id: str, *, gateway: Optional[LLMGateway] = None,
                 retriever: Optional[Retriever] = None):
        if db is None:
            raise RuntimeError("MongoDB is not configured.")
        self.db = db
        self.user_id = user_id.strip().lower()
        if not self.user_id:
            raise ValueError("A student identifier is required.")
        self.store = QuizStore(db)
        self.llm = gateway or LLMGateway()
        self.retriever = retriever    # e.g. rag_retriever(user_id, k=config.RETRIEVAL_K)

    # ================================================================== public API
    def start(self, topic: str, quiz_type: str = "mcq", source: str = "knowledge",
              difficulty: str = "medium", *, replace_active: bool = True) -> QuizView:
        topic = (topic or "").strip()
        if len(topic) < 2:
            raise LessonError("Tell me what the quiz should be about.")
        if quiz_type not in config.QUIZ_TYPES:
            raise LessonError("Choose a quiz type: multiple choice, short answer, or mixed.")
        if source not in config.SOURCES:
            raise LessonError("Choose a source: the tutor's knowledge or your documents.")
        if difficulty not in config.DIFFICULTIES:
            raise LessonError("Choose a difficulty: easy, medium or hard.")
        active = self.store.get_active(self.user_id)
        if active and not replace_active:
            raise LessonError("You already have a quiz in progress.")

        context, sources = "", []
        if source == "documents":
            if not self.retriever:
                raise LessonError("Searching your documents isn't available right now.")
            try:
                context, sources = self.retriever(topic)
            except Exception as exc:
                log.exception("document retrieval failed")
                raise LessonError("I couldn't search your documents. Please try again.",
                                  detail=str(exc)[:300]) from exc
            if not sources:
                raise LessonError("I couldn't find anything about that in your uploaded documents. "
                                  "Try another topic, or upload the material first.")
            sources = [{**s, "text": str(s.get("text", ""))[:400]} for s in sources]

        plan = config.QUIZ_TYPES[quiz_type]
        brief = self._brief()
        questions: list[Question] = []
        subject = ""
        for kind, target in plan.items():
            got, subj = self._generate_kind(kind, target, topic, difficulty, source, context,
                                            brief, [q.prompt for q in questions])
            questions += got
            subject = subject or subj

        now = _now()
        doc = {
            "quiz_id": uuid.uuid4().hex, "user_id": self.user_id,
            "topic": topic, "subject": subject.strip() or "Quiz",
            "quiz_type": quiz_type, "source": source, "difficulty": difficulty,
            "requested_total": sum(plan.values()),
            "questions": [q.model_dump() for q in questions],
            "answers": {}, "status": "active", "phase": "answering",
            "sources": sources, "context_snippet": context[:2000] if source == "documents" else "",
            "result": None, "created_at": now, "updated_at": now,
        }
        if active:                           # retire the old quiz only once the new one is ready
            active["status"] = "abandoned"
            self._save(active)
        self.store.create(doc)
        return self._to_view(doc)

    def get_active_view(self) -> Optional[QuizView]:
        doc = self.store.get_active(self.user_id)
        return self._to_view(doc) if doc else None

    def get_view(self, quiz_id: str) -> QuizView:
        return self._to_view(self._load(quiz_id))

    def save_answer(self, quiz_id: str, index: int, answer) -> QuizView:
        """Save one draft answer (so a refresh doesn't lose progress). Blank clears it."""
        doc = self._load(quiz_id)
        self._require_answering(doc)
        questions = self._questions(doc)
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(questions):
            raise LessonError("That question doesn't exist.")
        value = self._normalise(questions[index], answer)
        if value is None:
            doc["answers"].pop(str(index), None)
        else:
            doc["answers"][str(index)] = value
        self._save(doc)
        return self._to_view(doc)

    def submit(self, quiz_id: str, answers: Optional[list] = None) -> QuizView:
        """Grade the quiz. `answers` (one per question) overrides saved drafts; blanks are skipped."""
        doc = self._load(quiz_id)
        self._require_answering(doc)
        questions = self._questions(doc)

        if answers is None:
            given = [doc["answers"].get(str(i)) for i in range(len(questions))]
        else:
            if not isinstance(answers, (list, tuple)) or len(answers) != len(questions):
                raise LessonError("Please provide one answer slot per question (leave blanks to skip).")
            given = [self._normalise(q, a) for q, a in zip(questions, answers)]

        items = self._grade_all(questions, given)      # may raise -> nothing saved, retry is safe
        result = self._build_result(items)
        doc["answers"] = {str(i): a for i, a in enumerate(given) if a is not None}
        doc["result"] = result.model_dump()
        doc["phase"], doc["status"], doc["completed_at"] = "done", "completed", _now()
        self._save(doc)

        try:                                           # evidence -> mastery, never blocks the quiz
            record_outcome(self.db, self.user_id, doc["subject"], doc["topic"], result.score,
                           source_text=doc.get("context_snippet", ""), weight=config.MASTERY_WEIGHT)
            sync_to_profile(self.db, self.user_id)
        except Exception:
            log.exception("progress update failed")
        return self._to_view(doc)

    def abandon(self, quiz_id: str) -> None:
        doc = self._load(quiz_id)
        if doc["status"] == "active":
            doc["status"] = "abandoned"
            self._save(doc)

    def list_quizzes(self, limit: int = 10) -> list[dict]:
        return self.store.list_recent(self.user_id, limit)

    # ================================================================== generation
    def _generate_kind(self, kind, target, topic, difficulty, source, context, brief, existing):
        label, rules = _KIND[kind]
        source_rule = templates.DOCUMENTS_RULE if source == "documents" else templates.KNOWLEDGE_RULE
        collected: list[Question] = []
        seen = {_norm(p) for p in existing}
        subject = ""
        for _ in range(config.MAX_ROUNDS):
            need = target - len(collected)
            if need <= 0:
                break
            avoid = "\n".join(f"- {p}" for p in [*existing, *[q.prompt for q in collected]]) or "none"
            batch = self.llm.structured(
                QuizBatch, templates.GEN_SYS, templates.GEN_HUMAN,
                topic=topic, difficulty=difficulty, count=min(need, config.MAX_PER_CALL),
                kind_label=label, kind_rules=rules, source_rule=source_rule,
                student_brief=brief, avoid=avoid, context=context or "(none)",
            )
            subject = subject or batch.subject
            for q in batch.questions:
                key = _norm(q.prompt)
                if q.kind != kind or not key or key in seen:
                    continue                          # wrong kind or duplicate: top-up round will cover it
                seen.add(key)
                collected.append(q)
                if len(collected) == target:
                    break

        minimum = max(1, math.ceil(config.MIN_FRACTION * target))
        if len(collected) < minimum:
            hint = (" The documents may not cover this topic in enough detail." if source == "documents" else "")
            raise LLMOutputError("I couldn't write enough good questions for that. Please try again." + hint,
                                 detail=f"{kind}: got {len(collected)} of {target}")
        for q in collected:
            if q.kind == "mcq":                       # models like to put the answer first: shuffle in code
                correct = q.options[q.correct_index]
                options = list(q.options)
                random.shuffle(options)
                q.options, q.correct_index = options, options.index(correct)
        return collected, subject

    # ================================================================== grading
    def _grade_all(self, questions: list[Question], given: list) -> list[QuizItemResult]:
        items: list[Optional[QuizItemResult]] = [None] * len(questions)
        short_jobs = []
        for i, (q, a) in enumerate(zip(questions, given)):
            if a is None:                                          # skipped
                items[i] = self._item(i, q, a, Grade(score=0.0, feedback="Skipped."), skipped=True)
            elif q.kind == "mcq":                                  # graded by code
                ok = a == q.correct_index
                items[i] = self._item(i, q, a, Grade(
                    score=1.0 if ok else 0.0, feedback=q.explanation or ("Correct." if ok else "Not quite.")))
            else:
                short_jobs.append((i, q, a))

        def grade_short(job):
            i, q, a = job
            grade = self.llm.structured(
                Grade, lesson_templates.GRADE_SYS, lesson_templates.GRADE_HUMAN,
                question=q.prompt, reference_answer=q.reference_answer, answer=a)
            return i, self._item(i, q, a, grade)

        if short_jobs:                                             # parallel: 10 answers shouldn't take 10x
            with ThreadPoolExecutor(max_workers=config.GRADE_WORKERS) as pool:
                for i, item in pool.map(grade_short, short_jobs):  # re-raises the first failure
                    items[i] = item
        return items

    @staticmethod
    def _item(i, q: Question, answer, grade: Grade, skipped: bool = False) -> QuizItemResult:
        if q.kind == "mcq":
            your = q.options[answer] if isinstance(answer, int) else ""
            correct_answer = q.options[q.correct_index]
        else:
            your = answer or ""
            correct_answer = q.reference_answer
        return QuizItemResult(
            index=i, kind=q.kind, prompt=q.prompt, options=list(q.options),
            your_answer=your, correct_answer=correct_answer, score=grade.score,
            correct=grade.score >= config.CORRECT_SCORE, skipped=skipped, feedback=grade.feedback)

    @staticmethod
    def _build_result(items: list[QuizItemResult]) -> QuizResult:
        by_kind: dict[str, KindScore] = {}
        for kind in ("mcq", "short"):
            group = [it for it in items if it.kind == kind]
            if group:
                by_kind[kind] = KindScore(correct=sum(it.correct for it in group), total=len(group),
                                          score=round(sum(it.score for it in group) / len(group), 4))
        score = sum(it.score for it in items) / len(items)
        return QuizResult(score=round(score, 4), percent=round(score * 100),
                          correct_count=sum(it.correct for it in items), total=len(items),
                          skipped=sum(it.skipped for it in items), by_kind=by_kind, items=items)

    # ================================================================== internals
    def _load(self, quiz_id: str) -> dict:
        doc = self.store.get(self.user_id, quiz_id)
        if not doc:
            raise LessonNotFound("That quiz could not be found.")
        return doc

    @staticmethod
    def _require_answering(doc: dict) -> None:
        if doc["status"] != "active" or doc["phase"] != "answering":
            raise InvalidStateError("This quiz has already ended.")

    @staticmethod
    def _questions(doc: dict) -> list[Question]:
        return [Question(**q) for q in doc["questions"]]

    @staticmethod
    def _normalise(q: Question, answer):
        """mcq -> option index or None; short -> stripped text or None. Blank means 'skip'."""
        if answer is None or (isinstance(answer, str) and not answer.strip()):
            return None
        if q.kind == "mcq":
            if isinstance(answer, int) and not isinstance(answer, bool):
                idx = answer
            else:
                idx = next((i for i, opt in enumerate(q.options)
                            if opt.strip().lower() == str(answer).strip().lower()), None)
            if idx is None or not 0 <= idx < len(q.options):
                raise LessonError("Please choose one of the listed options.")
            return idx
        return str(answer).strip()[:2000]

    def _save(self, doc: dict) -> None:
        doc["updated_at"] = _now()
        self.store.save(doc)

    def _brief(self) -> str:
        profile_doc = self.db["student_profile"].find_one({"user_id": self.user_id}) or {}
        try:
            weak = weak_topics(self.db, self.user_id, 3)
        except Exception:
            weak = []
        return student_brief(profile_doc, weak)

    def _to_view(self, doc: dict) -> QuizView:
        questions = self._questions(doc)
        answering = doc["phase"] == "answering"
        drafts = {}
        for k, v in doc["answers"].items():
            q = questions[int(k)]
            drafts[int(k)] = q.options[v] if q.kind == "mcq" else v
        return QuizView(
            quiz_id=doc["quiz_id"], status=doc["status"], phase=doc["phase"], topic=doc["topic"],
            subject=doc["subject"], quiz_type=doc["quiz_type"], source=doc["source"],
            difficulty=doc["difficulty"], requested_total=doc["requested_total"], total=len(questions),
            questions=[PublicQuestion(index=i, kind=q.kind, prompt=q.prompt, options=list(q.options))
                       for i, q in enumerate(questions)] if answering else [],
            answers=drafts, answered_count=len(drafts), sources=doc.get("sources", []),
            result=QuizResult(**doc["result"]) if doc.get("result") else None,
        )
