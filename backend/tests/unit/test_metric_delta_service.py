"""The single delta policy (T1.5): one formatter for every %/ppt across table, chips, and exports.

Ratios/margins → percentage points ("+14.4 ppts"); everything else → relative percent ("+85.2%",
one decimal, U+2212 minus). This is the source of truth that ends the +85%/+85.0%/+85.2% and
relative-%-vs-ppts divergence.
"""
from app.services import metric_delta_service as m


def test_amount_relative_percent_up():
    d = m.compute(100, 80, is_ratio=False)
    assert d.display == "+25.0%"
    assert d.direction == "up" and d.tone == "gain"
    assert d.pct == 25.0 and d.is_ppts is False


def test_amount_relative_percent_down_uses_unicode_minus():
    d = m.compute(20, 25, is_ratio=False)
    assert d.display == "−20.0%"      # U+2212, not ASCII '-'
    assert d.direction == "down" and d.tone == "loss"


def test_ratio_renders_in_ppts_up():
    d = m.compute(74.9, 60.5, is_ratio=True)
    assert d.display == "+14.4 ppts"
    assert d.is_ppts is True and d.value == 14.4 and d.pct is None


def test_ratio_renders_in_ppts_down():
    d = m.compute(60.5, 74.9, is_ratio=True)
    assert d.display == "−14.4 ppts"
    assert d.direction == "down"


def test_missing_values_are_flat_no_display():
    assert m.compute(10, None, is_ratio=False).display is None
    assert m.compute(None, 10, is_ratio=True).display is None
    assert m.compute(None, None, is_ratio=False).direction == "flat"


def test_zero_prior_has_no_relative_percent():
    d = m.compute(5, 0, is_ratio=False)
    assert d.display is None                # prior == 0 → no meaningful relative %


def test_row_delta_amount_row():
    fields = m.row_delta_fields({"current_period": "$81.6B", "prior_period": "$44.1B"})
    assert fields["change_display"] == "+85.0%"
    assert fields["change_direction"] == "up" and fields["change_tone"] == "gain"


def test_row_delta_margin_row_is_ppts_not_relative_pct():
    # The exact bug the plan calls out: a margin must be ppts, not a relative %.
    fields = m.row_delta_fields({"current_period": "74.9%", "prior_period": "60.5%"})
    assert fields["change_display"] == "+14.4 ppts"


def test_row_delta_unparseable_returns_empty():
    assert m.row_delta_fields({"current_period": "n/a", "prior_period": "—"}) == {}
    assert m.row_delta_fields({"metric": "x"}) == {}


def test_mixed_percent_row_returns_none_not_a_bogus_amount():
    # current is a margin (%), prior is a bare number: computing this as an amount would yield the
    # +23.8%-for-a-margin category error. Mixed units must return None (no computed delta).
    assert m.delta_for_row({"current_period": "74.9%", "prior_period": "60.5"}) is None
    assert m.row_delta_fields({"current_period": "74.9%", "prior_period": "60.5"}) == {}
    # Symmetric: amount current, percent prior.
    assert m.delta_for_row({"current_period": "$5.0B", "prior_period": "12.0%"}) is None


def test_parse_handles_suffixes_and_parens():
    assert m._parse_number("$1,234.5M")[0] == 1234.5e6
    val, is_pct = m._parse_number("(2.5%)")
    assert is_pct is True and val == -2.5
