"""THROWAWAY Streamlit test view for lesson mode. Replace with the real frontend later.

In ui.py, after the learner is logged in and before the free-chat section:

    from lesson.streamlit_demo import render_lesson_mode
    mode = st.sidebar.radio("Mode", ["Free chat", "Lesson"], key="mode")
    ...
    if mode == "Lesson":
        render_lesson_mode(db, st.session_state.user_id, st.session_state.get("use_docs", True))
        st.stop()
"""
import streamlit as st

from .adapters import rag_retriever
from .engine import LessonEngine
from .errors import LessonError


def render_lesson_mode(db, user_id: str, use_docs: bool = True) -> None:
    engine = LessonEngine(db, user_id, retriever=rag_retriever(user_id) if use_docs else None)

    def act(fn, *args):
        try:
            with st.spinner("Working on it…"):
                st.session_state.lesson_view = fn(*args)
            st.session_state.pop("lesson_error", None)
        except LessonError as exc:
            st.session_state.lesson_error = f"{exc} {exc.detail}".strip()
        st.rerun()

    if "lesson_view" not in st.session_state:
        st.session_state.lesson_view = engine.get_active_view()   # resume after a refresh
    view = st.session_state.lesson_view

    st.markdown("### Lesson mode")
    if st.session_state.get("lesson_error"):
        st.error(st.session_state.lesson_error)

    if view is None or (view.status != "active" and view.phase != "done"):
        due = engine.due_summary()
        if due["count"]:
            st.info(f"📚 {due['count']} topic(s) are due for review.")
            if st.button("Review what's due", type="primary"):
                act(engine.start_review)
            st.divider()
        topic = st.text_input("What do you want to learn?", key="lesson_topic")
        if st.button("Start lesson", type="primary"):
            act(engine.start, topic)
        return

    st.progress(min(1.0, (view.segment_index + (1 if view.phase == "done" else 0)) / view.segment_total))
    st.caption(f"{view.topic} · segment {view.segment_index + 1} of {view.segment_total}: {view.segment_title}")

    if view.phase == "teach":
        st.markdown(view.content)
        if view.sources:
            with st.expander(f"Sources ({len(view.sources)})"):
                for s in view.sources:
                    st.markdown(f"**[{s['n']}] {s['label']}**")
                    st.caption(s["text"])
        c1, c2 = st.columns(2)
        if c1.button("Check my understanding", type="primary"):
            act(engine.go_to_check, view.lesson_id)
        if c2.button("I already know this"):
            act(engine.go_to_check, view.lesson_id)

    elif view.phase == "check":
        if view.content:                 # a review's first check has no explanation to re-read
            with st.expander("Re-read the explanation"):
                st.markdown(view.content)
        with st.form("lesson_check"):
            answers = []
            for q in view.questions:
                key = f"q_{view.lesson_id}_{view.segment_index}_{view.attempt}_{q.index}"
                if q.kind == "mcq":
                    answers.append(st.radio(q.prompt, q.options, index=None, key=key))
                else:
                    answers.append(st.text_area(q.prompt, key=key))
            submitted = st.form_submit_button("Submit answers", type="primary")
        if submitted:
            if any(a in (None, "") for a in answers):
                st.session_state.lesson_error = "Please answer every question."
                st.rerun()
            act(engine.submit_answers, view.lesson_id, answers)

    elif view.phase == "feedback":
        r = view.result
        st.markdown(f"**Score: {round(r.score * 100)}%** · {r.outcome}")
        for q in r.questions:
            st.markdown(f"{'✅' if q.correct else '❌'} {q.prompt}")
            if q.feedback:
                st.caption(q.feedback)
            if q.correct_answer:
                st.caption(f"Answer: {q.correct_answer}")
        label = "Try again with a new explanation" if r.outcome == "retry" else "Continue"
        if st.button(label, type="primary"):
            act(engine.continue_lesson, view.lesson_id)

    elif view.phase == "done":
        s = view.summary
        st.success("Lesson complete")
        if s:
            st.write(s.summary)
            for p in s.key_points:
                st.markdown(f"- {p}")
            if s.review_topics:
                st.info("Worth reviewing: " + ", ".join(s.review_topics))
            if s.next_topic:
                st.caption(f"Suggested next topic: {s.next_topic}")
        if st.button("Start another lesson"):
            st.session_state.lesson_view = None
            st.rerun()
        return

    if st.button("Leave this lesson"):
        engine.abandon(view.lesson_id)
        st.session_state.lesson_view = None
        st.rerun()
