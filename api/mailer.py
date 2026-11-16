
"""Sends transactional emails through the Resend HTTP API."""

import logging
import os
import requests

from . import config

log = logging.getLogger(__name__)


def send_mail(to: str, subject: str, html: str, text: str) -> bool:
    api_key = os.getenv("RESEND_API_KEY")

    if not api_key:
        log.error("RESEND_API_KEY is not configured.")
        return False

    payload = {
        "from": config.MAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            json=payload,
            headers=headers,
            timeout=20,
        )

        if response.status_code not in (200, 201):
            log.error(
                "Resend email failed: HTTP %s - %s",
                response.status_code,
                response.text,
            )
            return False

        log.info("Email successfully accepted by Resend for %s", to)
        return True

    except requests.RequestException:
        log.exception("Could not connect to Resend API.")
        return False



def _wrap(title: str, body: str) -> str:
    return f"""<div style="background:#f6f3ff;padding:32px 12px;font-family:Inter,Arial,sans-serif">
<div style="max-width:520px;margin:auto;background:#fff;border:1px solid #e7e1fb;border-radius:20px;padding:32px;color:#17112e">
<img src="{config.APP_URL}/logo.png" alt="Renewed AI Tutor" height="48" style="display:block;margin-bottom:16px">
<h2 style="margin:0 0 12px;color:#6d28d9">{title}</h2>{body}
<p style="color:#8a84a3;font-size:12px;margin-top:28px">Renewed AI Tutor</p></div></div>"""


def code_email(name: str, code: str, purpose: str) -> tuple[str, str, str]:
    what = "confirm your email" if purpose == "signup" else "reset your password"
    subject = f"{code} is your Renewed AI Tutor code"
    html = _wrap("Your verification code", f"""<p>Hi {name or 'there'}, use this code to {what}:</p>
<p style="font-size:36px;letter-spacing:10px;font-weight:800;color:#7c3aed;margin:18px 0">{code}</p>
<p style="color:#5f5878">It expires in {config.CODE_TTL_MIN} minutes. If this wasn't you, ignore this email.</p>""")
    return subject, html, f"Your Renewed AI Tutor code is {code}. It expires in {config.CODE_TTL_MIN} minutes."


def reminder_email(name: str, topics: list[dict], day: int) -> tuple[str, str, str]:
    names = ", ".join(t["topic"] for t in topics[:3])
    subject = f"Time to revisit: {names}"
    items = "".join(f"<li style='margin:6px 0'><b>{t['topic']}</b> "
                    f"<span style='color:#5f5878'>(mastery {t['pct']}%)</span></li>" for t in topics)
    when = "yesterday" if day == 1 else "two days ago"
    html = _wrap("A quick review will help", f"""<p>Hi {name or 'there'}, you found these topics tricky {when}.
A short review now helps them stick:</p><ul>{items}</ul>
<p><a href="{config.APP_URL}/lessons" style="display:inline-block;background:#7c3aed;color:#fff;
padding:12px 22px;border-radius:12px;text-decoration:none;font-weight:600">Review now</a></p>""")
    text = f"Hi {name}, review these topics: {names}. Open {config.APP_URL}/lessons"
    return subject, html, text
