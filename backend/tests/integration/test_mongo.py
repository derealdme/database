"""Step 4. Notes CRUD and collection validators (MongoDB)."""
import pytest

from tests._helpers import todo

pytestmark = pytest.mark.integration


def test_note_create_read_update_delete():
    todo("step 4", "services.notes create -> get -> update -> delete")


def test_validator_rejects_bad_document():
    todo("step 4", "insert a note missing a required field; expect WriteError")
