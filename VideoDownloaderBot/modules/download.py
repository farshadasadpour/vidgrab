"""
Download module — full rewrite.

Flow:
  1. User sends a URL.
  2. Bot downloads with yt-dlp (live progress bar).
  3. Bot asks: Upload to Telegram or S3?
  4. Bot uploads with live progress bar and sends result.
"""

import asyncio
import re
import uuid
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError
import yt_dlp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from VideoDownloaderBot import (
    DOWNLOAD_DIR,
    LOGGER,
    S3_BUCKET,
    S3_ENDPOINT,
    S3_ACCESS_KEY,
    S3_SECRET_KEY,
)
from VideoDownloaderBot.modules.status import increment_download_count

# ── URL detection ──────────────────────────────────────────────────────────
_URL_RE = re.compile(r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[^\s]*)?")

# Pending downloads: uid -> (file_path, title)
_pending: dict = {}


def extract_url(text: str) -> Optional[str]:
    match = _URL_RE.search(text)
    return match.group(0) if match else None


# ── Progress bar ───────────────────────────────────────────────────────────
def make_progress_bar(percent: float, width: int = 20) -> str:
    filled = int(width * percent / 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {percent:.1f}%"


# ── Safe message edit ──────────────────────────────────────────────────────
async def _edit(msg: Message, text: str, **kwargs) -> None:
    try:
        await msg.edit_text(text, **kwargs)
    except Exception:
        pass


# ── S3 client ──────────────────────────────────────────────────────────────
def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
    )


# ── yt-dlp download with progress ─────────────────────────────────────────
def _build_ydl_opts(output_template: str, progress_queue: asyncio.Queue, loop) -> dict:
    def progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed") or 0
            if total:
                percent = (downloaded / total) * 100
                speed_mb = speed / (1024 * 1024)
                asyncio.run_coroutine_threadsafe(
                    progress_queue.put((percent, downloaded, total, speed_mb)),
                    loop,
                )

    return {
        "outtmpl": output_template,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "progress_hooks": [progress_hook],
    }


def _do_download(url: str, output_template: str, progress_queue: asyncio.Queue, loop) -> dict:
    opts = _build_ydl_opts(output_template, progress_queue, loop)
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


# ── Download progress updater task ────────────────────────────────────────
async def _run_download_progress(status_msg: Message, progress_queue: asyncio.Queue):
    last_text = ""
    while True:
        try:
            percent, downloaded, total, speed_mb = await asyncio.wait_for(
                progress_queue.get(), timeout=1.0
            )
            text = (
                f"⬇️ *Downloading…*\n"
                f"{make_progress_bar(percent)}\n"
                f"`{downloaded // (1024*1024)} MB / {total // (1024*1024)} MB`\n"
                f"🚀 Speed: `{speed_mb:.1f} MB/s`"
            )
            if text != last_text:
                last_text = text
                await _edit(status_msg, text, parse_mode="Markdown")
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            break


# ── Step 1: Download and ask user ─────────────────────────────────────────
async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.text:
        return

    url = extract_url(message.text)
    if not url:
        return

    status_msg = await message.reply_text("⏳ Fetching video info…")
    uid = uuid.uuid4().hex[:8]
    output_template = str(DOWNLOAD_DIR / f"{uid}.%(ext)s")

    progress_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    progress_task = asyncio.create_task(
        _run_download_progress(status_msg, progress_queue)
    )

    try:
        info = await loop.run_in_executor(
            None, _do_download, url, output_template, progress_queue, loop
        )
    except yt_dlp.DownloadError as exc:
        progress_task.cancel()
        LOGGER.warning("yt-dlp error: %s", exc)
        await _edit(status_msg, f"❌ Download failed.\n\n`{exc}`")
        return
    except Exception as exc:
        progress_task.cancel()
        LOGGER.exception("Unexpected download error")
        await _edit(status_msg, f"❌ Unexpected error.\n\n`{exc}`")
        return
    finally:
        progress_task.cancel()

    files = list(DOWNLOAD_DIR.glob(f"{uid}.*"))
    if not files:
        await _edit(status_msg, "❌ Download failed — no file produced.")
        return

    file_path = files[0]
    title = (info.get("title") or "Video") if info else "Video"
    size_mb = file_path.stat().st_size / (1024 * 1024)

    # Store for callback
    _pending[uid] = (file_path, title)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Send to Telegram", callback_data=f"tg:{uid}"),
            InlineKeyboardButton("☁️ Upload to S3", callback_data=f"s3:{uid}"),
        ]
    ])

    await _edit(
        status_msg,
        f"✅ *Downloaded!*\n\n"
        f"🎬 {title}\n"
        f"📦 Size: `{size_mb:.1f} MB`\n\n"
        f"Where do you want to upload?",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ── Step 2: Handle button choice ──────────────────────────────────────────
async def choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    destination, uid = query.data.split(":", 1)

    if uid not in _pending:
        await query.edit_message_text("❌ Session expired. Send the URL again.")
        return

    file_path, title = _pending.pop(uid)

    if destination == "tg":
        await _upload_telegram(query.message, file_path, title)
    else:
        await _upload_s3(query.message, file_path, title, uid)


# ── Upload to Telegram ─────────────────────────────────────────────────────
async def _upload_telegram(message: Message, file_path: Path, title: str) -> None:
    try:
        await _edit(message, "📤 Uploading to Telegram…")
        with open(file_path, "rb") as f:
            await message.reply_video(
                video=f,
                caption=f"🎬 {title}",
                supports_streaming=True,
            )
        await message.delete()
        increment_download_count()
        LOGGER.info("Sent '%s' to Telegram", title)
    except Exception as exc:
        LOGGER.exception("Telegram upload error")
        await _edit(message, f"❌ Telegram upload failed.\n\n`{exc}`")
    finally:
        file_path.unlink(missing_ok=True)


# ── Upload to S3 with progress ─────────────────────────────────────────────
async def _upload_s3(message: Message, file_path: Path, title: str, uid: str) -> None:
    try:
        s3 = get_s3_client()
        file_size = file_path.stat().st_size
        loop = asyncio.get_event_loop()
        uploaded = 0
        last_percent = -1.0

        def progress_callback(bytes_transferred):
            nonlocal uploaded, last_percent
            uploaded += bytes_transferred
            percent = (uploaded / file_size) * 100
            if percent - last_percent >= 2:
                last_percent = percent
                speed = 0  # boto3 doesn't give speed natively
                text = (
                    f"☁️ *Uploading to S3…*\n"
                    f"{make_progress_bar(percent)}\n"
                    f"`{uploaded // (1024*1024)} MB / {file_size // (1024*1024)} MB`"
                )
                asyncio.run_coroutine_threadsafe(
                    _edit(message, text, parse_mode="Markdown"),
                    loop,
                )

        s3_key = f"videos/{uid}/{file_path.name}"

        await loop.run_in_executor(
            None,
            lambda: s3.upload_file(
                str(file_path),
                S3_BUCKET,
                s3_key,
                Callback=progress_callback,
                ExtraArgs={"ACL": "public-read"},
            ),
        )

        public_url = f"{S3_ENDPOINT}/{S3_BUCKET}/{s3_key}"
        size_mb = file_size / (1024 * 1024)

        await message.reply_text(
            f"✅ *{title}*\n\n"
            f"📦 Size: `{size_mb:.1f} MB`\n"
            f"🔗 [Download Link]({public_url})",
            parse_mode="Markdown",
        )
        await message.delete()
        increment_download_count()
        LOGGER.info("Uploaded '%s' to S3: %s", title, public_url)

    except ClientError as exc:
        LOGGER.error("S3 error: %s", exc)
        await _edit(message, f"❌ S3 upload failed.\n\n`{exc}`")
    except Exception as exc:
        LOGGER.exception("S3 unexpected error")
        await _edit(message, f"❌ Unexpected error.\n\n`{exc}`")
    finally:
        file_path.unlink(missing_ok=True)


# ── Register ───────────────────────────────────────────────────────────────
def register(app: Application) -> None:
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            download_handler,
        )
    )
    app.add_handler(CallbackQueryHandler(choice_handler, pattern=r"^(tg|s3):"))
