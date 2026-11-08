"""Step 4. Notes CRUD and collection validators (MongoDB)."""
import pytest
from fastapi import HTTPException
from pymongo.errors import WriteError

from app.db import mongo
from app.services import notes

from tests._helpers import todo

pytestmark = pytest.mark.integration

TEST_USER_ID = 999001


@pytest.fixture(autouse=True)
def _clean_notes():
    mongo.ensure_collections()
    db = mongo.get_db()
    db[mongo.NOTES].delete_many({"user_id": TEST_USER_ID})
    yield
    db[mongo.NOTES].delete_many({"user_id": TEST_USER_ID})


def test_note_create_read_update_delete():
    created = notes.create_note(TEST_USER_ID, {"body": "Initial note", "ticker": "aapl"})
    note_id = created["_id"]
    assert created["ticker"] == "AAPL"
    assert created["body"] == "Initial note"

    fetched = notes.get_note(TEST_USER_ID, note_id)
    assert fetched["body"] == "Initial note"

    updated = notes.update_note(TEST_USER_ID, note_id, {"body": "Revised note"})
    assert updated["body"] == "Revised note"

    notes.delete_note(TEST_USER_ID, note_id)
    with pytest.raises(HTTPException) as exc_info:
        notes.get_note(TEST_USER_ID, note_id)
    assert exc_info.value.status_code == 404


def test_validator_rejects_bad_document():
    db = mongo.get_db()
    with pytest.raises(WriteError):
        # Missing the required headline/published_at/sentiment fields.
        db[mongo.NEWS].insert_one({"ticker": "AAPL"})
