import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_state = {}
user_drafts = {}
media_buffer = {}

def escape(text):
    return text.replace("-", "\\-").replace(".", "\\.")\
               .replace("(", "\\(").replace(")", "\\)")\
               .replace("!", "\\!").replace("=", "\\=")\
               .replace("+", "\\+").replace("&", "\\&")\
               .replace("~", "\\~").replace("|", "\\|")\
               .replace("#", "\\#").replace(">", "\\>")\
               .replace("<", "\\<").replace("[", "\\[")\
               .replace("]", "\\]").replace("{", "\\{")\
               .replace("}", "\\}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("1. Основний постинг", callback_data="branch_text")]
    ]
    await update.message.reply_text("Оберіть тип допису:", reply_markup=InlineKeyboardMarkup(keyboard))

async def select_branch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_state[query.from_user.id] = query.data
    await query.edit_message_text("Надішліть текст, фото або відео:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    branch = user_state.get(uid)

    if branch != "branch_text":
        return

    if update.message.media_group_id:
        if uid not in media_buffer:
            media_buffer[uid] = []
        if update.message.photo:
            media_buffer[uid].append(("photo", update.message.photo[-1].file_id))
        elif update.message.video:
            media_buffer[uid].append(("video", update.message.video.file_id))
        return

    text = update.message.text or ""
    photo = update.message.photo[-1].file_id if update.message.photo else None
    video = update.message.video.file_id if update.message.video else None
    is_admin = str(uid) == os.getenv("ADMIN_ID")
    header = "адмін" if is_admin else "жолудевий вкид від комʼюніті"
    final_text = f"*{header}*\n\n{escape(text)}"

    user_drafts[uid] = {
        "text": final_text,
        "photo": photo,
        "video": video,
        "media": media_buffer.pop(uid, None)
    }

    buttons = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data="publish_text"),
         InlineKeyboardButton("✏️ Редагувати", callback_data="edit_text"),
         InlineKeyboardButton("❌ Відхилити", callback_data="reject_text")]
    ]

    if user_drafts[uid]["media"]:
        media_group = []
        for media_type, file_id in user_drafts[uid]["media"]:
            if media_type == "photo":
                media_group.append(InputMediaPhoto(media=file_id))
            elif media_type == "video":
                media_group.append(InputMediaVideo(media=file_id))
        await context.bot.send_media_group(chat_id=uid, media=media_group)
        await context.bot.send_message(chat_id=uid, text=final_text,
                                       reply_markup=InlineKeyboardMarkup(buttons),
                                       parse_mode="MarkdownV2")
    elif photo:
        await context.bot.send_photo(chat_id=uid, photo=photo, caption=final_text,
                                     reply_markup=InlineKeyboardMarkup(buttons),
                                     parse_mode="MarkdownV2")
    elif video:
        await context.bot.send_video(chat_id=uid, video=video, caption=final_text,
                                     reply_markup=InlineKeyboardMarkup(buttons),
                                     parse_mode="MarkdownV2")
    else:
        await context.bot.send_message(chat_id=uid, text=final_text,
                                       reply_markup=InlineKeyboardMarkup(buttons),
                                       parse_mode="MarkdownV2")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    draft = user_drafts.get(uid)

    if not draft:
        await query.edit_message_text("Немає чернетки для публікації.")
        return

    if query.data == "publish_text":
        try:
            if draft.get("media"):
                media_group = []
                for media_type, file_id in draft["media"]:
                    if media_type == "photo":
                        media_group.append(InputMediaPhoto(media=file_id))
                    elif media_type == "video":
                        media_group.append(InputMediaVideo(media=file_id))
                await context.bot.send_media_group(chat_id=os.getenv("CHANNEL_ID"), media=media_group)
                await context.bot.send_message(chat_id=os.getenv("CHANNEL_ID"), text=draft["text"], parse_mode="MarkdownV2")
            elif draft.get("photo"):
                await context.bot.send_photo(chat_id=os.getenv("CHANNEL_ID"), photo=draft["photo"],
                                             caption=draft["text"], parse_mode="MarkdownV2")
            elif draft.get("video"):
                await context.bot.send_video(chat_id=os.getenv("CHANNEL_ID"), video=draft["video"],
                                             caption=draft["text"], parse_mode="MarkdownV2")
            else:
                await context.bot.send_message(chat_id=os.getenv("CHANNEL_ID"), text=draft["text"], parse_mode="MarkdownV2")

            await context.bot.send_message(chat_id=uid, text="✅ Ваш допис опубліковано.")
            await query.edit_message_text("Опубліковано.")
            user_drafts.pop(uid)

        except Exception as e:
            logger.error(f"Publish error: {e}")
            await query.edit_message_text("Помилка при публікації.")

    elif query.data == "edit_text":
        await query.edit_message_text("✏️ Надішліть нову версію допису.")
        user_state[uid] = "branch_text"
        user_drafts.pop(uid)

    elif query.data == "reject_text":
        await context.bot.send_message(chat_id=uid, text="❌ Ваш матеріал не пройшов модерацію.")
        await query.edit_message_text("Відхилено.")
        user_drafts.pop(uid)

def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(select_branch, pattern="^branch_text$"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^(publish_text|edit_text|reject_text)$"))
    app.run_polling()

if __name__ == "__main__":
    main()