from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler, ContextTypes
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Відповідь на /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["Основний текст/фото/відео-допис"],
        ["Новини з посиланням (http)"],
        ["Анонімний внесок / інсайд"]
    ]
    reply_markup = {"keyboard": keyboard, "resize_keyboard": True}
    await update.message.reply_text(
        "Що вміє цей бот?\nЛаскаво просимо! Натисніть /start, щоб обрати тип допису.",
        reply_markup=reply_markup
    )

# Основний постинг
async def handle_text_photo_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if message.text and "http" in message.text:
        return await handle_link(update, context)

    content = []
    if message.caption:
        content.append(message.caption)
    elif message.text:
        content.append(message.text)

    media = []
    if message.photo:
        media.append(InputMediaPhoto(media=message.photo[-1].file_id, caption="\n".join(content)))
    elif message.video:
        media.append(InputMediaVideo(media=message.video.file_id, caption="\n".join(content)))

    if media:
        await context.bot.send_media_group(chat_id=CHANNEL_ID, media=media)
    else:
        await context.bot.send_message(chat_id=CHANNEL_ID, text="\n".join(content))

    await message.reply_text("Допис опубліковано.")

# Новини з лінком
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    url = message.text.strip()
    await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text=f"жолудевий вкид:\n{url}"
    )
    await message.reply_text("Новину опубліковано.")

# Анонімні інсайди
async def handle_anonymous(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    content = message.text or message.caption or "[Анонімне фото/відео]"

    media = []
    if message.photo:
        media.append(InputMediaPhoto(media=message.photo[-1].file_id, caption=content))
    elif message.video:
        media.append(InputMediaVideo(media=message.video.file_id, caption=content))

    if media:
        await context.bot.send_media_group(chat_id=CHANNEL_ID, media=media)
    else:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=f"Анонімний внесок:\n{content}")

    await message.reply_text("Анонімне повідомлення надіслано адміну.")

# Розпізнавання типу
async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or update.message.caption or ""

    if text.startswith("Новини з посиланням") or ("http" in text and len(text) < 300):
        return await handle_link(update, context)
    elif text.startswith("Анонімний внесок"):
        return await handle_anonymous(update, context)
    else:
        return await handle_text_photo_video(update, context)

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.ALL, router))

app.run_polling()