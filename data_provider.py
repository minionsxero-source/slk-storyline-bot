"""
Free, cloud-friendly OHLC data provider using Twelve Data's REST API.

Why swap out MetaTrader5?
  The MetaTrader5 python package only works by talking to a RUNNING MT5
  terminal on the same (Windows) machine - that's a "system" you'd have
  to keep online 24/7. This module instead pulls closed candles over
  plain HTTPS, so it can run from any free Linux runner (including
  GitHub Actions) with nothing kept running in the background.

  Since the storyline logic only reasons about CLOSED W1/D1/H4 candles
  (never live ticks or execution), a solid retail data feed is
  functionally equivalent to IC Markets' own candles for structure
  purposes - swing highs/lows, BOS, and breakouts will match almost
  every time. If you need literal IC Markets tick-for-tick data, see the
  README section on running this against MT5 on a broker VPS instead.

Docs: https://twelvedata.com/docs
Free tier: 800 requests/day, 8 requests/minute - plenty for a handful
of symbols scanned every 15-60 minutes.
"""

import time
import requests
import pandas as pd

import config

INTERVAL_MAP = {
    "H4": "4h",
    "D1": "1day",
    "W1": "1week",
}

BASE_URL = "https://api.twelvedata.com/time_series"


def get_candles(symbol: str, timeframe: str, n: int = 300) -> pd.DataFrame:
    """Return the n most recent CLOSED candles for symbol/timeframe, oldest first."""
    interval = INTERVAL_MAP[timeframe]
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": n + 2,
        "apikey": config.TWELVEDATA_API_KEY,
        "order": "ASC",
    }
    resp = requests.get(BASE_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") == "error":
        raise RuntimeError(f"Twelve Data error for {symbol} {timeframe}: {data.get('message')}")

    values = data.get("values")
    if not values:
        raise RuntimeError(f"No data returned for {symbol} {timeframe}")

    df = pd.DataFrame(values)
    df["time"] = pd.to_datetime(df["datetime"])
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype(float)
    df = df[["time", "open", "high", "low", "close"]].sort_values("time").reset_index(drop=True)

    # Drop the last row defensively in case it's a still-forming candle
    # (Twelve Data usually only returns closed bars for D1/W1/H4, but this
    # keeps behaviour consistent with the MT5 provider).
    df = df.iloc[:-1].reset_index(drop=True)
    return df.tail(n).reset_index(drop=True)


def get_candles_rate_limited(symbol: str, timeframe: str, n: int = 300, pause: float = 1.0) -> pd.DataFrame:
    """Same as get_candles but sleeps briefly first - handy when looping over
    many symbols back-to-back to stay under the free-tier rate limit."""
    time.sleep(pause)
    return get_candles(symbol, timeframe, n)
