"""
SLK / Malaysian SNR scanner:
  Rule 1 - daily-bias storyline (fresh level -> rejection -> H4 external breakout)
  Rule 2 - daily candle sweeps prior day high/low -> H4 external breakout
  Rule 2b - same sweep, but flagged extra if it overlaps both a weekly and
            daily key level (confluence)
Single pass, built for GitHub Actions cron.
"""

import sys
import traceback

import config
import data_provider
import storyline
import telegram_notifier
import state_store


def fmt_dt(ts):
    return ts.strftime("%a %-d %b, %H:%M")


def fmt_date(ts):
    return ts.strftime("%-d %b %Y")


def send_storyline_alert(daily_story):
    is_bullish = daily_story.direction == "bullish"
    side = "BUY" if is_bullish else "SELL"
    emoji = "🟢" if is_bullish else "🔴"
    clean_symbol = daily_story.symbol.replace("/", "")

    msg = (
        f"{emoji} {side} · {clean_symbol} · {daily_story.higher_tf}→{daily_story.lower_tf}\n"
        f"External breakout confirmed\n\n"
        f"Rejected key level @ {daily_story.rejection_price:.5f}; "
        f"{daily_story.lower_tf} broke {daily_story.breakout_price:.5f} "
        f"beyond the level that existed before the rejection.\n\n"
        f"Broke {daily_story.breakout_price:.5f} · {fmt_dt(daily_story.breakout_time)}\n"
        f"Rejected {fmt_dt(daily_story.rejection_time)}\n"
        f"Key level {daily_story.rejection_price:.5f} · formed {fmt_date(daily_story.level_formed_time)}\n"
        f"Trend aligned with {daily_story.higher_tf}\n\n"
        f"⚠️ Not an entry signal. Bias only — wait for your entry model."
    )
    telegram_notifier.send_message(msg)


def send_sweep_alert(sweep):
    is_bullish = sweep.direction == "bullish"
    side = "BUY" if is_bullish else "SELL"
    emoji = "🟢" if is_bullish else "🔴"
    clean_symbol = sweep.symbol.replace("/", "")
    level_label = "prior day high" if sweep.sweep_type == "high" else "prior day low"

    msg = (
        f"{emoji} {side} · {clean_symbol} · Daily Sweep→H4\n"
        f"Daily candle swept {level_label}, H4 gave an external breakout\n\n"
        f"Swept {sweep.swept_level:.5f} ({level_label}) · {fmt_dt(sweep.sweep_time)}\n"
        f"H4 Broke {sweep.breakout_price:.5f} · {fmt_dt(sweep.breakout_time)}\n\n"
        f"⚠️ Not an entry signal. Bias only — wait for your entry model."
    )
    telegram_notifier.send_message(msg)


def send_confluence_alert(sweep):
    is_bullish = sweep.direction == "bullish"
    side = "BUY" if is_bullish else "SELL"
    emoji = "🟢" if is_bullish else "🔴"
    clean_symbol = sweep.symbol.replace("/", "")

    msg = (
        f"{emoji} {side} · {clean_symbol} · Weekly+Daily Key Level Overlap\n"
        f"This sweep sits on BOTH a weekly and a daily key level\n\n"
        f"Weekly key level {sweep.weekly_level_price:.5f} · formed {fmt_date(sweep.weekly_level_time)}\n"
        f"Daily key level {sweep.daily_level_price:.5f} · formed {fmt_date(sweep.daily_level_time)}\n"
        f"Swept {sweep.swept_level:.5f} · {fmt_dt(sweep.sweep_time)}\n"
        f"H4 Broke {sweep.breakout_price:.5f} · {fmt_dt(sweep.breakout_time)}\n\n"
        f"⚠️ Not an entry signal. Bias only — wait for your entry model."
    )
    telegram_notifier.send_message(msg)


def scan_symbol(symbol: str):
    w1 = data_provider.get_candles_rate_limited(symbol, "W1", config.CANDLE_HISTORY["W1"])
    d1 = data_provider.get_candles_rate_limited(symbol, "D1", config.CANDLE_HISTORY["D1"])
    h4 = data_provider.get_candles_rate_limited(symbol, "H4", config.CANDLE_HISTORY["H4"])

    # --- Rule 1: SLK storyline ---
    daily_story = storyline.evaluate_storyline(symbol, *config.DAILY_CHAIN, d1, h4)
    if daily_story.confirmed:
        key = f"{symbol}:storyline:{daily_story.higher_tf}->{daily_story.lower_tf}"
        if not state_store.already_alerted(key, daily_story.breakout_time):
            send_storyline_alert(daily_story)
            state_store.mark_alerted(key, daily_story.breakout_time)
            print(f"[{symbol}] STORYLINE ALERT SENT: {daily_story.direction}")
        else:
            print(f"[{symbol}] storyline already alerted, skipping")
    else:
        print(f"[{symbol}] no confirmed daily storyline yet")

    # --- Rule 2 (+2b): daily sweep -> H4 breakout, with weekly/daily confluence flag ---
    sweep = storyline.evaluate_daily_sweep_breakout(symbol, w1, d1, h4)
    if sweep.confirmed:
        key = f"{symbol}:sweep"
        if not state_store.already_alerted(key, sweep.breakout_time):
            send_sweep_alert(sweep)
            state_store.mark_alerted(key, sweep.breakout_time)
            print(f"[{symbol}] SWEEP ALERT SENT: {sweep.direction}")

            if sweep.confluence:
                conf_key = f"{symbol}:confluence"
                if not state_store.already_alerted(conf_key, sweep.breakout_time):
                    send_confluence_alert(sweep)
                    state_store.mark_alerted(conf_key, sweep.breakout_time)
                    print(f"[{symbol}] CONFLUENCE ALERT SENT: {sweep.direction}")
        else:
            print(f"[{symbol}] sweep already alerted, skipping")
    else:
        print(f"[{symbol}] no confirmed daily sweep+breakout yet")


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
