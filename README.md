# CRUMBGRABBER Crypto Short Scanner

![CRUMBGRABBER summary](docs/summary.png)

## What this project does
The goal is to pull every available USD spot pair from the Kraken API using your own personal API key/token, scan them in Python, and surface the weakest names (especially meme coins) as short candidates. It looks for persistent lower highs across multiple timeframes, scores each coin, and writes a sortable HTML report with sparklines plus return columns.

Core ideas:
- Hype coins often drift into a series of lower highs as early holders sell into retail buyers.
- We check monthly, daily, and 4h charts for that lower-high pattern and weigh the timeframes.
- Year-to-date, 30-day, and 7-day returns are included for quick sorting.
- Each coin gets a score; higher means “more shortable” in theory.

## Getting started
1) **Clone and env**  
   ```bash
   python -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env  # add your Kraken API key/token if you want private endpoints; public OHLC works without
   ```

2) **Run the scanner** (uses cached data when present; stays just under the 1 req/sec personal rate limit):  
   ```bash
   .venv/bin/python main.py --top 50
   ```
   Useful flags:
   - `--refresh` to ignore cache and refetch OHLC
   - `--timeframes monthly,daily,4h` to limit frames
   - `--limit N` / `--start N` to batch through the pair list

3) **Open the report**  
   - `results/summary.html` for the full sortable table and sparklines  
   - `results/{PAIR}.html` and `{PAIR}_{tf}.html` for Plotly charts  
   - `results/analysis.csv` and `results/analysis.json` for raw scores

## Project layout
- `config/` — runtime settings
- `data/` — cached assets, pairs, and OHLC pulls
- `docs/` — repo docs (includes the screenshot above)
- `results/` — generated charts and summary HTML
- `src/` — analysis, scoring, outputs code
- `main.py` — entrypoint that orchestrates discovery, scoring, and exports

## How it works (short)
- Discovers USD spot pairs via Kraken API.
- Fetches OHLC for monthly, daily, and 4h (cached to avoid hammering Kraken).
- Detects descending-high patterns and volume profile proximity.
- Scores timeframes and aggregates to a single coin score (Solana meme coins get a small bonus).
- Writes CSV/JSON plus HTML with mini charts and sortable columns.

## Notes and limits
- Public OHLC calls do not require a key; private endpoints would need your API key/secret.
- Script is rate-limited to slightly under 1 req/sec to fit Kraken personal API limits.
- Caching lives under `data/cache` so re-runs are much faster.

## Disclaimer
This is not investment advice or an offer to buy/sell any security or token. Educational use only. Do not trade with funds you cannot afford to lose, and obey your local laws. The author assumes no responsibility for any actions you take with this code. If published, this repository is under the MIT license with no warranties, express or implied.

## License
MIT — see [LICENSE](LICENSE).
