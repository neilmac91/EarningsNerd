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
    # $81.6B + $29.8B ground in XBRL; $30.0B grounds in the excerpt; +85% is a percentage (not a
    # dollar amount) so it is out of scope entirely — the gate polices dollar figures only.
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


def test_machine_authored_cash_conversion_is_not_policed():
    # T5.1: earnings_quality.cash_conversion is machine-authored from XBRL by the deterministic filler
    # (the NI-vs-CFO ratio + free cash flow), so — like cash_flow / working_capital — it is excluded
    # from policing. A dollar figure here that is absent from XBRL/excerpt must NOT flag; only the
    # model-authored operating_vs_one_time in the same section is still policed.
    s = _sections(earnings_quality={
        "operating_vs_one_time": "One-time items were immaterial this period.",
        "cash_conversion": "Operating cash flow was 1.5x net income (cash conversion); free cash flow of $11.2B.",
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


def test_ppts_and_percentages_are_out_of_scope():
    # Percentages / ppts / bps are overwhelmingly model-DERIVED (margins, growth, ratios) and their
    # CONSISTENCY is the delta-consistency scorer's job — the trace gate polices dollar amounts only,
    # so a ppt delta is never flagged regardless of whether it reconciles to XBRL.
    xbrl = {"net_margin": {"current": {"value": 36.5}, "prior": {"value": 22.1}}}
    s = {"earnings_quality": {"operating_vs_one_time": "Operating margin widened 14.4 ppts; ROE 55%."}}
    assert ft.untraceable_figures(s, xbrl, "") == []


def test_scale_cued_excerpt_number_grounds_a_scaled_prose_figure():
    """The model writes '$486M'; the excerpt states it WITH a scale cue ('$486 million'). Grounds by
    value. (The readout showed the model copies real figures like this from its own input — the gate
    must recognize them.)"""
    s = _sections(the_print={"headline": "A $486M tax benefit was recorded.", "key_takeaways": ["ok"]})
    excerpt = "Deferred tax assets included a $486 million benefit in the reconciliation table."
    assert ft.untraceable_figures(s, _XBRL, excerpt) == []


def test_comma_grouped_excerpt_number_grounds_across_scale():
    """A prose '$105.8B' grounds against a raw '105,819' in a millions table (value 105.819e9, within the
    one-decimal rounding tolerance) — the scale-mismatch case, matched by value not by string."""
    s = _sections(the_print={"headline": "Revenue reached $105.8B.", "key_takeaways": ["ok"]})
    excerpt = "Net operating revenues were 105,819 for the period (in millions)."
    assert ft.untraceable_figures(s, None, excerpt) == []


def test_trillion_scale_excerpt_grounds():
    """A verbatim trillion-scale figure ('$3.5 trillion', routine on megabank/AUM prose — JPM's ~$4T is
    in the golden set) must ground against the excerpt's own 'trillion'/'tn' cue. The excerpt scale
    vocabulary mirrors the prose side; without it the copied figure false-flagged (['3.5t'])."""
    s = _sections(the_print={"headline": "Assets under management reached $3.5 trillion.",
                             "key_takeaways": ["ok"]})
    assert ft.untraceable_figures(s, None, "Assets under management of $3.5 trillion as of Dec 31.") == []
    assert ft.untraceable_figures(s, None, "AUM of $3.5tn at period end.") == []


def test_rounding_tolerance_grounds_against_exact_xbrl():
    """A prose '$2.2B' grounds against an exact XBRL 2,241,000,000 (rounds to $2.2B): half-last-digit
    tolerance (±0.05B) admits it. A flat 0.5% tolerance would not (2.241 is 1.9% off 2.2)."""
    xbrl = {"segment_op_income": {"current": {"value": 2_241_000_000}}}
    s = _sections(the_print={"headline": "Segment income was $2.2B.", "key_takeaways": ["ok"]})
    assert ft.untraceable_figures(s, xbrl, "") == []


def test_rounding_tolerance_still_flags_a_real_miss():
    """The tolerance is HALF the last digit's place, not a loose band: a fabricated '$2.5B' does NOT
    ground against an exact 2,241,000,000 (0.26B away, well beyond ±0.05B)."""
    xbrl = {"segment_op_income": {"current": {"value": 2_241_000_000}}}
    s = _sections(the_print={"headline": "Segment income was $2.5B.", "key_takeaways": ["ok"]})
    assert ft.untraceable_figures(s, xbrl, "") == ["2.5b"]


def test_large_mantissa_grounds_without_scientific_notation():
    """A figure with a >=1e6 mantissa ('$1,234,567M') must canonicalize in fixed notation and ground
    against its exact XBRL value. Under a ':g' format it became '1.23457e+06m' — rounded AND with a
    broken rounding-tolerance decimal count — and false-flagged a valid figure."""
    xbrl = {"total_assets": {"current": {"value": 1_234_567_000_000}}}
    s = _sections(the_print={"headline": "Total assets were $1,234,567M.", "key_takeaways": ["ok"]})
    assert ft.untraceable_figures(s, xbrl, "") == []


def test_negative_xbrl_value_grounds_positive_prose_magnitude():
    """XBRL stores a financing OUTFLOW as negative; the model writes the positive magnitude with a
    directional word. The magnitude must ground (xbrl_values is absolute), not false-flag."""
    xbrl = {"financing_cash_flow": {"current": {"value": -28_400_000_000}}}
    s = _sections(the_print={"headline": "Financing outflow of $28.4B on buybacks.", "key_takeaways": ["ok"]})
    assert ft.untraceable_figures(s, xbrl, "") == []


def test_model_derived_aggregate_is_flagged():
    """The residual the gate exists to surface: the model SUMS named line items into a 'total debt' that
    appears nowhere in XBRL or the excerpt as a single number. Its components are present; the sum is not
    — so it is untraceable (a T5 'numbers from code' signal, or a fabrication)."""
    s = _sections(the_print={
        "headline": "Coverage stayed strong.",
        "key_takeaways": ["Total debt of $43,890M against cash of $10,574M."],
    })
    excerpt = "Long-term debt 38,379 and current maturities 5,511 and cash and equivalents 10,574."
    # cash ($10,574M) grounds via the comma-grouped excerpt figure; the summed total debt does not.
    assert ft.untraceable_figures(s, None, excerpt) == ["43890m"]


def test_bare_incidental_number_does_not_ground_a_fabrication():
    """Precision floor: a fabricated '$60B' is NOT grounded by an incidental bare '60' in the excerpt
    (a count / page / percentage). Bare numbers are never scaled up — only scale-cued or comma-grouped
    magnitudes are."""
    s = _sections(the_print={"headline": "A $60B write-down was taken.", "key_takeaways": ["ok"]})
    assert ft.untraceable_figures(s, _XBRL, "The company operates in 60 countries.") == ["60b"]


def test_no_grounding_basis_flags_nothing():
    # Fully degraded path: no XBRL AND no excerpt/filing text → NO basis to judge, so flag nothing
    # (not flag-all). Flag-all would flood the corpus measurement on the excerpt-failure population and,
    # once armed, billing-punish already-degraded summaries.
    assert ft.untraceable_figures(_sections(), None, None) == []
    assert ft.untraceable_figures(_sections(), {}, "") == []


def test_filing_text_fallback_grounds_copied_figure():
    # The excerpt-failure case: the pipeline passes ``excerpt or filing_text`` so the gate grounds against
    # the same text the model generated from. A figure copied from the filing text must ground, not flag.
    s = _sections(the_print={"headline": "Revenue was $30.0 billion.", "key_takeaways": ["ok"]})
    filing_text = "... The Company reported revenue of $30.0 billion for the fiscal year ..."
    assert ft.untraceable_figures(s, None, filing_text) == []


def test_malformed_sections_do_not_crash():
    assert ft.untraceable_figures(["not", "a", "dict"], _XBRL, _EXCERPT) == []
    assert ft.untraceable_figures({"the_print": "a string not a dict"}, _XBRL, _EXCERPT) == []
    assert ft.untraceable_figures(None, _XBRL, _EXCERPT) == []
