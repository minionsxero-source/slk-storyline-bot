"""Persistent scanner state.

The first run establishes a silent baseline so old historical confirmations are
never replayed as new Telegram alerts.
"""
import json
import os
import config

STATE_VERSION = 3


def _load():
    if not os.path.exists(config.STATE_FILE):
        return {"version": STATE_VERSION, "symbols": {}}
    try:
        with open(config.STATE_FILE, "r") as f:
            data = json.load(f)
        if data.get("version") != STATE_VERSION:
            return {"version": STATE_VERSION, "symbols": {}}
        return data
    except Exception:
        return {"version": STATE_VERSION, "symbols": {}}


def _save(state):
    tmp = config.STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp, config.STATE_FILE)


def get_symbol(symbol):
    return _load()["symbols"].get(symbol, {})


def initialize_symbol(symbol, storyline_time=None, sweep_times=None, bias=None):
    state = _load()
    state["symbols"][symbol] = {
        "baseline": True,
        "last_storyline_time": str(storyline_time) if storyline_time is not None else None,
        "last_sweep_times": [str(x) for x in (sweep_times or [])],
        "active_bias": bias,
    }
    _save(state)


def update_symbol(symbol, **updates):
    state = _load()
    current = state["symbols"].setdefault(symbol, {"baseline": False})
    current.update(updates)
    _save(state)


def is_initialized(symbol):
    return bool(get_symbol(symbol).get("baseline"))


def storyline_is_new(symbol, event_time):
    last = get_symbol(symbol).get("last_storyline_time")
    return last != str(event_time)


def sweep_is_new(symbol, event_time):
    return str(event_time) not in set(get_symbol(symbol).get("last_sweep_times", []))


def record_storyline(symbol, event_time, bias):
    update_symbol(symbol, last_storyline_time=str(event_time), active_bias=bias)


def record_sweep(symbol, event_time):
    current = get_symbol(symbol).get("last_sweep_times", [])
    current = (current + [str(event_time)])[-20:]
    update_symbol(symbol, last_sweep_times=current)
