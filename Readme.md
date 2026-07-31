# Portfolio Tracker

A lightweight, read-only web app to track stock portfolio performance — built as a faster alternative to Robinhood / Schwab mobile apps.

## Problem Statement

I check my portfolio multiple times a day, but Schwab / Robinhood are heavy apps with a lot of functionality I don't need for a quick glance. They are slow on mobile and bury the info I actually want: daily P/L and total return.

## Main Use Case

Get a quick glance of how my stocks are performing daily with a minimal UI. No trading, no heavy charts — just holdings, daily gain/loss, and a price chart when a ticker is selected.

## Current Features

- Holdings table with avg purchase price, quantity, last price, total gain, daily gain
- Top daily gainers / losers cards
- Single-row selection to view price chart with SMA (50/100/200 day)

## Stack

1. **DuckDB** — local file DB (`data/portfolio.db`)
2. **Python + Pandas** — data manipulation
3. **yfinance** — market data
4. **Streamlit** — UI / web app
5. **Docker + Tailscale** — deploy to home server and access via tailnet

## Project Structure

```
.
├── app.py              # Streamlit entrypoint — orchestration only
├── src/
│   ├── config.py       # DB_PATH from env
│   ├── db.py           # DuckDB connection, init, get_purchase_history
│   ├── market.py       # yfinance wrappers, batch download
│   ├── metrics.py      # delta, total_return, daily_return (pure functions)
│   └── ui.py           # render_* components (no data fetching)
├── scripts/
│   └── backfill.py     # rebuild DB from Schwab CSV
├── data/               # gitignored — holds portfolio.db
├── stock_data/         # gitignored — Schwab exports
├── Dockerfile
└── requirements.txt
```

## Getting Started

### Local dev
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# first time only — place Schwab CSV in stock_data/ then:
mkdir -p data
python scripts/backfill.py

streamlit run app.py
```

### New device / after git pull
`data/` and `stock_data/` are gitignored for privacy, so they won't exist after clone. Copy your CSV from device 1 (AirDrop / `tailscale file cp` / scp) and rebuild:

```bash
mkdir -p data stock_data
# copy schwab_*.csv into stock_data/
python scripts/backfill.py
```

### Docker
```bash
docker build -t portfolio-tracker .

docker run --rm -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  -e DB_PATH=/app/data/portfolio.db \
  portfolio-tracker
```
Open http://localhost:8501

For Tailscale:
```bash
docker run -d --restart unless-stopped -p 127.0.0.1:8501:8501 \
  -v /path/to/data:/app/data -e DB_PATH=/app/data/portfolio.db \
  --name portfolio portfolio-tracker

tailscale serve --bg 8501   # then access via https://<machine>.ts.net
```

## Security Note

Never commit `data/` or `stock_data/` — they contain real positions and account IDs. Keep them gitignored. Git history retains files forever even if you later ignore them.

## TODO / Roadmap

### P0 — Critical Bugs
- [ ] Fix SQL injection in `insert_stock_purchase` — use parameterized queries everywhere (`src/db.py:15` pattern)
- [ ] Fix `st.set_page_config` must be first Streamlit call (currently after `st.title()` in `app.py`)
- [ ] Fix `get_previous_day_stock_price` — fails on weekends/holidays, returns Series not float, double `reset_index()` — use `5d` history + tail(2)
- [ ] Fix pure-function violation — `get_latest_price_for_purchased_stocks(purchased_stocks)` overwrites arg with global `purchase_history` in `src/market.py:14`

### P1 — Code Quality
- [ ] Split `src/ui.py:get_stock_portfolio_table` (105 lines) into `render_portfolio_table() -> selected_ticker`, `render_stock_controls() -> (period, sma)`, `render_stock_chart(data)` — no data fetching inside UI
- [ ] Rename `get_*` UI functions to `render_*` and remove `st.stop()` from inside helpers
- [ ] Standardize DataFrame mutation — use `.assign()` instead of mixed `.copy()` + in-place mutation (`src/metrics.py`)
- [ ] Batch yfinance calls — replace per-ticker loop in `market.py:26` with single `yf.download(tickers, period="5d")` + `@st.cache_data(ttl=60)`
- [ ] Pin versions in `requirements.txt`, add `.dockerignore`, fix Dockerfile HEALTHCHECK (needs `curl`), remove `.venv` 0-byte file
- [ ] Fix `app.py` to not use `if __name__ == '__main__'` — Streamlit doesn't need it

### P2 — Simple Features (not rebuilding Robinhood)
- [ ] **Portfolio value over time** — daily snapshot table `portfolio_snapshots(date, total_value)` + area chart — highest value feature
- [ ] **Allocation view** — donut chart by ticker / sector (`yf.Ticker.info['sector']`) + concentration warning >15%
- [ ] **Benchmark overlay** — portfolio % growth vs SPY/QQQ normalized to 100
- [ ] **Period returns** — WTD, MTD, YTD metrics on top (reuse `Close` at period start)
- [ ] **Driver analysis** — bar chart of `daily_return` by ticker: "what drove today's P/L"
- [ ] **Dividend income** — `yf.Ticker.dividends` * quantity, yield on cost
- [ ] **Watchlist** — separate `watchlist` table, same chart component, no qty

### P3 — DevOps / Polish
- [ ] `docker-compose.yml` with app + tailscale sidecar
- [ ] Add `data/.gitkeep` + README instructions for init
- [ ] Add logging instead of `print()`, add `ruff` + `mypy`
- [ ] README badges, sample screenshot