"""One place that talks to the LLM.

LLMGateway offers two calls:
  text(...)        free-text answer (used for teaching)
  structured(...)  a validated Pydantic object (plans, checks, grades, summaries)

structured() first tries the model's native structured output; if the endpoint does not
support it or the result is invalid, it falls back to "return JSON" prompting, strips
<think> blocks and code fences, validates with Pydantic, and retries. This is why a
single malformed reply no longer breaks the app.

Tests can pass a fake gateway to LessonEngine, so no API key is needed to test logic.
"""
import json
import logging
import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from . import config
from .errors import LLMOutputError

log = logging.getLogger(__name__)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def clean_model_text(raw: str) -> str:
    """Remove reasoning blocks some models emit before the real answer."""
    text = _THINK_BLOCK.sub("", raw or "")
    if "</think>" in text:               # closing tag only (opening tag was swallowed)
        text = text.split("</think>")[-1]
    return text.strip()


def extract_json(raw: str) -> dict:
    """Pull the outermost {...} out of a model reply and parse it."""
    text = clean_model_text(raw)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"no JSON object found in model output (starts: {text[:120]!r})")
    return json.loads(text[start:end + 1])


class LLMGateway:
    def __init__(self, teacher=None, structured_model=None):
        self._teacher = teacher
        self._structured_model = structured_model
        self._native_failures = 0

    # Models are imported lazily so importing the package never needs an API key.
    @property
    def teacher(self):
        if self._teacher is None:
            from llm import client
            self._teacher = client
        return self._teacher

    @property
    def structured_model(self):
        if self._structured_model is None:
            try:
                from llm import profile_client as model
            except ImportError:
                from llm import client as model
            self._structured_model = model
        return self._structured_model

    # ------------------------------------------------------------------ text
    def text(self, system: str, human: str, **variables) -> str:
        chain = ChatPromptTemplate.from_messages([("system", system), ("human", human)]) \
            | self.teacher | StrOutputParser()
        try:
            out = clean_model_text(chain.invoke(variables))
        except Exception as exc:
            raise LLMOutputError("The tutor couldn't prepare that step. Please try again.",
                                 detail=str(exc)[:300]) from exc
        if not out:
            raise LLMOutputError("The tutor returned an empty answer. Please try again.")
        return out

    # ------------------------------------------------------------ structured
    def structured(self, model_cls, system: str, human: str, **variables):
        last_exc = None
        for attempt in range(1 + config.MAX_LLM_RETRIES):
            try:
                if attempt == 0 and self._native_failures < config.NATIVE_FAILURE_LIMIT:
                    try:
                        result = self._native(model_cls, system, human, variables)
                        self._native_failures = 0
                        return result
                    except Exception as exc:
                        self._native_failures += 1
                        log.info("native structured output failed (%s); using JSON mode", exc)
                return self._json_mode(model_cls, system, human, variables)
            except Exception as exc:
                last_exc = exc
                log.warning("structured call attempt %d for %s failed: %s",
                            attempt + 1, model_cls.__name__, exc)
        raise LLMOutputError("The tutor had trouble preparing that step. Please try again.",
                             detail=str(last_exc)[:300]) from last_exc

    def _native(self, model_cls, system, human, variables):
        prompt = ChatPromptTemplate.from_messages([("system", system), ("human", human)])
        result = (prompt | self.structured_model.with_structured_output(model_cls)).invoke(variables)
        if isinstance(result, dict):
            result = model_cls.model_validate(result)
        if not isinstance(result, model_cls):
            raise ValueError("structured output returned nothing usable")
        return result

    def _json_mode(self, model_cls, system, human, variables):
        suffix = ("\n\nReturn ONLY one valid JSON object that matches this JSON schema. "
                  "No markdown, no commentary:\n{schema_json}")
        prompt = ChatPromptTemplate.from_messages([("system", system + suffix), ("human", human)])
        raw = (prompt | self.structured_model | StrOutputParser()).invoke(
            {**variables, "schema_json": json.dumps(model_cls.model_json_schema())}
        )
        return model_cls.model_validate(extract_json(raw))
