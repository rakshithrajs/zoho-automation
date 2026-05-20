"""Zoho OAuth2 access-token management using the refresh-token flow."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests

from config import ZohoConfig
from logger import get_logger

log = get_logger(__name__)

# Refresh slightly before the documented 1-hour expiry to avoid race conditions.
_TOKEN_TTL_SECONDS = 3500


@dataclass
class _CachedToken:
    value: str
    expires_at: float


class ZohoAuth:
    """Caches Zoho access tokens in-process and refreshes them on demand."""

    def __init__(self, cfg: ZohoConfig, session: Optional[requests.Session] = None):
        self._cfg = cfg
        self._session = session or requests.Session()
        self._token: Optional[_CachedToken] = None

    def get_access_token(self, force_refresh: bool = False) -> str:
        if not force_refresh and self._token and self._token.expires_at > time.time():
            return self._token.value

        log.info("Refreshing Zoho access token")
        url = f"{self._cfg.accounts_url}/oauth/v2/token"
        data = {
            "refresh_token": self._cfg.refresh_token,
            "client_id": self._cfg.client_id,
            "client_secret": self._cfg.client_secret,
            "grant_type": "refresh_token",
        }

        last_err: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                resp = self._session.post(url, data=data, timeout=20)
                if resp.status_code == 200:
                    payload = resp.json()
                    if "access_token" not in payload:
                        raise RuntimeError(
                            f"Token response missing access_token: {payload}"
                        )
                    self._token = _CachedToken(
                        value=payload["access_token"],
                        expires_at=time.time() + _TOKEN_TTL_SECONDS,
                    )
                    log.info("Zoho access token refreshed")
                    return self._token.value
                last_err = RuntimeError(
                    f"Zoho token endpoint returned {resp.status_code}: {resp.text}"
                )
            except requests.RequestException as exc:
                last_err = exc
            log.warning("Token refresh attempt %d failed: %s", attempt, last_err)
            time.sleep(2 * attempt)

        raise RuntimeError(f"Could not obtain Zoho access token: {last_err}")

    def auth_headers(self) -> dict:
        return {"Authorization": f"Zoho-oauthtoken {self.get_access_token()}"}


def exchange_code_for_refresh_token(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str = "http://localhost:8080",
    accounts_url: str = "https://accounts.zoho.in",
) -> dict:
    """One-time bootstrap: exchange a Zoho authorization code for a refresh token.

    Generate the `code` from the Zoho Self-Client page (it is single-use and
    valid for ~3-10 minutes). The returned dict contains `refresh_token`,
    `access_token`, `expires_in`, etc. Save `refresh_token` into your .env.
    """
    resp = requests.post(
        f"{accounts_url}/oauth/v2/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Failed to exchange code ({resp.status_code}): {resp.text}"
        )
    payload = resp.json()
    if "refresh_token" not in payload:
        raise RuntimeError(
            f"Response did not contain refresh_token (code may have already been used): {payload}"
        )
    return payload


if __name__ == "__main__":
    # Run once to mint a refresh token:
    #   uv run python auth.py <authorization_code>
    import os
    import sys

    from dotenv import load_dotenv

    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python auth.py <authorization_code>")
        sys.exit(1)

    result = exchange_code_for_refresh_token(
        code=sys.argv[1],
        client_id=os.environ["ZOHO_CLIENT_ID"],
        client_secret=os.environ["ZOHO_CLIENT_SECRET"],
        accounts_url=os.getenv("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.in"),
    )
    print("Access token:", result)
    print("Refresh token:", result["refresh_token"])
    print("Save this into .env as ZOHO_REFRESH_TOKEN")
