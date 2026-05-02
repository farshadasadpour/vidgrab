"""
Cleanup module — deletes files older than CLEANUP_MAX_AGE_HOURS from the downloads folder.
Runs automatically every hour via JobQueue.
"""

import os
import time
from pathlib import Path

from telegram.ext import Application

from VideoDownloaderBot import DOWNLOAD_DIR, LOGGER

# ── Config (can be moved to .env) ─────────────────────────────────────────
MAX_AGE_HOURS: int = int(os.environ.get("CLEANUP_MAX_AGE_HOURS", "1"))
MAX_AGE_SECONDS: int = MAX_AGE_HOURS * 3600
CLEANUP_INTERVAL: int = int(os.environ.get("CLEANUP_INTERVAL_HOURS", "1")) * 3600


# ── Cleanup logic ──────────────────────────────────────────────────────────
def cleanup_downloads() -> tuple[int, int]:
    """
    Delete files older than MAX_AGE_SECONDS from DOWNLOAD_DIR.
    Returns (deleted_count, failed_count).
    """
    deleted = 0
    failed = 0
    now = time.time()

    for file in Path(DOWNLOAD_DIR).iterdir():
        if not file.is_file():
            continue
        try:
            age = now - file.stat().st_mtime
            if age > MAX_AGE_SECONDS:
                file.unlink()
                deleted += 1
                LOGGER.info("🗑 Deleted: %s (age: %.0fs)", file.name, age)
        except Exception as exc:
            failed += 1
            LOGGER.warning("Could not delete %s: %s", file.name, exc)

    return deleted, failed


# ── Job callback ───────────────────────────────────────────────────────────
async def cleanup_job(context) -> None:
    deleted, failed = cleanup_downloads()
    LOGGER.info("Cleanup done — deleted: %d, failed: %d", deleted, failed)


# ── Register ───────────────────────────────────────────────────────────────
def register(app: Application) -> None:
    app.job_queue.run_repeating(
        cleanup_job,
        interval=CLEANUP_INTERVAL,
        first=CLEANUP_INTERVAL,
        name="cleanup_downloads",
    )
    LOGGER.info(
        "Cleanup scheduled — every %dh, removes files older than %dh",
        CLEANUP_INTERVAL // 3600,
        MAX_AGE_HOURS,
    )
