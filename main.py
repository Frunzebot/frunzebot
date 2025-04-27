from __future__ import annotations
import logging, os, time, re
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
    CallbackQueryHandler, ContextTypes, ConversationHandler,
    filters, JobQueue
)

# ─────── конфіг ───────
BOT_TOKEN  = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID   = int(os.getenv("ADMIN_ID", "0").strip() or 0)
CHANNEL_ID = "@frunze_pro"
if not BOT_TOKEN or ADMIN_ID == 0:
    raise RuntimeError("BOT_TOKEN і ADMIN_ID обов’язкові!")

# ─────── меню ───────
MODE_POST    = "Запропонувати пост"
MODE_NEWS    = "Поділитись новиною"
MODE_ANON    = "Анонімний інсайд"
MODE_SUPPORT = "Підтримати автора"
MENU_BTNS = (MODE_POST, MODE_NEWS, MODE_ANON, MODE_SUPPORT)

MAIN_KB = ReplyKeyboardMarkup(
    [[MODE_POST, MODE_NEWS],
     [MODE_ANON, MODE_SUPPORT]],
    resize_keyboard=True,
    is_persistent=True          # ← не ховається
)

CATEGORIES = ("Інформаційна отрута", "Суспільні питання", "Я і моя філософія")

class Status(Enum):
    PENDING = auto(); NEED_EDIT = auto()
    APPROVED = auto(); REJECTED = auto(); EXPIRED = auto()

db = TinyDB("frunze_drafts.json"); Q = Query()
save = lambda d: db.upsert(d, Q.draft_id == d["draft_id"])
get  = lambda i: (db.search(Q.draft_id == i) or [None])[0]
now_iso = lambda: datetime.utcnow().isoformat(timespec="seconds")

# ─────── Conversation states ───────
SELECT_MODE, WAIT_CONTENT, WAIT_CATEGORY = range(3)

# util: показати меню
async def send_menu(chat_id, bot):
    await bot.send_message(chat_id, "Обери тип допису:", reply_markup=MAIN_KB)

# ─────── кроки користувача ───────
async def cmd_start(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text(
        "Тут формують, а не споживають.", reply_markup=MAIN_KB)
    return SELECT_MODE

async def select_mode(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mode = u.message.text
    if mode not in MENU_BTNS:
        return SELECT_MODE
    if mode == MODE_SUPPORT:
        await u.message.reply_text("👉 https://buymeacoffee.com/...  (підтримати автора)")
        await send_menu(u.effective_chat.id, ctx.bot)
        return SELECT_MODE
    ctx.user_data["mode"] = mode
    prompt = {
        MODE_POST: "Надішли текст / фото / відео.",
        MODE_NEWS: "Надішли посилання на новину.",
        MODE_ANON: "Надішли інсайд (без збереження даних)."
    }[mode]
    await u.message.reply_text(prompt, reply_markup=ReplyKeyboardRemove())
    return WAIT_CONTENT

async def got_content(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # валідатор лінку
    if ctx.user_data.get("mode") == MODE_NEWS:
        if not re.match(r"https?://", u.message.text or ""):
            await u.message.reply_text("Це не схоже на URL. Спробуй ще раз.")
            return WAIT_CONTENT
    ctx.user_data["payload"] = u.message
    kb = ReplyKeyboardMarkup([[c] for c in CATEGORIES],
                             resize_keyboard=True, one_time_keyboard=True)
    await u.message.reply_text("Оберіть категорію:", reply_markup=kb)
    return WAIT_CATEGORY

async def choose_category(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cat = u.message.text
    if cat not in CATEGORIES:
        return WAIT_CATEGORY
    payload = ctx.user_data.pop("payload")
    mode    = ctx.user_data.pop("mode")
    did = f"{payload.chat.id}_{payload.id}"
    save(dict(
        draft_id=did, user_id=payload.from_user.id, mode=mode,
        status=Status.PENDING.name, category=cat, date=now_iso(),
        expire_at=(datetime.utcnow()+timedelta(minutes=30)).timestamp()
    ))
    caption = f"<b>Категорія:</b> {cat}\n<b>ID:</b> <code>{did}</code>"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅",callback_data=f"approve:{did}"),
                                InlineKeyboardButton("✏️",callback_data=f"edit:{did}"),
                                InlineKeyboardButton("❌",callback_data=f"reject:{did}")]])
    try: await payload.copy(ADMIN_ID, caption=caption, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception: await ctx.bot.send_message(ADMIN_ID, text=f"{caption}\n\n[Медіа/посилання недоступне]")
    await payload.reply_text("Дякую! Чернетка передана модератору.", reply_markup=MAIN_KB)
    return SELECT_MODE   # повертаємось одразу до вибору типу

async def cancel(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("Скасовано.", reply_markup=MAIN_KB)
    ctx.user_data.clear()
    return SELECT_MODE

# ─────── модерація ───────
async def mod_cb(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if u.effective_user.id != ADMIN_ID:
        await u.callback_query.answer("Недостатньо прав", show_alert=True); return
    act,did = u.callback_query.data.split(":"); d=get(did)
    if not d: 
        await u.callback_query.answer("Чернетку не знайдено", show_alert=True); return
    async def ping(txt):
        try: await ctx.bot.send_message(d["user_id"], txt, reply_markup=MAIN_KB)
        except Exception: pass
    if act=="approve":
        d["status"]=Status.APPROVED.name; save(d)
        await ping("✅ Ваш допис схвалено й буде опубліковано.")
        try: await ctx.bot.forward_message(CHANNEL_ID, d["user_id"], int(did.split("_")[1]))
        except Exception as e: logging.error("Publish fail: %s", e)
    elif act=="reject":
        d["status"]=Status.REJECTED.name; save(d)
        await ping("❌ Ваш допис не пройшов модерацію.")
    elif act=="edit":
        d["status"]=Status.NEED_EDIT.name; save(d)
        ctx.user_data["edit_draft"]=did
        await u.callback_query.message.reply_text("Напишіть, що потрібно підправити:")
    await u.callback_query.edit_message_reply_markup(None)

async def admin_comment(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    did=ctx.user_data.pop("edit_draft",None)
    if not did: return
    d=get(did)
    if d:
        await ctx.bot.send_message(
            d["user_id"],
            f"✏️ Ваш допис потребує правок:\n\n{u.message.text}\n\nНадішліть нову версію (30 хв).",
            reply_markup=MAIN_KB
        )
        await u.message.reply_text("Коментар надіслано.")

# ─────── авто-clean ───────
async def cleanup(ctx: ContextTypes.DEFAULT_TYPE):
    ts=time.time()
    for d in db:
        if d["status"]==Status.NEED_EDIT.name and d["expire_at"]<ts:
            d["status"]=Status.EXPIRED.name; save(d)
            try: await ctx.bot.send_message(d["user_id"],
                    "⏰ Час на правки минув. Заявка закрита.", reply_markup=MAIN_KB)
            except Exception: pass

# ─────── main ───────
def main():
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s")
    app = Application.builder().token(BOT_TOKEN).build()
    app.job_queue.run_repeating(cleanup, 300, first=300)

    conv=ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states = {
            SELECT_MODE:   [MessageHandler(filters.Regex(f"^({'|'.join(MENU_BTNS)})$"), select_mode)],
            WAIT_CONTENT:  [MessageHandler(filters.ALL & ~filters.COMMAND, got_content)],
            WAIT_CATEGORY: [MessageHandler(filters.Regex(f"^({'|'.join(CATEGORIES)})$"), choose_category)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True, per_chat=True, name="frunze_flow"
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(mod_cb))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID), admin_comment))

    logging.info("Bot started")
    app.run_polling(stop_signals=None)

if __name__=="__main__":
    main()