# CRUMBGRABBER Crypto Meme and coin Scanner

![CRUMBGRABBER summary](docs/summary.png)

## Scans 600+ coins using the Kraken API to find the best ones for shorting, with additional long logic.

It was impossible for me to look at 600 plus coins with the monthly. daily, and 4 hour charts, all at once to find suitable coins to short, so the idea was to automate part of this process using the Kraken API, along with Python and Plotly. Kraken doesn't have great robust scanners like a lot of major brokers do, and only pulling the daily OHLC with the larger time frames its possible to pull this off with only a personal API key. You will have to get that from Kraken though to make this work.

Note: I sometimes publish them at [crumbgrabber.trading](https://crumbgrabber.trading) or on some of the other socials you can find at [crumbgrabber.trading/bin/view/Contact Us/](https://crumbgrabber.trading/bin/view/Contact%20Us/) if you don't want to bother with installing the whole repo.

 The goal is to pull every available USD spot pair from the Kraken API using your own personal API key/token, scan them in Python, and surface the weakest names (especially meme coins) as short candidates. It looks for persistent lower highs across multiple timeframes, scores each coin, and writes a sortable HTML report with sparklines plus return columns.

Tried a bunch of different logic, and its ever evolving, but the basic idea is to look for the traditional meme coin hype cycle, where it may go up for the first month or two or longer, but then comes the inevitable small hype cycles which never seem to break the previous high, and each cycle is lower, until the coin eventually dies and gets delisted.

Latest Rev we are scoring things both positively and negatively, and I tried to keep the logic as simple as possible. We basically still take the three time frames with a few moving averages, Percentage of return on investment, average slope across all three time frames, and a couple rules about higher highs and higher lows. Added a configure file so the user can adjust the weights right now of course higher time frames are worth a lot more than the lower timeframes.

Right now Kraken is the only data source, but maybe in future revs we will try to add sentiment and other metrics from other data sources to make it more robust. 

It generates an html file that has sortable columns, and uses plotly to generate its own charts and summary html file. If you click on any of the charts in the summary file, they are all in that same folder, so they all open big when you click on them, even though they are small size to be in line and you can see the monthly, daily, and 4 hour charts at a glance.

The thumbnails are line charts, but when you click on a chart, the bigger ones use candlesticks. The idea is get a basic idea from the summary, then click on whatever chart interests you to zoom in closer. This means that there are a lot of plotly html files in the folder, and they get regenerated each time you run the report. Works for me. On my kind of non robust computer I have to have at least a 60 minute timeout to make sure the script fully runs and all of the things fully generate so it does take a bit of time.

## Getting started
1) **Clone and env**  
   ```bash
   python -m venv .venv
   . .venv/bin/activate
   uv pip install -r requirements.txt
   cp .env.example .env  # add your Kraken API key/token if you want private endpoints; public OHLC works without
   ```

2) **Run the scanner** (uses cached data when present; stays just under the 1 req/sec personal rate limit):  
   - Quick run:  
     ```bash
     uv run python main.py --top 50
     ```
   - Long run with auto-deps + timeout:  
     ```bash
     ./run_main.sh --refresh
     ```
     (activates `.venv`, loads `.env`, updates `requirements.txt` via `uv`, then runs `main.py` with a 60-minute timeout)

   Useful flags:
   - `--refresh` to ignore cache and refetch OHLC
   - `--timeframes monthly,daily,4h` to limit frames
   - `--limit N` / `--start N` to batch through the pair list

   - For the full 600+ pair run, budget ~45–60 minutes (set a generous process timeout if your shell enforces one).
   - For a quick smoke test, use `--limit 25` (or similar) to keep runtimes short.

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
- `run_main.sh` — helper to activate the venv, load `.env`, update deps with `uv`, and run `main.py` under a 60-minute timeout

## How it works (short)
- Discovers USD spot pairs via Kraken API.
- Fetches OHLC for monthly, daily, and 4h (cached to avoid hammering Kraken).
- Detects descending-high patterns and volume profile proximity.
- Scores timeframes using indicator votes (EMA slopes, returns, N-bars up/down) and aggregates to a single score (more negative = better short candidate; Solana meme coins get a small bonus).
- Writes CSV/JSON plus HTML with mini charts and sortable columns.

## Notes and limits
- Public OHLC calls do not require a key; private endpoints would need your API key/secret.
- Script is rate-limited to slightly under 1 req/sec to fit Kraken personal API limits.
- Caching lives under `data/cache` so re-runs are much faster.

## Disclaimer
This is not investment advice or an offer to buy/sell any security or token. Educational use only. Do not trade with funds you cannot afford to lose, and obey your local laws. The author assumes no responsibility for any actions you take with this code. If published, this repository is under the MIT license with no warranties, express or implied.

## License
MIT — see [LICENSE](LICENSE).
