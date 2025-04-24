from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = "YOUR_BOT_TOKEN"
CHANNEL_ID = "@frunze_pro"

user_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Основний постинг", callback_data="main_post")],
        [InlineKeyboardButton("Новини з посиланням", callback_data="news_link")],
        [InlineKeyboardButton("Анонімний внесок", callback_data="anon")]
    ]
    await update.message.reply_text("Оберіть тип допису:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    data = query.data
    user_state[user_id] = {"mode": data, "content": []}
    await query.message.reply_text("Надішліть текст, фото або відео.")