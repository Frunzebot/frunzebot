from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import os
import logging
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Змінні для сесій
user_sessions = {}
moderation_messages = {}
edit_windows = {}

logging.basicConfig(level=logging.INFO)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("1. Основний допис", callback_data="main_post")],
        [InlineKeyboardButton("2. Новина з посиланням", callback_data="link_post")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть тип допису:", reply_markup=reply_markup)

# Обробка вибору гілки
async def handle_branch_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    branch = query.data
    user_sessions[query.from_user.id] = {"branch": branch}
    await query.message.reply_text("Надішліть свій матеріал (текст, фото, відео або посилання).")

# Головна обробка повідомлень
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)

    if not session or "branch" not in session:
        await update.message.reply_text("Спочатку оберіть тип допису через /start.")
        return

    branch = session["branch"]
    if branch == "main_post":
        await handle_main_post(update, context)
    elif branch == "link_post":
        await handle_link_post(update, context)