"""
Morning Market Analyst — Telegram Bot
--------------------------------------
Commands:
  /analyze  — run a full morning briefing on demand
  /status   — show bot status + next scheduled run
  /help     — show available commands

Scheduler fires every weekday at the configured BRIEF_HOUR:BRIEF_MINUTE (default 6:30 AM PT).
"""

import os
import asyncio
import logging
from datetime import datetime
import pytz

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from analyst import run_morning_analysis_sync

# ── Config ─────────────────────────────────────────────────────────────────────

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID        = os.environ["CHAT_ID"]
BRIEF_HOUR     = int(os.getenv("BRIEF_HOUR", "6"))
BRIEF_MINUTE   = int(os.getenv("BRIEF_MINUTE", "30"))
TIMEZONE       = os.getenv("TIMEZONE", "America/Los_Angeles")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ── Progress ticker ────────────────────────────────────────────────────────────

PROGRESS_STEPS = [
    "🔍 Scanning premarket futures & VIX...",
    "📰 Pulling macro news & Fed calendar...",
    "🌊 Searching unusual options flow...",
    "📊 Analysing sector rotation...",
    "📈 Identifying top movers & catalysts...",
    "🧠 Scoring setups & building picks...",
    "✍️  Writing your briefing — almost done...",
]

async def progress_ticker(bot, chat_id: str, status_msg_id: int, stop_event: asyncio.Event):
    """Edit the status message every 15s with a progress update."""
    for step in PROGRESS_STEPS:
        if stop_event.is_set():
            return
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg_id,
                text=step
            )
        except Exception:
            pass
        await asyncio.sleep(15)
        if stop_event.is_set():
            return
    # If still running after all steps, keep showing last step
    while not stop_event.is_set():
        await asyncio.sleep(5)

# ── Core briefing sender ───────────────────────────────────────────────────────

async def send_briefing(app: Application, chat_id: str = None, scheduled: bool = False) -> None:
    """Generate and send the full market briefing with live progress updates."""
    chat_id = chat_id or CHAT_ID
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    # Only skip weekends for auto-scheduled runs, never for on-demand /analyze
    if scheduled and now.weekday() >= 5:
        log.info("Weekend — skipping scheduled briefing.")
        return

    log.info("Generating morning briefing...")

    # Send initial status message — we'll edit this as progress ticks
    status_msg = await app.bot.send_message(
        chat_id=chat_id,
        text="🔍 Starting market analysis..."
    )

    stop_event = asyncio.Event()

    # Start progress ticker in background
    ticker_task = asyncio.create_task(
        progress_ticker(app.bot, chat_id, status_msg.message_id, stop_event)
    )

    try:
        log.info("send_briefing: starting executor call")
        # Run the blocking Claude API call in a thread so the ticker keeps updating
        loop = asyncio.get_event_loop()
        briefing = await loop.run_in_executor(
            None, run_morning_analysis_sync
        )
        log.info(f"send_briefing: got briefing ({len(briefing)} chars)")

        # Stop the ticker
        stop_event.set()
        ticker_task.cancel()

        # Delete the progress message
        try:
            await app.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        except Exception:
            pass

        # Send the briefing in chunks (Telegram 4096 char limit)
        chunks = split_message(briefing, limit=4000)
        for i, chunk in enumerate(chunks):
            prefix = "" if i == 0 else "📄 _(continued)_\n\n"
            await app.bot.send_message(
                chat_id=chat_id,
                text=prefix + chunk,
                parse_mode="Markdown"
            )

    except Exception as e:
        stop_event.set()
        ticker_task.cancel()
        log.error(f"Briefing failed: {e}")
        try:
            await app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text=f"❌ Briefing failed: `{e}`",
                parse_mode="Markdown"
            )
        except Exception:
            await app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Briefing failed: `{e}`",
                parse_mode="Markdown"
            )


def split_message(text: str, limit: int = 4000) -> list[str]:
    """Split long message into chunks at paragraph boundaries."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for para in text.split("\n\n"):
        block = para + "\n\n"
        if len(current) + len(block) > limit:
            if current:
                chunks.append(current.strip())
            current = block
        else:
            current += block
    if current.strip():
        chunks.append(current.strip())
    return chunks

# ── Command handlers ───────────────────────────────────────────────────────────

async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_chat.id) != str(CHAT_ID):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    await send_briefing(ctx.application, chat_id=str(update.effective_chat.id), scheduled=False)


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_chat.id) != str(CHAT_ID):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    msg = (
        f"✅ *Market Bot is running*\n\n"
        f"🕐 Current time: `{now.strftime('%Y-%m-%d %H:%M %Z')}`\n"
        f"📅 Daily briefing: `{BRIEF_HOUR:02d}:{BRIEF_MINUTE:02d} {TIMEZONE}` (weekdays)\n"
        f"💬 Commands: /analyze · /status · /help"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = (
        "📈 *Morning Market Analyst Bot*\n\n"
        "/analyze — Run a full market briefing right now\n"
        "/status  — Show bot status and next scheduled run\n"
        "/help    — Show this message\n\n"
        "_Auto-briefings sent every weekday morning._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ── Scheduler + main ──────────────────────────────────────────────────────────

async def post_init(app: Application) -> None:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        send_briefing,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=BRIEF_HOUR,
            minute=BRIEF_MINUTE,
            timezone=TIMEZONE
        ),
        args=[app],
        kwargs={"scheduled": True},
        id="morning_briefing",
        replace_existing=True
    )
    scheduler.start()
    log.info(f"Scheduler started — {BRIEF_HOUR:02d}:{BRIEF_MINUTE:02d} {TIMEZONE} Mon–Fri")


def main() -> None:
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("help",    cmd_help))

    log.info("Bot polling started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
