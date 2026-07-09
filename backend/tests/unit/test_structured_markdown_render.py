"""Wave V visual-appeal guard: the deterministic markdown renderer bolds key figures.

`_build_structured_markdown` is the live user-facing renderer (the LLM editorial writer is
disabled — decision 3a) and its output is what the eval scores via `business_overview`. These
tests lock in that the financials bullets bold the metric label + current value (scannability)
WITHOUT bolding "Not disclosed" placeholders, and that the bold markup stays substring-matchable
so the eval numeric scorers are unaffected.
"""
from app.services.openai_service import openai_service


def _summary():
    return {
        "metadata": {"company_name": "TestCo", "filing_type": "10-K", "reporting_period": "FY2025"},
        "sections": {
            "executive_snapshot": {"headline": "TestCo grew.", "key_points": ["Revenue up"], "tone": "neutral"},
            "financial_highlights": {
                "table": [
                    {"metric": "Revenue", "current_period": "$42.3B", "prior_period": "$37.1B",
                     "change": "+14%", "commentary": "driven by services"},
                    {"metric": "EPS (Diluted)", "current_period": "Not disclosed"},
                ],
                "cash_flow": ["Operating cash flow $12.7B; capex $3.0B; free cash flow $9.7B"],
                "balance_sheet": ["Current assets $30.6B, current liabilities $24.3B, current ratio 1.26x"],
            },
        },
    }


def test_financials_bullet_bolds_metric_and_current_value():
    md = openai_service._build_structured_markdown(_summary())
    # Metric label and the real current figure are both bolded.
    assert "- **Revenue:** **$42.3B**" in md
    # Prior period / change are NOT bolded (kept secondary, so the current figure stands out).
    assert "vs. $37.1B (+14%)" in md


def test_not_disclosed_placeholder_is_not_bolded():
    md = openai_service._build_structured_markdown(_summary())
    assert "- **EPS (Diluted):** Not disclosed" in md
    assert "**Not disclosed**" not in md


def test_other_placeholder_values_are_not_bolded():
    # The model/extraction can emit placeholders beyond "Not disclosed" (N/A, None, —, …); none
    # should be bolded. Guards against the metric-value bolding defeating its own scannability goal.
    summary = {
        "metadata": {"company_name": "TestCo", "filing_type": "10-K"},
        "sections": {"financial_highlights": {"table": [
            {"metric": "Revenue", "current_period": "N/A"},
            {"metric": "Net Income", "current_period": "None"},
            {"metric": "EPS", "current_period": "—"},
        ]}},
    }
    md = openai_service._build_structured_markdown(summary)
    assert "**N/A**" not in md and "**None**" not in md and "**—**" not in md
    # The metric labels are still bolded — only the placeholder value is left plain.
    assert "- **Revenue:** N/A" in md


def test_bolded_figures_remain_substring_matchable_for_eval_scorers():
    # The eval's numeric scorers do a plain substring match on a lowercased haystack; the bold
    # asterisks must not separate the digits from their renderings ("42.3" still present).
    md = openai_service._build_structured_markdown(_summary()).lower()
    assert "42.3" in md
    assert "12.7" in md  # cash-flow figure still rendered
    assert "30.6" in md  # working-capital figure still rendered


def test_malformed_nondict_sections_do_not_crash_renderer():
    """Regression (PR #550 review): a malformed payload can make a section a TRUTHY non-dict
    (list/str/int), which `or {}` passed straight to `.get()` — crashing the fallback renderer, the
    very path meant to save a failed generation. The isinstance guards keep it rendering a string."""
    summary = {
        "metadata": {"company_name": "TestCo", "filing_type": "10-K"},
        "sections": {
            "executive_snapshot": ["not", "a", "dict"],
            "financial_highlights": "totally wrong",
            "management_discussion_insights": 42,
            "guidance_outlook": ["bad"],
        },
    }
    md = openai_service._build_structured_markdown(summary)  # must not raise
    assert isinstance(md, str) and "## Executive Summary" in md


def test_apply_structured_fallbacks_tolerates_nondict_metric_payloads():
    """Regression (PR #550 review): metric_entry guards metric/current/prior — a truthy non-dict
    metrics payload (e.g. a list where a {current,prior} dict is expected) previously crashed the
    `.get()` chain. The fallback filler must tolerate it and still populate what it can."""
    sections: dict = {}
    xbrl = {"revenue": ["oops"], "net_income": {"current": "bad", "prior": ["x"]}, "net_margin": 3}

    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)  # must not raise

    # v2 (Tier-3.1): the fallback fills the anchor v2 section `the_print` (was executive_snapshot).
    assert isinstance(sections.get("the_print"), dict)


def test_apply_structured_fallbacks_surfaces_cashflow_and_working_capital_v2():
    """v2 numeric-recall floor: ``balance_sheet_liquidity`` must carry the cash-flow bridge
    (operating/investing/financing) and the working-capital position (current assets/liabilities +
    ratio) from standardized XBRL. The model routes these into prose it tends to write WITHOUT
    figures, so the v2 cutover otherwise dropped investing/financing cash flow and current
    assets/liabilities from the summary (measured: recall 0.84 -> 0.74). Numbers from code."""
    sections: dict = {}
    xbrl = {
        "operating_cash_flow": {"current": {"value": 12_700_000_000, "period": "FY2025"}},
        "investing_cash_flow": {"current": {"value": -3_000_000_000, "period": "FY2025"}},
        "financing_cash_flow": {"current": {"value": -5_000_000_000, "period": "FY2025"}},
        "current_assets": {"current": {"value": 30_600_000_000, "period": "FY2025"}},
        "current_liabilities": {"current": {"value": 24_300_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    bsl = sections.get("balance_sheet_liquidity")
    assert isinstance(bsl, dict)
    # Working capital: both sides + derived current ratio (30.6 / 24.3 = 1.26x).
    wc = bsl.get("working_capital")
    assert "$30.6B" in wc and "$24.3B" in wc and "1.26x" in wc
    # Cash-flow bridge: all three legs in the dedicated `cash_flow` field, including the
    # previously-dropped investing/financing legs.
    cf = bsl.get("cash_flow")
    assert "operating" in cf and "$12.7B" in cf
    assert "investing" in cf and "financing" in cf


def test_apply_structured_fallbacks_preserves_model_liquidity_commentary():
    """The deterministic surfacing OWNS the figure fields (working_capital, cash_flow) but must leave
    the model's qualitative `leverage` + `liquidity` prose untouched — numbers from code, words from
    the model. The figure fields are authored even when the model wrote an unrelated "$" nearby (a
    plain presence check would wrongly suppress the specific facts)."""
    sections = {"balance_sheet_liquidity": {
        "leverage": "Net debt/EBITDA held at 1.2x.",
        "liquidity": "Ample liquidity — $12.7B in cash and an undrawn revolver.",
        "working_capital": "Working capital swung positive on an inventory drawdown.",
    }}
    xbrl = {
        "current_assets": {"current": {"value": 30_600_000_000, "period": "FY2025"}},
        "current_liabilities": {"current": {"value": 24_300_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": 12_700_000_000, "period": "FY2025"}},
        "investing_cash_flow": {"current": {"value": -3_000_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    bsl = sections["balance_sheet_liquidity"]
    # Model qualitative fields preserved verbatim.
    assert bsl["leverage"] == "Net debt/EBITDA held at 1.2x."
    assert bsl["liquidity"] == "Ample liquidity — $12.7B in cash and an undrawn revolver."
    # Figure fields authored from XBRL (the model's number-free working_capital is replaced).
    assert "$30.6B" in bsl["working_capital"] and "$24.3B" in bsl["working_capital"]
    assert "$12.7B" in bsl["cash_flow"] and "investing" in bsl["cash_flow"]


def test_apply_structured_fallbacks_uses_reporting_currency_for_foreign_filers():
    """Foreign issuers report in their own currency; the deterministic figures must use it (ISO
    prefix), never a bare '$' — which would mislabel e.g. EUR as dollars (~7x distortion the numeric
    scorers can't catch) and ding currency consistency."""
    sections: dict = {}
    xbrl = {
        "reporting_currency": "EUR",
        "current_assets": {"current": {"value": 30_600_000_000, "period": "FY2025"}},
        "current_liabilities": {"current": {"value": 24_300_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": 12_700_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    bsl = sections["balance_sheet_liquidity"]
    assert "EUR 30.6B" in bsl["working_capital"]
    assert "EUR 12.7B" in bsl["cash_flow"]
    # No bare dollar sign anywhere in the authored figures.
    assert "$" not in (bsl["working_capital"] + bsl["cash_flow"])


def test_apply_structured_fallbacks_working_capital_shows_yoy_when_priors_exist():
    """The schema promises working-capital YoY direction; when standardized metrics carry a prior
    period, the filler appends the prior current assets/liabilities + ratio (two more recallable
    facts) rather than a current-only line."""
    sections: dict = {}
    xbrl = {
        "current_assets": {"current": {"value": 30_600_000_000, "period": "FY25"},
                           "prior": {"value": 28_100_000_000, "period": "FY24"}},
        "current_liabilities": {"current": {"value": 24_300_000_000, "period": "FY25"},
                                "prior": {"value": 23_800_000_000, "period": "FY24"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    wc = sections["balance_sheet_liquidity"]["working_capital"]
    assert "current ratio 1.26x" in wc
    assert "A year earlier" in wc and "$28.1B" in wc and "$23.8B" in wc and "1.18x" in wc


def test_apply_structured_fallbacks_current_ratio_edge_cases():
    """Current-ratio guard: a ZERO numerator (current assets) still shows the ratio — 0.00x is a real
    signal, not noise — while a zero/None denominator (current liabilities) suppresses it with no
    division-by-zero. Numerator gated on presence (is not None), denominator on non-zero truthiness."""
    # Zero current assets, positive liabilities -> ratio 0.00x IS shown.
    s1: dict = {}
    openai_service._apply_structured_fallbacks(s1, {"company_name": "X"}, {
        "current_assets": {"current": {"value": 0.0, "period": "FY25"}},
        "current_liabilities": {"current": {"value": 24_300_000_000, "period": "FY25"}},
    })
    assert "current ratio 0.00x" in s1["balance_sheet_liquidity"]["working_capital"]

    # Zero current liabilities -> ratio suppressed, no crash, both sides still shown.
    s2: dict = {}
    openai_service._apply_structured_fallbacks(s2, {"company_name": "X"}, {
        "current_assets": {"current": {"value": 30_600_000_000, "period": "FY25"}},
        "current_liabilities": {"current": {"value": 0.0, "period": "FY25"}},
    })
    wc = s2["balance_sheet_liquidity"]["working_capital"]
    assert "current ratio" not in wc and "$30.6B" in wc


# --- T5.1: earnings_quality.cash_conversion machine-authored from XBRL (numbers from code) ---

def test_apply_structured_fallbacks_authors_cash_conversion():
    """§3's cash-conversion read is machine-authored: the NI-vs-CFO ratio (operating cash flow / net
    income — a derived relationship in no single XBRL magnitude) plus free cash flow. ONE-HOME: the
    ratio + FCF, never the OCF/NI dollar levels (those live in §8 / §2)."""
    sections: dict = {}
    xbrl = {
        "net_income": {"current": {"value": 20_000_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": 30_000_000_000, "period": "FY2025"}},
        "free_cash_flow": {"current": {"value": 25_000_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    cc = sections["earnings_quality"]["cash_conversion"]
    assert "1.5x net income" in cc and "cash conversion" in cc
    assert "free cash flow of $25.0B" in cc
    # ONE-HOME: the OCF/NI dollar LEVELS are not re-quoted here.
    assert "$30.0B" not in cc and "$20.0B" not in cc


def test_apply_structured_fallbacks_cash_conversion_ratio_only_when_fcf_absent():
    """FCF may be underivable (no capex tag); the ratio alone still grounds the accrual read."""
    sections: dict = {}
    xbrl = {
        "net_income": {"current": {"value": 20_000_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": 30_000_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    cc = sections["earnings_quality"]["cash_conversion"]
    assert cc == "Operating cash flow was 1.5x net income (cash conversion)."


def test_apply_structured_fallbacks_cash_conversion_loss_with_positive_ocf():
    """§3's highest-value accrual signal: a GAAP net loss alongside POSITIVE operating cash flow — the
    business generated cash despite the loss (non-cash charges/impairments). Stated qualitatively (a
    conversion multiple against a negative denominator is meaningless); FCF still appended."""
    sections: dict = {}
    xbrl = {
        "net_income": {"current": {"value": -5_000_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": 3_000_000_000, "period": "FY2025"}},
        "free_cash_flow": {"current": {"value": 2_000_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    cc = sections["earnings_quality"]["cash_conversion"]
    assert cc == "Operating cash flow was positive despite a net loss; free cash flow of $2.0B."
    assert "x net income" not in cc  # no meaningless ratio against a negative denominator


def test_apply_structured_fallbacks_cash_conversion_loss_with_positive_ocf_no_fcf():
    """The cash-despite-a-loss read stands alone when FCF is underivable (no capex tag)."""
    sections: dict = {}
    xbrl = {
        "net_income": {"current": {"value": -5_000_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": 3_000_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    assert sections["earnings_quality"]["cash_conversion"] == "Operating cash flow was positive despite a net loss."


def test_apply_structured_fallbacks_cash_conversion_loss_and_cash_burn_authors_nothing():
    """A loss AND negative operating cash flow, with no FCF, has no distinctive deterministic accrual
    read to surface here (the model's operating_vs_one_time / red_flags cover it) — author nothing,
    never an empty stub. Pins the deliberate drop (rule 12)."""
    sections: dict = {}
    xbrl = {
        "net_income": {"current": {"value": -5_000_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": -3_000_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    assert "cash_conversion" not in (sections.get("earnings_quality") or {})


def test_apply_structured_fallbacks_cash_conversion_negative_ocf_positive_ni():
    """A negative operating cash flow against a POSITIVE net income is a real accrual red flag — the
    negative multiple is authored, not suppressed. Pins the documented behavior (rule 12)."""
    sections: dict = {}
    xbrl = {
        "net_income": {"current": {"value": 20_000_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": -4_000_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    assert sections["earnings_quality"]["cash_conversion"] == "Operating cash flow was -0.2x net income (cash conversion)."


def test_apply_structured_fallbacks_cash_conversion_partial_metrics_no_crash():
    """The input-presence guards protect two crash paths on partial standardized XBRL — a missing OCF
    (`None / number`) and a missing NI (`None > 0`, a TypeError via short-circuit) — both must fall
    through to FCF-only without raising."""
    # net_income + free_cash_flow, NO operating_cash_flow.
    s1: dict = {}
    openai_service._apply_structured_fallbacks(s1, {"company_name": "X"}, {
        "net_income": {"current": {"value": 20_000_000_000, "period": "FY2025"}},
        "free_cash_flow": {"current": {"value": 9_000_000_000, "period": "FY2025"}},
    })
    assert s1["earnings_quality"]["cash_conversion"] == "Free cash flow of $9.0B."

    # operating_cash_flow + free_cash_flow, NO net_income.
    s2: dict = {}
    openai_service._apply_structured_fallbacks(s2, {"company_name": "X"}, {
        "operating_cash_flow": {"current": {"value": 30_000_000_000, "period": "FY2025"}},
        "free_cash_flow": {"current": {"value": 9_000_000_000, "period": "FY2025"}},
    })
    assert s2["earnings_quality"]["cash_conversion"] == "Free cash flow of $9.0B."


def test_apply_structured_fallbacks_cash_conversion_strips_stray_model_text_for_banks():
    """Ownership invariant: cash_conversion is machine-authored OR absent, never model-authored. On the
    bank path the filler suppresses (does not author), so a stray model-provided value — which would
    otherwise render UNPOLICED now that figure_trace excludes the field — must be stripped. The model's
    other earnings-quality prose is left intact."""
    sections = {"earnings_quality": {
        "operating_vs_one_time": "Reported results reflected the loan book.",
        # Fabricated figure + an OBJECTIVITY-banned adjective — exactly what must not survive.
        "cash_conversion": "Cash conversion was robust at $77.7B of operating cash flow.",
    }}
    xbrl = {
        "net_interest_income": {"current": {"value": 5_000_000_000, "period": "FY2025"}},
        "net_income": {"current": {"value": 20_000_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": 30_000_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    eq = sections["earnings_quality"]
    assert "cash_conversion" not in eq
    assert eq["operating_vs_one_time"] == "Reported results reflected the loan book."


def test_apply_structured_fallbacks_cash_conversion_strips_stray_model_text_when_uncomputable():
    """Same invariant on the non-bank nothing-computable path (no NI/OCF/FCF): a stray model-provided
    cash_conversion is stripped rather than left to render unpoliced."""
    sections = {"earnings_quality": {"cash_conversion": "Cash conversion was exceptional, near $99B."}}
    xbrl = {"revenue": {"current": {"value": 42_300_000_000, "period": "FY2025"}}}
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    assert "cash_conversion" not in sections["earnings_quality"]


def test_apply_structured_fallbacks_cash_conversion_near_breakeven_is_qualitative():
    """Near-breakeven positive NI: the multiple is dominated by a tiny denominator (NI $10M / OCF $2.5B
    = 250x) and reads as noise, so above the ±10x band the read is stated qualitatively — the signal
    (cash far exceeding income) without an absurd multiple."""
    sections: dict = {}
    xbrl = {
        "net_income": {"current": {"value": 10_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": 2_500_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    cc = sections["earnings_quality"]["cash_conversion"]
    assert cc == "Operating cash flow far exceeded net income."
    assert "x net income" not in cc and "250" not in cc


def test_apply_structured_fallbacks_cash_conversion_ratio_band_boundary():
    """The ±10x band is inclusive: exactly 10.0x still prints the multiple; just beyond flips to the
    qualitative read."""
    s1: dict = {}
    openai_service._apply_structured_fallbacks(s1, {"company_name": "X"}, {
        "net_income": {"current": {"value": 1_000_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": 10_000_000_000, "period": "FY2025"}},
    })
    assert s1["earnings_quality"]["cash_conversion"] == "Operating cash flow was 10.0x net income (cash conversion)."

    s2: dict = {}
    openai_service._apply_structured_fallbacks(s2, {"company_name": "X"}, {
        "net_income": {"current": {"value": 1_000_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": 11_000_000_000, "period": "FY2025"}},
    })
    assert s2["earnings_quality"]["cash_conversion"] == "Operating cash flow far exceeded net income."


def _segment_xbrl(currency=None):
    xbrl = {
        "segments": [
            {"name": "Americas", "revenue": 178_353_000_000.0, "revenue_prior": 167_045_000_000.0,
             "operating_income": 72_480_000_000.0, "period": "2025-09-27"},
            {"name": "Europe", "revenue": 111_032_000_000.0, "revenue_prior": 101_328_000_000.0,
             "operating_income": 47_739_000_000.0, "period": "2025-09-27"},
        ],
    }
    if currency:
        xbrl["reporting_currency"] = currency
    return xbrl


def test_apply_structured_fallbacks_segments_authored_from_xbrl():
    """§7 is machine-authored from XBRL segment dimensions: per-segment revenue + operating income +
    YoY revenue change + a deterministic mix (share of segment revenue) and operating-margin read."""
    sections: dict = {}
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, _segment_xbrl())

    seg = sections["segments"]
    assert [r["segment"] for r in seg] == ["Americas", "Europe"]   # revenue-descending
    a = seg[0]
    assert a["revenue"] == "$178.4B" and a["operating_income"] == "$72.5B"
    assert a["change"] == "+6.8%"                                   # (178.353-167.045)/167.045
    assert "62% of segment revenue" in a["commentary"] and "41% operating margin" in a["commentary"]
    assert seg[1]["change"] == "+9.6%"


def test_apply_structured_fallbacks_segments_strip_stray_model_rows():
    """Ownership invariant: a stray model-authored segments list is replaced by the deterministic table
    (its fabricated figures never survive)."""
    sections = {"segments": [{"segment": "Hallucinated", "revenue": "$999B", "commentary": "made up"}]}
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, _segment_xbrl())

    names = [r["segment"] for r in sections["segments"]]
    assert names == ["Americas", "Europe"] and "Hallucinated" not in names


def test_apply_structured_fallbacks_segments_stripped_when_no_xbrl():
    """No XBRL segment data (single-segment / undimensioned / bank filer) → the section is dropped, and
    a stray model segments list is stripped rather than left to render unpoliced (graceful degradation)."""
    sections = {"segments": [{"segment": "Hallucinated", "revenue": "$999B"}]}
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, {"revenue": {"current": {"value": 1.0}}})
    assert "segments" not in sections

    # Nothing to strip, nothing to inject → still absent, no crash.
    empty: dict = {}
    openai_service._apply_structured_fallbacks(empty, {"company_name": "X"}, {})
    assert "segments" not in empty


def test_apply_structured_fallbacks_segments_merge_model_commentary():
    """T5.2b hybrid: the model's qualitative driver (a commentary-only row keyed by the grounding's
    label list) is merged onto the CODE row — machine mix/margin first, model words appended. A label
    the code did not author is dropped (the model can never create a row); a code row the model said
    nothing about keeps the deterministic read alone."""
    sections = {"segments": [
        {"segment": "Americas", "commentary": "Growth was led by data center demand."},
        {"segment": "Phantom Division", "commentary": "Should never render."},
    ]}
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, _segment_xbrl())

    seg = sections["segments"]
    assert [r["segment"] for r in seg] == ["Americas", "Europe"]   # phantom dropped, order = code's
    assert seg[0]["commentary"] == (
        "62% of segment revenue, 41% operating margin — Growth was led by data center demand."
    )
    assert " — " not in seg[1]["commentary"]                        # Europe: deterministic-only
    # Figures stay code-authored regardless of what the model wrote.
    assert seg[0]["revenue"] == "$178.4B"


def test_apply_structured_fallbacks_segments_commentary_match_is_case_insensitive():
    sections = {"segments": [{"segment": "  AMERICAS ", "commentary": "Led by data center demand."}]}
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, _segment_xbrl())
    assert sections["segments"][0]["commentary"].endswith("— Led by data center demand.")


def test_apply_structured_fallbacks_segments_placeholder_commentary_ignored():
    """A placeholder / 'Not disclosed' / 'Not applicable' model line never reaches the cell —
    deterministic read only."""
    sections = {"segments": [
        {"segment": "Americas", "commentary": "Not disclosed—no drivers stated."},
        {"segment": "Europe", "commentary": "Not applicable for this filing."},
    ]}
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, _segment_xbrl())
    for row in sections["segments"]:
        assert " — " not in row["commentary"]


def test_apply_structured_fallbacks_segments_nonstring_commentary_dropped():
    """Schema-loose payloads: a dict/list-shaped commentary (or label) must be dropped, never
    str()-coerced into a Python repr in the user-facing cell."""
    sections = {"segments": [
        {"segment": "Americas", "commentary": {"text": "a $55.5B gain"}},
        {"segment": ["Europe"], "commentary": "A real driver."},
    ]}
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, _segment_xbrl())
    for row in sections["segments"]:
        assert " — " not in row["commentary"] and "{" not in row["commentary"]


def test_apply_structured_fallbacks_segments_commentary_cannot_create_section():
    """Commentary-only model rows with no XBRL segment data behind them: harvested, then everything is
    dropped — the model can never conjure the section key (ownership invariant unchanged)."""
    sections = {"segments": [{"segment": "Americas", "commentary": "A driver."}]}
    openai_service._apply_structured_fallbacks(
        sections, {"company_name": "X"}, {"revenue": {"current": {"value": 1.0}}}
    )
    assert "segments" not in sections


def test_apply_structured_fallbacks_segments_use_reporting_currency():
    """Foreign issuers: segment figures carry the ISO prefix, never a bare '$'."""
    sections: dict = {}
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, _segment_xbrl(currency="EUR"))
    seg = sections["segments"]
    assert seg[0]["revenue"] == "EUR 178.4B" and seg[0]["operating_income"] == "EUR 72.5B"
    assert "$" not in (seg[0]["revenue"] + seg[0]["operating_income"])


def test_apply_structured_fallbacks_cash_conversion_large_negative_ratio_is_qualitative():
    """A large operating cash OUTFLOW against a small positive income (NI $10M / OCF -$2.5B = -250x) is
    the same denominator-noise problem on the negative side — stated qualitatively as the red flag it is."""
    sections: dict = {}
    xbrl = {
        "net_income": {"current": {"value": 10_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": -2_500_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    cc = sections["earnings_quality"]["cash_conversion"]
    assert cc == "Operating cash flow was negative despite positive net income."
    assert "x net income" not in cc


def test_apply_structured_fallbacks_cash_conversion_suppressed_for_banks():
    """NI-vs-CFO and a capex-based FCF are meaningless for a financial institution (unclassified
    balance sheet, lending/deposit-driven cash flow). Gated on the SAME predicate as the bank
    grounding NOTE — presence of a bank revenue component suppresses the field entirely."""
    sections: dict = {}
    xbrl = {
        "net_interest_income": {"current": {"value": 5_000_000_000, "period": "FY2025"}},
        "net_income": {"current": {"value": 20_000_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": 30_000_000_000, "period": "FY2025"}},
        "free_cash_flow": {"current": {"value": 25_000_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    assert "cash_conversion" not in (sections.get("earnings_quality") or {})


def test_apply_structured_fallbacks_cash_conversion_graceful_when_metrics_absent():
    """Neither ratio nor FCF computable (no NI/OCF/FCF) → author nothing, never an empty stub."""
    sections: dict = {}
    xbrl = {"revenue": {"current": {"value": 42_300_000_000, "period": "FY2025"}}}
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    assert "cash_conversion" not in (sections.get("earnings_quality") or {})


def test_apply_structured_fallbacks_cash_conversion_uses_reporting_currency():
    """FCF is a monetary figure; a foreign issuer's must carry the ISO prefix, never a bare '$'. The
    unitless ratio is currency-agnostic."""
    sections: dict = {}
    xbrl = {
        "reporting_currency": "EUR",
        "net_income": {"current": {"value": 20_000_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": 30_000_000_000, "period": "FY2025"}},
        "free_cash_flow": {"current": {"value": 25_000_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    cc = sections["earnings_quality"]["cash_conversion"]
    assert "1.5x net income" in cc and "free cash flow of EUR 25.0B" in cc
    assert "$" not in cc


def test_apply_structured_fallbacks_cash_conversion_overwrites_model_text():
    """Code OWNS cash_conversion (the model no longer authors it): any model-written value is replaced
    unconditionally, while the model's qualitative operating_vs_one_time prose is left untouched."""
    sections = {"earnings_quality": {
        "operating_vs_one_time": "Reported net income included a $2.1B unrealized equity gain.",
        "cash_conversion": "The company generated strong cash flow of $99B this period.",
    }}
    xbrl = {
        "net_income": {"current": {"value": 20_000_000_000, "period": "FY2025"}},
        "operating_cash_flow": {"current": {"value": 30_000_000_000, "period": "FY2025"}},
        "free_cash_flow": {"current": {"value": 25_000_000_000, "period": "FY2025"}},
    }
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, xbrl)

    eq = sections["earnings_quality"]
    assert eq["operating_vs_one_time"] == "Reported net income included a $2.1B unrealized equity gain."
    assert "1.5x net income" in eq["cash_conversion"] and "$99B" not in eq["cash_conversion"]
