"""Step 2. bcrypt and JWT. No database needed (do not call current_user)."""
from tests._helpers import todo


def test_hash_then_verify_roundtrip():
    todo("step 2", "verify_password(p, hash_password(p)) is True")


def test_wrong_password_fails():
    todo("step 2", "verify_password('wrong', hash_password('right')) is False")


def test_garbage_hash_returns_false_not_error():
    todo("step 2", "verify_password('x', 'not-a-hash') is False")


def test_token_roundtrip():
    todo("step 2", "_decode(create_access_token(7, 'u'))['sub'] == '7'")


def test_tampered_token_is_401():
    todo("step 2", "_decode(token + 'x') raises HTTPException status 401")
