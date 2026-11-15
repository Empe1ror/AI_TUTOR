"""Exceptions raised by lesson mode.

Every LessonError has a message that is safe to show the learner.
`detail` carries the technical cause (for logs or a debug caption).
"""


class LessonError(Exception):
    def __init__(self, message: str, detail: str = ""):
        super().__init__(message)
        self.detail = detail


class LessonNotFound(LessonError):
    """The lesson id does not exist for this student."""


class InvalidStateError(LessonError):
    """The action is not allowed in the lesson's current step."""


class LLMOutputError(LessonError):
    """The model failed to produce usable output after retries."""
