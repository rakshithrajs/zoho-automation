"""Zoho Invoice operations: create invoice and download its PDF."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from auth import ZohoAuth
from config import INVOICE_DIR, ZohoConfig
from logger import get_logger

log = get_logger(__name__)


@dataclass
class InvoiceResult:
    invoice_id: str
    invoice_number: str
    amount_inr: float
    invoice_date: str
    pdf_path: Path


class ZohoInvoiceClient:
    def __init__(
        self,
        cfg: ZohoConfig,
        auth: ZohoAuth,
        session: Optional[requests.Session] = None,
    ):
        self._cfg = cfg
        self._auth = auth
        self._session = session or requests.Session()

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """HTTP wrapper that adds auth + org_id and retries once on 401."""
        url = f"{self._cfg.base_url}{path}"
        params = kwargs.pop("params", {}) or {}
        params.setdefault("organization_id", self._cfg.org_id)

        for attempt in range(2):
            headers = {**self._auth.auth_headers(), **kwargs.pop("headers", {})}
            resp = self._session.request(
                method, url, params=params, headers=headers, timeout=30, **kwargs
            )
            if resp.status_code == 401 and attempt == 0:
                log.warning("Got 401 from Zoho; forcing token refresh")
                self._auth.get_access_token(force_refresh=True)
                continue
            return resp
        return resp  # type: ignore[return-value]

    def create_invoice(
        self,
        inr_amount: float,
        line_item_name: str,
    ) -> dict:
        inr_amount = round(inr_amount, 2)
        today = datetime.now().strftime("%Y-%m-%d")
        payload = {
            "customer_id": self._cfg.customer_id,
            "date": today,
            "currency_code": "INR",
            "line_items": [
                {"name": line_item_name, "rate": inr_amount, "quantity": 1}
            ],
            "notes": f"Auto-generated invoice. INR total: {inr_amount}.",
        }

        resp = self._request("POST", "/invoices", json=payload)
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Invoice creation failed ({resp.status_code}): {resp.text}"
            )

        invoice = resp.json().get("invoice")
        if not invoice or "invoice_id" not in invoice:
            raise RuntimeError(f"Unexpected invoice response: {resp.text}")

        log.info(
            "Invoice created | id=%s number=%s amount_inr=%s",
            invoice["invoice_id"],
            invoice.get("invoice_number"),
            inr_amount,
        )
        invoice["_inr_amount"] = inr_amount
        invoice["_invoice_date"] = today
        return invoice

    def mark_as_paid_cash(
        self,
        invoice_id: str,
        amount: float,
        invoice_date: str,
    ) -> dict:
        """Record a full cash payment against the given invoice."""
        payload = {
            "customer_id": self._cfg.customer_id,
            "payment_mode": "Cash",
            "amount": amount,
            "date": invoice_date,
            "invoices": [{"invoice_id": invoice_id, "amount_applied": amount}],
        }
        resp = self._request("POST", "/customerpayments", json=payload)
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Marking invoice paid failed ({resp.status_code}): {resp.text}"
            )
        payment = resp.json().get("payment", {})
        log.info(
            "Invoice %s marked as paid in cash | payment_id=%s amount=%s",
            invoice_id,
            payment.get("payment_id"),
            amount,
        )
        return payment

    def download_pdf(self, invoice_id: str, invoice_number: str) -> Path:
        """Download the PDF for the given invoice; retry transient failures."""
        path = f"/invoices/{invoice_id}"
        last_err: Optional[Exception] = None

        for attempt in range(1, 4):
            try:
                resp = self._request(
                    "GET",
                    path,
                    params={"accept": "pdf"},
                    headers={"Accept": "application/pdf"},
                )
                if resp.status_code == 200 and resp.content:
                    safe_number = (invoice_number or invoice_id).replace("/", "_")
                    out = INVOICE_DIR / f"{safe_number}.pdf"
                    out.write_bytes(resp.content)
                    log.info("Invoice PDF saved to %s", out)
                    return out
                last_err = RuntimeError(
                    f"PDF download returned {resp.status_code}: {resp.text[:300]}"
                )
            except requests.RequestException as exc:
                last_err = exc
            log.warning("PDF download attempt %d failed: %s", attempt, last_err)
            time.sleep(2 * attempt)

        raise RuntimeError(f"Failed to download invoice PDF: {last_err}")
