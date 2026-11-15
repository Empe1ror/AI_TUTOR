# quiz/ — Quiz mode for Renewed AI Tutor

Learner gives a topic, picks a quiz type and a source, and gets a scored quiz.

| quiz_type | questions |
|-----------|-----------|
| `mcq`     | 10 multiple choice |
| `short`   | 10 short answer |
| `mixed`   | 15 = 8 multiple choice + 7 short answer (`QUIZ_MIXED_MCQ` / `QUIZ_MIXED_SHORT`) |

| source        | questions come from |
|---------------|---------------------|
| `knowledge`   | the tutor's own knowledge |
| `documents`   | only the learner's uploaded documents (clear error if the topic isn't in them) |

Optional `difficulty`: `easy | medium | hard`.

```
quiz/
├── __init__.py          QuizEngine, QuizView, QuizResult
├── config.py            counts, difficulty, grading workers, mastery weight (env-overridable)
├── models.py            QuizBatch (LLM schema), QuizView / QuizResult (frontend contract)
├── templates.py         question-writing prompts
├── store.py             MongoDB persistence ("quizzes" collection)
├── engine.py            the quiz engine
├── cli.py               terminal test:   python -m quiz.cli
├── streamlit_demo.py    throwaway test view
└── tests/               15 tests, no API key or MongoDB needed
```

**Requires the `lesson/` package** (it reuses its LLM gateway, question format, errors and
progress tracking). Install both folders in the project root. Overwrite the `lesson/` files
with the latest too: `progress.py` (new `weight`) and `adapters.py` (new `k`) changed.

## Use

```python
from lesson.adapters import rag_retriever
from quiz import QuizEngine, LessonError

engine = QuizEngine(db, user_id, retriever=rag_retriever(user_id, k=8))
view = engine.start("Photosynthesis", quiz_type="mixed", source="documents")
view = engine.save_answer(view.quiz_id, 0, "option text")   # optional: saves a draft
view = engine.submit(view.quiz_id, answers)                 # or submit(view.quiz_id) to use drafts
```

Frontend contract (`QuizView`): `phase == "answering"` -> render `questions` (no answer keys;
`answers` holds saved drafts). `phase == "done"` -> render `result` (percent, per-kind scores,
and per-question your_answer / correct_answer / feedback). Other calls: `get_active_view()`
(resume), `get_view(id)`, `abandon(id)`, `list_quizzes()`. All errors are `LessonError`
subclasses: show `str(exc)`, and `exc.detail` only when debugging.

## How it behaves
- Questions are written in batches of at most 10; if the model returns too few, wrong-kind
  or duplicate questions, up to 3 top-up rounds fill the gap. A quiz with at least 70% of the
  requested questions of each kind is accepted (`view.total` vs `view.requested_total`; this
  happens when a document is too short for 10 distinct questions); otherwise a friendly error.
- Options are shuffled in code; multiple choice is graded by code; short answers by the LLM
  with partial credit, graded in parallel (4 at a time).
- Blank answers count as skipped (score 0). Submitting is all-or-nothing: if grading fails,
  nothing is saved and `submit()` can be called again.
- The quiz score updates the topic's mastery (a quiz counts 1.5x a single lesson check) and
  refreshes the derived profile, so quizzes feed spaced review and the free-chat tutor too.
  Document quizzes also save the retrieved passages so later review questions stay grounded.
- Generating a full quiz takes several seconds to a minute depending on the model: show a
  spinner.

## Wire into ui.py (testing only)
```python
from quiz.streamlit_demo import render_quiz_mode
mode = st.sidebar.radio("Mode", ["Free chat", "Lesson", "Quiz"], key="mode")   # sidebar: radio only
...
# outside `with st.sidebar:`, next to the lesson-mode check:
if mode == "Quiz":
    render_quiz_mode(db, st.session_state.user_id)
    st.stop()
```
Optional one-time indexes: `from quiz.store import QuizStore; QuizStore(db).ensure_indexes()`.

## Test
```bash
python -m pytest quiz/tests lesson/tests -q
python -m quiz.cli        # real end-to-end run against your model and MongoDB
```
