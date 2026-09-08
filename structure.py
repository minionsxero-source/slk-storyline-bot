"""
Market-structure building blocks implementing the core rules from the
Malaysian SNR / SLK PDF:

- Fractal swing highs/lows        -> the "SNR levels" (A-shape / V-shape /
                                      open-close shape are all just swing
                                      points at this level of abstraction).
- Fresh / Unfresh                 -> a level is FRESH until touched by a
                                      wick. A wick-touch with a close-back
                                      makes it UNFRESH (this is also the
                                      "rejection"). A level can be used
                                      (touched) at most twice
                                      (fresh -> unfresh -> fresh -> unfresh).
                                      A candle BODY closing beyond the level
                                      breaks it and it becomes fresh again.
- BOS (break of structure)        -> a candle body closes beyond the most
                                      recent prior swing high/low -> that's
                                      the current trend/bias.
- External vs internal breakout   -> a breakout only counts if the level it
                                      breaks existed BEFORE the higher
                                      timeframe rejection (i.e. it is the
                                      last "external" swing point, not a
                                      minor swing created afterwards while
                                      price was still reacting).

This is a rule-based approximation of a discretionary, visual method.
SWING_LOOKBACK and the exact freshness/rejection rules below are the knobs
to tune against your own chart reading.
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
    uses: int = 0       # number of wick-touches so far (max 2)
    broken: bool = False  # broken by a candle body close


def find_swings(df: pd.DataFrame, lookback: int = config.SWING_LOOKBACK) -> List[SwingPoint]:
    """Simple fractal swing high/low detector."""
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
    """
    Scan forward through the candles and remember the LAST time a candle body
    closed beyond the most recent prior swing high (-> bullish BOS) or swing
    low (-> bearish BOS). That's the current storyline trend/bias.
    """
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
    """
    Walk forward through the candles and update each swing point's
    fresh / unfresh / uses / broken state IN PLACE, following the PDF rules:
      - wick touch without a body close beyond it -> unfresh, uses += 1
        (a "rejection")
      - body close beyond it                      -> broken = True,
        fresh again, uses reset to 0
      - a level tops out at 2 uses before it's considered exhausted
    """
    for s in swings:
        s.fresh, s.uses, s.broken = True, 0, False

    for i in range(len(df)):
        h, l, c = df["high"].iloc[i], df["low"].iloc[i], df["close"].iloc[i]
        for s in swings:
            if s.index >= i:
                continue  # a level can't react to candles before it exists
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
            elif s.uses < 2:
                s.uses += 1
                s.fresh = False
