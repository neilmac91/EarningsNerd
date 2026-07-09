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
