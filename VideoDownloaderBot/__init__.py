"""
VideoDownloaderBot — configuration & shared state.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
LOGGER = logging.getLogger(__name__)

BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    LOGGER.critical("BOT_TOKEN is not set. Exiting.")
    raise SystemExit(1)

OWNER_ID: int = int(os.environ.get("OWNER_ID", "0"))
LOG_CHANNEL: int = int(os.environ.get("LOG_CHANNEL", "0"))
MAX_FILE_SIZE_MB: int = int(os.environ.get("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024

DOWNLOAD_DIR: Path = Path(os.environ.get("DOWNLOAD_DIR", "downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Per-user config storage
USER_CONFIG_DIR: Path = Path("user_configs")
USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# YouTube cookies file path (optional)
YOUTUBE_COOKIES: str = os.environ.get("YOUTUBE_COOKIES", "cookies.txt")
INSTAGRAM_COOKIES: str = os.environ.get("INSTAGRAM_COOKIES", "instagram_cookies.txt")
LOGGER.info("Config loaded — owner=%s, max_size=%sMB", OWNER_ID, MAX_FILE_SIZE_MB)
