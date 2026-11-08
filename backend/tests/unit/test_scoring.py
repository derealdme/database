"""Step 2. Weight normalisation and proxy labels. No database needed."""
import re

import pytest

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
    w = Weights.normalised(valuation=2, profitability=2, growth=0, dividend=0)
    d = w.as_dict()
    assert d["valuation"] == pytest.approx(0.5)
    assert d["profitability"] == pytest.approx(0.5)
    assert d["growth"] == 0.0
    assert d["dividend"] == 0.0


def test_negative_weights_are_clamped_to_zero():
    w = Weights.normalised(valuation=1, profitability=-1, growth=0, dividend=0)
    assert w.as_dict()["profitability"] == 0.0


def test_all_zero_weights_fall_back_to_defaults():
    w = Weights.normalised(valuation=0, profitability=0, growth=0, dividend=0)
    assert w == Weights()


def test_sql_expression_contains_only_column_names_and_floats():
    w = Weights.normalised()
    assert re.match(
        r"^[a-z_]+_score \* [0-9.]+( \+ [a-z_]+_score \* [0-9.]+)*$",
        w.sql_expression(),
    )
