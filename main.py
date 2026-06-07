"""
main.py
-------
Entrypoint — runs Telegram bot in a background thread,
uvicorn (FastAPI webhook) in the main thread on Railway's PORT.
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
    """Run the Telegram bot in a background thread with its own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    from bot import main as bot_main
    log.info("Telegram bot thread starting...")
    bot_main()


def main():
    # Start Telegram bot in background thread
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    log.info("Telegram bot thread started")

    # Railway domain is configured to route to port 8000
    port = int(os.environ.get("PORT", "8000"))
    log.info(f"Starting webhook server on 0.0.0.0:{port}")
    uvicorn.run(
        "webhook:app",
        host="0.0.0.0",
        port=port,
        log_level="warning"
    )


if __name__ == "__main__":
    main()
