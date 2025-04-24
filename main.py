from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

user_states = {}
drafts = {}

def get_user_key(update: Update):
    return update.effective_user.id

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Основний допис", callback_data='main_post')],
        [InlineKeyboardButton("Новина з посиланням", callback_data='link_post')],
    ]
    await update.message.reply_text("Оберіть тип допису:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == 'main_post':
        user_states[user_id] = 'awaiting_main'
        await query.edit_message_text("Надішліть ваш матеріал (текст, фото, відео або все разом).")

    elif query.data == 'link_post':
        user_states[user_id] = 'awaiting_link'
        await query.edit_message_text("Надішліть посилання на новину.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id)

    if state == 'awaiting_main':
        draft_id = f"main_{user_id}"
        drafts[draft_id] = update.message
        keyboard = [
            [InlineKeyboardButton("✅ Опублікувати", callback_data=f'publish_main_{user_id}')],
            [InlineKeyboardButton("✏️ Редагувати", callback_data=f'edit_main_{user_id}')],
            [InlineKeyboardButton("❌ Відхилити", callback_data=f'delete_main_{user_id}')]
        ]
        await context.bot.send_message(chat_id=user_id, text="Попередній перегляд\n\nадмін", reply_markup=InlineKeyboardMarkup(keyboard))
        user_states[user_id] = 'waiting_main_confirm'

    elif state == 'awaiting_link':
        if update.message.text and update.message.text.startswith("http"):
            link = update.message.text
            draft_id = f"link_{user_id}"
            drafts[draft_id] = link
            keyboard = [
                [InlineKeyboardButton("✅ Опублікувати", callback_data=f'publish_link_{user_id}')],
                [InlineKeyboardButton("❌ Відхилити", callback_data=f'delete_link_{user_id}')]
            ]
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Попередній перегляд новини\n\nадмін\n[{link.split('//')[1]}]({link})",
                parse_mode='Markdown',
                disable_web_page_preview=False,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            user_states[user_id] = 'waiting_link_confirm'
        else:
            await update.message.reply_text("Це не схоже на посилання. Спробуйте знову.")

    else:
        await update.message.reply_text("Будь ласка, спочатку оберіть тип допису через /start.")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("publish_main_"):
        msg = drafts.get(f"main_{user_id}")
        if msg:
            caption = msg.caption or msg.text or " "
            if msg.video:
                await context.bot.send_video(chat_id=CHANNEL_ID, video=msg.video.file_id, caption=f"адмін\n{caption}")
            elif msg.photo:
                await context.bot.send_photo(chat_id=CHANNEL_ID, photo=msg.photo[-1].file_id, caption=f"адмін\n{caption}")
            else:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=f"адмін\n{caption}")
            await query.edit_message_text("✅ Опубліковано.")
            user_states[user_id] = None
            drafts.pop(f"main_{user_id}", None)

    elif query.data.startswith("delete_main_"):
        await query.edit_message_text("❌ Відхилено.")
        user_states[user_id] = None
        drafts.pop(f"main_{user_id}", None)

    elif query.data.startswith("edit_main_"):
        user_states[user_id] = 'awaiting_main'
        await query.edit_message_text("✏️ Надішліть нову версію допису.")

    elif query.data.startswith("publish_link_"):
        link = drafts.get(f"link_{user_id}")
        if link:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=f"адмін\n[читати новину]({link})", parse_mode='Markdown', disable_web_page_preview=False)
            await query.edit_message_text("✅ Посилання опубліковано.")
            user_states[user_id] = None
            drafts.pop(f"link_{user_id}", None)

    elif query.data.startswith("delete_link_"):
        await query.edit_message_text("❌ Посилання відхилено.")
        user_states[user_id] = None
        drafts.pop(f"link_{user_id}", None)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler, pattern='^(main_post|link_post)$'))
    app.add_handler(CallbackQueryHandler(callback_query_handler, pattern='^(publish_main_|delete_main_|edit_main_|publish_link_|delete_link_)'))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    app.run_polling()

if __name__ == '__main__':
    main()