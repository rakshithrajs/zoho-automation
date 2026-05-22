"""Telegram bot front-end: /invoice runs the pipeline and DMs the PDF back."""
from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from logger import get_logger
from main import run_pipeline

load_dotenv()
log = get_logger("zoho_automation.bot")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

# Optional comma-separated allowlist of Telegram user IDs. If empty, anyone
# who finds the bot could run /invoice — so set this in .env for safety.
_ALLOWED = {
    int(x) for x in os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",") if x.strip()
}


def _authorized(user_id: Optional[int]) -> bool:
    return not _ALLOWED or (user_id is not None and user_id in _ALLOWED)


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! Send /invoice <amount in INR> to generate an invoice and get the PDF here.\n"
        "Example: /invoice 30000"
    )


async def invoice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if not _authorized(user.id if user else None):
        await update.message.reply_text("Not authorized.")
        log.warning("Rejected /invoice from unauthorized user %s", user)
        return

    inr_amount: Optional[float] = None
    if ctx.args:
        try:
            inr_amount = float(ctx.args[0].replace(",", ""))
            if inr_amount <= 0:
                raise ValueError("amount must be positive")
        except ValueError:
            await update.message.reply_text(
                "Invalid amount. Usage: /invoice <amount in INR>, e.g. /invoice 30000"
            )
            return

    try:
        result = run_pipeline(inr_amount=inr_amount)
        with result.pdf_path.open("rb") as fh:
            await chat.send_document(document=fh, filename=result.pdf_path.name)
        log.info(
            "Sent invoice %s (INR %.2f) to chat %s",
            result.invoice_number,
            result.amount_inr,
            chat.id,
        )
    except Exception as exc:
        log.exception("Bot /invoice failed")
        await update.message.reply_text(f"Workflow failed:\n{exc}")


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("invoice", invoice))
    log.info("Telegram bot running — waiting for /invoice…")
    app.run_polling()


if __name__ == "__main__":
    main()
