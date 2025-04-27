"""
FRUNZEBOT – MVP ядро (Phase 1)
─────────────────────────────
• прийом тексту / фото / відео / документів
• вибір однієї з трьох категорій
• адмін-панель: ✅ ✏️ ❌
• фідбеки авторові
"""

from __future__ import annotations

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

# ────────────────── КОНФІГ ──────────────────
# .env опційний: локально зручно, на Railway достатньо Variables
if Path(".env").exists():
    load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID  = int(os.getenv("ADMIN_ID", "0").strip() or 0)

if not BOT_TOKEN or any(ch.isspace() for ch in BOT_TOKEN):
    raise RuntimeError(
        "BOT_TOKEN порожній або містить пробіли/перенесення рядка. "
        "Відредагуй змінні середовища."
    )
if ADMIN_ID == 0:
    raise RuntimeError("ADMIN_ID не заданий або не є числом Telegram-ID адміністратора.")

DB_PATH = "frunze_drafts.json"


# ────────────────── ДАНІ ──────────────────
class DraftStatus(Enum):
    PENDING   = auto()
    NEED_EDIT = auto()
    APPROVED  = auto()
    REJECTED  = auto()


CATEGORIES: tuple[str, ...] = (
    "Інформаційна отрута",
    "Суспільні питання",
    "Я і моя філософія",
)

db     = TinyDB(DB_PATH)
DQ     = Query()


def save_draft(obj: dict) -> None:
    db.upsert(obj, DQ.draft_id == obj["draft_id"])


def get_draft(draft_id: str) -> dict | None:
    res = db.search(DQ.draft_id == draft_id)
    return res[0] if res else None


# ────────────────── ХЕНДЛЕРИ ──────────────────
async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    kb = ReplyKeyboardMarkup(
        [["Запропонувати пост"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(
        "Тут формують, а не споживають.\n\nНадішли текст / фото / відео й обери категорію.",
        reply_markup=kb,
    )


async def handle_payload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приймаємо перше повідомлення від користувача, кешуємо й просимо категорію."""
    context.user_data["payload"] = update.message
    cat_kb = ReplyKeyboardMarkup(
        [[c] for c in CATEGORIES], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text("Оберіть категорію:", reply_markup=cat_kb)


async def set_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Користувач обрав категорію — формуємо чернетку й шлемо адмінові."""
    category = update.message.text
    payload = context.user_data.pop("payload", None)

    if category not in CATEGORIES or payload is None:
        return  # зайвий виклик

    draft_id = f"{payload.chat.id}_{payload.id}"
    draft = {
        "draft_id": draft_id,
        "user_id": payload.from_user.id,
        "status": DraftStatus.PENDING.name,
        "category": category,
        "date": datetime.utcnow().isoformat(timespec="seconds"),
    }
    save_draft(draft)

    # ————— шлемо адміну —————
    caption = (
        f"<b>Категорія:</b> {category}\n"
        f"<b>ID:</b> <code>{draft_id}</code>"
    )
    buttons = InlineKeyboardMarkup(
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
            chat_id=ADMIN_ID,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=buttons,
        )
    except Exception as err:  # noqa: BLE001
        logging.warning("Не вдалося скопіювати медіа для адміна: %s", err)
        await context.bot.send_message(
            chat_id=ADMIN_ID, text=f"{caption}\n\n[Медіа недоступне]"
        )

    await payload.reply_text(
        "Дякую! Чернетка передана модератору.",
        reply_markup=ReplyKeyboardRemove(),
    )


# ────────────────── МОДЕРАЦІЯ ──────────────────
async def cb_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.callback_query.answer("Ти не адміністратор 😉", show_alert=True)
        return

    action, draft_id = update.callback_query.data.split(":")
    draft = get_draft(draft_id)
    if not draft:
        await update.callback_query.answer("Чернетку не знайдено", show_alert=True)
        return

    async def notify(text: str) -> None:
        try:
            await context.bot.send_message(draft["user_id"], text)
        except Exception as e:  # noqa: BLE001
            logging.warning("Не вдалося повідомити користувача: %s", e)

    if action == "approve":
        draft["status"] = DraftStatus.APPROVED.name
        save_draft(draft)
        await notify("✅ Ваш допис схвалено й буде опубліковано.")
        await update.callback_query.edit_message_reply_markup(None)

    elif action == "reject":
        draft["status"] = DraftStatus.REJECTED.name
        save_draft(draft)
        await notify("❌ Ваш допис не пройшов модерацію.")
        await update.callback_query.edit_message_reply_markup(None)

    elif action == "edit":
        draft["status"] = DraftStatus.NEED_EDIT.name
        save_draft(draft)
        context.user_data["edit_draft"] = draft_id
        await update.callback_query.message.reply_text(
            "Напишіть, що потрібно підправити:",
            reply_markup=ReplyKeyboardRemove(),
        )
        await update.callback_query.answer()


async def admin_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    draft_id = context.user_data.pop("edit_draft", None)
    if not draft_id or update.effective_user.id != ADMIN_ID:
        return

    draft = get_draft(draft_id)
    if not draft:
        return

    comment = update.message.text
    await context.bot.send_message(
        chat_id=draft["user_id"],
        text=(
            "✏️ Ваш допис потребує правок:\n\n"
            f"{comment}\n\n"
            "Надішліть нову версію у відповідь."
        ),
    )
    await update.message.reply_text("Коментар відправлено автору.")


# ────────────────── MAIN ──────────────────
def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    )

    app = Application.builder().token(BOT_TOKEN).build()

    # команда старт
    app.add_handler(CommandHandler("start", cmd_start))

    # крок 1 — користувач надсилає контент
    app.add_handler(
        MessageHandler(
            filters.ALL
            & ~filters.COMMAND
            & ~filters.Regex(f"^({'|'.join(CATEGORIES)})$"),
            handle_payload,
        )
    )

    # крок 2 — вибір категорії
    app.add_handler(
        MessageHandler(filters.Regex(f"^({'|'.join(CATEGORIES)})$"), set_category)
    )

    # кнопки модерації
    app.add_handler(CallbackQueryHandler(cb_moderation))

    # текст-роз'яснення від адміна після ✏️
    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID), admin_comment))

    logging.info("Bot starting…")
    app.run_polling(stop_signals=None)  # Railway kill → процес завершується сам


if __name__ == "__main__":
    main()