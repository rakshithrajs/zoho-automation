# Zoho Weekly Invoice Automation

Automates the weekly workflow:

1. Fetch live USD → INR rate (Frankfurter API).
2. Create an INR invoice in Zoho Invoice (India region).
3. Download the invoice PDF.
4. Email the PDF to yourself via Gmail SMTP.
5. Log every step to console and rotating file logs.

## Project layout

```
zoho-automation/
├── auth.py              # Zoho OAuth refresh-token flow
├── config.py            # Loads .env into typed config
├── email_service.py     # Gmail SMTP (SSL) sender
├── exchange_rate.py     # Frankfurter USD→INR fetcher (with retries)
├── invoice.py           # Create invoice + download PDF
├── logger.py            # Console + rotating-file logger
├── main.py              # Pipeline entry point
├── pyproject.toml       # uv-managed dependencies
├── .env.example
├── invoices/            # Saved invoice PDFs (gitignored)
└── logs/                # automation.log (gitignored, rotated)
```

## Setup

```powershell
uv sync
copy .env.example .env   # then fill in real values
```

### 1. Zoho credentials

1. Go to <https://api-console.zoho.in/> and create a **Self Client** (or Server-based App).
2. Note the `Client ID` and `Client Secret`.
3. Generate an authorization code with scope:
   `ZohoInvoice.invoices.CREATE,ZohoInvoice.invoices.READ,ZohoInvoice.contacts.READ`
4. Exchange the code for a **refresh token** (one-time):
   ```
   POST https://accounts.zoho.in/oauth/v2/token
       grant_type=authorization_code
       client_id=...
       client_secret=...
       redirect_uri=http://localhost:8080
       code=...
   ```
   Save the returned `refresh_token` into `.env` as `ZOHO_REFRESH_TOKEN`.
5. From the Zoho Invoice dashboard, copy the **Organization ID** → `ZOHO_ORG_ID`.
6. Fetch your customer ID once (e.g. `GET /invoice/v3/customers?organization_id=...`)
   and put it in `ZOHO_CUSTOMER_ID`.

The refresh token does **not** expire (unless revoked); access tokens are
auto-refreshed every run and on `401` responses.

### 2. Gmail App Password

1. Enable 2-Step Verification on the Google account.
2. Visit <https://myaccount.google.com/apppasswords>.
3. Create a 16-character app password for "Mail".
4. Put it in `.env` as `GMAIL_APP_PASSWORD` (no spaces).

### 3. Run locally

```powershell
uv run python main.py
```

A successful run prints the invoice ID, INR amount, and exchange rate to
the console and `logs/automation.log`, saves the PDF under `invoices/`,
and emails it to `EMAIL_RECIPIENT`.

## Scheduling weekly runs

### Windows Task Scheduler

1. Open **Task Scheduler → Create Task**.
2. **General**: name `ZohoWeeklyInvoice`; check *Run whether user is logged on or not*.
3. **Triggers**: New → Weekly → e.g. Monday 09:00.
4. **Actions**: New → Start a program
   - Program/script: `uv`
   - Add arguments: `run python main.py`
   - Start in: `D:\zoho-automation`
5. **Conditions**: uncheck "Start only on AC power" if on a laptop.
6. Save (Windows will prompt for the account password).

Quick test from the command line:
```powershell
schtasks /Run /TN ZohoWeeklyInvoice
```

### Linux/macOS cron

```cron
# Every Monday at 09:00
0 9 * * 1 cd /path/to/zoho-automation && uv run python main.py >> logs/cron.log 2>&1
```

## Security notes

- `.env` is gitignored; never commit it. Rotate the Zoho refresh token and
  Gmail app password if they ever land in git history.
- Logs only record invoice IDs, amounts, and exchange rates — no secrets.
- All HTTP calls use TLS; SMTP uses `SMTP_SSL` on port 465.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Missing required environment variable: …` | `.env` not loaded or key missing. |
| `Zoho token endpoint returned 400` | Refresh token revoked or wrong region (`accounts.zoho.in` vs `.com`). |
| `Invoice creation failed (400)` | Bad `customer_id` or currency not enabled in the org. |
| `PDF download returned 404` | Invoice ID wrong, or PDF not yet generated — automatic retry handles this. |
| SMTP `535` auth error | Using the Google account password instead of an App Password. |
