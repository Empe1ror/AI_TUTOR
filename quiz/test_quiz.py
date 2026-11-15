"""Quiz backend tests: no API key, no real MongoDB.

Run from the project root:   python -m pytest quiz/tests -q
"""
import itertools

import mongomock
import pytest

from lesson.models import Grade, Question
from quiz import InvalidStateError, LessonError, LLMOutputError, QuizEngine
from quiz.models import QuizBatch

USER = "ada"


class FakeGateway:
    """Scripted LLM: writes `per_call` questions per request (or fewer, to test top-ups)."""
    def __init__(self, per_call=None, grade=0.5):
        self.per_call, self.grade_score = per_call, grade
        self.fail_grade, self.duplicate = False, False
        self.calls = []
        self._n = itertools.count()

    def structured(self, cls, system, human, **v):
        self.calls.append((cls, v))
        if cls is Grade:
            if self.fail_grade:
                raise LLMOutputError("grader down")
            return Grade(score=self.grade_score, feedback="graded")
        assert cls is QuizBatch
        kind = "mcq" if "multiple-choice" in v["kind_label"] else "short"
        n = min(v["count"], self.per_call or v["count"])
        qs = []
        for _ in range(n):
            i = 0 if self.duplicate else next(self._n)
            if kind == "mcq":
                qs.append(Question(kind="mcq", prompt=f"MCQ {i}?", options=["right", "w1", "w2", "w3"],
                                   correct_index=0, explanation="Because."))
            else:
                qs.append(Question(kind="short", prompt=f"Explain {i}", reference_answer="the key idea"))
        return QuizBatch(subject="Science", questions=qs)


@pytest.fixture
def db():
    d = mongomock.MongoClient()["quiz_test"]
    d["student_profile"].insert_one({"user_id": USER, "Profile": {
        "student": {"name": "Ada", "learning_goals": []},
        "background": {"experience_level": "unknown", "subjects_of_interest": []},
        "strengths": [], "weaknesses": [],
        "knowledge_progress": {"subjects": [], "topics": [], "knowledge_gaps": []},
        "learning_preferences": {}}})
    return d


def key(engine, view):
    return engine.store.get(USER, view.quiz_id)["questions"]


def correct_answers(engine, view):
    out = []
    for q in key(engine, view):
        out.append(q["options"][q["correct_index"]] if q["kind"] == "mcq" else "my answer")
    return out


def test_quiz_sizes_by_type(db):
    for qtype, mcq, short in (("mcq", 10, 0), ("short", 0, 10), ("mixed", 8, 7)):
        v = QuizEngine(db, USER, gateway=FakeGateway()).start("Photosynthesis", qtype)
        kinds = [q.kind for q in v.questions]
        assert (kinds.count("mcq"), kinds.count("short")) == (mcq, short), qtype
        assert v.total == v.requested_total == mcq + short
        assert not hasattr(v.questions[0], "correct_index")        # no answer keys for the frontend
    assert [q.kind for q in v.questions] == ["mcq"] * 8 + ["short"] * 7   # grouped, mcq first


def test_mcq_quiz_full_marks_updates_mastery(db):
    eng = QuizEngine(db, USER, gateway=FakeGateway())
    v = eng.start("Photosynthesis", "mcq")
    v = eng.submit(v.quiz_id, correct_answers(eng, v))
    assert v.phase == "done" and v.status == "completed"
    assert v.result.percent == 100 and v.result.correct_count == 10 and v.result.by_kind["mcq"].total == 10
    row = db["topic_progress"].find_one({"topic": "Photosynthesis"})
    assert row["subject"] == "Science" and row["mastery"] > 0.5
    p = db["student_profile"].find_one({"user_id": USER})["Profile"]
    assert p["knowledge_progress"]["topics"][0]["topic"] == "Photosynthesis"


def test_options_are_shuffled(db):
    positions = set()
    for _ in range(6):
        v = QuizEngine(db, USER, gateway=FakeGateway()).start("T1", "mcq")
        positions |= {q["correct_index"] for q in key(QuizEngine(db, USER), v)}
    assert len(positions) > 1


def test_short_quiz_graded_by_llm_with_partial_credit(db):
    gw = FakeGateway(grade=0.5)
    eng = QuizEngine(db, USER, gateway=gw)
    v = eng.start("Photosynthesis", "short")
    v = eng.submit(v.quiz_id, ["an answer"] * 10)
    assert sum(1 for c in gw.calls if c[0] is Grade) == 10
    assert v.result.score == pytest.approx(0.5) and v.result.correct_count == 0   # 0.5 < pass mark
    assert v.result.items[0].correct_answer == "the key idea"


def test_mixed_quiz_scores_per_kind(db):
    eng = QuizEngine(db, USER, gateway=FakeGateway(grade=1.0))
    v = eng.start("Photosynthesis", "mixed")
    v = eng.submit(v.quiz_id, correct_answers(eng, v))
    assert v.result.total == 15 and v.result.percent == 100
    assert (v.result.by_kind["mcq"].total, v.result.by_kind["short"].total) == (8, 7)


def test_top_up_rounds_fill_short_batches(db):
    gw = FakeGateway(per_call=6)
    v = QuizEngine(db, USER, gateway=gw).start("Photosynthesis", "mcq")
    assert v.total == 10 and sum(1 for c in gw.calls if c[0] is QuizBatch) == 2


def test_accepts_slightly_short_quiz_but_reports_it(db):
    v = QuizEngine(db, USER, gateway=FakeGateway(per_call=3)).start("Photosynthesis", "mcq")
    assert v.total == 9 and v.requested_total == 10            # 3 rounds x 3 = 9 >= 70%


def test_too_few_questions_fails_cleanly(db):
    eng = QuizEngine(db, USER, gateway=FakeGateway(per_call=1))
    with pytest.raises(LLMOutputError):
        eng.start("Photosynthesis", "mcq")
    assert db["quizzes"].count_documents({}) == 0


def test_duplicates_are_removed(db):
    gw = FakeGateway(per_call=3)
    gw.duplicate = True
    with pytest.raises(LLMOutputError):
        QuizEngine(db, USER, gateway=gw).start("Photosynthesis", "mcq")   # only 1 unique question exists


def test_documents_source(db):
    with pytest.raises(LessonError):                                      # no retriever
        QuizEngine(db, USER, gateway=FakeGateway()).start("Cells", "mcq", "documents")
    with pytest.raises(LessonError):                                      # nothing relevant found
        QuizEngine(db, USER, gateway=FakeGateway(), retriever=lambda q: ("No docs", [])).start("Cells", "mcq", "documents")
    gw = FakeGateway()
    sources = [{"n": 1, "label": "bio.pdf, page 2", "score": 0.9, "text": "x" * 900}]
    eng = QuizEngine(db, USER, gateway=gw, retriever=lambda q: ("[1] Cells divide by mitosis.", sources))
    v = eng.start("Cells", "mixed", "documents")
    gen = [c[1] for c in gw.calls if c[0] is QuizBatch][0]
    assert "ONLY" in gen["source_rule"] and "mitosis" in gen["context"]
    assert v.source == "documents" and v.sources[0]["label"] == "bio.pdf, page 2"
    assert len(v.sources[0]["text"]) == 400
    v = eng.submit(v.quiz_id, correct_answers(eng, v))
    assert "mitosis" in db["topic_progress"].find_one({"topic": "Cells"})["source_text"]   # grounds later reviews


def test_drafts_resume_and_skips(db):
    eng = QuizEngine(db, USER, gateway=FakeGateway())
    v = eng.start("Photosynthesis", "mcq")
    q0 = key(eng, v)[0]
    eng.save_answer(v.quiz_id, 0, q0["options"][q0["correct_index"]])
    eng.save_answer(v.quiz_id, 1, 0)                         # integer index also accepted
    resumed = QuizEngine(db, USER).get_active_view()
    assert resumed.quiz_id == v.quiz_id and resumed.answered_count == 2
    assert resumed.answers[0] == q0["options"][q0["correct_index"]]
    eng.save_answer(v.quiz_id, 1, "")                       # clearing a draft
    assert eng.get_view(v.quiz_id).answered_count == 1
    v = eng.submit(v.quiz_id)                               # uses drafts; the 9 blanks are skipped
    assert v.result.skipped == 9 and v.result.correct_count == 1 and v.result.percent == 10


def test_submit_validation_and_state_unchanged(db):
    eng = QuizEngine(db, USER, gateway=FakeGateway())
    v = eng.start("Photosynthesis", "mcq")
    with pytest.raises(LessonError):
        eng.submit(v.quiz_id, ["only one"])
    with pytest.raises(LessonError):
        eng.submit(v.quiz_id, ["not an option"] * 10)
    with pytest.raises(LessonError):
        eng.save_answer(v.quiz_id, 50, "x")
    assert eng.get_view(v.quiz_id).phase == "answering"


def test_grader_failure_changes_nothing_and_double_submit_blocked(db):
    gw = FakeGateway()
    eng = QuizEngine(db, USER, gateway=gw)
    v = eng.start("Photosynthesis", "short")
    gw.fail_grade = True
    with pytest.raises(LLMOutputError):
        eng.submit(v.quiz_id, ["a"] * 10)
    assert eng.get_view(v.quiz_id).phase == "answering" and db["topic_progress"].count_documents({}) == 0
    gw.fail_grade = False
    eng.submit(v.quiz_id, ["a"] * 10)
    with pytest.raises(InvalidStateError):
        eng.submit(v.quiz_id, ["a"] * 10)
    assert db["topic_progress"].find_one({})["attempts"] == 1


def test_input_validation_and_replace_active(db):
    eng = QuizEngine(db, USER, gateway=FakeGateway())
    for bad in (dict(topic="x"), dict(topic="Cells", quiz_type="essay"),
                dict(topic="Cells", source="web"), dict(topic="Cells", difficulty="insane")):
        with pytest.raises(LessonError):
            eng.start(**bad)
    v1 = eng.start("Cells", "mcq")
    v2 = eng.start("Atoms", "mcq")
    assert eng.get_active_view().quiz_id == v2.quiz_id
    assert eng.store.get(USER, v1.quiz_id)["status"] == "abandoned"
    with pytest.raises(LessonError):
        eng.start("Ions", "mcq", replace_active=False)
    assert {q["topic"] for q in eng.list_quizzes()} == {"Cells", "Atoms"}


def test_batch_drops_invalid_questions_but_not_all():
    good = {"kind": "mcq", "prompt": "q", "options": ["a", "b"], "correct_index": 1}
    bad = {"kind": "mcq", "prompt": "q2", "options": ["a", "b"], "correct_index": 9}
    assert len(QuizBatch.model_validate({"questions": [good, bad]}).questions) == 1
    with pytest.raises(ValueError):
        QuizBatch.model_validate({"questions": [bad]})
