"""Unit tests for app.utils.numbers.coerce_float.

Contract: ``None`` for None / blank string / anything ``float()`` rejects; otherwise ``float(value)``
exactly as the builtin parses it (so whitespace is tolerated, but locale decorations such as
commas, ``%`` or currency symbols are NOT stripped — callers must strip those first).

Previously covered only incidentally by the deleted FMP/Stocktwits integration tests (WS-8a);
the helper itself is still live in ``alpha_vantage.py`` and ``earnings_calendar_service.py``.
"""
import hashlib
import math
from decimal import Decimal

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



def test_displayed_units_preserve_base_values_and_shared_delta_identity():
    # Actual d PDD/TSM spellings must normalize to the same base amounts as their
    # source-equivalent abbreviated/full-value spellings, including mixed-unit pairs.
    from app.services.metric_delta_service import _parse_number, row_delta_fields
    from app.schemas.summary import _parse_numeric
    from app.utils.numbers import parse_display_number

    examples = [
        ("CNY 431,845,713 thousand", "431845713000", False),
        ("RMB 393,836.097 million", "393836097000", False),
        ("TWD 3,809,054 million", "3809054000000", False),
        ("NT$2,894.308bn", "2894308000000", False),
        ("DKK 23.03", "23.03", False),
        ("EUR 32,667.3M", "32667300000", False),
        ("USD 1.2 trillion", "1200000000000", False),
        ("HK$1.2t", "1200000000000", False),
        ("£2mn", "2000000", False),
        ("¥3k", "3000", False),
        ("$1.5 billion", "1500000000", False),
        ("$(10,707)M", "-10707000000", False),
        ("$(0.19)", "-0.19", False),
        ("($1,200M)", "-1200000000", False),
        ("-$1,200M", "-1200000000", False),
        ("$−0.80", "-0.80", False),
        ("+EUR 1.25", "1.25", False),
        ("(2.5%)", "-2.5", True),
        ("14.1 percent", "14.1", True),
        ("3.4x", "3.4", False),
        ("120bps", "120", False),
        ("120 basis points", "120", False),
        (Decimal("2.5"), "2.5", False),
        (0, "0", False),
    ]
    for text, expected, is_percent in examples:
        assert parse_display_number(text) == (Decimal(expected), is_percent), text
        assert _parse_number(text) == (float(expected), is_percent), text
        assert _parse_numeric(text) == Decimal(expected), text

    for current, prior, expected in [
        ("CNY 431,845,713 thousand", "RMB 393,836.097 million", "+9.7%"),
        ("TWD 3,809,054 million", "NT$2,894.308bn", "+31.6%"),
        ("EUR 32,667.3M", "EUR 28,262,900,000", "+15.6%"),
        ("$(10,707)M", "-$11.817bn", "+9.4%"),
        ("14.1%", "10.1 percent", "+4.0 ppts"),
    ]:
        fields = row_delta_fields({"current_period": current, "prior_period": prior})
        assert fields["change_display"] == expected

    for text in [
        True, None, [], "", "NaN", "Infinity", float("inf"), Decimal("NaN"),
        "1.2B / 900M", "1-2B", "3 million and 2 million", "1,23M", "1,234,56",
        "USD EUR 5", "XYZ 5M", "$--5", "(-5)", "((5))", "5M bn", "$3 widgets",
        "$87,004,000,000 (2025-12-31)", "approximately $5M", "1e3", "5M%",
    ]:
        assert parse_display_number(text) == (None, False), text
        assert _parse_numeric(text) is None, text
        assert row_delta_fields({"current_period": text, "prior_period": "$1M"}) == {}, text


def test_normalized_loss_changes_agree_with_shared_delta_direction():
    # Actual BA/INTC d amounts: profit after loss, widening losses and the inverse
    # improvement must carry the same direction in numeric API and rendered deltas.
    from app.schemas.summary import NormalizedFact
    from app.services.metric_delta_service import row_delta_fields

    for current, prior, delta, denominator, display in [
        ("$2,235M", "$(11,817)M", "14052000000", "11817000000", "+118.9%"),
        ("$4,281M", "$(10,707)M", "14988000000", "10707000000", "+140.0%"),
        ("$(3,728)M", "$(821)M", "-2907000000", "821000000", "−354.1%"),
        ("$(0.73)", "$(0.19)", "-0.54", "0.19", "−284.2%"),
        ("$(821)M", "$(3,728)M", "2907000000", "3728000000", "+78.0%"),
        ("$(821)M", "$2,235M", "-3056000000", "2235000000", "−136.7%"),
    ]:
        fact = NormalizedFact(metric="Net income", currentPeriod=current, priorPeriod=prior)
        expected = Decimal(delta) / Decimal(denominator) * Decimal(100)
        assert fact.delta_value == Decimal(delta)
        assert fact.delta_percent == expected
        fields = row_delta_fields({"current_period": current, "prior_period": prior})
        assert fields["change_display"] == display
        assert fields["change_direction"] == ("up" if expected > 0 else "down")

    for current in ("$2,235M", "$(821)M", "$0"):
        fact = NormalizedFact(metric="Net income", currentPeriod=current, priorPeriod="$0")
        assert fact.delta_value == fact.current_value
        assert fact.delta_percent is None
        assert row_delta_fields({"current_period": current, "prior_period": "$0"}) == {}


# ISO 4217 List One as of February 2026 (pycountry 26.2.16's iso4217.json), less its nine fund codes
# and the 14 X-codes that name no national currency. When ISO changes the list, re-derive both.
ISO_4217_COUNT = 155
ISO_4217_SHA256 = "0b9d5f081d87f7714b2e30857b4cba0b350b5ffa26ffc0696f1d4abf8c33a8d3"


def test_every_currency_a_money_label_can_carry_parses_and_names_its_code():
    """Rule 12 gate: ``money_prefix_for`` labels a figure with the filer's reporting currency, which
    comes from its XBRL units, so the display parser and the exact-delta currency reader read every
    ISO 4217 currency it can write. Before the full list, an AED, SAR or ILS figure parsed to
    nothing and its row stored no change figure. The list itself is pinned, so dropping a code fails
    here as well as one that stops reading."""
    from app.utils.numbers import ISO_4217_CURRENCIES, display_currency, money_prefix_for, parse_display_number

    codes = " ".join(sorted(ISO_4217_CURRENCIES))
    assert (len(ISO_4217_CURRENCIES), hashlib.sha256(codes.encode()).hexdigest()) == (
        ISO_4217_COUNT, ISO_4217_SHA256), codes
    assert not {"XYZ", "XXX", "XTS", "XAU", "XDR", "CLF", "ANG", "HRK", "BGN"} & ISO_4217_CURRENCIES
    for code in sorted(ISO_4217_CURRENCIES):
        label = f"{money_prefix_for(code)}30.6B"
        assert parse_display_number(label) == (Decimal("30600000000"), False), label
        assert display_currency(label) == (True, code), label

    # A code reads in capitals, as money_prefix_for writes it, so a word never reads as a currency.
    # The 21 codes the parser read before the full list still read in any case.
    for text in ["aed 30.6B", "top 5", "all 5", "Try 5", "XYZ 5M", "XXX 5M", "XAU 5M", "CLF 5M"]:
        assert parse_display_number(text) == (None, False), text
    assert parse_display_number("usd 5m") == (Decimal("5000000"), False)
    assert display_currency("top 5 segments") == (False, None)


@pytest.mark.parametrize("text, named", [
    ("AED 941.2B", (True, "AED")),
    ("AED941.2B", (True, "AED")),  # glued to its figure: the exact-delta reader used to miss it
    ("(AED 1.2B)", (True, "AED")),
    ("US$941.2B", (True, "USD")),  # the exact-delta reader used to read "S$", Singapore's
    ("S$5B", (True, "SGD")),
    ("NT$5B", (True, "TWD")),
    ("HK$5B", (True, "HKD")),
    ("RMB 5B", (True, "CNY")),
    ("usd 5m", (True, "USD")),
    ("$941.2B", (True, "USD")),
    ("-€5B", (True, "EUR")),
    ("¥100.0B", (True, None)),  # JPY or CNY: no code, so exact binding refuses it
    ("941.2B", (False, None)),
    ("941.2B AED", (False, None)),  # not a figure the parser reads, so nothing binds to it
    ("top 5 segments", (False, None)),
    (None, (False, None)),
])
def test_a_figure_names_the_currency_of_the_prefix_the_parser_reads(text, named):
    from app.utils.numbers import display_currency

    assert display_currency(text) == named

