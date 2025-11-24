from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from src.scoring.coin_ranker import TimeframeOutcome


@dataclass
class PairResult:
    pair: str
    wsname: str
    score: float
    is_solana: bool
    outcomes: List[TimeframeOutcome]
    frames: Dict[str, pd.DataFrame]
