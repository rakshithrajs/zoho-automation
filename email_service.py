"""Send the invoice PDF via Gmail SMTP over SSL."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from config import EmailConfig
from logger import get_logger

log = get_logger(__name__)


def send_invoice_email(
    cfg: EmailConfig,
    pdf_path: Path,
    invoice_number: str,
    invoice_date: str,
    amount_inr: float,
    exchange_rate: float,
) -> None:
    """Email the invoice PDF to the configured recipient."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"Invoice PDF not found: {pdf_path}")

    msg = EmailMessage()
    msg["From"] = cfg.username
    msg["To"] = cfg.recipient
    msg["Subject"] = f"Weekly Invoice {invoice_number} — {invoice_date}"
    msg.set_content(
        "Hi,\n\n"
        f"Attached is the weekly invoice {invoice_number} dated {invoice_date}.\n"
        f"Amount: INR {amount_inr:.2f} (USD→INR rate used: {exchange_rate}).\n\n"
        "— Zoho Automation"
    )

    with pdf_path.open("rb") as fh:
        msg.add_attachment(
            fh.read(),
            maintype="application",
            subtype="pdf",
            filename=pdf_path.name,
        )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=context) as smtp:
        smtp.login(cfg.username, cfg.app_password)
        smtp.send_message(msg)

    log.info("Invoice email sent to %s with attachment %s", cfg.recipient, pdf_path.name)
