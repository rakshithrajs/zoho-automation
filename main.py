"""Entry point: run the weekly invoice pipeline end-to-end."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import requests

from auth import ZohoAuth
from config import AppConfig, load_config
from email_service import send_invoice_email
from invoice import ZohoInvoiceClient
from logger import get_logger
from telegram_service import send_invoice_telegram

log = get_logger("zoho_automation.main")


@dataclass
class InvoiceRun:
    invoice_id: str
    invoice_number: str
    invoice_date: str
    amount_inr: float
    pdf_path: Path


def run_pipeline(
    cfg: AppConfig | None = None,
    inr_amount: float | None = None,
) -> InvoiceRun:
    """Create + mark paid + download PDF. No notifications. Returns the result."""
    cfg = cfg or load_config()
    amount = inr_amount if inr_amount is not None else cfg.inr_amount
    session = requests.Session()

    auth = ZohoAuth(cfg.zoho, session=session)
    invoices = ZohoInvoiceClient(cfg.zoho, auth, session=session)

    invoice = invoices.create_invoice(
        inr_amount=amount,
        line_item_name=cfg.line_item_name,
    )

    invoices.mark_as_paid_cash(
        invoice_id=invoice["invoice_id"],
        amount=invoice["_inr_amount"],
        invoice_date=invoice["_invoice_date"],
    )

    invoice_number = invoice.get("invoice_number", invoice["invoice_id"])
    pdf_path = invoices.download_pdf(
        invoice_id=invoice["invoice_id"],
        invoice_number=invoice_number,
    )

    return InvoiceRun(
        invoice_id=invoice["invoice_id"],
        invoice_number=invoice_number,
        invoice_date=invoice["_invoice_date"],
        amount_inr=invoice["_inr_amount"],
        pdf_path=pdf_path,
    )


def run(inr_amount: float | None = None) -> int:
    """CLI entry point: runs the pipeline and emails + telegrams the PDF."""
    log.info("=== Weekly invoice automation started ===")
    try:
        cfg = load_config()
        result = run_pipeline(cfg, inr_amount=inr_amount)

        send_invoice_email(
            cfg.email,
            pdf_path=result.pdf_path,
            invoice_number=result.invoice_number,
            invoice_date=result.invoice_date,
            amount_inr=result.amount_inr,
        )

        send_invoice_telegram(
            cfg.telegram,
            pdf_path=result.pdf_path,
            invoice_number=result.invoice_number,
            invoice_date=result.invoice_date,
            amount_inr=result.amount_inr,
        )

        log.info("=== Weekly invoice automation completed successfully ===")
        return 0
    except Exception as exc:
        log.exception("Weekly invoice automation FAILED: %s", exc)
        return 1


if __name__ == "__main__":
    cli_amount = float(sys.argv[1]) if len(sys.argv) > 1 else None
    sys.exit(run(inr_amount=cli_amount))
