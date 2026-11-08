"""Step 4. sp_execute_trade, CHECK constraints and triggers (MySQL)."""
import uuid

import pytest
from sqlalchemy.exc import DBAPIError

from app.db import mysql
from app.services.portfolio import create_portfolio

from tests._helpers import todo

pytestmark = pytest.mark.integration

TEST_USERNAME = "it_trades_user"
TEST_TICKER = "AAPL"


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
def priced_stock_id() -> int:
    """A stock with a row in stock_latest_price, so the procedure can price a trade."""
    row = mysql.query_one(
        "SELECT s.stock_id FROM stocks s JOIN stock_latest_price p"
        "  ON p.stock_id = s.stock_id"
        " WHERE s.ticker = :t",
        {"t": TEST_TICKER},
    )
    if row is None:
        pytest.skip(
            f"{TEST_TICKER} has no row in stock_latest_price; "
            "run tests/fixtures/seed_ci.py first"
        )
    return row["stock_id"]


@pytest.fixture()
def portfolio(seed_user_id):
    name = f"it-trades-{uuid.uuid4().hex[:8]}"
    return create_portfolio(seed_user_id, name, 1000.00)


def test_buy_with_insufficient_cash_rolls_back(portfolio, priced_stock_id):
    pid = portfolio["portfolio_id"]
    before_cash = mysql.query_one(
        "SELECT cash_balance FROM portfolios WHERE portfolio_id = :p", {"p": pid}
    )["cash_balance"]
    before_n = mysql.query_one(
        "SELECT COUNT(*) AS n FROM transactions WHERE portfolio_id = :p", {"p": pid}
    )["n"]

    with pytest.raises(DBAPIError) as exc_info:
        # 1,000,000 shares is far beyond the $1,000 starting cash at any
        # real AAPL price.
        mysql.call_trade_procedure(pid, TEST_TICKER, "BUY", 1_000_000, 0.0005)
    assert "INSUFFICIENT_CASH" in str(exc_info.value)

    after_cash = mysql.query_one(
        "SELECT cash_balance FROM portfolios WHERE portfolio_id = :p", {"p": pid}
    )["cash_balance"]
    after_n = mysql.query_one(
        "SELECT COUNT(*) AS n FROM transactions WHERE portfolio_id = :p", {"p": pid}
    )["n"]
    assert after_cash == before_cash
    assert after_n == before_n


def test_sell_more_than_held_is_rejected(portfolio, priced_stock_id):
    pid = portfolio["portfolio_id"]

    with pytest.raises(DBAPIError) as exc_info:
        mysql.call_trade_procedure(pid, TEST_TICKER, "SELL", 10, 0.0005)
    assert "INSUFFICIENT_HOLDINGS" in str(exc_info.value)

    held_txns = mysql.query_one(
        "SELECT COUNT(*) AS n FROM transactions"
        " WHERE portfolio_id = :p AND stock_id = :s",
        {"p": pid, "s": priced_stock_id},
    )["n"]
    assert held_txns == 0


def test_check_constraint_rejects_negative_price(priced_stock_id):
    with pytest.raises(DBAPIError) as exc_info:
        mysql.execute(
            "INSERT INTO stock_prices (stock_id, price_date, close_price)"
            " VALUES (:s, '2099-01-01', -1)",
            {"s": priced_stock_id},
        )
    assert "chk_price_pos" in str(exc_info.value)
