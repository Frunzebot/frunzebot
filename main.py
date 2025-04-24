import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

drafts = {}
ADMIN_ID = 6266425881

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Основний текст/фото/відео-допис", callback_data='main')],
        [InlineKeyboardButton("Новини з посиланням (http)", callback_data='link')],
        [InlineKeyboardButton("Анонімний внесок / інсайд", callback_data='anon')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Що вміє цей бот?\nЛаскаво просимо! Натисніть /start, щоб обрати тип допису.", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["type"] = query.data
    await query.edit_message_text(text="Надішліть текст / фото / відео або посилання.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_type = context.user_data.get("type")
    user = update.message.from_user
    content = {
        "text": update.message.text_html if update.message.text else "",
        "photo": update.message.photo[-1].file_id if update.message.photo else None,
        "video": update.message.video.file_id if update.message.video else None,
        "from_user": user.id
    }
    drafts[user.id] = {"type": msg_type, "content": content}

    buttons = [
        [InlineKeyboardButton("Опублікувати", callback_data=f"publish_{user.id}")],
        [InlineKeyboardButton("Відхилити", callback_data=f"reject_{user.id}")]
    ]
    preview = f"<b>Попередній перегляд</b>\n\n"
    preview += f"{content['text']}\n\n" if content['text'] else ""

    if msg_type == "anon":
        signature = "жолудевий вкид анонімно"
    elif user.id == ADMIN_ID:
        signature = "адмін"
    else:
        signature = "жолудевий вкид від комʼюніті"

    formatted = f"{signature}"

    await context.bot.send_message(chat_id=ADMIN_ID, text=preview + formatted, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
    await update.message.reply_text("✅ Дякуємо! Ваш матеріал передано на модерацію.")

async def decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    decision, user_id = query.data.split("_")
    user_id = int(user_id)
    data = drafts.get(user_id)
    if not data:
        await query.edit_message_text("Помилка: чернетку не знайдено.")
        return

    content = data["content"]
    msg_type = data["type"]

    if decision == "publish":
        header = "FrunzePro\nадмін\n\n" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті\n\n"
        final_text = header + (content['text'] if content['text'] else "")

        if content["photo"]:
            await context.bot.send_photo(chat_id='@frunze_pro', photo=content["photo"], caption=final_text, parse_mode="HTML")
        elif content["video"]:
            await context.bot.send_video(chat_id='@frunze_pro', video=content["video"], caption=final_text, parse_mode="HTML")
        else:
            await context.bot.send_message(chat_id='@frunze_pro', text=final_text, parse_mode="HTML")

        await context.bot.send_message(chat_id=user_id, text="✅ Дякуємо за інсайд. Ваш допис опубліковано.")
    else:
        await context.bot.send_message(chat_id=user_id, text="❌ Дякуємо за матеріал, але ваш матеріал не пройшов модерацію.")

    del drafts[user_id]
    await query.edit_message_text("Рішення виконано.")

def main():
    from os import getenv
    BOT_TOKEN = getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button, pattern="^(main|link|anon)$"))
    app.add_handler(CallbackQueryHandler(decision, pattern="^(publish|reject)_"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()