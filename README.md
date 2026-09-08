# SLK Storyline Bot

Cloud-hosted Telegram scanner for the clarified SLK / Malaysian SNR rules.

## Current rules implemented

- Current/initial bias is based on the latest confirmed **D1 BOS**.
- BOS requires a candle **body close strictly beyond** the structure level. Wick-only breaks and closes exactly on the level do not count.
- A/V Key Levels are exact:
  - **V:** red candle closes at a price and the following green candle opens at exactly that price.
  - **A:** green candle closes at a price and the following red candle opens at exactly that price.
- A/V rules apply on **D1 and H4**.
- A fresh level becomes unfresh when touched.
- If a level is body-broken, it flips **A ↔ V at the same price** and becomes fresh.
- The latest Key Level touched becomes the relevant/latest level; other levels become unfresh.
- D1 rejection:
  - bullish = wick touches V and D1 closes strictly above V;
  - bearish = wick touches A and D1 closes strictly below A.
- Rejection alone never confirms a storyline.
- For a D1 rejection, find the H4 candle that touches that D1 Key Level. Look **strictly before** that H4 candle and use the last matching H4 A/V as the External Level.
- Bullish External BO = H4 body close strictly above the last A.
- Bearish External BO = H4 body close strictly below the last V.
- Internal H4 BO does not confirm a normal storyline.
- Same-direction confirmed storyline = **Continuation**.
- A D1 BOS resets unconfirmed storyline work; wait for a new rejection after the new BOS.
- Daily sweep confirmation = H4 opposite-direction **Internal BO**, alert immediately on the closed H4 candle.
- Weekly liquidity sweep confirmation = opposite-direction **D1 BOS**.
- Previous Day + Previous Week liquidity swept on the same D1 setup = **one High Probability Sweep**.
- Sweep alerts show the **actual wick price**. Storyline alerts show the **A/V level prices**.
- No entries, SL, TP, lot size, or timeframe-alignment filter.
- First deployment scan establishes a silent baseline so old historical alerts are not replayed.

## Hosting

The scanner is designed for GitHub Actions and broadcasts through Supabase to approved Telegram users. The workflow runs every 4 hours at minute 7 UTC.

Do not put Supabase service-role keys or Telegram tokens in public files.
