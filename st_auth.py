"""Authentication for the Streamlit UI.

Shares the `users` / `auth_codes` collections, bcrypt hashing, code hashing and the Resend
mailer with the FastAPI app (api/), so one account works in both.

Login survives a browser refresh: a random session token is stored (hashed) in MongoDB
and kept in a cookie. Usage in ui.py:   user = require_login()
"""
import hashlib
import hmac
import random
import re
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import streamlit as st
import streamlit.components.v1 as components

from api import config, mailer          # api/__init__.py is empty, so no FastAPI is imported
from db import Database, db

COOKIE = "rt_st_session"
SESSION_DAYS = 14
MAX_FAILS, LOCK_MINUTES = 5, 10
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

users, codes, sessions = db["users"], db["auth_codes"], db["st_sessions"]
now = lambda: datetime.now(timezone.utc)
_aware = lambda t: t if t.tzinfo else t.replace(tzinfo=timezone.utc)


@st.cache_resource
def _ensure_indexes():
    try:
        sessions.create_index("expires", expireAfterSeconds=0)     # Mongo deletes expired sessions
        sessions.create_index("token_hash", unique=True)
        users.create_index("email", unique=True)
    except Exception:
        pass
    return True


# ------------------------------------------------------------------ hashing (same scheme as api/security.py)
def _hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode()[:72], bcrypt.gensalt()).decode()


def _check_pw(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode()[:72], h.encode())
    except Exception:
        return False


def _hash_code(email: str, code: str) -> str:
    return hmac.new(config.SECRET.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ------------------------------------------------------------------ email codes
def _issue(email: str, purpose: str, name: str = "") -> str | None:
    """Send a 6-digit code. Returns an error message, or None on success."""
    old = codes.find_one({"email": email, "purpose": purpose})
    if old and (now() - _aware(old["created_at"])).total_seconds() < 45:
        return "Please wait a moment before requesting another code."
    code = f"{random.SystemRandom().randrange(1_000_000):06d}"
    codes.replace_one({"email": email, "purpose": purpose}, {
        "email": email, "purpose": purpose, "code_hash": _hash_code(email, code), "attempts": 0,
        "created_at": now(), "expires": now() + timedelta(minutes=config.CODE_TTL_MIN)}, upsert=True)
    subject, html, text = mailer.code_email(name, code, purpose)
    if not mailer.send_mail(email, subject, html, text):
        return "We couldn't send the email. Please try again shortly."
    return None


def _check_code(email: str, purpose: str, code: str) -> str | None:
    """Returns an error message, or None if the code is right (and consumes it)."""
    doc = codes.find_one({"email": email, "purpose": purpose})
    if not doc or _aware(doc["expires"]) < now():
        return "That code has expired. Request a new one."
    if doc["attempts"] >= 5:
        return "Too many attempts. Request a new code."
    if not secrets.compare_digest(doc["code_hash"], _hash_code(email, code.strip())):
        codes.update_one({"_id": doc["_id"]}, {"$inc": {"attempts": 1}})
        return "That code isn't right. Check it and try again."
    codes.delete_one({"_id": doc["_id"]})
    return None


# ------------------------------------------------------------------ sessions and cookie
def _write_cookie(value: str, days: int) -> None:
    """Set (or, with days=0, delete) the cookie from the browser. Renders an invisible component."""
    max_age = days * 86400
    components.html(f"""<script>
      var P = window.parent;
      var secure = P.location.protocol === 'https:' ? '; Secure' : '';
      P.document.cookie = "{COOKIE}={value}; path=/; max-age={max_age}; SameSite=Lax" + secure;
    </script>""", height=0)


def _start_session(user: dict) -> None:
    d = Database(db, user["user_id"])
    if not d.get_student_profile():
        d.create_student_profile(user.get("name", ""))
    token = secrets.token_urlsafe(32)
    sessions.insert_one({"token_hash": _token_hash(token), "user_id": user["user_id"],
                         "created_at": now(), "expires": now() + timedelta(days=SESSION_DAYS)})
    users.update_one({"user_id": user["user_id"]}, {"$set": {"login_fails": 0, "locked_until": None}})
    st.session_state.user = {"user_id": user["user_id"], "email": user["email"], "name": user.get("name", "")}
    st.session_state._set_cookie = token
    st.session_state.pop("auth_pending", None)
    st.rerun()


def _user_from_cookie() -> dict | None:
    token = st.context.cookies.get(COOKIE)
    if not token:
        return None
    s = sessions.find_one({"token_hash": _token_hash(token)})
    if not s or _aware(s["expires"]) < now():
        return None
    return users.find_one({"user_id": s["user_id"], "verified": True}, {"_id": 0, "pw_hash": 0})


def logout() -> None:
    token = st.context.cookies.get(COOKIE)
    if token:
        sessions.delete_one({"token_hash": _token_hash(token)})
    st.session_state.clear()
    st.session_state._clear_cookie = True
    st.rerun()


# ------------------------------------------------------------------ pages
def _err(msg: str):
    st.error(msg)


def _sign_in(email: str, password: str) -> None:
    email = email.strip().lower()
    user = users.find_one({"email": email})
    if user and user.get("locked_until") and _aware(user["locked_until"]) > now():
        return _err(f"Too many failed attempts. Try again in {LOCK_MINUTES} minutes.")
    if user and user.get("verified") and not user.get("pw_hash"):
        return _err("This account uses Google sign-in on the web app. Use \"Forgot password\" to add a password.")
    if not user or not _check_pw(password, user.get("pw_hash", "")):
        if user:
            fails = user.get("login_fails", 0) + 1
            upd = {"login_fails": fails}
            if fails >= MAX_FAILS:
                upd = {"login_fails": 0, "locked_until": now() + timedelta(minutes=LOCK_MINUTES)}
            users.update_one({"_id": user["_id"]}, {"$set": upd})
        return _err("Email or password is incorrect.")
    if not user.get("verified"):
        problem = _issue(email, "signup", user.get("name", ""))
        if problem:
            return _err(problem)
        st.session_state.auth_pending = {"email": email, "purpose": "signup"}
        st.rerun()
    _start_session(user)


def _sign_up(name: str, email: str, password: str) -> None:
    email = email.strip().lower()
    if not name.strip():
        return _err("Please enter your name.")
    if not EMAIL_RE.match(email):
        return _err("Please enter a valid email address.")
    if len(password) < 8:
        return _err("Password must be at least 8 characters.")
    existing = users.find_one({"email": email})
    if existing and existing.get("verified"):
        return _err("An account with this email already exists. Sign in instead.")
    users.update_one({"email": email}, {
        "$set": {"email": email, "user_id": email, "name": name.strip(),
                 "pw_hash": _hash_pw(password), "verified": False},
        "$setOnInsert": {"created_at": now(), "reminders_enabled": True}}, upsert=True)
    problem = _issue(email, "signup", name.strip())
    if problem:
        return _err(problem)
    st.session_state.auth_pending = {"email": email, "purpose": "signup"}
    st.rerun()


def _forgot(email: str) -> None:
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        return _err("Please enter a valid email address.")
    user = users.find_one({"email": email, "verified": True})
    if user:
        problem = _issue(email, "reset", user.get("name", ""))
        if problem:
            return _err(problem)
    # same answer either way: don't reveal which emails exist
    st.session_state.auth_pending = {"email": email, "purpose": "reset"}
    st.rerun()


def _verify_form(pending: dict) -> None:
    email, purpose = pending["email"], pending["purpose"]
    st.markdown("### Check your email" if purpose == "signup" else "### Enter your reset code")
    st.caption(f"If that address has an account, a 6-digit code is on its way to **{email}**. "
               f"It expires in {config.CODE_TTL_MIN} minutes.")
    with st.form("verify_form"):
        code = st.text_input("6-digit code", max_chars=6)
        new_pw = st.text_input("New password (8+ characters)", type="password") if purpose == "reset" else ""
        go = st.form_submit_button("Verify and continue" if purpose == "signup" else "Set new password",
                                   type="primary", use_container_width=True)
    if go:
        if purpose == "reset" and len(new_pw) < 8:
            return _err("Password must be at least 8 characters.")
        problem = _check_code(email, purpose, code)
        if problem:
            return _err(problem)
        if purpose == "signup":
            user = users.find_one({"email": email})
            if not user:
                return _err("Account not found. Please sign up again.")
            users.update_one({"email": email}, {"$set": {"verified": True}})
            _start_session({**user, "verified": True})
        else:
            users.update_one({"email": email}, {"$set": {"pw_hash": _hash_pw(new_pw)}})
            st.session_state.pop("auth_pending", None)
            st.session_state.auth_notice = "Password updated. Sign in with your new password."
            st.rerun()
    c1, c2 = st.columns(2)
    if c1.button("Resend code", use_container_width=True):
        user = users.find_one({"email": email})
        problem = _issue(email, purpose, (user or {}).get("name", "")) if user else None
        st.warning(problem) if problem else st.success("A new code was sent.")
    if c2.button("Back", use_container_width=True):
        st.session_state.pop("auth_pending", None)
        st.rerun()


def _login_page() -> None:
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.markdown("## 🎓 Renewed AI Tutor")
        st.caption("Sign in to open your personal learning space.")
        if config.SECRET == "change-me-in-production":
            st.warning("JWT_SECRET is not set. Set a long random value before deploying.")
        pending = st.session_state.get("auth_pending")
        if pending:
            return _verify_form(pending)
        if st.session_state.get("auth_notice"):
            st.success(st.session_state.pop("auth_notice"))
        tab_in, tab_up, tab_forgot = st.tabs(["Sign in", "Create account", "Forgot password"])
        with tab_in:
            with st.form("signin_form"):
                email = st.text_input("Email", key="si_email")
                pw = st.text_input("Password", type="password", key="si_pw")
                go = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if go:
                _sign_in(email, pw)
        with tab_up:
            with st.form("signup_form"):
                name = st.text_input("Name", key="su_name")
                email = st.text_input("Email", key="su_email")
                pw = st.text_input("Password (8+ characters)", type="password", key="su_pw")
                go = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if go:
                _sign_up(name, email, pw)
        with tab_forgot:
            with st.form("forgot_form"):
                email = st.text_input("Email", key="fp_email")
                go = st.form_submit_button("Send reset code", type="primary", use_container_width=True)
            if go:
                _forgot(email)


# ------------------------------------------------------------------ public entry point
def require_login() -> dict:
    """Call right after st.set_page_config(). Shows the login page and stops the script until signed in."""
    _ensure_indexes()
    if st.session_state.pop("_clear_cookie", False):
        _write_cookie("", 0)
    if "user" not in st.session_state:
        user = _user_from_cookie()
        if user:
            st.session_state.user = {"user_id": user["user_id"], "email": user["email"], "name": user.get("name", "")}
    if "user" not in st.session_state:
        _login_page()
        st.stop()
    token = st.session_state.pop("_set_cookie", None)
    if token:
        _write_cookie(token, SESSION_DAYS)
    return st.session_state.user