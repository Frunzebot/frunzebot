import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from datetime import datetime, timedelta
from textwrap import shorten

logging.basicConfig(level=logging.INFO)

ADMIN_ID = 6266425881
CHANNEL_ID = "@frunze_pro"
drafts = {}
edit_windows = {}

def generate_hard_masked_link_message(url: str, author: str, custom_text: str = "") -> str:
    description = shorten(custom_text, width=140, placeholder="…") if custom_text else "читати більше тут"
    masked_link = f"[{description}]({url})"
    return f"{author}\n{masked_link}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Основний текст/фото/відео-допис", callback_data='main')],
        [InlineKeyboardButton("Новини з посиланням (http)", callback_data='link')]
    ]
    await update.message.reply_text(
        "Оберіть тип допису для продовження:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
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
    await query.edit_message_text("Надішліть один допис або посилання (в залежності від вибору).")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    msg_type = context.user_data.get("type")

    if not msg_type:
        await update.message.reply_text("Спочатку оберіть тип допису через /start.")
        return

    if context.user_data.get("submitted", False):
        await update.message.reply_text("Ви вже надіслали. Натисніть ✏️ для редагування або дочекайтесь рішення.")
        return

    now = datetime.now()

    if msg_type == "main":
        text = update.message.caption_html or update.message.text_html or ""
        photo = update.message.photo[-1].file_id if update.message.photo else None
        video = update.message.video.file_id if update.message.video else None

        drafts[user_id] = {"type": "main", "content": {"text": text, "photo": photo, "video": video}}
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

    elif msg_type == "link":
        text = update.message.text
        if not text or ("http" not in text and "https" not in text):
            await update.message.reply_text("Будь ласка, надішліть правильне посилання.")
            return

        signature = "адмін" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті"
        preview = f"<b>Попередній перегляд новини</b>\n\n{text}\n\n<i>{signature}</i>"

        drafts[user_id] = {"type": "link", "content": {"text": text, "from_user": user_id}}
        context.user_data["submitted"] = True

        buttons = [
            [InlineKeyboardButton("✅ Опублікувати", callback_data=f"publish_link|{user_id}")],
            [InlineKeyboardButton("❌ Відхилити", callback_data=f"reject_link|{user_id}")]
        ]
        await context.bot.send_message(chat_id=ADMIN_ID, text=preview, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
        await update.message.reply_text("✅ Посилання передано на модерацію.")

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
    post_type = data["type"]

    if post_type == "main":
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
            await context.bot.send_message(chat_id=user_id, text="❌ Ваш матеріал не пройшов модерацію.")

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

    elif post_type == "link":
        text = content["text"]
        url = text.strip().split()[0]
        description = text.replace(url, "").strip() or url
        signature = "адмін" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті"
        formatted = generate_hard_masked_link_message(url, signature, description)

        if action == "publish_link":
            await context.bot.send_message(chat_id=CHANNEL_ID, text=formatted, parse_mode="Markdown", disable_web_page_preview=False)
            await context.bot.send_message(chat_id=user_id, text="✅ Ваше посилання опубліковано.")
        elif action == "reject_link":
            await context.bot.send_message(chat_id=user_id, text="❌ Ваше посилання не пройшло модерацію.")

    drafts.pop(user_id, None)
    edit_windows.pop(user_id, None)
    context.user_data.clear()
    await query.edit_message_text("✅ Рішення виконано.")

def main():
    from os import getenv
    app = ApplicationBuilder().token(getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button, pattern="^(main|link)$"))
    app.add_handler(CallbackQueryHandler(decision, pattern="^(publish|reject|edit|publish_link|reject_link)\|"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()