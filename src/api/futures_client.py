from __future__ import annotations

import logging
from requests import HTTPError
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)


class KrakenFuturesClient:
    """Lightweight client for Kraken Futures public endpoints."""

    def __init__(self, base_url: str = "https://futures.kraken.com/derivatives/api/v3", session: requests.Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "result" in data and data.get("result") != "success":
            logger.warning("Kraken Futures API returned non-success for %s: %s", path, data.get("result"))
        return data

    def get_instruments(self) -> Dict[str, Any]:
        return self._get("instruments")

    def get_tickers(self) -> Dict[str, Any]:
        return self._get("tickers")

    def get_risk_rates(self) -> Dict[str, Any]:
        # Try documented path; fall back to alternate naming.
        try:
            return self._get("risk-rate-tables")
        except HTTPError:
            try:
                return self._get("risk-rates")
            except HTTPError as exc:
                logger.warning("Risk rates endpoint not available: %s", exc)
                return {}
