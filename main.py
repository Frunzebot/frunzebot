import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

user_states = {}

# Старт / Меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Основний текст/фото/відео-допис", callback_data="main_post")],
        [InlineKeyboardButton("Новини з посиланням (http)", callback_data="news_link")],
        [InlineKeyboardButton("Анонімний внесок / інсайд", callback_data="anonymous_post")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть тип допису:", reply_markup=reply_markup)

# Вибір гілки
async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_states[user_id] = {"branch": query.data, "content": None}
    await query.edit_message_text("Надішліть текст / фото / відео або посилання.")

# Отримання контенту
async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_states:
        await update.message.reply_text("Натисніть /start і виберіть тип допису.")
        return

    branch = user_states[user_id]["branch"]
    content_type = None
    content = None

    if update.message.text:
        content_type = "text"
        content = update.message.text
    elif update.message.photo:
        content_type = "photo"
        content = update.message.photo[-1].file_id
    elif update.message.video:
        content_type = "video"
        content = update.message.video.file_id
    else:
        await update.message.reply_text("Формат не підтримується.")
        return

    user_states[user_id]["content"] = {"type": content_type, "data": content}

    # Кнопки модерації
    keyboard = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data="publish")],
        [InlineKeyboardButton("✏️ Редагувати", callback_data="edit")],
        [InlineKeyboardButton("❌ Відхилити", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if content_type == "text":
        await update.message.reply_text(f"Чернетка допису:\n\n{content}", reply_markup=reply_markup)
    elif content_type == "photo":
        await update.message.reply_photo(photo=content, caption="Чернетка допису (фото):", reply_markup=reply_markup)
    elif content_type == "video":
        await update.message.reply_video(video=content, caption="Чернетка допису (відео):", reply_markup=reply_markup)

# Кнопки: опублікувати / редагувати / відхилити
async def moderation_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_states or not user_states[user_id].get("content"):
        await query.edit_message_text("Чернетка відсутня.")
        return

    content = user_states[user_id]["content"]
    action = query.data

    if action == "cancel":
        user_states.pop(user_id)
        await query.edit_message_text("Скасовано.")
        return

    if action == "edit":
        await query.edit_message_text("Надішліть новий текст / фото / відео.")
        return

    if action == "publish":
        try:
            if content["type"] == "text":
                await context.bot.send_message(chat_id=CHANNEL_ID, text=content["data"])
            elif content["type"] == "photo":
                await context.bot.send_photo(chat_id=CHANNEL_ID, photo=content["data"])
            elif content["type"] == "video":
                await context.bot.send_video(chat_id=CHANNEL_ID, video=content["data"])

            await query.edit_message_text("✅ Допис опубліковано!")
        except Exception as e:
            await query.edit_message_text(f"Помилка публікації: {str(e)}")

        user_states.pop(user_id)

# Запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_selection, pattern="^(main_post|news_link|anonymous_post)$"))
    app.add_handler(CallbackQueryHandler(moderation_action, pattern="^(publish|edit|cancel)$"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_content))

    app.run_polling()