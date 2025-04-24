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
    keyboard = [[InlineKeyboardButton("Основний текст/фото/відео-допис", callback_data='main')]]
    await update.message.reply_text("Оберіть тип допису для продовження:", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data.clear()

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.update({
        "type": query.data,
        "submitted": False,
        "edit_mode": False,
        "edit_locked": False
    })
    await query.edit_message_text("Надішліть один допис (текст, фото, відео або все разом).")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    now = datetime.now()

    if context.user_data.get("type") != "main":
        await update.message.reply_text("Будь ласка, спочатку оберіть тип допису через /start.")
        return

    if context.user_data.get("submitted", False):
        if context.user_data.get("edit_mode") and not context.user_data.get("edit_locked"):
            if datetime.now() <= edit_windows.get(user_id, now):
                context.user_data.update({"submitted": True, "edit_locked": True})
            else:
                await update.message.reply_text("❌ Час редагування завершився. Створіть новий допис через /start.")
                return
        else:
            await update.message.reply_text("Ви вже надіслали матеріал. Натисніть ✏️ для редагування.")
            return

    text = update.message.caption_html or update.message.text_html or ""
    photo = update.message.photo[-1].file_id if update.message.photo else None
    video = update.message.video.file_id if update.message.video else None

    drafts[user_id] = {
        "content": {"text": text, "photo": photo, "video": video},
        "timestamp": now
    }
    context.user_data["submitted"] = True

    signature = "адмін" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті"
    preview = f"<b>Попередній перегляд</b>\n\n{text}\n\n<i>{signature}</i>" if text else f"<b>Попередній перегляд</b>\n\n<i>{signature}</i>"

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
    text = content["text"]
    photo = content["photo"]
    video = content["video"]
    signature = "адмін" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті"
    caption = f"{signature}\n\n{text}" if text else signature

    if action == "publish":
        if video:
            await context.bot.send_video(chat_id=CHANNEL_ID, video=video, caption=caption if text else None, parse_mode="HTML")
        elif photo:
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=caption if text else None, parse_mode="HTML")
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="HTML")
        await context.bot.send_message(chat_id=user_id, text="✅ Ваш допис опубліковано.")

    elif action == "reject":
        await context.bot.send_message(chat_id=user_id, text="❌ Ваш матеріал не пройшов модерацію. Ви можете надіслати нову версію.")

    elif action == "edit":
        await context.bot.send_message(chat_id=user_id, text="✏️ Надішліть нову версію допису. У вас є 20 хвилин.")
        context.user_data.update({
            "type": "main",
            "submitted": False,
            "edit_mode": True,
            "edit_locked": False
        })
        edit_windows[user_id] = datetime.now() + timedelta(minutes=20)
        return

    # Очистка
    drafts.pop(user_id, None)
    edit_windows.pop(user_id, None)
    context.user_data.update({
        "submitted": False,
        "edit_mode": False,
        "edit_locked": False
    })
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