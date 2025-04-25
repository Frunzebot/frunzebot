import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

TOKEN = 'YOUR_BOT_TOKEN'
CHANNEL_ID = 'YOUR_CHANNEL_ID'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_states = {}
user_drafts = {}

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = 'awaiting_content'
    await update.message.reply_text("Надішліть свій текст, фото або відео:")

# ================== RECEIVE POST ==================
async def receive_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id)

    if state != 'awaiting_content':
        return

    content = {'text': '', 'photos': [], 'videos': []}

    if update.message.text:
        content['text'] = update.message.text

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        content['photos'].append(file_id)

    if update.message.video:
        file_id = update.message.video.file_id
        content['videos'].append(file_id)

    if update.message.caption:
        content['text'] = update.message.caption

    if not content['text'] and not content['photos'] and not content['videos']:
        await update.message.reply_text("Будь ласка, надішліть текст, фото або відео.")
        return

    user_drafts[user_id] = content
    user_states[user_id] = 'preview_ready'

    await send_preview(update, context, user_id)

# ================== SEND PREVIEW ==================
async def send_preview(update, context, user_id):
    content = user_drafts[user_id]
    text = content['text']
    photos = content['photos']
    videos = content['videos']

    username = update.effective_user.username
    signature = "адмін" if username == "FrunzePro" else "жолудевий вкид від комʼюніті"
    full_text = f"{signature}\n\n{text}" if text else signature

    keyboard = [
        [
            InlineKeyboardButton("✅ Опублікувати", callback_data="publish"),
            InlineKeyboardButton("✏️ Редагувати", callback_data="edit"),
            InlineKeyboardButton("❌ Відхилити", callback_data="reject")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if photos and not videos:
        if len(photos) == 1:
            await context.bot.send_photo(chat_id=user_id, photo=photos[0], caption=full_text, reply_markup=reply_markup)
        else:
            media = [InputMediaPhoto(media=p) for p in photos]
            media[0].caption = full_text
            await context.bot.send_media_group(chat_id=user_id, media=media)
            await context.bot.send_message(chat_id=user_id, text="⤴️ Попередній перегляд", reply_markup=reply_markup)
    elif videos:
        await context.bot.send_video(chat_id=user_id, video=videos[0], caption=full_text, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=user_id, text=full_text, reply_markup=reply_markup)

# ================== BUTTON HANDLER ==================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data
    content = user_drafts.get(user_id)

    if not content:
        await query.edit_message_text("Чернетка не знайдена.")
        return

    if data == "publish":
        text = content['text']
        photos = content['photos']
        videos = content['videos']
        username = query.from_user.username
        signature = "адмін" if username == "FrunzePro" else "жолудевий вкид від комʼюніті"
        full_text = f"{signature}\n\n{text}" if text else signature

        if photos and not videos:
            if len(photos) == 1:
                await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photos[0], caption=full_text)
            else:
                media = [InputMediaPhoto(media=p) for p in photos]
                media[0].caption = full_text
                await context.bot.send_media_group(chat_id=CHANNEL_ID, media=media)
        elif videos:
            await context.bot.send_video(chat_id=CHANNEL_ID, video=videos[0], caption=full_text)
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=full_text)

        await context.bot.send_message(chat_id=user_id, text="✅ Ваш допис опубліковано.")
        user_drafts.pop(user_id, None)
        user_states.pop(user_id, None)

    elif data == "reject":
        await context.bot.send_message(chat_id=user_id, text="❌ Ваш допис *не пройшов* модерацію.", parse_mode="Markdown")
        user_drafts.pop(user_id, None)
        user_states.pop(user_id, None)

    elif data == "edit":
        user_states[user_id] = 'awaiting_content'
        await context.bot.send_message(chat_id=user_id, text="Надішліть нову версію допису.")

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, receive_post))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()

if __name__ == '__main__':
    main()