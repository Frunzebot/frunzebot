"""
FRUNZEBOT – MVP ядро (Phase 1)
──────────────────────────────
• користувач надсилає текст / фото / відео
• бот просить вибрати категорію
• адмін отримує чернетку з кнопками ✅ ✏️ ❌
• бот шле автору: «схвалено / правки / відхилено»
"""

from __future__ import annotations
import logging, os
from enum import Enum, auto
from datetime import datetime
from tinydb import TinyDB, Query
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ─────── конфіг ───────
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID  = int(os.getenv("ADMIN_ID", "0").strip() or 0)
if not BOT_TOKEN or ADMIN_ID == 0:
    raise RuntimeError("Задай BOT_TOKEN і ADMIN_ID у Variables на Railway!")

# ─────── дані ───────
class DraftStatus(Enum):
    PENDING   = auto()
    NEED_EDIT = auto()
    APPROVED  = auto()
    REJECTED  = auto()

CATEGORIES = (
    "Інформаційна отрута",
    "Суспільні питання",
    "Я і моя філософія",
)

db = TinyDB("frunze_drafts.json")
DQ = Query()

def save_draft(d: dict): db.upsert(d, DQ.draft_id == d["draft_id"])
def get_draft(did: str):  r = db.search(DQ.draft_id == did); return r[0] if r else None

# ─────── хендлери ───────
async def cmd_start(update: Update, _):
    kb = ReplyKeyboardMarkup([["Запропонувати пост"]],
                              resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "Тут формують, а не споживають.\n\n"
        "Надішли текст / фото / відео й обери категорію.",
        reply_markup=kb
    )

async def handle_payload(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Записуємо перше повідомлення й питаємо категорію."""
    ctx.user_data["payload"] = update.message
    cat_kb = ReplyKeyboardMarkup([[c] for c in CATEGORIES],
                                 resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Оберіть категорію:", reply_markup=cat_kb)

async def choose_category(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cat = update.message.text
    payload = ctx.user_data.pop("payload", None)
    if cat not in CATEGORIES or payload is None:
        return

    draft_id = f"{payload.chat.id}_{payload.id}"
    draft = dict(
        draft_id=draft_id, user_id=payload.from_user.id,
        status=DraftStatus.PENDING.name, category=cat,
        date=datetime.utcnow().isoformat(timespec="seconds")
    )
    save_draft(draft)

    caption = f"<b>Категорія:</b> {cat}\n<b>ID:</b> <code>{draft_id}</code>"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅", callback_data=f"approve:{draft_id}"),
        InlineKeyboardButton("✏️", callback_data=f"edit:{draft_id}"),
        InlineKeyboardButton("❌", callback_data=f"reject:{draft_id}")
    ]])

    try:
        await payload.copy(chat_id=ADMIN_ID, caption=caption,
                           reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception as err:
        logging.warning("Copy failed: %s", err)
        await ctx.bot.send_message(chat_id=ADMIN_ID,
                                   text=f"{caption}\n\n[Медіа недоступне]")

    await payload.reply_text("Дякую! Чернетка передана модератору.",
                             reply_markup=ReplyKeyboardRemove())

async def mod_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.callback_query.answer("Недостатньо прав", show_alert=True); return
    action, did = update.callback_query.data.split(":")
    draft = get_draft(did)
    if not draft:
        await update.callback_query.answer("Чернетку не знайдено", show_alert=True); return

    async def ping(txt): 
        try: await ctx.bot.send_message(draft["user_id"], txt)
        except Exception as e: logging.warning("Notify fail: %s", e)

    if action == "approve":
        draft["status"] = DraftStatus.APPROVED.name; save_draft(draft)
        await ping("✅ Ваш допис схвалено й буде опубліковано.")
        await update.callback_query.edit_message_reply_markup(None)

    elif action == "reject":
        draft["status"] = DraftStatus.REJECTED.name; save_draft(draft)
        await ping("❌ Ваш допис не пройшов модерацію.")
        await update.callback_query.edit_message_reply_markup(None)

    elif action == "edit":
        draft["status"] = DraftStatus.NEED_EDIT.name; save_draft(draft)
        ctx.user_data["edit_draft"] = did
        await update.callback_query.message.reply_text(
            "Напишіть, що потрібно підправити:", reply_markup=ReplyKeyboardRemove())
        await update.callback_query.answer()

async def admin_comment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    did = ctx.user_data.pop("edit_draft", None)
    if not did: return
    draft = get_draft(did)
    if not draft: return
    await ctx.bot.send_message(
        draft["user_id"],
        f"✏️ Ваш допис потребує правок:\n\n{update.message.text}\n\n"
        "Надішліть нову версію у відповідь."
    )
    await update.message.reply_text("Коментар надіслано.")

# ─────── запуск ───────
def main():
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s")

    app = Application.builder().token(BOT_TOKEN).build()

    # порядок важливий: спершу адмін-коментар, щоб не ловити ✏️ як новий допис
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID), admin_comment))
    app.add_handler(
        MessageHandler(
            filters.ALL
            & ~filters.COMMAND
            & ~filters.Regex(f"^({'|'.join(CATEGORIES)})$")
            & ~filters.User(ADMIN_ID),          # ← адмін НЕ тригерить payload
            handle_payload
        )
    )
    app.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(CATEGORIES)})$"), choose_category))
    app.add_handler(CallbackQueryHandler(mod_callback))

    logging.info("Bot starting…")
    app.run_polling(stop_signals=None)

if __name__ == "__main__":
    main()