import os
import uuid
import streamlit as st
from dotenv import load_dotenv
from db import db, Database
from memory import chat_with_memory, seed_session_history, store

load_dotenv()
st.set_page_config(page_title="Renewed AI Tutor", page_icon="🎓", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root { --ink:#f3f2ff; --muted:#a7a5bd; --panel:#171625; --line:#302d48; --accent:#9b8cff; }
.stApp { background: radial-gradient(ellipse at 15% 0%, #252044 0%, #11101b 42%, #0d0c14 100%); color:var(--ink); }
[data-testid="stSidebar"] { background:#12111d; border-right:1px solid #29263c; }
.block-container { max-width: 1250px; padding-top: 2rem; padding-bottom: 3rem; }
.hero { padding: 1.35rem 1.5rem; border:1px solid #373151; border-radius:20px; background:linear-gradient(120deg,rgba(100,81,173,.22),rgba(28,25,45,.72)); margin-bottom:1.2rem; }
.eyebrow { text-transform:uppercase; letter-spacing:.18em; font-size:.72rem; color:#b8adff; font-weight:700; }
.hero h1 { margin:.35rem 0 .45rem; font-size:2.1rem; letter-spacing:-.04em; color:#fff; }
.hero p { color:#c2bfd5; margin:0; font-size:1rem; }
.metric-card { background:rgba(25,23,41,.82); border:1px solid #302d48; border-radius:14px; padding:1rem; min-height:95px; }
.metric-label { color:#aaa6c3; font-size:.8rem; margin-bottom:.3rem; }
.metric-value { color:#fff; font-size:1.25rem; font-weight:700; }
div[data-testid="stChatMessage"] { border:1px solid rgba(100,92,140,.18); border-radius:16px; padding:.7rem 1rem; background:rgba(23,22,37,.58); }
.stButton>button { border-radius:10px; border:1px solid #4a426b; }
.stButton>button[kind="primary"] { background:#8c78f6; border-color:#8c78f6; color:white; }
.small-note { color:#aaa6bd; font-size:.82rem; }
</style>
<div class="hero"><div class="eyebrow">RENEWED LEARNING EXPERIENCE</div><h1>Learn deeply. Grow confidently.</h1><p>Your adaptive AI tutor for clear explanations, guided practice, and lasting understanding.</p></div>
""", unsafe_allow_html=True)

if not os.getenv("NVIDIA_API_KEY"):
    st.error("NVIDIA_API_KEY is missing. Add it to your .env file before starting the tutor.")
    st.code("NVIDIA_API_KEY=your_nvidia_api_key\\nNVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1\\nMONGODB_URI=your_mongodb_connection_string", language="text")
    st.stop()
if db is None:
    st.error("MongoDB is not configured. Add MONGODB_URI to your .env file, then restart Streamlit.")
    st.stop()

# ---- Identity and persistent learner profile ----
with st.sidebar:
    st.markdown("## 🎓 Renewed AI Tutor")
    st.caption("Personal learning space")
    if "user_id" not in st.session_state:
        st.session_state.user_id = ""
    if "student_name" not in st.session_state:
        st.session_state.student_name = ""
    with st.form("student_login", clear_on_submit=False):
        name = st.text_input("Your name", value=st.session_state.student_name, placeholder="e.g. Ada")
        learner_id = st.text_input("Student ID", value=st.session_state.user_id, placeholder="Choose a consistent ID")
        login = st.form_submit_button("Open my learning space", type="primary", use_container_width=True)
    if login:
        if not name.strip() or not learner_id.strip():
            st.warning("Enter both your name and a student ID.")
        else:
            st.session_state.student_name = name.strip()
            st.session_state.user_id = learner_id.strip().lower().replace(" ", "_")
            st.session_state.pop("session_id", None)
            st.session_state.pop("messages", None)
            st.rerun()
    st.divider()

    if st.session_state.get("user_id"):
        try:
            database = Database(db, st.session_state.user_id)
            profile_doc = database.get_student_profile()
            if not profile_doc:
                profile_doc = database.create_student_profile(st.session_state.student_name)
            profile = profile_doc.get("Profile", {})
            student = profile.get("student", {}) if isinstance(profile, dict) else {}
            st.markdown(f"### Welcome, {student.get('name', st.session_state.student_name)}")
            st.caption("Your progress is saved to your learner profile.")
            if st.button("＋ Start a new lesson", use_container_width=True):
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.messages = []
                st.session_state.history_seeded = True
                st.rerun()
            with st.expander("Learning profile", expanded=False):
                background = profile.get("background", {}) if isinstance(profile, dict) else {}
                st.write("**Experience level**", background.get("experience_level", "unknown"))
                goals = student.get("learning_goals", [])
                st.write("**Learning goals**")
                st.write(" · ".join(goals) if goals else "Not identified yet")
                interests = background.get("subjects_of_interest", [])
                st.write("**Subjects of interest**")
                st.write(" · ".join(interests) if interests else "Not identified yet")
                topics = profile.get("knowledge_progress", {}).get("topics", []) if isinstance(profile, dict) else []
                st.write(f"**Topics tracked:** {len(topics)}")
                if st.button("Refresh profile from this lesson", use_container_width=True):
                    try:
                        with st.spinner("Updating your learning profile…"):
                            database.update_student_profile(st.session_state.session_id)
                        st.success("Learning profile updated.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Profile update failed: {exc}")
            st.divider()
            st.markdown("**Try a learning mode**")
            suggestions = ["Teach me a topic from the basics", "Help me solve a problem step by step", "Quiz me on what I know", "Help me debug my code"]
            for suggestion in suggestions:
                if st.button(suggestion, key=f"suggest_{suggestion}", use_container_width=True):
                    st.session_state.pending_prompt = suggestion
                    st.rerun()
        except Exception as exc:
            st.error(f"Could not connect to your learner data: {exc}")
            st.stop()

if not st.session_state.get("user_id"):
    st.info("Start by entering your name and a consistent Student ID in the left sidebar. Your ID is used to find your saved learning profile.")
    st.markdown("### What you can do here")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**🧠 Understand concepts**\n\nLearn from first principles with plain-language explanations and examples.")
    with c2:
        st.markdown("**🧩 Practise actively**\n\nWork through problems, hints, quizzes, and guided exercises.")
    with c3:
        st.markdown("**📈 Build continuity**\n\nKeep a long-term learner profile that can adapt as you progress.")
    st.stop()

# Ensure session and hydrate persistent chat history once per selected session.
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history_seeded" not in st.session_state:
    try:
        prior_rows = database.get_session_conversations(st.session_state.session_id)
        seed_session_history(st.session_state.session_id, prior_rows)
    except Exception:
        pass
    st.session_state.history_seeded = True

# Current session summary and chat surface
profile_doc = database.get_student_profile() or {}
profile = profile_doc.get("Profile", {})
student = profile.get("student", {}) if isinstance(profile, dict) else {}
background = profile.get("background", {}) if isinstance(profile, dict) else {}

m1, m2, m3 = st.columns(3)
with m1:
    st.markdown(f'<div class="metric-card"><div class="metric-label">LEARNER</div><div class="metric-value">{student.get("name", st.session_state.student_name)}</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="metric-card"><div class="metric-label">EXPERIENCE LEVEL</div><div class="metric-value">{str(background.get("experience_level", "unknown")).title()}</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="metric-card"><div class="metric-label">MESSAGES THIS LESSON</div><div class="metric-value">{len(st.session_state.messages)}</div></div>', unsafe_allow_html=True)

st.markdown("### Your tutor")
st.caption("Ask a question, name a topic, share code, or tell the tutor what you want to practise.")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

pending = st.session_state.pop("pending_prompt", None)
user_input = st.chat_input("What would you like to learn today?")
if pending and not user_input:
    user_input = pending

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    with st.chat_message("assistant"):
        response_area = st.empty()
        try:
            with st.spinner("Thinking through the best way to teach this…"):
                response = chat_with_memory.invoke(
                    {"student_profile": str(profile), "input": user_input},
                    config={"configurable": {"session_id": st.session_state.session_id}}
                )
            response_area.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            database.add_conversation(st.session_state.session_id, [{"user_input": user_input, "ai_response": response}])
        except Exception as exc:
            response_area.error(f"I couldn't complete that response. Check your API key, model access, and connection, then try again. Details: {exc}")
            st.session_state.messages.pop()
