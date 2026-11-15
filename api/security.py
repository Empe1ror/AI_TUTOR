import hashlib, hmac
from datetime import datetime, timedelta, timezone
import bcrypt, jwt
from fastapi import Cookie, HTTPException
from db import db
from . import config


def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode()[:72], bcrypt.gensalt()).decode()


def check_pw(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode()[:72], h.encode())
    except Exception:
        return False


def hash_code(email: str, code: str) -> str:
    return hmac.new(config.SECRET.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def make_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=config.TOKEN_DAYS)
    return jwt.encode({"sub": user_id, "exp": exp}, config.SECRET, algorithm="HS256")


def current_user(rt_token: str | None = Cookie(default=None)) -> dict:
    if not rt_token:
        raise HTTPException(401, "Please sign in.")
    try:
        uid = jwt.decode(rt_token, config.SECRET, algorithms=["HS256"])["sub"]
    except Exception:
        raise HTTPException(401, "Your session expired. Please sign in again.")
    user = db["users"].find_one({"user_id": uid, "verified": True}, {"_id": 0, "pw_hash": 0})
    if not user:
        raise HTTPException(401, "Account not found.")
    return user
