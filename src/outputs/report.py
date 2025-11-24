from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import settings
from src.scoring.coin_ranker import TimeframeOutcome
from src.types import PairResult

matplotlib.use("Agg")

logger = logging.getLogger(__name__)


# ---------- Small helpers ----------
def _format_pct(val: float | None) -> str:
    if val is None or pd.isna(val):
        return "—"
    return f"{val*100:.3f}%"


def _format_slope(val: float | None) -> str:
    if val is None or pd.isna(val):
        return "—"
    return f"{val:.4f}"


def _format_num(val: float | None) -> str:
    if val is None or pd.isna(val):
        return "—"
    if abs(val) >= 1_000_000:
        return f"{val/1_000_000:.2f}M"
    if abs(val) >= 1_000:
        return f"{val/1_000:.2f}K"
    return f"{val:.2f}"


def _safe_tail(df: pd.DataFrame, days: int) -> pd.DataFrame:
    if df.empty:
        return df
    cutoff = pd.Timestamp.now(tz=timezone.utc) - timedelta(days=days)
    return df[df["time"] >= cutoff]


def _compute_returns(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"ytd": None, "d30": None, "d7": None}
    last_close = df["close"].iloc[-1]
    now = pd.Timestamp.now(tz=timezone.utc)
    start_year = pd.Timestamp(year=now.year, month=1, day=1, tz=timezone.utc)
    ytd_df = df[df["time"] >= start_year]
    ret_ytd = None
    if not ytd_df.empty:
        first = ytd_df["close"].iloc[0]
        if first != 0:
            ret_ytd = (last_close - first) / first
    d30_df = _safe_tail(df, 30)
    ret_30 = None
    if not d30_df.empty:
        first = d30_df["close"].iloc[0]
        if first != 0:
            ret_30 = (last_close - first) / first
    d7_df = _safe_tail(df, 7)
    ret_7 = None
    if not d7_df.empty:
        first = d7_df["close"].iloc[0]
        if first != 0:
            ret_7 = (last_close - first) / first
    return {"ytd": ret_ytd, "d30": ret_30, "d7": ret_7}


def _sparkline_b64(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    fig, ax = plt.subplots(figsize=(3, 0.9))
    ax.plot(df["time"], df["close"], color="#2a9d4b", linewidth=1.25)
    ax.axis("off")
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("ascii")


def _load_oi_funding() -> dict:
    path = settings.FUTURES_TICKERS_PARQUET
    if not path.exists():
        return {}
    try:
        df = pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read %s: %s", path, exc)
        return {}
    df = df.rename(columns=str.lower)
    mapping = {}
    for _, row in df.iterrows():
        key = (row.get("pair") or row.get("symbol") or "").replace("/", "").upper()
        if not key:
            continue
        mapping[key] = {
            "oi": row.get("openinterest"),
            "funding": row.get("fundingrate"),
        }
    return mapping


def _timeframe_map(outcomes: Iterable[TimeframeOutcome]) -> dict:
    return {o.name: o for o in outcomes}


def _yesterday_volume(df: pd.DataFrame) -> float | None:
    """Sum yesterday's volume for a daily frame (returns None if missing)."""
    if df.empty or "volume" not in df.columns:
        return None
    yday = (datetime.now(tz=timezone.utc) - timedelta(days=1)).date()
    mask = df["time"].dt.date == yday
    if mask.any():
        return float(df.loc[mask, "volume"].sum())
    return None


# ---------- Console and tabular exports ----------
def summarize_to_console(results: List[PairResult], top_n: int = 20) -> None:
    print("Top pairs:")
    print(f"{'Pair':10} {'Score':>8} {'M':>3} {'D':>3} {'4h':>3}")
    for res in results[:top_n]:
        tf_map = _timeframe_map(res.outcomes)
        m = "Y" if tf_map.get("monthly", TimeframeOutcome("", None, None, 0, 0)).passed else "N"
        d = "Y" if tf_map.get("daily", TimeframeOutcome("", None, None, 0, 0)).passed else "N"
        h = "Y" if tf_map.get("4h", TimeframeOutcome("", None, None, 0, 0)).passed else "N"
        print(f"{res.wsname:10} {res.score:8.3f} {m:>3} {d:>3} {h:>3}")


def export_tabular(results: List[PairResult], csv_path: Path, json_path: Path) -> None:
    rows: List[dict] = []
    for res in results:
        tf_map = _timeframe_map(res.outcomes)
        monthly = tf_map.get("monthly")
        daily = tf_map.get("daily")
        h4 = tf_map.get("4h")
        rows.append(
            {
                "pair": res.pair,
                "wsname": res.wsname,
                "score": res.score,
                "is_solana_bonus": res.is_solana,
                "monthly_passed": monthly.passed if monthly else False,
                "monthly_slope": monthly.pattern.slope if monthly else 0.0,
                "monthly_pattern_score": monthly.pattern.score if monthly else 0.0,
                "monthly_volume_decline": monthly.volume_decline_score if monthly else 0.0,
                "monthly_poc_score": monthly.poc_distance_score if monthly else 0.0,
                "daily_passed": daily.passed if daily else False,
                "daily_slope": daily.pattern.slope if daily else 0.0,
                "daily_pattern_score": daily.pattern.score if daily else 0.0,
                "daily_volume_decline": daily.volume_decline_score if daily else 0.0,
                "daily_poc_score": daily.poc_distance_score if daily else 0.0,
                "4h_passed": h4.passed if h4 else False,
                "4h_slope": h4.pattern.slope if h4 else 0.0,
                "4h_pattern_score": h4.pattern.score if h4 else 0.0,
                "4h_volume_decline": h4.volume_decline_score if h4 else 0.0,
                "4h_poc_score": h4.poc_distance_score if h4 else 0.0,
            }
        )
    df = pd.DataFrame(rows)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    df.to_json(json_path, orient="records", indent=2)
    logger.info("Wrote %s and %s", csv_path, json_path)


# ---------- Plotly exports ----------
def _plot_candles(df: pd.DataFrame, title: str) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
    )
    fig.add_trace(
        go.Candlestick(
            x=df["time"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(x=df["time"], y=df["volume"], name="Volume", marker_color="rgba(50,100,200,0.45)"),
        row=2,
        col=1,
    )
    fig.update_layout(title=title, showlegend=False)
    fig.update_xaxes(rangeslider_visible=False)
    return fig


def export_plotly_timeframes(results: List[PairResult], results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    for res in results:
        for tf, df in res.frames.items():
            if df is None or df.empty:
                continue
            fig = _plot_candles(df, f"{res.wsname} ({tf})")
            out = results_dir / f"{res.pair}_{tf}.html"
            fig.write_html(out, include_plotlyjs="cdn")


def export_plotly(results: List[PairResult], results_dir: Path, top_n: int) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    for res in results[:top_n]:
        # Prefer lower timeframe if available
        for tf in ("4h", "daily", "monthly"):
            df = res.frames.get(tf)
            if df is not None and not df.empty:
                fig = _plot_candles(df, f"{res.wsname} ({tf} view)")
                out = results_dir / f"{res.pair}.html"
                fig.write_html(out, include_plotlyjs="cdn")
                break


# ---------- Summary HTML ----------
def _row_class(monthly_pass: bool, daily_pass: bool, h4_pass: bool) -> str:
    if monthly_pass and daily_pass:
        return "likely-short"
    if monthly_pass or daily_pass or h4_pass:
        return "possible-long"
    return "watch"


def export_summary_html(results: List[PairResult], path: Path) -> None:
    oi_map = _load_oi_funding()
    hero_b64 = ""
    hero_img = settings.RESULTS_DIR / "crumbgrabber.png"
    if hero_img.exists():
        hero_b64 = base64.b64encode(hero_img.read_bytes()).decode("ascii")

    rows_html = []
    for res in results:
        tf_map = _timeframe_map(res.outcomes)
        monthly = tf_map.get("monthly")
        daily = tf_map.get("daily")
        h4 = tf_map.get("4h")
        df_monthly = res.frames.get("monthly", pd.DataFrame())
        df_daily = res.frames.get("daily", pd.DataFrame())
        df_4h = res.frames.get("4h", pd.DataFrame())
        returns = _compute_returns(df_daily if not df_daily.empty else df_monthly if not df_monthly.empty else df_4h)
        spark_m = _sparkline_b64(df_monthly)
        spark_d = _sparkline_b64(df_daily)
        spark_h = _sparkline_b64(df_4h)
        vol_yday = _yesterday_volume(df_daily)

        oi_key = res.pair.upper().replace("/", "")
        oi_info = oi_map.get(oi_key, {})
        oi = oi_info.get("oi")
        funding = oi_info.get("funding")

        row_class = _row_class(monthly.passed if monthly else False, daily.passed if daily else False, h4.passed if h4 else False)
        rows_html.append(
            f"""
            <tr class="{row_class}"
                data-score="{res.score}"
                data-monthly="{1 if monthly and monthly.passed else 0}"
                data-daily="{1 if daily and daily.passed else 0}"
                data-h4="{1 if h4 and h4.passed else 0}"
                data-oi="{oi if oi is not None else ''}"
                data-funding="{funding if funding is not None else ''}"
                data-vol-yday="{vol_yday if vol_yday is not None else ''}"
                data-ret-ytd="{returns['ytd'] if returns['ytd'] is not None else ''}"
                data-ret-30d="{returns['d30'] if returns['d30'] is not None else ''}"
                data-ret-7d="{returns['d7'] if returns['d7'] is not None else ''}"
                data-monthly-slope="{monthly.pattern.slope if monthly else 0.0}"
                data-daily-slope="{daily.pattern.slope if daily else 0.0}"
                data-h4-slope="{h4.pattern.slope if h4 else 0.0}"
                data-sol="{1 if res.is_solana else 0}"
            >
                <td>{res.wsname}</td>
                <td class="num">{res.score:.3f}</td>
                <td>{f"<a href='{res.pair}_monthly.html' target='_blank'><img class='spark' src='data:image/png;base64,{spark_m}' alt='monthly' /></a>" if spark_m else "—"}</td>
                <td>{f"<a href='{res.pair}_daily.html' target='_blank'><img class='spark' src='data:image/png;base64,{spark_d}' alt='daily' /></a>" if spark_d else "—"}</td>
                <td>{f"<a href='{res.pair}_4h.html' target='_blank'><img class='spark' src='data:image/png;base64,{spark_h}' alt='4h' /></a>" if spark_h else "—"}</td>
                <td class="num">{_format_num(vol_yday)}</td>
                <td class="num">{_format_slope(monthly.pattern.slope if monthly else None)}</td>
                <td class="num">{_format_slope(daily.pattern.slope if daily else None)}</td>
                <td class="num">{_format_slope(h4.pattern.slope if h4 else None)}</td>
                <td class="num">{_format_pct(returns['ytd'])}</td>
                <td class="num">{_format_pct(returns['d30'])}</td>
                <td class="num">{_format_pct(returns['d7'])}</td>
                <td class="num">{_format_num(oi)}</td>
                <td class="num">{f"{funding:.6f}" if funding is not None and not pd.isna(funding) else '—'}</td>
            </tr>
            """
        )

    hero_img_tag = f"<img src='data:image/png;base64,{hero_b64}' alt='Crumbgrabber' />" if hero_b64 else ""
    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>CRUMBGRABBER Trading Crypto Summary</title>
  <style>
    body {{ font-family: Arial, sans-serif; padding: 16px; color: #111; }}
    h1 {{ margin: 0 0 6px 0; }}
    .hero {{ display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }}
    .hero img {{ height: 64px; width: 64px; object-fit: cover; border-radius: 8px; }}
    .subtitle {{ color: #555; font-size: 13px; margin-top: -4px; }}
    .controls {{ display: none; }}
    input[type="search"] {{ display: none; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #e5e5e5; text-align: left; }}
    th.sortable {{ cursor: pointer; }}
    tr.likely-short {{ background: #f8fffa; }}
    tr.watch {{ background: #fff; }}
    .pill {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; color: #fff; }}
    .pill.pass {{ background: #2a9d4b; }}
    .pill.fail {{ background: #c0392b; }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .legend {{ font-size: 13px; color: #444; }}
    .badge {{ display: inline-block; background: #2a9d4b; color: #fff; padding: 2px 6px; border-radius: 6px; font-size: 12px; }}
    .spark {{ height: 40px; width: 120px; }}
    .filter-row {{ display: flex; gap: 18px; align-items: center; flex-wrap: wrap; margin-top: 6px; }}
    .filter-block {{ display: inline-flex; align-items: center; gap: 10px; white-space: nowrap; }}
    .pipe {{ color: #777; font-weight: 700; }}
    select {{ padding: 6px 8px; border: 1px solid #ccc; border-radius: 6px; }}
    .reset-btn {{ padding: 6px 10px; border: 1px solid #888; border-radius: 6px; background: #f2f2f2; cursor: pointer; }}
  </style>
</head>
<body>
  <div class="hero">
    {hero_img_tag}
    <div>
      <h1>CRUMBGRABBER Trading Crypto Summary</h1>
    </div>
  </div>
  <table id="coins">
    <thead>
      <tr>
        <th class="sortable" data-key="name">Name</th>
        <th class="sortable" data-key="score" data-type="num">Score</th>
        <th>Monthly Chart</th>
        <th>Daily Chart</th>
        <th>4h Chart</th>
        <th class="sortable" data-key="vol_yday" data-type="num">Volume yesterday</th>
        <th class="sortable" data-key="monthly_slope" data-type="num">Monthly Slope</th>
        <th class="sortable" data-key="daily_slope" data-type="num">Daily Slope</th>
        <th class="sortable" data-key="h4_slope" data-type="num">4h Slope</th>
        <th class="sortable" data-key="ret_ytd" data-type="num">Return YTD</th>
        <th class="sortable" data-key="ret_30d" data-type="num">Return 30d</th>
        <th class="sortable" data-key="ret_7d" data-type="num">Return 7d</th>
        <th class="sortable" data-key="open_interest" data-type="num">Open Interest</th>
        <th class="sortable" data-key="funding" data-type="num">Funding</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
  <script>
    const table = document.getElementById('coins').getElementsByTagName('tbody')[0];
    const headers = document.querySelectorAll('th.sortable');
    let sortState = {{ key: 'score', dir: -1 }};
    headers.forEach(h => {{
      h.addEventListener('click', () => {{
        const key = h.dataset.key;
        const type = h.dataset.type || 'text';
        sortState = sortState.key === key ? {{ key, dir: -sortState.dir }} : {{ key, dir: 1 }};
        const rows = Array.from(table.rows);
        rows.sort((a, b) => {{
          const av = value(a, key, type);
          const bv = value(b, key, type);
          if (av < bv) return -sortState.dir;
          if (av > bv) return sortState.dir;
          return 0;
        }});
        rows.forEach(r => table.appendChild(r));
      }});
    }});

    function value(row, key, type) {{
      switch (key) {{
        case 'name': return row.cells[0].innerText;
        case 'score': return parseFloat(row.dataset.score || row.cells[1].innerText) || 0;
        case 'vol_yday': return parseFloat(row.dataset.volYday || row.cells[5].innerText) || 0;
        case 'monthly_slope': return parseFloat(row.cells[6].innerText) || 0;
        case 'daily_slope': return parseFloat(row.cells[7].innerText) || 0;
        case 'h4_slope': return parseFloat(row.cells[8].innerText) || 0;
        case 'ret_ytd': return parseFloat(row.dataset.retYtd || row.cells[9].innerText) || 0;
        case 'ret_30d': return parseFloat(row.dataset.ret30d || row.cells[10].innerText) || 0;
        case 'ret_7d': return parseFloat(row.dataset.ret7d || row.cells[11].innerText) || 0;
        case 'open_interest': return parseFloat(row.dataset.oi || row.cells[12].innerText.replace(/,/g,'')) || 0;
        case 'funding': return parseFloat(row.dataset.funding || row.cells[13].innerText) || 0;
        default: return row.cells[0].innerText;
      }}
    }}
  </script>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    logger.info("Wrote summary HTML -> %s", path)
