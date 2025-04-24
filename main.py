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
        await context.bot.send_message(chat_id=user_id, text="✏️ Ви можете надіслати нову версію допису. У вас є 20 хвилин.")
        context.user_data["type"] = "main"
        context.user_data["submitted"] = False
        context.user_data["edit_mode"] = True
        context.user_data["edit_locked"] = False
        edit_windows[user_id] = datetime.now() + timedelta(minutes=20)
        return

    # Очищення
    drafts.pop(user_id, None)
    edit_windows.pop(user_id, None)
    context.user_data["submitted"] = False
    context.user_data["edit_mode"] = False
    context.user_data["edit_locked"] = False
    await query.edit_message_text("✅ Рішення виконано.")