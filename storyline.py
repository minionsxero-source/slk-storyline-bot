"""SLK storyline and liquidity-sweep engine.

The scanner deliberately implements the clarified rules from the user's SLK
method rather than generic SNR/fractal assumptions.
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd

import structure


@dataclass
class StorylineResult:
    symbol: str
    direction: Optional[str]
    classification: Optional[str]  # continuation / reversal
    rejection_time: Optional[object]
    rejection_price: Optional[float]  # D1 A/V price
    rejection_kind: Optional[str]
    external_level: Optional[float]  # H4 A/V price
    external_kind: Optional[str]
    breakout_time: Optional[object]
    breakout_price: Optional[float]  # H4 close
    confirmed: bool
    d1_bos_time: Optional[object]


@dataclass
class SweepResult:
    symbol: str
    direction: Optional[str]
    sweep_time: Optional[object]
    swept_level: Optional[float]  # actual wick price
    sweep_type: Optional[str]  # PDH / PDL / PWH / PWL / DAY+WEEK
    high_probability: bool
    confirmation_time: Optional[object]
    confirmation_price: Optional[float]
    confirmation_tf: Optional[str]
    confirmation_type: Optional[str]  # Internal BO / Daily BOS
    confirmed: bool
    previous_day_wick: Optional[float] = None
    previous_week_wick: Optional[float] = None


def _empty_story(symbol):
    return StorylineResult(symbol, None, None, None, None, None, None, None, None, None, False, None)


def _body_close_break(row, kind, price):
    if kind == "A":
        return float(row["close"]) > price
    return float(row["close"]) < price


def _find_h4_touch_for_d1_rejection(h4: pd.DataFrame, rejection_time, level_price):
    """First H4 candle belonging to/after the D1 rejection that touches the D1 level."""
    candidates = h4[h4["time"] >= rejection_time]
    for _, row in candidates.iterrows():
        if float(row["low"]) <= level_price <= float(row["high"]):
            return row
    return None


def _external_after_touch(h4: pd.DataFrame, touch_index: int, direction: str):
    """Find the last A/V created strictly before the D1-touch H4 candle.

    Then wait for a body close through that exact level. The touch candle itself
    is excluded from candidate creation as required by the rule.
    """
    levels = structure.find_av_levels(h4)
    eligible = [x for x in levels if x.index < touch_index]
    if not eligible:
        return None

    wanted = "A" if direction == "bullish" else "V"
    candidates = [x for x in eligible if x.kind == wanted]
    if not candidates:
        return None
    ext = candidates[-1]

    for i in range(touch_index, len(h4)):
        row = h4.iloc[i]
        if _body_close_break(row, ext.kind, ext.price):
            return ext, row
    return None


def _d1_level_states(d1: pd.DataFrame):
    """Replay A/V state and yield valid first-touch rejection candidates."""
    levels = structure.find_av_levels(d1)
    # Runtime state is separate from the creation objects so each replay is
    # deterministic and a level can flip A<->V at the same price.
    state = {
        id(x): {"kind": x.kind, "fresh": True, "touches": 0, "formed": x.time}
        for x in levels
    }
    by_index = {}
    for level in levels:
        by_index.setdefault(level.index, []).append(level)

    for i, row in d1.iterrows():
        # Newly created A/V levels are available from this candle onward.
        for level in by_index.get(i, []):
            state[id(level)]["kind"] = level.kind
            state[id(level)]["fresh"] = True
            state[id(level)]["touches"] = 0

        touched = []
        for level in levels:
            if level.index >= i:
                continue
            st = state[id(level)]
            if float(row["low"]) <= level.price <= float(row["high"]):
                touched.append((level, st))

        # Latest touched level wins. For a single candle with several levels,
        # use the level closest to the candle close as the deterministic final
        # interaction; otherwise the candle path cannot be known from OHLC.
        if touched:
            touched.sort(key=lambda x: abs(float(row["close"]) - x[0].price))
            winning_level, winning_state = touched[0]
            for level, st in touched:
                if level is not winning_level:
                    st["fresh"] = False

            old_kind = winning_state["kind"]
            body_break = (float(row["close"]) > winning_level.price
                          if old_kind == "A"
                          else float(row["close"]) < winning_level.price)
            if body_break:
                winning_state["kind"] = "V" if old_kind == "A" else "A"
                winning_state["fresh"] = True
                winning_state["touches"] = 0
            else:
                # First touch of a fresh level is the only touch eligible to
                # become a rejection. The caller evaluates direction/close.
                winning_state["touches"] += 1
                was_fresh = winning_state["fresh"]
                winning_state["fresh"] = False
                yield {
                    "time": row["time"],
                    "price": winning_level.price,
                    "kind": old_kind,
                    "fresh_before_touch": was_fresh,
                    "level_index": winning_level.index,
                }


def _replay_d1_storylines(symbol: str, d1: pd.DataFrame, h4: pd.DataFrame):
    """Replay the D1/H4 storyline as a chronological event machine.

    D1 BOS establishes the structural direction and resets unconfirmed work.
    After that, a fresh same-direction D1 rejection is eligible. A confirmed
    H4 external BO is what actually confirms the storyline and changes the
    active bias immediately. If an opposite rejection occurs before a new D1
    BOS, its H4 external BO may become a reversal. If several rejections are
    possible, the first valid external BO to close wins.
    """
    swings = structure.find_swings(d1)
    bos_events = structure.bos_events(d1, swings)
    if not bos_events:
        return []

    bos_by_time = {x["time"]: x for x in bos_events}
    d1_bos_times = sorted(x["time"] for x in bos_events)
    av_levels = structure.find_av_levels(d1)
    av_state = {id(x): {"kind": x.kind, "fresh": True, "touches": 0} for x in av_levels}

    # Build all valid D1 rejection candidates first. A candidate is invalidated
    # by the next D1 BOS after its rejection, but otherwise remains a possible
    # storyline until its corresponding H4 external BO occurs.
    candidates = []
    active_bias = None
    structure_bias = None
    for i, row in d1.iterrows():
        if row["time"] in bos_by_time:
            be = bos_by_time[row["time"]]
            active_bias = be["direction"]
            structure_bias = be["direction"]
            # D1 BOS invalidates every older pending rejection. A/V freshness
            # itself is handled independently below.
            candidates = [c for c in candidates if c["rejection_time"] > row["time"]]

        for level in av_levels:
            if level.index == i:
                av_state[id(level)] = {"kind": level.kind, "fresh": True, "touches": 0}

        touched = []
        for level in av_levels:
            if level.index >= i:
                continue
            st = av_state[id(level)]
            if float(row["low"]) <= level.price <= float(row["high"]):
                touched.append((level, st))
        if not touched or active_bias is None:
            continue

        # Latest touched Key Level wins. For multiple levels inside one OHLC
        # candle, use the one closest to the close as a deterministic proxy.
        touched.sort(key=lambda x: abs(float(row["close"]) - x[0].price))
        winning, st = touched[0]
        for level, other in touched:
            if level is not winning:
                other["fresh"] = False

        old_kind = st["kind"]
        body_break = (float(row["close"]) > winning.price
                      if old_kind == "A"
                      else float(row["close"]) < winning.price)
        if body_break:
            st["kind"] = "V" if old_kind == "A" else "A"
            st["fresh"] = True
            st["touches"] = 0
            continue

        first_touch = bool(st["fresh"])
        st["touches"] += 1
        st["fresh"] = False
        if not first_touch:
            continue

        rejection_direction = (
            "bullish" if old_kind == "V" and float(row["close"]) > winning.price
            else "bearish" if old_kind == "A" and float(row["close"]) < winning.price
            else None
        )
        if rejection_direction is None:
            continue

        # After a D1 BOS, the next storyline must follow the new structural
        # direction. Before the next D1 BOS, an opposite rejection is allowed
        # and can become a reversal through its own external BO.
        if row["time"] >= max([t for t in d1_bos_times if t <= row["time"]], default=row["time"]) and \
           structure_bias != rejection_direction and row["time"] in bos_by_time:
            continue
        if row["time"] > max([t for t in d1_bos_times if t <= row["time"]], default=row["time"]) and \
           rejection_direction != structure_bias and structure_bias is not None:
            # Opposite rejection is allowed only if it is before the next BOS;
            # since we are between BOS events, keep it as a reversal candidate.
            pass

        touch = _find_h4_touch_for_d1_rejection(h4, row["time"], winning.price)
        if touch is None:
            continue
        result = _external_after_touch(h4, int(touch.name), rejection_direction)
        if result is None:
            continue
        ext, breakout = result

        # A candidate cannot survive a later D1 BOS occurring before its BO.
        later_bos = [t for t in d1_bos_times if row["time"] < t < breakout["time"]]
        if later_bos:
            continue

        candidates.append({
            "rejection_time": row["time"],
            "rejection_price": winning.price,
            "rejection_kind": old_kind,
            "direction": rejection_direction,
            "external_level": ext.price,
            "external_kind": ext.kind,
            "breakout_time": breakout["time"],
            "breakout_price": float(breakout["close"]),
            "d1_bos_time": max([t for t in d1_bos_times if t <= row["time"]], default=None),
        })

    # The replay above has all possible confirmations. Process them in H4
    # confirmation order. Once one confirms, any older pending candidate is
    # completed/ignored; a later rejection can produce a later continuation.
    candidates.sort(key=lambda x: x["breakout_time"])
    events = []
    processed_rejections = set()
    for c in candidates:
        if c["rejection_time"] in processed_rejections:
            continue
        # A prior confirmed storyline after this rejection completes that old
        # setup. Only the first breakout after the rejection can win.
        prior = [e for e in events if c["rejection_time"] <= e.breakout_time < c["breakout_time"]]
        if prior:
            continue
        prior_events = [e for e in events if e.breakout_time < c["breakout_time"]]
        latest_bos_before = [b for b in bos_events if b["time"] <= c["breakout_time"]]
        active_bias_at_confirmation = (
            prior_events[-1].direction if prior_events else
            (latest_bos_before[-1]["direction"] if latest_bos_before else None)
        )
        classification = (
            "continuation" if c["direction"] == active_bias_at_confirmation else "reversal"
        )
        events.append(StorylineResult(
            symbol=symbol,
            direction=c["direction"],
            classification=classification,
            rejection_time=c["rejection_time"],
            rejection_price=c["rejection_price"],
            rejection_kind=c["rejection_kind"],
            external_level=c["external_level"],
            external_kind=c["external_kind"],
            breakout_time=c["breakout_time"],
            breakout_price=c["breakout_price"],
            confirmed=True,
            d1_bos_time=c["d1_bos_time"],
        ))
        active_bias = c["direction"]
        processed_rejections.add(c["rejection_time"])

    return events

def evaluate_storyline(symbol: str, d1: pd.DataFrame, h4: pd.DataFrame,
                       state: Optional[dict] = None) -> StorylineResult:
    """Return the newest confirmed normal-storyline event."""
    events = _replay_d1_storylines(symbol, d1, h4)
    if not events:
        return _empty_story(symbol)
    return events[-1]


def find_storyline_events(symbol: str, d1: pd.DataFrame, h4: pd.DataFrame):
    return _replay_d1_storylines(symbol, d1, h4)


def _daily_sweep(row, prev):
    # Use the actual wick extreme in the alert, while the liquidity reference
    # is the previous day's high/low.
    if float(row["high"]) > float(prev["high"]) and float(row["close"]) < float(prev["high"]):
        return "bearish", "PDH", float(row["high"])
    if float(row["low"]) < float(prev["low"]) and float(row["close"]) > float(prev["low"]):
        return "bullish", "PDL", float(row["low"])
    return None


def _weekly_sweep(row, prev_week):
    if float(row["high"]) > float(prev_week["high"]):
        # A weekly-high sweep needs the D1 candle to close back below it.
        if float(row["close"]) < float(prev_week["high"]):
            return "bearish", "PWH", float(row["high"])
    if float(row["low"]) < float(prev_week["low"]):
        if float(row["close"]) > float(prev_week["low"]):
            return "bullish", "PWL", float(row["low"])
    return None


def _h4_internal_bos_after(h4, start_time, direction):
    # H4 sweep confirmation is a BOS in the opposite direction of the sweep.
    # Use confirmed fractal structure and body close.
    swings = structure.find_swings(h4)
    for i, row in h4[h4["time"] >= start_time].iterrows():
        prior = [s for s in swings if s.index < i]
        if direction == "bullish":
            highs = [s for s in prior if s.kind == "high"]
            if highs and float(row["close"]) > highs[-1].price:
                return row
        else:
            lows = [s for s in prior if s.kind == "low"]
            if lows and float(row["close"]) < lows[-1].price:
                return row
    return None


def _daily_opposite_bos_after(d1, start_time, direction):
    swings = structure.find_swings(d1)
    for i, row in d1[d1["time"] >= start_time].iterrows():
        prior = [s for s in swings if s.index < i]
        if direction == "bullish":
            highs = [s for s in prior if s.kind == "high"]
            if highs and float(row["close"]) > highs[-1].price:
                return row
        else:
            lows = [s for s in prior if s.kind == "low"]
            if lows and float(row["close"]) < lows[-1].price:
                return row
    return None


def evaluate_sweeps(symbol: str, w1: pd.DataFrame, d1: pd.DataFrame, h4: pd.DataFrame):
    """Return all confirmed, chronologically ordered sweep setups."""
    results = []
    if len(d1) < 3 or len(w1) < 3:
        return results

    # Map each D1 candle to its previous completed week using calendar periods.
    d1 = d1.copy()
    w1 = w1.copy()
    d1["week_key"] = d1["time"].dt.to_period("W-SUN")
    w1["week_key"] = w1["time"].dt.to_period("W-SUN")

    for i in range(1, len(d1)):
        row = d1.iloc[i]
        prev = d1.iloc[i - 1]
        day = _daily_sweep(row, prev)
        week = None
        wk = row["week_key"]
        previous_weeks = w1[w1["week_key"] < wk]
        if not previous_weeks.empty:
            pw = previous_weeks.iloc[-1]
            week = _weekly_sweep(row, pw)

        if not day and not week:
            continue

        # If both are swept on the same D1 candle, it is one High Probability
        # setup. Direction must agree; otherwise keep the individual liquidity
        # event rather than forcing an impossible combined direction.
        combined = bool(day and week and day[0] == week[0])
        if combined:
            direction = day[0]
            h4_conf = _h4_internal_bos_after(h4, row["time"], direction)
            if h4_conf is not None:
                results.append(SweepResult(symbol, direction, row["time"], day[2],
                    "DAY+WEEK", True, h4_conf["time"], float(h4_conf["close"]),
                    "H4", "Internal BO", True, previous_day_wick=day[2], previous_week_wick=week[2]))
            continue

        if day:
            direction = day[0]
            conf = _h4_internal_bos_after(h4, row["time"], direction)
            if conf is not None:
                results.append(SweepResult(symbol, direction, row["time"], day[2], day[1], False,
                    conf["time"], float(conf["close"]), "H4", "Internal BO", True))

        if week:
            direction = week[0]
            conf = _daily_opposite_bos_after(d1, row["time"], direction)
            if conf is not None:
                results.append(SweepResult(symbol, direction, row["time"], week[2], week[1], False,
                    conf["time"], float(conf["close"]), "D1", "Daily BOS", True))

    return results
