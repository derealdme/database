"""Step 2. Pydantic request validation. No database needed."""
from tests._helpers import todo


def test_register_rejects_bad_username():
    todo("step 2", "RegisterRequest(username='a b!', ...) raises ValidationError")


def test_register_lowercases_email():
    todo("step 2", "email ' A@B.COM ' becomes 'a@b.com'")


def test_trade_uppercases_ticker_and_rejects_zero_quantity():
    todo("step 2", "' aapl ' -> 'AAPL'; quantity=0 raises ValidationError")


def test_screener_limit_bounds():
    todo("step 2", "ScreenerRequest(limit=0) and limit=501 raise ValidationError")


def test_note_rating_bounds():
    todo("step 2", "NoteCreate(body='x', rating=6) raises ValidationError")
