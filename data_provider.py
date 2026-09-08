"""
Free, cloud-friendly OHLC data provider using Twelve Data's REST API.
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


def get_candles(symbol: str, timeframe: str, n: int = 300, retries: int = 2) -> pd.DataFrame:
    """Return the n most recent CLOSED candles for symbol/timeframe, oldest first.
    Retries once on transient network errors (timeouts, connection resets)."""
    interval = INTERVAL_MAP[timeframe]
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": n + 2,
        "apikey": config.TWELVEDATA_API_KEY,
        "order": "ASC",
    }

    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=30)
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
            df = df.iloc[:-1].reset_index(drop=True)
            return df.tail(n).reset_index(drop=True)

        except (requests.exceptions.RequestException, RuntimeError) as e:
            last_error = e
            if attempt < retries:
                time.sleep(5)  # brief pause before retrying
                continue
            raise last_error


def get_candles_rate_limited(symbol: str, timeframe: str, n: int = 300, pause: float = 8.0) -> pd.DataFrame:
    """Same as get_candles but sleeps first - required to stay under Twelve
    Data's free-tier limit of 8 requests/minute (one request every 7.5s
    minimum). 8s gives a small safety margin."""
    time.sleep(pause)
    return get_candles(symbol, timeframe, n)
