# bot.py  –  FRUNZEBOT MVP ядро
# python-telegram-bot v20+

import logging
import os
from enum import Enum, auto
from datetime import datetime, timedelta

from tinydb import TinyDB, Query
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ──────────── КОНФІГ ────────────
BOT_TOKEN   = os.getenv("TELEGRAM_TOKEN") or "PUT_YOUR_TOKEN_HERE"
ADMIN_ID    = int(os.getenv("ADMIN_ID")   or 6266425881)      # заміни своїм
DB_PATH     = "frunze_drafts.json"

CATEGORIES = [
    "Інформаційна отрута",
    "Суспільні питання",
    "Я і моя філософія",
]

class DraftStatus(Enum):
    PENDING   = auto()
    NEED_EDIT = auto()
    APPROVED  = auto()
    REJECTED  = auto()

# ──────────── СХОВИЩЕ ────────────
db = TinyDB(DB_PATH)
Draft = Query()

def save_draft(draft: dict):
    db.upsert(draft, Draft.draft_id == draft["draft_id"])

def get_draft(draft_id: str) -> dict | None:
    res = db.search(Draft.draft_id == draft_id)
    return res[0] if res else None

# ──────────── ХЕНДЛЕРИ ────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = ReplyKeyboardMarkup(
        [["Запропонувати пост"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text(
        "Тут формують, а не споживають.\n\nНадішли текст / фото / відео – "
        "і обери категорію.", reply_markup=kb
    )

async def incoming_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # зберігаємо чернетку у context до вибору категорії
    context.user_data["payload"] = update.message
    kb = ReplyKeyboardMarkup(
        [[c] for c in CATEGORIES], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text("Обери категорію:", reply_markup=kb)

async def set_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text not in CATEGORIES:
        return
    payload = context.user_data.pop("payload", None)
    if not payload:
        return

    draft_id = f"{payload.chat.id}_{payload.id}"
    draft = {
        "draft_id": draft_id,
        "user_id": payload.from_user.id,
        "status": DraftStatus.PENDING.name,
        "category": update.message.text,
        "date": datetime.now().isoformat(),
    }
    save_draft(draft)

    # надсилаємо адмінові чернетку
    caption = f"<b>Категорія:</b> {draft['category']}\n<b>ID:</b> {draft_id}"
    buttons = [
        [
            InlineKeyboardButton("✅ Опублікувати", callback_data=f"approve:{draft_id}"),
            InlineKeyboardButton("✏️ Потребує правок", callback_data=f"edit:{draft_id}"),
            InlineKeyboardButton("❌ Відхилити",    callback_data=f"reject:{draft_id}"),
        ]
    ]
    kb = InlineKeyboardMarkup(buttons)
    await payload.copy(chat_id=ADMIN_ID, caption=caption, parse_mode=ParseMode.HTML, reply_markup=kb)

    await payload.reply_text("Дякую! Чернетка передана модератору.", reply_markup=ReplyKeyboardRemove())

# ──────────── АДМІН-КНОПКИ ────────────
async def moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.callback_query.answer("Не твоє питання 😉", show_alert=True)
        return

    action, draft_id = update.callback_query.data.split(":")
    draft = get_draft(draft_id)
    if not draft:
        await update.callback_query.answer("Чернетка не знайдена", show_alert=True)
        return

    # готуємо функції
    async def notify_user(text):
        try:
            await context.bot.send_message(chat_id=draft["user_id"], text=text)
        except Exception as e:
            logging.warning("Could not notify user: %s", e)

    if action == "approve":
        draft["status"] = DraftStatus.APPROVED.name
        save_draft(draft)
        await notify_user("✅ Ваш допис схвалено й буде опубліковано.")
        await update.callback_query.edit_message_reply_markup(None)

    elif action == "reject":
        draft["status"] = DraftStatus.REJECTED.name
        save_draft(draft)
        await notify_user("❌ Ваш допис не пройшов модерацію.")
        await update.callback_query.edit_message_reply_markup(None)

    elif action == "edit":
        draft["status"] = DraftStatus.NEED_EDIT.name
        save_draft(draft)
        context.user_data["pending_edit"] = draft_id
        await update.callback_query.message.reply_text(
            "Напиши коротко, що саме треба підправити:",
            reply_markup=ReplyKeyboardRemove()
        )
        await update.callback_query.answer()

async def admin_edit_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft_id = context.user_data.pop("pending_edit", None)
    if not draft_id:
        return

    draft = get_draft(draft_id)
    if not draft:
        return

    comment = update.message.text
    await context.bot.send_message(
        chat_id=draft["user_id"],
        text=f"✏️ Ваш допис потребує правок:\n\n{comment}\n\n"
             "Будь ласка, надішліть оновлену версію у відповідь."
    )
    await update.message.reply_text("Коментар надіслано автору.")

# ──────────── МЕЙН ────────────
def main():
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_category))
    app.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.TEXT) &
        ~filters.Filter(lambda m: m.text in CATEGORIES),
        incoming_content,
    ))
    app.add_handler(CallbackQueryHandler(moderation_callback))
    app.add_handler(MessageHandler(filters.TEXT, admin_edit_comment))

    logging.info("Bot starting…")
    app.run_polling()

if __name__ == "__main__":
    main()