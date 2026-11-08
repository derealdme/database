"""Step 2. bcrypt and JWT. No database needed (do not call current_user)."""
import pytest
from fastapi import HTTPException

from app.core.security import _decode, create_access_token, hash_password, verify_password

from tests._helpers import todo


def test_hash_then_verify_roundtrip():
    plain = "correct horse battery staple"
    assert verify_password(plain, hash_password(plain)) is True


def test_wrong_password_fails():
    assert verify_password("wrong", hash_password("right")) is False


def test_garbage_hash_returns_false_not_error():
    assert verify_password("x", "not-a-hash") is False


def test_token_roundtrip():
    token = create_access_token(7, "u")
    assert _decode(token)["sub"] == "7"


def test_tampered_token_is_401():
    token = create_access_token(7, "u")
    with pytest.raises(HTTPException) as exc_info:
        _decode(token + "x")
    assert exc_info.value.status_code == 401
