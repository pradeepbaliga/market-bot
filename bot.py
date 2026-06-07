"""
Morning Market Analyst — Telegram Bot
--------------------------------------
Commands:
  /analyze  — run a full morning briefing on demand
  /status   — show bot status + next scheduled run
  /help     — show available commands

Scheduler fires every weekday at the configured MARKET_BRIEF_TIME (default 6:30 AM PT).
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

from analyst import run_morning_analysis

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
CHAT_ID          = os.environ["CHAT_ID"]           # your personal chat ID
ANTHROPIC_KEY    = os.environ["ANTHROPIC_API_KEY"]
BRIEF_HOUR       = int(os.getenv("BRIEF_HOUR", "6"))    # 6 AM
BRIEF_MINUTE     = int(os.getenv("BRIEF_MINUTE", "30")) # :30
TIMEZONE         = os.getenv("TIMEZONE", "America/Los_Angeles")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

async def send_briefing(app: Application) -> None:
    """Generate and send the full market briefing."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    # Skip weekends
    if now.weekday() >= 5:
        log.info("Weekend — skipping briefing.")
        return

    log.info("Generating morning briefing...")
    await app.bot.send_message(
        chat_id=CHAT_ID,
        text="⏳ *Generating your Morning Market Briefing...*\nSearching live data — give me 30–60 seconds.",
        parse_mode="Markdown"
    )

    try:
        briefing = await run_morning_analysis()
        # Telegram has a 4096-char limit per message — chunk if needed
        chunks = split_message(briefing, limit=4000)
        for i, chunk in enumerate(chunks):
            prefix = "" if i == 0 else "_(continued)_\n\n"
            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=prefix + chunk,
                parse_mode="Markdown"
            )
    except Exception as e:
        log.error(f"Briefing failed: {e}")
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=f"❌ Briefing failed: `{e}`",
            parse_mode="Markdown"
        )


def split_message(text: str, limit: int = 4000) -> list[str]:
    """Split a long message into chunks at paragraph boundaries."""
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

# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /analyze — on-demand briefing."""
    if str(update.effective_chat.id) != str(CHAT_ID):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    await update.message.reply_text("⏳ Running market analysis — give me ~60 seconds...")
    await send_briefing(ctx.application)


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status — show next scheduled run."""
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
    """Handle /help."""
    msg = (
        "📈 *Morning Market Analyst Bot*\n\n"
        "/analyze — Run a full market briefing right now\n"
        "/status  — Show bot status and schedule\n"
        "/help    — Show this message\n\n"
        "_Briefings are auto-sent every weekday morning._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Register commands
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("help",    cmd_help))

    # Scheduler — fire weekdays at configured time
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
        id="morning_briefing",
        name="Morning Market Briefing",
        replace_existing=True
    )
    scheduler.start()
    log.info(f"Scheduler started — briefings at {BRIEF_HOUR:02d}:{BRIEF_MINUTE:02d} {TIMEZONE} (Mon–Fri)")

    log.info("Bot polling started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
