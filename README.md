# 🧠 DexMind — Telegram AI Agent

> A smart, personal AI assistant on Telegram — powered by **OpenRouter.ai** free LLMs, deployed on **Vercel**.

---

## ✨ Features

- 🧠 **Session Memory** — remembers last 5 conversations per user
- 🌦 **Live Weather** — just mention a city (e.g. *weather in Mumbai*)
- 🕐 **Date & Time** — real-time IST date/time support
- 🔀 **Switchable AI Model** — change model via env variable, no code edit needed
- ⚡ **Serverless** — runs on Vercel via Telegram Webhook
- 🎮 **BGMI Account Formatter** — converts raw account data into professional listings

---

## 🚀 Commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | Show all commands |
| `/clear` | Clear your chat history |
| `/model` | Show current AI model |
| `/datetime` | Current IST date & time |
| `/developer` | Developer info |
| `/bgmi` | 🎮 Activate BGMI account formatter mode |
| `/chat` | 💬 Exit BGMI mode, return to normal chat |

---

## 🎮 BGMI Account Formatter

Type `/bgmi` to enter BGMI mode. Then paste any raw, messy account data and the bot will instantly convert it into a clean professional listing.

**Example Input:**
```
rp s12 s13 s14 m1 m2 a7 a8 maxed, 3 mythic sets, 500 uc,
glacier m416 lv4 hit effect, akm red dawn lv3,
lvl 65, conqueror, 2 room cards
```

**Example Output:**
```
#G
|[ BGMI ULTIMATE ACCOUNT ]|

🎮 RP S12, S13, S14, M1, M2
       A7, A8 MAXED

➖ Mythic Fashion × 3
💵 500 UC

── Upgradable ──
🔫 Glacier M416 (Lv. 4) + Hit Effect
🔫 Red Dawn AKM (Lv. 3)

⛔️ Level   : 65
⛔️ Tier    : Conqueror
💳 Room Cards × 2

✍️ LOGIN :
✍️ PRICE :
✍️ BUY : @GalaxyAccounts ✅
```

---

## 🛠 Deploy on Vercel

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/dexmind-bot.git
cd dexmind-bot
```

### 2. Set environment variables in Vercel dashboard

| Variable | Value |
|---|---|
| `TELEGRAM_TOKEN` | Your bot token from [@BotFather](https://t.me/BotFather) |
| `OPENROUTER_API_KEY` | From [openrouter.ai](https://openrouter.ai) |
| `MODEL` | e.g. `mistralai/mistral-7b-instruct:free` |
| `WEBHOOK_SECRET` | Any random secret string e.g. `dexmind_secret` |

### 3. Deploy to Vercel
```bash
vercel --prod
```

### 4. Set Telegram Webhook (one time only)
```bash
export TELEGRAM_TOKEN=your_token
export VERCEL_URL=https://your-project.vercel.app
export WEBHOOK_SECRET=dexmind_secret

python setup_webhook.py
```

✅ Done! Your bot is live.

---

## 📁 Project Structure

```
dexmind-bot/
├── api/
│   └── index.py        ← Vercel entrypoint (webhook handler)
├── setup_webhook.py    ← Run once after deploy to register webhook
├── requirements.txt
├── vercel.json
└── README.md
```

---

## 🤖 Free Models (OpenRouter)

```
mistralai/mistral-7b-instruct:free
meta-llama/llama-3-8b-instruct:free
google/gemma-3-4b-it:free
```

> 💡 **Tip:** For BGMI formatting, use `mistralai/mistral-7b-instruct:free` or `meta-llama/llama-3-8b-instruct:free` for best results.

---

## ⚠️ Railway vs Vercel

| | Railway | Vercel |
|---|---|---|
| Mode | Polling (long-running) | Webhook (serverless) |
| Memory | Persists across messages | Resets on cold start |
| Cost | Free tier available | Free tier available |

> ⚠️ **Note:** BGMI mode and chat history are stored in-memory. They reset on Vercel cold starts. This is expected behavior for serverless deployments.

---

## 📦 Requirements

```
requests==2.32.3
```

> Pure `requests` only — no heavy frameworks. Fully compatible with Vercel serverless.

---

## 👨‍💻 Developer

**PraX** — [@Dex_Error_404](https://t.me/Dex_Error_404)

Bot Version: `3.23.26`
