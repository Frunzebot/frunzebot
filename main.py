import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Дані
CHANNEL_ID = "@frunze_pro"
ADMIN_ID = 6266425881

# Стан користувача
user_state = {}
user_drafts = {}

# Кнопки модерації
def moderation_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Опублікувати", callback_data="action_publish")],
        [InlineKeyboardButton("✏️ Редагувати", callback_data="action_edit")],
        [InlineKeyboardButton("❌ Відхилити", callback_data="action_reject")]
    ])

# Старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state[update.effective_user.id] = "awaiting_content"
    await update.message.reply_text("Надішліть текст, фото або відео:")

# Обробка контенту
async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_state.get(user_id)

    if state != "awaiting_content":
        return

    content = {"text": "", "media": []}

    if update.message.text:
        content["text"] = update.message.text

    if update.message.photo:
        photo = update.message.photo[-1].file_id
        content["media"].append(("photo", photo))

    if update.message.video:
        video = update.message.video.file_id
        content["media"].append(("video", video))

    if not content["text"] and not content["media"]:
        return

    user_drafts[user_id] = content
    user_state[user_id] = "pending_moderation"

    caption = "адмін" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті"

    await update.message.reply_text("Ваш допис передано на модерацію.")

    if content["media"]:
        media_group = []
        for i, (m_type, file_id) in enumerate(content["media"]):
            caption_to_use = content["text"] if i == 0 else None
            if m_type == "photo":
                media_group.append(InputMediaPhoto(media=file_id, caption=caption_to_use))
            elif m_type == "video":
                media_group.append(InputMediaVideo(media=file_id, caption=caption_to_use))
        message = await context.bot.send_media_group(chat_id=ADMIN_ID, media=media_group)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=caption,
            reply_markup=moderation_keyboard(),
            reply_to_message_id=message[0].message_id
        )
    else:
        sent = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"{caption}

{content['text']}",
            reply_markup=moderation_keyboard()
        )

# Кнопки модерації
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    draft = user_drafts.get(ADMIN_ID)

    if not draft:
        await query.answer()
        await query.edit_message_text("❌ Немає чернетки для публікації.")
        return

    if data == "action_publish":
        caption = "адмін"
        if draft["media"]:
            media_group = []
            for i, (m_type, file_id) in enumerate(draft["media"]):
                caption_to_use = draft["text"] if i == 0 else None
                if m_type == "photo":
                    media_group.append(InputMediaPhoto(media=file_id, caption=caption_to_use))
                elif m_type == "video":
                    media_group.append(InputMediaVideo(media=file_id, caption=caption_to_use))
            await context.bot.send_media_group(chat_id=CHANNEL_ID, media=media_group)
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=f"{caption}

{draft['text']}")
        await query.edit_message_text("✅ Допис опубліковано.")
        await context.bot.send_message(chat_id=ADMIN_ID, text="✅ Ваш допис опубліковано.")
        user_drafts.pop(ADMIN_ID, None)

    elif data == "action_reject":
        await query.edit_message_text("❌ Допис відхилено.")
        await context.bot.send_message(chat_id=ADMIN_ID, text="❌ Ваш допис не пройшов модерацію.")
        user_drafts.pop(ADMIN_ID, None)

    elif data == "action_edit":
        user_state[ADMIN_ID] = "awaiting_edit"
        await context.bot.send_message(chat_id=ADMIN_ID, text="Надішліть нову версію допису.")
        await query.answer()

# Обробка редагування
async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_state.get(user_id)

    if state != "awaiting_edit":
        return

    content = {"text": "", "media": []}

    if update.message.text:
        content["text"] = update.message.text

    if update.message.photo:
        photo = update.message.photo[-1].file_id
        content["media"].append(("photo", photo))

    if update.message.video:
        video = update.message.video.file_id
        content["media"].append(("video", video))

    if not content["text"] and not content["media"]:
        return

    user_drafts[user_id] = content
    user_state[user_id] = "pending_moderation"

    caption = "адмін"

    await update.message.reply_text("Ваш оновлений допис передано на модерацію.")

    if content["media"]:
        media_group = []
        for i, (m_type, file_id) in enumerate(content["media"]):
            caption_to_use = content["text"] if i == 0 else None
            if m_type == "photo":
                media_group.append(InputMediaPhoto(media=file_id, caption=caption_to_use))
            elif m_type == "video":
                media_group.append(InputMediaVideo(media=file_id, caption=caption_to_use))
        message = await context.bot.send_media_group(chat_id=ADMIN_ID, media=media_group)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=caption,
            reply_markup=moderation_keyboard(),
            reply_to_message_id=message[0].message_id
        )
    else:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"{caption}

{content['text']}",
            reply_markup=moderation_keyboard()
        )

# Основна функція
def main():
    import os
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_edit, block=False))
    app.add_handler(MessageHandler(filters.ALL, handle_content))

    app.run_polling()

if __name__ == "__main__":
    main()