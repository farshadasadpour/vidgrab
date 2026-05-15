"""
History module — stores download history per user.
Command: /history
Allows users to view and delete their uploaded files from S3.
"""

import json
import time
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from VideoDownloaderBot import LOGGER
from VideoDownloaderBot.modules.user_config import get_user_config

# ── Storage ────────────────────────────────────────────────────────────────
HISTORY_DIR = Path("user_history")
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

MAX_HISTORY = 50


def _history_path(user_id: int) -> Path:
    return HISTORY_DIR / f"{user_id}.json"


def load_history(user_id: int) -> list:
    path = _history_path(user_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def save_history(user_id: int, history: list) -> None:
    _history_path(user_id).write_text(json.dumps(history, indent=2))


def add_to_history(user_id: int, entry: dict) -> None:
    """
    entry = {
        "uid": "abc123",
        "title": "Video title",
        "url": "https://...",
        "destination": "s3" or "telegram",
        "s3_key": "videos/uid/file.mp4",   # only if s3
        "s3_bucket": "mybucket",            # only if s3
        "s3_endpoint": "https://...",       # only if s3
        "public_url": "https://...",        # only if s3
        "size_mb": 12.3,
        "timestamp": 1234567890,
    }
    """
    history = load_history(user_id)
    history.insert(0, entry)
    history = history[:MAX_HISTORY]
    save_history(user_id, history)


def remove_from_history(user_id: int, uid: str) -> Optional[dict]:
    history = load_history(user_id)
    entry = next((e for e in history if e["uid"] == uid), None)
    if entry:
        history = [e for e in history if e["uid"] != uid]
        save_history(user_id, history)
    return entry


# ── /history command ───────────────────────────────────────────────────────
async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    history = load_history(user_id)

    if not history:
        await update.effective_message.reply_text(
            "📋 *Your Download History*\n\n"
            "No downloads yet. Send a video URL to get started!",
            parse_mode="Markdown",
        )
        return

    await update.effective_message.reply_text(
        f"📋 *Your Download History* — {len(history)} item(s)\n\n"
        f"Showing last {min(len(history), 10)}. Tap a file to manage it:",
        parse_mode="Markdown",
    )

    for entry in history[:10]:
        await _send_history_entry(update, entry)


async def _send_history_entry(update: Update, entry: dict) -> None:
    uid = entry.get("uid", "")
    title = entry.get("title", "Unknown")[:50]
    destination = entry.get("destination", "telegram")
    size_mb = entry.get("size_mb", 0)
    timestamp = entry.get("timestamp", 0)
    date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp)) if timestamp else "—"

    dest_icon = "☁️" if destination == "s3" else "📱"
    dest_label = "S3" if destination == "s3" else "Telegram"

    buttons = []
    if destination == "s3" and entry.get("public_url"):
        buttons.append([InlineKeyboardButton("🔗 Open Link", url=entry["public_url"])])
        buttons.append([InlineKeyboardButton("🗑 Delete from S3 & History", callback_data=f"hist_del:{uid}")])
    else:
        buttons.append([InlineKeyboardButton("🗑 Remove from History", callback_data=f"hist_del:{uid}")])

    keyboard = InlineKeyboardMarkup(buttons)

    await update.effective_message.reply_text(
        f"{dest_icon} *{title}*\n"
        f"📦 `{size_mb:.1f} MB`  •  {dest_label}  •  `{date_str}`",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ── Delete callback ────────────────────────────────────────────────────────
async def hist_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    uid = query.data.split(":", 1)[1]

    entry = remove_from_history(user_id, uid)
    if not entry:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # If S3 — delete the file from bucket too
    if entry.get("destination") == "s3" and entry.get("s3_key"):
        cfg = get_user_config(user_id)
        if cfg:
            try:
                s3 = boto3.client(
                    "s3",
                    endpoint_url=cfg["s3_endpoint"],
                    aws_access_key_id=cfg["s3_access_key"],
                    aws_secret_access_key=cfg["s3_secret_key"],
                )
                s3.delete_object(Bucket=cfg["s3_bucket"], Key=entry["s3_key"])
                LOGGER.info("User %s deleted S3 file: %s", user_id, entry["s3_key"])

                await query.edit_message_text(
                    f"🗑 *Deleted from S3*\n\n"
                    f"_{entry.get('title', 'File')}_ removed from your bucket and history.",
                    parse_mode="Markdown",
                )
                return

            except ClientError as exc:
                LOGGER.error("S3 delete error for user %s: %s", user_id, exc)
                await query.edit_message_text(
                    f"❌ Could not delete from S3.\n\n`{exc}`\n\n"
                    f"Removed from history only.",
                    parse_mode="Markdown",
                )
                return

    # Telegram entry — just remove from history
    await query.edit_message_text(
        f"🗑 *Removed from history*\n\n"
        f"_{entry.get('title', 'File')}_ removed.",
        parse_mode="Markdown",
    )


# ── Register ───────────────────────────────────────────────────────────────
def register(app: Application) -> None:
    app.add_handler(CommandHandler("history", history_handler))
    app.add_handler(CallbackQueryHandler(hist_delete_callback, pattern=r"^hist_del:"))