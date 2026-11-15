"""Run from the project root:   uvicorn api.main:app --reload --port 8000"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from lesson.errors import LessonError
from db import db
from . import auth, config, routes

if db is None:
    raise RuntimeError("MONGODB_URI is not set.")
try:
    db["users"].create_index("email", unique=True)
    db["users"].create_index("user_id")
    db["auth_codes"].create_index("expires", expireAfterSeconds=3600)
    db["reminders"].create_index([("sent", 1), ("due", 1)])
except Exception:
    logging.getLogger(__name__).exception("index setup skipped")

app = FastAPI(title="Renewed AI Tutor API")
app.add_middleware(CORSMiddleware, allow_origins=[config.APP_URL, "http://localhost:3000"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(LessonError)
async def lesson_error(_, exc: LessonError):
    return JSONResponse({"detail": str(exc), "debug": exc.detail}, status_code=400)


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(auth.router, prefix="/auth")
app.include_router(routes.router)
