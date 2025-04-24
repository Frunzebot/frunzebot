import os
from zipfile import ZipFile

# Створимо структуру main.py (окремим файлом)
code = """
# main.py — Telegram-бот Frunzebot (усі 3 гілки інтегровані)
# Версія: 2025.04.25
# Автор: GPT для Frunze

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, CallbackQueryHandler, ContextTypes
)

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Приклад: '@frunze_pro'

# Логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Стан
user_state = {}
user_drafts = {}

# Гілка вибору
BRANCH = {
    "TEXT": "branch_text",
    "LINK": "branch_link",
    "ANON": "branch_anon"
}

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("1. Основний постинг", callback_data="text")],
        [InlineKeyboardButton("2. Новини з посиланням", callback_data="link")],
        [InlineKeyboardButton("3. Анонімний внесок", callback_data="anon")]
    ]
    await update.message.reply_text("Оберіть тип допису:", reply_markup=InlineKeyboardMarkup(keyboard))

# Вибір гілки
async def branch_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_state[query.from_user.id] = query.data
    await query.edit_message_text("Надішліть свій допис:")

# Обробка повідомлення
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    branch = user_state.get(uid)

    if not branch:
        await update.message.reply_text("Будь ласка, спочатку оберіть тип допису через /start.")
        return

    text = update.message.text or ""
    photo = update.message.photo[-1].file_id if update.message.photo else None
    video = update.message.video.file_id if update.message.video else None
    is_admin = str(uid) == os.getenv("ADMIN_ID")

    if branch == "text":
        header = "адмін" if is_admin else "жолудевий вкид від комʼюніті"
    elif branch == "link":
        if not ("http://" in text or "https://" in text):
            await update.message.reply_text("Це не схоже на посилання. Надішліть валідний лінк.")
            return
        header = "адмін" if is_admin else "жолудевий вкид від комʼюніті"
    elif branch == "anon":
        header = "жолудевий вкид анонімно"
        await update.message.reply_text("✅ Дякуємо за інсайд. Ваш матеріал передано адміну.")

    # Формуємо текст
    message_text = f"*{header}*\n\n{text}" if branch != "anon" else f"*{header}*\n\n{text}"

    buttons = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data="publish"),
         InlineKeyboardButton("✏️ Редагувати", callback_data="edit"),
         InlineKeyboardButton("❌ Відхилити", callback_data="reject")]
    ]

    user_drafts[uid] = {"text": message_text, "photo": photo, "video": video, "branch": branch}

    if photo:
        await context.bot.send_photo(chat_id=uid, photo=photo, caption=message_text,
                                     reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    elif video:
        await context.bot.send_video(chat_id=uid, video=video, caption=message_text,
                                     reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=uid, text=message_text,
                                       reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

# Кнопки модерації
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    draft = user_drafts.get(uid)

    if not draft:
        await query.edit_message_text("Немає чернетки для публікації.")
        return

    if data == "publish":
        if draft["photo"]:
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=draft["photo"],
                                         caption=draft["text"], parse_mode="Markdown")
        elif draft["video"]:
            await context.bot.send_video(chat_id=CHANNEL_ID, video=draft["video"],
                                         caption=draft["text"], parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=draft["text"], parse_mode="Markdown")

        if draft["branch"] == "anon":
            await context.bot.send_message(chat_id=uid, text="✅ Дякуємо за інсайд. Ваш допис опубліковано.")
        await query.edit_message_text("Опубліковано.")
        user_drafts.pop(uid)

    elif data == "edit":
        await query.edit_message_text("Надішліть нову версію допису.")
        user_state[uid] = draft["branch"]

    elif data == "reject":
        if draft["branch"] == "anon":
            await context.bot.send_message(chat_id=uid, text="❌ Дякуємо за матеріал, але ваш матеріал не пройшов модерацію.")
        await query.edit_message_text("Відхилено.")
        user_drafts.pop(uid)

# Головна
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(branch_select, pattern="^(text|link|anon)$"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^(publish|edit|reject)$"))

    app.run_polling()

if __name__ == "__main__":
    main()
"""

# Зберегти у файл
file_path = "/mnt/data/main.py"
with open(file_path, "w") as f:
    f.write(code)

file_path