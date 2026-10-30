"""MongoDB persistence for Renewed AI Tutor."""
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient, DESCENDING

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=4000) if MONGODB_URI else None
db = client["tutor_database"] if client else None

class Database:
    def __init__(self, database, user_id):
        if database is None:
            raise RuntimeError("MongoDB is not configured. Add MONGODB_URI to your .env file.")
        self.db = database
        self.user_id = user_id.strip().lower()
        if not self.user_id:
            raise ValueError("A student identifier is required.")

    def create_student_profile(self, name):
        profiles = self.db["student_profile"]
        profile = {
            "user_id": self.user_id,
            "Profile": {
                "student": {"name": name.strip() or self.user_id, "learning_goals": []},
                "background": {"experience_level": "unknown", "subjects_of_interest": []},
                "strengths": [], "weaknesses": [],
                "knowledge_progress": {"subjects": [], "topics": [], "knowledge_gaps": []},
                "learning_preferences": {
                    "pace": "unknown", "depth": "unknown", "step_by_step": "unknown",
                    "examples": "unknown", "analogies": "unknown", "visual_explanations": "unknown",
                    "practical_exercises": "unknown", "theory_vs_practice": "unknown",
                    "challenge_level": "unknown"
                }
            },
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        profiles.update_one({"user_id": self.user_id}, {"$setOnInsert": profile}, upsert=True)
        return self.get_student_profile()

    def get_student_profile(self):
        return self.db["student_profile"].find_one({"user_id": self.user_id})

    def get_session_id(self):
        # Retained for CLI compatibility. Streamlit creates explicit session IDs.
        count = self.db["conversation"].count_documents({"user_id": self.user_id})
        return f"{self.user_id}_conv_{count + 1:06d}"

    def add_conversation(self, session_id, history):
        if not history:
            return
        self.db["conversation"].insert_one({
            "user_id": self.user_id, "session_id": session_id,
            "conversations": history, "created_at": datetime.now(timezone.utc)
        })

    def get_conversations(self):
        return list(self.db["conversation"].find({"user_id": self.user_id}).sort("created_at", DESCENDING))

    def get_session_conversations(self, session_id):
        docs = self.db["conversation"].find({"user_id": self.user_id, "session_id": session_id}).sort("created_at", 1)
        rows = []
        for doc in docs:
            rows.extend(doc.get("conversations", []))
        return rows

    def update_student_profile(self, session_id):
        """Refresh the long-term profile from the current session; failures are returned to the UI."""
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        from llm import client
        from prompts import update_student_profile_prompt

        rows = self.get_session_conversations(session_id)
        if not rows:
            return self.get_student_profile()
        current = self.get_student_profile() or {}
        chain = ChatPromptTemplate.from_messages([
            ("system", update_student_profile_prompt + "\\n\\nExisting profile:\\n" + str(current.get("Profile", current))),
            ("human", "{conversations}")
        ]) | client | JsonOutputParser()
        result = chain.invoke({"conversations": rows})
        self.db["student_profile"].update_one(
            {"user_id": self.user_id},
            {"$set": {"Profile": result, "updated_at": datetime.now(timezone.utc)}},
            upsert=True
        )
        return self.get_student_profile()
