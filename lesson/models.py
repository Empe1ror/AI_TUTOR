"""Data shapes for lesson mode.

Three groups:
  1. LLM output schemas      (LessonPlan, Check, Grade, LessonSummary, ProfileDelta)
  2. What the frontend sees  (LessonView and friends) - never contains answer keys
  3. Validators that reject bad model output so the engine can retry
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ----------------------------------------------------------------- LLM schemas
class Segment(BaseModel):
    title: str = Field(description="Short title for this segment")
    objective: str = Field(description="One thing the student can do after this segment")


class LessonPlan(BaseModel):
    subject: str = Field(description="Broad subject area, e.g. 'Computer Science'")
    topic: str = Field(description="Clean topic title")
    segments: list[Segment]

    @model_validator(mode="after")
    def _has_segments(self):
        if not self.segments:
            raise ValueError("a lesson needs at least one segment")
        return self


class Question(BaseModel):
    kind: Literal["mcq", "short"]
    prompt: str
    options: list[str] = Field(default_factory=list, description="4 options for mcq")
    correct_index: Optional[int] = Field(default=None, description="0-based index of the correct option (mcq)")
    reference_answer: str = Field(default="", description="Model answer (short)")
    explanation: str = ""

    @model_validator(mode="after")
    def _consistent(self):
        if self.kind == "mcq":
            if len(self.options) < 2:
                raise ValueError("mcq needs at least 2 options")
            if self.correct_index is None or not (0 <= self.correct_index < len(self.options)):
                raise ValueError("mcq correct_index is missing or out of range")
        elif not self.reference_answer.strip():
            raise ValueError("short question needs a reference_answer")
        return self


class Check(BaseModel):
    questions: list[Question]

    @model_validator(mode="after")
    def _has_questions(self):
        if not self.questions:
            raise ValueError("a check needs at least one question")
        return self


class Grade(BaseModel):
    score: float = Field(description="0.0 to 1.0")
    feedback: str = ""

    @field_validator("score")
    @classmethod
    def _clamp(cls, v):
        return max(0.0, min(1.0, float(v)))


class LessonSummary(BaseModel):
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    next_topic: str = ""
    review_topics: list[str] = Field(default_factory=list)  # filled by code, not the model


class ProfileDelta(BaseModel):
    """Only NEW soft facts. Topic mastery is tracked by code, never by the model."""
    new_goals: list[str] = Field(default_factory=list)
    new_interests: list[str] = Field(default_factory=list)
    experience_level: str = "unknown"
    preference_updates: dict[str, str] = Field(default_factory=dict)


# ------------------------------------------------------------ frontend-facing
class PublicQuestion(BaseModel):
    """A question as the student sees it: no answer key."""
    index: int
    kind: Literal["mcq", "short"]
    prompt: str
    options: list[str] = Field(default_factory=list)


class QuestionResult(BaseModel):
    index: int
    kind: str
    prompt: str
    score: float
    correct: bool
    feedback: str = ""
    correct_answer: str = ""


class AttemptResult(BaseModel):
    attempt: int
    score: float
    passed: bool
    outcome: Literal["passed", "retry", "gap"]
    questions: list[QuestionResult]


class SegmentScore(BaseModel):
    index: int
    title: str
    score: float
    attempts: int
    outcome: Literal["passed", "gap"]


class LessonView(BaseModel):
    """Everything a frontend needs to render the lesson at its current step.

    phase:
      teach     -> show `content`; the student reads, then calls go_to_check()
      check     -> show `questions`; the student calls submit_answers()
      feedback  -> show `result`; the student calls continue_lesson()
      done      -> show `summary`
    """
    lesson_id: str
    status: Literal["active", "completed", "abandoned"]
    mode: Literal["lesson", "review"] = "lesson"
    phase: Literal["teach", "check", "feedback", "done"]
    subject: str
    topic: str
    outline: list[str]
    segment_index: int
    segment_total: int
    segment_title: str
    objective: str
    content: str = ""
    questions: list[PublicQuestion] = Field(default_factory=list)
    result: Optional[AttemptResult] = None
    sources: list[dict] = Field(default_factory=list)
    attempt: int = 1
    max_attempts: int = 3
    scores: list[SegmentScore] = Field(default_factory=list)
    summary: Optional[LessonSummary] = None
