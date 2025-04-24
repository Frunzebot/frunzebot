
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, CommandHandler, filters

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Основний текст/фото/відео-допис", callback_data='post')],
        [InlineKeyboardButton("Новини з посиланням (http)", callback_data='link')],
        [InlineKeyboardButton("Анонімний внесок / інсайд", callback_data='anon')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть тип допису:", reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['type'] = query.data
    await query.edit_message_text("Надішліть текст / фото / відео або посилання.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = update.message.text or update.message.caption or "Медіа"
    media = update.message.photo[-1].file_id if update.message.photo else None
    message = f"({context.user_data.get('type', 'анонімно')}) [ФОТО/МЕДІА]" if media else content

    keyboard = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data='approve')],
        [InlineKeyboardButton("✏️ Редагувати", callback_data='edit')],
        [InlineKeyboardButton("❌ Відхилити", callback_data='reject')]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=ADMIN_ID, text=message, reply_markup=markup)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
