"""
Download module — full rewrite with:
  - Per-user S3 config (fallback to Telegram if not set)
  - YouTube blocked with friendly message
  - Friendly error messages for common HTTP errors
  - Download progress bar with heartbeat animation
  - One active download per user with cancel option
  - History saved after every successful upload
"""

import asyncio
import re
import time
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
    YOUTUBE_COOKIES,
)
from VideoDownloaderBot.modules.history import add_to_history
from VideoDownloaderBot.modules.status import increment_download_count
from VideoDownloaderBot.modules.user_config import get_user_config, has_s3_config

# ── URL detection ──────────────────────────────────────────────────────────
_URL_RE = re.compile(r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[^\s]*)?")
_YOUTUBE_RE = re.compile(r"(youtube\.com/watch|youtu\.be/|youtube\.com/shorts/)")

# ── State ──────────────────────────────────────────────────────────────────
_active: dict = {}   # user_id -> {"uid": ..., "status_msg": ...}
_pending: dict = {}  # uid -> (file_path, title, url)

# ── Constants ──────────────────────────────────────────────────────────────
EDIT_INTERVAL = 3.0
HEARTBEAT = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


# ── Helpers ────────────────────────────────────────────────────────────────
def extract_url(text: str) -> Optional[str]:
    match = _URL_RE.search(text)
    return match.group(0) if match else None


def make_progress_bar(percent: float, width: int = 20) -> str:
    filled = int(width * percent / 100)
    return f"[{'█' * filled}{'░' * (width - filled)}] {percent:.1f}%"


async def _edit(msg: Message, text: str, **kwargs) -> None:
    try:
        await msg.edit_text(text, **kwargs)
    except Exception:
        pass


def _friendly_error(exc: Exception) -> str:
    err = str(exc)
    if "HTTP Error 410" in err or "Gone" in err:
        return "❌ This video is no longer available.\n\nIt may have been deleted or expired on the source site."
    elif "HTTP Error 403" in err or "Forbidden" in err:
        return "❌ Access denied.\n\nThis video is private or region-restricted."
    elif "HTTP Error 404" in err or "Not Found" in err:
        return "❌ Video not found.\n\nThe URL may be wrong or the content was removed."
    elif "HTTP Error 429" in err or "Too Many Requests" in err:
        return "❌ Rate limited by the source site.\n\nPlease wait a few minutes and try again."
    elif "HTTP Error 401" in err or "Unauthorized" in err:
        return "❌ This video requires login to download."
    elif "HTTP Error 500" in err or "HTTP Error 503" in err:
        return "❌ The source site is having issues.\n\nPlease try again later."
    elif "Unsupported URL" in err:
        return "❌ This URL is not supported.\n\nMake sure it's a direct video link."
    elif "Sign in" in err or "bot" in err.lower():
        return "❌ The source site is blocking server downloads.\n\nTry a different site."
    else:
        return f"❌ Download failed.\n\n`{exc}`"


# ── yt-dlp ─────────────────────────────────────────────────────────────────
def _build_ydl_opts(output_template: str, progress_queue: asyncio.Queue, loop) -> dict:
    def progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed") or 0
            asyncio.run_coroutine_threadsafe(
                progress_queue.put({
                    "percent": (downloaded / total * 100) if total else 0,
                    "downloaded": downloaded,
                    "total": total,
                    "speed": speed / (1024 * 1024),
                    "has_total": bool(total),
                }),
                loop,
            )

    opts = {
        "outtmpl": output_template,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "progress_hooks": [progress_hook],
    }

    cookies_path = Path(YOUTUBE_COOKIES)
    if cookies_path.exists():
        opts["cookiefile"] = str(cookies_path)

    return opts


def _do_download(url: str, output_template: str, progress_queue: asyncio.Queue, loop) -> dict:
    opts = _build_ydl_opts(output_template, progress_queue, loop)
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


# ── Progress display with heartbeat ───────────────────────────────────────
async def _run_progress_display(
    status_msg: Message,
    progress_queue: asyncio.Queue,
    uid: str,
    label: str = "⬇️ Downloading",
):
    last_edit_time = 0.0
    last_data = None
    heartbeat_idx = 0

    cancel_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🛑 Cancel", callback_data=f"cancel:{uid}")
    ]])

    while True:
        try:
            # Drain queue — keep only latest data
            try:
                while True:
                    last_data = progress_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

            now = time.time()
            spin = HEARTBEAT[heartbeat_idx % len(HEARTBEAT)]
            heartbeat_idx += 1

            if last_data and last_data["has_total"]:
                text = (
                    f"{label}… {spin}\n"
                    f"{make_progress_bar(last_data['percent'])}\n"
                    f"`{last_data['downloaded'] // (1024*1024)} MB"
                    f" / {last_data['total'] // (1024*1024)} MB`\n"
                    f"🚀 `{last_data['speed']:.1f} MB/s`"
                )
            elif last_data:
                text = (
                    f"{label}… {spin}\n"
                    f"`{last_data['downloaded'] // (1024*1024)} MB downloaded`\n"
                    f"🚀 `{last_data['speed']:.1f} MB/s`"
                )
            else:
                text = f"{label}… {spin}\n`Starting…`"

            if now - last_edit_time >= EDIT_INTERVAL:
                await _edit(
                    status_msg,
                    text,
                    parse_mode="Markdown",
                    reply_markup=cancel_keyboard,
                )
                last_edit_time = now

            await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            LOGGER.warning("Progress display error: %s", exc)
            await asyncio.sleep(1.0)


# ── Download handler ───────────────────────────────────────────────────────
async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.text:
        return

    url = extract_url(message.text)
    if not url:
        return

    # Block YouTube
    if _YOUTUBE_RE.search(url):
        await message.reply_text(
            "⚠️ *YouTube is not supported*\n\n"
            "YouTube blocks downloads from server IPs.\n\n"
            "✅ *Supported:* Twitter/X, Instagram, TikTok, Reddit, "
            "Vimeo, Dailymotion, Facebook, and 1000+ more.",
            parse_mode="Markdown",
        )
        return

    user_id = update.effective_user.id

    # One download at a time
    if user_id in _active:
        active_uid = _active[user_id]["uid"]
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🛑 Stop & start new", callback_data=f"cancel:{active_uid}:new:{url}"),
            InlineKeyboardButton("⏳ Keep waiting", callback_data="cancel:ignore"),
        ]])
        await message.reply_text(
            "⚠️ You already have an active download.\nWhat do you want to do?",
            reply_markup=keyboard,
        )
        return

    await _start_download(message, user_id, url)


async def _start_download(message: Message, user_id: int, url: str) -> None:
    status_msg = await message.reply_text("⏳ Fetching video info…")
    uid = uuid.uuid4().hex[:8]
    output_template = str(DOWNLOAD_DIR / f"{uid}.%(ext)s")
    progress_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    _active[user_id] = {"uid": uid, "status_msg": status_msg}

    progress_task = asyncio.create_task(
        _run_progress_display(status_msg, progress_queue, uid)
    )

    try:
        info = await loop.run_in_executor(
            None, _do_download, url, output_template, progress_queue, loop
        )
    except yt_dlp.DownloadError as exc:
        progress_task.cancel()
        await _edit(status_msg, _friendly_error(exc), parse_mode="Markdown")
        for f in DOWNLOAD_DIR.glob(f"{uid}.*"):
            f.unlink(missing_ok=True)
        return
    except asyncio.CancelledError:
        progress_task.cancel()
        await _edit(status_msg, "🛑 Download cancelled.")
        for f in DOWNLOAD_DIR.glob(f"{uid}.*"):
            f.unlink(missing_ok=True)
        return
    except Exception as exc:
        progress_task.cancel()
        LOGGER.exception("Unexpected download error")
        await _edit(status_msg, f"❌ Unexpected error.\n\n`{exc}`")
        for f in DOWNLOAD_DIR.glob(f"{uid}.*"):
            f.unlink(missing_ok=True)
        return
    finally:
        progress_task.cancel()
        _active.pop(user_id, None)

    files = list(DOWNLOAD_DIR.glob(f"{uid}.*"))
    if not files:
        await _edit(status_msg, "❌ Download failed — no file produced.")
        return

    file_path = files[0]
    title = (info.get("title") or "Video") if info else "Video"
    size_mb = file_path.stat().st_size / (1024 * 1024)

    _pending[uid] = (file_path, title, url)

    if has_s3_config(user_id):
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📱 Telegram", callback_data=f"tg:{uid}"),
            InlineKeyboardButton("☁️ My S3", callback_data=f"s3:{uid}"),
        ]])
        destination_text = "Where do you want to upload?"
    else:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📱 Send to Telegram", callback_data=f"tg:{uid}"),
            InlineKeyboardButton("⚙️ Setup S3", callback_data=f"setup_s3:{uid}"),
        ]])
        destination_text = "No S3 configured — send to Telegram or use /setup first."

    await _edit(
        status_msg,
        f"✅ *Downloaded!*\n\n"
        f"🎬 {title}\n"
        f"📦 Size: `{size_mb:.1f} MB`\n\n"
        f"{destination_text}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ── Cancel handler ─────────────────────────────────────────────────────────
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":", 3)
    action = parts[1] if len(parts) > 1 else ""

    if action == "ignore":
        await query.answer("⏳ Waiting for current download…", show_alert=False)
        return

    uid = parts[1]
    user_id = update.effective_user.id

    _active.pop(user_id, None)
    _pending.pop(uid, None)
    for f in DOWNLOAD_DIR.glob(f"{uid}.*"):
        f.unlink(missing_ok=True)

    if len(parts) == 4 and parts[2] == "new":
        new_url = parts[3]
        await query.edit_message_text("🛑 Cancelled. Starting new download…")
        await _start_download(query.message, user_id, new_url)
    else:
        await query.edit_message_text("🛑 Cancelled and files removed.")


# ── Upload choice handler ──────────────────────────────────────────────────
async def choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id

    if data.startswith("setup_s3:"):
        await query.edit_message_text(
            "⚙️ Use /setup to configure your S3 bucket first.\nThen resend the URL.",
        )
        return

    destination, uid = data.split(":", 1)

    if uid not in _pending:
        await query.edit_message_text("❌ Session expired. Send the URL again.")
        return

    file_path, title, url = _pending.pop(uid)

    if destination == "tg":
        await _upload_telegram(query.message, file_path, title, url, user_id, uid)
    elif destination == "s3":
        cfg = get_user_config(user_id)
        if not cfg:
            await query.edit_message_text("❌ No S3 config. Use /setup first.")
            file_path.unlink(missing_ok=True)
            return
        await _upload_s3(query.message, file_path, title, url, user_id, uid, cfg)


# ── Upload to Telegram ─────────────────────────────────────────────────────
async def _upload_telegram(
    message: Message,
    file_path: Path,
    title: str,
    url: str,
    user_id: int,
    uid: str,
) -> None:
    try:
        await _edit(message, "📤 Uploading to Telegram…")
        size_mb = file_path.stat().st_size / (1024 * 1024)

        with open(file_path, "rb") as f:
            await message.reply_video(
                video=f,
                caption=f"🎬 {title}",
                supports_streaming=True,
                read_timeout=300,
                write_timeout=300,
            )

        add_to_history(user_id, {
            "uid": uid,
            "title": title,
            "url": url,
            "destination": "telegram",
            "size_mb": round(size_mb, 2),
            "timestamp": time.time(),
        })

        await message.delete()
        increment_download_count()
        LOGGER.info("Sent '%s' to Telegram for user %s", title, user_id)

    except Exception as exc:
        LOGGER.exception("Telegram upload error")
        await _edit(message, f"❌ Telegram upload failed.\n\n`{exc}`")
    finally:
        file_path.unlink(missing_ok=True)


# ── Upload to S3 ───────────────────────────────────────────────────────────
async def _upload_s3(
    message: Message,
    file_path: Path,
    title: str,
    url: str,
    user_id: int,
    uid: str,
    cfg: dict,
) -> None:
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=cfg["s3_endpoint"],
            aws_access_key_id=cfg["s3_access_key"],
            aws_secret_access_key=cfg["s3_secret_key"],
        )
        bucket = cfg["s3_bucket"]
        file_size = file_path.stat().st_size
        loop = asyncio.get_event_loop()
        uploaded = 0
        last_edit_time = 0.0

        def progress_callback(bytes_transferred):
            nonlocal uploaded, last_edit_time
            uploaded += bytes_transferred
            percent = (uploaded / file_size) * 100
            now = time.time()
            if now - last_edit_time >= EDIT_INTERVAL:
                last_edit_time = now
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
                bucket,
                s3_key,
                Callback=progress_callback,
                ExtraArgs={"ACL": "public-read"},
            ),
        )

        public_url = f"{cfg['s3_endpoint']}/{bucket}/{s3_key}"
        size_mb = file_size / (1024 * 1024)

        add_to_history(user_id, {
            "uid": uid,
            "title": title,
            "url": url,
            "destination": "s3",
            "s3_key": s3_key,
            "s3_bucket": bucket,
            "s3_endpoint": cfg["s3_endpoint"],
            "public_url": public_url,
            "size_mb": round(size_mb, 2),
            "timestamp": time.time(),
        })

        await message.reply_text(
            f"✅ *{title}*\n\n"
            f"📦 Size: `{size_mb:.1f} MB`\n"
            f"🔗 [Download Link]({public_url})",
            parse_mode="Markdown",
        )
        await message.delete()
        increment_download_count()
        LOGGER.info("Uploaded '%s' to S3 for user %s", title, user_id)

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
    app.add_handler(CallbackQueryHandler(choice_handler, pattern=r"^(tg|s3|setup_s3):"))
    app.add_handler(CallbackQueryHandler(cancel_handler, pattern=r"^cancel:"))