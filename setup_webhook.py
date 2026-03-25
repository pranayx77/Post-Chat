"""
DexMind — Webhook Setup Script
================================
Deploy karne ke baad ek baar chalao:
  python setup_webhook.py

Ye Telegram ko batata hai ki updates kahan bhejna hai (Vercel URL).
"""

import os
import sys
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
VERCEL_URL     = os.getenv("VERCEL_URL")        # e.g. https://dexmind-bot.vercel.app
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dexmind_secret")

if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN env variable not set!")
    sys.exit(1)

if not VERCEL_URL:
    print("❌ VERCEL_URL env variable not set!")
    print("   Set it like: export VERCEL_URL=https://your-project.vercel.app")
    sys.exit(1)

webhook_url = f"{VERCEL_URL.rstrip('/')}/api/index"

print(f"🔗 Setting webhook to: {webhook_url}")

resp = requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
    json={
        "url": webhook_url,
        "secret_token": WEBHOOK_SECRET,
        "allowed_updates": ["message"],
        "drop_pending_updates": True,
    },
    timeout=10,
)

data = resp.json()

if data.get("ok"):
    print("✅ Webhook set successfully!")
    print(f"   URL     : {webhook_url}")
    print(f"   Secret  : {WEBHOOK_SECRET}")
else:
    print(f"❌ Failed to set webhook: {data}")
    sys.exit(1)

# Verify
info = requests.get(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getWebhookInfo",
    timeout=10,
).json()

print("\n📋 Webhook Info:")
wh = info.get("result", {})
print(f"   URL             : {wh.get('url')}")
print(f"   Pending updates : {wh.get('pending_update_count', 0)}")
print(f"   Last error      : {wh.get('last_error_message', 'None')}")
