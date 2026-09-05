"""Unit tests for app.utils.numbers.coerce_float.

Contract: ``None`` for None / blank string / anything ``float()`` rejects; otherwise ``float(value)``
exactly as the builtin parses it (so whitespace is tolerated, but locale decorations such as
commas, ``%`` or currency symbols are NOT stripped — callers must strip those first).

Previously covered only incidentally by the deleted FMP/Stocktwits integration tests (WS-8a);
the helper itself is still live in ``alpha_vantage.py`` and ``earnings_calendar_service.py``.
"""
import math

import pytest

from app.utils.numbers import coerce_float


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, 1.0),
        (0, 0.0),
        (-3, -3.0),
        (2.5, 2.5),
        (True, 1.0),  # bool is an int subclass; float(True) == 1.0
        ("1.25", 1.25),
        ("-0.5", -0.5),
        ("  42  ", 42.0),  # float() tolerates surrounding whitespace
        ("1e3", 1000.0),
        ("0", 0.0),
    ],
)
def test_coerces_numbers_and_numeric_strings(value, expected):
    result = coerce_float(value)
    assert result == expected
    assert isinstance(result, float)


@pytest.mark.parametrize("value", [None, ""])
def test_none_and_blank_are_none(value):
    assert coerce_float(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "N/A",
        "abc",
        "   ",  # whitespace-only is not blank per the guard, and float() rejects it
        "1,234.5",  # commas are NOT stripped
        "12%",  # nor percent signs
        "$3.50",  # nor currency symbols
        [],
        {},
        object(),
    ],
)
def test_non_numeric_inputs_are_none(value):
    assert coerce_float(value) is None


def test_nan_and_inf_strings_pass_through_like_float():
    # float() accepts these spellings, and so does coerce_float — it does not sanitize them.
    assert math.isnan(coerce_float("nan"))
    assert coerce_float("inf") == math.inf
