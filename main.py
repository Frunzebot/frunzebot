import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)

ADMIN_ID = 6266425881
CHANNEL_ID = "@frunze_pro"
drafts = {}
edit_windows = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Основний текст/фото/відео-допис", callback_data='main')],
    ]
    await update.message.reply_text(
        "Оберіть тип допису для продовження:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data.clear()

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["type"] = query.data
    context.user_data["submitted"] = False
    await query.edit_message_text("Надішліть один допис (текст, фото, відео або все разом).")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_type = context.user_data.get("type")
    already_sent = context.user_data.get("submitted", False)
    user = update.message.from_user
    user_id = user.id

    if msg_type != "main":
        await update.message.reply_text("Будь ласка, спочатку оберіть тип допису через /start.")
        return

    now = datetime.now()
    edit_deadline = edit_windows.get(user_id)

    if already_sent and not edit_deadline:
        await update.message.reply_text("Ви вже надіслали матеріал. Очікуйте рішення або натисніть ✏️ Редагувати.")
        return

    if edit_deadline and now > edit_deadline:
        edit_windows.pop(user_id, None)
        await update.message.reply_text("❌ Час редагування завершився. Створіть новий допис через /start.")
        return

    content = {
        "text": update.message.text_html if update.message.text else "",
        "photo": update.message.photo[-1].file_id if update.message.photo else None,
        "video": update.message.video.file_id if update.message.video else None,
        "from_user": user_id,
        "timestamp": now
    }

    drafts[user_id] = {"type": msg_type, "content": content}
    context.user_data["submitted"] = True

    signature = "адмін" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті"
    preview = "<b>Попередній перегляд</b>\n\n"
    if content["text"]:
        preview += content["text"] + "\n\n"
    preview += f"<i>{signature}</i>"

    buttons = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data=f"publish|{user_id}")],
        [InlineKeyboardButton("✏️ Редагувати", callback_data=f"edit|{user_id}")],
        [InlineKeyboardButton("❌ Відхилити", callback_data=f"reject|{user_id}")]
    ]

    await context.bot.send_message(chat_id=ADMIN_ID, text=preview, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
    await update.message.reply_text("✅ Дякуємо! Ваш матеріал передано на модерацію.")

async def decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, user_id = query.data.split("|")
    user_id = int(user_id)

    data = drafts.get(user_id)
    if not data:
        await query.edit_message_text("❌ Чернетку не знайдено.")
        return

    content = data["content"]
    signature = "адмін" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті"
    final_text = f"{signature}\n\n{content['text']}" if content['text'] else signature

    if action == "publish":
        if content["photo"]:
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=content["photo"], caption=final_text, parse_mode="HTML")
        elif content["video"]:
            await context.bot.send_video(chat_id=CHANNEL_ID, video=content["video"], caption=final_text, parse_mode="HTML")
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=final_text, parse_mode="HTML")
        await context.bot.send_message(chat_id=user_id, text="✅ Ваш допис опубліковано.")

    elif action == "reject":
        await context.bot.send_message(chat_id=user_id, text="❌ Ваш матеріал не пройшов модерацію. Ви можете надіслати нову версію.")

    elif action == "edit":
        await context.bot.send_message(chat_id=user_id, text="✏️ Ви можете надіслати нову версію допису. У вас є 20 хвилин.")
        context.user_data["type"] = "main"
        context.user_data["submitted"] = False
        edit_windows[user_id] = datetime.now() + timedelta(minutes=20)
        return

    # Видаляємо чернетку після будь-якого рішення
    drafts.pop(user_id, None)
    edit_windows.pop(user_id, None)
    await query.edit_message_text("✅ Рішення виконано.")

def main():
    from os import getenv
    app = ApplicationBuilder().token(getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button, pattern="^(main)$"))
    app.add_handler(CallbackQueryHandler(decision, pattern="^(publish|reject|edit)\|"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()