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

# Гілка 1 — Основний текст/фото/відео-допис
async def handle_main_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    content = {"text": update.message.text, "photo": update.message.photo, "video": update.message.video}
    user_sessions[user_id]["content"] = content
    keyboard = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data="publish_main")],
        [InlineKeyboardButton("✏️ Редагувати", callback_data="edit_main")],
        [InlineKeyboardButton("❌ Відхилити", callback_data="reject_main")]
    ]
    preview_text = "Попередній перегляд

адмін"
    await update.message.reply_text(preview_text, reply_markup=InlineKeyboardMarkup(keyboard))
    moderation_messages[user_id] = update.message.message_id

# Обробка публікації гілки 1
async def handle_main_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    content = user_sessions.get(user_id, {}).get("content", {})
    decision = query.data

    if decision == "publish_main":
        text = content.get("text", "")
        if content.get("photo"):
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=content["photo"][-1].file_id, caption=f"адмін

{text}")
        elif content.get("video"):
            await context.bot.send_video(chat_id=CHANNEL_ID, video=content["video"].file_id, caption=f"адмін

{text}")
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=f"адмін

{text}")
        await query.message.reply_text("✅ Опубліковано.")
        user_sessions.pop(user_id, None)

    elif decision == "reject_main":
        await query.message.reply_text("❌ Матеріал відхилено.")
        user_sessions.pop(user_id, None)

    elif decision == "edit_main":
        await query.message.reply_text("✏️ Надішліть нову версію. У вас є 20 хвилин.")
        edit_windows[user_id] = datetime.now() + timedelta(minutes=20)

# Гілка 2 — Новини з посиланням
async def handle_link_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    link = update.message.text.strip()

    if not link.startswith("http"):
        await update.message.reply_text("Надішліть коректне посилання, яке починається з http або https.")
        return

    preview_text = f"Попередній перегляд новини

адмін

[{link}]({link})"
    keyboard = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data="publish_link")],
        [InlineKeyboardButton("❌ Відхилити", callback_data="reject_link")]
    ]
    await update.message.reply_text(preview_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    user_sessions[user_id]["link"] = link

# Обробка рішення по новині
async def handle_link_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    decision = query.data
    link = user_sessions.get(user_id, {}).get("link")

    if decision == "publish_link":
        msg = f"адмін

[Читати новину]({link})"
        await context.bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="Markdown", disable_web_page_preview=False)
        await query.message.reply_text("✅ Посилання опубліковано.")
        user_sessions.pop(user_id, None)

    elif decision == "reject_link":
        await query.message.reply_text("❌ Посилання відхилено.")
        user_sessions.pop(user_id, None)

# Запуск бота
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_branch_selection, pattern="^(main_post|link_post)$"))
    app.add_handler(CallbackQueryHandler(handle_main_decision, pattern="^(publish_main|edit_main|reject_main)$"))
    app.add_handler(CallbackQueryHandler(handle_link_decision, pattern="^(publish_link|reject_link)$"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
