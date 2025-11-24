from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from config import settings
from src.api.kraken_client import KrakenPublicClient


logger = logging.getLogger(__name__)


@dataclass
class PairMeta:
    altname: str
    wsname: str
    base: str
    quote: str
    is_solana: bool = False


def _normalize_base(altname: str, base: str) -> str:
    if altname.endswith("USD"):
        return altname[:-3]
    if base:
        return base.lstrip("X").lstrip("Z")
    return altname


def _is_usd_spot_pair(info: Dict[str, any]) -> bool:
    wsname = info.get("wsname", "")
    altname = info.get("altname", "")
    quote = info.get("quote", "")
    if altname.endswith(".d"):  # dark pool
        return False
    if quote not in {"ZUSD", "USD"} and not altname.endswith("USD") and "/USD" not in wsname:
        return False
    # crude spot filter: futures/swaps typically expose "trade" or "margin" flags; keep aclass currency only
    if info.get("aclass_base") and info.get("aclass_base") != "currency":
        return False
    return True


def discover_usd_pairs(client: KrakenPublicClient) -> List[PairMeta]:
    """Return USD spot pairs with metadata, forcing whitelist inclusion."""
    pairs = client.get_asset_pairs()
    metas: List[PairMeta] = []
    for _, info in pairs.items():
        if not _is_usd_spot_pair(info):
            continue
        wsname = info.get("wsname", "") or info.get("altname", "")
        altname = info.get("altname", "")
        quote = info.get("quote", "")
        base = info.get("base", "")
        base_symbol = _normalize_base(altname, base).upper()
        is_solana = base_symbol == "SOL" or base_symbol in settings.SOL_MEME_BASES
        metas.append(
            PairMeta(
                altname=altname,
                wsname=wsname,
                base=base_symbol,
                quote=quote if quote else "USD",
                is_solana=is_solana,
            )
        )

    # Ensure whitelist members are present
    whitelist_missing = settings.PAIR_WHITELIST - {m.altname for m in metas}
    for altname in whitelist_missing:
        metas.append(PairMeta(altname=altname, wsname=f"{altname[:-3]}/USD", base=_normalize_base(altname, ""), quote="USD"))

    return metas


def write_pairs_csv(pairs: List[PairMeta], path: Path | None = None) -> Path:
    """Persist discovered USD pairs to CSV."""
    target = path or settings.PAIRS_CSV
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in pairs:
        rows.append(
            {
                "altname": p.altname,
                "wsname": p.wsname,
                "base": p.base,
                "quote": p.quote,
                "is_solana": p.is_solana,
            }
        )
    pd.DataFrame(rows).to_csv(target, index=False)
    return target


def export_pairs_to_csv(pairs: List[PairMeta], path: Path | None = None) -> Path:
    """Persist discovered USD spot pairs for later runs/reference."""
    path = path or settings.PAIRS_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in pairs:
        rows.append(
            {
                "altname": p.altname,
                "wsname": p.wsname,
                "base": p.base,
                "quote": p.quote,
                "is_solana": p.is_solana,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _cache_path(pair: str, tf: str) -> Path:
    filename = settings.CACHE_FILE_TEMPLATE.format(pair=pair, tf=tf)
    return settings.CACHE_DIR / filename


def _load_state() -> dict:
    if settings.STATE_FILE.exists():
        try:
            return pd.read_json(settings.STATE_FILE).to_dict()
        except Exception:  # noqa: BLE001
            logger.warning("Failed to read state file, starting fresh: %s", settings.STATE_FILE)
    return {}


def _save_state(state: dict) -> None:
    settings.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        pd.DataFrame(state).to_json(settings.STATE_FILE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to persist state file %s: %s", settings.STATE_FILE, exc)


def _state_key(pair: str, tf: str) -> str:
    return f"{pair}_{tf}"


def _is_cache_fresh(path: Path, ttl: timedelta) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return datetime.now(tz=timezone.utc) - mtime < ttl


def _kraken_ts(days_back: Optional[int]) -> Optional[int]:
    if days_back is None:
        return None
    ts = datetime.now(tz=timezone.utc) - timedelta(days=days_back)
    return int(ts.timestamp())


def fetch_ohlc(
    client: KrakenPublicClient,
    pair: PairMeta,
    tf: str,
    refresh: bool = False,
) -> pd.DataFrame:
    """Fetch OHLCV for a pair+timeframe with caching and optional resample."""
    cfg = settings.TIMEFRAMES[tf]
    cache_file = _cache_path(pair.altname, tf)
    state = _load_state()
    state_key = _state_key(pair.altname, tf)

    # If cache is fresh, return early.
    if not refresh and _is_cache_fresh(cache_file, cfg.cache_ttl):
        return pd.read_parquet(cache_file)

    # Determine since timestamp for incremental pull.
    since = _kraken_ts(cfg.history_days)
    base_df = None
    if cache_file.exists() and not refresh:
        base_df = pd.read_parquet(cache_file)
        if not base_df.empty:
            last_ts = int(base_df["time"].max().timestamp())
            # subtract one interval to avoid gaps
            since = max(since or last_ts, last_ts - cfg.interval_minutes * 60)

    raw, _ = client.get_ohlc(pair=pair.altname, interval=cfg.interval_minutes, since=since)
    df = pd.DataFrame(
        raw,
        columns=["time", "open", "high", "low", "close", "vwap", "volume", "count"],
    )
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    numeric_cols = ["open", "high", "low", "close", "vwap", "volume"]
    df[numeric_cols] = df[numeric_cols].astype(float)
    df["count"] = df["count"].astype(int)
    df = df.sort_values("time").reset_index(drop=True)

    # Merge with existing cache if present
    if base_df is not None and not base_df.empty:
        df = pd.concat([base_df, df], ignore_index=True)
        df = df.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)

    if cfg.resample_rule:
        df = _resample_ohlc(df, cfg.resample_rule)

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_file, index=False)

    # Update state with latest timestamp (seconds)
    if not df.empty:
        state[state_key] = {"last_ts": int(df["time"].max().timestamp())}
        _save_state(state)
    return df


def _resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample OHLCV using pandas rules (e.g., 'M' for month-end)."""
    resampled = (
        df.set_index("time")
        .resample(rule)
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "vwap": "mean", "volume": "sum", "count": "sum"})
        .dropna()
        .reset_index()
    )
    return resampled


def export_pairs_to_csv(pairs: List[PairMeta], path: Path | None = None) -> Path:
    """Write discovered USD pairs to CSV for reference."""
    path = path or settings.PAIRS_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        [
            {
                "altname": p.altname,
                "wsname": p.wsname,
                "base": p.base,
                "quote": p.quote,
                "is_solana": p.is_solana,
            }
            for p in pairs
        ]
    )
    df.to_csv(path, index=False)
    return path
