"""Soft profile facts (goals, interests, preferences) extracted by the LLM as small deltas.

This replaces the old "LLM rewrites the whole profile as JSON" step. The model only
proposes NEW facts; plain Python validates and merges them, so a bad reply can never
delete or corrupt the profile. Mastery, strengths and weaknesses are NOT handled here:
progress.py owns those.
"""
import copy
import logging
import threading
from datetime import datetime, timedelta, timezone

from . import config, templates
from .llm_utils import LLMGateway
from .models import ProfileDelta

LEVELS = {"beginner", "elementary", "intermediate", "advanced", "mixed"}
PREFERENCE_VALUES = {
    "pace": {"slow", "moderate", "fast"},
    "depth": {"basic", "moderate", "deep"},
    "step_by_step": {"preferred", "not_preferred"},
    "examples": {"preferred", "not_preferred"},
    "analogies": {"preferred", "not_preferred"},
    "visual_explanations": {"preferred", "not_preferred"},
    "practical_exercises": {"preferred", "not_preferred"},
    "theory_vs_practice": {"theory", "balanced", "practice"},
    "challenge_level": {"low", "moderate", "high"},
}
log = logging.getLogger(__name__)
MAX_LIST_ITEMS = 15
MAX_ITEM_CHARS = 100


def student_brief(profile_doc: dict, weak: list[dict] | tuple = ()) -> str:
    """A compact text summary of the learner for prompts."""
    p = (profile_doc or {}).get("Profile") or {}
    student = p.get("student") or {}
    background = p.get("background") or {}
    prefs = {k: v for k, v in (p.get("learning_preferences") or {}).items() if v and v != "unknown"}
    goals = student.get("learning_goals") or []
    lines = [f"Name: {student.get('name', 'unknown')}",
             f"Experience level: {background.get('experience_level', 'unknown')}"]
    if goals:
        lines.append("Goals: " + "; ".join(goals[:5]))
    if prefs:
        lines.append("Preferences: " + ", ".join(f"{k}={v}" for k, v in prefs.items()))
    if weak:
        lines.append("Topics they find difficult: " + "; ".join(w["topic"] for w in weak))
    return "\n".join(lines)


def _format_conversation(rows: list[dict], limit: int = 20) -> str:
    parts = []
    for r in rows[-limit:]:
        if r.get("user_input"):
            parts.append(f"Student: {str(r['user_input'])[:800]}")
        if r.get("ai_response"):
            parts.append(f"Tutor: {str(r['ai_response'])[:400]}")
    return "\n".join(parts)


def extract_delta(rows: list[dict], profile: dict, gateway: LLMGateway) -> ProfileDelta:
    return gateway.structured(
        ProfileDelta, templates.DELTA_SYS, templates.DELTA_HUMAN,
        profile=str({k: profile.get(k) for k in ("student", "background", "learning_preferences")}),
        conversation=_format_conversation(rows),
    )


def _merge_list(existing: list, new: list[str]) -> list:
    out = [str(x) for x in (existing or [])]
    seen = {x.lower() for x in out}
    for item in new:
        item = str(item).strip()[:MAX_ITEM_CHARS]
        if item and item.lower() not in seen:
            out.append(item)
            seen.add(item.lower())
    return out[:MAX_LIST_ITEMS]


def apply_delta(profile: dict, delta: ProfileDelta) -> dict:
    """Pure function: returns a new profile with the validated delta merged in."""
    p = copy.deepcopy(profile or {})
    student = p.setdefault("student", {})
    background = p.setdefault("background", {})
    prefs = p.setdefault("learning_preferences", {})

    student["learning_goals"] = _merge_list(student.get("learning_goals"), delta.new_goals)
    background["subjects_of_interest"] = _merge_list(background.get("subjects_of_interest"),
                                                    delta.new_interests)
    level = delta.experience_level.strip().lower()
    if level in LEVELS:
        background["experience_level"] = level
    for key, value in delta.preference_updates.items():
        value = str(value).strip().lower()
        if key in PREFERENCE_VALUES and value in PREFERENCE_VALUES[key]:
            prefs[key] = value
    return p


def update_profile_from_conversations(db, user_id: str, rows: list[dict],
                                      gateway: LLMGateway | None = None) -> dict:
    """Extract a delta from the conversation and merge it. Only the soft fields are written."""
    col = db[config.PROFILE_COLLECTION]
    doc = col.find_one({"user_id": user_id}) or {}
    profile = doc.get("Profile") or {}
    if not rows:
        return profile
    delta = extract_delta(rows, profile, gateway or LLMGateway())
    new = apply_delta(profile, delta)
    col.update_one({"user_id": user_id}, {"$set": {
        "Profile.student.learning_goals": new["student"]["learning_goals"],
        "Profile.background.subjects_of_interest": new["background"]["subjects_of_interest"],
        "Profile.background.experience_level": new["background"].get("experience_level", "unknown"),
        "Profile.learning_preferences": new["learning_preferences"],
        "updated_at": datetime.now(timezone.utc),
    }})
    return new


# ===================================================================== automatic updates
# Chat turns saved by the UI carry no marker. Once a turn has been folded into the profile
# it is flagged `profiled: True`, so progress survives refreshes and closed browsers.
_running: set[str] = set()
_guard = threading.Lock()


def _aware(ts):
    return ts if ts is None or ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def maybe_update_profile(db, user_id: str, *, force: bool = False, every: int | None = None,
                         gateway: LLMGateway | None = None) -> bool:
    """Update the soft profile if enough new chat turns have piled up. Never raises.

    force=True lowers the bar to PROFILE_MIN_TURNS_FORCE turns and ignores the retry
    cooldown (use it when a chat ends). Returns True if an update ran.
    """
    with _guard:
        if user_id in _running:          # one update per learner at a time
            return False
        _running.add(user_id)
    try:
        conv = db[config.CONVERSATION_COLLECTION]
        pending = {"user_id": user_id, "profiled": {"$ne": True}}
        needed = config.PROFILE_MIN_TURNS_FORCE if force else (every or config.PROFILE_EVERY_N_TURNS)
        if conv.count_documents(pending) < needed:
            return False

        sync = (db[config.PROFILE_COLLECTION].find_one({"user_id": user_id}) or {}).get("profile_sync") or {}
        failed_at = _aware(sync.get("last_error_at"))
        if not force and failed_at and datetime.now(timezone.utc) - failed_at < timedelta(
                seconds=config.PROFILE_RETRY_COOLDOWN_S):
            return False                 # recently failed: don't hammer the API on every message

        docs = list(conv.find(pending).sort("created_at", 1).limit(config.PROFILE_MAX_ROWS))
        rows = [r for d in docs for r in d.get("conversations", [])]
        update_profile_from_conversations(db, user_id, rows, gateway)
        conv.update_many({"_id": {"$in": [d["_id"] for d in docs]}}, {"$set": {"profiled": True}})
        db[config.PROFILE_COLLECTION].update_one({"user_id": user_id}, {"$set": {
            "profile_sync": {"last_run": datetime.now(timezone.utc), "last_error": "", "last_error_at": None}}})
        return True
    except Exception as exc:
        log.exception("automatic profile update failed")
        try:                             # failed turns stay pending and are retried after the cooldown
            db[config.PROFILE_COLLECTION].update_one({"user_id": user_id}, {"$set": {
                "profile_sync.last_error": str(exc)[:300],
                "profile_sync.last_error_at": datetime.now(timezone.utc)}})
        except Exception:
            pass
        return False
    finally:
        with _guard:
            _running.discard(user_id)


def update_profile_in_background(db, user_id: str, **kwargs) -> threading.Thread:
    """Fire-and-forget version for the UI, so the learner never waits on it."""
    t = threading.Thread(target=maybe_update_profile, args=(db, user_id), kwargs=kwargs, daemon=True)
    t.start()
    return t
