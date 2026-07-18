"""
telegram.py – Send LinkedIn job-post notifications to a Telegram chat.

Usage (test):
    python telegram.py
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHAT_ID   = os.getenv("CHAT_ID", "").strip()

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(text: str) -> bool:
    """Send a raw Markdown message to the configured Telegram chat."""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ BOT_TOKEN or CHAT_ID not set in .env")
        return False

    resp = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        },
        timeout=10,
    )

    if resp.ok:
        print("✅ Message sent successfully.")
        return True
    else:
        print(f"❌ Failed to send: {resp.status_code} – {resp.text}")
        return False


def send_job_post(
    author: str,
    post_url: str,
    content: str,
    post_date: str,
    contact_info: str,
) -> bool:
    """Format a job-post row (CSV columns) and send it to Telegram."""
    url_line = f"[View post]({post_url})" if post_url and post_url != "N/A" else "_URL not available_"
    contact_line = contact_info if contact_info and contact_info not in ("N/A", "DM", "DM me", "Dm Me Resume") else "_DM the author_"

    # Truncate long content so the message stays readable
    snippet = content.strip()
    if len(snippet) > 400:
        snippet = snippet[:400].rstrip() + "…"

    text = (
        f"💼 *New Job Post Found*\n\n"
        f"👤 *Author:* {author}\n"
        f"🕒 *Posted:* {post_date}\n"
        f"📎 {url_line}\n\n"
        f"{snippet}\n\n"
        f"📩 *Contact:* {contact_line}"
    )

    return send_message(text)


