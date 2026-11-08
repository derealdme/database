# QuantScore

INF2003 Database Systems group project. An S&P 500 research and paper-trading platform built on two databases:

- **MySQL 8**: stocks, sectors, fundamentals snapshots, daily prices, users, portfolios, transactions, watchlists. 12 tables, 8 views, 3 stored procedures, 2 triggers.
- **MongoDB 7**: news articles with sentiment, company profiles, research notes, activity logs, benchmark prices. 5 collections with JSON-schema validators.

Stack: FastAPI (Python 3.11) + React 18 (Vite). Data: three Kaggle datasets (prices, constituents' financials, financial news headlines).

## Features

| Feature | Store | Where |
|---|---|---|
| Stock search, detail, sector context | MySQL | `routers/stocks.py`, `StockSearch.jsx`, `StockDetail.jsx` |
| QuantScore factor ranking | MySQL views | `services/scoring.py`, `Scores.jsx` |
| Screener and comparison | MySQL | `services/screener.py`, `Screener.jsx` |
| Portfolio simulator | MySQL procedure `sp_execute_trade` | `services/portfolio.py`, `Portfolio.jsx` |
| News, sentiment, research notes | MongoDB | `services/news.py`, `services/notes.py`, `Sentiment.jsx`, `Notes.jsx` |
| SQL vs NoSQL benchmark | both | `services/benchmark.py`, `services/throughput.py`, `Benchmark.jsx` |

## Scoring: what the factors really are

QuantScore combines four sector-relative sub-scores (50 = sector average). Two are proxies, and the app labels them as such:

- **Valuation**: P/E, P/S, P/B versus sector.
- **Profitability (proxy)**: earnings yield and EBITDA / market cap. Both are divided by price, so this overlaps with valuation.
- **Growth (proxy: price momentum)**: 1-year price return versus sector and 52-week range position. Not revenue or earnings growth.
- **Dividend**: dividend yield versus sector.

Sentiment is a keyword baseline and has not been validated against labelled data.

## Run it

Full instructions: **[docs/SETUP.md](docs/SETUP.md)**.

Short version: `docker compose up -d`, copy `.env.example` to `.env`, `pip install -r backend/requirements.txt`, `python etl/run_all.py`, `python backend/run.py`, then `npm ci && npm run dev` in `frontend/`.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/unit                       # no database needed
RUN_INTEGRATION=1 pytest tests/integration   # needs MySQL + MongoDB
```

## Other docs

- [docs/ER-diagram.md](docs/ER-diagram.md)
- [docs/performance-analysis.md](docs/performance-analysis.md)
