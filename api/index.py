"""
DexMind — Telegram AI Agent + Dashboard API (Vercel Serverless)
================================================================
All routes handled by single handler (vercel.json rewrites everything here).

Routes:
  GET  /api/config         → Bot status JSON
  POST /api/update-model   → Update AI model in memory
  POST /* (with secret)    → Telegram webhook
  GET  /*                  → Alive ping
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

MAX_HISTORY = 10  # max messages in history (5 pairs)

# Mutable model state — updated via /api/update-model
# Using a dict so it can be mutated across scope boundaries
_state = {
    "model": os.getenv("MODEL", "mistralai/mistral-7b-instruct:free"),
}

def get_model() -> str:
    return _state["model"]

def set_model(new_model: str) -> None:
    _state["model"] = new_model

# ─────────────────────────── LOGGING ──────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory history { user_id: [{role, content}] }
user_histories: dict = {}

# ─────────────────────────── CORS HELPER ──────────────────────────────────────

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Bot-Api-Secret-Token",
}

# ─────────────────────────── TELEGRAM HELPER ──────────────────────────────────

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

# ─────────────────────────── AI CALL ──────────────────────────────────────────

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
                "model": get_model(),
                "messages": messages,
                "max_tokens": 512,
                "temperature": 0.7,
            },
            timeout=25,
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
        "Commands: /help  /clear  /model  /datetime  /developer"
    )


def handle_help(chat_id: int) -> None:
    tg_send(chat_id,
        f"🧠 *{BOT_NAME} — Commands*\n\n"
        "/start      – Welcome message\n"
        "/help       – Show this help\n"
        "/clear      – Clear your chat history\n"
        "/model      – Show current AI model\n"
        "/datetime   – Show current date & time\n"
        "/developer  – About the developer\n\n"
        "Just type anything to chat with me!\n"
        "Include a city name for live weather. 🌦"
    )


def handle_clear(chat_id: int, user_id: int) -> None:
    user_histories.pop(user_id, None)
    tg_send(chat_id, "🗑️ Your conversation history has been cleared!")


def handle_model(chat_id: int) -> None:
    tg_send(chat_id, f"🤖 *Current AI Model:*\n`{get_model()}`")


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

    if text.startswith("/start"):
        handle_start(chat_id, first_name)
    elif text.startswith("/help"):
        handle_help(chat_id)
    elif text.startswith("/clear"):
        handle_clear(chat_id, user_id)
    elif text.startswith("/model"):
        handle_model(chat_id)
    elif text.startswith("/datetime"):
        handle_datetime(chat_id)
    elif text.startswith("/developer"):
        handle_developer(chat_id)
    else:
        tg_typing(chat_id)
        reply = ai_reply(user_id, text)
        tg_send(chat_id, reply)

# ─────────────────────────── VERCEL ENTRYPOINT ────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # Suppress default access logs

    # ── CORS preflight ────────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def _path(self) -> str:
        """Return path without query string."""
        return self.path.split("?")[0].rstrip("/")

    # ── GET routes ────────────────────────────────────────────────────────────

    def do_GET(self):
        p = self._path()

        if p == "/api/config":
            # ── GET /api/config — Dashboard status endpoint ──────────────────
            self._send_json(200, {
                "status":   "running",
                "model":    get_model(),
                "bot_name": BOT_NAME,
                "version":  BOT_VERSION,
                "developer": DEVELOPER,
                "active_users": len(user_histories),
            })

        else:
            # ── Alive ping ───────────────────────────────────────────────────
            body = f"{BOT_NAME} v{BOT_VERSION} is alive! 🧠".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            for k, v in CORS_HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

    # ── POST routes ───────────────────────────────────────────────────────────

    def do_POST(self):
        p      = self._path()
        body   = self._read_body()
        secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")

        # ── Telegram Webhook ─────────────────────────────────────────────────
        # Identified by the secret token header Telegram always sends
        if WEBHOOK_SECRET and secret == WEBHOOK_SECRET:
            try:
                data = json.loads(body)
                process_update(data)
                self._send_json(200, {"ok": True})
            except Exception as e:
                logger.error("Webhook error: %s", e)
                # Always return 200 so Telegram doesn't retry forever
                self._send_json(200, {"ok": True})
            return

        # ── POST /api/update-model ───────────────────────────────────────────
        if p == "/api/update-model":
            try:
                payload   = json.loads(body)
                new_model = payload.get("model", "").strip()
                if not new_model:
                    self._send_json(400, {"success": False, "error": "model field required"})
                    return
                set_model(new_model)
                logger.info("Model updated to: %s", new_model)
                self._send_json(200, {"success": True, "model": get_model()})
            except Exception as e:
                self._send_json(400, {"success": False, "error": str(e)})
            return

        # ── Unknown POST ─────────────────────────────────────────────────────
        self._send_json(404, {"error": "Not found"})
