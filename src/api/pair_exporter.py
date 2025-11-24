from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from src.api.data_fetcher import PairMeta


def export_pairs_csv(pairs: Iterable[PairMeta], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["altname", "wsname", "base", "quote", "is_solana"])
        writer.writeheader()
        for p in pairs:
            writer.writerow(
                {
                    "altname": p.altname,
                    "wsname": p.wsname,
                    "base": p.base,
                    "quote": p.quote,
                    "is_solana": p.is_solana,
                }
            )
