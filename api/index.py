"""
DexMind — Telegram AI Agent (Vercel Webhook Edition)
=====================================================
- Vercel serverless compatible (webhook, not polling)
- python-telegram-bot==21.6
- OpenRouter free LLM
- Live weather via wttr.in
- Per-user session memory
- Date & Time (IST)
- Developer info
"""

import os
import re
import json
import logging
import asyncio
import urllib.parse
from datetime import datetime
from functools import partial
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler

import requests
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ─────────────────────────── CONFIG ───────────────────────────────────────────

TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL              = os.getenv("MODEL", "mistralai/mistral-7b-instruct:free")
WEBHOOK_SECRET     = os.getenv("WEBHOOK_SECRET", "dexmind_secret")

BOT_NAME     = "DexMind"
BOT_VERSION  = "3.23.26"
DEVELOPER    = "PraX"
DEV_TELEGRAM = "https://t.me/Dex_Error_404"
TIMEZONE     = ZoneInfo("Asia/Kolkata")

# ─────────────────────────── LOGGING ──────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────── OPENROUTER CLIENT ────────────────────────────────

ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

user_histories: dict[int, list[dict]] = {}
MAX_HISTORY_PAIRS = 5

SYSTEM_PROMPT = (
    f"You are {BOT_NAME}, a helpful and friendly AI assistant inside a Telegram chat. "
    "Keep answers clear and concise. "
    "If weather data is provided in the message, summarise it naturally. "
    "If current date/time is provided in the message, use it naturally in your response."
)

# ─────────────────────────── HELPERS ──────────────────────────────────────────

_DATETIME_RE = re.compile(
    r"\b(time|date|day|today|now|current time|current date|kal|aaj|kitne baje)\b",
    re.IGNORECASE,
)
_WEATHER_RE  = re.compile(
    r"\b(weather|temperature|forecast|rain|sunny|cloudy|hot|cold|humid)\b",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(r"\bin\s+([A-Za-z\s]+?)(?:[?!.,]|$)", re.IGNORECASE)


def _datetime_context() -> str:
    now = datetime.now(TIMEZONE)
    return (
        f"[Current date & time (IST): "
        f"{now.strftime('%A, %d %B %Y')} | {now.strftime('%I:%M %p')}]"
    )


def _fetch_weather(location: str = "") -> str:
    try:
        url = f"https://wttr.in/{urllib.parse.quote(location)}?format=3"
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        return r.text.strip()
    except Exception as e:
        logger.warning("Weather fetch failed: %s", e)
        return ""


def _weather_context(text: str) -> str:
    if not _WEATHER_RE.search(text):
        return ""
    m = _LOCATION_RE.search(text)
    loc = m.group(1).strip() if m else ""
    data = _fetch_weather(loc)
    return f"[Live weather: {data}]" if data else ""


def _sync_call(messages: list[dict]) -> str:
    resp = ai_client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=512,
        temperature=0.7,
    )
    content = resp.choices[0].message.content
    return content.strip() if content else "⚠️ Empty response from AI. Please try again."


async def get_ai_reply(user_id: int, user_text: str) -> str:
    history = user_histories.setdefault(user_id, [])

    context_parts = []
    weather_ctx = _weather_context(user_text)
    if weather_ctx:
        context_parts.append(weather_ctx)
    if _DATETIME_RE.search(user_text):
        context_parts.append(_datetime_context())

    content = "\n".join(context_parts + [user_text]).strip()
    history.append({"role": "user", "content": content})

    if len(history) > MAX_HISTORY_PAIRS * 2:
        history[:] = history[-(MAX_HISTORY_PAIRS * 2):]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    try:
        reply = await asyncio.get_event_loop().run_in_executor(
            None, partial(_sync_call, messages)
        )
    except Exception as e:
        logger.error("OpenRouter error: %s", e)
        history.pop()
        return "⚠️ Couldn't reach the AI right now. Please try again in a moment."

    history.append({"role": "assistant", "content": reply})
    return reply

# ─────────────────────────── TELEGRAM HANDLERS ────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name or "there"
    now  = datetime.now(TIMEZONE).strftime("%I:%M %p, %d %B %Y")
    await update.message.reply_text(
        f"👋 Hey {name}! I'm *{BOT_NAME}* — your personal AI assistant.\n"
        f"🕐 Current time (IST): {now}\n\n"
        "Try asking:\n"
        "• What's the weather in Mumbai?\n"
        "• What time is it?\n"
        "• Tell me a fun fact\n"
        "• Help me write an email\n\n"
        "Commands: /help  /clear  /model  /datetime  /developer",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"🧠 *{BOT_NAME} — Commands*\n\n"
        "/start      – Welcome message\n"
        "/help       – Show this help\n"
        "/clear      – Clear your chat history\n"
        "/model      – Show current AI model\n"
        "/datetime   – Show current date & time\n"
        "/developer  – About the developer\n\n"
        "Just type anything to chat with me!\n"
        "Include a city name for live weather. 🌦",
        parse_mode="Markdown",
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_histories.pop(update.effective_user.id, None)
    await update.message.reply_text("🗑️ Your conversation history has been cleared!")


async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"🤖 *Current AI Model:*\n`{MODEL}`",
        parse_mode="Markdown",
    )


async def cmd_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now(TIMEZONE)
    await update.message.reply_text(
        f"🗓 *Date & Time (IST)*\n\n"
        f"📅 Date : {now.strftime('%A, %d %B %Y')}\n"
        f"🕐 Time : {now.strftime('%I:%M:%S %p')}",
        parse_mode="Markdown",
    )


async def cmd_developer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"👨‍💻 *Developer Info*\n\n"
        f"🧑 Name       : {DEVELOPER}\n"
        f"📬 Telegram   : {DEV_TELEGRAM}\n"
        f"🤖 Bot        : {BOT_NAME} v`{BOT_VERSION}`",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    user_text = update.message.text.strip()
    if not user_text:
        return
    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )
        reply = await get_ai_reply(update.effective_user.id, user_text)
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error("Handler error: %s", e)
        await update.message.reply_text("⚠️ Something went wrong. Please try again.")

# ─────────────────────────── APP BUILDER ──────────────────────────────────────

def build_app():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).updater(None).build()
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("clear",     cmd_clear))
    app.add_handler(CommandHandler("model",     cmd_model))
    app.add_handler(CommandHandler("datetime",  cmd_datetime))
    app.add_handler(CommandHandler("developer", cmd_developer))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app

# ─────────────────────────── VERCEL ENTRYPOINT ────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(f"{BOT_NAME} v{BOT_VERSION} is alive! 🧠".encode())

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")
            return

        try:
            data = json.loads(body)
            app  = build_app()

            # Fix: create fresh event loop for Vercel serverless
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def process():
                await app.initialize()
                update = Update.de_json(data, app.bot)
                await app.process_update(update)
                await app.shutdown()

            loop.run_until_complete(process())
            loop.close()

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        except Exception as e:
            logger.error("Webhook error: %s", e)
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Internal Server Error")
