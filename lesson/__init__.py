"""Lesson mode for Renewed AI Tutor: structured, segment-by-segment lessons with
quiz-gated progress and code-owned mastery tracking.

Typical use:
    from lesson import LessonEngine, LessonError
    engine = LessonEngine(db, user_id, retriever=rag_retriever(user_id))
    view = engine.start("Cybernetics")
    view = engine.go_to_check(view.lesson_id)
    view = engine.submit_answers(view.lesson_id, ["option text", "my explanation"])
    view = engine.continue_lesson(view.lesson_id)
"""
from .adapters import rag_retriever
from .engine import LessonEngine
from .errors import InvalidStateError, LessonError, LessonNotFound, LLMOutputError
from .llm_utils import LLMGateway
from .models import LessonView
from .profile import maybe_update_profile, update_profile_from_conversations, update_profile_in_background
from .progress import due_for_review, due_summary, record_outcome, snapshot, sync_to_profile, weak_topics
from .store import LessonStore

__all__ = [
    "LessonEngine", "LessonView", "LessonStore", "LLMGateway",
    "LessonError", "LessonNotFound", "InvalidStateError", "LLMOutputError",
    "rag_retriever", "update_profile_from_conversations",
    "maybe_update_profile", "update_profile_in_background",
    "record_outcome", "due_summary", "sync_to_profile", "snapshot", "weak_topics", "due_for_review",
]
