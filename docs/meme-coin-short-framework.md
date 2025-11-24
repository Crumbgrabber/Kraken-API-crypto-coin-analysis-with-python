# Meme Coin Shorting Framework (Kraken-First)

A shared reference for future agents and developers: what we are trying to do, what factors matter, and how to instrument data collection and modeling for shorting meme coins. Kraken is the first target venue; the approach should generalize to Coinbase and other platforms as we add them.

## Goals
- Identify shortable meme coins with clear, repeatable signals instead of hype-driven longs.
- Factor platform costs (conversion, trading, funding) into timing and profitability.
- Build data pipelines to track market/chain/social interest and detect waning momentum.
- Prototype ML/heuristics that rank short candidates and optimize entry timing.

## Platform Scope
- **Primary**: Kraken (current implementation target).
- **Next**: Coinbase; evaluate other venues for short availability, liquidity, and trustworthiness.
- **Constraints**: Smaller coins are often unshortable or legally restricted for US users. Plan to monitor new platforms/law changes to widen coverage.

## Trading Cost Reality
- Fiat→crypto and crypto→crypto conversions carry fees before any short is opened.
- Funding rates generally favor longs over shorts; carrying shorts is expensive.
- A few percentage points of slippage/fees can flip a correct call into a loss; timing must account for costs.

## Meme Coin Hype Cycle (Conceptual)
Typical arc (time scale can be minutes on micro-caps, months on large caps):
1) **Initial Hype**: Social media surge; market cap and volume spike as insiders/retail pile in.
2) **Insider Behavior**: Founders either hold or sell into demand.
3) **Blow-Off High**: A peak/highest high on monthly/daily charts.
4) **Lower Highs**: Fails to make new highs; rallies stall below prior peaks.
5) **Distribution/Drift Down**: Volume thins or shows selling conviction; price fades.
6) **Rug/Exhaustion**: On fast cycles (e.g., pump.fun launches) this can be minutes; on larger names, months.

## Chart/TA Signals to Track
- **Timeframe gating**: Prefer monthly and daily patterns; 4h only for very new coins with fast cycles.
- **Highest high behavior**: After the initial or second/third month, many meme coins never break the all-time high. Lower highs with fading interest are core short setups.
- **Volume Spread / Wyckoff cues**:
  - High-volume down days = strong selling conviction.
  - Up moves with rising volume that fail to break prior highs = short zone.
  - Up moves with falling volume = weak rally, potential short.
  - If price breaks prior highs on rising volume, stand down (possible new hype cycle).
- **Volume profile levels**:
  - Point of Control (POC) and developing POC near visible-range profiles (4h/daily).
  - Align POC with horizontal S/R; use as candidate short entries or targets.
- **Support/Resistance behavior**: Repeated lower highs into known resistance strengthen short bias; a break of prior high invalidates.

## Interest/Activity Factors to Collect
Track these over time; decays vs price can flag waning interest:
- Market cap (ideally daily from Kraken; otherwise other APIs).
- Open interest on futures/perps (per exchange).
- On-chain transactions and active addresses for the token’s chain.
- Trading volume (spot and derivatives).
- Social: mentions/tweets, Reddit activity, sentiment scores.
- Dev pulse: announcements, GitHub commits (if any), site backlinks, web traffic.
- Exchange coverage/liquidity: which venues list/allow shorts, depth/fee structure.

## Data Strategy
- Pull and persist all Kraken-available fields per asset (one-time metadata + daily metrics).
- Add auxiliary sources for social, on-chain, web/dev signals when available.
- Build “interest over time” charts for price vs market cap vs OI vs chain tx vs social.
- Label periods of new highs, lower highs, high-volume down days, and failed retests for downstream modeling.

## Modeling/Heuristic Ideas
- Scorecards that weight: lower-high structure, volume confirmation, volume-profile alignment, and interest decay divergence.
- ML features: slopes/decay rates of market cap, OI, chain tx, social mentions vs price; volume/price regime flags; funding rates; fee-adjusted expected value.
- Fast-cycle mode for newly listed coins (4h/15m data) vs standard mode (daily/monthly).
- Output: ranked short candidates + suggested entry bands (POC/SR), with cost-adjusted breakeven thresholds.

## Operational Notes
- Only short when higher timeframes show the pattern; skip if a prior high is broken on rising volume/interest.
- Track platform/legal constraints; maintain a registry of shortable venues per coin.
- Always include fee/funding estimates in expected value before executing.

## Kraken Data to Persist (What/When)
- **Static (pull once, reuse)**: AssetInfo (decimals, status), AssetPairs (fees, lot size, marginable flag), futures instruments (tick size, contract size).
- **Incremental daily/4h**:
  - Spot OHLCV with VWAP (4h, 1d; resample to monthly).
  - Spot Ticker EOD snapshot: last/close proxy, 24h vol/high/low, VWAP, trades.
  - Futures tickers: `openInterest`, `fundingRate`, `markPrice`, 24h vol/high/low.
  - Futures OHLC (4h, 1d) for mark/last time series.
  - Basis calc: `markPrice` (futures) minus spot close/VWAP (absolute and %).
  - Funding schedule: `risk_rates` for cadence/next times (refresh daily or when listings change).

## External Data Needed (Kraken lacks)
- Daily market cap per coin (CoinGecko or similar).
- On-chain activity: tx counts, active addresses, gas/fees (chain explorers/APIs).
- Social: mentions/tweets, Reddit, sentiment scores.
- Dev/web pulse: site traffic, backlinks, GitHub commits/releases (if any).

## Storage and Refresh Policy
- **Format**: Parquet for columnar time-series; optional DuckDB for fast SQL-style joins across factors.
- **Static**: Cache once; only refresh if exchange metadata changes.
- **Incremental**: Append new closed candles and EOD snapshots; track last timestamp to avoid re-pulling.
- **Intervals**: 4h and 1d from Kraken; resample to monthly for higher-timeframe logic. Add a “fast-cycle” mode (4h/15m) later for brand-new listings if needed.
