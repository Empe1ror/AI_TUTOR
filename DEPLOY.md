# Renewed AI Tutor: API + Frontend

Put both folders in your existing project root:

```
renewed-ai-tutor/
├── api/               <- NEW  FastAPI layer (auth, email codes, reminders, endpoints)
├── web/               <- NEW  Next.js frontend (deploy this folder to Vercel)
├── lesson/ quiz/ rag/ db.py llm.py memory.py prompts.py   (your existing backend, unchanged)
└── requirements-api.txt   <- NEW  (append these to requirements.txt)
```

## 1. Run it locally

```bash
pip install -r requirements.txt -r requirements-api.txt
uvicorn api.main:app --reload --port 8000        # from the project root

cd web && npm install && npm run dev             # http://localhost:3000
```
Without SMTP settings, verification and reminder emails are printed in the API terminal.

## 2. Backend environment variables (.env)

```
NVIDIA_API_KEY=...   NVIDIA_BASE_URL=...   NVIDIA_EMBEDING_KEY=...   MONGODB_URI=...   (as today)
JWT_SECRET=<long random string>
APP_URL=https://your-site.vercel.app           # the Vercel URL, used in email links
CRON_SECRET=<long random string>               # same value as in Vercel
GOOGLE_CLIENT_ID=<see section 2b>
MAIL_FROM=Renewed AI Tutor <youraddress@gmail.com>
SMTP_HOST=smtp.gmail.com   SMTP_PORT=587   SMTP_USER=youraddress@gmail.com   SMTP_PASSWORD=<Gmail app password>
```
Gmail: turn on 2-step verification, then create an "App password". Any SMTP provider works (Brevo, Zoho, Mailgun).
For real launches use a provider with your own domain so emails don't land in spam.

## 2b. Google sign-in (one-time setup)

1. Go to console.cloud.google.com, create a project, then **APIs & Services > OAuth consent screen** (External) and fill in the app name and your email.
2. **Credentials > Create credentials > OAuth client ID > Web application.**
3. Under **Authorized JavaScript origins** add `http://localhost:3000` and your Vercel URL (for example `https://your-site.vercel.app`, plus any custom domain). No redirect URIs are needed.
4. Copy the Client ID into the backend as `GOOGLE_CLIENT_ID` and into Vercel as `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (same value). Redeploy after adding the Vercel variable.
5. While the consent screen is in "Testing", only test users you add can sign in. Click "Publish app" when you're ready for everyone.

If `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is not set, the Google button simply doesn't appear. Google accounts skip the email-code step, because Google has already verified the address.

## 3. Deploy

**Backend (FastAPI): host on Render, Railway or Fly.io.** Start command from the project root:
`uvicorn api.main:app --host 0.0.0.0 --port $PORT`. Add the env vars above.
Why not Vercel for the API: quizzes and lessons call the LLM for up to a minute, and Vercel's serverless
time limits and short-lived processes cut those off. The frontend proxies every call, so users never notice.

**Frontend (Vercel):** import the repo, set **Root Directory = `web`**, and add:
- `API_URL` = your deployed backend URL (no trailing slash)
- `CRON_SECRET` = same value as the backend

Pages call `/backend/...`, which Vercel rewrites to `API_URL`, so the login cookie stays on one domain
and the two halves behave as one app.

## 4. Weak-topic email reminders

After every lesson check or quiz, topics with mastery below 70% are scheduled for emails 1 day and 2 days later.
`web/vercel.json` runs a daily cron (08:00 UTC, 09:00 Lagos) calling `/api/cron/reminders`, which asks the backend
to send what is due. A reminder is skipped if the learner has improved since, or turned reminders off in Settings.
Vercel's free plan allows daily crons, which fits 1-day and 2-day reminders. Test it by hand:
`curl -X POST $API_URL/cron/send-reminders -H "Authorization: Bearer $CRON_SECRET"`

## 5. Good to know
- Accounts use the email as the learner ID. Old Streamlit student IDs (like "judah") are not linked automatically.
- Chat memory is rebuilt from MongoDB on each request, so it survives restarts and multiple servers.
- Not built yet: rate limiting beyond the code resend delay, tests for the API layer.
