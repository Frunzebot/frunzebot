import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

user_sessions = {}

def build_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("Основний допис", callback_data="main_post")],
        [InlineKeyboardButton("Новина з посиланням", callback_data="link_post")],
        [InlineKeyboardButton("Анонімний внесок", callback_data="anon_post")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Оберіть тип допису:", reply_markup=build_main_keyboard())

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.from_user.id
    user_sessions[chat_id] = {"branch": query.data}
    await query.message.reply_text("Надішліть ваш матеріал.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        await update.message.reply_text("Будь ласка, спочатку оберіть тип допису через /start.")
        return

    branch = user_sessions[user_id]["branch"]
    message = update.message

    if branch == "main_post":
        user_sessions[user_id]["content"] = message
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Опублікувати", callback_data="publish")],
            [InlineKeyboardButton("✏️ Редагувати", callback_data="edit")],
            [InlineKeyboardButton("❌ Відхилити", callback_data="reject")]
        ])
        await message.reply_text("Попередній перегляд\n\n*адмін*", parse_mode="Markdown", reply_markup=keyboard)

    elif branch == "link_post":
        if message.text and "http" in message.text:
            user_sessions[user_id]["link"] = message.text
            preview = "*Попередній перегляд новини*\n\n*адмін*"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Опублікувати", callback_data="publish_link")],
                [InlineKeyboardButton("❌ Відхилити", callback_data="reject_link")]
            ])
            await message.reply_text(preview, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await message.reply_text("Будь ласка, надішліть коректне посилання.")
    else:
        await message.reply_text("Цю гілку ще не реалізовано.")

async def handle_publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = user_sessions.get(user_id)

    if not session:
        await query.message.reply_text("Немає активної сесії.")
        return

    branch = session["branch"]

    if branch == "main_post":
        content = session.get("content")
        if content:
            if content.text and content.photo:
                await context.bot.send_photo(CHANNEL_ID, photo=content.photo[-1].file_id, caption=content.text + "\n\nадмін")
            elif content.text and content.video:
                await context.bot.send_video(CHANNEL_ID, video=content.video.file_id, caption=content.text + "\n\nадмін")
            elif content.photo:
                await context.bot.send_photo(CHANNEL_ID, photo=content.photo[-1].file_id, caption="адмін")
            elif content.video:
                await context.bot.send_video(CHANNEL_ID, video=content.video.file_id, caption="адмін")
            elif content.text:
                await context.bot.send_message(CHANNEL_ID, text=content.text + "\n\nадмін")
            await query.message.reply_text("✅ Допис опубліковано.")
        else:
            await query.message.reply_text("Немає вмісту для публікації.")
    elif branch == "link_post":
        link = session.get("link")
        if link:
            caption = "*адмін*\n[Читати новину](" + link + ")"
            await context.bot.send_message(CHANNEL_ID, text=caption, parse_mode="Markdown", disable_web_page_preview=False)
            await query.message.reply_text("✅ Посилання опубліковано.")
        else:
            await query.message.reply_text("Немає посилання для публікації.")

async def handle_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_sessions.pop(user_id, None)
    await query.message.reply_text("❌ Допис не пройшов модерацію.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^(main_post|link_post|anon_post)$"))
    app.add_handler(CallbackQueryHandler(handle_publish, pattern="^(publish|publish_link)$"))
    app.add_handler(CallbackQueryHandler(handle_reject, pattern="^(reject|reject_link)$"))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()