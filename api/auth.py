import random, secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from google.auth.transport import requests as g_requests
from google.oauth2 import id_token
from pydantic import BaseModel, EmailStr, Field
from db import db, Database
from . import config, mailer
from .security import check_pw, current_user, hash_code, hash_pw, make_token

router = APIRouter()
now = lambda: datetime.now(timezone.utc)
users, codes = db["users"], db["auth_codes"]


class Signup(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class Login(BaseModel):
    email: EmailStr
    password: str


class Verify(BaseModel):
    email: EmailStr
    code: str
    purpose: str = "signup"


class Resend(BaseModel):
    email: EmailStr
    purpose: str = "signup"


class Forgot(BaseModel):
    email: EmailStr


class Reset(BaseModel):
    email: EmailStr
    code: str
    password: str = Field(min_length=8, max_length=128)


def _issue(email: str, purpose: str, name: str = "") -> None:
    old = codes.find_one({"email": email, "purpose": purpose})
    if old and (now() - old["created_at"].replace(tzinfo=timezone.utc)).total_seconds() < 45:
        raise HTTPException(429, "Please wait a moment before requesting another code.")
    code = f"{random.SystemRandom().randrange(1_000_000):06d}"
    codes.replace_one({"email": email, "purpose": purpose}, {
        "email": email, "purpose": purpose, "code_hash": hash_code(email, code), "attempts": 0,
        "created_at": now(), "expires": now() + timedelta(minutes=config.CODE_TTL_MIN)}, upsert=True)
    subject, html, text = mailer.code_email(name, code, purpose)
    if not mailer.send_mail(email, subject, html, text):
        raise HTTPException(502, "We couldn't send the email. Please try again shortly.")


def _check(email: str, purpose: str, code: str) -> None:
    doc = codes.find_one({"email": email, "purpose": purpose})
    if not doc or doc["expires"].replace(tzinfo=timezone.utc) < now():
        raise HTTPException(400, "That code has expired. Request a new one.")
    if doc["attempts"] >= 5:
        raise HTTPException(429, "Too many attempts. Request a new code.")
    if not secrets.compare_digest(doc["code_hash"], hash_code(email, code.strip())):
        codes.update_one({"_id": doc["_id"]}, {"$inc": {"attempts": 1}})
        raise HTTPException(400, "That code isn't right. Check it and try again.")
    codes.delete_one({"_id": doc["_id"]})


def _login(resp: Response, user_id: str) -> None:
    resp.set_cookie(config.COOKIE, make_token(user_id), httponly=True, samesite="lax",
                    secure=config.SECURE, max_age=config.TOKEN_DAYS * 86400, path="/")


@router.post("/signup")
def signup(b: Signup):
    email = b.email.lower()
    existing = users.find_one({"email": email})
    if existing and existing.get("verified"):
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    users.update_one({"email": email}, {
        "$set": {"email": email, "user_id": email, "name": b.name.strip(), "pw_hash": hash_pw(b.password), "verified": False},
        "$setOnInsert": {"created_at": now(), "reminders_enabled": True}}, upsert=True)
    _issue(email, "signup", b.name.strip())
    return {"ok": True}


@router.post("/verify")
def verify(b: Verify, resp: Response):
    email = b.email.lower()
    _check(email, "signup", b.code)
    user = users.find_one({"email": email})
    if not user:
        raise HTTPException(400, "Account not found. Please sign up again.")
    users.update_one({"email": email}, {"$set": {"verified": True}})
    d = Database(db, email)
    if not d.get_student_profile():
        d.create_student_profile(user["name"])
    _login(resp, email)
    return {"ok": True}


@router.post("/resend")
def resend(b: Resend):
    email = b.email.lower()
    user = users.find_one({"email": email})
    if user and (b.purpose == "reset" or not user.get("verified")):
        _issue(email, b.purpose, user.get("name", ""))
    return {"ok": True}


@router.post("/login")
def login(b: Login, resp: Response):
    user = users.find_one({"email": b.email.lower()})
    if user and user.get("verified") and not user.get("pw_hash"):
        raise HTTPException(401, "This account uses Google sign-in. Tap \"Continue with Google\".")
    if not user or not check_pw(b.password, user.get("pw_hash", "")):
        raise HTTPException(401, "Email or password is incorrect.")
    if not user.get("verified"):
        _issue(user["email"], "signup", user["name"])
        raise HTTPException(403, "UNVERIFIED")
    _login(resp, user["user_id"])
    return {"ok": True}


@router.post("/forgot")
def forgot(b: Forgot):
    user = users.find_one({"email": b.email.lower(), "verified": True})
    if user:
        _issue(user["email"], "reset", user["name"])
    return {"ok": True}          # same answer either way: don't reveal which emails exist


@router.post("/reset")
def reset(b: Reset):
    email = b.email.lower()
    _check(email, "reset", b.code)
    users.update_one({"email": email}, {"$set": {"pw_hash": hash_pw(b.password)}})
    return {"ok": True}


class GoogleIn(BaseModel):
    credential: str


@router.post("/google")
def google(b: GoogleIn, resp: Response):
    if not config.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google sign-in isn't set up yet.")
    try:
        info = id_token.verify_oauth2_token(b.credential, g_requests.Request(), config.GOOGLE_CLIENT_ID)
    except Exception:
        raise HTTPException(401, "Google sign-in failed. Please try again.")
    if not info.get("email_verified"):
        raise HTTPException(401, "Your Google email isn't verified.")
    email = info["email"].lower()
    name = (info.get("name") or email.split("@")[0]).strip()
    existing = users.find_one({"email": email})
    if existing and not existing.get("verified"):
        users.delete_one({"email": email})     # drop a pending password signup: stops someone pre-registering your email
    users.update_one({"email": email}, {
        "$set": {"email": email, "user_id": email, "verified": True, "google_sub": info["sub"]},
        "$setOnInsert": {"name": name, "created_at": now(), "reminders_enabled": True}}, upsert=True)
    user = users.find_one({"email": email})
    d = Database(db, email)
    if not d.get_student_profile():
        d.create_student_profile(user["name"])
    _login(resp, email)
    return {"ok": True}


@router.post("/logout")
def logout(resp: Response):
    resp.delete_cookie(config.COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user=Depends(current_user)):
    return {"name": user["name"], "email": user["email"], "reminders_enabled": user.get("reminders_enabled", True)}
