"""T3.2 number-diff gate: prose figures must trace to XBRL / a computed delta / the filing excerpt.

The gate is conservative by design (false positives turn off billing via AI_QUALITY_GATE), so most of
these cases pin what it must NOT flag.
"""
from app.services.ai import figure_trace as ft

_XBRL = {
    "revenue": {"current": {"value": 81_600_000_000}, "prior": {"value": 44_100_000_000}},
    "net_income": {"current": {"value": 29_760_000_000}},
}
_EXCERPT = "Data center revenue grew to $30.0 billion; the segment led growth."


def _sections(**over):
    base = {
        "the_print": {"headline": "Revenue reached $81.6B.", "key_takeaways": ["Net income of $29.8B."]},
        "earnings_quality": {"operating_vs_one_time": "Growth of +85% YoY was broad-based."},
    }
    base.update(over)
    return base


def test_grounded_figures_are_not_flagged():
    # $81.6B + $29.8B (XBRL), +85% (computed delta 44.1B->81.6B), $30.0B (excerpt) all trace.
    assert ft.untraceable_figures(_sections(), _XBRL, _EXCERPT) == []


def test_fabricated_prose_figure_is_flagged():
    s = _sections(earnings_quality={"operating_vs_one_time": "A one-time gain of $55.5B flattered results."})
    assert ft.untraceable_figures(s, _XBRL, _EXCERPT) == ["55.5b"]


def test_excerpt_number_grounds_a_segment_figure():
    # A figure legitimately quoted from the filing prose (not in standardized XBRL) must ground.
    s = _sections(segments=[{"segment": "Data Center", "commentary": "Data center revenue was $30.0 billion."}])
    assert ft.untraceable_figures(s, _XBRL, _EXCERPT) == []


def test_years_and_counts_are_not_figures():
    s = _sections(the_print={"headline": "In fiscal 2025 the company operated 12 plants across 3 regions."})
    assert ft.untraceable_figures(s, _XBRL, _EXCERPT) == []


def test_results_table_and_verbatim_quotes_are_not_policed():
    # The table is XBRL-injected; quotes are verbatim from the filing — both excluded from policing.
    s = _sections(
        results_that_matter={"table": [{"metric": "Mystery", "current_period": "$77.7B"}]},
        forward_signals={"guidance": "Guided cautiously.", "quotes": [{"quote": "We target $123B in 2030."}]},
    )
    assert ft.untraceable_figures(s, _XBRL, _EXCERPT) == []


def test_machine_authored_fields_are_not_policed():
    # cash_flow / working_capital are authored by the deterministic filler from XBRL, not the model.
    s = _sections(balance_sheet_liquidity={
        "cash_flow": "Cash flow — operating $44.4B, investing $8.8B, financing $2.2B.",
        "working_capital": "Current assets $66.6B vs. current liabilities $11.1B (current ratio 6.00x).",
        "leverage": "Leverage remained conservative.",
    })
    assert ft.untraceable_figures(s, _XBRL, _EXCERPT) == []


def test_foreign_currency_grounds_by_magnitude():
    # Canonical keys are currency-agnostic (strip the symbol/ISO, match the scaled magnitude), so an
    # EUR filer's "€81.6B" grounds against the XBRL value 81.6e9 — no false positive on foreign filers.
    s = _sections(the_print={"headline": "Revenue reached EUR 81.6B for the year."})
    assert ft.untraceable_figures(s, _XBRL, _EXCERPT) == []


def test_per_share_unitless_numbers_are_not_policed():
    # EPS "$2.05" has no scale unit → not canonicalized → not policed (avoids per-share FPs; the eval's
    # numeric scorer covers EPS). A scaled fabrication in the same prose is still caught.
    s = _sections(the_print={"headline": "Diluted EPS was $2.05, and a $55.5B charge was recorded."})
    assert ft.untraceable_figures(s, _XBRL, _EXCERPT) == ["55.5b"]


def test_ppts_delta_grounds():
    # A margin's ppt delta is in the legitimate set (both % and ppt renderings are allowed). Sections
    # kept minimal so only the ppt figure is under test.
    xbrl = {"net_margin": {"current": {"value": 36.5}, "prior": {"value": 22.1}}}
    s = {"earnings_quality": {"operating_vs_one_time": "Operating margin widened 14.4 ppts."}}
    assert ft.untraceable_figures(s, xbrl, "") == []


def test_excerpt_bare_magnitude_grounds_a_scaled_prose_figure():
    """The $486M case: the filing states the figure as a BARE number in a table ('... 486 ...') and the
    model writes it scaled ('$486M'). The magnitude substring grounds it — canonical-key matching alone
    missed it (a false positive the readout surfaced)."""
    s = _sections(the_print={"headline": "A $486M tax benefit was recorded.", "key_takeaways": ["ok"]})
    excerpt = "Deferred tax assets included a 486 benefit line in the reconciliation table."
    assert ft.untraceable_figures(s, _XBRL, excerpt) == []


def test_magnitude_match_is_word_bounded():
    """A magnitude must match on a boundary: '$33.7B' is NOT grounded by '133.7' in the excerpt."""
    s = _sections(the_print={"headline": "Net cash of $33.7B.", "key_takeaways": ["ok"]})
    assert ft.untraceable_figures(s, _XBRL, "The index rose to 133.7 today.") == ["33.7b"]


def test_no_xbrl_no_excerpt_is_safe():
    # Degraded path: nothing to trace against → the gate must not crash and flags only real figures.
    assert isinstance(ft.untraceable_figures(_sections(), None, None), list)


def test_malformed_sections_do_not_crash():
    assert ft.untraceable_figures(["not", "a", "dict"], _XBRL, _EXCERPT) == []
    assert ft.untraceable_figures({"the_print": "a string not a dict"}, _XBRL, _EXCERPT) == []
    assert ft.untraceable_figures(None, _XBRL, _EXCERPT) == []
