"""Step 2. Pydantic request validation. No database needed."""
import pytest
from pydantic import ValidationError

from app.schemas import NoteCreate, RegisterRequest, ScreenerRequest, TradeRequest

from tests._helpers import todo


def test_register_rejects_bad_username():
    with pytest.raises(ValidationError):
        RegisterRequest(username="a b!", email="a@b.com", password="longenough1")


def test_register_lowercases_email():
    r = RegisterRequest(username="validuser", email=" A@B.COM ", password="longenough1")
    assert r.email == "a@b.com"


def test_trade_uppercases_ticker_and_rejects_zero_quantity():
    t = TradeRequest(ticker=" aapl ", side="BUY", quantity=1)
    assert t.ticker == "AAPL"
    with pytest.raises(ValidationError):
        TradeRequest(ticker="AAPL", side="BUY", quantity=0)


def test_screener_limit_bounds():
    with pytest.raises(ValidationError):
        ScreenerRequest(limit=0)
    with pytest.raises(ValidationError):
        ScreenerRequest(limit=501)


def test_note_rating_bounds():
    with pytest.raises(ValidationError):
        NoteCreate(body="x", rating=6)
