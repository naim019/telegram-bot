import time
import random
import os
from typing import Dict, Any
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from flask import Flask, request

# Bot token from Render environment
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Mining Config
INITIAL_RATE_PER_SECOND = 0.00000010
UPGRADE_COST_MULTIPLIER = 1.5
BASE_UPGRADE_COST = 0.0001
CLICKER_GAME_REWARD_FACTOR = 0.5

# Fake In-Memory Database (reset when server restarts)
USER_DATABASE: Dict[int, Dict[str, Any]] = {}

def get_default_user(user_id: int):
    return {
        "user_id": user_id,
        "balance": 0.0,
        "rate_per_second": INITIAL_RATE_PER_SECOND,
        "upgrade_level": 1,
        "last_active": time.time()
    }

def get_user(user_id: int):
    if user_id not in USER_DATABASE:
        USER_DATABASE[user_id] = get_default_user(user_id)
    return USER_DATABASE[user_id]

def save_user(user_id: int, data):
    USER_DATABASE[user_id] = data

def upgrade_cost(level: int):
    return BASE_UPGRADE_COST * (UPGRADE_COST_MULTIPLIER ** (level - 1))

def format_btc(amount: float):
    return f"{amount:.8f}"

def apply_idle_mining(user):
    now = time.time()
    delta = now - user["last_active"]
    MAX_IDLE = 604800  # 7 days max
    effective = min(delta, MAX_IDLE)
    
    earned = effective * user["rate_per_second"]
    user["balance"] += earned
    user["last_active"] = now
    return earned


# Telegram Commands =====================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    earned = apply_idle_mining(user)
    save_user(user["user_id"], user)

    msg = (
        f"🌟 **Welcome Miner!**\n"
        f"💰 Balance: **{format_btc(user['balance'])} BTC**\n"
        f"⛏️ Level: **{user['upgrade_level']}**\n"
        f"⚡ Rate: **{format_btc(user['rate_per_second'])} BTC/sec**\n"
        f"🛠️ Upgrade cost: **{format_btc(upgrade_cost(user['upgrade_level']))} BTC**\n\n"
        f"🎮 Mine Game: /mine_game\n"
        f"📈 Upgrade: /upgrade"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    apply_idle_mining(user)

    cost = upgrade_cost(user["upgrade_level"])

    if user["balance"] >= cost:
        user["balance"] -= cost
        user["upgrade_level"] += 1
        user["rate_per_second"] *= 2
        save_user(user["user_id"], user)

        msg = (
            f"✅ **Upgrade Successful!**\n"
            f"New Level: **{user['upgrade_level']}**\n"
            f"New Rate: **{format_btc(user['rate_per_second'])} BTC/sec**"
        )
    else:
        msg = (
            f"❌ Not enough BTC!\n"
            f"Required: **{format_btc(cost)}** BTC"
        )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def mine_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    apply_idle_mining(user)

    base = user["rate_per_second"] * 86400 * CLICKER_GAME_REWARD_FACTOR
    reward = base * (1 + random.uniform(-0.1, 0.1))

    user["balance"] += reward
    save_user(user["user_id"], user)

    await update.message.reply_text(
        f"🏆 Bonus Reward: **+{format_btc(reward)} BTC**",
        parse_mode="Markdown"
    )


# Flask + Webhook =======================================

app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("upgrade", upgrade))
application.add_handler(CommandHandler("mine_game", mine_game))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))


@app.post("/")
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok"
