"""Persistence for quiz documents (one document per quiz)."""
from typing import Optional

from . import config


class QuizStore:
    def __init__(self, db):
        self.col = db[config.QUIZZES_COLLECTION]

    def ensure_indexes(self) -> None:
        self.col.create_index([("user_id", 1), ("quiz_id", 1)], unique=True)
        self.col.create_index([("user_id", 1), ("status", 1), ("updated_at", -1)])

    def create(self, doc: dict) -> None:
        self.col.insert_one(dict(doc))

    def get(self, user_id: str, quiz_id: str) -> Optional[dict]:
        return self.col.find_one({"user_id": user_id, "quiz_id": quiz_id}, {"_id": 0})

    def get_active(self, user_id: str) -> Optional[dict]:
        cur = self.col.find({"user_id": user_id, "status": "active"}, {"_id": 0}) \
            .sort("updated_at", -1).limit(1)
        return next(iter(cur), None)

    def save(self, doc: dict) -> None:
        self.col.replace_one({"user_id": doc["user_id"], "quiz_id": doc["quiz_id"]}, doc)

    def list_recent(self, user_id: str, limit: int = 10) -> list[dict]:
        cur = self.col.find({"user_id": user_id}, {
            "_id": 0, "quiz_id": 1, "topic": 1, "subject": 1, "quiz_type": 1, "source": 1,
            "status": 1, "created_at": 1, "result.score": 1, "result.percent": 1,
        }).sort("created_at", -1).limit(limit)
        return list(cur)
