"""
Market-structure building blocks implementing the core rules from the
Malaysian SNR / SLK PDF.
"""

from dataclasses import dataclass
from typing import List, Optional
import pandas as pd

import config


@dataclass
class SwingPoint:
    index: int
    time: object
    price: float
    kind: str  # "high" or "low"
    fresh: bool = True
    uses: int = 0
    broken: bool = False
    last_touch_time: object = None  # most recent wick-touch (rejection) time


def find_swings(df: pd.DataFrame, lookback: int = config.SWING_LOOKBACK) -> List[SwingPoint]:
    swings = []
    n = len(df)
    for i in range(lookback, n - lookback):
        window_high = df["high"].iloc[i - lookback: i + lookback + 1]
        window_low = df["low"].iloc[i - lookback: i + lookback + 1]
        if df["high"].iloc[i] == window_high.max():
            swings.append(SwingPoint(index=i, time=df["time"].iloc[i],
                                      price=df["high"].iloc[i], kind="high"))
        if df["low"].iloc[i] == window_low.min():
            swings.append(SwingPoint(index=i, time=df["time"].iloc[i],
                                      price=df["low"].iloc[i], kind="low"))
    swings.sort(key=lambda s: s.index)
    return swings


def last_bos_trend(df: pd.DataFrame, swings: List[SwingPoint]) -> Optional[str]:
    trend = None
    for i in range(len(df)):
        prior_highs = [s for s in swings if s.kind == "high" and s.index < i]
        prior_lows = [s for s in swings if s.kind == "low" and s.index < i]
        ref_high = prior_highs[-1].price if prior_highs else None
        ref_low = prior_lows[-1].price if prior_lows else None

        close = df["close"].iloc[i]
        if ref_high is not None and close > ref_high:
            trend = "bullish"
        if ref_low is not None and close < ref_low:
            trend = "bearish"
    return trend


def track_freshness(swings: List[SwingPoint], df: pd.DataFrame):
    for s in swings:
        s.fresh, s.uses, s.broken, s.last_touch_time = True, 0, False, None

    for i in range(len(df)):
        h, l, c = df["high"].iloc[i], df["low"].iloc[i], df["close"].iloc[i]
        for s in swings:
            if s.index >= i:
                continue
            if s.kind == "high":
                touched = h >= s.price
                broken_by_body = c > s.price
            else:
                touched = l <= s.price
                broken_by_body = c < s.price

            if not touched:
                continue

            if broken_by_body:
                s.broken = True
                s.fresh = True
                s.uses = 0
                s.last_touch_time = None
            elif s.uses < 2:
                s.uses += 1
                s.fresh = False
                s.last_touch_time = df["time"].iloc[i]
