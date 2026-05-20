"""USD → INR exchange rate lookups via the Frankfurter API."""
from __future__ import annotations

import time
from typing import Optional

import requests

from logger import get_logger

log = get_logger(__name__)


def fetch_usd_to_inr(api_url: str, session: Optional[requests.Session] = None) -> float:
    """Return the latest USD→INR rate, retrying transient failures."""
    sess = session or requests.Session()
    last_err: Optional[Exception] = None

    for attempt in range(1, 4):
        try:
            resp = sess.get(api_url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                rate = data.get("rates", {}).get("INR")
                if not rate:
                    raise RuntimeError(f"Unexpected exchange rate payload: {data}")
                log.info("Fetched USD→INR rate: %s", rate)
                return float(rate)
            last_err = RuntimeError(
                f"Exchange API returned {resp.status_code}: {resp.text}"
            )
        except requests.RequestException as exc:
            last_err = exc
        log.warning("Exchange-rate attempt %d failed: %s", attempt, last_err)
        time.sleep(2 * attempt)

    raise RuntimeError(f"Failed to fetch USD→INR rate: {last_err}")

if __name__ == "__main__":
    # Quick test of the exchange rate fetcher
    try:
        rate = fetch_usd_to_inr("https://api.frankfurter.app/latest?from=USD&to=INR")
        print(f"Current USD→INR rate: {rate}")
    except Exception as exc:
        print(f"Error fetching exchange rate: {exc}")