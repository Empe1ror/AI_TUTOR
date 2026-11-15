"""The lesson state machine.

    start() -> [teach] -go_to_check()-> [check] -submit_answers()-> [feedback]
                 ^                                                      |
                 |----- continue_lesson() (retry: same segment) <-------|
                                          (pass / gap: next segment, or done)

Code owns the flow and the numbers; the LLM only fills in content (plan, teaching text,
questions, short-answer grades, summary). Every public method returns a LessonView and
persists the lesson after each step, so a lesson can be resumed after a refresh.

If an LLM call fails mid-step, nothing is saved: the stored lesson is unchanged and the
same call can simply be retried.
"""
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from . import config, templates
from .errors import InvalidStateError, LessonError, LessonNotFound, LLMOutputError
from .llm_utils import LLMGateway
from .models import (AttemptResult, Check, Grade, LessonPlan, LessonSummary, LessonView,
                     PublicQuestion, Question, QuestionResult, SegmentScore)
from .profile import student_brief
from .progress import due_for_review, due_summary, record_outcome, sync_to_profile, weak_topics
from .store import LessonStore

log = logging.getLogger(__name__)

Retriever = Callable[[str], tuple]   # query -> (context_text, sources)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class LessonEngine:
    def __init__(self, db, user_id: str, *, gateway: Optional[LLMGateway] = None,
                 retriever: Optional[Retriever] = None):
        if db is None:
            raise RuntimeError("MongoDB is not configured.")
        self.db = db
        self.user_id = user_id.strip().lower()
        if not self.user_id:
            raise ValueError("A student identifier is required.")
        self.store = LessonStore(db)
        self.llm = gateway or LLMGateway()
        self.retriever = retriever

    # ================================================================== public API
    def start(self, topic: str, *, replace_active: bool = True) -> LessonView:
        topic = (topic or "").strip()
        if len(topic) < 2:
            raise LessonError("Tell me what you'd like to learn.")

        active = self.store.get_active(self.user_id)
        if active and not replace_active:
            raise LessonError("You already have a lesson in progress.")

        context, _ = self._retrieve(topic)
        plan = self.llm.structured(
            LessonPlan, templates.PLAN_SYS, templates.PLAN_HUMAN,
            topic=topic, student_brief=self._brief(), context=context,
            min_segments=config.MIN_SEGMENTS, max_segments=config.MAX_SEGMENTS,
            words=config.SEGMENT_WORDS,
        )
        segments = [s for s in plan.segments if s.title.strip()][:config.MAX_SEGMENTS]
        if not segments:
            raise LLMOutputError("I couldn't plan that lesson. Try rephrasing the topic.")

        now = _now()
        doc = {
            "lesson_id": uuid.uuid4().hex, "user_id": self.user_id,
            "subject": plan.subject.strip() or "General", "topic": plan.topic.strip() or topic,
            "segments": [s.model_dump() for s in segments],
            "mode": "lesson", "max_attempts": config.MAX_ATTEMPTS,
            "current": 0, "phase": "teach", "status": "active", "attempts": 0,
            "segment_text": "", "check": {"questions": []}, "sources": [],
            "last_result": None, "scores": [], "summary": None,
            "created_at": now, "updated_at": now,
        }
        self._prepare_segment(doc)          # may raise; nothing has been saved yet
        if active:                          # only now is it safe to retire the old lesson
            active["status"] = "abandoned"
            self._save(active)
        self.store.create(doc)
        return self._to_view(doc)

    def due_summary(self) -> dict:
        """{'count': n, 'next_due': datetime|None} for a "3 topics due" badge."""
        return due_summary(self.db, self.user_id)

    def start_review(self, max_topics: Optional[int] = None, *, replace_active: bool = True) -> LessonView:
        """Spaced review: quiz the learner on topics whose review date has arrived.

        Starts directly at the check (no re-teaching). A wrong answer triggers a short
        re-teach and a fresh check, exactly like a lesson; results feed the same mastery.
        """
        rows = due_for_review(self.db, self.user_id, max_topics or config.REVIEW_MAX_TOPICS)
        if not rows:
            raise LessonError("Nothing is due for review right now. Nice work!")
        active = self.store.get_active(self.user_id)
        if active and not replace_active:
            raise LessonError("You already have a lesson in progress.")

        now = _now()
        doc = {
            "lesson_id": uuid.uuid4().hex, "user_id": self.user_id,
            "subject": "Review", "topic": "Review session",
            "segments": [{"title": r["topic"], "objective": f"Recall and apply: {r['topic']}",
                          "subject": r.get("subject", ""), "parent_topic": r.get("parent_topic", ""),
                          "source_text": r.get("source_text", "")} for r in rows],
            "mode": "review", "max_attempts": config.REVIEW_MAX_ATTEMPTS,
            "current": 0, "phase": "check", "status": "active", "attempts": 0,
            "segment_text": "", "check": {"questions": []}, "sources": [],
            "last_result": None, "scores": [], "summary": None,
            "created_at": now, "updated_at": now,
        }
        self._prepare_segment(doc)          # may raise; nothing has been saved yet
        if active:
            active["status"] = "abandoned"
            self._save(active)
        self.store.create(doc)
        return self._to_view(doc)

    def get_active_view(self) -> Optional[LessonView]:
        doc = self.store.get_active(self.user_id)
        return self._to_view(doc) if doc else None

    def get_view(self, lesson_id: str) -> LessonView:
        return self._to_view(self._load(lesson_id))

    def go_to_check(self, lesson_id: str) -> LessonView:
        """The student finished reading (or clicked "I already know this")."""
        doc = self._load(lesson_id)
        self._require(doc, "teach")
        doc["phase"] = "check"
        self._save(doc)
        return self._to_view(doc)

    def submit_answers(self, lesson_id: str, answers: list) -> LessonView:
        """answers: one per question, in order. mcq: option text or index; short: text."""
        doc = self._load(lesson_id)
        self._require(doc, "check")
        questions = [Question(**q) for q in doc["check"]["questions"]]
        cleaned = self._normalise_answers(questions, answers)

        results: list[QuestionResult] = []
        for i, (q, a) in enumerate(zip(questions, cleaned)):
            grade = self._grade(q, a)       # may raise LLMOutputError -> state unchanged
            results.append(QuestionResult(
                index=i, kind=q.kind, prompt=q.prompt, score=grade.score,
                correct=grade.score >= config.PASS_SCORE, feedback=grade.feedback,
                correct_answer=q.options[q.correct_index] if q.kind == "mcq" else "",
            ))
        score = sum(r.score for r in results) / len(results)
        attempt = doc["attempts"] + 1
        max_attempts = doc.get("max_attempts", config.MAX_ATTEMPTS)
        if score >= config.PASS_SCORE:
            outcome = "passed"
        elif attempt >= max_attempts:
            outcome = "gap"
        else:
            outcome = "retry"

        if outcome != "retry":              # safe to reveal reference answers now
            for r, q in zip(results, questions):
                if q.kind == "short":
                    r.correct_answer = q.reference_answer

        seg = doc["segments"][doc["current"]]
        doc["attempts"] = attempt
        doc["phase"] = "feedback"
        doc["last_result"] = AttemptResult(
            attempt=attempt, score=round(score, 4), passed=outcome == "passed",
            outcome=outcome, questions=results).model_dump()
        if outcome != "retry":
            doc["scores"].append(SegmentScore(
                index=doc["current"], title=seg["title"], score=round(score, 4),
                attempts=attempt, outcome=outcome).model_dump())
        self._save(doc)

        try:                                # evidence -> mastery (pure code); never blocks the lesson
            record_outcome(self.db, self.user_id, seg.get("subject") or doc["subject"], seg["title"],
                           score, parent_topic=seg.get("parent_topic") or doc["topic"],
                           source_text=doc.get("segment_text", ""))
            sync_to_profile(self.db, self.user_id)
        except Exception:
            log.exception("progress update failed")
        return self._to_view(doc)

    def continue_lesson(self, lesson_id: str) -> LessonView:
        """After feedback: re-teach the segment (retry), move on, or finish the lesson."""
        doc = self._load(lesson_id)
        self._require(doc, "feedback")
        res = doc["last_result"]

        if res["outcome"] == "retry":
            missed = "; ".join(q["prompt"] for q in res["questions"] if not q["correct"])
            hint = ("The student did not pass the check on this segment. Re-teach the SAME idea "
                    "in a fresh way: use a different analogy and simpler wording. "
                    f"They got these wrong: {missed}")
            self._prepare_segment(doc, reteach_hint=hint)
        else:
            doc["current"] += 1
            doc["attempts"] = 0
            if doc["current"] >= len(doc["segments"]):
                self._finish(doc)
            else:
                self._prepare_segment(doc)
        self._save(doc)
        return self._to_view(doc)

    def abandon(self, lesson_id: str) -> None:
        doc = self._load(lesson_id)
        if doc["status"] == "active":
            doc["status"] = "abandoned"
            self._save(doc)

    def list_lessons(self, limit: int = 10) -> list[dict]:
        return self.store.list_recent(self.user_id, limit)

    # ================================================================== internals
    def _load(self, lesson_id: str) -> dict:
        doc = self.store.get(self.user_id, lesson_id)
        if not doc:
            raise LessonNotFound("That lesson could not be found.")
        return doc

    @staticmethod
    def _require(doc: dict, phase: str) -> None:
        if doc["status"] != "active":
            raise InvalidStateError("This lesson has ended.")
        if doc["phase"] != phase:
            raise InvalidStateError("That action isn't available at this step of the lesson.",
                                    detail=f"lesson is in phase '{doc['phase']}', expected '{phase}'")

    def _save(self, doc: dict) -> None:
        doc["updated_at"] = _now()
        self.store.save(doc)

    def _brief(self) -> str:
        profile_doc = self.db[config.PROFILE_COLLECTION].find_one({"user_id": self.user_id}) or {}
        try:
            weak = weak_topics(self.db, self.user_id, 3)
        except Exception:
            weak = []
        return student_brief(profile_doc, weak)

    def _retrieve(self, query: str) -> tuple[str, list[dict]]:
        if not self.retriever:
            return config.NO_CONTEXT, []
        try:
            context, sources = self.retriever(query)
        except Exception:
            log.exception("retrieval failed; continuing without documents")
            return config.NO_CONTEXT, []
        trimmed = [{**s, "text": str(s.get("text", ""))[:400]} for s in (sources or [])]
        return context or config.NO_CONTEXT, trimmed

    def _prepare_segment(self, doc: dict, reteach_hint: str = "") -> None:
        """Generate the content for the current segment (mutates doc).

        lesson, or review after a failed check: teaching text, then a check.
        review, first pass: just a recall check (no re-teaching).
        """
        seg = doc["segments"][doc["current"]]
        parent = seg.get("parent_topic") or doc["topic"]
        context, sources = self._retrieve(f"{parent} {seg['title']} {seg['objective']}")
        avoid = "\n".join(f"- {q['prompt']}" for q in doc["check"]["questions"]) or "none"

        if doc.get("mode") == "review" and not reteach_hint:
            check = self.llm.structured(
                Check, templates.REVIEW_CHECK_SYS, templates.CHECK_HUMAN,
                topic=seg["title"], parent_topic=parent,
                source_text=seg.get("source_text") or "(not available: rely on well-established knowledge of the topic)",
                context=context, avoid=avoid, max_questions=config.MAX_QUESTIONS,
            )
            text, phase = "", "check"
        else:
            text = self.llm.text(
                templates.TEACH_SYS, templates.TEACH_HUMAN,
                student_brief=self._brief(), topic=parent, n=doc["current"] + 1,
                total=len(doc["segments"]), title=seg["title"], objective=seg["objective"],
                context=context, extra=reteach_hint, words=config.SEGMENT_WORDS,
            )
            check = self.llm.structured(
                Check, templates.CHECK_SYS, templates.CHECK_HUMAN,
                objective=seg["objective"], segment_text=text, context=context,
                avoid=avoid, max_questions=config.MAX_QUESTIONS,
            )
            phase = "teach"
        questions = self._prepare_questions(check)
        doc.update(segment_text=text, sources=sources, phase=phase, last_result=None,
                   check={"questions": [q.model_dump() for q in questions]})

    @staticmethod
    def _prepare_questions(check: Check) -> list[Question]:
        questions = list(check.questions)[:config.MAX_QUESTIONS]
        for q in questions:
            if q.kind == "mcq":             # models like to put the answer first: shuffle in code
                correct = q.options[q.correct_index]
                options = list(q.options)
                random.shuffle(options)
                q.options, q.correct_index = options, options.index(correct)
        return questions

    @staticmethod
    def _normalise_answers(questions: list[Question], answers) -> list:
        if not isinstance(answers, (list, tuple)) or len(answers) != len(questions):
            raise LessonError("Please answer every question before submitting.")
        out = []
        for q, a in zip(questions, answers):
            if q.kind == "mcq":
                idx = None
                if isinstance(a, int) and not isinstance(a, bool):
                    idx = a
                elif isinstance(a, str):
                    for i, opt in enumerate(q.options):
                        if opt.strip().lower() == a.strip().lower():
                            idx = i
                            break
                if idx is None or not 0 <= idx < len(q.options):
                    raise LessonError("Please choose one option for each multiple-choice question.")
                out.append(idx)
            else:
                text = str(a or "").strip()
                if not text:
                    raise LessonError("Please write an answer for every question.")
                out.append(text[:2000])
        return out

    def _grade(self, q: Question, answer) -> Grade:
        if q.kind == "mcq":                 # graded by code: reliable and free
            ok = answer == q.correct_index
            return Grade(score=1.0 if ok else 0.0,
                         feedback=q.explanation or ("Correct." if ok else "Not quite."))
        return self.llm.structured(
            Grade, templates.GRADE_SYS, templates.GRADE_HUMAN,
            question=q.prompt, reference_answer=q.reference_answer, answer=answer,
        )

    def _finish(self, doc: dict) -> None:
        doc["status"], doc["phase"], doc["completed_at"] = "completed", "done", _now()
        scores = doc["scores"]
        review = [s["title"] for s in scores if s["outcome"] == "gap"]
        if doc.get("mode") == "review":     # plain code summary: no extra LLM call
            passed = [s["title"] for s in scores if s["outcome"] == "passed"]
            doc["summary"] = LessonSummary(
                summary=f"You reviewed {len(scores)} topic(s): {len(passed)} solid, {len(review)} need more practice.",
                key_points=passed, review_topics=review).model_dump()
            return
        results = "\n".join(
            f"- {s['title']}: {round(s['score'] * 100)}% ({s['outcome']}, {s['attempts']} attempt(s))"
            for s in scores)
        try:
            summary = self.llm.structured(LessonSummary, templates.SUMMARY_SYS,
                                          templates.SUMMARY_HUMAN, topic=doc["topic"], results=results)
        except Exception:                   # the wrap-up is a nicety: never fail the lesson over it
            log.exception("summary generation failed; using a plain one")
            summary = LessonSummary(
                summary=f"You worked through all {len(doc['segments'])} parts of {doc['topic']}.",
                key_points=[s["title"] for s in scores if s["outcome"] == "passed"])
        summary.review_topics = review
        doc["summary"] = summary.model_dump()

    def _to_view(self, doc: dict) -> LessonView:
        segments = doc["segments"]
        idx = min(doc["current"], len(segments) - 1)
        seg = segments[idx]
        phase = doc["phase"]
        questions = []
        if phase == "check":
            questions = [PublicQuestion(index=i, kind=q["kind"], prompt=q["prompt"],
                                        options=list(q.get("options", [])))
                         for i, q in enumerate(doc["check"]["questions"])]
        return LessonView(
            lesson_id=doc["lesson_id"], status=doc["status"], mode=doc.get("mode", "lesson"), phase=phase,
            subject=doc["subject"], topic=doc["topic"],
            outline=[s["title"] for s in segments],
            segment_index=idx, segment_total=len(segments),
            segment_title=seg["title"], objective=seg["objective"],
            content=doc.get("segment_text", "") if phase != "done" else "",
            questions=questions,
            result=AttemptResult(**doc["last_result"]) if phase == "feedback" and doc.get("last_result") else None,
            sources=doc.get("sources", []) if phase != "done" else [],
            attempt=doc["attempts"] if phase in ("feedback", "done") else doc["attempts"] + 1,
            max_attempts=doc.get("max_attempts", config.MAX_ATTEMPTS),
            scores=[SegmentScore(**s) for s in doc["scores"]],
            summary=LessonSummary(**doc["summary"]) if phase == "done" and doc.get("summary") else None,
        )
