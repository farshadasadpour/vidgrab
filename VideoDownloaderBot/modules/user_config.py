"""
User config module — step-by-step S3 setup via conversation.
Commands: /myconfig, /setup
"""

import json
from pathlib import Path
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from VideoDownloaderBot import LOGGER, USER_CONFIG_DIR

# ── Conversation states ────────────────────────────────────────────────────
STEP_ENDPOINT, STEP_ACCESS_KEY, STEP_SECRET_KEY, STEP_BUCKET, STEP_CONFIRM = range(5)


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


# ── /myconfig — show current config ───────────────────────────────────────
async def myconfig_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    cfg = get_user_config(user_id)

    if not cfg:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("⚙️ Setup S3 Now", callback_data="start_setup")
        ]])
        await update.effective_message.reply_text(
            "⚙️ *Your S3 Config*\n\n"
            "❌ No S3 configured yet.\n\n"
            "Without S3, files will be sent directly to Telegram _(50MB limit)_.\n\n"
            "Tap below to set up your S3 bucket:",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        return

    masked_secret = cfg.get("s3_secret_key", "")[:4] + "••••••••"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Update Config", callback_data="start_setup")],
        [InlineKeyboardButton("🗑 Delete Config", callback_data="delconfig:confirm")],
    ])

    await update.effective_message.reply_text(
        f"⚙️ *Your S3 Config*\n\n"
        f"🌐 Endpoint: `{cfg.get('s3_endpoint')}`\n"
        f"🪣 Bucket: `{cfg.get('s3_bucket')}`\n"
        f"🔑 Access Key: `{cfg.get('s3_access_key')}`\n"
        f"🔒 Secret Key: `{masked_secret}`\n\n"
        f"✅ S3 is active — uploads go to your bucket.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ── Setup start ────────────────────────────────────────────────────────────
async def setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()

    text = (
        "⚙️ *S3 Setup — Step 1 of 4*\n\n"
        "Please send your *S3 Endpoint URL*.\n\n"
        "Examples:\n"
        "• `https://s3.amazonaws.com`\n"
        "• `https://s3.ir-thr-at1.arvanstorage.ir`\n"
        "• `https://storage.googleapis.com`\n\n"
        "Send /cancel to abort at any time."
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(text, parse_mode="Markdown")

    return STEP_ENDPOINT


async def setup_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text(
        "❌ S3 setup cancelled.\n\nUse /setup anytime to try again."
    )
    return ConversationHandler.END


# ── Step 1: Endpoint ───────────────────────────────────────────────────────
async def step_endpoint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    endpoint = update.effective_message.text.strip()

    if not endpoint.startswith("http"):
        await update.effective_message.reply_text(
            "⚠️ That doesn't look like a valid URL.\n"
            "Please send a URL starting with `https://`",
            parse_mode="Markdown",
        )
        return STEP_ENDPOINT

    context.user_data["s3_endpoint"] = endpoint

    await update.effective_message.reply_text(
        "✅ Endpoint saved!\n\n"
        "⚙️ *S3 Setup — Step 2 of 4*\n\n"
        "Now send your *Access Key*.\n\n"
        "Send /cancel to abort.",
        parse_mode="Markdown",
    )
    return STEP_ACCESS_KEY


# ── Step 2: Access Key ─────────────────────────────────────────────────────
async def step_access_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["s3_access_key"] = update.effective_message.text.strip()

    await update.effective_message.reply_text(
        "✅ Access Key saved!\n\n"
        "⚙️ *S3 Setup — Step 3 of 4*\n\n"
        "Now send your *Secret Key*.\n\n"
        "⚠️ Your message will be deleted immediately for security.\n\n"
        "Send /cancel to abort.",
        parse_mode="Markdown",
    )
    return STEP_SECRET_KEY


# ── Step 3: Secret Key ─────────────────────────────────────────────────────
async def step_secret_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["s3_secret_key"] = update.effective_message.text.strip()

    # Delete message containing secret key immediately
    try:
        await update.effective_message.delete()
    except Exception:
        pass

    await update.effective_message.reply_text(
        "✅ Secret Key saved! _(message deleted for security)_\n\n"
        "⚙️ *S3 Setup — Step 4 of 4*\n\n"
        "Now send your *Bucket Name*.\n\n"
        "Send /cancel to abort.",
        parse_mode="Markdown",
    )
    return STEP_BUCKET


# ── Step 4: Bucket ─────────────────────────────────────────────────────────
async def step_bucket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["s3_bucket"] = update.effective_message.text.strip()

    cfg = context.user_data
    masked_secret = cfg["s3_secret_key"][:4] + "••••••••"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm & Save", callback_data="confirm_setup"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup"),
        ]
    ])

    await update.effective_message.reply_text(
        "⚙️ *Review your S3 Config*\n\n"
        f"🌐 Endpoint: `{cfg['s3_endpoint']}`\n"
        f"🪣 Bucket: `{cfg['s3_bucket']}`\n"
        f"🔑 Access Key: `{cfg['s3_access_key']}`\n"
        f"🔒 Secret Key: `{masked_secret}`\n\n"
        "Does everything look correct?",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return STEP_CONFIRM


# ── Step 5: Confirm ────────────────────────────────────────────────────────
async def step_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_setup":
        context.user_data.clear()
        await query.edit_message_text("❌ Setup cancelled. Use /setup to try again.")
        return ConversationHandler.END

    user_id = update.effective_user.id
    cfg = {
        "s3_endpoint":   context.user_data["s3_endpoint"],
        "s3_access_key": context.user_data["s3_access_key"],
        "s3_secret_key": context.user_data["s3_secret_key"],
        "s3_bucket":     context.user_data["s3_bucket"],
    }
    save_user_config(user_id, cfg)
    context.user_data.clear()
    LOGGER.info("User %s saved S3 config", user_id)

    await query.edit_message_text(
        "✅ *S3 Config Saved!*\n\n"
        "Your uploads will now go to your S3 bucket.\n\n"
        "Use /myconfig to view or update anytime.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ── Delete config callback ─────────────────────────────────────────────────
async def delconfig_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    deleted = delete_user_config(update.effective_user.id)
    if deleted:
        await query.edit_message_text(
            "🗑 *S3 config deleted.*\n\n"
            "Files will now be sent directly to Telegram.\n\n"
            "Use /setup to configure S3 again.",
            parse_mode="Markdown",
        )
    else:
        await query.edit_message_text("❌ No config found to delete.")


# ── Register ───────────────────────────────────────────────────────────────
def register(app: Application) -> None:
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("setup", setup_start),
            CallbackQueryHandler(setup_start, pattern="^start_setup$"),
        ],
        states={
            STEP_ENDPOINT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, step_endpoint)],
            STEP_ACCESS_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, step_access_key)],
            STEP_SECRET_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, step_secret_key)],
            STEP_BUCKET:     [MessageHandler(filters.TEXT & ~filters.COMMAND, step_bucket)],
            STEP_CONFIRM:    [CallbackQueryHandler(step_confirm, pattern="^(confirm|cancel)_setup$")],
        },
        fallbacks=[CommandHandler("cancel", setup_cancel)],
        per_user=True,
        per_chat=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("myconfig", myconfig_handler))
    app.add_handler(CallbackQueryHandler(delconfig_callback, pattern=r"^delconfig:"))