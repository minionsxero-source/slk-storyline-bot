import os

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "PUT_YOUR_CHAT_ID_HERE")

# ---------------------------------------------------------------------------
# Data provider: Twelve Data (free, REST, no terminal/VPS needed)
# Get a free key at https://twelvedata.com/
# ---------------------------------------------------------------------------
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "PUT_YOUR_TWELVEDATA_KEY_HERE")

# ---------------------------------------------------------------------------
# IC Markets (via MetaTrader5 terminal) - OPTIONAL, only needed if you run
# mt5_data.py instead of data_provider.py (see README: "literal IC Markets
# feed" section). Requires a Windows machine/VPS running 24/7.
# ---------------------------------------------------------------------------
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "ICMarketsSC-Demo")  # e.g. ICMarketsSC-Live01
MT5_PATH = os.getenv("MT5_PATH", "")  # optional, full path to terminal64.exe

# ---------------------------------------------------------------------------
# Symbols to scan - Twelve Data format ("BASE/QUOTE").
# Indices (NAS100, US30, etc.) need a paid Twelve Data plan, so the free
# default list sticks to FX + gold. Add indices back if you upgrade, or
# route them through a different free source.
# ---------------------------------------------------------------------------
SYMBOLS = [
    # Metals & Crypto
    "XAU/USD",
    "BTC/USD",

    # Majors
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD",

    # EUR crosses
    "EUR/GBP", "EUR/JPY", "EUR/CHF", "EUR/AUD", "EUR/CAD", "EUR/NZD",

    # GBP crosses
    "GBP/JPY", "GBP/CHF", "GBP/AUD", "GBP/CAD", "GBP/NZD",

    # AUD crosses
    "AUD/JPY", "AUD/CHF", "AUD/CAD", "AUD/NZD",

    # NZD crosses
    "NZD/JPY", "NZD/CHF", "NZD/CAD",

    # CAD/CHF crosses
    "CAD/JPY", "CAD/CHF",
    "CHF/JPY",
]

# ---------------------------------------------------------------------------
# Storyline timeframe chains, exactly as taught in the PDF:
#   Weekly storyline: fresh + reject on W1  -> external breakout on D1
#   Daily storyline:  fresh + reject on D1  -> external breakout on H4
# ---------------------------------------------------------------------------
WEEKLY_CHAIN = ("W1", "D1")
DAILY_CHAIN = ("D1", "H4")

CANDLE_HISTORY = {
    "W1": 300,
    "D1": 400,
    "H4": 800,
}

# Fractal swing lookback: how many candles on each side confirm a swing point.
SWING_LOOKBACK = 2
# How close two levels' prices must be (as a % of price) to count as
# "overlapping" for the weekly/daily confluence check.
CONFLUENCE_TOLERANCE_PCT = 0.15
# How often to rescan (seconds). 15 min is a sane default for W1/D1/H4 work.
SCAN_INTERVAL_SECONDS = 15 * 60

# Where confirmed-alert history is persisted so we don't spam duplicates.
STATE_FILE = "storyline_state.json"
