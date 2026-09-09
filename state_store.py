"""Persistent scanner state.

The first successful scan establishes a silent baseline so historical
storylines and sweeps are never replayed as new Telegram alerts.

For sweeps we use a chronological watermark rather than only remembering
the last N individual timestamps. This prevents a large historical sweep
list from being replayed.
"""

import json
import os
from datetime import datetime

import config


STATE_VERSION = 4


def _empty_state():
    return {
        "version": STATE_VERSION,
        "symbols": {},
    }


def _load():
    if not os.path.exists(config.STATE_FILE):
        return _empty_state()

    try:
        with open(config.STATE_FILE, "r") as f:
            data = json.load(f)

        if data.get("version") != STATE_VERSION:
            print(
                f"State version mismatch: "
                f"found={data.get('version')} expected={STATE_VERSION}. "
                f"Starting a new silent baseline."
            )
            return _empty_state()

        if "symbols" not in data or not isinstance(data["symbols"], dict):
            return _empty_state()

        return data

    except Exception as exc:
        print(f"Unable to load scanner state: {exc}")
        return _empty_state()


def _save(state):
    tmp = config.STATE_FILE + ".tmp"

    with open(tmp, "w") as f:
        json.dump(
            state,
            f,
            indent=2,
            default=str,
        )

    os.replace(tmp, config.STATE_FILE)


def _time_value(value):
    """Convert a timestamp into a comparable datetime.

    Returns None if the value cannot be parsed.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value)

    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except Exception:
        return None


def _max_time(values):
    """Return the latest valid timestamp from a collection."""
    parsed = []

    for value in values or []:
        dt = _time_value(value)
        if dt is not None:
            parsed.append((dt, str(value)))

    if not parsed:
        return None

    return max(parsed, key=lambda x: x[0])[1]


def get_symbol(symbol):
    state = _load()
    return state.get("symbols", {}).get(symbol, {})


def initialize_symbol(
    symbol,
    storyline_time=None,
    sweep_times=None,
    bias=None,
):
    """
    Establish a silent baseline.

    The latest historical storyline and latest historical sweep are stored
    as watermarks. Nothing from before or at the baseline can be emitted
    as a new alert.
    """

    state = _load()

    latest_sweep_time = _max_time(sweep_times or [])

    state["symbols"][symbol] = {
        "baseline": True,

        # Storyline watermark
        "last_storyline_time": (
            str(storyline_time)
            if storyline_time is not None
            else None
        ),

        # Sweep chronological watermark
        "last_sweep_time": latest_sweep_time,

        # Keep a small history for diagnostics/backwards compatibility.
        "last_sweep_times": [
            str(x)
            for x in (sweep_times or [])[-20:]
        ],

        "active_bias": bias,
    }

    _save(state)

    print(
        f"[{symbol}] state baseline saved: "
        f"storyline={storyline_time}, "
        f"last_sweep={latest_sweep_time}, "
        f"bias={bias}"
    )


def update_symbol(symbol, **updates):
    state = _load()

    current = state["symbols"].setdefault(
        symbol,
        {
            "baseline": False,
            "last_storyline_time": None,
            "last_sweep_time": None,
            "last_sweep_times": [],
            "active_bias": None,
        },
    )

    current.update(updates)

    _save(state)


def is_initialized(symbol):
    return bool(
        get_symbol(symbol).get("baseline")
    )


def storyline_is_new(symbol, event_time):
    """
    A storyline is new only if its timestamp is newer than the
    stored storyline watermark.

    This is safer than simply checking timestamp inequality.
    """

    current = get_symbol(symbol)

    last = _time_value(
        current.get("last_storyline_time")
    )

    event = _time_value(event_time)

    if event is None:
        return False

    if last is None:
        return True

    return event > last


def sweep_is_new(symbol, event_time):
    """
    A sweep is new only if it occurred after the stored sweep watermark.

    This is the critical duplicate-protection mechanism.

    Historical events older than or equal to the watermark are ignored,
    even if they are not present in the small diagnostic history list.
    """

    current = get_symbol(symbol)

    last = _time_value(
        current.get("last_sweep_time")
    )

    event = _time_value(event_time)

    if event is None:
        return False

    if last is None:
        return True

    return event > last


def record_storyline(symbol, event_time, bias):
    """
    Advance the storyline watermark after successful Telegram delivery.
    """

    update_symbol(
        symbol,
        last_storyline_time=str(event_time),
        active_bias=bias,
    )


def record_sweep(symbol, event_time):
    """
    Advance the sweep watermark after successful Telegram delivery.

    The diagnostic history is retained, but it is NOT used to determine
    whether an event is new.
    """

    current = get_symbol(symbol)

    history = list(
        current.get("last_sweep_times", [])
    )

    event_text = str(event_time)

    if event_text not in history:
        history.append(event_text)

    history = history[-20:]

    previous_watermark = _time_value(
        current.get("last_sweep_time")
    )

    new_time = _time_value(event_time)

    # Only move the watermark forward.
    if (
        new_time is not None
        and (
            previous_watermark is None
            or new_time > previous_watermark
        )
    ):
        last_sweep_time = event_text
    else:
        last_sweep_time = current.get(
            "last_sweep_time"
        )

    update_symbol(
        symbol,
        last_sweep_time=last_sweep_time,
        last_sweep_times=history,
    )
