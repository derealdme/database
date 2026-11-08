"""Step 3. Tiny seed for CI (the Kaggle data is not in the repo).

Run from backend/ after the schema is loaded:  python tests/fixtures/seed_ci.py
Inserts: 2 sectors, 3 stocks (AAPL, MSFT, XOM), 1 financial_snapshot each,
30 days of stock_prices each, CALL sp_refresh_latest_prices(), 1 test user,
20 news_articles in Mongo. Idempotent: safe to run twice.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db import mongo, mysql  # noqa: E402

SECTORS = ["Technology", "Energy"]

STOCKS = [
    ("AAPL", "Apple Inc.", "Technology"),
    ("MSFT", "Microsoft Corporation", "Technology"),
    ("XOM", "Exxon Mobil Corporation", "Energy"),
]

SNAPSHOT_DATE = date(2023, 12, 29)

SNAPSHOTS = {
    "AAPL": dict(snapshot_price=192.53, pe_ratio=31.5, eps=6.11, dividend_yield=0.0044,
                 market_cap=3_000_000_000_000, ebitda=125_820_000_000,
                 price_sales_ratio=7.8, price_book_ratio=48.1,
                 week52_low=124.17, week52_high=199.62),
    "MSFT": dict(snapshot_price=376.04, pe_ratio=35.8, eps=10.51, dividend_yield=0.0073,
                 market_cap=2_800_000_000_000, ebitda=105_000_000_000,
                 price_sales_ratio=12.9, price_book_ratio=14.6,
                 week52_low=213.43, week52_high=384.30),
    "XOM": dict(snapshot_price=102.09, pe_ratio=10.2, eps=9.89, dividend_yield=0.0346,
                market_cap=411_000_000_000, ebitda=55_000_000_000,
                price_sales_ratio=1.2, price_book_ratio=2.1,
                week52_low=95.77, week52_high=120.70),
}

# Base close per ticker; prices walk a small fixed pattern so re-running
# the script produces byte-identical rows (idempotent, no randomness).
PRICE_BASE = {"AAPL": 190.0, "MSFT": 370.0, "XOM": 100.0}
PRICE_DAYS = 30

DEMO_USER = ("ci_demo", "ci_demo@example.com", "ci-demo-password-123")

NEWS_COUNT = 20
SENTIMENT_CYCLE = [
    (0.8, "positive"), (0.0, "neutral"), (-0.6, "negative"),
]


def seed_sectors_and_stocks() -> dict[str, int]:
    for name in SECTORS:
        mysql.execute(
            "INSERT INTO sectors (sector_name) VALUES (:name)"
            " ON DUPLICATE KEY UPDATE sector_name = VALUES(sector_name)",
            {"name": name},
        )
    sector_ids = {
        row["sector_name"]: row["sector_id"]
        for row in mysql.query("SELECT sector_id, sector_name FROM sectors")
    }

    for ticker, company_name, sector_name in STOCKS:
        mysql.execute(
            "INSERT INTO stocks (ticker, company_name, sector_id)"
            " VALUES (:ticker, :name, :sid)"
            " ON DUPLICATE KEY UPDATE company_name = VALUES(company_name),"
            " sector_id = VALUES(sector_id)",
            {"ticker": ticker, "name": company_name, "sid": sector_ids[sector_name]},
        )

    rows = mysql.query("SELECT stock_id, ticker FROM stocks")
    return {row["ticker"]: row["stock_id"] for row in rows if row["ticker"] in PRICE_BASE}


def seed_financial_snapshots(stock_ids: dict[str, int]) -> None:
    for ticker, stock_id in stock_ids.items():
        fields = SNAPSHOTS[ticker]
        mysql.execute(
            """
            INSERT INTO financial_snapshots
                (stock_id, as_of_date, snapshot_price, pe_ratio, eps,
                 dividend_yield, market_cap, ebitda, price_sales_ratio,
                 price_book_ratio, week52_low, week52_high)
            VALUES
                (:stock_id, :as_of_date, :snapshot_price, :pe_ratio, :eps,
                 :dividend_yield, :market_cap, :ebitda, :price_sales_ratio,
                 :price_book_ratio, :week52_low, :week52_high)
            ON DUPLICATE KEY UPDATE
                snapshot_price = VALUES(snapshot_price),
                pe_ratio = VALUES(pe_ratio),
                eps = VALUES(eps),
                dividend_yield = VALUES(dividend_yield),
                market_cap = VALUES(market_cap),
                ebitda = VALUES(ebitda),
                price_sales_ratio = VALUES(price_sales_ratio),
                price_book_ratio = VALUES(price_book_ratio),
                week52_low = VALUES(week52_low),
                week52_high = VALUES(week52_high)
            """,
            {"stock_id": stock_id, "as_of_date": SNAPSHOT_DATE, **fields},
        )


def seed_stock_prices(stock_ids: dict[str, int]) -> None:
    for ticker, stock_id in stock_ids.items():
        base = PRICE_BASE[ticker]
        for day_offset in range(PRICE_DAYS):
            price_date = SNAPSHOT_DATE - timedelta(days=(PRICE_DAYS - 1 - day_offset))
            # Deterministic small saw-tooth so high >= low and close >= 0
            # always hold, with no randomness between runs.
            wobble = (day_offset % 5) - 2  # -2..2
            close = round(base + wobble, 2)
            open_ = round(close - 0.5, 2)
            high = round(max(open_, close) + 1.0, 2)
            low = round(min(open_, close) - 1.0, 2)
            mysql.execute(
                """
                INSERT INTO stock_prices
                    (stock_id, price_date, open_price, high_price, low_price,
                     close_price, adjusted_close, volume)
                VALUES
                    (:stock_id, :price_date, :open_price, :high_price, :low_price,
                     :close_price, :close_price, :volume)
                ON DUPLICATE KEY UPDATE
                    open_price = VALUES(open_price),
                    high_price = VALUES(high_price),
                    low_price = VALUES(low_price),
                    close_price = VALUES(close_price),
                    adjusted_close = VALUES(adjusted_close),
                    volume = VALUES(volume)
                """,
                {
                    "stock_id": stock_id,
                    "price_date": price_date,
                    "open_price": open_,
                    "high_price": high,
                    "low_price": low,
                    "close_price": close,
                    "volume": 1_000_000 + day_offset * 1000,
                },
            )


def refresh_latest_prices() -> None:
    with mysql.connection() as conn:
        conn.execute(text("CALL sp_refresh_latest_prices()"))


def seed_user() -> None:
    username, email, password = DEMO_USER
    mysql.execute(
        "INSERT INTO users (username, email, password_hash)"
        " VALUES (:username, :email, :hash)"
        " ON DUPLICATE KEY UPDATE email = VALUES(email),"
        " password_hash = VALUES(password_hash)",
        {"username": username, "email": email, "hash": hash_password(password)},
    )


def seed_mongo_news(stock_ids: dict[str, int]) -> None:
    mongo.ensure_collections()
    db = mongo.get_db()
    coll = db[mongo.NEWS]
    tickers = list(stock_ids.keys())

    for i in range(NEWS_COUNT):
        ticker = tickers[i % len(tickers)]
        score, label = SENTIMENT_CYCLE[i % len(SENTIMENT_CYCLE)]
        published_at = datetime(2023, 12, 1, tzinfo=timezone.utc) + timedelta(days=i)
        headline = f"{ticker} CI seed headline #{i}"
        doc_id = hashlib.sha256(f"{ticker}|{published_at.isoformat()}|{headline}".encode()).hexdigest()
        coll.update_one(
            {"_id": doc_id},
            {
                "$set": {
                    "ticker": ticker,
                    "headline": headline,
                    "url": None,
                    "publisher": "CI Fixture",
                    "published_at": published_at,
                    "source": "seed_ci.py",
                    "sentiment": {"score": score, "label": label, "terms": []},
                }
            },
            upsert=True,
        )


def main() -> None:
    stock_ids = seed_sectors_and_stocks()
    seed_financial_snapshots(stock_ids)
    seed_stock_prices(stock_ids)
    refresh_latest_prices()
    seed_user()
    seed_mongo_news(stock_ids)

    n_stocks = mysql.query_one("SELECT COUNT(*) AS n FROM stocks")["n"]
    n_prices = mysql.query_one("SELECT COUNT(*) AS n FROM stock_prices")["n"]
    n_news = mongo.get_db()[mongo.NEWS].count_documents({"source": "seed_ci.py"})
    print(f"seed_ci: stocks={n_stocks} prices={n_prices} news={n_news}")


if __name__ == "__main__":
    main()
