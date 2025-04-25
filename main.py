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
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import os

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6266425881
CHANNEL_ID = "@frunze_pro"

logging.basicConfig(level=logging.INFO)

user_drafts = {}
user_states = {}

# Гілка 1
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = "main_post"
    await update.message.reply_text("Надішліть текст, фото або відео:")

async def handle_main_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_states.get(user_id) != "main_post":
        return

    content = {
        "text": update.message.text or "",
        "photos": [],
        "videos": [],
    }

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        content["photos"].append(file_id)
    if update.message.video:
        file_id = update.message.video.file_id
        content["videos"].append(file_id)

    if not content["text"] and not content["photos"] and not content["videos"]:
        await update.message.reply_text("Надішліть хоча б текст, фото або відео.")
        return

    user_drafts[user_id] = content

    keyboard = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data="action_publish")],
        [InlineKeyboardButton("✏️ Редагувати", callback_data="action_edit")],
        [InlineKeyboardButton("❌ Відхилити", callback_data="action_cancel")],
    ]

    caption = content["text"] or ""
    if user_id == ADMIN_ID:
        caption = "адмін\n\n" + caption
    else:
        caption = "жолудевий вкид від комʼюніті\n\n" + caption

    if content["photos"]:
        if len(content["photos"]) == 1:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=content["photos"][0],
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            media_group = [
                InputMediaPhoto(photo_id) for photo_id in content["photos"]
            ]
            media_group[0].caption = caption
            await context.bot.send_media_group(chat_id=ADMIN_ID, media=media_group)
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="Оберіть дію:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

    elif content["videos"]:
        await context.bot.send_video(
            chat_id=ADMIN_ID,
            video=content["videos"][0],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    await update.message.reply_text("Ваш допис передано на модерацію.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id != ADMIN_ID:
        await query.edit_message_text("Недостатньо прав.")
        return

    if user_id not in user_drafts:
        await query.edit_message_text("Немає чернетки для публікації.")
        return

    data = query.data
    content = user_drafts[user_id]

    text = content["text"] or ""
    author = "адмін"

    caption = f"{author}\n\n{text}" if text else author

    if data == "action_publish":
        try:
            if content["photos"]:
                if len(content["photos"]) == 1:
                    await context.bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=content["photos"][0],
                        caption=caption,
                    )
                else:
                    media_group = [
                        InputMediaPhoto(photo_id) for photo_id in content["photos"]
                    ]
                    media_group[0].caption = caption
                    await context.bot.send_media_group(
                        chat_id=CHANNEL_ID, media=media_group
                    )
            elif content["videos"]:
                await context.bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=content["videos"][0],
                    caption=caption,
                )
            else:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)

            await query.edit_message_text("✅ Допис опубліковано.")
            await context.bot.send_message(
                chat_id=user_id, text="✅ Ваш допис опубліковано."
            )
        except Exception as e:
            logging.error(f"Помилка при публікації: {e}")
            await context.bot.send_message(chat_id=user_id, text="❌ Помилка при публікації.")

        user_drafts.pop(user_id, None)

    elif data == "action_cancel":
        user_drafts.pop(user_id, None)
        await query.edit_message_text("❌ Допис відхилено.")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Ваш допис не пройшов модерацію.",
        )

    elif data == "action_edit":
        user_states[user_id] = "main_post"
        await context.bot.send_message(
            chat_id=user_id, text="Надішліть нову версію допису."
        )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL, handle_main_post))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()