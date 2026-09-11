"""Single-pass SLK scanner for GitHub Actions.

The bot reports the actual prices at which the detected SLK/SNR events happened.
It does not publish entries, stop losses, take profits, or position sizing.
"""

import sys
import traceback

import config
import data_provider
import storyline
import state_store
import telegram_notifier


def fmt_dt(ts):
    return ts.strftime("%Y-%m-%d %H:%M UTC")


def fmt_price(symbol, price):
    if price is None:
        return "-"
    if "JPY" in symbol:
        return f"{price:.3f}"
    if "XAU" in symbol:
        return f"{price:.2f}"
    if "BTC" in symbol:
        return f"{price:.2f}"
    return f"{price:.5f}"


def send_storyline_alert(s):
    emoji = "🟢" if s.direction == "bullish" else "🔴"
    side = "BULLISH" if s.direction == "bullish" else "BEARISH"
    label = "Continuation" if s.classification == "continuation" else "Reversal"

    # These are event prices, not entry prices. The rejection price is the
    # actual D1 A/V level, the external level is the H4 A/V level, and the
    # breakout price is the closed H4 candle close that confirmed the BO.
    msg = (
        f"{emoji} <b>{s.symbol.replace('/', '')} — {side} STORYLINE</b>\n"
        f"<b>{label}</b> · D1 → H4\n\n"
        f"<b>D1 STRUCTURE</b>\n"
        f"BOS confirmed: {fmt_dt(s.d1_bos_time) if s.d1_bos_time else '-'}\n\n"
        f"<b>D1 REJECTION</b>\n"
        f"Level: <b>{fmt_price(s.symbol, s.rejection_price)}</b> ({s.rejection_kind}-shape)\n"
        f"Time: {fmt_dt(s.rejection_time)}\n\n"
        f"<b>H4 CONFIRMATION</b>\n"
        f"External Level: <b>{fmt_price(s.symbol, s.external_level)}</b> ({s.external_kind}-shape)\n"
        f"Breakout close: <b>{fmt_price(s.symbol, s.breakout_price)}</b>\n"
        f"Confirmed: {fmt_dt(s.breakout_time)}\n\n"
        f"<b>STORYLINE</b>\n"
        f"{fmt_price(s.symbol, s.rejection_price)} → "
        f"{fmt_price(s.symbol, s.external_level)} → "
        f"{fmt_price(s.symbol, s.breakout_price)}\n\n"
        f"<b>BIAS: {side}</b>\n"
        f"STATUS: VALID\n\n"
        f"⚠️ Bias/storyline only — no entry, SL or TP."
    )
    telegram_notifier.send_message(msg)


def send_sweep_alert(s):
    emoji = "🟢" if s.direction == "bullish" else "🔴"
    side = "BULLISH" if s.direction == "bullish" else "BEARISH"
    title = "HIGH PROBABILITY SWEEP" if s.high_probability else "LIQUIDITY SWEEP"

    if s.sweep_type == "DAY+WEEK":
        sweep_lines = (
            f"Previous Day wick: <b>{fmt_price(s.symbol, s.previous_day_wick)}</b>\n"
            f"Previous Week wick: <b>{fmt_price(s.symbol, s.previous_week_wick)}</b>"
        )
    else:
        sweep_lines = f"Swept wick: <b>{fmt_price(s.symbol, s.swept_level)}</b> ({s.sweep_type})"

    msg = (
        f"{emoji} <b>{s.symbol.replace('/', '')} — {side}</b>\n"
        f"<b>{title}</b> · {s.confirmation_type}\n\n"
        f"{sweep_lines}\n\n"
        f"Sweep detected: {fmt_dt(s.sweep_time)}\n"
        f"Confirmed: {fmt_dt(s.confirmation_time)}\n"
        f"Confirmation close: <b>{fmt_price(s.symbol, s.confirmation_price)}</b>\n\n"
        f"⚠️ Bias/storyline only — no entry, SL or TP."
    )
    telegram_notifier.send_message(msg)


def scan_symbol(symbol: str):
    w1 = data_provider.get_candles_rate_limited(symbol, "W1", config.CANDLE_HISTORY["W1"])
    d1 = data_provider.get_candles_rate_limited(symbol, "D1", config.CANDLE_HISTORY["D1"])
    h4 = data_provider.get_candles_rate_limited(symbol, "H4", config.CANDLE_HISTORY["H4"])

    # Do not let an incomplete/malformed provider response create a false
    # storyline. Each timeframe must contain enough closed OHLC candles.
    for tf, frame, minimum in (("W1", w1, 20), ("D1", d1, 50), ("H4", h4, 100)):
        if frame is None or frame.empty or len(frame) < minimum:
            raise RuntimeError(f"Insufficient {tf} closed candles for {symbol}: {len(frame) if frame is not None else 0}")
        if frame[["open", "high", "low", "close"]].isna().any().any():
            raise RuntimeError(f"Missing OHLC values in {tf} data for {symbol}")

    story_events = storyline.find_storyline_events(symbol, d1, h4)
    sweep_events = storyline.evaluate_sweeps(symbol, w1, d1, h4)

    # Establish baseline silently on first successful scan. This prevents old
    # historical storylines/sweeps from being replayed after deployment.
    if not state_store.is_initialized(symbol):
        latest_story = story_events[-1].breakout_time if story_events else None
        latest_sweeps = [x.sweep_time for x in sweep_events[-20:]]
        latest_bos = __import__("structure").latest_bos(d1)
        state_store.initialize_symbol(
            symbol,
            storyline_time=latest_story,
            sweep_times=latest_sweeps,
            bias=latest_bos["direction"] if latest_bos else None,
        )
        print(f"[{symbol}] baseline initialized silently")
        return

    new_stories = [x for x in story_events if state_store.storyline_is_new(symbol, x.breakout_time)]
    if new_stories:
        event = new_stories[-1]
        send_storyline_alert(event)
        state_store.record_storyline(symbol, event.breakout_time, event.direction)
        print(f"[{symbol}] STORYLINE ALERT: {event.direction} {event.classification}")

    new_sweeps = [x for x in sweep_events if state_store.sweep_is_new(symbol, x.sweep_time)]
    for event in new_sweeps:
        send_sweep_alert(event)
        state_store.record_sweep(symbol, event.sweep_time)
        print(f"[{symbol}] SWEEP ALERT: {event.direction} {event.sweep_type}")


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
