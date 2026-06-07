"""
main.py — Railway entrypoint
uvicorn runs in main thread on PORT=8000
Telegram bot runs in background thread with isolated event loop
"""

import asyncio
import logging
import threading
import os

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)


def run_telegram_bot():
    """Telegram bot in its own thread + event loop — crash here won't kill uvicorn."""
    try:
        import time
        time.sleep(3)  # Wait for old instance to fully stop before polling
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        log.info("Telegram bot starting...")
        from bot import main as bot_main
        bot_main()
    except Exception as e:
        log.error(f"Telegram bot crashed: {e}", exc_info=True)


def main():
    # Start bot in background — isolated, won't affect HTTP server
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True, name="telegram-bot")
    bot_thread.start()
    log.info("Telegram bot thread started")

    # uvicorn in main thread — Railway needs this to stay alive on port 8000
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    log.info(f"Starting uvicorn on 0.0.0.0:{port}")
    uvicorn.run(
        "webhook:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()
