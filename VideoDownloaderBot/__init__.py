"""
VideoDownloaderBot — configuration & shared state.
All other modules import from here.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env ──────────────────────────────────────────────────────────────
load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
LOGGER = logging.getLogger(__name__)

# ── Required config ────────────────────────────────────────────────────────
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    LOGGER.critical("BOT_TOKEN is not set. Exiting.")
    raise SystemExit(1)

OWNER_ID: int = int(os.environ.get("OWNER_ID", "0"))
LOG_CHANNEL: int = int(os.environ.get("LOG_CHANNEL", "0"))
API_ID: int = int(os.environ.get("API_ID", "0"))
API_HASH: str = os.environ.get("API_HASH", "")
# ── Optional config ────────────────────────────────────────────────────────
MAX_FILE_SIZE_MB: int = int(os.environ.get("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024

DOWNLOAD_DIR: Path = Path(os.environ.get("DOWNLOAD_DIR", "downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
S3_ENDPOINT: str = os.environ.get("S3_ENDPOINT", "")
S3_ACCESS_KEY: str = os.environ.get("S3_ACCESS_KEY", "")
S3_SECRET_KEY: str = os.environ.get("S3_SECRET_KEY", "")
S3_BUCKET: str = os.environ.get("S3_BUCKET", "")

LOGGER.info("Config loaded — owner=%s, max_size=%sMB", OWNER_ID, MAX_FILE_SIZE_MB)
