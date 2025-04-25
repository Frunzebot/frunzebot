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

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@frunze_pro"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

user_state = {}
user_drafts = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state[user_id] = "awaiting_content"
    await update.message.reply_text("Надішліть текст, фото або відео:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_state.get(user_id)
    if state != "awaiting_content":
        return

    content = {"text": None, "photos": [], "videos": []}

    if update.message.text:
        content["text"] = update.message.text

    if update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
        content["photos"].append(photo_file_id)

    if update.message.video:
        video_file_id = update.message.video.file_id
        content["videos"].append(video_file_id)

    if not any([content["text"], content["photos"], content["videos"]]):
        await update.message.reply_text("Будь ласка, надішліть текст, фото або відео.")
        return

    user_drafts[user_id] = content
    user_state[user_id] = "awaiting_action"

    caption = content["text"] if content["text"] else ""
    signature = "адмін" if user_id == 6266425881 else "жолудевий вкид від комʼюніті"
    preview_text = f"{caption}\n\n{signature}"

    keyboard = [
        [
            InlineKeyboardButton("✅ Опублікувати", callback_data="publish"),
            InlineKeyboardButton("✏️ Редагувати", callback_data="edit"),
            InlineKeyboardButton("❌ Відхилити", callback_data="reject"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if content["photos"]:
        if len(content["photos"]) == 1:
            await update.message.reply_photo(
                photo=content["photos"][0],
                caption=preview_text,
                reply_markup=reply_markup,
            )
        else:
            media_group = [
                InputMediaPhoto(media=pid) for pid in content["photos"]
            ]
            media_group[0].caption = preview_text
            await update.message.reply_media_group(media=media_group)
            await update.message.reply_text(
                preview_text, reply_markup=reply_markup
            )
    elif content["videos"]:
        await update.message.reply_video(
            video=content["videos"][0],
            caption=preview_text,
            reply_markup=reply_markup,
        )
    else:
        await update.message.reply_text(preview_text, reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_drafts:
        await query.edit_message_text("❌ Немає чернетки для публікації.")
        return

    if data == "publish":
        draft = user_drafts[user_id]
        caption = draft["text"] if draft["text"] else ""
        signature = "адмін" if user_id == 6266425881 else "жолудевий вкид від комʼюніті"
        final_text = f"{caption}\n\n{signature}"

        try:
            if draft["photos"]:
                if len(draft["photos"]) == 1:
                    await context.bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=draft["photos"][0],
                        caption=final_text,
                    )
                else:
                    media_group = [
                        InputMediaPhoto(media=pid) for pid in draft["photos"]
                    ]
                    media_group[0].caption = final_text
                    await context.bot.send_media_group(chat_id=CHANNEL_ID, media=media_group)
                    await context.bot.send_message(chat_id=CHANNEL_ID, text=final_text)
            elif draft["videos"]:
                await context.bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=draft["videos"][0],
                    caption=final_text,
                )
            else:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=final_text)

            await query.edit_message_text("✅ Допис опубліковано.")
            await context.bot.send_message(chat_id=user_id, text="✅ Ваш допис опубліковано.")
        except Exception as e:
            logging.error(str(e))
            await query.edit_message_text("❌ Помилка при публікації.")

        user_drafts.pop(user_id, None)
        user_state[user_id] = "awaiting_content"

    elif data == "edit":
        await query.edit_message_text("✏️ Надішліть нову версію допису.")
        user_state[user_id] = "awaiting_content"
    elif data == "reject":
        await query.edit_message_text("❌ Допис відхилено.")
        await context.bot.send_message(chat_id=user_id, text="❌ Ваш допис не пройшов модерацію.")
        user_drafts.pop(user_id, None)
        user_state[user_id] = "awaiting_content"

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()

if __name__ == "__main__":
    main()