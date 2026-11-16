"""Authentication for the Streamlit UI (email + password, no email verification).

Shares the `users` collection and bcrypt hashing with the FastAPI app (api/), so an account
created here also works in the web app. Login survives a browser refresh: a random session
token is stored (hashed) in MongoDB and kept in a cookie.

Usage in ui.py:   user = require_login()
"""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import streamlit as st
import streamlit.components.v1 as components

from db import Database, db

COOKIE = "rt_st_session"
SESSION_DAYS = 14
MAX_FAILS, LOCK_MINUTES = 5, 10
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

users, sessions = db["users"], db["st_sessions"]
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


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


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
def _sign_in(email: str, password: str) -> None:
    email = email.strip().lower()
    user = users.find_one({"email": email})
    if user and user.get("locked_until") and _aware(user["locked_until"]) > now():
        return st.error(f"Too many failed attempts. Try again in {LOCK_MINUTES} minutes.")
    if user and user.get("verified") and not user.get("pw_hash"):
        return st.error("This account uses Google sign-in on the web app, so it has no password here.")
    if not user or not user.get("verified") or not _check_pw(password, user.get("pw_hash", "")):
        if user and user.get("verified"):
            fails = user.get("login_fails", 0) + 1
            upd = {"login_fails": fails}
            if fails >= MAX_FAILS:
                upd = {"login_fails": 0, "locked_until": now() + timedelta(minutes=LOCK_MINUTES)}
            users.update_one({"_id": user["_id"]}, {"$set": upd})
        return st.error("Email or password is incorrect. If you haven't signed up yet, use \"Create account\".")
    _start_session(user)


def _sign_up(name: str, email: str, password: str) -> None:
    email = email.strip().lower()
    if not name.strip():
        return st.error("Please enter your name.")
    if not EMAIL_RE.match(email):
        return st.error("Please enter a valid email address.")
    if len(password) < 8:
        return st.error("Password must be at least 8 characters.")
    existing = users.find_one({"email": email})
    if existing and existing.get("verified"):
        return st.error("An account with this email already exists. Sign in instead.")
    users.update_one({"email": email}, {
        "$set": {"email": email, "user_id": email, "name": name.strip(),
                 "pw_hash": _hash_pw(password), "verified": True},
        "$setOnInsert": {"created_at": now(), "reminders_enabled": True}}, upsert=True)
    _start_session(users.find_one({"email": email}))


def _login_page() -> None:
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.markdown("## 🎓 Renewed AI Tutor")
        st.caption("Sign in to open your personal learning space.")
        tab_in, tab_up = st.tabs(["Sign in", "Create account"])
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