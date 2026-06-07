"""
main.py — Railway entrypoint
Telegram bot runs in MAIN thread (needs signal handlers)
uvicorn runs in background thread
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


def run_uvicorn():
    """Run FastAPI webhook server in background thread."""
    try:
        import uvicorn
        port = int(os.environ.get("PORT", "8000"))
        log.info(f"Starting uvicorn on 0.0.0.0:{port}")
        uvicorn.run(
            "webhook:app",
            host="0.0.0.0",
            port=port,
            log_level="info",
        )
    except Exception as e:
        log.error(f"Uvicorn crashed: {e}", exc_info=True)


def main():
    # Start uvicorn in background thread first
    uvicorn_thread = threading.Thread(target=run_uvicorn, daemon=True, name="uvicorn")
    uvicorn_thread.start()
    log.info("Uvicorn thread started")

    # Telegram bot MUST run in main thread (signal handlers requirement)
    log.info("Starting Telegram bot in main thread...")
    from bot import main as bot_main
    bot_main()


if __name__ == "__main__":
    main()
