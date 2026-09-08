import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "PUT_YOUR_TWELVEDATA_KEY_HERE")

SYMBOLS = [
    "XAU/USD", "BTC/USD",
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD",
    "EUR/GBP", "EUR/JPY", "EUR/CHF", "EUR/AUD", "EUR/CAD", "EUR/NZD",
    "GBP/JPY", "GBP/CHF", "GBP/AUD", "GBP/CAD", "GBP/NZD",
    "AUD/JPY", "AUD/CHF", "AUD/CAD", "AUD/NZD",
    "NZD/JPY", "NZD/CHF", "NZD/CAD", "CAD/JPY", "CAD/CHF", "CHF/JPY",
]

# Normal storyline is D1 rejection -> H4 external BO. No timeframe-alignment filter.
DAILY_CHAIN = ("D1", "H4")

CANDLE_HISTORY = {"W1": 300, "D1": 400, "H4": 800}
SWING_LOOKBACK = 2
STATE_FILE = "storyline_state.json"
SCAN_INTERVAL_SECONDS = 4 * 60 * 60
