"""Quiz data shapes: the LLM output schema and what the frontend sees (never answer keys)."""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from lesson.models import PublicQuestion, Question  # reused: same question format as lessons


class QuizBatch(BaseModel):
    """One model call's worth of questions. Invalid questions are dropped, not fatal."""
    subject: str = Field(default="", description="Broad subject area, e.g. 'Computer Science'")
    questions: list[Question]

    @field_validator("questions", mode="before")
    @classmethod
    def _drop_bad_questions(cls, value):
        good = []
        for item in value or []:
            try:
                good.append(item if isinstance(item, Question) else Question.model_validate(item))
            except Exception:
                continue
        return good

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.questions:
            raise ValueError("no valid questions in the batch")
        return self


class KindScore(BaseModel):
    correct: int
    total: int
    score: float          # mean score 0-1 for this kind


class QuizItemResult(BaseModel):
    index: int
    kind: Literal["mcq", "short"]
    prompt: str
    options: list[str] = Field(default_factory=list)
    your_answer: str = ""
    correct_answer: str = ""
    score: float
    correct: bool
    skipped: bool = False
    feedback: str = ""


class QuizResult(BaseModel):
    score: float                   # mean question score, 0-1 (short answers can earn partial credit)
    percent: int
    correct_count: int
    total: int
    skipped: int
    by_kind: dict[str, KindScore]
    items: list[QuizItemResult]


class QuizView(BaseModel):
    """phase 'answering': show `questions`; call save_answer() as the learner goes (optional)
    and submit() at the end.  phase 'done': show `result`."""
    quiz_id: str
    status: Literal["active", "completed", "abandoned"]
    phase: Literal["answering", "done"]
    topic: str
    subject: str
    quiz_type: Literal["mcq", "short", "mixed"]
    source: Literal["knowledge", "documents"]
    difficulty: str
    requested_total: int
    total: int
    questions: list[PublicQuestion] = Field(default_factory=list)
    answers: dict[int, Any] = Field(default_factory=dict)       # saved drafts (mcq: option text)
    answered_count: int = 0
    sources: list[dict] = Field(default_factory=list)
    result: Optional[QuizResult] = None
