"""Telegram bot: subject -> skill -> week -> (generate) -> preview -> ✅ upload."""
import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, filters

from . import pipeline, pricing
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


def skill_rows(subject):
    rows = [(label, f"skill:{k}") for k, label in SKILLS.items()]
    rows.append(("⬅️ კვირები", f"subj:{subject}"))
    return rows


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
    ctx.user_data["ov"] = ov
    ctx.user_data.pop("chosen", None)
    await q.edit_message_text(f"{ov.title}\n\n{ov.text}")
    for f in ov.files:
        with open(f, "rb") as fh:
            await q.message.reply_document(fh, filename=f.name)
    if not ov.has_content:
        return await q.message.reply_text(
            "დავალება ჯერ არ არის.", reply_markup=kb([("⬅️ კვირები", f"subj:{subject}")]))
    if len(ov.files) > 1:        # several candidates -> let the user pick the source
        rows = [(f"📄 {f.name}", f"src:{i}") for i, f in enumerate(ov.files)]
        rows.append(("📚 ყველა ფაილი ერთად", "src:all"))
        return await q.message.reply_text("რომელი ფაილია დავალების წყარო?", reply_markup=kb(rows))
    ctx.user_data["chosen"] = list(ov.files)
    await q.message.reply_text("რომელი skill გამოვიყენო?", reply_markup=kb(skill_rows(subject)))


@owner_only
async def on_source(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    ov = ctx.user_data.get("ov")
    if not ov:
        return await q.edit_message_text("დაწერე /start")
    pick = q.data.split(":", 1)[1]
    chosen = list(ov.files) if pick == "all" else [ov.files[int(pick)]]
    ctx.user_data["chosen"] = chosen
    names = ", ".join(f.name for f in chosen)
    await q.edit_message_text(f"წყარო: {names}\n\nრომელი skill გამოვიყენო?",
                              reply_markup=kb(skill_rows(ctx.user_data["subject"])))


@owner_only
async def on_skill(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    subject, ov = ctx.user_data.get("subject"), ctx.user_data.get("ov")
    if not subject or not ov:
        return await q.edit_message_text("დაწერე /start")
    skill = q.data.split(":", 1)[1]
    ctx.user_data["skill"] = skill
    if skill not in pricing.LLM_SKILLS:                 # cppwork: no model, no cost
        return await generate(q, ctx, skill)
    await q.edit_message_text("⏳ ფასს ვითვლი (Haiku 5.5)…")
    try:
        est, note = await asyncio.to_thread(pipeline.estimate, ov, skill, ctx.user_data.get("chosen"))
    except Exception as e:
        log.exception("estimate failed")
        return await q.edit_message_text(f"❌ {e}\n/start")
    default_id = settings.anthropic_model
    rows = [(f"{pricing.MODELS[k]['emoji']} {name} — ≈ {pricing.fmt_usd(usd)}"
             + (" ⭐" if pricing.MODELS[k]["id"] == default_id else ""), f"mdl:{k}") for k, name, usd in est]
    rows.append(("⬅️ უკან", f"subj:{subject}"))
    await q.edit_message_text(
        "რომელი მოდელით დავწერო?\n≈ სავარაუდო ფასი ამ დავალებაზე; ზუსტს შესრულების შემდეგ დაგიწერ "
        f"(შეცდომის გასწორებისას შეიძლება მეტი გამოვიდეს).\n{note}", reply_markup=kb(rows))


@owner_only
async def on_model(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    skill = ctx.user_data.get("skill")
    if not skill or not ctx.user_data.get("ov"):
        return await q.edit_message_text("დაწერე /start")
    await generate(q, ctx, skill, q.data.split(":", 1)[1])




async def generate(q, ctx, skill, model=None):
    """Run the skill (in a thread) and show the result; `q` is the callback query to edit."""
    subject, ov = ctx.user_data.get("subject"), ctx.user_data.get("ov")
    await q.edit_message_text("⏳ ვაგენერირებ…")
    try:
        job = await asyncio.to_thread(pipeline.prepare, ov, skill, ctx.user_data.get("chosen"), model)
    except Exception as e:  # show the reason, keep the bot alive
        log.exception("prepare failed")
        return await q.edit_message_text(
            f"❌ {e}", reply_markup=kb([("⬅️ კვირები", f"subj:{subject}")]))
    ctx.user_data["job"] = job
    await q.edit_message_text(f"📄 მზადაა ({job.info.splitlines()[0]})\n{job.cost_note}")
    for f in [job.upload_file, *job.extra_files]:
        with open(f, "rb") as fh:
            await q.message.reply_document(fh, filename=f.name)
    targets = job.targets
    if not targets:
        return await q.message.reply_text("⚠️ ამ კვირაში დავალების ადგილი (assignment) არ არის — ატვირთვა შეუძლებელია.\n/start")
    lines = []
    for t in targets:
        ex = t.get("existing")
        lines.append(f"• {t.get('label', '')}" + (f" — უკვე ატვირთულია: {', '.join(ex)} (ჩაანაცვლებს)" if ex else " — ცარიელია"))
    if len(targets) == 1:
        rows = [("✅ ატვირთე", "ok:0"), ("❌ გაუქმება", "no")]
        text = "ატვირთვა დავალების ადგილას?\n" + "\n".join(lines)
    else:
        rows = [(f"✅ {t.get('label', i)}", f"ok:{i}") for i, t in enumerate(targets)] + [("❌ გაუქმება", "no")]
        text = "რომელ დავალებაში ავტვირთო?\n" + "\n".join(lines)
    await q.message.reply_text(text, reply_markup=kb(rows))


@owner_only
async def on_decision(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    job = ctx.user_data.get("job")
    if q.data == "no" or not job:
        ctx.user_data.clear()
        return await q.edit_message_text("გაუქმდა. /start")
    idx = int(q.data.split(":", 1)[1])
    if idx >= len(job.targets):
        return await q.edit_message_text("ატვირთვის ადგილი ვერ ვიპოვე. /start")
    job.target = job.targets[idx]
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
    builder = Application.builder().token(settings.telegram_token)
    if settings.telegram_api_base:                       # go through a proxy when Telegram is blocked
        builder = (builder.base_url(f"{settings.telegram_api_base}/bot")
                          .base_file_url(f"{settings.telegram_api_base}/file/bot"))
    app = builder.build()
    owner = filters.User(user_id=settings.owner_id)      # nobody else can use the bot
    app.add_handler(CommandHandler(["start", "new"], start, filters=owner))
    app.add_handler(CallbackQueryHandler(on_subject, pattern=r"^subj:"))
    app.add_handler(CallbackQueryHandler(on_home, pattern=r"^home$"))
    app.add_handler(CallbackQueryHandler(on_week, pattern=r"^wk:\d+$"))
    app.add_handler(CallbackQueryHandler(on_source, pattern=r"^src:(\d+|all)$"))
    app.add_handler(CallbackQueryHandler(on_skill, pattern=r"^skill:"))
    app.add_handler(CallbackQueryHandler(on_model, pattern=r"^mdl:\w+$"))
    app.add_handler(CallbackQueryHandler(on_decision, pattern=r"^(ok:\d+|no)$"))
    return app


def main():
    logging.basicConfig(level=logging.INFO)
    app = build_app()
    if settings.health_port:
        from . import health
        health.start(settings.health_port)
        log.info("health endpoint on port %s", settings.health_port)
    if settings.mode == "webhook":
        app.run_webhook(listen="0.0.0.0", port=settings.port, url_path=settings.telegram_token,
                        webhook_url=f"{settings.webhook_url}/{settings.telegram_token}")
    else:
        app.run_polling()


if __name__ == "__main__":
    main()
