"""
main.py
-------
Entrypoint — runs the Telegram bot and FastAPI webhook server concurrently.
"""

import asyncio
import logging
import threading
import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)


def run_webhook_server():
    """Run FastAPI/uvicorn in a background thread."""
    port = int(os.getenv("PORT", "8000"))
    log.info(f"Starting webhook server on port {port}")
    uvicorn.run(
        "webhook:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )


def main():
    # Start webhook server in background thread
    webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
    webhook_thread.start()
    log.info("Webhook server thread started")

    # Run Telegram bot in main thread (blocking)
    from bot import main as run_bot
    run_bot()


if __name__ == "__main__":
    main()
