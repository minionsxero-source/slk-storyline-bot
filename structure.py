"""SLK structure and A/V Key Level primitives.

A/V levels are intentionally separate from generic market structure:
- V = red candle closes at a price and the following green candle opens at
  exactly that price.
- A = green candle closes at a price and the following red candle opens at
  exactly that price.

A/V freshness is stateful. A level is fresh until touched. A later body close
through the level flips A<->V at the same price and makes the new level fresh.
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
    kind: str  # high / low


@dataclass
class AVLevel:
    index: int
    time: object
    price: float
    kind: str  # A / V
    fresh: bool = True
    touches: int = 0
    last_touch_time: object = None
    flip_time: object = None


def candle_color(row) -> Optional[str]:
    if row["close"] > row["open"]:
        return "green"
    if row["close"] < row["open"]:
        return "red"
    return None


def find_av_levels(df: pd.DataFrame) -> List[AVLevel]:
    """Create every exact A/V level from adjacent candles.

    The relationship is evaluated using the previous candle's CLOSE and the
    next candle's OPEN. Exact equality is intentional per the SLK rule.
    """
    levels: List[AVLevel] = []
    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        cur = df.iloc[i]
        prev_color = candle_color(prev)
        cur_color = candle_color(cur)
        if prev_color == "red" and cur_color == "green" and cur["open"] == prev["close"]:
            levels.append(AVLevel(i, cur["time"], float(prev["close"]), "V"))
        elif prev_color == "green" and cur_color == "red" and cur["open"] == prev["close"]:
            levels.append(AVLevel(i, cur["time"], float(prev["close"]), "A"))
    return levels


def update_av_state(levels: List[AVLevel], df: pd.DataFrame) -> None:
    """Replay candles through A/V levels and calculate their final state.

    Latest touch rule: when price touches a Key Level, that level becomes the
    latest relevant level and all other levels are marked unfresh. If the
    touched level is body-broken, it flips A<->V at the same price and the new
    type is fresh.
    """
    for level in levels:
        level.fresh = True
        level.touches = 0
        level.last_touch_time = None
        level.flip_time = None

    for i, row in df.iterrows():
        h, l, c = float(row["high"]), float(row["low"]), float(row["close"])
        for level in levels:
            if level.index >= i:
                continue
            touched = l <= level.price <= h
            if not touched:
                continue

            body_break = c > level.price if level.kind == "A" else c < level.price
            level.last_touch_time = row["time"]

            # The latest touched level takes priority; all other levels become
            # unfresh. This is applied even when the current level is broken.
            for other in levels:
                if other is not level:
                    other.fresh = False

            if body_break:
                level.kind = "V" if level.kind == "A" else "A"
                level.fresh = True
                level.touches = 0
                level.flip_time = row["time"]
            else:
                level.touches += 1
                level.fresh = False


def find_swings(df: pd.DataFrame, lookback: int = config.SWING_LOOKBACK) -> List[SwingPoint]:
    """Generic confirmed fractal swings used only for D1 structure BOS."""
    swings: List[SwingPoint] = []
    n = len(df)
    for i in range(lookback, n - lookback):
        window_high = df["high"].iloc[i - lookback:i + lookback + 1]
        window_low = df["low"].iloc[i - lookback:i + lookback + 1]
        if df["high"].iloc[i] == window_high.max():
            swings.append(SwingPoint(i, df["time"].iloc[i], float(df["high"].iloc[i]), "high"))
        if df["low"].iloc[i] == window_low.min():
            swings.append(SwingPoint(i, df["time"].iloc[i], float(df["low"].iloc[i]), "low"))
    swings.sort(key=lambda s: s.index)
    return swings


def bos_events(df: pd.DataFrame, swings: List[SwingPoint]):
    """Return confirmed D1 BOS events.

    A BOS requires a candle body close strictly beyond the latest confirmed
    swing level. Wick-only moves and closes exactly on the level do not count.
    A continuous close beyond the same reference is not emitted repeatedly.
    """
    events = []
    last_state = None
    for i in range(len(df)):
        prior_highs = [s for s in swings if s.kind == "high" and s.index < i]
        prior_lows = [s for s in swings if s.kind == "low" and s.index < i]
        close = float(df["close"].iloc[i])
        bull = bool(prior_highs and close > prior_highs[-1].price)
        bear = bool(prior_lows and close < prior_lows[-1].price)
        state = "bullish" if bull else "bearish" if bear else None
        if state and state != last_state:
            ref = prior_highs[-1] if state == "bullish" else prior_lows[-1]
            events.append({
                "time": df["time"].iloc[i],
                "direction": state,
                "price": close,
                "level": ref.price,
            })
        if state:
            last_state = state
    return events


def latest_bos(df: pd.DataFrame) -> Optional[dict]:
    swings = find_swings(df)
    events = bos_events(df, swings)
    return events[-1] if events else None
