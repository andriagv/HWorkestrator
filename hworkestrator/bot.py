"""Telegram bot: subject -> skill -> week -> (generate) -> preview -> ✅ upload."""
import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, filters

from . import pipeline
from .config import settings
from .registry import SKILLS, SUBJECTS
from .weeks import int_to_roman

log = logging.getLogger("hworkestrator")


def owner_only(fn):
    """Callback queries cannot be filtered by user in PTB, so check explicitly."""
    async def wrapper(update: Update, ctx):
        user = update.effective_user
        if user is None or user.id != settings.owner_id:
            return
        return await fn(update, ctx)
    return wrapper


def kb(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=d)] for t, d in rows])


def grid(buttons, per_row=4):
    rows = [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=d) for t, d in r] for r in rows])


@owner_only
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    rows = [(s["title"], f"subj:{k}") for k, s in SUBJECTS.items()]
    await update.effective_message.reply_text("აირჩიე საგანი:", reply_markup=kb(rows))


async def show_weeks(msg, subject_key):
    """Edit `msg` into the week picker for the subject."""
    title = SUBJECTS[subject_key]["title"]
    try:
        weeks = await asyncio.to_thread(pipeline.list_weeks, subject_key)
    except Exception as e:
        log.exception("list_weeks failed")
        return await msg.edit_text(f"❌ {e}\n\n/start")
    if not weeks:
        return await msg.edit_text(f"{title}\nკვირები ვერ ვიპოვე.\n\n/start")
    buttons = [(int_to_roman(w), f"wk:{w}") for w in weeks]
    markup = grid(buttons + [("⬅️ საგნები", "home")], per_row=4)
    await msg.edit_text(f"{title}\nაირჩიე კვირა:", reply_markup=markup)


@owner_only
async def on_subject(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data["subject"] = q.data.split(":", 1)[1]
    await q.edit_message_text("⏳ ვტვირთავ კვირებს…")
    await show_weeks(q.message, ctx.user_data["subject"])


@owner_only
async def on_home(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ctx.user_data.clear()
    rows = [(s["title"], f"subj:{k}") for k, s in SUBJECTS.items()]
    await q.edit_message_text("აირჩიე საგანი:", reply_markup=kb(rows))


@owner_only
async def on_week(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    subject = ctx.user_data.get("subject")
    if not subject:
        return await q.edit_message_text("დაწერე /start")
    week = int(q.data.split(":", 1)[1])
    ctx.user_data["week"] = week
    await q.edit_message_text(f"⏳ ვამოწმებ {int_to_roman(week)} კვირას…")
    try:
        ov = await asyncio.to_thread(pipeline.overview, subject, week)
    except Exception as e:
        log.exception("overview failed")
        return await q.edit_message_text(f"❌ {e}\n\n/start")
    await q.edit_message_text(f"{ov.title}\n\n{ov.text}")
    for f in ov.files:
        with open(f, "rb") as fh:
            await q.message.reply_document(fh, filename=f.name)
    if not ov.has_content:
        return await q.message.reply_text(
            "დავალება ჯერ არ არის.", reply_markup=kb([("⬅️ კვირები", f"subj:{subject}")]))
    rows = [(label, f"skill:{k}") for k, label in SKILLS.items()]
    rows.append(("⬅️ კვირები", f"subj:{subject}"))
    await q.message.reply_text("რომელი skill გამოვიყენო?", reply_markup=kb(rows))


@owner_only
async def on_skill(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    subject, week = ctx.user_data.get("subject"), ctx.user_data.get("week")
    if not subject or not week:
        return await q.edit_message_text("დაწერე /start")
    skill = q.data.split(":", 1)[1]
    await q.edit_message_text("⏳ ვაგენერირებ…")
    try:
        job = await asyncio.to_thread(pipeline.prepare, subject, skill, week)
    except Exception as e:  # show the reason, keep the bot alive
        log.exception("prepare failed")
        return await q.edit_message_text(
            f"❌ {e}", reply_markup=kb([("⬅️ კვირები", f"subj:{subject}")]))
    ctx.user_data["job"] = job
    await q.edit_message_text(f"📄 მზადაა ({job.info.splitlines()[0]})")
    for f in [job.upload_file, *job.extra_files]:
        with open(f, "rb") as fh:
            await q.message.reply_document(fh, filename=f.name)
    existing = job.target.get("existing")
    warn = (f"\n⚠️ ამჟამად უკვე ატვირთულია: {', '.join(existing)} — ახალი ფაილი ჩაანაცვლებს."
            if existing else "")
    await q.message.reply_text(
        "ატვირთვა დავალების ადგილას?" + warn,
        reply_markup=kb([("✅ ატვირთე", "ok"), ("❌ გაუქმება", "no")]))


@owner_only
async def on_decision(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    job = ctx.user_data.get("job")
    if q.data == "no" or not job:
        ctx.user_data.clear()
        return await q.edit_message_text("გაუქმდა. /start")
    await q.edit_message_text("⏳ ვტვირთავ…")
    try:
        result = await asyncio.to_thread(pipeline.submit, job)
    except Exception as e:
        log.exception("submit failed")
        return await q.edit_message_text(f"❌ ატვირთვა ვერ მოხერხდა: {e}")
    ctx.user_data.clear()
    await q.edit_message_text(result + "\n\n/start")


def build_app():
    if not settings.telegram_token or not settings.owner_id:
        raise SystemExit("TELEGRAM_BOT_TOKEN და OWNER_TELEGRAM_ID აუცილებელია")
    app = Application.builder().token(settings.telegram_token).build()
    owner = filters.User(user_id=settings.owner_id)      # nobody else can use the bot
    app.add_handler(CommandHandler(["start", "new"], start, filters=owner))
    app.add_handler(CallbackQueryHandler(on_subject, pattern=r"^subj:"))
    app.add_handler(CallbackQueryHandler(on_home, pattern=r"^home$"))
    app.add_handler(CallbackQueryHandler(on_week, pattern=r"^wk:\d+$"))
    app.add_handler(CallbackQueryHandler(on_skill, pattern=r"^skill:"))
    app.add_handler(CallbackQueryHandler(on_decision, pattern=r"^(ok|no)$"))
    return app


def main():
    logging.basicConfig(level=logging.INFO)
    app = build_app()
    if settings.mode == "webhook":
        app.run_webhook(listen="0.0.0.0", port=settings.port, url_path=settings.telegram_token,
                        webhook_url=f"{settings.webhook_url}/{settings.telegram_token}")
    else:
        app.run_polling()


if __name__ == "__main__":
    main()
