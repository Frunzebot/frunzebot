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
    CallbackQueryHandler, ContextTypes, filters, JobQueue
)

# ──────── конфіг ────────
BOT_TOKEN  = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID   = int(os.getenv("ADMIN_ID", "0").strip() or 0)
CHANNEL_ID = "@frunze_pro"

if not BOT_TOKEN or ADMIN_ID == 0:
    raise RuntimeError("BOT_TOKEN та ADMIN_ID мають бути у Variables!")

MENU_POST      = "Запропонувати пост"
MENU_NEWS      = "Поділитись новиною"
MENU_ANON      = "Анонімний інсайд"
MENU_SUPPORT   = "Підтримати автора"
MENU_BTNS      = (MENU_POST, MENU_NEWS, MENU_ANON, MENU_SUPPORT)

CATEGORIES = ("Інформаційна отрута", "Суспільні питання", "Я і моя філософія")

class Status(Enum):
    PENDING = auto(); NEED_EDIT = auto(); APPROVED = auto()
    REJECTED = auto(); EXPIRED = auto()

db = TinyDB("frunze_drafts.json"); Q = Query()
save = lambda d: db.upsert(d, Q.draft_id == d["draft_id"])
get  = lambda i: (db.search(Q.draft_id == i) or [None])[0]
now_iso = lambda: datetime.utcnow().isoformat(timespec="seconds")

# ───────── команда /start ─────────
async def cmd_start(u: Update, _):
    kb = ReplyKeyboardMarkup(
        [[MENU_POST, MENU_NEWS],
         [MENU_ANON, MENU_SUPPORT]],
        resize_keyboard=True
    )
    await u.message.reply_text(
        "Тут формують, а не споживають.\n\n"
        "Обери тип допису в меню нижче.", reply_markup=kb
    )

# ───────── вибір режиму ─────────
async def choose_mode(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mode = u.message.text
    if mode not in MENU_BTNS:                # не наша кнопка — ігноруємо
        return
    ctx.user_data.clear()
    ctx.user_data["mode"] = mode
    if mode == MENU_SUPPORT:
        await u.message.reply_text("👉 https://buymeacoffee.com/...  (підтримати автора)")
        ctx.user_data.clear()
        return
    prompt = {
        MENU_POST:  "Надішли текст / фото / відео для публікації.",
        MENU_NEWS:  "Надішли посилання на новину.",
        MENU_ANON:  "Надішли інсайд (ми не зберігаємо твої дані)."
    }[mode]
    await u.message.reply_text(prompt, reply_markup=ReplyKeyboardRemove())

# ───────── прийом контенту ─────────
async def handle_content(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if "mode" not in ctx.user_data:          # користувач не вибрав тип
        return
    ctx.user_data["payload"] = u.message
    cat_kb = ReplyKeyboardMarkup([[c] for c in CATEGORIES],
                                 resize_keyboard=True, one_time_keyboard=True)
    await u.message.reply_text("Оберіть категорію:", reply_markup=cat_kb)

# ───────── вибір категорії ─────────
async def choose_category(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if "payload" not in ctx.user_data: return
    cat = u.message.text
    if cat not in CATEGORIES: return
    payload = ctx.user_data.pop("payload")
    mode    = ctx.user_data.pop("mode")
    did = f"{payload.chat.id}_{payload.id}"
    save(dict(
        draft_id=did, user_id=payload.from_user.id,
        status=Status.PENDING.name, category=cat, mode=mode,
        date=now_iso(), expire_at=(datetime.utcnow()+timedelta(minutes=30)).timestamp()
    ))
    caption = f"<b>Категорія:</b> {cat}\n<b>ID:</b> <code>{did}</code>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅",callback_data=f"approve:{did}"),
                                InlineKeyboardButton("✏️",callback_data=f"edit:{did}"),
                                InlineKeyboardButton("❌",callback_data=f"reject:{did}")]])
    try:
        await payload.copy(ADMIN_ID, caption=caption, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        await ctx.bot.send_message(ADMIN_ID, text=f"{caption}\n\n[Медіа/посилання недоступне]")
    await payload.reply_text("Дякую! Чернетка передана модератору.")

# ───────── модерація ─────────
async def mod_cb(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if u.effective_user.id != ADMIN_ID:
        await u.callback_query.answer("Недостатньо прав", show_alert=True); return
    act,did = u.callback_query.data.split(":"); d=get(did)
    if not d: await u.callback_query.answer("Чернетку не знайдено", show_alert=True); return
    async def ping(t): 
        try: await ctx.bot.send_message(d["user_id"], t)
        except Exception: pass
    if act=="approve":
        d["status"]=Status.APPROVED.name; save(d)
        await ping("✅ Ваш допис схвалено й буде опубліковано.")
        try: await ctx.bot.forward_message(CHANNEL_ID, d["user_id"], int(did.split("_")[1]))
        except Exception as e: logging.error("Publish fail: %s",e)
        await u.callback_query.edit_message_reply_markup(None)
    elif act=="reject":
        d["status"]=Status.REJECTED.name; save(d)
        await ping("❌ Ваш допис не пройшов модерацію.")
        await u.callback_query.edit_message_reply_markup(None)
    elif act=="edit":
        d["status"]=Status.NEED_EDIT.name; save(d)
        ctx.user_data["edit_draft"]=did
        await u.callback_query.message.reply_text("Напишіть, що потрібно підправити:")
        await u.callback_query.answer()

# ───────── коментар адміна ─────────
async def admin_comment(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    did=ctx.user_data.pop("edit_draft",None)
    if not did: return
    d=get(did)
    if d:
        await ctx.bot.send_message(d["user_id"],
            f"✏️ Ваш допис потребує правок:\n\n{u.message.text}\n\n"
            "Надішліть нову версію у відповідь (30 хв).")
        await u.message.reply_text("Коментар надіслано.")

# ───────── авто-чистильник ─────────
async def cleanup(ctx: ContextTypes.DEFAULT_TYPE):
    ts=time.time()
    for d in db:
        if d["status"]==Status.NEED_EDIT.name and d["expire_at"]<ts:
            d["status"]=Status.EXPIRED.name; save(d)
            try: await ctx.bot.send_message(d["user_id"],
                    "⏰ Час на правки минув. Заявка закрита.")
            except Exception: pass

# ───────── main ─────────
def main():
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s")
    app=Application.builder().token(BOT_TOKEN).build()
    app.job_queue.run_repeating(cleanup, 300, first=300)

    app.add_handler(CommandHandler("start", cmd_start))
    # порядок важливий
    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID), admin_comment))
    app.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(MENU_BTNS)})$"), choose_mode))
    app.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.TEXT)
        & ~filters.Regex(f"^({'|'.join(CATEGORIES)})$")
        & ~filters.User(ADMIN_ID), handle_content))
    app.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(CATEGORIES)})$"), choose_category))
    app.add_handler(CallbackQueryHandler(mod_cb))

    logging.info("Bot starting…")
    app.run_polling(stop_signals=None)

if __name__=="__main__":
    main()