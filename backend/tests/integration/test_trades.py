"""Step 4. sp_execute_trade, CHECK constraints and triggers (MySQL)."""
import pytest

from tests._helpers import todo

pytestmark = pytest.mark.integration


def test_buy_with_insufficient_cash_rolls_back():
    todo("step 4", "CALL sp_execute_trade for more than cash; expect error; "
         "portfolio cash and transactions unchanged")


def test_sell_more_than_held_is_rejected():
    todo("step 4", "trigger/procedure rejects; nothing written")


def test_check_constraint_rejects_negative_price():
    todo("step 4", "INSERT a negative close_price into stock_prices fails")
