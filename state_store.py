"""Tiny JSON-file store so we don't re-send the same confirmed storyline
alert every scan cycle."""

import json
import os
import config


def _load():
    if not os.path.exists(config.STATE_FILE):
        return {}
    with open(config.STATE_FILE, "r") as f:
        return json.load(f)


def _save(state):
    with open(config.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def already_alerted(key: str, breakout_time) -> bool:
    state = _load()
    return state.get(key) == str(breakout_time)


def mark_alerted(key: str, breakout_time):
    state = _load()
    state[key] = str(breakout_time)
    _save(state)
