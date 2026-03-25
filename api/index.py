"""
DexMind — Telegram AI Agent (Vercel Lightweight Edition)
=========================================================
No heavy frameworks — pure requests + Telegram Bot API directly.
Vercel serverless compatible.
"""

import os
import re
import json
import logging
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler

import requests

# ─────────────────────────── CONFIG ───────────────────────────────────────────

TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL              = os.getenv("MODEL", "mistralai/mistral-7b-instruct:free")
WEBHOOK_SECRET     = os.getenv("WEBHOOK_SECRET", "dexmind_secret")

BOT_NAME     = "DexMind"
BOT_VERSION  = "3.23.26"
DEVELOPER    = "PraX"
DEV_TELEGRAM = "https://t.me/Dex_Error_404"
TIMEZONE     = ZoneInfo("Asia/Kolkata")

SYSTEM_PROMPT = (
    f"You are {BOT_NAME}, a helpful and friendly AI assistant inside a Telegram chat. "
    "Keep answers clear and concise. "
    "If weather data is provided, summarise it naturally. "
    "If date/time is provided, use it naturally."
)

BGMI_SYSTEM_PROMPT = """You are a BGMI (Battlegrounds Mobile India) account listing formatter.
Your ONLY job is to convert raw, unformatted account details into a professional, well-structured listing for selling gaming accounts.

STRICT FORMATTING RULES — follow exactly:

1. Header:
   #G (or tag like #G090 if given)
   |[ BGMI PREMIUM/ULTIMATE/BASIC ACCOUNT ]|
   (choose tier based on account value — ULTIMATE if mythics/high RP, PREMIUM if mid, BASIC if low)

2. Section order (include section only if data is available):
   🎮 RP history (Seasons: S1–S19, Months: M1–M6, Anniversaries: A1–A12)
   ➖ Mythic Fashion count
   💵 UC / Coins
   🎽 Special sets / outfits
   🔫 Upgradable guns section (header: "── Upgradable ──")
   🚘 Vehicle skins
   ⛔️ Account details (ID, level, server, tier, etc.)
   💳 Room cards

3. Gun format:
   🔫 [Skin Name] [Gun Name] (Lv. X)
   If maxed: (Lv. 7) ✅ Maxed
   If has hit effect: add "+ Hit Effect"
   Example: 🔫 Glacier M416 (Lv. 4) + Hit Effect

4. RP history — comma separated, line break for readability:
   🎮 RP S12, S13, S14, M1, M2
          A7, A8, A9, A10 MAXED

5. Vehicle section:
   List special/named skins first, then count generics (UAZ x2, Buggy x1, etc.)

6. Account details — each line starts with ⛔️

7. ALWAYS end with exactly:
✍️ LOGIN :
✍️ PRICE :
✍️ BUY : @GalaxyAccounts ✅

IMPORTANT RULES:
- Fix ALL spelling mistakes silently
- Use correct BGMI gun names (M416, AKM, AWM, M24, Kar98k, UZI, Vector, DP-28, MK14, Groza, etc.)
- Organize messy/random data into proper sections
- Add emojis consistently as shown
- Output ONLY the formatted listing — no explanations, no extra text
- If a section has no data, skip it entirely"""

MAX_HISTORY = 10  # max messages in history (5 pairs)

# ─────────────────────────── LOGGING ──────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory stores
user_histories: dict = {}   # { user_id: [{role, content}] }
bgmi_users:     set  = set()  # user_ids currently in BGMI mode

# ─────────────────────────── TELEGRAM HELPERS ─────────────────────────────────

def tg_send(chat_id: int, text: str, parse_mode: str = "Markdown") -> None:
    """Send message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        logger.error("Telegram send error: %s", e)


def tg_typing(chat_id: int) -> None:
    """Send typing action."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
            timeout=5,
        )
    except Exception:
        pass

# ─────────────────────────── WEATHER HELPER ───────────────────────────────────

_WEATHER_RE  = re.compile(
    r"\b(weather|temperature|forecast|rain|sunny|cloudy|hot|cold|humid)\b",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(r"\bin\s+([A-Za-z\s]+?)(?:[?!.,]|$)", re.IGNORECASE)


def get_weather(text: str) -> str:
    if not _WEATHER_RE.search(text):
        return ""
    m = _LOCATION_RE.search(text)
    loc = m.group(1).strip() if m else ""
    if not loc:
        return ""
    try:
        url = f"https://wttr.in/{urllib.parse.quote(loc)}?format=3"
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        return f"[Live weather: {r.text.strip()}]"
    except Exception:
        return ""

# ─────────────────────────── DATETIME HELPER ──────────────────────────────────

_DATETIME_RE = re.compile(
    r"\b(time|date|day|today|now|current time|current date|kal|aaj|kitne baje)\b",
    re.IGNORECASE,
)


def get_datetime() -> str:
    now = datetime.now(TIMEZONE)
    return (
        f"[Current date & time (IST): "
        f"{now.strftime('%A, %d %B %Y')} | {now.strftime('%I:%M %p')}]"
    )

# ─────────────────────────── AI CALL — CHAT ───────────────────────────────────

def ai_reply(user_id: int, user_text: str) -> str:
    history = user_histories.setdefault(user_id, [])

    # Build context
    parts = []
    w = get_weather(user_text)
    if w:
        parts.append(w)
    if _DATETIME_RE.search(user_text):
        parts.append(get_datetime())
    parts.append(user_text)

    content = "\n".join(parts).strip()
    history.append({"role": "user", "content": content})

    # Trim history
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": messages,
                "max_tokens": 400,
                "temperature": 0.7,
            },
            timeout=55,
        )
        r.raise_for_status()
        data  = r.json()
        reply = data["choices"][0]["message"]["content"].strip()
        history.append({"role": "assistant", "content": reply})
        return reply or "⚠️ Empty response. Try again."

    except Exception as e:
        logger.error("OpenRouter error: %s", e)
        history.pop()
        return "⚠️ Couldn't reach AI right now. Please try again."

# ─────────────────────────── AI CALL — BGMI FORMATTER ─────────────────────────

def ai_bgmi_format(raw_text: str) -> str:
    """Format raw BGMI account data into a professional listing."""
    messages = [
        {"role": "system", "content": BGMI_SYSTEM_PROMPT},
        {"role": "user",   "content": raw_text},
    ]
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": messages,
                "max_tokens": 700,
                "temperature": 0.2,   # low temp = consistent formatting
            },
            timeout=55,
        )
        r.raise_for_status()
        data  = r.json()
        reply = data["choices"][0]["message"]["content"].strip()
        return reply or "⚠️ Formatting failed. Please try again."

    except Exception as e:
        logger.error("BGMI format error: %s", e)
        return "⚠️ Couldn't reach AI right now. Please try again."

# ─────────────────────────── COMMAND HANDLERS ─────────────────────────────────

def handle_start(chat_id: int, first_name: str) -> None:
    now = datetime.now(TIMEZONE).strftime("%I:%M %p, %d %B %Y")
    tg_send(chat_id,
        f"👋 Hey {first_name}! I'm *{BOT_NAME}* — your personal AI assistant.\n"
        f"🕐 Current time (IST): {now}\n\n"
        "Try asking:\n"
        "• What's the weather in Mumbai?\n"
        "• What time is it?\n"
        "• Tell me a fun fact\n"
        "• Help me write an email\n\n"
        "🎮 *BGMI Account Formatter also available!*\n"
        "Type /bgmi to activate it.\n\n"
        "Commands: /help  /clear  /model  /datetime  /developer  /bgmi"
    )


def handle_help(chat_id: int) -> None:
    tg_send(chat_id,
        f"🧠 *{BOT_NAME} — Commands*\n\n"
        "/start      – Welcome message\n"
        "/help       – Show this help\n"
        "/clear      – Clear your chat history\n"
        "/model      – Show current AI model\n"
        "/datetime   – Show current date & time\n"
        "/developer  – About the developer\n"
        "/bgmi       – 🎮 BGMI account formatter mode\n"
        "/chat       – 💬 Exit BGMI mode, back to normal chat\n\n"
        "Just type anything to chat with me!\n"
        "Include a city name for live weather. 🌦"
    )


def handle_clear(chat_id: int, user_id: int) -> None:
    user_histories.pop(user_id, None)
    tg_send(chat_id, "🗑️ Your conversation history has been cleared!")


def handle_model(chat_id: int) -> None:
    tg_send(chat_id, f"🤖 *Current AI Model:*\n`{MODEL}`")


def handle_datetime(chat_id: int) -> None:
    now = datetime.now(TIMEZONE)
    tg_send(chat_id,
        f"🗓 *Date & Time (IST)*\n\n"
        f"📅 Date : {now.strftime('%A, %d %B %Y')}\n"
        f"🕐 Time : {now.strftime('%I:%M:%S %p')}"
    )


def handle_developer(chat_id: int) -> None:
    tg_send(chat_id,
        f"👨‍💻 *Developer Info*\n\n"
        f"🧑 Name       : {DEVELOPER}\n"
        f"📬 Telegram   : {DEV_TELEGRAM}\n"
        f"🤖 Bot        : {BOT_NAME} v`{BOT_VERSION}`"
    )


def handle_bgmi_enter(chat_id: int, user_id: int) -> None:
    """Activate BGMI formatting mode for this user."""
    bgmi_users.add(user_id)
    tg_send(chat_id,
        "🎮 *BGMI Account Formatter — ACTIVE*\n\n"
        "Paste raw BGMI account details and I'll instantly convert them into a "
        "clean, professional listing.\n\n"
        "*Example input:*\n"
        "`rp s12 s13 s14 m1 m2 a7 a8 maxed, 3 mythic fashion, 500 uc, "
        "glacier m416 lv4 hit effect, lvl 65, conqueror`\n\n"
        "➡️ Send your account data now!\n"
        "Type /chat anytime to go back to normal mode."
    )


def handle_bgmi_exit(chat_id: int, user_id: int) -> None:
    """Deactivate BGMI formatting mode."""
    bgmi_users.discard(user_id)
    tg_send(chat_id,
        "💬 *Normal chat mode restored!*\n"
        "Ask me anything. Type /bgmi to use the formatter again."
    )

# ─────────────────────────── UPDATE PROCESSOR ─────────────────────────────────

def process_update(data: dict) -> None:
    msg = data.get("message") or data.get("edited_message")
    if not msg:
        return

    chat_id    = msg["chat"]["id"]
    user_id    = msg["from"]["id"]
    first_name = msg["from"].get("first_name", "there")
    text       = msg.get("text", "").strip()

    if not text:
        return

    # ── Global commands (work in any mode) ────────────────────────────────────
    if text.startswith("/start"):
        handle_start(chat_id, first_name)
        return
    if text.startswith("/help"):
        handle_help(chat_id)
        return
    if text.startswith("/clear"):
        handle_clear(chat_id, user_id)
        return
    if text.startswith("/model"):
        handle_model(chat_id)
        return
    if text.startswith("/datetime"):
        handle_datetime(chat_id)
        return
    if text.startswith("/developer"):
        handle_developer(chat_id)
        return
    if text.startswith("/bgmi"):
        handle_bgmi_enter(chat_id, user_id)
        return
    if text.startswith("/chat"):
        handle_bgmi_exit(chat_id, user_id)
        return

    # ── Mode-based routing ─────────────────────────────────────────────────────
    tg_typing(chat_id)

    if user_id in bgmi_users:
        # BGMI formatting mode
        reply = ai_bgmi_format(text)
        tg_send(chat_id, reply, parse_mode="Markdown")
    else:
        # Normal AI chat mode
        reply = ai_reply(user_id, text)
        tg_send(chat_id, reply)

# ─────────────────────────── VERCEL ENTRYPOINT ────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # suppress default access logs

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(f"{BOT_NAME} v{BOT_VERSION} is alive! 🧠".encode())

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Webhook secret validation
        secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")
            return

        try:
            data = json.loads(body)
            process_update(data)
        except Exception as e:
            logger.error("Webhook error: %s", e)
        finally:
            # Always return 200 to Telegram to prevent retries
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
