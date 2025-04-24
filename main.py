import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO)

ADMIN_ID = 6266425881
CHANNEL_ID = "@frunze_pro"
drafts = {}
link_drafts = {}

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Основний текст/фото/відео-допис", callback_data='main')],
        [InlineKeyboardButton("Новини з посиланням (http)", callback_data='link')]
    ]
    await update.message.reply_text("Оберіть тип допису для продовження:", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data.clear()

# Обробка вибору гілки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["type"] = query.data
    await query.edit_message_text("Надішліть контент згідно обраної гілки.")

# ГІЛКА 1 — Текст/Фото/Відео
async def handle_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("type") != "main":
        return

    user = update.message.from_user
    text = update.message.caption_html or update.message.text_html or ""
    photo = update.message.photo[-1].file_id if update.message.photo else None
    video = update.message.video.file_id if update.message.video else None

    drafts[user.id] = {"text": text, "photo": photo, "video": video}

    signature = "адмін" if user.id == ADMIN_ID else "жолудевий вкид від комʼюніті"
    preview = f"<b>Попередній перегляд</b>\n\n{text}\n\n<i>{signature}</i>"

    buttons = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data=f"main_publish_{user.id}")],
        [InlineKeyboardButton("❌ Відхилити", callback_data=f"main_reject_{user.id}")]
    ]

    await context.bot.send_message(chat_id=ADMIN_ID, text=preview, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
    await update.message.reply_text("✅ Допис передано на модерацію.")
    async def handle_main_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[-1])
    action = query.data.split("_")[1]

    data = drafts.get(user_id)
    if not data:
        await query.edit_message_text("❌ Чернетку не знайдено.")
        return

    text, photo, video = data["text"], data["photo"], data["video"]
    signature = "адмін" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті"
    caption = f"{signature}\n\n{text}" if text else signature

    if action == "publish":
        if video:
            await context.bot.send_video(chat_id=CHANNEL_ID, video=video, caption=caption, parse_mode="HTML")
        elif photo:
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=caption, parse_mode="HTML")
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="HTML")
        await context.bot.send_message(chat_id=user_id, text="✅ Ваш допис опубліковано.")
    else:
        await context.bot.send_message(chat_id=user_id, text="❌ Ваш матеріал не пройшов модерацію.")

    del drafts[user_id]
    await query.edit_message_text("✅ Рішення виконано.")

# === ГІЛКА 2 — Посилання
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("type") != "link":
        await update.message.reply_text("Будь ласка, спочатку оберіть тип допису через /start.")
        return

    user = update.message.from_user
    url = update.message.text.strip()
    link_drafts[user.id] = {"url": url}

    signature = "адмін" if user.id == ADMIN_ID else "жолудевий вкид від комʼюніті"
    preview = f"<b>Попередній перегляд новини</b>\n\n<b>{signature}</b>\n[Перейти до новини]({url})"

    buttons = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data=f"link_publish_{user.id}")],
        [InlineKeyboardButton("❌ Відхилити", callback_data=f"link_reject_{user.id}")]
    ]

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=preview,
        parse_mode="HTML",
        disable_web_page_preview=False,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    await update.message.reply_text("✅ Посилання передано на модерацію.")

async def handle_link_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[-1])
    action = query.data.split("_")[1]

    data = link_drafts.get(user_id)
    if not data:
        await query.edit_message_text("❌ Чернетку не знайдено.")
        return

    url = data["url"]
    signature = "адмін" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті"
    post_text = f"{signature}\n[Читати новину]({url})"

    await context.bot.send_message(chat_id=CHANNEL_ID, text=post_text, parse_mode="MarkdownV2", disable_web_page_preview=False)
    await context.bot.send_message(chat_id=user_id, text="✅ Ваше посилання опубліковано.")

    del link_drafts[user_id]
    await query.edit_message_text("✅ Рішення виконано.")

# === ЗАПУСК ===
def main():
    from os import getenv
    app = ApplicationBuilder().token(getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button, pattern="^(main|link)$"))
    app.add_handler(MessageHandler(filters.TEXT & filters.Entity("url"), handle_link))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_main))
    app.add_handler(CallbackQueryHandler(handle_main_decision, pattern="^main_(publish|reject)_"))
    app.add_handler(CallbackQueryHandler(handle_link_decision, pattern="^link_(publish|reject)_"))

    app.run_polling()

if __name__ == "__main__":
    main()