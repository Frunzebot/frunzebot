from __future__ import annotations
import os, re, time, logging, requests
from enum import Enum, auto
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from tinydb import TinyDB, Query
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ConversationHandler,
    MessageHandler, CallbackQueryHandler, ContextTypes,
    filters, JobQueue
)

# ─────── ENV ───────
BOT_TOKEN  = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID   = int(os.getenv("ADMIN_ID", "0").strip() or 0)
CHANNEL_ID = "@frunze_pro"
if not BOT_TOKEN or ADMIN_ID == 0:
    raise RuntimeError("У Variables обов’язково BOT_TOKEN та ADMIN_ID!")

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
    is_persistent=True
)

CATEGORIES = ("Інформаційна отрута", "Суспільні питання", "Я і моя філософія")

# ─────── база ───────
class St(Enum):
    PENDING = auto(); NEED_EDIT = auto()
    APPROVED = auto(); REJECTED = auto(); EXPIRED = auto()

db = TinyDB("frunze_drafts.json"); Q = Query()
save = lambda d: db.upsert(d, Q.id == d["id"])
get  = lambda i: (db.search(Q.id == i) or [None])[0]

# ─────── утиліта OG-мета ───────
def og_meta(url: str) -> tuple[str, str]:
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        s = BeautifulSoup(r.text, "html.parser")
        ttl = (s.find("meta", property="og:title") or {}).get("content") \
           or (s.title.string if s.title else "")
        desc = (s.find("meta", property="og:description") or {}).get("content") or ""
        return ttl.strip(), desc.strip()
    except Exception:
        return "", ""

# ─────── Conversation states ───────
SELECT_MODE, WAIT_CONTENT, WAIT_CAT = range(3)

async def send_menu(chat_id, bot):
    await bot.send_message(chat_id, "Обери тип допису:", reply_markup=MAIN_KB)

# ─────── /start ───────
async def start(upd: Update, _):
    await upd.message.reply_text("Тут формують, а не споживають.", reply_markup=MAIN_KB)
    return SELECT_MODE

# ─────── вибір режиму ───────
async def pick_mode(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m = upd.message.text
    if m not in MENU_BTNS:
        return SELECT_MODE
    if m == MODE_SUPPORT:
        await upd.message.reply_text("👉 https://buymeacoffee.com/...  (підтримати автора)")
        await send_menu(upd.effective_chat.id, ctx.bot); return SELECT_MODE
    ctx.user_data["mode"] = m
    prompt = {MODE_POST:"Надішли текст / фото / відео.",
              MODE_NEWS:"Надішли посилання на новину.",
              MODE_ANON:"Надішли інсайд (без збереження даних)."}[m]
    await upd.message.reply_text(prompt, reply_markup=ReplyKeyboardRemove())
    return WAIT_CONTENT

# ─────── контент ───────
async def got_content(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mode = ctx.user_data["mode"]
    if mode == MODE_NEWS:
        url = upd.message.text or ""
        if not re.match(r"https?://", url):
            await upd.message.reply_text("Це не схоже на URL. Спробуй ще раз.")
            return WAIT_CONTENT
        title, desc = og_meta(url)
        ctx.user_data["meta"] = dict(url=url, title=title, desc=desc)
    ctx.user_data["payload"] = upd.message
    kb = ReplyKeyboardMarkup([[c] for c in CATEGORIES],
                             resize_keyboard=True, one_time_keyboard=True)
    await upd.message.reply_text("Оберіть категорію:", reply_markup=kb)
    return WAIT_CAT

# ─────── категорія → чернетка ───────
async def choose_cat(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cat = upd.message.text
    if cat not in CATEGORIES: return WAIT_CAT
    payload, mode = ctx.user_data.pop("payload"), ctx.user_data.pop("mode")
    meta = ctx.user_data.pop("meta", {})
    tag = "Фрунзе" if payload.from_user.id == ADMIN_ID else "Жолудевий вкид від спільноти"

    if mode == MODE_NEWS:
        url, title, desc = meta["url"], meta["title"] or "Без заголовка", meta["desc"]
        pub_text = (f"📰 <b>{tag}</b>\n<b>{title}</b>\n{desc}\n\n"
                    f"<a href=\"{url}\">Читати на сайті</a>")
    else:
        pub_text = f"<b>{tag}</b>"

    did = f"{payload.chat.id}_{payload.id}"
    draft = dict(id=did, uid=payload.from_user.id, mode=mode,
                 cat=cat, status=St.PENDING.name, pub=pub_text,
                 exp=(time.time()+1800))
    save(draft)

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅",f"approve:{did}"),
                                InlineKeyboardButton("✏️",f"edit:{did}"),
                                InlineKeyboardButton("❌",f"reject:{did}")]])
    if mode == MODE_NEWS:
        await ctx.bot.send_message(ADMIN_ID, pub_text,
            parse_mode=ParseMode.HTML, reply_markup=kb,
            disable_web_page_preview=False)
    else:
        try:
            await payload.copy(ADMIN_ID,
                caption=f"{pub_text}\n\n<b>Категорія:</b> {cat}\n<b>ID:</b> <code>{did}</code>",
                parse_mode=ParseMode.HTML, reply_markup=kb)
        except Exception:
            await ctx.bot.send_message(ADMIN_ID,
                f"{pub_text}\n\n<b>Категорія:</b> {cat}\n<b>ID:</b> <code>{did}</code>\n\n[Медіа недоступне]",
                parse_mode=ParseMode.HTML, reply_markup=kb)

    await payload.reply_text("Дякую! Чернетка передана модератору.", reply_markup=MAIN_KB)
    return SELECT_MODE

async def cancel(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await upd.message.reply_text("Скасовано.", reply_markup=MAIN_KB)
    return SELECT_MODE

# ─────── модерація ───────
async def cb_mod(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if upd.effective_user.id != ADMIN_ID:
        await upd.callback_query.answer("Недостатньо прав", show_alert=True); return
    act,did = upd.callback_query.data.split(":"); d = get(did)
    if not d: 
        await upd.callback_query.answer("Чернетку не знайдено", show_alert=True); return

    async def ping(msg):
        try: await ctx.bot.send_message(d["uid"], msg, reply_markup=MAIN_KB)
        except Exception: pass

    if act=="approve":
        d["status"]=St.APPROVED.name; save(d)
        await ping("✅ Ваш допис схвалено й буде опубліковано.")
        if d["mode"]==MODE_NEWS:
            await ctx.bot.send_message(CHANNEL_ID, d["pub"],
                parse_mode=ParseMode.HTML, disable_web_page_preview=False)
        else:
            uid,msg_id = d["id"].split("_")
            await ctx.bot.forward_message(CHANNEL_ID, int(uid), int(msg_id))
    elif act=="reject":
        d["status"]=St.REJECTED.name; save(d)
        await ping("❌ Ваш допис не пройшов модерацію.")
    elif act=="edit":
        d["status"]=St.NEED_EDIT.name; save(d)
        ctx.user_data["edit"]=did
        await upd.callback_query.message.reply_text("Напишіть, що потрібно підправити:")
    await upd.callback_query.edit_message_reply_markup(None)

async def admin_com(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    did = ctx.user_data.pop("edit",None)
    if not did: return
    d=get(did)
    if d:
        await ctx.bot.send_message(d["uid"],
            f"✏️ Ваш допис потребує правок:\n\n{upd.message.text}\n\nНадішліть нову версію (30 хв).",
            reply_markup=MAIN_KB)
        await upd.message.reply_text("Коментар надіслано.")

# ─────── авто-clean ───────
async def clean(ctx: ContextTypes.DEFAULT_TYPE):
    ts=time.time()
    for d in db:
        if d["status"]==St.NEED_EDIT.name and d["exp"]<ts:
            d["status"]=St.EXPIRED.name; save(d)
            try: await ctx.bot.send_message(d["uid"],
                    "⏰ Час на правки минув. Заявка закрита.", reply_markup=MAIN_KB)
            except Exception: pass

# ─────── main ───────
def main():
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s")
    app = Application.builder().token(BOT_TOKEN).build()
    app.job_queue.run_repeating(clean, 300, first=300)

    flow = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_MODE: [MessageHandler(filters.Regex(f"^({'|'.join(MENU_BTNS)})$"), pick_mode)],
            WAIT_CONTENT:[MessageHandler(filters.ALL & ~filters.COMMAND, got_content)],
            WAIT_CAT:    [MessageHandler(filters.Regex(f"^({'|'.join(CATEGORIES)})$"), choose_cat)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True, per_chat=True, name="frunze_flow"
    )

    app.add_handler(flow)
    app.add_handler(CallbackQueryHandler(cb_mod))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID), admin_com))

    logging.info("Bot started"); app.run_polling(stop_signals=None)

if __name__=="__main__":
    main()