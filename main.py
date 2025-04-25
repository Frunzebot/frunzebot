from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = -1002093750924  # твій канал

application = ApplicationBuilder().token(BOT_TOKEN).build()

# /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привіт! Обери тип допису:")

# Зберігання чернеток
user_drafts = {}

# Обробка повідомлень (текст / фото / відео)
async def handle_message(update: Update, context: CallbackContext):
    user = update.message.from_user
    is_admin = user.id == ADMIN_ID
    sender_label = "адмін" if is_admin else "жолудевий вкид від комʼюніті"

    files = []
    content_type = None
    caption = update.message.caption or update.message.text or ""

    # Перевірка на фото
    if update.message.photo:
        content_type = "photo"
        for photo in update.message.photo:
            files.append(InputMediaPhoto(media=photo.file_id, caption=caption))

    # Перевірка на відео
    elif update.message.video:
        content_type = "video"
        files.append(InputMediaVideo(media=update.message.video.file_id, caption=caption))

    # Якщо є текст без фото/відео
    elif update.message.text:
        content_type = "text"

    # Зберігаємо чернетку
    if content_type in ["photo", "video"]:
        user_drafts[update.message.chat_id] = {
            "files": files,
            "caption": caption,
            "sender_id": user.id
        }

    preview_text = f"{sender_label}:\n{caption}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Опублікувати", callback_data="approve"),
         InlineKeyboardButton("✏️ Редагувати", callback_data="edit"),
         InlineKeyboardButton("❌ Відхилити", callback_data="reject")]
    ])

    # Надсилаємо попередній перегляд адміну
    if content_type == "photo" or content_type == "video":
        await context.bot.send_media_group(chat_id=ADMIN_ID, media=files)
        await context.bot.send_message(chat_id=ADMIN_ID, text=preview_text, reply_markup=keyboard)
    elif content_type == "text":
        await context.bot.send_message(chat_id=ADMIN_ID, text=preview_text, reply_markup=keyboard)

# Обробка кнопок
async def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    action = query.data
    chat_id = query.message.chat_id
    draft = user_drafts.get(chat_id)

    if not draft:
        await context.bot.send_message(chat_id=ADMIN_ID, text="⚠️ Чернетка не знайдена.")
        return

    sender_id = draft["sender_id"]
    files = draft["files"]
    caption = draft["caption"]

    sender_label = "адмін" if sender_id == ADMIN_ID else "жолудевий вкид від комʼюніті"
    caption = f"{sender_label}:\n{caption}"

    if action == "approve":
        if files:
            await context.bot.send_media_group(chat_id=CHANNEL_ID, media=files)
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)

        await context.bot.send_message(chat_id=sender_id, text="✅ Ваш допис опубліковано.")

    elif action == "reject":
        await context.bot.send_message(chat_id=sender_id, text="❌ Ваш допис не пройшов модерацію.")
    elif action == "edit":
        await context.bot.send_message(chat_id=sender_id, text="✏️ Ваш допис потребує редагування. Надішліть, будь ласка, нову версію.")