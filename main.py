from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import os
import logging

# Логування
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Чернетки та статуси
drafts = {}
post_types = {}

# Стартове меню
def get_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Основний допис", callback_data="main_post")],
        [InlineKeyboardButton("Новина з посиланням", callback_data="link_post")]
    ])

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post_types[update.effective_user.id] = None
    await update.message.reply_text("Оберіть тип допису:", reply_markup=get_menu())

# Обробка кнопок меню
async def select_post_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    post_types[query.from_user.id] = query.data
    await query.message.reply_text("Надішліть ваш матеріал або посилання.")

# Основна логіка допису
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    post_type = post_types.get(user_id)

    if not post_type:
        await update.message.reply_text("Будь ласка, спочатку оберіть тип допису через /start.")
        return

    # Гілка 1 — основний текст/фото/відео-допис
    if post_type == "main_post":
        content = {"text": update.message.text, "photo": None, "video": None}
        if update.message.photo:
            content["photo"] = update.message.photo[-1].file_id
        if update.message.video:
            content["video"] = update.message.video.file_id
        drafts[user_id] = content

        text = update.message.text or ""
        preview = "*Попередній перегляд*
_адмін_
" + text

        buttons = [
            [InlineKeyboardButton("✅ Опублікувати", callback_data="publish")],
            [InlineKeyboardButton("✏️ Редагувати", callback_data="edit")],
            [InlineKeyboardButton("❌ Відхилити", callback_data="reject")]
        ]
        await update.message.reply_text(preview, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

    # Гілка 2 — посилання
    elif post_type == "link_post":
        link = update.message.text
        if not link.startswith("http"):
            await update.message.reply_text("Це не схоже на посилання. Спробуйте ще раз.")
            return
        drafts[user_id] = {"link": link}
        preview = "*Попередній перегляд новини*
_адмін_
[Читати новину](" + link + ")"
        buttons = [
            [InlineKeyboardButton("✅ Опублікувати", callback_data="publish")],
            [InlineKeyboardButton("❌ Відхилити", callback_data="reject")]
        ]
        await update.message.reply_text(preview, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

# Обробка кнопок після попереднього перегляду
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    content = drafts.get(user_id)

    if not content:
        await query.message.reply_text("Чернетку не знайдено.")
        return

    if data == "publish":
        if "link" in content:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text="адмін
[Читати новину](" + content["link"] + ")",
                parse_mode="Markdown"
            )
        else:
            caption = f"адмін
{content.get('text') or ''}"
            if content.get("photo"):
                await context.bot.send_photo(chat_id=CHANNEL_ID, photo=content["photo"], caption=caption)
            elif content.get("video"):
                await context.bot.send_video(chat_id=CHANNEL_ID, video=content["video"], caption=caption)
            else:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)
        await query.message.reply_text("✅ Опубліковано.")
        drafts.pop(user_id)

    elif data == "edit":
        await query.message.reply_text("✏️ Надішліть нову версію допису.")
    elif data == "reject":
        await query.message.reply_text("❌ Ваш матеріал не пройшов модерацію.")
        drafts.pop(user_id)

# Запуск бота
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(select_post_type, pattern="^(main_post|link_post)$"))
app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_message))
app.add_handler(CallbackQueryHandler(handle_callback, pattern="^(publish|edit|reject)$"))

if __name__ == "__main__":
    app.run_polling()
