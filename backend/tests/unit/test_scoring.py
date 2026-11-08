"""Step 2. Weight normalisation and proxy labels. No database needed."""
from app.services.scoring import FACTOR_LABELS, FACTOR_NOTES, Weights

from tests._helpers import todo


# --- Worked example: copy this shape for the placeholders below. --------
def test_default_weights_sum_to_one():
    w = Weights.normalised()
    assert abs(sum(w.as_dict().values()) - 1.0) < 1e-9


# --- Guards step 0 (proxy relabel). Must stay green. --------------------
def test_proxy_factors_are_labelled_as_proxies():
    assert "proxy" in FACTOR_LABELS["profitability"].lower()
    assert "proxy" in FACTOR_LABELS["growth"].lower()
    assert "momentum" in FACTOR_NOTES["growth"].lower()


# --- Placeholders -------------------------------------------------------
def test_custom_weights_are_rescaled():
    todo("step 2", "Weights.normalised(valuation=2, profitability=2, growth=0, "
         "dividend=0) gives 0.5/0.5/0/0")


def test_negative_weights_are_clamped_to_zero():
    todo("step 2", "a negative weight becomes 0 before rescaling")


def test_all_zero_weights_fall_back_to_defaults():
    todo("step 2", "all-zero input returns Weights() defaults")


def test_sql_expression_contains_only_column_names_and_floats():
    todo("step 2", "sql_expression() matches r'^[a-z_]+_score \\* [0-9.]+( \\+ ...)*$'")
