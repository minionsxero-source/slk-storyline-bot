"""
Storyline detection, exactly per the SLK / Malaysian SNR method:

  1. Find the current trend via the LAST BOS on the higher timeframe.
  2. Find the most recent fresh swing level that has been touched and
     REJECTED (wick-touch + close back = "rejection candle with closing",
     which also flips that level to unfresh).
  3. Drop ONE timeframe lower and wait for an EXTERNAL breakout: a candle
     body closing beyond the last swing point that existed BEFORE the
     higher-timeframe rejection (internal breakouts formed after the
     rejection don't count).
  4. If steps 2 and 3 both happen in the trend's direction -> the
     storyline is CONFIRMED.

This module intentionally stops at the storyline. It never computes an
entry, stop loss, or take profit.
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd

import structure


@dataclass
class StorylineResult:
    symbol: str
    higher_tf: str
    lower_tf: str
    direction: Optional[str]          # "bullish" / "bearish" / None
    rejection_time: Optional[object]
    breakout_time: Optional[object]
    confirmed: bool


def evaluate_storyline(symbol: str, higher_tf: str, lower_tf: str,
                        htf_df: pd.DataFrame, ltf_df: pd.DataFrame) -> StorylineResult:

    htf_swings = structure.find_swings(htf_df)
    structure.track_freshness(htf_swings, htf_df)
    trend = structure.last_bos_trend(htf_df, htf_swings)

    if trend is None:
        return StorylineResult(symbol, higher_tf, lower_tf, None, None, None, False)

    # bearish storyline rejects off a swing HIGH; bullish rejects off a swing LOW
    rejection_kind = "high" if trend == "bearish" else "low"

    # most recent level of that kind that has been touched (rejected) and not broken
    candidates = [s for s in htf_swings if s.kind == rejection_kind
                  and s.uses >= 1 and not s.broken]
    if not candidates:
        return StorylineResult(symbol, higher_tf, lower_tf, trend, None, None, False)

    rejection_level = candidates[-1]
    rejection_time = rejection_level.time

    ltf_after = ltf_df[ltf_df["time"] >= rejection_time].reset_index(drop=True)
    if len(ltf_after) < 5:
        return StorylineResult(symbol, higher_tf, lower_tf, trend, rejection_time, None, False)

    # the "external" reference = last LTF swing that existed BEFORE the HTF rejection
    ltf_swings_before = [s for s in structure.find_swings(ltf_df) if s.time < rejection_time]
    kind_needed = "high" if trend == "bullish" else "low"
    ext_candidates = [s for s in ltf_swings_before if s.kind == kind_needed]
    if not ext_candidates:
        return StorylineResult(symbol, higher_tf, lower_tf, trend, rejection_time, None, False)

    external_level = ext_candidates[-1].price

    breakout_time = None
    for i in range(len(ltf_after)):
        close = ltf_after["close"].iloc[i]
        if trend == "bullish" and close > external_level:
            breakout_time = ltf_after["time"].iloc[i]
            break
        if trend == "bearish" and close < external_level:
            breakout_time = ltf_after["time"].iloc[i]
            break

    confirmed = breakout_time is not None
    return StorylineResult(symbol, higher_tf, lower_tf, trend, rejection_time, breakout_time, confirmed)
