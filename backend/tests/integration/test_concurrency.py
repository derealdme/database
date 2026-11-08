"""Step 5. Parallel buys on one portfolio."""
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy.exc import DBAPIError

from app.db import mysql
from app.services.portfolio import create_portfolio

from tests._helpers import todo

pytestmark = pytest.mark.integration

TEST_USERNAME = "it_concurrency_user"
TEST_TICKER = "AAPL"
N_WORKERS = 20
AFFORDABLE_BUYS = 10


@pytest.fixture()
def seed_user_id() -> int:
    row = mysql.query_one(
        "SELECT user_id FROM users WHERE username = :u", {"u": TEST_USERNAME})
    if row:
        return row["user_id"]
    return mysql.insert_returning_id(
        "INSERT INTO users (username, email, password_hash)"
        " VALUES (:u, :e, :h)",
        {"u": TEST_USERNAME, "e": f"{TEST_USERNAME}@example.com", "h": "x" * 60},
    )


@pytest.fixture()
def latest_price() -> float:
    row = mysql.query_one(
        "SELECT p.close_price FROM stock_latest_price p"
        " JOIN stocks s ON s.stock_id = p.stock_id"
        " WHERE s.ticker = :t",
        {"t": TEST_TICKER},
    )
    if row is None:
        pytest.skip(
            f"{TEST_TICKER} has no row in stock_latest_price; "
            "run tests/fixtures/seed_ci.py first"
        )
    return float(row["close_price"])


@pytest.fixture()
def funded_portfolio(seed_user_id, latest_price):
    # Enough cash for exactly AFFORDABLE_BUYS one-share buys, fee included,
    # so 20 concurrent attempts must leave at least 10 rejected.
    cost_per_share = latest_price * 1.0005
    initial_cash = round(cost_per_share * AFFORDABLE_BUYS + 1, 2)
    name = f"it-concurrency-{uuid.uuid4().hex[:8]}"
    return create_portfolio(seed_user_id, name, initial_cash)


def _attempt_buy(portfolio_id: int) -> bool:
    try:
        mysql.call_trade_procedure(portfolio_id, TEST_TICKER, "BUY", 1, 0.0005)
        return True
    except DBAPIError as exc:
        if "INSUFFICIENT_CASH" in str(exc):
            return False
        raise


def test_parallel_buys_never_overdraw_cash(funded_portfolio):
    pid = funded_portfolio["portfolio_id"]

    with ThreadPoolExecutor(max_workers=N_WORKERS) as pool:
        results = list(pool.map(_attempt_buy, [pid] * N_WORKERS))

    successes = sum(results)
    assert successes <= AFFORDABLE_BUYS

    cash = mysql.query_one(
        "SELECT cash_balance FROM portfolios WHERE portfolio_id = :p", {"p": pid}
    )["cash_balance"]
    assert cash >= 0


def test_ledger_matches_holdings_after_parallel_buys(funded_portfolio):
    pid = funded_portfolio["portfolio_id"]

    with ThreadPoolExecutor(max_workers=N_WORKERS) as pool:
        list(pool.map(_attempt_buy, [pid] * N_WORKERS))

    ledger_qty = mysql.query_one(
        "SELECT COALESCE(SUM(quantity), 0) AS q FROM transactions"
        " WHERE portfolio_id = :p AND transaction_type = 'BUY'",
        {"p": pid},
    )["q"]
    holding = mysql.query_one(
        "SELECT net_quantity AS q FROM v_portfolio_holdings WHERE portfolio_id = :p",
        {"p": pid},
    )
    held_qty = holding["q"] if holding else 0
    assert float(ledger_qty) == float(held_qty)
