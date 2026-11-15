"""Tunable settings for quiz mode (all env-overridable). Quiz mode builds on the lesson/ package."""
import os

from lesson import config as lesson_config


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return int(default)


def _float(name, default):
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


QUIZZES_COLLECTION = "quizzes"

# How many questions each quiz type has
MCQ_COUNT = _int("QUIZ_MCQ_COUNT", 10)
SHORT_COUNT = _int("QUIZ_SHORT_COUNT", 10)
MIXED_MCQ = _int("QUIZ_MIXED_MCQ", 8)
MIXED_SHORT = _int("QUIZ_MIXED_SHORT", 7)      # mixed quiz = 8 + 7 = 15
QUIZ_TYPES = {
    "mcq": {"mcq": MCQ_COUNT},
    "short": {"short": SHORT_COUNT},
    "mixed": {"mcq": MIXED_MCQ, "short": MIXED_SHORT},
}
DIFFICULTIES = ("easy", "medium", "hard")
SOURCES = ("knowledge", "documents")

# Generation
MAX_PER_CALL = 5          # questions requested per model call (keeps replies short)
MAX_ROUNDS = 4             # top-up calls if the model returns too few / duplicates
MIN_FRACTION = 0.7         # accept a quiz with at least 70% of the requested questions of each kind
RETRIEVAL_K = 8            # passages to retrieve for a document quiz (use with rag_retriever(k=...))

# Grading / mastery
GRADE_WORKERS = 4                              # short answers graded in parallel
CORRECT_SCORE = lesson_config.PASS_SCORE       # score at which a question counts as correct
MASTERY_WEIGHT = _float("QUIZ_MASTERY_WEIGHT", 1.5)   # a whole quiz is stronger evidence than one check
