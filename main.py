from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Збереження чернетки
draft_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Основний допис", callback_data="main_post")],
        [InlineKeyboardButton("Новина з посиланням", callback_data="link_post")],
        [InlineKeyboardButton("Анонімний внесок", callback_data="anonymous_post")]
    ]
    await update.message.reply_text("Оберіть тип допису:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = context.user_data.get("state")

    if state == "main_post":
        draft_data[user_id] = update.message
        keyboard = [
            [InlineKeyboardButton("✅ Опублікувати", callback_data="publish")],
            [InlineKeyboardButton("✏️ Редагувати", callback_data="edit")],
            [InlineKeyboardButton("❌ Відхилити", callback_data="reject")]
        ]
        await context.bot.send_message(chat_id=user_id, text="Попередній перегляд", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "main_post":
        context.user_data["state"] = "main_post"
        await query.edit_message_text("Надішліть текст, фото або відео для публікації.")
    elif query.data == "publish":
        message = draft_data.get(user_id)
        if message:
            caption = message.caption or message.text or ""
            if message.photo:
                await context.bot.send_photo(chat_id=CHANNEL_ID, photo=message.photo[-1].file_id, caption=f"адмін\n\n{caption}")
            elif message.video:
                await context.bot.send_video(chat_id=CHANNEL_ID, video=message.video.file_id, caption=f"адмін\n\n{caption}")
            else:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=f"адмін\n\n{caption}")
            await query.edit_message_text("✅ Допис опубліковано.")
        else:
            await query.edit_message_text("❌ Чернетку не знайдено.")
    elif query.data == "edit":
        context.user_data["state"] = "main_post"
        await query.edit_message_text("✏️ Надішліть нову версію допису.")
    elif query.data == "reject":
        draft_data.pop(user_id, None)
        await query.edit_message_text("❌ Допис відхилено.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()

if __name__ == "__main__":
    main()