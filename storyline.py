"""
Storyline detection per the SLK / Malaysian SNR method (daily-bias chain),
a standalone daily-sweep + H4-breakout rule, and a weekly/daily key-level
confluence check layered onto the sweep rule.
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd

import structure
import config


@dataclass
class StorylineResult:
    symbol: str
    higher_tf: str
    lower_tf: str
    direction: Optional[str]
    rejection_time: Optional[object]
    rejection_price: Optional[float]
    level_formed_time: Optional[object]
    breakout_time: Optional[object]
    breakout_price: Optional[float]
    swept_level: Optional[float]
    confirmed: bool


@dataclass
class SweepResult:
    symbol: str
    direction: Optional[str]
    sweep_time: Optional[object]
    swept_level: Optional[float]
    sweep_type: Optional[str]  # "high" or "low"
    breakout_time: Optional[object]
    breakout_price: Optional[float]
    confirmed: bool
    # confluence extras
    confluence: bool = False
    weekly_level_price: Optional[float] = None
    weekly_level_time: Optional[object] = None
    daily_level_price: Optional[float] = None
    daily_level_time: Optional[object] = None


def _find_external_breakout(ltf_df: pd.DataFrame, after_time, trend: str):
    ltf_after = ltf_df[ltf_df["time"] >= after_time].reset_index(drop=True)
    if len(ltf_after) < 5:
        return None, None, None

    ltf_swings_before = [s for s in structure.find_swings(ltf_df) if s.time < after_time]
    kind_needed = "high" if trend == "bullish" else "low"
    ext_candidates = [s for s in ltf_swings_before if s.kind == kind_needed]
    if not ext_candidates:
        return None, None, None

    external_level = ext_candidates[-1].price
    for i in range(len(ltf_after)):
        close = ltf_after["close"].iloc[i]
        if trend == "bullish" and close > external_level:
            return ltf_after["time"].iloc[i], close, external_level
        if trend == "bearish" and close < external_level:
            return ltf_after["time"].iloc[i], close, external_level

    return None, None, external_level


def _nearby_level(swings, price, kind, tolerance_pct, require_touched=True):
    """Closest swing of `kind` within tolerance_pct% of `price` (or None)."""
    tol = price * (tolerance_pct / 100)
    matches = [s for s in swings if s.kind == kind and abs(s.price - price) <= tol
               and (not require_touched or s.uses >= 1)]
    if not matches:
        return None
    return min(matches, key=lambda s: abs(s.price - price))


def _empty_storyline(symbol, higher_tf, lower_tf, direction=None,
                      rejection_time=None, rejection_price=None, level_formed_time=None):
    return StorylineResult(symbol, higher_tf, lower_tf, direction,
                            rejection_time, rejection_price, level_formed_time,
                            None, None, None, False)


def evaluate_storyline(symbol: str, higher_tf: str, lower_tf: str,
                        htf_df: pd.DataFrame, ltf_df: pd.DataFrame) -> StorylineResult:

    htf_swings = structure.find_swings(htf_df)
    structure.track_freshness(htf_swings, htf_df)
    trend = structure.last_bos_trend(htf_df, htf_swings)

    if trend is None:
        return _empty_storyline(symbol, higher_tf, lower_tf, None)

    rejection_kind = "high" if trend == "bearish" else "low"
    candidates = [s for s in htf_swings if s.kind == rejection_kind
                  and s.uses >= 1 and not s.broken]
    if not candidates:
        return _empty_storyline(symbol, higher_tf, lower_tf, trend)

    rejection_level = candidates[-1]
    rejection_time = rejection_level.last_touch_time or rejection_level.time
    level_formed_time = rejection_level.time
    rejection_price = rejection_level.price

    breakout_time, breakout_price, external_level = _find_external_breakout(ltf_df, rejection_time, trend)

    confirmed = breakout_time is not None
    return StorylineResult(symbol, higher_tf, lower_tf, trend,
                            rejection_time, rejection_price, level_formed_time,
                            breakout_time, breakout_price, external_level, confirmed)


def evaluate_daily_sweep_breakout(symbol: str, w1_df: pd.DataFrame, d1_df: pd.DataFrame,
                                   h4_df: pd.DataFrame, lookback_days: int = 5,
                                   tolerance_pct: float = None) -> SweepResult:
    """
    Rule 2: a daily candle sweeps the previous daily candle's high/low
    (wicks beyond it, closes back on the origin side) and H4 confirms an
    external breakout in that direction.

    Layered on top: if that same sweep price also sits on (within
    tolerance) a proper WEEKLY key level (A/V-shape swing) AND a proper
    DAILY key level (A-shape swing), that's flagged as a confluence.
    """
    if tolerance_pct is None:
        tolerance_pct = config.CONFLUENCE_TOLERANCE_PCT

    n = len(d1_df)
    earliest_i = max(1, n - lookback_days)

    for i in range(n - 1, earliest_i - 1, -1):
        cur = d1_df.iloc[i]
        prev = d1_df.iloc[i - 1]

        direction = swept_level = sweep_time = sweep_type = None
        if cur["high"] > prev["high"] and cur["close"] < prev["high"]:
            direction, swept_level, sweep_time, sweep_type = "bearish", prev["high"], cur["time"], "high"
        elif cur["low"] < prev["low"] and cur["close"] > prev["low"]:
            direction, swept_level, sweep_time, sweep_type = "bullish", prev["low"], cur["time"], "low"

        if direction is None:
            continue

        breakout_time, breakout_price, _ = _find_external_breakout(h4_df, sweep_time, direction)
        confirmed = breakout_time is not None

        # --- confluence check ---
        w1_swings = structure.find_swings(w1_df)
        structure.track_freshness(w1_swings, w1_df)
        d1_swings = structure.find_swings(d1_df)
        structure.track_freshness(d1_swings, d1_df)

        weekly_match = _nearby_level(w1_swings, swept_level, sweep_type, tolerance_pct)
        daily_match = _nearby_level(d1_swings, swept_level, sweep_type, tolerance_pct)
        confluence = weekly_match is not None and daily_match is not None

        return SweepResult(
            symbol, direction, sweep_time, swept_level, sweep_type,
            breakout_time, breakout_price, confirmed,
            confluence=confluence,
            weekly_level_price=weekly_match.price if weekly_match else None,
            weekly_level_time=weekly_match.time if weekly_match else None,
            daily_level_price=daily_match.price if daily_match else None,
            daily_level_time=daily_match.time if daily_match else None,
        )

    return SweepResult(symbol, None, None, None, None, None, None, False)
