"""Weak-topic reminders: 1 day and 2 days after a topic is found weak, the learner gets an email.

schedule_weak() runs after every lesson/quiz submission. send_due() runs from a daily cron.
A reminder is skipped if the learner has since improved (mastery >= 0.7) or turned reminders off.
"""
import logging
from datetime import datetime, timedelta, timezone
from lesson import config as lcfg
from lesson.progress import weak_topics
from . import mailer

log = logging.getLogger(__name__)
now = lambda: datetime.now(timezone.utc)


def schedule_weak(db, user_id: str) -> None:
    try:
        for w in weak_topics(db, user_id, 5):
            recent = db["reminders"].count_documents(
                {"user_id": user_id, "topic": w["topic"], "created_at": {"$gt": now() - timedelta(days=3)}})
            if recent:
                continue
            for day in (1, 2):
                db["reminders"].insert_one({"user_id": user_id, "topic": w["topic"], "day": day, "sent": False,
                                            "due": now() + timedelta(days=day), "created_at": now()})
    except Exception:
        log.exception("could not schedule reminders")


def send_due(db) -> dict:
    due = list(db["reminders"].find({"sent": False, "due": {"$lte": now()}}))
    by_user: dict[str, list[dict]] = {}
    for r in due:
        by_user.setdefault(r["user_id"], []).append(r)
    sent = skipped = 0
    for uid, rows in by_user.items():
        user = db["users"].find_one({"user_id": uid}) or {}
        topics = []
        if user.get("reminders_enabled", True) and user.get("email"):
            for r in rows:
                p = db[lcfg.PROGRESS_COLLECTION].find_one({"user_id": uid, "topic": r["topic"]}) or {}
                if p and p.get("mastery", 1) < 0.7 and r["topic"] not in [t["topic"] for t in topics]:
                    topics.append({"topic": r["topic"], "pct": round(p["mastery"] * 100)})
        if topics:
            subject, html, text = mailer.reminder_email(user.get("name", ""), topics, max(r["day"] for r in rows))
            ok = mailer.send_mail(user["email"], subject, html, text)
            sent += ok
            if not ok:
                continue                       # leave unsent: retried tomorrow
        else:
            skipped += 1
        db["reminders"].update_many({"_id": {"$in": [r["_id"] for r in rows]}}, {"$set": {"sent": True, "sent_at": now()}})
    return {"emails_sent": sent, "skipped": skipped}
