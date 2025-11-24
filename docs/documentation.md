# Project Documentation
Summary
- Goal: identify USD-quoted Kraken spot pairs showing waning hype (descending highs across monthly/daily/4h) with volume context. No trading/execution.
- Output: ranked list + CSV/JSON + Plotly HTML charts. SOL memecoins get +1 bonus.

Setup
- Host: Windows 11 + WSL2 (Ubuntu), Python 3.13, `uv`, VS Code. Workspace root `/mnt/d`.
- Install deps: `uv pip install -r requirements.txt`.
- Run: `uv run python main.py --top 15 --refresh --export-pairs [--pairs JTOUSD,BONKUSD] [--plotly-top 5]`.
- Data/cache: `data/cache/{pair}_{tf}.parquet`; results: `results/analysis.*` + Plotly HTML; pair list: `data/pairs_usd.csv` (via `--export-pairs`).
- Env: `.env` for future private keys; public OHLC does not require auth.
- Current cache status: monthly OHLCV fetched for ~682 USD pairs (batched via `--timeframes monthly` and start/limit).
- Scoring mode: `PATTERN_DETECTOR_VERSION=2` (rule-based highs + strict EMA slopes); daily requires ema_50 descending (ema_200 enforced when available), 4h requires ema_7 descending with a small tolerance; missing/insufficient EMA data fails the timeframe. Recent-high checks: monthly current high ≤ prior month; daily recent 7d high ≤ prior 23d; 4h last 12 bars high ≤ earlier bars in 7d.
- Indicators: run `PYTHONPATH=. .venv/bin/python src/analysis/compute_indicators.py --timeframes monthly,daily,4h` (supports `--limit/--start/--pairs`) to generate VWMA Parquets under `data/indicators/{pair}_{tf}_indicators.parquet`:
  - monthly: vwma_5, vwma_12
  - daily: vwma_5, vwma_30, vwma_50, vwma_200
  - 4h: vwma_5, vwma_7
  Pairs source: `data/pairs_usd.csv` (export via main.py if missing). Uses cached OHLC in `data/cache`.

Architecture (refs: docs/PLAN.md)
- Config: `config/settings.py` (timeframes, cache TTLs, pattern detector selector, rate pacing 1.1s/request, paths; SOL bonus now 0).
- API: `src/api/kraken_client.py` (public REST + pacing), `src/api/data_fetcher.py` (USD pair discovery, OHLC fetch, resample monthly with `ME`, cache, pair CSV export).
- Analysis: `src/analysis/pattern_detector.py` (legacy scored descending-highs), `src/analysis/pattern_detector2.py` (rule-based highs + strict EMA slope checks), `src/analysis/volume_profile.py` (POC/VA).
- Scoring: `src/scoring/coin_ranker.py` (pattern score + volume decline + POC distance; weighted by timeframe; no SOL bonus).
- Indicators: `src/analysis/compute_indicators.py` produces EMA Parquets (monthly ema_5/12; daily ema_5/30/50/200; 4h ema_5/7) under `data/indicators/` for detector v2.
- Output: `src/outputs/report.py` (console, CSV/JSON export, Plotly HTML; summary page with sparklines and filters).
- Entry: `main.py` CLI orchestrator; picks detector via `PATTERN_DETECTOR_VERSION` (v2 currently active).

Indicators/logic (current)
- Pattern: local highs via `argrelextrema`; score 0..1 for descending steps, penalties for breaks; slope < 0 boosts score.
- Volume: decline score (early vs recent), POC proximity score via histogram profile.
- Aggregation: monthly/daily/4h weights from settings; no hard fail—rank all; Solana base gets +1.

Rate limits
- Public REST paced at 1.1s between calls (`PUBLIC_MIN_INTERVAL_SEC`). Adjust if Kraken guidance changes. Consider backoff on 429/5xx if observed.

Testing
- Smoke: `uv run python main.py --limit 3 --refresh` (live Kraken). Add mocks/unit tests later for pattern and caching.
- Batch seed examples:
  - Monthly only (batched): `uv run python main.py --refresh --timeframes monthly --start 0 --limit 80` (repeat with start offsets)
  - Daily only: `uv run python main.py --refresh --timeframes daily --start 0 --limit 80`
  - 4h only: `uv run python main.py --refresh --timeframes 4h --start 0 --limit 80`

Docs
- Plan: `docs/PLAN.md` (universe, scoring, stack).
- Usage: `docs/USAGE.md` (flags, outputs).

References
- Kraken API docs: https://docs.kraken.com/api/
- Kraken API specs (OpenAPI): https://github.com/krakenfx/api-specs
- Alt SDKs (reference only): https://pypi.org/project/krakipy/ https://pypi.org/project/krakenex/
- GitHub remote (to push when ready): https://github.com/Crumbgrabber/Kraken-API-crypto-coin-analysis-with-python

Browser automation toolbox
- Playwright (Windows) at `C:\Users\User\Documents\codex-browser`; run `cmd.exe /C C:\Users\User\Documents\codex-browser\codex-browser.bat <url> [--selector ...] [--slug ...] [--headed]`. Outputs to `C:\Users\User\Documents\codex_browser_captures`.
- If Playwright blocked, start MCP hub (`cd /mnt/d/mcphub && ./scripts/start-hub.sh --no-watch`) and use Tavily MCP (`tavily-search`) for research.
