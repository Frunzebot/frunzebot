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
    file_id = draft["file_id"]
    original_caption = draft["caption"]
    content_type = draft["content_type"]

    sender_label = "адмін" if sender_id == ADMIN_ID else "жолудевий вкид від комʼюніті"
    caption = f"{sender_label}:\n{original_caption}"

    if action == "approve":
        if content_type == "photo":
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=file_id, caption=caption)
        elif content_type == "video":
            await context.bot.send_video(chat_id=CHANNEL_ID, video=file_id, caption=caption)
        elif content_type == "text":
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)

        await context.bot.send_message(chat_id=sender_id, text="✅ Ваш допис опубліковано.")

    elif action == "reject":
        await context.bot.send_message(chat_id=sender_id, text="❌ Ваш допис не пройшов модерацію.")
    elif action == "edit":
        await context.bot.send_message(chat_id=sender_id, text="✏️ Ваш допис потребує редагування. Надішліть, будь ласка, нову версію.")