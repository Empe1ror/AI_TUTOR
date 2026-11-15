"""Terminal test harness for lesson mode (no Streamlit needed).

Run from the project root:   python -m lesson.cli
"""
import sys

from .adapters import rag_retriever
from .engine import LessonEngine
from .errors import LessonError


def _show_result(view):
    r = view.result
    print(f"\nScore: {round(r.score * 100)}%  ->  {r.outcome.upper()} (attempt {r.attempt}/{view.max_attempts})")
    for q in r.questions:
        print(f"  {'OK ' if q.correct else 'NO '} {q.prompt}\n      {q.feedback}")
        if q.correct_answer:
            print(f"      Answer: {q.correct_answer}")


def run():
    from db import Database, db
    if db is None:
        sys.exit("MONGODB_URI is not set.")
    name = input("Your name: ").strip()
    user_id = input("Student ID: ").strip().lower().replace(" ", "_")
    database = Database(db, user_id)
    if not database.get_student_profile():
        database.create_student_profile(name)

    use_docs = input("Use my uploaded documents? (y/n) ").strip().lower() == "y"
    engine = LessonEngine(db, user_id, retriever=rag_retriever(user_id) if use_docs else None)

    view = engine.get_active_view()
    if view and input(f"Resume '{view.topic}'? (y/n) ").strip().lower() != "y":
        engine.abandon(view.lesson_id)
        view = None
    due = engine.due_summary()["count"]
    if due:
        print(f"\n{due} topic(s) are due for review. Type 'review' to start a review session.")
    while view is None:
        try:
            wanted = input("What do you want to learn? ").strip()
            view = engine.start_review() if wanted.lower() == "review" else engine.start(wanted)
        except LessonError as exc:
            print("!", exc, exc.detail)

    while view.phase != "done":
        try:
            if view.phase == "teach":
                print(f"\n=== Segment {view.segment_index + 1}/{view.segment_total}: {view.segment_title} ===\n")
                print(view.content)
                input("\n[Enter] to take the check ")
                view = engine.go_to_check(view.lesson_id)
            elif view.phase == "check":
                answers = []
                for q in view.questions:
                    print(f"\n{q.prompt}")
                    if q.kind == "mcq":
                        for i, opt in enumerate(q.options):
                            print(f"  {i + 1}. {opt}")
                        pick = input("Your choice (number): ").strip()
                        answers.append(int(pick) - 1 if pick.isdigit() else None)
                    else:
                        answers.append(input("Your answer: "))
                view = engine.submit_answers(view.lesson_id, answers)
            elif view.phase == "feedback":
                _show_result(view)
                input("\n[Enter] to continue ")
                view = engine.continue_lesson(view.lesson_id)
        except LessonError as exc:
            print("!", exc, exc.detail)

    s = view.summary
    print("\n=== Lesson complete ===")
    print(s.summary)
    for p in s.key_points:
        print(" -", p)
    if s.review_topics:
        print("Worth reviewing:", ", ".join(s.review_topics))
    if s.next_topic:
        print("Next topic:", s.next_topic)


if __name__ == "__main__":
    run()
