import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    CommandHandler,
)
import os

# Логування
logging.basicConfig(level=logging.INFO)

# Дані для Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@frunze_pro")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6266425881"))

# Стан та чернетки
user_state = {}
user_drafts = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state[user_id] = "awaiting_post"
    await update.message.reply_text("Надішліть текст, фото або відео:")

async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.effective_message

    # Стан має бути "awaiting_post"
    if user_state.get(user_id) != "awaiting_post":
        return

    # Підготовка контенту
    content = {
        "text": message.text or message.caption or "",
        "photos": [],
        "video": None,
    }

    if message.photo:
        content["photos"] = [p.file_id for p in message.photo]
    elif message.video:
        content["video"] = message.video.file_id

    user_drafts[user_id] = content
    user_state[user_id] = "awaiting_action"

    # Підпис
    sender = "адмін" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті"

    # Підготовка попереднього перегляду
    text = content["text"]
    buttons = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data="action_publish")],
        [InlineKeyboardButton("✏️ Редагувати", callback_data="action_edit")],
        [InlineKeyboardButton("❌ Відхилити", callback_data="action_cancel")],
    ]

    if content["photos"]:
        media = [InputMediaPhoto(photo_id) for photo_id in content["photos"]]
        media[0].caption = f"{text}\n\n{sender}"
        await context.bot.send_media_group(chat_id=user_id, media=media)
        await context.bot.send_message(chat_id=user_id, text=sender, reply_markup=InlineKeyboardMarkup(buttons))
    elif content["video"]:
        await context.bot.send_video(chat_id=user_id, video=content["video"], caption=f"{text}\n\n{sender}", reply_markup=InlineKeyboardMarkup(buttons))
    elif text:
        await context.bot.send_message(chat_id=user_id, text=f"{text}\n\n{sender}", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action = query.data

    draft = user_drafts.get(user_id)

    if not draft:
        await query.edit_message_text("❌ Немає чернетки для публікації.")
        return

    if action == "action_publish":
        # Публікація
        text = draft["text"]
        sender = "адмін" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті"

        if draft["photos"]:
            media = [InputMediaPhoto(photo_id) for photo_id in draft["photos"]]
            media[0].caption = f"{text}\n\n{sender}"
            await context.bot.send_media_group(chat_id=CHANNEL_ID, media=media)
        elif draft["video"]:
            await context.bot.send_video(chat_id=CHANNEL_ID, video=draft["video"], caption=f"{text}\n\n{sender}")
        elif text:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=f"{text}\n\n{sender}")

        del user_drafts[user_id]
        user_state[user_id] = "awaiting_post"
        await context.bot.send_message(chat_id=user_id, text="✅ Ваш допис опубліковано.")

    elif action == "action_cancel":
        del user_drafts[user_id]
        user_state[user_id] = "awaiting_post"
        await context.bot.send_message(chat_id=user_id, text="❌ Ваш допис не пройшов модерацію.")

    elif action == "action_edit":
        user_state[user_id] = "awaiting_post"
        await context.bot.send_message(chat_id=user_id, text="✏️ Надішліть нову версію допису.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_content))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()

if __name__ == "__main__":
    main()