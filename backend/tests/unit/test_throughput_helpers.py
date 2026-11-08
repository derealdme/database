"""Step 6. Pure helpers in app/services/throughput.py. No database needed."""
import pytest

from app.services.throughput import percentile, summarise

from tests._helpers import todo


def test_percentile_nearest_rank():
    assert percentile(list(range(1, 101)), 95) == 95


def test_percentile_empty_raises():
    with pytest.raises(ValueError):
        percentile([], 50)


def test_summarise_req_per_s():
    assert summarise([10.0] * 50, errors=0, wall_s=5.0)["req_per_s"] == 10.0
