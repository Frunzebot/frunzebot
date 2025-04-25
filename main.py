from telegram import InputMediaPhoto, InputMediaVideo

# Обробка повідомлень (текст / фото / відео)
async def handle_message(update: Update, context: CallbackContext):
    user = update.message.from_user
    is_admin = user.id == ADMIN_ID
    sender_label = "адмін" if is_admin else "жолудевий вкид від комʼюніті"

    files = []
    content_type = None
    caption = update.message.caption or update.message.text or ""

    if update.message.photo:
        content_type = "photo"
        for photo in update.message.photo:
            files.append(InputMediaPhoto(media=photo.file_id, caption=caption))

    elif update.message.video:
        content_type = "video"
        files.append(InputMediaVideo(media=update.message.video.file_id, caption=caption))

    elif update.message.text:
        content_type = "text"

    # Якщо є фото/відео, зберігаємо чернетку
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
    if content_type == "photo":
        await context.bot.send_media_group(chat_id=ADMIN_ID, media=files)
        await context.bot.send_message(chat_id=ADMIN_ID, text=preview_text, reply_markup=keyboard)
    elif content_type == "video":
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
            if len(files) == 1:
                await context.bot.send_media_group(chat_id=CHANNEL_ID, media=files)
            else:
                # Якщо декілька фото або відео, надсилаємо разом
                await context.bot.send_media_group(chat_id=CHANNEL_ID, media=files)
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)

        await context.bot.send_message(chat_id=sender_id, text="✅ Ваш допис опубліковано.")

    elif action == "reject":
        await context.bot.send_message(chat_id=sender_id, text="❌ Ваш допис не пройшов модерацію.")
    elif action == "edit":
        await context.bot.send_message(chat_id=sender_id, text="✏️ Ваш допис потребує редагування. Надішліть, будь ласка, нову версію.")