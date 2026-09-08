"""
Thin data-provider wrapper around the MetaTrader5 Python package.

IC Markets is an MT4/MT5 broker, so the simplest reliable way to pull
OHLC candles programmatically is to run this script on a machine that has
the IC Markets MT5 terminal installed and logged in, and let the
`MetaTrader5` python package talk to that running terminal.

Docs: https://www.mql5.com/en/docs/python_metatrader5
"""

import MetaTrader5 as mt5
import pandas as pd
import config

TF_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
}

_initialized = False


def init_mt5():
    global _initialized
    if _initialized:
        return
    kwargs = {}
    if config.MT5_PATH:
        kwargs["path"] = config.MT5_PATH
    if not mt5.initialize(**kwargs):
        raise RuntimeError(f"MT5 initialize() failed, error = {mt5.last_error()}")
    if config.MT5_LOGIN:
        ok = mt5.login(config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER)
        if not ok:
            raise RuntimeError(f"MT5 login failed, error = {mt5.last_error()}")
    _initialized = True


def shutdown_mt5():
    mt5.shutdown()


def get_candles(symbol: str, timeframe: str, n: int = 300) -> pd.DataFrame:
    """Return the n most recent CLOSED candles for symbol/timeframe."""
    init_mt5()
    tf = TF_MAP[timeframe]
    # pull a couple extra so we can safely drop the still-forming candle
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n + 2)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No data returned for {symbol} {timeframe}: {mt5.last_error()}")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    df = df[["time", "open", "high", "low", "close", "volume"]]
    df = df.iloc[:-1].reset_index(drop=True)  # drop the currently-forming candle
    return df.tail(n).reset_index(drop=True)
