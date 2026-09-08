"""
SLK / Malaysian SNR storyline scanner.

Per symbol:
  1. Build the WEEKLY storyline  (W1 fresh + reject  -> D1 external breakout)
  2. Build the DAILY storyline   (D1 fresh + reject  -> H4 external breakout)
  3. ALIGNMENT FILTER: only alert if weekly direction == daily direction.
     e.g. weekly bullish + daily bearish -> skipped, no alert sent.
  4. If aligned AND the daily storyline is newly confirmed, send a
     Telegram message with the STORYLINE ONLY (direction + which levels
     confirmed it). No entries, no SL/TP, no lot sizing - by design.
"""

import time
import traceback

import config
import mt5_data
import storyline
import telegram_notifier
import state_store


def scan_symbol(symbol: str):
    w1 = mt5_data.get_candles(symbol, "W1", config.CANDLE_HISTORY["W1"])
    d1 = mt5_data.get_candles(symbol, "D1", config.CANDLE_HISTORY["D1"])
    h4 = mt5_data.get_candles(symbol, "H4", config.CANDLE_HISTORY["H4"])

    weekly_story = storyline.evaluate_storyline(symbol, *config.WEEKLY_CHAIN, w1, d1)
    daily_story = storyline.evaluate_storyline(symbol, *config.DAILY_CHAIN, d1, h4)

    if not daily_story.confirmed:
        return

    # --- Timeframe alignment: weekly bias must match daily bias ---
    if weekly_story.direction is None or weekly_story.direction != daily_story.direction:
        print(f"[{symbol}] daily storyline confirmed ({daily_story.direction}) "
              f"but weekly is {weekly_story.direction} -> NOT aligned, skipped")
        return

    key = f"{symbol}:{daily_story.higher_tf}->{daily_story.lower_tf}"
    if state_store.already_alerted(key, daily_story.breakout_time):
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


def run():
    telegram_notifier.send_message("🟢 SLK Storyline Scanner started (IC Markets feed).")
    while True:
        for symbol in config.SYMBOLS:
            try:
                scan_symbol(symbol)
            except Exception as e:
                print(f"[{symbol}] ERROR: {e}")
                traceback.print_exc()
        time.sleep(config.SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        run()
    finally:
        mt5_data.shutdown_mt5()
