"""Backend tests: no API key, no real MongoDB (uses mongomock).

Run from the project root:   python -m pytest lesson/tests -q
Dev dependencies:            pip install pytest mongomock
"""
import mongomock
import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from lesson import InvalidStateError, LessonEngine, LessonError, LLMGateway, LLMOutputError
from lesson.llm_utils import clean_model_text, extract_json
from lesson.models import (Check, Grade, LessonPlan, LessonSummary, ProfileDelta, Question,
                           Segment)
from lesson.profile import apply_delta, maybe_update_profile, update_profile_in_background
from lesson.progress import label, record_outcome, snapshot

USER = "ada"


class FakeGateway:
    """Scripted stand-in for the LLM."""
    def __init__(self, segments=3, short=False, short_score=0.5):
        self.segments, self.short, self.short_score = segments, short, short_score
        self.fail_grade = False
        self.fail_delta = False
        self.delta_calls = 0
        self.calls = []

    def text(self, system, human, **v):
        return f"Teaching: {v['title']} ({v.get('extra') or 'first pass'})"

    def structured(self, cls, system, human, **v):
        self.calls.append((cls, v))
        if cls is LessonPlan:
            return LessonPlan(subject="Science", topic=v["topic"],
                              segments=[Segment(title=f"Part {i+1}", objective=f"Goal {i+1}")
                                        for i in range(self.segments)])
        if cls is Check:
            qs = [Question(kind="mcq", prompt=f"MCQ for {v.get('objective') or v.get('topic')}",
                           options=["right", "w1", "w2", "w3"], correct_index=0, explanation="Because.")]
            if self.short:
                qs.append(Question(kind="short", prompt="Explain it", reference_answer="ref"))
            return Check(questions=qs)
        if cls is Grade:
            if self.fail_grade:
                raise LLMOutputError("grader down")
            return Grade(score=self.short_score, feedback="graded")
        if cls is LessonSummary:
            return LessonSummary(summary="Nice work", key_points=["a"], next_topic="Next")
        if cls is ProfileDelta:
            self.delta_calls += 1
            if self.fail_delta:
                raise LLMOutputError("delta down")
            return ProfileDelta(new_goals=["Learn cybernetics"], experience_level="beginner")
        raise AssertionError(cls)


@pytest.fixture
def db():
    d = mongomock.MongoClient()["tutor_test"]
    d["student_profile"].insert_one({"user_id": USER, "Profile": {
        "student": {"name": "Ada", "learning_goals": []},
        "background": {"experience_level": "unknown", "subjects_of_interest": []},
        "strengths": [], "weaknesses": [],
        "knowledge_progress": {"subjects": [], "topics": [], "knowledge_gaps": []},
        "learning_preferences": {}}})
    return d


def answers(engine, view, correct=True):
    """Read the answer key from storage (the view deliberately has none)."""
    doc = engine.store.get(USER, view.lesson_id)
    out = []
    for q in doc["check"]["questions"]:
        if q["kind"] == "mcq":
            idx = q["correct_index"] if correct else (q["correct_index"] + 1) % len(q["options"])
            out.append(q["options"][idx])
        else:
            out.append("my explanation")
    return out


def test_happy_path_and_progress(db):
    eng = LessonEngine(db, USER, gateway=FakeGateway(3))
    v = eng.start("Cybernetics")
    assert (v.phase, v.segment_index, v.segment_total) == ("teach", 0, 3)
    assert v.questions == []                       # no questions while reading
    for i in range(3):
        v = eng.go_to_check(v.lesson_id)
        assert v.phase == "check" and not hasattr(v.questions[0], "correct_index")
        v = eng.submit_answers(v.lesson_id, answers(eng, v))
        assert v.phase == "feedback" and v.result.outcome == "passed"
        v = eng.continue_lesson(v.lesson_id)
    assert v.phase == "done" and v.status == "completed"
    assert v.summary.summary == "Nice work" and v.summary.review_topics == []
    assert db["topic_progress"].count_documents({"user_id": USER}) == 3
    profile = db["student_profile"].find_one({"user_id": USER})["Profile"]
    assert len(profile["knowledge_progress"]["topics"]) == 3     # synced for the sidebar / free chat


def test_retry_then_pass(db):
    eng = LessonEngine(db, USER, gateway=FakeGateway(2))
    v = eng.start("Topic")
    v = eng.go_to_check(v.lesson_id)
    v = eng.submit_answers(v.lesson_id, answers(eng, v, correct=False))
    assert v.result.outcome == "retry" and v.result.attempt == 1
    v = eng.continue_lesson(v.lesson_id)
    assert (v.phase, v.segment_index, v.attempt) == ("teach", 0, 2)
    assert "different analogy" in v.content            # reteach hint reached the teacher
    v = eng.go_to_check(v.lesson_id)
    v = eng.submit_answers(v.lesson_id, answers(eng, v))
    assert v.result.outcome == "passed"
    v = eng.continue_lesson(v.lesson_id)
    assert v.segment_index == 1 and v.attempt == 1


def test_gap_after_max_attempts_then_moves_on(db):
    eng = LessonEngine(db, USER, gateway=FakeGateway(2))
    v = eng.start("Topic")
    for expected in ("retry", "retry", "gap"):
        v = eng.go_to_check(v.lesson_id)
        v = eng.submit_answers(v.lesson_id, answers(eng, v, correct=False))
        assert v.result.outcome == expected
        v = eng.continue_lesson(v.lesson_id)
    assert v.segment_index == 1                        # moved on instead of looping forever
    assert v.scores[0].outcome == "gap"
    row = db["topic_progress"].find_one({"topic": "Part 1"})
    assert row["mastery"] < 0.4 and label(row["mastery"]) == "struggling"


def test_gap_shows_in_summary(db):
    eng = LessonEngine(db, USER, gateway=FakeGateway(1))
    v = eng.start("Topic")
    for _ in range(3):
        v = eng.go_to_check(v.lesson_id)
        v = eng.submit_answers(v.lesson_id, answers(eng, v, correct=False))
        v = eng.continue_lesson(v.lesson_id)
    assert v.phase == "done" and v.summary.review_topics == ["Part 1"]


def test_phase_guards_and_double_submit(db):
    eng = LessonEngine(db, USER, gateway=FakeGateway(2))
    v = eng.start("Topic")
    with pytest.raises(InvalidStateError):
        eng.submit_answers(v.lesson_id, ["x"])         # still in teach phase
    v = eng.go_to_check(v.lesson_id)
    ans = answers(eng, v)
    eng.submit_answers(v.lesson_id, ans)
    with pytest.raises(InvalidStateError):
        eng.submit_answers(v.lesson_id, ans)           # double-click is harmless
    assert db["topic_progress"].find_one({"topic": "Part 1"})["attempts"] == 1


def test_invalid_answers_do_not_change_state(db):
    eng = LessonEngine(db, USER, gateway=FakeGateway(2, short=True))
    v = eng.start("Topic")
    v = eng.go_to_check(v.lesson_id)
    with pytest.raises(LessonError):
        eng.submit_answers(v.lesson_id, ["right"])     # one answer missing
    with pytest.raises(LessonError):
        eng.submit_answers(v.lesson_id, ["not an option", "text"])
    assert eng.get_view(v.lesson_id).phase == "check"


def test_short_answer_partial_credit_and_grader_failure(db):
    gw = FakeGateway(2, short=True, short_score=0.2)
    eng = LessonEngine(db, USER, gateway=gw)
    v = eng.start("Topic")
    v = eng.go_to_check(v.lesson_id)
    gw.fail_grade = True
    with pytest.raises(LLMOutputError):
        eng.submit_answers(v.lesson_id, answers(eng, v))
    assert eng.get_view(v.lesson_id).phase == "check"  # nothing saved, student can resubmit
    assert db["topic_progress"].count_documents({}) == 0
    gw.fail_grade = False
    v = eng.submit_answers(v.lesson_id, answers(eng, v))
    assert v.result.score == pytest.approx(0.6) and v.result.outcome == "retry"   # (1.0 + 0.2) / 2


def test_resume_and_replace_active(db):
    eng = LessonEngine(db, USER, gateway=FakeGateway(2))
    v1 = eng.start("First")
    eng.go_to_check(v1.lesson_id)
    resumed = LessonEngine(db, USER, gateway=FakeGateway(2)).get_active_view()
    assert resumed.lesson_id == v1.lesson_id and resumed.phase == "check"
    v2 = eng.start("Second")
    assert eng.get_active_view().lesson_id == v2.lesson_id
    assert eng.store.get(USER, v1.lesson_id)["status"] == "abandoned"
    with pytest.raises(InvalidStateError):
        eng.go_to_check(v1.lesson_id)
    with pytest.raises(LessonError):
        eng.start("Third", replace_active=False)


def test_failed_start_keeps_old_lesson(db):
    gw = FakeGateway(2)
    eng = LessonEngine(db, USER, gateway=gw)
    v1 = eng.start("First")
    gw.text = lambda *a, **k: (_ for _ in ()).throw(LLMOutputError("boom"))
    with pytest.raises(LLMOutputError):
        eng.start("Second")
    assert eng.get_active_view().lesson_id == v1.lesson_id


def test_mastery_moves_with_evidence(db):
    m1 = record_outcome(db, USER, "S", "T", 1.0)
    m2 = record_outcome(db, USER, "S", "T", 1.0)
    m3 = record_outcome(db, USER, "S", "T", 0.0)
    assert m1 < m2 and m3 < m2
    assert snapshot(db, USER)["topics"][0]["topic"] == "T"


def test_json_helpers():
    raw = '<think>hmm {not json}</think>\n```json\n{"score": 0.4, "feedback": "ok"}\n```'
    assert extract_json(raw) == {"score": 0.4, "feedback": "ok"}
    assert clean_model_text("reasoning</think>answer") == "answer"
    with pytest.raises(ValueError):
        extract_json("no braces here")


def test_gateway_json_fallback_and_retry():
    # FakeListChatModel has no native structured output -> exercises the JSON fallback
    model = FakeListChatModel(responses=["not json at all",
                                         '<think>x</think>```json\n{"score": 1.4, "feedback": "f"}\n```'])
    gw = LLMGateway(teacher=FakeListChatModel(responses=["hello"]), structured_model=model)
    grade = gw.structured(Grade, "Grade it.", "Answer: {a}", a="x")
    assert grade.score == 1.0                          # clamped
    assert gw.text("Say hi.", "go") == "hello"


def test_gateway_gives_up_with_friendly_error():
    gw = LLMGateway(structured_model=FakeListChatModel(responses=["garbage"]))
    with pytest.raises(LLMOutputError) as exc:
        gw.structured(Grade, "Grade it.", "go")
    assert "try again" in str(exc.value).lower() and exc.value.detail


def test_apply_delta_validates_and_dedupes():
    profile = {"student": {"learning_goals": ["Pass exams"]},
               "background": {"experience_level": "unknown", "subjects_of_interest": []},
               "learning_preferences": {"pace": "unknown"}}
    delta = ProfileDelta(new_goals=["pass exams", "Learn ML"], new_interests=["AI"],
                         experience_level="intermediate",
                         preference_updates={"pace": "fast", "examples": "banana", "nonsense": "preferred"})
    new = apply_delta(profile, delta)
    assert new["student"]["learning_goals"] == ["Pass exams", "Learn ML"]
    assert new["background"]["experience_level"] == "intermediate"
    assert new["learning_preferences"] == {"pace": "fast"}      # invalid key/value dropped
    assert profile["learning_preferences"] == {"pace": "unknown"}   # input untouched


def test_bad_model_output_is_rejected_by_models():
    with pytest.raises(ValueError):
        Question(kind="mcq", prompt="q", options=["a", "b"], correct_index=5)
    with pytest.raises(ValueError):
        Check(questions=[])


# ------------------------------------------------------ automatic profile updates
def add_turns(db, n, start=0):
    from datetime import datetime, timedelta, timezone
    base = datetime.now(timezone.utc)
    for i in range(start, start + n):
        db["conversation"].insert_one({"user_id": USER, "session_id": "s1", "created_at": base + timedelta(seconds=i),
                                       "conversations": [{"user_input": f"q{i}", "ai_response": f"a{i}"}]})


def test_auto_update_waits_for_threshold_then_marks_turns(db):
    gw = FakeGateway()
    add_turns(db, 5)
    assert maybe_update_profile(db, USER, gateway=gw) is False and gw.delta_calls == 0
    add_turns(db, 1, start=5)
    assert maybe_update_profile(db, USER, gateway=gw) is True
    assert db["conversation"].count_documents({"profiled": True}) == 6
    p = db["student_profile"].find_one({"user_id": USER})["Profile"]
    assert p["student"]["learning_goals"] == ["Learn cybernetics"]
    assert p["background"]["experience_level"] == "beginner"
    assert maybe_update_profile(db, USER, gateway=gw) is False       # nothing new -> no extra LLM call
    assert gw.delta_calls == 1


def test_auto_update_force_and_lesson_progress_untouched(db):
    gw = FakeGateway()
    eng = LessonEngine(db, USER, gateway=gw)
    v = eng.start("Topic")
    v = eng.go_to_check(v.lesson_id)
    eng.submit_answers(v.lesson_id, answers(eng, v))
    add_turns(db, 1)
    assert maybe_update_profile(db, USER, force=True, gateway=gw) is False   # 1 turn < forced minimum
    add_turns(db, 1, start=1)
    assert maybe_update_profile(db, USER, force=True, gateway=gw) is True
    p = db["student_profile"].find_one({"user_id": USER})["Profile"]
    assert len(p["knowledge_progress"]["topics"]) == 1               # code-owned progress survived


def test_auto_update_failure_keeps_turns_and_cools_down(db):
    gw = FakeGateway()
    gw.fail_delta = True
    add_turns(db, 6)
    assert maybe_update_profile(db, USER, gateway=gw) is False
    assert db["conversation"].count_documents({"profiled": True}) == 0     # still pending
    assert "delta down" in db["student_profile"].find_one({"user_id": USER})["profile_sync"]["last_error"]
    gw.fail_delta = False
    calls = gw.delta_calls
    assert maybe_update_profile(db, USER, gateway=gw) is False              # cooling down
    assert gw.delta_calls == calls
    assert maybe_update_profile(db, USER, force=True, gateway=gw) is True   # force bypasses cooldown
    assert db["conversation"].count_documents({"profiled": True}) == 6


def test_background_update_runs_off_thread(db):
    gw = FakeGateway()
    add_turns(db, 6)
    update_profile_in_background(db, USER, gateway=gw).join(timeout=5)
    assert db["conversation"].count_documents({"profiled": True}) == 6


# ------------------------------------------------------------ spaced review
def make_due(db, gw, segments=2):
    """Finish `segments` lesson segments, then make every topic overdue for review."""
    from datetime import datetime, timedelta, timezone
    eng = LessonEngine(db, USER, gateway=gw)
    v = eng.start("Topic")
    for _ in range(segments):
        v = eng.go_to_check(v.lesson_id)
        v = eng.submit_answers(v.lesson_id, answers(eng, v))
        v = eng.continue_lesson(v.lesson_id)
    db["topic_progress"].update_many({}, {"$set": {"next_review": datetime.now(timezone.utc) - timedelta(days=1)}})
    return eng


def test_review_nothing_due(db):
    eng = LessonEngine(db, USER, gateway=FakeGateway(2))
    assert eng.due_summary()["count"] == 0
    with pytest.raises(LessonError):
        eng.start_review()
    v = eng.start("Topic")                                   # a fresh lesson schedules reviews in the future
    v = eng.go_to_check(v.lesson_id)
    eng.submit_answers(v.lesson_id, answers(eng, v))
    s = eng.due_summary()
    assert s["count"] == 0 and s["next_due"] is not None


def test_review_flow_updates_mastery_and_schedule(db):
    gw = FakeGateway(2)
    eng = make_due(db, gw, 2)
    assert eng.due_summary()["count"] == 2
    before = {r["topic"]: r["mastery"] for r in db["topic_progress"].find()}
    v = eng.start_review()
    assert (v.mode, v.phase, v.content, v.segment_total) == ("review", "check", "", 2)
    first_check = [c for c in gw.calls if c[0] is Check][-1][1]
    assert "Teaching:" in first_check["source_text"]         # grounded in what the student studied
    for _ in range(2):
        assert v.phase == "check"
        v = eng.submit_answers(v.lesson_id, answers(eng, v))
        assert v.result.outcome == "passed"
        v = eng.continue_lesson(v.lesson_id)
    assert v.phase == "done" and v.mode == "review" and "2 topic" in v.summary.summary
    rows = list(db["topic_progress"].find())
    assert len(rows) == 2                                    # same rows updated, no "Review" subject created
    assert all(r["mastery"] > before[r["topic"]] and r["subject"] == "Science" for r in rows)
    assert eng.due_summary()["count"] == 0                   # review dates pushed into the future


def test_review_failure_reteaches_then_marks_gap(db):
    gw = FakeGateway(2)
    eng = make_due(db, gw, 1)
    v = eng.start_review()
    v = eng.submit_answers(v.lesson_id, answers(eng, v, correct=False))
    assert v.result.outcome == "retry" and v.max_attempts == 2
    v = eng.continue_lesson(v.lesson_id)
    assert v.phase == "teach" and "different analogy" in v.content      # short re-teach
    v = eng.go_to_check(v.lesson_id)
    v = eng.submit_answers(v.lesson_id, answers(eng, v, correct=False))
    assert v.result.outcome == "gap"
    v = eng.continue_lesson(v.lesson_id)
    assert v.phase == "done" and v.summary.review_topics == ["Part 1"]


def test_review_replaces_active_lesson(db):
    gw = FakeGateway(2)
    eng = make_due(db, gw, 1)                                # leaves a lesson active at segment 2
    old = eng.get_active_view().lesson_id
    v = eng.start_review()
    assert eng.get_active_view().lesson_id == v.lesson_id
    assert eng.store.get(USER, old)["status"] == "abandoned"
    with pytest.raises(LessonError):
        eng.start_review(replace_active=False)
