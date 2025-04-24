import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

user_states = {}
preview_store = {}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Основний текст/фото/відео-допис", callback_data="main_post")],
        [InlineKeyboardButton("Новини з посиланням (http)", callback_data="news_link")],
        [InlineKeyboardButton("Анонімний внесок / інсайд", callback_data="anon_post")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть тип допису:", reply_markup=reply_markup)

# Обробка вибору гілки
async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    user_states[user_id] = query.data
    await query.message.reply_text("Очікую контент (текст / фото / відео / посилання):")

# Обробка вхідного контенту
async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id)

    text = update.message.text or update.message.caption or ""
    photo = update.message.photo[-1].file_id if update.message.photo else None
    video = update.message.video.file_id if update.message.video else None

    is_link = text.startswith("http://") or text.startswith("https://")

    if state == "news_link" or (is_link and not state):
        signature = "адмін" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті"
        formatted = f"{signature}

{text}"
        preview_store[user_id] = {"type": "text", "content": formatted, "route": "news"}
        keyboard = [
            [InlineKeyboardButton("✅ Опублікувати", callback_data=f"publish_{user_id}_news")],
            [InlineKeyboardButton("❌ Відхилити", callback_data=f"reject_{user_id}_news")]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"Чернетка новини:

{formatted}", reply_markup=markup)
        return

    if state == "anon_post":
        await update.message.reply_text("✅ Дякуємо за інсайд. Ваш матеріал передано адміну.")
        signature = "жолудевий вкид анонімно"
        preview_store[user_id] = {
            "type": "media" if photo or video else "text",
            "text": text,
            "photo": photo,
            "video": video,
            "route": "anon"
        }
        keyboard = [
            [InlineKeyboardButton("✅ Опублікувати", callback_data=f"publish_{user_id}_anon")],
            [InlineKeyboardButton("❌ Відхилити", callback_data=f"reject_{user_id}_anon")]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        if photo:
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo, caption=f"{signature}

{text}", reply_markup=markup)
        elif video:
            await context.bot.send_video(chat_id=ADMIN_ID, video=video, caption=f"{signature}

{text}", reply_markup=markup)
        else:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"{signature}

{text}", reply_markup=markup)
        return

    if state == "main_post":
        signature = "адмін" if user_id == ADMIN_ID else "жолудевий вкид від комʼюніті"
        preview_store[user_id] = {
            "type": "media" if photo or video else "text",
            "text": text,
            "photo": photo,
            "video": video,
            "route": "main"
        }
        keyboard = [
            [InlineKeyboardButton("✅ Опублікувати", callback_data=f"publish_{user_id}_main")],
            [InlineKeyboardButton("✏️ Редагувати", callback_data=f"edit_{user_id}_main")],
            [InlineKeyboardButton("❌ Відхилити", callback_data=f"reject_{user_id}_main")]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        preview = f"{signature}

{text}"
        if photo:
            await update.message.reply_photo(photo=photo, caption=preview, reply_markup=markup)
        elif video:
            await update.message.reply_video(video=video, caption=preview, reply_markup=markup)
        else:
            await update.message.reply_text(preview, reply_markup=markup)
        return

# Обробка кнопок підтвердження
async def handle_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    action, uid, route = data[0], int(data[1]), data[2]
    item = preview_store.get(uid)

    if not item:
        await query.edit_message_text("Чернетку втрачено.")
        return

    if action == "publish":
        if item["type"] == "text":
            await context.bot.send_message(chat_id=CHANNEL_ID, text=item["content"] if "content" in item else f"{'жолудевий вкид анонімно' if route=='anon' else 'адмін'}

{item['text']}")
        elif item["type"] == "media":
            caption = f"{'жолудевий вкид анонімно' if route=='anon' else 'адмін'}

{item['text']}"
            if item["photo"]:
                await context.bot.send_photo(chat_id=CHANNEL_ID, photo=item["photo"], caption=caption)
            elif item["video"]:
                await context.bot.send_video(chat_id=CHANNEL_ID, video=item["video"], caption=caption)

        if route == "anon":
            await context.bot.send_message(chat_id=uid, text="✅ Дякуємо за інсайд. Ваш допис опубліковано.")

        await query.edit_message_text("✅ Опубліковано.")
        del preview_store[uid]

    elif action == "reject":
        if route == "anon":
            await context.bot.send_message(chat_id=uid, text="❌ Дякуємо за матеріал, але ваш матеріал не пройшов модерацію.")
        await query.edit_message_text("❌ Відхилено.")
        if uid in preview_store:
            del preview_store[uid]

    elif action == "edit":
        user_states[uid] = "main_post"
        await context.bot.send_message(chat_id=uid, text="✏️ Надішліть новий текст або медіа.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_selection, pattern="^(main_post|news_link|anon_post)$"))
    app.add_handler(CallbackQueryHandler(handle_decision, pattern="^(publish|reject|edit)_\d+_.*$"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_content))
    app.run_polling()

if __name__ == "__main__":
    main() 