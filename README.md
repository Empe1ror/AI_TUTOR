# Renewed AI Tutor 🎓🤖

### An AI-powered personalized learning assistant

Renewed AI Tutor is an adaptive tutoring system built on Large Language Models. It teaches in small steps, checks understanding with quizzes, remembers how each learner is doing, brings back topics that are fading, and can teach from the learner's own uploaded notes.

Built with Python, FastAPI, LangChain, NVIDIA AI, MongoDB Atlas, Next.js and Streamlit.

---

## 🎯 Project Vision

Instead of giving every student the same generic answer, the tutor considers:

- The student's level and background.
- Their goals and interests.
- What they have already learned, and how well.
- Where they struggle.
- Their own study material.

---

## ✨ Features

### Learning modes
- **Free chat.** Ask anything. The tutor remembers the conversation and the learner's profile, and can answer from uploaded documents with numbered citations like `[1]`.
- **Lessons.** A topic is planned into 3 to 6 short segments. Each segment is taught, then checked with a short quiz. The learner advances at 70% or higher, otherwise the segment is re-taught with a new explanation (3 tries, then it is marked as a gap and the lesson moves on).
- **Quizzes.** Multiple choice (10), short answer (10) or mixed (15), at easy, medium or hard difficulty. Questions come from the tutor's knowledge or only from the learner's uploaded documents.
- **Spaced review.** Each graded check schedules the topic's next review (1, 3, 7 or 21 days depending on mastery). "Review what's due" quizzes the learner on overdue topics.

### Personalization
- **Code-owned mastery.** Mastery is a moving average of real scores, calculated in code, not guessed by the model. It feeds strengths, weaknesses, knowledge gaps and review dates.
- **Automatic profile updates.** The LLM only proposes small new facts (goals, interests, preferences). Python validates and merges them, so a bad model reply cannot corrupt a profile.

### Study library (RAG)
- Upload PDF, DOCX, TXT or MD files (up to 10 MB each).
- Text is split into chunks, embedded and stored in MongoDB Atlas Vector Search.
- Every search is filtered by user ID, so learners only ever see their own documents.
- Lessons, quizzes and chat can all draw on the library.

### Web app (Next.js on Vercel)
- Landing page, sign up with email verification code, Google sign-in, password reset.
- Dashboard with progress, due reviews and mastery bars.
- Chat, Lessons, Quizzes, Library and Settings pages.
- Light and dark themes.
- 🎤 **Dictation.** A Dictate button on chat and on short-answer questions uses the browser's speech recognition (Chrome, Edge and Safari; hidden where unsupported).
- Weak-topic **email reminders** 1 and 2 days after a topic is found weak (skipped if the learner improved or turned reminders off).

### Streamlit app (original interface)
The first interface is still included and useful for quick testing: chat, lesson mode, quiz mode, document upload and a learner profile sidebar.

---

## 🧠 Architecture

```
Browser ──► Next.js (Vercel) ──/backend/*──► FastAPI ──► LangChain ──► NVIDIA models
                                                │
                                                └──► MongoDB Atlas (data + vector search)
```

The frontend calls `/backend/...`, which Vercel rewrites to the FastAPI server. This keeps the login cookie on one domain.

| Technology | Purpose |
|---|---|
| Python | Backend language |
| FastAPI | API layer (auth, endpoints, reminders) |
| LangChain | LLM orchestration |
| NVIDIA AI endpoints | Chat and embedding models |
| MongoDB Atlas | Data storage and Vector Search |
| Next.js / React | Main web frontend |
| Streamlit | Original testing interface |
| Resend | Transactional email |

---

## 📂 Project Structure

```text
renewed-ai-tutor/
├── api/                 FastAPI layer
│   ├── main.py          App entry point
│   ├── auth.py          Sign up, verify, login, Google, password reset
│   ├── routes.py        Dashboard, chat, lesson, quiz, library, cron endpoints
│   ├── security.py      Password hashing, JWT cookie, current user
│   ├── reminders.py     Weak-topic reminder scheduling and sending
│   ├── mailer.py        Email templates and Resend sending
│   └── config.py        API settings
├── lesson/              Lesson mode (state machine, mastery, profile deltas)
├── quiz/                Quiz mode (builds on lesson/)
├── rag/                 Document ingest, embedding, retrieval
├── web/                 Next.js frontend (deploy this folder to Vercel)
│   ├── app/             Pages (landing, signin, verify, forgot, dashboard, chat, lessons, quizzes, library, settings)
│   ├── components/      AppShell, Md, CodeInput, GoogleButton, ThemeToggle, DictateButton
│   └── lib/api.ts       API helper
├── ui.py                Streamlit interface
├── app.py               Command-line interface
├── llm.py               Model clients and the tutoring chain
├── memory.py            Chat history management
├── db.py                MongoDB connection and student profile operations
├── prompts.py           Tutor, profile and RAG prompts
├── requirements.txt     Core Python dependencies
├── requirements-api.txt Extra dependencies for the API
└── DEPLOY.md            Deployment guide
```

---

## ⚙️ Installation and Setup

### Prerequisites
- Python 3.10 or later
- Node.js 20.9 or later
- Git
- A **MongoDB Atlas** cluster (Vector Search runs on Atlas)
- NVIDIA API keys for the chat model and the embedding model

### 1. Clone and create a virtual environment

```bash
git clone <YOUR_REPOSITORY_URL>
cd renewed-ai-tutor
python -m venv venv
```

Activate it:

- Windows: `venv\Scripts\activate`
- Linux / macOS: `source venv/bin/activate`

### 2. Install dependencies

```bash
pip install -r requirements.txt -r requirements-api.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
# Models and database
NVIDIA_API_KEY=your_nvidia_api_key
NVIDIA_EMBEDING_KEY=your_nvidia_embedding_key
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
MONGODB_URI=your_mongodb_atlas_connection_string

# API layer
JWT_SECRET=a_long_random_string
APP_URL=http://localhost:3000
CRON_SECRET=a_long_random_string
RESEND_API_KEY=your_resend_api_key
MAIL_FROM=Renewed AI Tutor <no-reply@yourdomain.com>
GOOGLE_CLIENT_ID=optional_google_oauth_client_id
```

Optional: `EMBED_MODEL` and `EMBED_DIMS` (must match your embedding model and Atlas index), plus the lesson and quiz tuning values listed in `lesson/config.py` and `quiz/config.py`.

**Never commit your `.env` file or expose keys.**

### 4. Create the vector index (once)

```bash
python -m rag.setup_index
```

Wait until the index shows **READY** in Atlas (Search & Vector Search tab).

### 5. Run it

**Web app (recommended):**

```bash
# terminal 1, from the project root
uvicorn api.main:app --reload --port 8000

# terminal 2
cd web
npm install
npm run dev          # http://localhost:3000
```

**Streamlit version:**

```bash
streamlit run ui.py
```

**Command line:**

```bash
python app.py
```

---

## 🚀 Deployment

- **Backend (FastAPI):** host on Render, Railway or Fly.io with `uvicorn api.main:app --host 0.0.0.0 --port $PORT`. Not Vercel, because lessons and quizzes can take up to a minute.
- **Frontend (Next.js):** deploy the `web` folder to Vercel (Root Directory = `web`). Set `API_URL` (your backend URL), `CRON_SECRET` (same as the backend) and optionally `NEXT_PUBLIC_GOOGLE_CLIENT_ID`.
- **Reminders:** `web/vercel.json` runs a daily cron that calls the backend to send due reminder emails.

See [DEPLOY.md](DEPLOY.md) for the full walkthrough, including Google sign-in setup.

---

## 🧪 Testing

```bash
pip install pytest mongomock
python -m pytest lesson quiz -q      # logic tests, no API key or MongoDB needed
python -m lesson.cli                 # real end-to-end lesson in the terminal
python -m quiz.cli                   # real end-to-end quiz in the terminal
```

---

## 🛣️ Development Roadmap

### Phase 1: Core AI tutoring ✅
- [x] LLM integration and tutoring prompts
- [x] Conversational memory
- [x] Student profiles and MongoDB persistence
- [x] Streamlit interface

### Phase 2: Retrieval-Augmented Generation ✅
- [x] Document upload and text extraction
- [x] Chunking, embeddings and vector search
- [x] Retrieval-grounded answers with source citations

### Phase 3: Advanced student memory 🔄
- [x] Chat memory that survives restarts
- [x] Automatic profile updates from conversations
- [x] Learning progress and mastery tracking
- [x] Knowledge gaps and spaced review
- [ ] Richer long-term learning history and recommendations

### Phase 4: Intelligent assessment ✅
- [x] AI-generated quizzes (multiple choice, short answer, mixed)
- [x] Automatic grading with partial credit and feedback
- [x] Difficulty levels
- [ ] Fully adaptive difficulty based on past results

### Phase 5: Product and platform 🔄
- [x] Next.js web app with accounts, email verification and Google sign-in
- [x] Dashboard, light and dark themes
- [x] Email reminders for weak topics
- [x] Voice dictation for answers
- [ ] Rate limiting and API tests
- [ ] Agentic tutor: multi-step learning plans and resource recommendations

---

## 🔐 Security Notes

- Keep API keys and connection strings in `.env`, never in code.
- Passwords are hashed with bcrypt, and sessions use an HTTP-only JWT cookie.
- Verification codes are hashed, expire after 10 minutes and allow 5 attempts.
- Every document search is filtered by user ID.
- Use a strong, unique `JWT_SECRET` and `CRON_SECRET` in production.
- Dictation uses the browser's speech recognition. In Chrome, audio is processed by Google's servers, so mention this in your privacy note.

---

## 👨‍💻 Author

**Damperor**

Aspiring AI/ML Engineer | Educational Technology Enthusiast | Graphics Designer

---

*Renewed AI Tutor: rethinking how students learn with Artificial Intelligence.*