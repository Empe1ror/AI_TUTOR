"""Settings for the API layer (all from environment variables / .env)."""
import os
from dotenv import load_dotenv
load_dotenv()

SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
APP_URL = os.getenv("APP_URL", "http://localhost:3000").rstrip("/")   # the Vercel site
COOKIE = "rt_token"
TOKEN_DAYS = 14
SECURE = APP_URL.startswith("https")
CRON_SECRET = os.getenv("CRON_SECRET", "")
MAIL_FROM = os.getenv("MAIL_FROM", "Renewed AI Tutor <no-reply@example.com>")
CODE_TTL_MIN = 10
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
