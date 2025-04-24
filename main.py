import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

logging.basicConfig(level=logging.INFO)

ADMIN_ID = 6266425881
CHANNEL_ID = '@frunze_pro'
drafts = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Основний текст/фото/відео-допис", callback_data='main')],
        [InlineKeyboardButton("Новини з посиланням (http)", callback_data='link')],
        [InlineKeyboardButton("Анонімний внесок / інсайд", callback_data='anon')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Що вміє цей бот?\nНатисніть /start, щоб обрати тип допису.", reply_markup=reply_markup)

async def select_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["type"] = query.data
    await query.edit_message_text("Надішліть текст / фото / відео або посилання.")

async def handle_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    msg_type = context.user_data.get("type")
    content = {
        "text": update.message.text_html if update.message.text else "",
        "photo": update.message.photo[-1].file_id if update.message.photo else None,
        "video": update.message.video.file_id if update.message.video else None,
        "from_user": user.id,
    }
    drafts[user.id] = {"type": msg_type, "content": content}

    # Підпис
    if msg_type == "anon":
        signature = "жолудевий вкид анонімно"
    elif user.id == ADMIN_ID:
        signature = "адмін"
    else:
        signature = "жолудевий вкид від комʼюніті"

    # Попередній перегляд
    preview = "<b>Попередній перегляд</b>\n\n"
    if content["text"]:
        preview += f"{content['text']}\n\n"
    preview += signature

    buttons = [
        [InlineKeyboardButton("Опублікувати", callback_data=f"publish_{user.id}")],
        [InlineKeyboardButton("Відхилити", callback_data=f"reject_{user.id}")]
    ]

    await context.bot.send_message(chat_id=ADMIN_ID, text=preview, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
    await update.message.reply_text("✅ Дякуємо! Ваш матеріал передано на модерацію.")

async def process_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    decision, user_id = query.data.split("_")
    user_id = int(user_id)

    data = drafts.get(user_id)
    if not data:
        await query.edit_message_text("Чернетку не знайдено.")
        return

    content = data["content"]
    msg_type = data["type"]

    # Підпис
    if msg_type == "anon":
        signature = "жолудевий вкид анонімно"
    elif user_id == ADMIN_ID:
        header = "FrunzePro\nадмін\n\n"
        signature = "адмін"
    else:
        header = "жолудевий вкид від комʼюніті\n\n"
        signature = "жолудевий вкид від комʼюніті"

    final_text = f"{header if user_id != ADMIN_ID else header}{content['text']}" if content['text'] else header

    if decision == "publish":
        if content["photo"]:
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=content["photo"], caption=final_text, parse_mode="HTML")
        elif content["video"]:
            await context.bot.send_video(chat_id=CHANNEL_ID, video=content["video"], caption=final_text, parse_mode="HTML")
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=final_text, parse_mode="HTML")
        await context.bot.send_message(chat_id=user_id, text="✅ Дякуємо за інсайт. Ваш допис опубліковано.")
    else:
        await context.bot.send_message(chat_id=user_id, text="❌ Дякуємо за матеріал, але ваш матеріал не пройшов модерацію.")

    del drafts[user_id]
    await query.edit_message_text("Рішення виконано.")

def main():
    from os import getenv
    app = ApplicationBuilder().token(getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(select_type, pattern="^(main|link|anon)$"))
    app.add_handler(CallbackQueryHandler(process_decision, pattern="^(publish|reject)_"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_submission))

    app.run_polling()

if __name__ == '__main__':
    main()