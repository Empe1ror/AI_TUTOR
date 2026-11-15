"""Code-owned learner progress. No LLM is involved in this file.

topic_progress: one document per (user, subject, topic)
    {user_id, subject, topic, parent_topic, mastery 0-1, attempts, last_score,
     last_seen, next_review}

Mastery moves toward each new quiz score (exponential moving average), so it reflects
evidence, not a model's guess. `sync_to_profile` writes a derived view into the existing
student_profile document so the sidebar and the free-chat tutor see lesson progress too.
"""
from datetime import datetime, timedelta, timezone

from . import config


def label(mastery: float) -> str:
    if mastery >= 0.85:
        return "mastered"
    if mastery >= 0.70:
        return "proficient"
    if mastery >= 0.40:
        return "developing"
    return "struggling"


_STATUS = {"mastered": "completed", "proficient": "completed",
           "developing": "learning", "struggling": "needs_review"}


def _level(avg: float) -> str:
    if avg < 0.4:
        return "beginner"
    if avg < 0.6:
        return "elementary"
    if avg < 0.8:
        return "intermediate"
    return "advanced"


def _review_days(mastery: float) -> int:
    return 1 if mastery < 0.4 else 3 if mastery < 0.7 else 7 if mastery < 0.85 else 21


def record_outcome(db, user_id: str, subject: str, topic: str, score: float,
                   parent_topic: str = "", source_text: str = "", weight: float = 1.0) -> float:
    """Fold one quiz score (0-1) into the topic's mastery. Returns the new mastery."""
    col = db[config.PROGRESS_COLLECTION]
    key = {"user_id": user_id, "subject": subject, "topic": topic}
    doc = col.find_one(key) or {}
    score = max(0.0, min(1.0, float(score)))
    old = doc.get("mastery", config.MASTERY_START)
    new = old + min(1.0, config.MASTERY_ALPHA * weight) * (score - old)
    now = datetime.now(timezone.utc)
    fields = {"mastery": round(new, 4), "last_score": round(score, 4),
              "parent_topic": parent_topic, "last_seen": now,
              "next_review": now + timedelta(days=_review_days(new))}
    if source_text:                      # what the student studied: grounds later review questions
        fields["source_text"] = source_text[:2000]
    col.update_one(key, {"$set": fields, "$inc": {"attempts": 1}}, upsert=True)
    return new


def weak_topics(db, user_id: str, limit: int = 5) -> list[dict]:
    cur = db[config.PROGRESS_COLLECTION].find(
        {"user_id": user_id, "mastery": {"$lt": 0.7}}, {"_id": 0}
    ).sort("mastery", 1).limit(limit)
    return list(cur)


def due_for_review(db, user_id: str, limit: int = 5) -> list[dict]:
    cur = db[config.PROGRESS_COLLECTION].find(
        {"user_id": user_id, "next_review": {"$lte": datetime.now(timezone.utc)}}, {"_id": 0}
    ).sort("next_review", 1).limit(limit)
    return list(cur)


def snapshot(db, user_id: str) -> dict:
    """Derive profile-shaped progress (topics, subjects, strengths, weaknesses, gaps)."""
    rows = list(db[config.PROGRESS_COLLECTION].find({"user_id": user_id}, {"_id": 0}))
    topics, strengths, weaknesses, gaps = [], [], [], []
    by_subject: dict[str, list[float]] = {}
    for r in rows:
        m = float(r.get("mastery", 0.0))
        lab = label(m)
        attempts = int(r.get("attempts", 0))
        pct = round(m * 100)
        topics.append({"topic": r["topic"], "subject": r.get("subject", ""),
                       "status": _STATUS[lab], "mastery": lab})
        by_subject.setdefault(r.get("subject", ""), []).append(m)
        if lab == "mastered":
            strengths.append({"area": r["topic"], "evidence": f"Mastery {pct}% over {attempts} check(s)"})
        if lab == "struggling" and attempts >= 2:
            weaknesses.append({"area": r["topic"], "evidence": f"Mastery {pct}% after {attempts} check(s)"})
            gaps.append({"topic": r["topic"], "reason": "Repeatedly missed the lesson checks"})
    subjects = [{"subject": s, "level": _level(sum(v) / len(v))} for s, v in by_subject.items() if s]
    return {"topics": topics, "subjects": subjects, "strengths": strengths,
            "weaknesses": weaknesses, "knowledge_gaps": gaps}


def sync_to_profile(db, user_id: str) -> None:
    """Write the derived progress into the student's profile document (no LLM)."""
    snap = snapshot(db, user_id)
    db[config.PROFILE_COLLECTION].update_one(
        {"user_id": user_id},
        {"$set": {
            "Profile.knowledge_progress.topics": snap["topics"],
            "Profile.knowledge_progress.subjects": snap["subjects"],
            "Profile.knowledge_progress.knowledge_gaps": snap["knowledge_gaps"],
            "Profile.strengths": snap["strengths"],
            "Profile.weaknesses": snap["weaknesses"],
            "updated_at": datetime.now(timezone.utc),
        }},
    )


def due_summary(db, user_id: str) -> dict:
    """{'count': topics due now, 'next_due': when the next one is due (only if none are due)}."""
    col = db[config.PROGRESS_COLLECTION]
    now = datetime.now(timezone.utc)
    count = col.count_documents({"user_id": user_id, "next_review": {"$lte": now}})
    next_due = None
    if not count:
        cur = col.find({"user_id": user_id, "next_review": {"$gt": now}},
                       {"_id": 0, "next_review": 1}).sort("next_review", 1).limit(1)
        first = next(iter(cur), None)
        next_due = first["next_review"] if first else None
    return {"count": count, "next_due": next_due}
