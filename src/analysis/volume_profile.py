from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pandas as pd


@dataclass
class VolumeProfileResult:
    poc: float
    vah: float
    val: float
    bin_edges: np.ndarray
    histogram: np.ndarray


def compute_volume_profile(df: pd.DataFrame, bins: int = 30, target_value_area: float = 0.7) -> VolumeProfileResult:
    """Approximate volume profile using price histogram weighted by volume."""
    if df.empty or df["volume"].sum() == 0:
        return VolumeProfileResult(poc=float("nan"), vah=float("nan"), val=float("nan"), bin_edges=np.array([]), histogram=np.array([]))

    prices = df["close"].to_numpy()
    volumes = df["volume"].to_numpy()
    hist, edges = np.histogram(prices, bins=bins, weights=volumes)

    if hist.sum() == 0:
        return VolumeProfileResult(poc=float("nan"), vah=float("nan"), val=float("nan"), bin_edges=edges, histogram=hist)

    poc_idx = int(hist.argmax())
    poc_price = _bin_midpoint(edges, poc_idx)
    vah, val = _value_area_bounds(hist, edges, poc_idx, target_value_area)

    return VolumeProfileResult(poc=poc_price, vah=vah, val=val, bin_edges=edges, histogram=hist)


def _bin_midpoint(edges: np.ndarray, idx: int) -> float:
    return float((edges[idx] + edges[idx + 1]) / 2.0)


def _value_area_bounds(hist: np.ndarray, edges: np.ndarray, poc_idx: int, target: float) -> Tuple[float, float]:
    total = hist.sum()
    included = {poc_idx}
    left = poc_idx - 1
    right = poc_idx + 1
    volume_accum = hist[poc_idx]

    while volume_accum / total < target and (left >= 0 or right < len(hist)):
        left_vol = hist[left] if left >= 0 else -1
        right_vol = hist[right] if right < len(hist) else -1

        if right_vol >= left_vol and right < len(hist):
            included.add(right)
            volume_accum += hist[right]
            right += 1
        elif left >= 0:
            included.add(left)
            volume_accum += hist[left]
            left -= 1
        else:
            break

    lower_idx = min(included)
    upper_idx = max(included)
    return edges[upper_idx + 1], edges[lower_idx]
