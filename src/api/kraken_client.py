from __future__ import annotations

import logging
import time
from typing import Any, Dict, Tuple

import requests

from config import settings


logger = logging.getLogger(__name__)


class KrakenPublicClient:
    """Lightweight public Kraken client (no auth needed for OHLC/asset pairs)."""

    def __init__(self, base_url: str = "https://api.kraken.com/0/public", session: requests.Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self._last_call_ts = 0.0

    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        self._respect_rate_limit()
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        errors = data.get("error") or []
        if errors:
            raise RuntimeError(f"Kraken API error for {path}: {errors}")
        return data["result"]

    def _respect_rate_limit(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_call_ts
        min_interval = settings.PUBLIC_MIN_INTERVAL_SEC
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call_ts = time.monotonic()

    def get_asset_pairs(self) -> Dict[str, Any]:
        """Return the full AssetPairs map."""
        return self._get("AssetPairs")

    def get_assets(self) -> Dict[str, Any]:
        """Return the full Assets map (asset info)."""
        return self._get("Assets")

    def get_ohlc(self, pair: str, interval: int, since: int | None = None) -> Tuple[list, int | None]:
        """Fetch OHLC for a pair at the given interval (minutes)."""
        params: Dict[str, Any] = {"pair": pair, "interval": interval}
        if since is not None:
            params["since"] = int(since)
        result = self._get("OHLC", params=params)
        # The pair key is dynamic in the response; pick the first key that isn't "last".
        pair_key = next((k for k in result.keys() if k != "last"), None)
        if pair_key is None:
            raise RuntimeError("Unexpected OHLC response: missing pair data")
        return result[pair_key], result.get("last")
