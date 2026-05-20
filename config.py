"""Centralised configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
INVOICE_DIR = PROJECT_ROOT / "invoices"
LOG_DIR = PROJECT_ROOT / "logs"
INVOICE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)


def _required(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


@dataclass(frozen=True)
class ZohoConfig:
    base_url: str
    accounts_url: str
    org_id: str
    client_id: str
    client_secret: str
    refresh_token: str
    customer_id: str


@dataclass(frozen=True)
class EmailConfig:
    smtp_host: str
    smtp_port: int
    username: str
    app_password: str
    recipient: str


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str


@dataclass(frozen=True)
class AppConfig:
    zoho: ZohoConfig
    email: EmailConfig
    telegram: TelegramConfig
    usd_amount: float
    line_item_name: str
    exchange_api_url: str


def load_config() -> AppConfig:
    zoho = ZohoConfig(
        base_url=os.getenv("ZOHO_BASE_URL", "https://www.zohoapis.in/invoice/v3"),
        accounts_url=os.getenv("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.in"),
        org_id=_required("ZOHO_ORG_ID"),
        client_id=_required("ZOHO_CLIENT_ID"),
        client_secret=_required("ZOHO_CLIENT_SECRET"),
        refresh_token=_required("ZOHO_REFRESH_TOKEN"),
        customer_id=_required("ZOHO_CUSTOMER_ID"),
    )
    email = EmailConfig(
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "465")),
        username=_required("GMAIL_USERNAME"),
        app_password=_required("GMAIL_APP_PASSWORD"),
        recipient=os.getenv("EMAIL_RECIPIENT") or _required("GMAIL_USERNAME"),
    )
    telegram = TelegramConfig(
        bot_token=_required("TELEGRAM_BOT_TOKEN"),
        chat_id=_required("TELEGRAM_CHAT_ID"),
    )
    return AppConfig(
        zoho=zoho,
        email=email,
        telegram=telegram,
        usd_amount=float(os.getenv("USD_AMOUNT", "350")),
        line_item_name=os.getenv("LINE_ITEM_NAME", "Weekly Development Work"),
        exchange_api_url=os.getenv(
            "EXCHANGE_API_URL", "https://api.frankfurter.app/latest?from=USD&to=INR"
        ),
    )
