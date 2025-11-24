# Usage

## Install
```bash
pip install -r requirements.txt
```

Ensure `.env` contains `KRAKENAPIKEY` and `KRAKENPRIVATEKEY` if you later add private calls. Public OHLC does not require auth.

## Run analyzer
```bash
python main.py --top 15
```

Flags:
- `--refresh` refreshes cache for all timeframes.
- `--start N` starts processing at index N of the discovered USD pairs (0-based) for batching.
- `--limit N` processes only N pairs after the start offset.
- `--pairs JTOUSD,BONKUSD` runs only the listed pairs.
- `--plotly-top N` overrides how many Plotly HTML charts are written (default from settings).
- `--top N` controls console display count.
- `--export-pairs` writes the discovered USD spot pairs to `data/pairs_usd.csv`.
- `--timeframes monthly,daily,4h` limits which timeframes are processed (e.g., `--timeframes monthly` for fast monthly-only seeding).
- `--refresh-metadata` caches Assets/AssetPairs to `data/cache/asset_*.json`.
- `--refresh-futures` caches futures instruments + tickers (funding/OI/basis) to `data/cache/instruments.json` and `data/cache/futures_tickers.parquet`.
- `--refresh-risk-rates` attempts to cache futures risk rates to `data/cache/risk_rates.json` (writes a stub if the endpoint is unavailable).

Outputs:
- Console table (score + per-timeframe pass/fail).
- `results/analysis.csv` and `results/analysis.json`
- Plotly HTML charts under `results/` for every pair/timeframe (`{pair}_monthly.html`, `{pair}_daily.html`, `{pair}_4h.html`) plus a rollup `{pair}.html` for top-N.
- `results/summary.html` includes mini-chart thumbnails (monthly/daily/4h) linking to full charts, OI/funding columns, and quick filters (class, Solana-only, score/oi/funding thresholds, text search).

## Indicators (EMA)
- Compute EMAs for all cached OHLC: `PYTHONPATH=. .venv/bin/python src/analysis/compute_indicators.py --timeframes monthly,daily,4h [--limit N] [--start N] [--pairs ALT1,ALT2]`
- Outputs under `data/indicators/{pair}_{tf}_indicators.parquet` with:
  - monthly: ema_5, ema_12
  - daily: ema_5, ema_30, ema_50, ema_200
  - 4h: ema_5, ema_7
- Requires cached OHLC in `data/cache/` and pairs list in `data/pairs_usd.csv` (export with `main.py --export-pairs` if missing).

## Scoring logic (no hard fail)
- Each timeframe gets a pattern score (0..1) for descending highs; small breaks reduce the score instead of hard-failing the pair.
- Volume decline and proximity to POC contribute to per-timeframe score.
- Scores are weighted across monthly/daily/4h; Solana memecoins get +1.

## Scoring highlights
- Hard fail if any timeframe violates strict lower highs (zero tolerance).
- Volume profile POC proximity and volume decline contribute to score.
- Solana memecoins get +1 (base asset in the allowlist).
