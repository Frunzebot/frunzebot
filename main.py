from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

application = ApplicationBuilder().token(BOT_TOKEN).build()

# Обробка /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привіт! Обери тип допису:")

# Обробка повідомлень
async def handle_message(update: Update, context: CallbackContext):
    user = update.message.from_user
    content = update.message.text or ""
    is_admin = user.id == ADMIN_ID

    sender_label = "адмін" if is_admin else "жолудевий вкид від комʼюніті"
    caption = f"{sender_label}:\n{content}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Опублікувати", callback_data="approve"),
         InlineKeyboardButton("✏️ Редагувати", callback_data="edit"),
         InlineKeyboardButton("❌ Відхилити", callback_data="reject")]
    ])

    # Надсилаємо адміну попередній перегляд
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=caption,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    context.user_data["sender_id"] = user.id
    context.user_data["original_message"] = content

# Обробка кнопок
async def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    action = query.data
    sender_id = context.user_data.get("sender_id")
    original = context.user_data.get("original_message")

    if action == "approve":
        await context.bot.send_message(chat_id="@frunzepro", text=original)
        await context.bot.send_message(chat_id=sender_id, text="✅ Ваш допис опубліковано.")
    elif action == "reject":
        await context.bot.send_message(chat_id=sender_id, text="❌ Ваш допис не пройшов модерацію.")
    elif action == "edit":
        await context.bot.send_message(chat_id=sender_id, text="✏️ Ваш допис потребує редагування. Надішліть, будь ласка, нову версію для повторної перевірки.")

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
application.add_handler(CallbackQueryHandler(handle_callback))

application.run_polling()