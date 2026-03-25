# 🧠 DexMind — Telegram AI Agent

> A smart, personal AI assistant on Telegram — powered by **OpenRouter.ai** free LLMs, deployed on **Vercel**.

---

## ✨ Features

- 🧠 **Session Memory** — remembers last 5 conversations per user
- 🌦 **Live Weather** — just mention a city (e.g. *weather in Mumbai*)
- 🕐 **Date & Time** — real-time IST date/time support
- 🔀 **Switchable AI Model** — change model via env variable, no code edit needed
- ⚡ **Serverless** — runs on Vercel via Telegram Webhook

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

---

## ⚠️ Railway vs Vercel

| | Railway | Vercel |
|---|---|---|
| Mode | Polling (long-running) | Webhook (serverless) |
| Memory | Persists across messages | Resets on cold start |
| Cost | Free tier available | Free tier available |

---

## 📦 Requirements

```
python-telegram-bot==21.6
openai==1.51.0
requests==2.32.3
```

---

## 👨‍💻 Developer

**PraX** — [@Dex_Error_404](https://t.me/Dex_Error_404)

Bot Version: `3.23.26`
