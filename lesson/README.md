# lesson/ — Lesson mode for Renewed AI Tutor

Structured, segment-by-segment lessons with a quiz check before the learner moves on,
plus code-owned progress tracking. Free chat is untouched: the learner picks the mode.

```
lesson/
├── __init__.py        public API (LessonEngine, errors, helpers)
├── config.py          pass mark, attempts, segment size... (env-overridable)
├── errors.py          LessonError family (messages safe to show the learner)
├── models.py          Pydantic schemas: LLM outputs + LessonView (what the frontend gets)
├── templates.py       lesson prompts (separate from the main tutor prompt on purpose)
├── llm_utils.py       LLMGateway: structured output with JSON fallback, <think> stripping, retries
├── engine.py          the lesson state machine
├── store.py           MongoDB persistence for lessons
├── progress.py        code-owned mastery (topic_progress) + sync into student_profile
├── profile.py         small LLM "delta" for goals/interests/preferences (replaces JsonOutputParser)
├── adapters.py        rag_retriever(user_id) -> plugs the existing rag package in
├── cli.py             terminal test harness:   python -m lesson.cli
├── streamlit_demo.py  throwaway test view for Streamlit
└── tests/             23 tests, no API key or MongoDB needed
```

## 1. Install

Copy the `lesson/` folder into the project root (next to `ui.py`, `db.py`, `llm.py`).
No new runtime dependencies (Pydantic ships with LangChain). For tests:
`pip install pytest mongomock`.

It expects `llm.py` to export `client` (teaching) and `profile_client` (temperature 0,
structured work). If `profile_client` is missing it falls back to `client`.

Optional: create indexes once (not required to run)
```python
from db import db
from lesson.store import LessonStore
LessonStore(db).ensure_indexes()
```

## 2. Replace JsonOutputParser in db.py

Replace the whole body of `Database.update_student_profile` with:

```python
def update_student_profile(self, session_id):
    from lesson.profile import update_profile_from_conversations
    rows = self.get_session_conversations(session_id)
    if rows:
        update_profile_from_conversations(self.db, self.user_id, rows)
    return self.get_student_profile()
```
The model now returns a tiny validated delta (new goals, interests, preferences). Python
merges it, so a truncated or malformed reply can no longer corrupt the profile, and the
red "OUTPUT_PARSING_FAILURE" box goes away. Strengths, weaknesses and topics are now
derived from quiz evidence (progress.py), not written by the model.

### 2b. Make profile updates automatic (remove the button)

The profile now updates itself: once `PROFILE_UPDATE_EVERY` (6) new chat turns pile up, a
background thread extracts the delta. Turns are flagged `profiled` in MongoDB, so nothing
is lost across refreshes, and a failed update is retried after a 5-minute cooldown.

In `ui.py`:
1. Delete the whole `if st.button("Refresh profile from this lesson"...)` block.
2. Right after `database.add_conversation(...)` in the chat handler add:
   ```python
   from lesson import update_profile_in_background
   update_profile_in_background(db, st.session_state.user_id)
   ```
3. In the sidebar "＋ Start a new lesson" button (it really starts a new *chat*; consider
   renaming it "New chat"), call this before resetting the session:
   ```python
   update_profile_in_background(db, st.session_state.user_id, force=True)
   ```
Lesson progress needs none of this: it updates after every quiz, in code.

## 3. Wire the mode switch into ui.py (testing only)

```python
from lesson.streamlit_demo import render_lesson_mode

mode = st.sidebar.radio("Mode", ["Free chat", "Lesson"], key="mode")   # in the sidebar
...
# after the metric cards, before the "### Your tutor" chat section:
if mode == "Lesson":
    render_lesson_mode(db, st.session_state.user_id, st.session_state.get("use_docs", True))
    st.stop()
```

### 3b. Spaced review ("Review what's due")

Each graded check schedules the topic's next review (1 / 3 / 7 / 21 days by mastery).
`engine.due_summary()` returns the number due (for a badge); `engine.start_review()` starts a
session on the most overdue topics (default 4). It opens straight on a recall check built
from the text the learner studied; a wrong answer triggers a short re-teach and a fresh
check (2 tries per topic), and results update the same mastery scores. Review views have
`view.mode == "review"`, and the first check has an empty `content`. Config:
`LESSON_REVIEW_TOPICS`, `LESSON_REVIEW_MAX_ATTEMPTS`.

## 4. Frontend contract (for the real UI later)

Every call returns a `LessonView` (Pydantic). Render by `view.phase`:

| phase      | show                          | next call                                      |
|------------|-------------------------------|------------------------------------------------|
| `teach`    | `content`, `sources`          | `go_to_check(id)` ("I already know this" is the same call) |
| `check`    | `questions` (no answer keys)  | `submit_answers(id, [answer, ...])`            |
| `feedback` | `result` (score, per question)| `continue_lesson(id)`                          |
| `done`     | `summary`, `scores`           | `start(topic)` for a new lesson                |

Other calls: `start(topic)`, `get_active_view()` (resume after refresh), `get_view(id)`,
`abandon(id)`, `list_lessons()`, `start_review()`, `due_summary()`. MCQ answers can be the option text or its index; short
answers are text. All errors are `LessonError` subclasses: show `str(exc)` to the learner
and `exc.detail` only in debug.

## 5. How it behaves

- Segment passes when the average check score is >= `LESSON_PASS_SCORE` (0.7).
- On a fail the segment is re-taught with a different analogy and a fresh check.
  After `LESSON_MAX_ATTEMPTS` (3) total tries it is marked a gap and the lesson moves on.
- MCQs are graded by code; short answers by the LLM (partial credit).
- Each graded attempt updates `topic_progress` mastery (moving average of scores) and
  refreshes the derived topics/strengths/weaknesses in `student_profile`, so free chat
  and the sidebar see lesson progress too.
- If an LLM call fails, nothing is saved; calling the same method again retries cleanly.
- Starting a lesson abandons any active one (only after the new one is ready).

## 6. Config (.env, all optional)

`LESSON_PASS_SCORE`, `LESSON_MAX_ATTEMPTS`, `LESSON_MIN_SEGMENTS`, `LESSON_MAX_SEGMENTS`,
`LESSON_SEGMENT_WORDS`, `LESSON_MAX_QUESTIONS`, `PROFILE_UPDATE_EVERY`, `PROFILE_RETRY_COOLDOWN_S`.

## 7. Test

```bash
python -m pytest lesson/tests -q      # logic, no API key needed
python -m lesson.cli                  # real end-to-end run in the terminal
```
Run the CLI first: it exercises your real NVIDIA model and MongoDB, which the unit tests
deliberately do not.
