"""All learner-facing endpoints. Thin wrappers around your existing engines."""
from typing import Any, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel
from db import db, Database
from memory import chat_with_memory, seed_session_history
from rag import ingest_document, retrieve, format_context, list_documents, delete_document, NO_CONTEXT
from lesson import LessonEngine, rag_retriever, maybe_update_profile
from lesson.progress import due_for_review, due_summary
from lesson.store import LessonStore
from quiz import QuizEngine
from quiz import config as qcfg
from . import config, reminders
from .security import current_user

router = APIRouter()


def lesson_engine(u, docs=True):
    uid = u["user_id"]
    return LessonEngine(db, uid, retriever=rag_retriever(uid) if docs else None)


def quiz_engine(u):
    uid = u["user_id"]
    return QuizEngine(db, uid, retriever=rag_retriever(uid, k=qcfg.RETRIEVAL_K))


# ------------------------------------------------------------------ dashboard / settings
@router.get("/dashboard")
def dashboard(u=Depends(current_user)):
    uid = u["user_id"]
    rows = list(db["topic_progress"].find({"user_id": uid}, {"_id": 0}).sort("last_seen", -1))
    active = LessonStore(db).get_active(uid)
    profile = (Database(db, uid).get_student_profile() or {}).get("Profile", {})
    return {
        "name": u["name"],
        "stats": {"topics": len(rows), "due": due_summary(db, uid)["count"],
                  "quizzes": db["quizzes"].count_documents({"user_id": uid, "status": "completed"})},
        "due_topics": [r["topic"] for r in due_for_review(db, uid, 4)],
        "mastery": [{"topic": r["topic"], "pct": round(r.get("mastery", 0) * 100)} for r in rows[:6]],
        "active_lesson": {"topic": active["topic"], "current": active["current"] + 1,
                          "total": len(active["segments"])} if active else None,
        "goals": profile.get("student", {}).get("learning_goals", []),
    }


class SettingsIn(BaseModel):
    name: Optional[str] = None
    reminders_enabled: Optional[bool] = None


@router.patch("/settings")
def settings(b: SettingsIn, u=Depends(current_user)):
    upd = {}
    if b.name and b.name.strip():
        upd["name"] = b.name.strip()
        db["student_profile"].update_one({"user_id": u["user_id"]}, {"$set": {"Profile.student.name": upd["name"]}})
    if b.reminders_enabled is not None:
        upd["reminders_enabled"] = b.reminders_enabled
    if upd:
        db["users"].update_one({"user_id": u["user_id"]}, {"$set": upd})
    return {"ok": True}


# ------------------------------------------------------------------ free chat
class ChatIn(BaseModel):
    message: str
    session_id: str
    use_docs: bool = True


@router.post("/chat")
def chat(b: ChatIn, bg: BackgroundTasks, u=Depends(current_user)):
    uid, d = u["user_id"], Database(db, u["user_id"])
    seed_session_history(b.session_id, d.get_session_conversations(b.session_id))   # survives restarts
    context, sources = NO_CONTEXT, []
    if b.use_docs:
        try:
            context, sources = format_context(retrieve(uid, b.message))
        except Exception:
            pass
    profile = (d.get_student_profile() or {}).get("Profile", {})
    reply = chat_with_memory.invoke(
        {"student_profile": str(profile), "context": context, "input": b.message},
        config={"configurable": {"session_id": b.session_id}})
    d.add_conversation(b.session_id, [{"user_input": b.message, "ai_response": reply}])
    bg.add_task(maybe_update_profile, db, uid)
    return {"reply": reply, "sources": [{**s, "text": s["text"][:400]} for s in sources]}


@router.get("/chat/sessions")
def sessions(u=Depends(current_user)):
    rows = db["conversation"].aggregate([
        {"$match": {"user_id": u["user_id"]}}, {"$sort": {"created_at": 1}},
        {"$group": {"_id": "$session_id", "title": {"$first": {"$arrayElemAt": ["$conversations.user_input", 0]}},
                    "updated": {"$last": "$created_at"}}},
        {"$sort": {"updated": -1}}, {"$limit": 30}])
    return [{"session_id": r["_id"], "title": str(r["title"])[:60], "updated": r["updated"]} for r in rows]


@router.get("/chat/history")
def history(session_id: str, u=Depends(current_user)):
    out = []
    for r in Database(db, u["user_id"]).get_session_conversations(session_id):
        out += [{"role": "user", "content": r.get("user_input", "")}, {"role": "assistant", "content": r.get("ai_response", "")}]
    return out


# ------------------------------------------------------------------ lessons
class StartLesson(BaseModel):
    topic: str
    use_docs: bool = True


class Answers(BaseModel):
    answers: list[Any]


@router.get("/lesson/active")
def lesson_active(u=Depends(current_user)):
    return lesson_engine(u).get_active_view()


@router.get("/lesson/due")
def lesson_due(u=Depends(current_user)):
    return due_summary(db, u["user_id"])


@router.post("/lesson/start")
def lesson_start(b: StartLesson, u=Depends(current_user)):
    return lesson_engine(u, b.use_docs).start(b.topic)


@router.post("/lesson/review")
def lesson_review(u=Depends(current_user)):
    return lesson_engine(u).start_review()


@router.post("/lesson/{lid}/check")
def lesson_check(lid: str, u=Depends(current_user)):
    return lesson_engine(u).go_to_check(lid)


@router.post("/lesson/{lid}/submit")
def lesson_submit(lid: str, b: Answers, bg: BackgroundTasks, u=Depends(current_user)):
    view = lesson_engine(u).submit_answers(lid, b.answers)
    bg.add_task(reminders.schedule_weak, db, u["user_id"])
    return view


@router.post("/lesson/{lid}/continue")
def lesson_continue(lid: str, u=Depends(current_user)):
    return lesson_engine(u).continue_lesson(lid)


@router.post("/lesson/{lid}/abandon")
def lesson_abandon(lid: str, u=Depends(current_user)):
    lesson_engine(u).abandon(lid)
    return {"ok": True}


# ------------------------------------------------------------------ quizzes
class StartQuiz(BaseModel):
    topic: str
    quiz_type: str = "mcq"
    source: str = "knowledge"
    difficulty: str = "medium"


class QuizAnswers(BaseModel):
    answers: Optional[list[Any]] = None


@router.get("/quiz/active")
def quiz_active(u=Depends(current_user)):
    return quiz_engine(u).get_active_view()


@router.post("/quiz/start")
def quiz_start(b: StartQuiz, u=Depends(current_user)):
    return quiz_engine(u).start(b.topic, b.quiz_type, b.source, b.difficulty)


@router.post("/quiz/{qid}/submit")
def quiz_submit(qid: str, b: QuizAnswers, bg: BackgroundTasks, u=Depends(current_user)):
    view = quiz_engine(u).submit(qid, b.answers)
    bg.add_task(reminders.schedule_weak, db, u["user_id"])
    return view


@router.post("/quiz/{qid}/abandon")
def quiz_abandon(qid: str, u=Depends(current_user)):
    quiz_engine(u).abandon(qid)
    return {"ok": True}


# ------------------------------------------------------------------ library
@router.get("/library")
def library(u=Depends(current_user)):
    return list_documents(u["user_id"])


@router.post("/library")
async def upload(files: list[UploadFile] = File(...), u=Depends(current_user)):
    out = []
    for f in files:
        try:
            rec = ingest_document(u["user_id"], f.filename, await f.read())
            out.append({"filename": f.filename, "ok": True, "duplicate": rec.get("duplicate", False),
                        "n_chunks": rec.get("n_chunks"), "skipped": rec.get("skipped_chunks", 0)})
        except Exception as exc:
            out.append({"filename": f.filename, "ok": False, "error": str(exc)})
    return out


@router.delete("/library/{doc_id}")
def remove_doc(doc_id: str, u=Depends(current_user)):
    delete_document(u["user_id"], doc_id)
    return {"ok": True}


# ------------------------------------------------------------------ cron (called daily by Vercel Cron)
@router.post("/cron/send-reminders")
def cron(authorization: str = Header(default="")):
    if not config.CRON_SECRET or authorization != f"Bearer {config.CRON_SECRET}":
        raise HTTPException(401, "Unauthorized")
    return reminders.send_due(db)
