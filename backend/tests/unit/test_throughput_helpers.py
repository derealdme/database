"""Step 6. Pure helpers in app/services/throughput.py. No database needed."""
from tests._helpers import todo


def test_percentile_nearest_rank():
    todo("step 6", "percentile(list(range(1, 101)), 95) == 95")


def test_percentile_empty_raises():
    todo("step 6", "percentile([], 50) raises ValueError")


def test_summarise_req_per_s():
    todo("step 6", "summarise([10.0]*50, errors=0, wall_s=5.0)['req_per_s'] == 10.0")
