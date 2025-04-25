import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_state = {}
user_drafts = {}

def escape(text):
    return text.replace("-", "\\-") \
               .replace(".", "\\.") \
               .replace("(", "\\(").replace(")", "\\)") \
               .replace("!", "\\!") \
               .replace("=", "\\=").replace("+", "\\+") \
               .replace("&", "\\&").replace("~", "\\~") \
               .replace("|", "\\|").replace("#", "\\#") \
               .replace(">", "\\>").replace("<", "\\<")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("1. Основний постинг", callback_data="branch_text")],
        [InlineKeyboardButton("2. Новини з посиланням", callback_data="branch_link")],
        [InlineKeyboardButton("3. Анонімний внесок", callback_data="branch_anon")]
    ]
    await update.message.reply_text("Оберіть тип допису:", reply_markup=InlineKeyboardMarkup(keyboard))

async def select_branch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_state[query.from_user.id] = query.data
    await query.edit_message_text("Надішліть свій допис:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    branch = user_state.get(uid)

    if not branch:
        await update.message.reply_text("Оберіть тип допису через /start.")
        return

    text = update.message.text or ""
    photo = update.message.photo[-1].file_id if update.message.photo else None
    video = update.message.video.file_id if update.message.video else None
    is_admin = str(uid) == os.getenv("ADMIN_ID")

    if branch == "branch_text":
        header = "адмін" if is_admin else "жолудевий вкид від комʼюніті"
    elif branch == "branch_link":
        if not ("http://" in text or "https://" in text):
            await update.message.reply_text("Це не лінк. Надішліть валідне посилання.")
            return
        header = "адмін" if is_admin else "жолудевий вкид від комʼюніті"
    elif branch == "branch_anon":
        header = "жолудевий вкид анонімно"
        await update.message.reply_text("✅ Дякуємо за інсайд. Ваш матеріал передано адміну.")

    safe_text = escape(text)
    message_text = f"*{header}*\n\n{safe_text}"

    user_drafts[uid] = {
        "text": message_text,
        "photo": photo,
        "video": video,
        "branch": branch
    }

    buttons = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data="action_publish"),
         InlineKeyboardButton("✏️ Редагувати", callback_data="action_edit"),
         InlineKeyboardButton("❌ Відхилити", callback_data="action_reject")]
    ]

    if photo:
        await context.bot.send_photo(chat_id=uid, photo=photo, caption=message_text,
                                     reply_markup=InlineKeyboardMarkup(buttons), parse_mode="MarkdownV2")
    elif video:
        await context.bot.send_video(chat_id=uid, video=video, caption=message_text,
                                     reply_markup=InlineKeyboardMarkup(buttons), parse_mode="MarkdownV2")
    else:
        await context.bot.send_message(chat_id=uid, text=message_text,
                                       reply_markup=InlineKeyboardMarkup(buttons), parse_mode="MarkdownV2")

async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    action = query.data
    draft = user_drafts.get(uid)

    if not draft:
        await query.edit_message_text("Немає чернетки для публікації.")
        return

    try:
        if action == "action_publish":
            if draft["photo"]:
                await context.bot.send_photo(chat_id=os.getenv("CHANNEL_ID"), photo=draft["photo"],
                                             caption=draft["text"], parse_mode="MarkdownV2")
            elif draft["video"]:
                await context.bot.send_video(chat_id=os.getenv("CHANNEL_ID"), video=draft["video"],
                                             caption=draft["text"], parse_mode="MarkdownV2")
            else:
                await context.bot.send_message(chat_id=os.getenv("CHANNEL_ID"),
                                               text=draft["text"], parse_mode="MarkdownV2")

            if draft["branch"] == "branch_anon":
                await context.bot.send_message(chat_id=uid, text="✅ Дякуємо за інсайд. Ваш допис опубліковано.")

            await query.edit_message_text("Опубліковано.")
            user_drafts.pop(uid)

        elif action == "action_edit":
            await query.edit_message_text("Надішліть нову версію допису.")
            user_state[uid] = draft["branch"]
            user_drafts.pop(uid)

        elif action == "action_reject":
            if draft["branch"] == "branch_anon":
                await context.bot.send_message(chat_id=uid, text="❌ Дякуємо за матеріал, але ваш матеріал не пройшов модерацію.")
            await query.edit_message_text("Відхилено.")
            user_drafts.pop(uid)

    except Exception as e:
        logger.error(f"Callback action error: {e}")
        await query.edit_message_text("Сталася помилка. Спробуйте ще раз.")

def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(select_branch, pattern="^branch_"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_message))
    app.add_handler(CallbackQueryHandler(handle_action, pattern="^action_"))
    app.run_polling()

if __name__ == "__main__":
    main()