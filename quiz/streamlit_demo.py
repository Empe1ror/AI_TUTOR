"""THROWAWAY Streamlit test view for quiz mode. Replace with the real frontend later.

In ui.py (outside `with st.sidebar:`), next to the lesson-mode switch:

    from quiz.streamlit_demo import render_quiz_mode
    mode = st.sidebar.radio("Mode", ["Free chat", "Lesson", "Quiz"], key="mode")
    ...
    if mode == "Quiz":
        render_quiz_mode(db, st.session_state.user_id)
        st.stop()
"""
import streamlit as st

from lesson.adapters import rag_retriever
from lesson.errors import LessonError

from . import config
from .engine import QuizEngine

TYPE_LABELS = {"mcq": "Multiple choice (10 questions)", "short": "Short answer (10 questions)",
               "mixed": "Mixed (15 questions)"}
SOURCE_LABELS = {"knowledge": "Tutor's knowledge", "documents": "My uploaded documents"}


def render_quiz_mode(db, user_id: str) -> None:
    engine = QuizEngine(db, user_id, retriever=rag_retriever(user_id, k=config.RETRIEVAL_K))

    def act(fn, *args, **kwargs):
        try:
            with st.spinner("Working on it… (a full quiz can take up to a minute)"):
                st.session_state.quiz_view = fn(*args, **kwargs)
            st.session_state.pop("quiz_error", None)
        except LessonError as exc:
            st.session_state.quiz_error = f"{exc} {exc.detail}".strip()
        st.rerun()

    if "quiz_view" not in st.session_state:
        st.session_state.quiz_view = engine.get_active_view()      # resume after a refresh
    view = st.session_state.quiz_view

    st.markdown("### Quiz mode")
    if st.session_state.get("quiz_error"):
        st.error(st.session_state.quiz_error)

    if view is None or (view.status != "active" and view.phase != "done"):
        topic = st.text_input("Quiz topic", key="quiz_topic")
        qtype = st.radio("Quiz type", list(TYPE_LABELS), format_func=TYPE_LABELS.get, key="quiz_type")
        source = st.radio("Questions come from", list(SOURCE_LABELS), format_func=SOURCE_LABELS.get,
                          horizontal=True, key="quiz_source")
        difficulty = st.select_slider("Difficulty", config.DIFFICULTIES, value="medium", key="quiz_difficulty")
        if st.button("Create quiz", type="primary"):
            act(engine.start, topic, qtype, source, difficulty)
        return

    if view.phase == "answering":
        st.caption(f"{view.topic} · {TYPE_LABELS[view.quiz_type]} · {view.difficulty}")
        if view.total < view.requested_total:
            st.info(f"Only {view.total} good questions could be written (requested {view.requested_total}).")
        if view.sources:
            with st.expander(f"Sources used ({len(view.sources)})"):
                for s in view.sources:
                    st.markdown(f"**[{s['n']}] {s['label']}**")
        with st.form("quiz_form"):
            answers = []
            for q in view.questions:
                key = f"qz_{view.quiz_id}_{q.index}"
                st.markdown(f"**{q.index + 1}. {q.prompt}**")
                if q.kind == "mcq":
                    answers.append(st.radio("Choose one", q.options, index=None, key=key,
                                            label_visibility="collapsed"))
                else:
                    answers.append(st.text_area("Your answer", key=key, label_visibility="collapsed"))
            submitted = st.form_submit_button("Submit quiz", type="primary")
        if submitted:
            act(engine.submit, view.quiz_id, answers)       # blanks are skipped
        if st.button("Discard this quiz"):
            engine.abandon(view.quiz_id)
            st.session_state.quiz_view = None
            st.rerun()
        return

    r = view.result
    st.success(f"Score: {r.percent}%  ·  {r.correct_count}/{r.total} correct"
               + (f"  ·  {r.skipped} skipped" if r.skipped else ""))
    for kind, ks in r.by_kind.items():
        st.caption(f"{'Multiple choice' if kind == 'mcq' else 'Short answer'}: {ks.correct}/{ks.total}")
    for it in r.items:
        with st.expander(f"{'✅' if it.correct else '❌'} {it.index + 1}. {it.prompt}"):
            st.markdown(f"**Your answer:** {it.your_answer or '(skipped)'}")
            st.markdown(f"**Correct answer:** {it.correct_answer}")
            if it.feedback:
                st.caption(it.feedback)
    if st.button("New quiz", type="primary"):
        st.session_state.quiz_view = None
        st.rerun()
