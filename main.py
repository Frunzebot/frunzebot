"""
FRUNZEBOT MVP  — ядро першої фази
* прийом контенту
* вибір категорії
* адмін-модерація: ✅ ✏️ ❌
"""

import logging
import os
from enum import Enum, auto
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from tinydb import TinyDB, Query
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ──────────────── КОНФІГ ────────────────
ENV_PATH = Path(".env")
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "PUT_TOKEN_HERE")
ADMIN_ID  = int(os.getenv("ADMIN_ID", 123456789))          # заміни своїм

DB_PATH = "frunze_drafts.json"

CATEGORIES = (
    "Інформаційна отрута",
    "Суспільні питання",
    "Я і моя філософія",
)


# ──────────────── ДАНІ ────────────────
class DraftStatus(Enum):
    PENDING   = auto()
    NEED_EDIT = auto()
    APPROVED  = auto()
    REJECTED  = auto()


db     = TinyDB(DB_PATH)
DraftQ = Query()


def save_draft(entry: dict):
    db.upsert(entry, DraftQ.draft_id == entry["draft_id"])


def get_draft(d_id: str) -> dict | None:
    res = db.search(DraftQ.draft_id == d_id)
    return res[0] if res else None


# ──────────────── ХЕНДЛЕРИ ────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = ReplyKeyboardMarkup(
        [["Запропонувати пост"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(
        "Тут формують, а не споживають.\n\nНадішли текст, фото або відео й обери категорію.",
        reply_markup=kb,
    )


async def handle_payload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Зберігаємо повідомлення у user_data → просимо обрати категорію.
    """
    context.user_data["payload"] = update.message
    cat_kb = ReplyKeyboardMarkup(
        [[c] for c in CATEGORIES], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text("Оберіть категорію:", reply_markup=cat_kb)


async def set_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Користувач натиснув одну з трьох категорій → формуємо чернетку й шлемо адмінам.
    """
    category = update.message.text
    payload: Update | None = context.user_data.pop("payload", None)

    if category not in CATEGORIES or payload is None:
        return  # позбавляємось помилкових спрацювань

    draft_id = f"{payload.chat.id}_{payload.id}"
    draft = {
        "draft_id": draft_id,
        "user_id": payload.from_user.id,
        "status": DraftStatus.PENDING.name,
        "category": category,
        "date": datetime.utcnow().isoformat(),
    }
    save_draft(draft)

    # ─── надсилаємо адмінові ───
    caption = (
        f"<b>Категорія:</b> {category}\n<b>ID:</b> <code>{draft_id}</code>"
    )
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅", callback_data=f"approve:{draft_id}"),
                InlineKeyboardButton("✏️", callback_data=f"edit:{draft_id}"),
                InlineKeyboardButton("❌", callback_data=f"reject:{draft_id}"),
            ]
        ]
    )

    try:
        await payload.copy(
            chat_id=ADMIN_ID, caption=caption, reply_markup=btns, parse_mode=ParseMode.HTML
        )
    except Exception as err:
        # fallback: надсилаємо тільки текст, якщо копіювати медіа не вдалося
        logging.warning("Copy failed: %s", err)
        await context.bot.send_message(
            chat_id=ADMIN_ID, text=f"{caption}\n\n[Не вдалося скопіювати медіа]"
        )

    await payload.reply_text(
        "Дякую! Чернетка передана модератору.", reply_markup=ReplyKeyboardRemove()
    )


# ──────────────── МОДЕРАЦІЯ ────────────────
async def cb_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Адмін натискає ✅ ✏️ ❌
    """
    if update.effective_user.id != ADMIN_ID:
        await update.callback_query.answer("Недостатньо прав", show_alert=True)
        return

    action, draft_id = update.callback_query.data.split(":")
    draft = get_draft(draft_id)
    if not draft:
        await update.callback_query.answer("Чернетку не знайдено", show_alert=True)
        return

    async def ping_user(text: str):
        try:
            await context.bot.send_message(draft["user_id"], text)
        except Exception as e:
            logging.warning("Notify fail: %s", e)

    if action == "approve":
        draft["status"] = DraftStatus.APPROVED.name
        save_draft(draft)
        await ping_user("✅ Ваш допис схвалено й буде опубліковано.")
        await update.callback_query.edit_message_reply_markup(None)

    elif action == "reject":
        draft["status"] = DraftStatus.REJECTED.name
        save_draft(draft)
        await ping_user("❌ Ваш допис не пройшов модерацію.")
        await update.callback_query.edit_message_reply_markup(None)

    elif action == "edit":
        draft["status"] = DraftStatus.NEED_EDIT.name
        save_draft(draft)
        context.user_data["edit_draft"] = draft_id
        await update.callback_query.message.reply_text(
            "Напишіть, що потрібно підправити:", reply_markup=ReplyKeyboardRemove()
        )
        await update.callback_query.answer()


async def admin_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Адмін надсилає пояснення для NEED_EDIT
    """
    draft_id = context.user_data.pop("edit_draft", None)
    if not draft_id or update.effective_user.id != ADMIN_ID:
        return

    draft = get_draft(draft_id)
    if not draft:
        return

    comment = update.message.text
    await context.bot.send_message(
        chat_id=draft["user_id"],
        text=f"✏️ Ваш допис потребує правок:\n\n{comment}\n\nНадішліть нову версію у відповідь.",
    )
    await update.message.reply_text("Коментар відправлено автору.")


# ──────────────── ЗБІРКА ────────────────
def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    )
    app = Application.builder().token(BOT_TOKEN).build()

    # командний старт
    app.add_handler(CommandHandler("start", cmd_start))

    # користувач спершу надсилає контент → payload
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND & ~filters.Regex("|".join(CATEGORIES)),
            handle_payload,
        )
    )

    # далі — вибір категорії
    app.add_handler(
        MessageHandler(filters.Regex(f"^({'|'.join(CATEGORIES)})$"), set_category)
    )

    # кнопки модерації
    app.add_handler(CallbackQueryHandler(cb_moderation))

    # текст від адміна після ✏️
    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID), admin_comment))

    logging.info("Bot started")
    app.run_polling(stop_signals=None)  # Railway сам глушить процес


if __name__ == "__main__":
    run()