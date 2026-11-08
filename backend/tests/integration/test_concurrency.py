"""Step 5. Parallel buys on one portfolio."""
import pytest

from tests._helpers import todo

pytestmark = pytest.mark.integration


def test_parallel_buys_never_overdraw_cash():
    todo("step 5", "20 threads buy at once; cash >= 0 afterwards")


def test_ledger_matches_holdings_after_parallel_buys():
    todo("step 5", "SUM(transactions) per ticker == v_portfolio_holdings")
