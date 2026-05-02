"""
User config module — stores per-user S3 credentials in JSON files.
Commands: /myconfig, /setconfig, /delconfig
"""

import json
from pathlib import Path
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from VideoDownloaderBot import LOGGER, USER_CONFIG_DIR


# ── Storage helpers ────────────────────────────────────────────────────────

def _config_path(user_id: int) -> Path:
    return USER_CONFIG_DIR / f"{user_id}.json"


def get_user_config(user_id: int) -> Optional[dict]:
    path = _config_path(user_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def save_user_config(user_id: int, config: dict) -> None:
    _config_path(user_id).write_text(json.dumps(config, indent=2))


def delete_user_config(user_id: int) -> bool:
    path = _config_path(user_id)
    if path.exists():
        path.unlink()
        return True
    return False


def has_s3_config(user_id: int) -> bool:
    cfg = get_user_config(user_id)
    if not cfg:
        return False
    return all(cfg.get(k) for k in ("s3_endpoint", "s3_access_key", "s3_secret_key", "s3_bucket"))


# ── /myconfig ──────────────────────────────────────────────────────────────

async def myconfig_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    cfg = get_user_config(user_id)

    if not cfg:
        await update.effective_message.reply_text(
            "⚙️ *Your S3 Config*\n\n"
            "❌ No S3 config set.\n\n"
            "Use `/setconfig` to configure your S3 bucket:\n"
            "`/setconfig <endpoint> <access_key> <secret_key> <bucket>`\n\n"
            "Example:\n"
            "`/setconfig https://s3.amazonaws.com AKIAIOSFODNN7 wJalrXUtn mybucket`\n\n"
            "📌 If no S3 config is set, files will be sent directly to Telegram.",
            parse_mode="Markdown",
        )
        return

    # Mask secret key
    masked_secret = cfg.get("s3_secret_key", "")[:4] + "****"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Delete S3 Config", callback_data="delconfig:confirm")]
    ])

    await update.effective_message.reply_text(
        f"⚙️ *Your S3 Config*\n\n"
        f"🌐 Endpoint: `{cfg.get('s3_endpoint')}`\n"
        f"🪣 Bucket: `{cfg.get('s3_bucket')}`\n"
        f"🔑 Access Key: `{cfg.get('s3_access_key')}`\n"
        f"🔒 Secret Key: `{masked_secret}`\n\n"
        f"✅ S3 is configured — uploads will go to your bucket.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ── /setconfig ─────────────────────────────────────────────────────────────

async def setconfig_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    args = context.args

    if not args or len(args) < 4:
        await update.effective_message.reply_text(
            "⚙️ *Set S3 Config*\n\n"
            "Usage:\n"
            "`/setconfig <endpoint> <access_key> <secret_key> <bucket>`\n\n"
            "Example:\n"
            "`/setconfig https://s3.amazonaws.com AKIAIOSFODNN7 wJalrXUtn mybucket`",
            parse_mode="Markdown",
        )
        return

    config = {
        "s3_endpoint": args[0],
        "s3_access_key": args[1],
        "s3_secret_key": args[2],
        "s3_bucket": args[3],
    }

    save_user_config(user_id, config)
    LOGGER.info("User %s saved S3 config", user_id)

    await update.effective_message.reply_text(
        f"✅ *S3 Config Saved!*\n\n"
        f"🌐 Endpoint: `{config['s3_endpoint']}`\n"
        f"🪣 Bucket: `{config['s3_bucket']}`\n\n"
        f"Your uploads will now go to your S3 bucket.",
        parse_mode="Markdown",
    )


# ── /delconfig callback ────────────────────────────────────────────────────

async def delconfig_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    deleted = delete_user_config(user_id)

    if deleted:
        await query.edit_message_text(
            "🗑 *S3 config deleted.*\n\n"
            "Files will now be sent directly to Telegram.",
            parse_mode="Markdown",
        )
    else:
        await query.edit_message_text("❌ No config found to delete.")


# ── Register ───────────────────────────────────────────────────────────────

def register(app: Application) -> None:
    app.add_handler(CommandHandler("myconfig", myconfig_handler))
    app.add_handler(CommandHandler("setconfig", setconfig_handler))
    app.add_handler(CallbackQueryHandler(delconfig_callback, pattern=r"^delconfig:"))