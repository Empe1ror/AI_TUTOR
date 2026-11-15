"""Persistence for lesson documents (one document per lesson)."""
from typing import Optional

from . import config


class LessonStore:
    def __init__(self, db):
        self.col = db[config.LESSONS_COLLECTION]

    def ensure_indexes(self) -> None:
        self.col.create_index([("user_id", 1), ("lesson_id", 1)], unique=True)
        self.col.create_index([("user_id", 1), ("status", 1), ("updated_at", -1)])

    def create(self, doc: dict) -> None:
        self.col.insert_one(dict(doc))   # copy: insert_one adds _id to what it receives

    def get(self, user_id: str, lesson_id: str) -> Optional[dict]:
        return self.col.find_one({"user_id": user_id, "lesson_id": lesson_id}, {"_id": 0})

    def get_active(self, user_id: str) -> Optional[dict]:
        cur = self.col.find({"user_id": user_id, "status": "active"}, {"_id": 0}) \
            .sort("updated_at", -1).limit(1)
        return next(iter(cur), None)

    def save(self, doc: dict) -> None:
        self.col.replace_one({"user_id": doc["user_id"], "lesson_id": doc["lesson_id"]}, doc)

    def list_recent(self, user_id: str, limit: int = 10) -> list[dict]:
        cur = self.col.find({"user_id": user_id}, {"_id": 0, "lesson_id": 1, "topic": 1, "subject": 1,
                                                    "status": 1, "current": 1, "created_at": 1}) \
            .sort("created_at", -1).limit(limit)
        return list(cur)
