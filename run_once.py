"""
Single-pass version of main.py, designed to be triggered by a GitHub
Actions cron schedule instead of an internal while-loop. Each run:
  1. Scans every symbol once.
  2. Applies the exact same weekly/daily storyline + alignment logic.
  3. Sends Telegram alerts for anything newly confirmed.
  4. Exits. state_store.py's JSON file is what makes de-duplication work
     across separate runs (the workflow commits it back to the repo).
"""

import sys
import traceback

import config
import data_provider
import storyline
import telegram_notifier
import state_store


def scan_symbol(symbol: str):
    w1 = data_provider.get_candles_rate_limited(symbol, "W1", config.CANDLE_HISTORY["W1"])
    d1 = data_provider.get_candles_rate_limited(symbol, "D1", config.CANDLE_HISTORY["D1"])
    h4 = data_provider.get_candles_rate_limited(symbol, "H4", config.CANDLE_HISTORY["H4"])

    weekly_story = storyline.evaluate_storyline(symbol, *config.WEEKLY_CHAIN, w1, d1)
    daily_story = storyline.evaluate_storyline(symbol, *config.DAILY_CHAIN, d1, h4)

    if not daily_story.confirmed:
        print(f"[{symbol}] no confirmed daily storyline yet")
        return

    if weekly_story.direction is None or weekly_story.direction != daily_story.direction:
        print(f"[{symbol}] daily storyline confirmed ({daily_story.direction}) "
              f"but weekly is {weekly_story.direction} -> NOT aligned, skipped")
        return

    key = f"{symbol}:{daily_story.higher_tf}->{daily_story.lower_tf}"
    if state_store.already_alerted(key, daily_story.breakout_time):
        print(f"[{symbol}] already alerted for this breakout, skipping")
        return

    direction_word = "BULLISH" if daily_story.direction == "bullish" else "BEARISH"
    msg = (
        f"<b>{symbol}</b> — {direction_word} STORYLINE CONFIRMED\n"
        f"Weekly bias: {weekly_story.direction} (aligned ✅)\n"
        f"Daily fresh level rejected → 4H external breakout confirmed.\n"
        f"Rejection: {daily_story.rejection_time}\n"
        f"4H Breakout: {daily_story.breakout_time}\n\n"
        f"⚠️ Storyline only — no entry given. Go refine it yourself on 1H/M5."
    )
    telegram_notifier.send_message(msg)
    state_store.mark_alerted(key, daily_story.breakout_time)
    print(f"[{symbol}] ALERT SENT: {direction_word} storyline confirmed & TF-aligned")


def main():
    had_error = False
    for symbol in config.SYMBOLS:
        try:
            scan_symbol(symbol)
        except Exception as e:
            had_error = True
            print(f"[{symbol}] ERROR: {e}")
            traceback.print_exc()
    sys.exit(1 if had_error else 0)


if __name__ == "__main__":
    main()
