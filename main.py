from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

pending_messages = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Основний допис", callback_data="main_post")]
    ]
    await update.message.reply_text("Оберіть тип допису:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "main_post":
        context.user_data["post_type"] = "main"
        await query.message.reply_text("Надішліть текст, фото або відео (можна все разом).")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post_type = context.user_data.get("post_type")
    if not post_type:
        await update.message.reply_text("Будь ласка, оберіть тип допису через /start.")
        return

    user_id = update.effective_user.id
    content = {"text": update.message.text, "photo": update.message.photo, "video": update.message.video}

    pending_messages[user_id] = content
    keyboard = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data="publish")],
        [InlineKeyboardButton("✏️ Редагувати", callback_data="edit")],
        [InlineKeyboardButton("❌ Відхилити", callback_data="reject")]
    ]
    await update.message.reply_text("Попередній перегляд", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    content = pending_messages.get(user_id)

    if content:
        text = content.get("text", "")
        caption = f"адмін\n\n{text}" if text else "адмін"

        if content.get("photo"):
            await context.bot.send_photo(CHANNEL_ID, photo=content["photo"][-1].file_id, caption=caption)
        elif content.get("video"):
            await context.bot.send_video(CHANNEL_ID, video=content["video"].file_id, caption=caption)
        elif text:
            await context.bot.send_message(CHANNEL_ID, text=caption)

        del pending_messages[user_id]
        await query.edit_message_text("✅ Допис опубліковано.")
    else:
        await query.edit_message_text("❌ Чернетку не знайдено.")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_callback, pattern="^(main_post|publish|edit|reject)$"))
app.add_handler(MessageHandler(filters.ALL, handle_message))