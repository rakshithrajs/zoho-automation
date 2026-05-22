"""Send the invoice PDF to a Telegram chat via python-telegram-bot."""
from __future__ import annotations

import asyncio
from pathlib import Path

from telegram import Bot
from telegram.request import HTTPXRequest

from config import TelegramConfig
from logger import get_logger

log = get_logger(__name__)


async def _send(cfg: TelegramConfig, pdf_path: Path, caption: str) -> None:
    # Bump timeouts — invoice PDFs can be a few MB and Telegram occasionally lags.
    request = HTTPXRequest(connect_timeout=20, read_timeout=60, write_timeout=60)
    bot = Bot(token=cfg.bot_token, request=request)
    with pdf_path.open("rb") as fh:
        await bot.send_document(
            chat_id=cfg.chat_id,
            document=fh,
            filename=pdf_path.name,
            caption=caption,
        )


def send_invoice_telegram(
    cfg: TelegramConfig,
    pdf_path: Path,
    invoice_number: str,
    invoice_date: str,
    amount_inr: float,
) -> None:
    """Send the invoice PDF as a Telegram document with a summary caption."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"Invoice PDF not found: {pdf_path}")

    caption = (
        f"Invoice {invoice_number}\n"
        f"Date: {invoice_date}\n"
        f"Amount: INR {amount_inr:.2f}"
    )

    asyncio.run(_send(cfg, pdf_path, caption))
    log.info(
        "Invoice sent to Telegram chat %s with attachment %s",
        cfg.chat_id,
        pdf_path.name,
    )
