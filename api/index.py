"""
DexMind — Telegram AI Agent + Dashboard (Vercel Serverless)
============================================================
All routes in one file — no separate dashboard.py needed.

Routes:
  GET  /dashboard          → Bot Control Panel HTML
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

MAX_HISTORY = 10

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

user_histories: dict = {}

# ─────────────────────────── DASHBOARD HTML ───────────────────────────────────

DASHBOARD_HTML = '<!DOCTYPE html>\n<html class="dark" lang="en">\n<head>\n<meta charset="utf-8"/>\n<meta content="width=device-width, initial-scale=1.0" name="viewport"/>\n<title>DexMind — Bot Control Panel</title>\n<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@200;400;600;800&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet"/>\n<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>\n<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>\n<script id="tailwind-config">\n  tailwind.config = {\n    darkMode: "class",\n    theme: {\n      extend: {\n        colors: {\n          "tertiary-fixed-dim": "#ffba4a",\n          "surface-dim": "#131313",\n          "primary-fixed-dim": "#47d6ff",\n          "inverse-primary": "#00677f",\n          "on-error-container": "#ffdad6",\n          "tertiary": "#ffd79f",\n          "tertiary-fixed": "#ffddb1",\n          "on-secondary": "#520070",\n          "inverse-surface": "#e5e2e1",\n          "on-error": "#690005",\n          "surface-container-high": "#2a2a2a",\n          "on-surface": "#e5e2e1",\n          "primary-container": "#00d2ff",\n          "on-tertiary-container": "#6c4700",\n          "on-tertiary-fixed": "#291800",\n          "error-container": "#93000a",\n          "surface-tint": "#47d6ff",\n          "surface-container": "#201f1f",\n          "on-tertiary": "#442b00",\n          "on-primary-fixed-variant": "#004e60",\n          "primary-fixed": "#b6ebff",\n          "on-secondary-container": "#e498ff",\n          "on-tertiary-fixed-variant": "#624000",\n          "on-primary-fixed": "#001f28",\n          "inverse-on-surface": "#313030",\n          "outline": "#859399",\n          "tertiary-container": "#ffb229",\n          "on-secondary-fixed": "#320046",\n          "secondary-fixed": "#f9d8ff",\n          "on-background": "#e5e2e1",\n          "surface-bright": "#3a3939",\n          "error": "#ffb4ab",\n          "secondary-fixed-dim": "#edb1ff",\n          "outline-variant": "#3c494e",\n          "on-secondary-fixed-variant": "#6e208c",\n          "surface-container-low": "#1c1b1b",\n          "secondary": "#edb1ff",\n          "surface-container-lowest": "#0e0e0e",\n          "surface-variant": "#353534",\n          "primary": "#a5e7ff",\n          "on-surface-variant": "#bbc9cf",\n          "on-primary-container": "#00566a",\n          "background": "#131313",\n          "surface": "#131313",\n          "secondary-container": "#6e208c",\n          "on-primary": "#003543",\n          "surface-container-highest": "#353534"\n        },\n        fontFamily: {\n          "headline": ["Manrope"],\n          "body": ["Inter"],\n          "label": ["Inter"]\n        },\n        borderRadius: { "DEFAULT": "1rem", "lg": "2rem", "xl": "3rem", "full": "9999px" },\n      },\n    },\n  }\n</script>\n<style>\n  .material-symbols-outlined {\n    font-variation-settings: \'FILL\' 0, \'wght\' 400, \'GRAD\' 0, \'opsz\' 24;\n  }\n  .liquid-glass {\n    background: rgba(28, 27, 27, 0.4);\n    backdrop-filter: blur(24px);\n    border: 1px solid rgba(229, 226, 225, 0.08);\n    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);\n  }\n  .neon-pulse {\n    box-shadow: 0 0 15px rgba(0, 210, 255, 0.3);\n  }\n  .hide-scrollbar::-webkit-scrollbar { display: none; }\n  .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }\n\n  /* Toast */\n  #toast {\n    position: fixed;\n    bottom: 5rem;\n    right: 2rem;\n    z-index: 9999;\n    padding: 0.75rem 1.5rem;\n    border-radius: 0.75rem;\n    font-size: 0.8rem;\n    font-weight: 700;\n    letter-spacing: 0.05em;\n    text-transform: uppercase;\n    backdrop-filter: blur(20px);\n    transition: opacity 0.4s ease, transform 0.4s ease;\n    opacity: 0;\n    transform: translateY(10px);\n    pointer-events: none;\n  }\n  #toast.show {\n    opacity: 1;\n    transform: translateY(0);\n  }\n  #toast.success {\n    background: rgba(0, 210, 255, 0.15);\n    border: 1px solid rgba(0, 210, 255, 0.3);\n    color: #a5e7ff;\n  }\n  #toast.error {\n    background: rgba(255, 73, 73, 0.15);\n    border: 1px solid rgba(255, 73, 73, 0.3);\n    color: #ffb4ab;\n  }\n\n  /* Skeleton shimmer */\n  .skeleton {\n    background: linear-gradient(90deg, #1c1b1b 25%, #2a2a2a 50%, #1c1b1b 75%);\n    background-size: 200% 100%;\n    animation: shimmer 1.5s infinite;\n    border-radius: 0.5rem;\n  }\n  @keyframes shimmer {\n    0% { background-position: 200% 0; }\n    100% { background-position: -200% 0; }\n  }\n\n  /* Model button selected state */\n  .model-btn.selected {\n    background: rgba(165, 231, 255, 0.08) !important;\n    color: #a5e7ff !important;\n  }\n  .model-btn.selected .model-check {\n    opacity: 1 !important;\n  }\n  .model-btn .model-check {\n    opacity: 0;\n  }\n\n  /* Spin on loading */\n  .spin { animation: spin 1s linear infinite; }\n  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }\n</style>\n</head>\n<body class="bg-background text-on-surface font-body selection:bg-primary/30 min-h-screen">\n\n<!-- ═══════════════════════ TOP NAV ═══════════════════════ -->\n<nav class="fixed top-0 w-full z-50 bg-[#131313]/30 backdrop-blur-2xl flex justify-between items-center px-8 h-20 shadow-[0_8px_32px_0_rgba(0,210,255,0.05)]">\n  <div class="flex items-center gap-4">\n    <span class="text-xl font-black text-[#a5e7ff] tracking-tighter font-headline">Bot Control Panel</span>\n    <div id="statusBadge" class="flex items-center gap-2 px-3 py-1 bg-primary/10 rounded-full border border-primary/20">\n      <span id="statusDot" class="w-2 h-2 bg-primary rounded-full animate-pulse"></span>\n      <span id="statusText" class="text-[10px] font-bold uppercase tracking-widest text-primary">Loading…</span>\n    </div>\n  </div>\n  <div class="flex items-center gap-6">\n    <div class="hidden md:flex items-center gap-8">\n      <a class="text-[#e5e2e1]/50 font-manrope font-bold tracking-tight hover:text-[#edb1ff] transition-colors duration-300" href="#">Dashboard</a>\n      <a class="text-[#a5e7ff] font-bold border-b-2 border-[#00d2ff] font-manrope tracking-tight" href="#">AI Settings</a>\n      <a class="text-[#e5e2e1]/50 font-manrope font-bold tracking-tight hover:text-[#edb1ff] transition-colors duration-300" href="#">Logs</a>\n    </div>\n    <div class="flex items-center gap-4 border-l border-outline-variant/30 pl-6">\n      <button class="material-symbols-outlined text-[#a5e7ff] active:scale-95 duration-200">sensors</button>\n      <div class="flex items-center gap-2 group cursor-pointer">\n        <img class="w-10 h-10 rounded-full object-cover ring-2 ring-primary/20 group-hover:ring-primary/50 transition-all"\n             src="https://lh3.googleusercontent.com/aida-public/AB6AXuAWvBdL28m3_h3xFo4IXE4bTacXWcz5oUfqBMYj5vq_W3ZlC9wQgjrT5KInC0WH9xTyS5zpSye72IuO-D5WnMR67CGCzJFsx5D-7jLALJq5pC6BFY4U3WO6xubnn7dIPzY3Kp6-VKYYsufhsMKwws2TkkOAjErBj6aKL5ym12uuvpAbgNLyAMgU0udpDxOseipKwl8a31Yog3ezOm8wOLRfoAQ-GYmbCTM-gyWvs33Bs0fukeqv4OJ3ioM-TV7W1ZFrEOYBXx77Sak"/>\n        <span class="material-symbols-outlined text-[#e5e2e1]/50">keyboard_arrow_down</span>\n      </div>\n    </div>\n  </div>\n</nav>\n\n<!-- ═══════════════════════ SIDEBAR ═══════════════════════ -->\n<aside class="hidden lg:flex flex-col py-8 h-screen w-72 fixed left-0 top-0 border-r border-[#e5e2e1]/10 bg-[#131313] z-40">\n  <div class="px-8 mb-12">\n    <div class="flex items-center gap-3">\n      <div class="w-10 h-10 bg-gradient-to-br from-primary to-secondary rounded-xl flex items-center justify-center">\n        <span class="material-symbols-outlined text-background font-bold" style="font-variation-settings: \'FILL\' 1;">psychology</span>\n      </div>\n      <div>\n        <h1 class="text-[#a5e7ff] font-black italic tracking-tight font-headline">DexMind Engine</h1>\n        <p id="sidebarVersion" class="font-manrope uppercase tracking-widest text-[10px] text-on-surface/40">v<span id="versionNum">…</span> Active</p>\n      </div>\n    </div>\n  </div>\n  <nav class="flex-1 space-y-2">\n    <a class="flex items-center gap-4 px-8 py-4 text-[#e5e2e1]/40 hover:text-[#e5e2e1] hover:bg-[#1c1b1b] transition-all duration-500 group" href="#">\n      <span class="material-symbols-outlined group-hover:translate-x-1 duration-300">dashboard</span>\n      <span class="font-manrope uppercase tracking-widest text-[10px]">Dashboard</span>\n    </a>\n    <a class="flex items-center gap-4 px-8 py-4 bg-gradient-to-r from-[#00d2ff]/10 to-transparent text-[#00d2ff] border-l-4 border-[#00d2ff] group" href="#">\n      <span class="material-symbols-outlined" style="font-variation-settings: \'FILL\' 1;">psychology</span>\n      <span class="font-manrope uppercase tracking-widest text-[10px] font-bold">AI Settings</span>\n    </a>\n  </nav>\n  <div class="px-6 mt-auto space-y-6">\n    <button id="deployBtn" onclick="deployModel()"\n      class="w-full py-4 bg-gradient-to-r from-primary-container to-secondary-container rounded-xl text-on-primary font-bold tracking-tight hover:shadow-[0_0_20px_rgba(0,210,255,0.3)] transition-all active:scale-[0.98] flex items-center justify-center gap-2">\n      <span id="deployIcon" class="material-symbols-outlined text-sm">rocket_launch</span>\n      Deploy Model\n    </button>\n    <div class="space-y-1">\n      <a class="flex items-center gap-4 px-4 py-2 text-[#e5e2e1]/40 hover:text-[#e5e2e1] transition-colors" href="#">\n        <span class="material-symbols-outlined text-sm">menu_book</span>\n        <span class="font-manrope uppercase tracking-widest text-[10px]">Docs</span>\n      </a>\n      <a class="flex items-center gap-4 px-4 py-2 text-error/60 hover:text-error transition-colors" href="#">\n        <span class="material-symbols-outlined text-sm">logout</span>\n        <span class="font-manrope uppercase tracking-widest text-[10px]">Logout</span>\n      </a>\n    </div>\n  </div>\n</aside>\n\n<!-- ═══════════════════════ MAIN ═══════════════════════ -->\n<main class="lg:ml-72 pt-28 pb-12 px-6 md:px-12 max-w-7xl">\n  <header class="mb-12">\n    <h2 class="text-4xl md:text-5xl font-headline font-extrabold tracking-tighter text-on-surface mb-2">System Orchestration</h2>\n    <p class="text-on-surface/50 text-lg max-w-2xl font-light">Fine-tune the neural architecture and integration parameters for the DexMind core engine.</p>\n  </header>\n\n  <!-- Live Stats Bar -->\n  <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">\n    <div class="liquid-glass rounded-xl p-4 flex flex-col gap-1">\n      <span class="text-[10px] uppercase tracking-widest text-primary/60 font-bold">Status</span>\n      <span id="statStatus" class="text-lg font-black text-primary font-headline">…</span>\n    </div>\n    <div class="liquid-glass rounded-xl p-4 flex flex-col gap-1">\n      <span class="text-[10px] uppercase tracking-widest text-secondary/60 font-bold">Version</span>\n      <span id="statVersion" class="text-lg font-black text-secondary font-headline">…</span>\n    </div>\n    <div class="liquid-glass rounded-xl p-4 flex flex-col gap-1">\n      <span class="text-[10px] uppercase tracking-widest text-tertiary/60 font-bold">Bot Name</span>\n      <span id="statBotName" class="text-lg font-black text-tertiary font-headline">…</span>\n    </div>\n    <div class="liquid-glass rounded-xl p-4 flex flex-col gap-1">\n      <span class="text-[10px] uppercase tracking-widest text-on-surface/40 font-bold">Active Users</span>\n      <span id="statUsers" class="text-lg font-black font-headline">…</span>\n    </div>\n  </div>\n\n  <!-- Bento Grid -->\n  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">\n\n    <!-- ── AI Model Configuration ── -->\n    <section class="liquid-glass rounded-xl p-8 lg:col-span-2 flex flex-col justify-between group hover:border-primary/30 transition-all duration-500">\n      <div>\n        <div class="flex items-center gap-4 mb-8">\n          <div class="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">\n            <span class="material-symbols-outlined text-primary">hub</span>\n          </div>\n          <div>\n            <h3 class="font-headline font-bold text-xl tracking-tight">AI Model Configuration</h3>\n            <p class="text-xs text-on-surface/40 uppercase tracking-widest">Core Intelligence Selection</p>\n          </div>\n        </div>\n\n        <div class="space-y-6">\n          <div class="space-y-4">\n            <div class="flex justify-between items-end ml-1">\n              <label class="text-[10px] uppercase tracking-widest text-primary font-bold">Primary Engine Selection</label>\n              <span id="activeModelLabel" class="text-[10px] font-bold text-primary/60 bg-primary/5 px-2 py-0.5 rounded-full border border-primary/10 uppercase tracking-widest">Loading…</span>\n            </div>\n            <!-- Search box -->\n            <div class="space-y-3">\n              <div class="relative group">\n                <span class="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-on-surface/30 group-focus-within:text-primary transition-colors">search</span>\n                <input id="modelSearch" oninput="filterModels(this.value)"\n                  class="w-full bg-surface-container-lowest border border-white/5 rounded-xl py-3 pl-12 pr-4 text-sm text-on-surface focus:ring-2 focus:ring-primary/40 focus:border-transparent transition-all placeholder:text-on-surface/20"\n                  placeholder="Search neural models…" type="text"/>\n              </div>\n\n              <!-- Model list -->\n              <div class="liquid-glass rounded-xl overflow-hidden border border-white/5">\n                <div id="modelList" class="max-h-[220px] overflow-y-auto hide-scrollbar divide-y divide-white/5">\n                  <!-- Populated by JS -->\n                  <div class="px-6 py-8 text-center text-on-surface/30 text-sm skeleton h-16"></div>\n                </div>\n              </div>\n            </div>\n          </div>\n\n          <!-- Model status bar -->\n          <div class="p-6 bg-surface-container-lowest/50 rounded-xl border border-white/5">\n            <div class="flex justify-between items-center mb-4">\n              <span class="text-sm font-medium">Active Model</span>\n              <span id="modelStatusBadge" class="text-[10px] bg-secondary/10 text-secondary px-2 py-0.5 rounded-full border border-secondary/20 uppercase tracking-widest font-bold">Syncing</span>\n            </div>\n            <div class="h-1.5 w-full bg-surface-container rounded-full overflow-hidden">\n              <div id="modelBar" class="h-full w-0 bg-gradient-to-r from-primary to-secondary neon-pulse transition-all duration-700"></div>\n            </div>\n            <p id="activeModelFull" class="text-[11px] text-on-surface/40 mt-3 italic font-mono">Fetching configuration…</p>\n          </div>\n        </div>\n      </div>\n\n      <!-- Action buttons -->\n      <div class="mt-8 flex items-center gap-4">\n        <button id="updateModelBtn" onclick="updateModel()"\n          class="flex-1 py-4 bg-surface-bright/50 hover:bg-primary text-on-surface hover:text-on-primary font-bold rounded-xl transition-all duration-300 flex items-center justify-center gap-2 group">\n          <span id="updateIcon" class="material-symbols-outlined text-sm">sync</span>\n          Update Model\n        </button>\n        <button onclick="refreshConfig()"\n          class="p-4 bg-surface-container-highest/30 hover:bg-surface-container-highest rounded-xl transition-colors" title="Refresh config">\n          <span class="material-symbols-outlined">refresh</span>\n        </button>\n      </div>\n    </section>\n\n    <!-- ── API Management ── -->\n    <section class="liquid-glass rounded-xl p-8 flex flex-col group hover:border-secondary/30 transition-all duration-500">\n      <div class="flex items-center gap-4 mb-8">\n        <div class="w-12 h-12 rounded-full bg-secondary/10 flex items-center justify-center">\n          <span class="material-symbols-outlined text-secondary">api</span>\n        </div>\n        <div>\n          <h3 class="font-headline font-bold text-xl tracking-tight">API Management</h3>\n          <p class="text-xs text-on-surface/40 uppercase tracking-widest">Connectivity &amp; Security</p>\n        </div>\n      </div>\n      <div class="space-y-6 flex-1">\n        <div class="space-y-2">\n          <label class="text-[10px] uppercase tracking-widest text-secondary font-bold ml-1">Bot API Token</label>\n          <div class="relative">\n            <input id="apiTokenInput" class="w-full bg-surface-container-lowest border-none rounded-xl py-4 px-6 text-on-surface focus:ring-2 focus:ring-secondary/40" type="password" value="sk-dexmind-4920kL-9921"/>\n            <button onclick="toggleToken()" class="material-symbols-outlined absolute right-4 top-1/2 -translate-y-1/2 text-on-surface/30 hover:text-secondary transition-colors" id="visibilityIcon">visibility</button>\n          </div>\n        </div>\n        <div class="space-y-2">\n          <label class="text-[10px] uppercase tracking-widest text-secondary font-bold ml-1">Webhook URL</label>\n          <input id="webhookInput" class="w-full bg-surface-container-lowest border-none rounded-xl py-4 px-6 text-on-surface focus:ring-2 focus:ring-secondary/40" placeholder="https://your-project.vercel.app/api/index" type="text"/>\n        </div>\n      </div>\n      <div class="mt-8 p-4 bg-error/5 border border-error/10 rounded-xl">\n        <p class="text-[11px] text-error/80 leading-relaxed">\n          <span class="font-bold">Security Alert:</span> Do not share your API token. Anyone with access can control your bot nodes.\n        </p>\n      </div>\n    </section>\n\n    <!-- ── Notification Preferences ── -->\n    <section class="liquid-glass rounded-xl p-8 lg:col-span-1 group">\n      <div class="flex items-center gap-4 mb-8">\n        <div class="w-12 h-12 rounded-full bg-tertiary/10 flex items-center justify-center">\n          <span class="material-symbols-outlined text-tertiary">notifications_active</span>\n        </div>\n        <div>\n          <h3 class="font-headline font-bold text-xl tracking-tight">Alerts</h3>\n          <p class="text-xs text-on-surface/40 uppercase tracking-widest">Event Subscriptions</p>\n        </div>\n      </div>\n      <div class="space-y-6">\n        <div class="flex items-center justify-between p-4 bg-surface-container-lowest/30 rounded-xl">\n          <div>\n            <p class="font-bold text-sm">Message Alerts</p>\n            <p class="text-[11px] text-on-surface/40">Direct user interaction notifications</p>\n          </div>\n          <label class="relative inline-flex items-center cursor-pointer">\n            <input checked class="sr-only peer" type="checkbox"/>\n            <div class="w-11 h-6 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[\'\'] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>\n          </label>\n        </div>\n        <div class="flex items-center justify-between p-4 bg-surface-container-lowest/30 rounded-xl">\n          <div>\n            <p class="font-bold text-sm">System Health</p>\n            <p class="text-[11px] text-on-surface/40">Uptime and resource utilization logs</p>\n          </div>\n          <label class="relative inline-flex items-center cursor-pointer">\n            <input checked class="sr-only peer" type="checkbox"/>\n            <div class="w-11 h-6 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[\'\'] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>\n          </label>\n        </div>\n        <div class="flex items-center justify-between p-4 bg-surface-container-lowest/30 rounded-xl">\n          <div>\n            <p class="font-bold text-sm">User Sign-ups</p>\n            <p class="text-[11px] text-on-surface/40">New registration milestones</p>\n          </div>\n          <label class="relative inline-flex items-center cursor-pointer">\n            <input class="sr-only peer" type="checkbox"/>\n            <div class="w-11 h-6 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[\'\'] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>\n          </label>\n        </div>\n      </div>\n    </section>\n\n    <!-- ── Advanced Settings ── -->\n    <section class="liquid-glass rounded-xl p-8 lg:col-span-2 group hover:border-primary/20 transition-all duration-500">\n      <div class="flex items-center gap-4 mb-8">\n        <div class="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">\n          <span class="material-symbols-outlined text-primary">tune</span>\n        </div>\n        <div>\n          <h3 class="font-headline font-bold text-xl tracking-tight">Advanced Settings</h3>\n          <p class="text-xs text-on-surface/40 uppercase tracking-widest">Creative Parameter Tuning</p>\n        </div>\n      </div>\n      <div class="grid grid-cols-1 md:grid-cols-2 gap-12">\n        <div class="space-y-8">\n          <div class="space-y-4">\n            <div class="flex justify-between items-center">\n              <label class="text-[10px] uppercase tracking-widest text-primary font-bold">Temperature</label>\n              <span id="tempValue" class="text-xs font-mono text-primary bg-primary/10 px-2 py-0.5 rounded">0.70</span>\n            </div>\n            <input id="tempSlider" oninput="document.getElementById(\'tempValue\').textContent = parseFloat(this.value).toFixed(2)"\n              class="w-full h-1.5 bg-surface-container-lowest rounded-lg appearance-none cursor-pointer accent-primary"\n              type="range" min="0" max="2" step="0.01" value="0.7"/>\n            <div class="flex justify-between text-[10px] text-on-surface/30">\n              <span>PRECISE</span><span>BALANCED</span><span>CREATIVE</span>\n            </div>\n          </div>\n          <div class="p-6 bg-primary/5 rounded-xl border border-primary/10">\n            <p class="text-xs leading-relaxed text-on-surface/70">\n              <span class="text-primary font-bold">Pro Tip:</span> Higher temperature values result in more diverse but less predictable outputs. 0.7 is recommended for general assistance.\n            </p>\n          </div>\n        </div>\n        <div class="space-y-4">\n          <label class="text-[10px] uppercase tracking-widest text-primary font-bold ml-1">System Prompt Context</label>\n          <textarea id="systemPromptInput"\n            class="w-full bg-surface-container-lowest border-none rounded-xl py-4 px-6 text-on-surface text-sm focus:ring-2 focus:ring-primary/40 hide-scrollbar resize-none"\n            placeholder="Enter the core personality and rules for the AI…" rows="6">You are DexMind, a helpful and friendly AI assistant inside a Telegram chat. Keep answers clear and concise. If weather data is provided, summarise it naturally. If date/time is provided, use it naturally.</textarea>\n        </div>\n      </div>\n      <div class="mt-8 flex justify-end">\n        <button onclick="showToast(\'Settings saved locally ✓\', \'success\')"\n          class="px-12 py-4 bg-on-surface text-background font-black rounded-xl hover:scale-105 active:scale-95 transition-all">\n          Apply Changes\n        </button>\n      </div>\n    </section>\n\n  </div><!-- /bento grid -->\n\n  <!-- Footer -->\n  <footer class="mt-24 pt-12 border-t border-outline-variant/10 flex flex-col md:flex-row justify-between items-center gap-8">\n    <div class="flex items-center gap-6 opacity-40 grayscale hover:grayscale-0 hover:opacity-100 transition-all duration-700">\n      <img class="w-8 h-8 rounded-lg grayscale"\n           src="https://lh3.googleusercontent.com/aida-public/AB6AXuDAp7yQfQvP4V7jvdgEtZqga6v9iiFzlq4wVOReYJm_Khmtij6TYumDBzvHOS9kXp4AbbASUfTtmwSI9Tfyl0Mbl689FQqg7EXpUATgXHROC5uv91_FgWEBvWDAER68uP9-_Bo9I7kUJoFwdvvSvveZNMDlYQjU32i7Hm67OWt64Gfz4x8GwAhx_wag9DpMI0BLFsShdaqEaUss2IYkpEn9npiNV9lzM7rkNvipetNwm1_E4Mc80ek57Li-uvfhRrRIr1Yf3w6Aw1Y"/>\n      <span class="text-xs tracking-[0.3em] font-headline font-bold">DEXMIND ENGINE PROTOCOL</span>\n    </div>\n    <p class="text-[10px] uppercase tracking-widest text-on-surface/30">© 2025 DexMind Intelligence Systems · Developer: PraX</p>\n  </footer>\n</main>\n\n<!-- Floating pulse -->\n<div class="fixed bottom-8 right-8 z-50">\n  <div class="liquid-glass rounded-full p-4 flex items-center gap-4 border border-primary/20 neon-pulse">\n    <div class="relative w-4 h-4">\n      <div class="absolute inset-0 bg-primary rounded-full blur-sm animate-pulse"></div>\n      <div class="relative w-4 h-4 bg-primary rounded-full"></div>\n    </div>\n    <span class="text-[10px] font-bold uppercase tracking-widest text-primary pr-2">Processing Logs</span>\n  </div>\n</div>\n\n<!-- Toast -->\n<div id="toast"></div>\n\n<!-- ═══════════════════════ JAVASCRIPT ═══════════════════════ -->\n<script>\n// ─── Config ───────────────────────────────────────────────────────────────────\n// Change this to your Vercel deployment URL in production.\n// For local testing, leave as empty string (relative URLs).\nconst API_BASE = "https://dex-mind-66kj-nlr3vno4m-pranayx77s-projects.vercel.app/";   // e.g. "https://your-project.vercel.app"\n\nconst MODELS = [\n  { id: "mistralai/mistral-7b-instruct:free",   label: "Mistral 7B Instruct",    desc: "Optimized for Reasoning · Free" },\n  { id: "meta-llama/llama-3-8b-instruct:free",  label: "Llama 3 (8B Instruct)",  desc: "Meta Open Source · Free" },\n  { id: "google/gemma-3-4b-it:free",            label: "Gemma 3 (4B IT)",         desc: "Google Lightweight · Free" },\n  { id: "anthropic/claude-3.5-sonnet",          label: "Claude 3.5 Sonnet",       desc: "Anthropic High-Speed" },\n  { id: "openai/gpt-4o-mini",                   label: "GPT-4o Mini",             desc: "OpenAI Efficient" },\n];\n\nlet selectedModel = null;   // tracks what the user picked in UI\nlet currentModel  = null;   // what backend reports as active\n\n// ─── Toast ────────────────────────────────────────────────────────────────────\nfunction showToast(msg, type = "success") {\n  const t = document.getElementById("toast");\n  t.textContent = msg;\n  t.className   = `show ${type}`;\n  clearTimeout(t._timer);\n  t._timer = setTimeout(() => { t.className = type; }, 3000);\n}\n\n// ─── Render model list ────────────────────────────────────────────────────────\nfunction renderModels(filter = "") {\n  const list    = document.getElementById("modelList");\n  const lower   = filter.toLowerCase();\n  const visible = MODELS.filter(m =>\n    m.label.toLowerCase().includes(lower) || m.desc.toLowerCase().includes(lower)\n  );\n\n  if (!visible.length) {\n    list.innerHTML = `<div class="px-6 py-6 text-center text-on-surface/30 text-sm">No models match "${filter}"</div>`;\n    return;\n  }\n\n  list.innerHTML = visible.map(m => {\n    const isActive   = m.id === currentModel;\n    const isSelected = m.id === selectedModel;\n    const cls = isSelected ? "selected" : "";\n    return `\n      <button data-model="${m.id}" onclick="selectModel(\'${m.id}\')"\n        class="model-btn w-full px-6 py-4 flex items-center justify-between hover:bg-primary/10 transition-colors text-left group ${cls}">\n        <div class="flex flex-col">\n          <span class="text-sm font-bold ${isSelected ? \'text-primary\' : isActive ? \'text-primary/70\' : \'text-on-surface/80\'}">${m.label}</span>\n          <span class="text-[10px] text-on-surface/40 uppercase tracking-tighter">${m.desc}${isActive ? \' · ✓ Active\' : \'\'}</span>\n        </div>\n        <span class="material-symbols-outlined model-check text-primary text-lg ${isSelected || isActive ? \'!opacity-100\' : \'\'}">\n          ${isSelected ? \'check_circle\' : isActive ? \'radio_button_checked\' : \'radio_button_unchecked\'}\n        </span>\n      </button>`;\n  }).join("");\n}\n\nfunction filterModels(val) { renderModels(val); }\n\nfunction selectModel(id) {\n  selectedModel = id;\n  renderModels(document.getElementById("modelSearch").value);\n}\n\n// ─── Fetch config from backend ────────────────────────────────────────────────\nasync function fetchConfig() {\n  try {\n    const res  = await fetch(`${API_BASE}/api/config`);\n    if (!res.ok) throw new Error(`HTTP ${res.status}`);\n    const data = await res.json();\n    applyConfig(data);\n  } catch (err) {\n    console.error("Config fetch failed:", err);\n    setStatusError();\n  }\n}\n\nfunction applyConfig(data) {\n  currentModel  = data.model  || "";\n  selectedModel = selectedModel || currentModel;\n\n  // Nav badge\n  document.getElementById("statusText").textContent = data.status || "running";\n  document.getElementById("statusDot").classList.add("animate-pulse");\n\n  // Sidebar version\n  document.getElementById("versionNum").textContent = data.version || "—";\n\n  // Stats bar\n  document.getElementById("statStatus").textContent   = (data.status || "running").toUpperCase();\n  document.getElementById("statVersion").textContent  = `v${data.version || "—"}`;\n  document.getElementById("statBotName").textContent  = data.bot_name || "DexMind";\n  document.getElementById("statUsers").textContent    = data.active_users ?? "0";\n\n  // Active model label (short name)\n  const shortName = modelShortName(currentModel);\n  document.getElementById("activeModelLabel").textContent   = shortName;\n  document.getElementById("activeModelFull").textContent    = currentModel || "Unknown";\n  document.getElementById("modelStatusBadge").textContent   = "Active";\n\n  // Progress bar animation (cosmetic — shows how "known" the model is)\n  const knownIdx = MODELS.findIndex(m => m.id === currentModel);\n  const pct = knownIdx >= 0 ? 70 + (knownIdx * 6) : 55;\n  document.getElementById("modelBar").style.width = `${pct}%`;\n\n  renderModels();\n}\n\nfunction setStatusError() {\n  document.getElementById("statusText").textContent = "Offline";\n  document.getElementById("statusDot").classList.remove("animate-pulse");\n  document.getElementById("statusDot").style.background = "#ffb4ab";\n  document.getElementById("statStatus").textContent = "OFFLINE";\n}\n\nfunction modelShortName(id) {\n  const m = MODELS.find(m => m.id === id);\n  return m ? m.label : (id ? id.split("/").pop() : "Unknown");\n}\n\n// ─── Update model on backend ──────────────────────────────────────────────────\nasync function updateModel() {\n  const target = selectedModel || currentModel;\n  if (!target) { showToast("Please select a model first", "error"); return; }\n  if (target === currentModel) { showToast("This model is already active", "error"); return; }\n\n  const btn  = document.getElementById("updateModelBtn");\n  const icon = document.getElementById("updateIcon");\n  btn.disabled  = true;\n  icon.classList.add("spin");\n\n  try {\n    const res  = await fetch(`${API_BASE}/api/update-model`, {\n      method:  "POST",\n      headers: { "Content-Type": "application/json" },\n      body:    JSON.stringify({ model: target }),\n    });\n    const data = await res.json();\n    if (data.success) {\n      currentModel = data.model;\n      document.getElementById("activeModelFull").textContent  = currentModel;\n      document.getElementById("activeModelLabel").textContent = modelShortName(currentModel);\n      document.getElementById("modelStatusBadge").textContent = "Updated";\n      renderModels();\n      showToast(`✓ Model switched to ${modelShortName(currentModel)}`, "success");\n    } else {\n      throw new Error(data.error || "Unknown error");\n    }\n  } catch (err) {\n    showToast(`✗ Update failed: ${err.message}`, "error");\n  } finally {\n    btn.disabled = false;\n    icon.classList.remove("spin");\n  }\n}\n\n// Deploy = same as update (alias for sidebar button)\nasync function deployModel() {\n  const icon = document.getElementById("deployIcon");\n  icon.classList.add("spin");\n  await updateModel();\n  icon.classList.remove("spin");\n}\n\n// Manual refresh\nasync function refreshConfig() {\n  showToast("Refreshing config…", "success");\n  await fetchConfig();\n}\n\n// ─── Toggle token visibility ──────────────────────────────────────────────────\nfunction toggleToken() {\n  const inp  = document.getElementById("apiTokenInput");\n  const icon = document.getElementById("visibilityIcon");\n  if (inp.type === "password") {\n    inp.type      = "text";\n    icon.textContent = "visibility_off";\n  } else {\n    inp.type      = "password";\n    icon.textContent = "visibility";\n  }\n}\n\n// ─── Init ─────────────────────────────────────────────────────────────────────\ndocument.addEventListener("DOMContentLoaded", () => {\n  renderModels();           // show skeleton → real list\n  fetchConfig();            // hit backend\n  setInterval(fetchConfig, 30000);  // auto-refresh every 30s\n});\n</script>\n</body>\n</html>\n'

# ─────────────────────────── CORS ─────────────────────────────────────────────

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Bot-Api-Secret-Token",
}

# ─────────────────────────── TELEGRAM HELPERS ─────────────────────────────────

def tg_send(chat_id: int, text: str, parse_mode: str = "Markdown") -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        logger.error("Telegram send error: %s", e)

def tg_typing(chat_id: int) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"}, timeout=5,
        )
    except Exception:
        pass

# ─────────────────────────── WEATHER ──────────────────────────────────────────

_WEATHER_RE  = re.compile(r"\b(weather|temperature|forecast|rain|sunny|cloudy|hot|cold|humid)\b", re.IGNORECASE)
_LOCATION_RE = re.compile(r"\bin\s+([A-Za-z\s]+?)(?:[?!.,]|$)", re.IGNORECASE)

def get_weather(text: str) -> str:
    if not _WEATHER_RE.search(text):
        return ""
    m = _LOCATION_RE.search(text)
    loc = m.group(1).strip() if m else ""
    try:
        r = requests.get(f"https://wttr.in/{urllib.parse.quote(loc)}?format=3", timeout=6)
        r.raise_for_status()
        return f"[Live weather: {r.text.strip()}]"
    except Exception:
        return ""

# ─────────────────────────── DATETIME ─────────────────────────────────────────

_DATETIME_RE = re.compile(r"\b(time|date|day|today|now|current time|current date|kal|aaj|kitne baje)\b", re.IGNORECASE)

def get_datetime() -> str:
    now = datetime.now(TIMEZONE)
    return f"[Current date & time (IST): {now.strftime('%A, %d %B %Y')} | {now.strftime('%I:%M %p')}]"

# ─────────────────────────── AI CALL ──────────────────────────────────────────

def ai_reply(user_id: int, user_text: str) -> str:
    history = user_histories.setdefault(user_id, [])
    parts = []
    w = get_weather(user_text)
    if w:
        parts.append(w)
    if _DATETIME_RE.search(user_text):
        parts.append(get_datetime())
    parts.append(user_text)
    content = "\n".join(parts).strip()
    history.append({"role": "user", "content": content})
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={"model": get_model(), "messages": messages, "max_tokens": 512, "temperature": 0.7},
            timeout=25,
        )
        r.raise_for_status()
        reply = r.json()["choices"][0]["message"]["content"].strip()
        history.append({"role": "assistant", "content": reply})
        return reply or "⚠️ Empty response. Try again."
    except Exception as e:
        logger.error("OpenRouter error: %s", e)
        history.pop()
        return "⚠️ Couldn't reach AI right now. Please try again."

# ─────────────────────────── COMMAND HANDLERS ─────────────────────────────────

def handle_start(chat_id, first_name):
    now = datetime.now(TIMEZONE).strftime("%I:%M %p, %d %B %Y")
    tg_send(chat_id,
        f"👋 Hey {first_name}! I'm *{BOT_NAME}* — your personal AI assistant.\n"
        f"🕐 Current time (IST): {now}\n\n"
        "Try asking:\n• What's the weather in Mumbai?\n• What time is it?\n• Tell me a fun fact\n\n"
        "Commands: /help  /clear  /model  /datetime  /developer"
    )

def handle_help(chat_id):
    tg_send(chat_id,
        f"🧠 *{BOT_NAME} — Commands*\n\n"
        "/start      – Welcome message\n/help       – Show this help\n"
        "/clear      – Clear your chat history\n/model      – Show current AI model\n"
        "/datetime   – Show current date & time\n/developer  – About the developer\n\n"
        "Just type anything to chat with me!\nInclude a city name for live weather. 🌦"
    )

def handle_clear(chat_id, user_id):
    user_histories.pop(user_id, None)
    tg_send(chat_id, "🗑️ Your conversation history has been cleared!")

def handle_model(chat_id):
    tg_send(chat_id, f"🤖 *Current AI Model:*\n`{get_model()}`")

def handle_datetime(chat_id):
    now = datetime.now(TIMEZONE)
    tg_send(chat_id,
        f"🗓 *Date & Time (IST)*\n\n"
        f"📅 Date : {now.strftime('%A, %d %B %Y')}\n"
        f"🕐 Time : {now.strftime('%I:%M:%S %p')}"
    )

def handle_developer(chat_id):
    tg_send(chat_id,
        f"👨\u200d💻 *Developer Info*\n\n"
        f"🧑 Name       : {DEVELOPER}\n"
        f"📬 Telegram   : {DEV_TELEGRAM}\n"
        f"🤖 Bot        : {BOT_NAME} v`{BOT_VERSION}`"
    )

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
    if text.startswith("/start"):      handle_start(chat_id, first_name)
    elif text.startswith("/help"):     handle_help(chat_id)
    elif text.startswith("/clear"):    handle_clear(chat_id, user_id)
    elif text.startswith("/model"):    handle_model(chat_id)
    elif text.startswith("/datetime"): handle_datetime(chat_id)
    elif text.startswith("/developer"):handle_developer(chat_id)
    else:
        tg_typing(chat_id)
        tg_send(chat_id, ai_reply(user_id, text))

# ─────────────────────────── VERCEL HANDLER ───────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def _path(self):
        return self.path.split("?")[0].rstrip("/")

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        p = self._path()

        if p == "/dashboard":
            # ── Dashboard HTML ───────────────────────────────────────────────
            self._send_html(DASHBOARD_HTML)

        elif p == "/api/config":
            # ── Bot status JSON ──────────────────────────────────────────────
            self._send_json(200, {
                "status":       "running",
                "model":        get_model(),
                "bot_name":     BOT_NAME,
                "version":      BOT_VERSION,
                "developer":    DEVELOPER,
                "active_users": len(user_histories),
            })

        else:
            # ── Alive ping ───────────────────────────────────────────────────
            body = f"{BOT_NAME} v{BOT_VERSION} is alive! 🧠".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def do_POST(self):
        p      = self._path()
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)
        secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")

        # ── Telegram Webhook ─────────────────────────────────────────────────
        if WEBHOOK_SECRET and secret == WEBHOOK_SECRET:
            try:
                process_update(json.loads(body))
            except Exception as e:
                logger.error("Webhook error: %s", e)
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
                self._send_json(200, {"success": True, "model": get_model()})
            except Exception as e:
                self._send_json(400, {"success": False, "error": str(e)})
            return

        self._send_json(404, {"error": "Not found"})
