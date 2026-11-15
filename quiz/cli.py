"""Terminal test harness for quiz mode.   Run from the project root:   python -m quiz.cli"""
import sys

from lesson.adapters import rag_retriever
from lesson.errors import LessonError

from . import config
from .engine import QuizEngine

TYPES = {"1": "mcq", "2": "short", "3": "mixed"}


def run():
    from db import Database, db
    if db is None:
        sys.exit("MONGODB_URI is not set.")
    name = input("Your name: ").strip()
    user_id = input("Student ID: ").strip().lower().replace(" ", "_")
    database = Database(db, user_id)
    if not database.get_student_profile():
        database.create_student_profile(name)

    engine = QuizEngine(db, user_id, retriever=rag_retriever(user_id, k=config.RETRIEVAL_K))
    view = None
    while view is None:
        topic = input("Quiz topic: ")
        qtype = TYPES.get(input("Type: 1) multiple choice (10)  2) short answer (10)  3) mixed (15): ").strip(), "mcq")
        source = "documents" if input("Use my uploaded documents? (y/n) ").strip().lower() == "y" else "knowledge"
        try:
            print("Writing your quiz...")
            view = engine.start(topic, qtype, source)
        except LessonError as exc:
            print("!", exc, exc.detail)

    answers = []
    for q in view.questions:
        print(f"\nQ{q.index + 1}/{view.total}: {q.prompt}")
        if q.kind == "mcq":
            for i, opt in enumerate(q.options):
                print(f"  {i + 1}. {opt}")
            pick = input("Your choice (number, Enter to skip): ").strip()
            answers.append(int(pick) - 1 if pick.isdigit() else None)
        else:
            answers.append(input("Your answer (Enter to skip): "))

    while True:
        try:
            print("\nGrading...")
            view = engine.submit(view.quiz_id, answers)
            break
        except LessonError as exc:
            print("!", exc, exc.detail)
            if input("Try grading again? (y/n) ").strip().lower() != "y":
                return

    r = view.result
    print(f"\n=== Score: {r.percent}%  ({r.correct_count}/{r.total} correct, {r.skipped} skipped) ===")
    for kind, ks in r.by_kind.items():
        print(f"  {kind}: {ks.correct}/{ks.total}")
    for it in r.items:
        print(f"\n{'OK ' if it.correct else 'NO '} Q{it.index + 1}: {it.prompt}")
        print(f"    You: {it.your_answer or '(skipped)'}")
        print(f"    Answer: {it.correct_answer}")
        print(f"    {it.feedback}")


if __name__ == "__main__":
    run()
