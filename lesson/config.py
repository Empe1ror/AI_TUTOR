"""Tunable settings for lesson mode.

Every number can be overridden with an environment variable (put it in .env),
so you can experiment without touching code.
"""
import os


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return int(default)


# MongoDB collections (same database as the rest of the app)
LESSONS_COLLECTION = "lessons"
PROGRESS_COLLECTION = "topic_progress"
PROFILE_COLLECTION = "student_profile"

# Lesson shape
MIN_SEGMENTS = _int("LESSON_MIN_SEGMENTS", 3)
MAX_SEGMENTS = _int("LESSON_MAX_SEGMENTS", 6)
SEGMENT_WORDS = _int("LESSON_SEGMENT_WORDS", 200)
MAX_QUESTIONS = _int("LESSON_MAX_QUESTIONS", 2)

# Mastery gate
PASS_SCORE = _float("LESSON_PASS_SCORE", 0.7)     # average score needed to advance
MAX_ATTEMPTS = _int("LESSON_MAX_ATTEMPTS", 3)     # total tries per segment before moving on

# Mastery maths (progress.py)
MASTERY_START = 0.3    # a topic the student has never been tested on
MASTERY_ALPHA = 0.35   # how far one new score moves the mastery (0-1)

# LLM calls
MAX_LLM_RETRIES = 2          # extra attempts when output is invalid
NATIVE_FAILURE_LIMIT = 3     # after this many failures, stop trying with_structured_output

NO_CONTEXT = "No reference material available."

# Automatic profile updates (profile.py)
PROFILE_EVERY_N_TURNS = _int("PROFILE_UPDATE_EVERY", 6)       # new chat turns before an update runs
PROFILE_MIN_TURNS_FORCE = _int("PROFILE_MIN_TURNS_FORCE", 2)   # minimum when forced (e.g. new chat)
PROFILE_MAX_ROWS = _int("PROFILE_MAX_ROWS", 20)               # turns sent to the model per update
PROFILE_RETRY_COOLDOWN_S = _int("PROFILE_RETRY_COOLDOWN_S", 300)  # pause after a failed update
CONVERSATION_COLLECTION = "conversation"

# Spaced review ("Review what's due")
REVIEW_MAX_TOPICS = _int("LESSON_REVIEW_TOPICS", 4)          # topics per review session
REVIEW_MAX_ATTEMPTS = _int("LESSON_REVIEW_MAX_ATTEMPTS", 2)  # tries per topic in a review
