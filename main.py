from __future__ import annotations
import logging, os, time
from enum import Enum, auto
from datetime import datetime, timedelta

from tinydb import TinyDB, Query
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, JobQueue     # ← JobQueue імпортовано
)

# ───── конфіг ─────
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID  = int(os.getenv("ADMIN_ID", "0").strip() or 0)
CHANNEL_ID = "@frunze_pro"

if not BOT_TOKEN or ADMIN_ID == 0:
    raise RuntimeError("Задай BOT_TOKEN і ADMIN_ID у Variables!")

# ───── дані ─────
class Status(Enum):
    PENDING = auto(); NEED_EDIT = auto()
    APPROVED = auto(); REJECTED = auto(); EXPIRED = auto()

CATEGORIES = ("Інформаційна отрута", "Суспільні питання", "Я і моя філософія")

db = TinyDB("frunze_drafts.json"); DQ = Query()
save = lambda d: db.upsert(d, DQ.draft_id == d["draft_id"])
get  = lambda i: (db.search(DQ.draft_id == i) or [None])[0]
now_iso = lambda: datetime.utcnow().isoformat(timespec="seconds")

# ───── хендлери ─────
async def cmd_start(u: Update,_):
    kb = ReplyKeyboardMarkup([["Запропонувати пост","Поділитись новиною"],
                              ["Анонімний інсайд","Підтримати автора"]],
                              resize_keyboard=True)
    await u.message.reply_text(
        "Тут формують, а не споживають.\n\n"
        "Надішли текст / фото / відео й обери категорію.", reply_markup=kb)

async def handle_payload(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["payload"] = u.message
    await u.message.reply_text("Оберіть категорію:",
        reply_markup=ReplyKeyboardMarkup([[x] for x in CATEGORIES],
                      resize_keyboard=True, one_time_keyboard=True))

async def choose_category(u: Update, c: ContextTypes.DEFAULT_TYPE):
    cat, payload = u.message.text, c.user_data.pop("payload", None)
    if cat not in CATEGORIES or payload is None: return
    did = f"{payload.chat.id}_{payload.id}"
    save(dict(draft_id=did, user_id=payload.from_user.id,
              status=Status.PENDING.name, category=cat, date=now_iso(),
              expire_at=(datetime.utcnow()+timedelta(minutes=30)).timestamp()))
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅",callback_data=f"approve:{did}"),
                                InlineKeyboardButton("✏️",callback_data=f"edit:{did}"),
                                InlineKeyboardButton("❌",callback_data=f"reject:{did}")]])
    caption = f"<b>Категорія:</b> {cat}\n<b>ID:</b> <code>{did}</code>"
    try:
        await payload.copy(chat_id=ADMIN_ID, caption=caption, reply_markup=kb,
                           parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.warning("Copy fail: %s", e)
        await c.bot.send_message(ADMIN_ID, text=f"{caption}\n\n[Медіа недоступне]")
    await payload.reply_text("Дякую! Чернетка передана модератору.",
                             reply_markup=ReplyKeyboardRemove())

async def mod_cb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.effective_user.id != ADMIN_ID:
        await u.callback_query.answer("Недостатньо прав", show_alert=True); return
    act,did = u.callback_query.data.split(":"); d=get(did)
    if not d: await u.callback_query.answer("Чернетку не знайдено", show_alert=True); return
    async def ping(t): 
        try: await c.bot.send_message(d["user_id"],t)
        except Exception: pass
    if act=="approve":
        d["status"]=Status.APPROVED.name; save(d)
        await ping("✅ Ваш допис схвалено й буде опубліковано.")
        try: await c.bot.forward_message(CHANNEL_ID, d["user_id"], int(did.split("_")[1]))
        except Exception as e: logging.error("Publish fail: %s",e)
        await u.callback_query.edit_message_reply_markup(None)
    elif act=="reject":
        d["status"]=Status.REJECTED.name; save(d)
        await ping("❌ Ваш допис не пройшов модерацію.")
        await u.callback_query.edit_message_reply_markup(None)
    elif act=="edit":
        d["status"]=Status.NEED_EDIT.name; save(d)
        c.user_data["edit_draft"]=did
        await u.callback_query.message.reply_text(
            "Напишіть, що потрібно підправити:", reply_markup=ReplyKeyboardRemove())
        await u.callback_query.answer()

async def admin_comment(u: Update, c: ContextTypes.DEFAULT_TYPE):
    did=c.user_data.pop("edit_draft",None)
    if not did: return
    d=get(did);  # може бути None, але малоймовірно
    if d:
        await c.bot.send_message(d["user_id"],
            f"✏️ Ваш допис потребує правок:\n\n{u.message.text}\n\nНадішліть нову версію у відповідь (у вас 30 хв).")
        await u.message.reply_text("Коментар надіслано.")

# ───── clean-up ─────
async def cleanup(ctx: ContextTypes.DEFAULT_TYPE):
    ts=time.time()
    for d in db:
        if d["status"]==Status.NEED_EDIT.name and d["expire_at"]<ts:
            d["status"]=Status.EXPIRED.name; save(d)
            try: await ctx.bot.send_message(d["user_id"],
                    "⏰ Час на правки минув. Заявка закрита.")
            except Exception: pass

def main():
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s")
    app=Application.builder().token(BOT_TOKEN).build()
    app.job_queue.run_repeating(cleanup, 300, first=300)

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID), admin_comment))
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND
        & ~filters.Regex(f"^({'|'.join(CATEGORIES)})$") & ~filters.User(ADMIN_ID),
        handle_payload))
    app.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(CATEGORIES)})$"), choose_category))
    app.add_handler(CallbackQueryHandler(mod_cb))

    logging.info("Bot starting…")
    app.run_polling(stop_signals=None)

if __name__=="__main__":
    main()