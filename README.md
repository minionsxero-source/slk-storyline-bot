# SLK Storyline Scanner (Malaysian SNR method)

Scans the market the way the PDF teaches it:

1. **Last BOS** on the higher timeframe → current trend/bias.
2. Wait for a **fresh level rejection** (wick touch + close back) on that
   higher timeframe.
3. Drop **one timeframe lower** and wait for an **external breakout**
   (candle body close beyond the last swing that existed *before* the
   rejection — internal breakouts don't count).
4. If that happens → the **storyline is confirmed** and you get a
   Telegram message. **No entry, SL, or TP is ever sent** — that part is
   left to you, on purpose, as you asked.

Two chains run in parallel per symbol:
- **Weekly storyline**: W1 fresh+reject → D1 external breakout
- **Daily storyline**: D1 fresh+reject → H4 external breakout

**Timeframe alignment filter**: an alert is only sent when the weekly
storyline direction and the daily storyline direction agree. If the
weekly is bullish but the daily just confirmed bearish (or vice versa),
the pair is skipped — nothing is sent until both timeframes line up.

## Files
- `config.py` — symbols, timeframe chains, API keys/credentials, scan interval
- `data_provider.py` — **free, no-server** OHLC data via Twelve Data's REST API
- `mt5_data.py` — optional literal IC Markets feed via a running MT5 terminal (needs a 24/7 Windows box — see "Two ways to run this" below)
- `structure.py` — swing/fractal detection, fresh/unfresh tracking, BOS/trend detection
- `storyline.py` — combines the above into the fresh→reject→external-breakout storyline logic
- `telegram_notifier.py` — sends the alert message
- `state_store.py` — prevents duplicate alerts for the same breakout
- `main.py` — a self-hosted, always-running loop version (use this if you DO have a server/VPS)
- `run_once.py` — a single-pass version built for GitHub Actions cron (use this for the free 24/7 setup below)
- `.github/workflows/scan.yml` — the GitHub Actions schedule that runs `run_once.py` every 15 min, forever, for free

## Two ways to run this

### A) Free, 24/7, no server to maintain (recommended) — GitHub Actions + Twelve Data

This is the setup that needs **nothing running on your computer or any
paid VPS**. GitHub runs the scan for you on a schedule; Twelve Data
supplies the candles over plain HTTPS (no MT5 terminal required).

1. Create a free account at [twelvedata.com](https://twelvedata.com/)
   and grab your API key (free tier: 800 requests/day, 8/min — plenty
   for a handful of FX pairs scanned every 15 min).

2. Push this folder to a **new GitHub repository** (private is fine).

3. In the repo, go to **Settings → Secrets and variables → Actions** and
   add three repository secrets:
   - `TELEGRAM_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
   - `TELEGRAM_CHAT_ID` — message your bot once, then read it from
     `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - `TWELVEDATA_API_KEY` — from step 1

4. That's it. `.github/workflows/scan.yml` will start running every 15
   minutes automatically. You can also trigger a manual run any time
   from the repo's **Actions** tab ("Run workflow"). Each run:
   - pulls fresh W1/D1/H4 candles,
   - checks the storyline + weekly/daily alignment,
   - sends a Telegram message if a new storyline is confirmed,
   - commits the updated `storyline_state.json` back to the repo so the
     next run knows what's already been alerted (this is how state
     survives even though each run starts on a brand-new machine).

   Cost: **$0**. GitHub Actions gives every account free minutes each
   month (2,000+ for private repos, unlimited for public repos), and a
   run here takes seconds.

5. Adjust `config.py` → `SYMBOLS` to taste. Indices (NAS100, US30, etc.)
   need a paid Twelve Data plan, so the default list is FX + gold. If
   you want indices, either upgrade Twelve Data or wire in another free
   source for just those symbols.

**Note on data source**: this method uses Twelve Data's candles, not IC
Markets' literal feed. Since the storyline logic only reasons about
*closed* W1/D1/H4 candles — never ticks or execution — this makes no
practical difference: swing highs/lows, BOS, rejections, and breakouts
will line up with your IC Markets chart the vast majority of the time.
If you need it to be the exact IC Markets candle (e.g. for a broker with
unusual spreads/gaps), use option B.

### B) Literal IC Markets feed via MT5 (needs a 24/7 Windows box)

If you specifically want MT5-sourced IC Markets candles, you do need
*something* running the MT5 terminal around the clock — there's no way
around that, since the `MetaTrader5` python package only talks to a live
terminal process, and that package is Windows-only. Practical free-ish
options:

- **IC Markets' free VPS** — IC Markets provides a free VPS (hosted by
  them) to clients who meet a minimum trading volume/balance
  requirement. If you qualify, this is genuinely free from your side —
  you just remote into it, drop this bot + your MT5 terminal on it, and
  it runs 24/7 on their infrastructure. Check current eligibility on
  their site, as requirements change.
- **Your own always-on PC** — free but not "no system": your computer
  has to stay on and connected.

Setup with this route:
```bash
pip install -r requirements.txt
```
Set `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` as environment variables
(or edit `config.py`), make sure `SYMBOLS` in `config.py` match your MT5
Market Watch names exactly (IC Markets often suffixes symbols, e.g.
`XAUUSD.a`), then run the always-on loop:
```bash
python main.py
```
(`main.py` imports `mt5_data` — swap `data_provider` back in if you've
already switched files around.)

## Important notes / limitations

- This is a **rule-based approximation** of a discretionary, visual
  method. The PDF's fresh/unfresh, rejection, and internal-vs-external
  breakout rules are encoded as literally as possible, but you should
  watch the bot's calls against your own chart reading for a while and
  tune `SWING_LOOKBACK` (and the freshness rules in `structure.py` if
  needed) before trusting it blindly.
- The bot **never** outputs an entry, stop loss, take profit, or risk
  size — only the storyline (direction + which timeframes confirmed it),
  as requested.
- Nothing here is financial advice — it's an automation of the method
  described in the PDF you shared, and it can still misread structure,
  especially around gaps, low-liquidity candles, or very choppy ranges.
