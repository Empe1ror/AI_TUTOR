"""Quiz mode for Renewed AI Tutor (builds on the lesson/ package).

    from quiz import QuizEngine
    engine = QuizEngine(db, user_id, retriever=rag_retriever(user_id, k=8))
    view = engine.start("Photosynthesis", quiz_type="mixed", source="knowledge")   # 15 questions
    engine.save_answer(view.quiz_id, 0, "option text")     # optional drafts
    view = engine.submit(view.quiz_id, answers)            # or submit() to use the saved drafts
"""
from lesson.errors import InvalidStateError, LessonError, LessonNotFound, LLMOutputError

from .engine import QuizEngine
from .models import QuizResult, QuizView
from .store import QuizStore

__all__ = ["QuizEngine", "QuizView", "QuizResult", "QuizStore",
           "LessonError", "LessonNotFound", "InvalidStateError", "LLMOutputError"]
