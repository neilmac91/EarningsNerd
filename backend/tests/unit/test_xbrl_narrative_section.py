"""Unit tests for the summary prompt's XBRL grounding block (roadmap 2.6 Phase B).

`build_xbrl_narrative_section` is the single point that decides which SEC-verified figures the
summary *narrative* may cite. Phase B adds the full cash-flow statement (investing/financing) and
working-capital lines to that whitelist. These tests exercise the real builder/formatter offline
(no AI call) and prove (a) the new metrics surface with correct labels/formatting, (b) the ratio
format renders a dimensionless multiple, and (c) the block is byte-for-byte unchanged for filings
that carry only the legacy metrics (so the eval baseline / flag-off behaviour can't regress).
"""

import pytest

from app.services.openai_service import (
    _XBRL_NARRATIVE_SPEC,
    _format_xbrl_metric_value,
    build_xbrl_narrative_section,
)


def _cur(value, period="2024-09-28"):
    return {"current": {"value": value, "period": period}}


class TestFormat:
    def test_usd_pct_eps_unchanged(self):
        # Regression: the pre-existing format kinds must be untouched.
        assert _format_xbrl_metric_value(391035000000.0, "usd") == "$391,035,000,000"
        assert _format_xbrl_metric_value(45.2, "pct") == "45.2%"
        assert _format_xbrl_metric_value(6.13, "eps") == "6.13"
        assert _format_xbrl_metric_value(None, "usd") == "Not disclosed"

    def test_ratio_renders_dimensionless_multiple(self):
        # A current ratio is a multiple, never $ or % — e.g. "2.50x".
        assert _format_xbrl_metric_value(2.5, "ratio") == "2.50x"
        assert _format_xbrl_metric_value(1.0, "ratio") == "1.00x"


class TestSpec:
    def test_new_2_6_keys_are_whitelisted(self):
        keys = {key for _, key, _ in _XBRL_NARRATIVE_SPEC}
        for new_key in (
            "investing_cash_flow", "financing_cash_flow",
            "current_assets", "current_liabilities", "working_capital", "current_ratio",
        ):
            assert new_key in keys, f"{new_key} missing from _XBRL_NARRATIVE_SPEC"

    def test_current_ratio_uses_ratio_format(self):
        spec = {key: kind for _, key, kind in _XBRL_NARRATIVE_SPEC}
        assert spec["current_ratio"] == "ratio"
        assert spec["investing_cash_flow"] == "usd"
        assert spec["working_capital"] == "usd"


class TestBuildSection:
    def test_empty_inputs_return_blank(self):
        assert build_xbrl_narrative_section(None) == ""
        assert build_xbrl_narrative_section({}) == ""
        # all-absent values → no rows → blank (so the prompt is unchanged)
        assert build_xbrl_narrative_section({"revenue": {"current": {"value": None}}}) == ""

    def test_new_metrics_surface_with_labels_and_formats(self):
        section = build_xbrl_narrative_section({
            "investing_cash_flow": _cur(-15000000.0),
            "financing_cash_flow": _cur(-40000000.0),
            "current_assets": _cur(300000000.0),
            "current_liabilities": _cur(120000000.0),
            "working_capital": _cur(180000000.0),
            "current_ratio": _cur(2.5),
        })
        assert "Investing Cash Flow: $-15,000,000" in section
        assert "Financing Cash Flow: $-40,000,000" in section
        assert "Current Assets: $300,000,000" in section
        assert "Current Liabilities: $120,000,000" in section
        assert "Working Capital: $180,000,000" in section
        assert "Current Ratio: 2.50x" in section  # ratio format, not $/%

    def test_malformed_entries_skip_without_raising(self):
        # Defensive: a non-dict entry / current / prior (corrupted cache or future upstream change)
        # must be skipped, never raise AttributeError in the summary hot path.
        section = build_xbrl_narrative_section({
            "revenue": ["not", "a", "dict"],                 # entry not a dict
            "net_income": {"current": "also not a dict"},     # current not a dict
            "eps_diluted": None,                              # entry is None
            "gross_profit": {"current": {"value": 50.0, "period": "2024-09-28"},
                             "prior": "bad-prior"},            # prior not a dict → no YoY, no raise
        })
        # only the well-formed gross_profit survives
        assert "Gross Profit: $50 (period: 2024-09-28)" in section
        assert "prior:" not in section
        assert "Revenue" not in section and "Net Income" not in section

    def test_non_dict_metrics_returns_blank(self):
        assert build_xbrl_narrative_section(["not", "a", "dict"]) == ""

    def test_absent_whitelisted_keys_are_skipped(self):
        # Only revenue present → only the Revenue line; no "Not disclosed" noise, no other labels.
        section = build_xbrl_narrative_section({"revenue": _cur(100.0)})
        assert "Revenue: $100" in section
        assert "Current Ratio" not in section
        assert "Working Capital" not in section
        assert "Not disclosed" not in section

    def test_prior_period_appended_when_present(self):
        # Prior-period context (pre-existing behaviour). NOTE: an explicit YoY % was trialled here but
        # dropped — a judged before/after showed it induced the model to over-explain the now-salient
        # cash-flow deltas with *fabricated* causal drivers (faithfulness 4→2). See tasks/lessons.md.
        section = build_xbrl_narrative_section({
            "revenue": {
                "current": {"value": 391.0, "period": "2024-09-28"},
                "prior": {"value": 383.0, "period": "2023-09-30"},
            }
        })
        assert "Revenue: $391 (period: 2024-09-28); prior: $383 (2023-09-30)" in section
        assert "YoY:" not in section  # no derived comparative fed to the model (fabrication guard)

    def test_none_or_empty_period_falls_back_to_na(self):
        # A present-but-None/empty period must render "N/A", not "None" / "" (defensive hardening).
        section = build_xbrl_narrative_section({
            "revenue": {"current": {"value": 100.0, "period": None},
                        "prior": {"value": 90.0, "period": ""}},
        })
        assert "Revenue: $100 (period: N/A); prior: $90 (N/A)" in section

    def test_working_capital_fallback_rejects_boolean_values(self):
        # bool is an int subclass; a stray True/False must not slip into CA - CL arithmetic.
        section = build_xbrl_narrative_section({
            "current_assets": {"current": {"value": True, "period": "2024"}},
            "current_liabilities": {"current": {"value": 100.0, "period": "2024"}},
        })
        assert "Working Capital" not in section  # derivation refused, no bogus "$-99"

    def test_free_cash_flow_label_names_the_derivation(self):
        section = build_xbrl_narrative_section({"free_cash_flow": _cur(28_000_000.0)})
        assert "Free Cash Flow (OCF - CapEx): $28,000,000" in section

    def test_working_capital_fallback_derived_when_untagged(self):
        # working_capital absent, but current assets/liabilities present → derive CA - CL, labeled.
        section = build_xbrl_narrative_section({
            "current_assets": {"current": {"value": 300.0, "period": "2024"},
                               "prior": {"value": 250.0, "period": "2023"}},
            "current_liabilities": {"current": {"value": 120.0, "period": "2024"},
                                    "prior": {"value": 100.0, "period": "2023"}},
        })
        # derived value 300-120=180 current, 250-100=150 prior (no YoY suffix — see above)
        assert "Working Capital (Current Assets - Current Liabilities): $180 (period: 2024)" in section
        assert "prior: $150 (2023)" in section
        assert "YoY:" not in section

    def test_working_capital_direct_value_preferred_over_fallback(self):
        # When the metric IS tagged, use it as-is with the plain "Working Capital" label (no derivation).
        section = build_xbrl_narrative_section({
            "working_capital": _cur(999.0),
            "current_assets": _cur(300.0),
            "current_liabilities": _cur(120.0),
        })
        assert "Working Capital: $999" in section
        assert "Current Assets - Current Liabilities" not in section

    def test_working_capital_fallback_skipped_when_side_missing(self):
        # Only current assets present (no liabilities) → no derivation, no crash, no WC line.
        section = build_xbrl_narrative_section({"current_assets": _cur(300.0)})
        assert "Working Capital" not in section
        assert "Current Assets: $300" in section

    def test_legacy_only_block_is_byte_for_byte(self):
        # The flag-OFF / pre-Phase-B narrative must be unchanged: with only legacy metrics present,
        # the new keys produce nothing and the block matches the exact prior output.
        section = build_xbrl_narrative_section({
            "revenue": {"current": {"value": 391035000000.0, "period": "2024-09-28"}},
            "net_income": {"current": {"value": 93736000000.0, "period": "2024-09-28"}},
        })
        assert section == (
            "XBRL STANDARDIZED FINANCIAL DATA (SEC-verified; quote these figures verbatim):\n"
            "- Revenue: $391,035,000,000 (period: 2024-09-28)\n"
            "- Net Income: $93,736,000,000 (period: 2024-09-28)"
        )


class TestReportingCurrencyDirective:
    """Wave 3 / FPI: for foreign (non-USD) filers the block must emphatically name the reporting
    currency (cuts the intermittent '$'-mislabel slip); for USD/domestic it stays byte-for-byte
    unchanged so the eval baseline can't regress."""

    def test_non_usd_prepends_currency_directive(self):
        block = build_xbrl_narrative_section({
            "reporting_currency": "DKK",
            "revenue": _cur(309_100_000_000.0, "2025-12-31"),
        })
        assert block.startswith("CURRENCY — this issuer reports in DKK")
        assert 'render EVERY monetary figure' in block
        assert 'NEVER as a bare "$"' in block
        # the SEC-verified figures block is still present, after the directive
        assert "XBRL STANDARDIZED FINANCIAL DATA" in block
        # and its figures are relabeled to the reporting currency, not a bare '$'
        assert "Revenue: DKK 309,100,000,000" in block
        assert "Revenue: $" not in block

    def test_usd_is_byte_for_byte_unchanged(self):
        metrics = {"reporting_currency": "USD", "revenue": _cur(383_000_000_000.0)}
        with_flag = build_xbrl_narrative_section(metrics)
        no_flag = build_xbrl_narrative_section({"revenue": _cur(383_000_000_000.0)})
        assert with_flag == no_flag  # USD adds nothing
        assert with_flag.startswith("XBRL STANDARDIZED FINANCIAL DATA")

    def test_missing_currency_is_unchanged(self):
        block = build_xbrl_narrative_section({"revenue": _cur(100_000_000_000.0)})
        assert block.startswith("XBRL STANDARDIZED FINANCIAL DATA")
        assert "CURRENCY —" not in block

    def test_empty_metrics_still_empty(self):
        # No rows -> "" regardless of currency (nothing to ground).
        assert build_xbrl_narrative_section({"reporting_currency": "EUR"}) == ""


class TestReturnsBand:
    """±200% ROE/ROA band parity (#621 staff review): the band that keeps near-zero-equity noise
    (HD's "1644.4%") out of the machine-authored §4 line must also keep it out of the model's
    grounding — otherwise the narrative feeds the model the exact figure the render suppressed,
    and a restated "ROE of 1,644%" in prose is invisible to the dollar-only figure gate."""

    def test_out_of_band_current_drops_the_line(self):
        # HD-class: ~$1B equity → arithmetically-true 1644.4% ROE. Never shown to the model;
        # in-band ROA on the same filer still grounds.
        section = build_xbrl_narrative_section({
            "return_on_equity": _cur(1644.4),
            "return_on_assets": _cur(17.9),
        })
        assert "Return on Equity" not in section
        assert "1644.4" not in section
        assert "Return on Assets: 17.9%" in section

    def test_out_of_band_prior_drops_just_the_prior_clause(self):
        # Equity recovered from near-zero: current is honest, the prior is noise — mirror §4's
        # _ratio_clause exactly (current renders, parenthetical dropped).
        section = build_xbrl_narrative_section({
            "return_on_equity": {
                "current": {"value": 45.0, "period": "2025-12-31"},
                "prior": {"value": 1644.4, "period": "2024-12-31"},
            },
        })
        assert "Return on Equity: 45.0% (period: 2025-12-31)" in section
        assert "prior" not in section and "1644.4" not in section

    def test_in_band_values_unchanged_including_honest_negatives(self):
        # A loss against positive equity is honest signal, not noise — stays, with its prior.
        section = build_xbrl_narrative_section({
            "return_on_equity": {
                "current": {"value": -12.3, "period": "2025-12-31"},
                "prior": {"value": 8.1, "period": "2024-12-31"},
            },
        })
        assert "Return on Equity: -12.3% (period: 2025-12-31); prior: 8.1% (2024-12-31)" in section

    def test_band_boundary_is_inclusive(self):
        # Exactly ±200.0 is IN band — same boundary the §4 render tests pin.
        section = build_xbrl_narrative_section({
            "return_on_equity": _cur(200.0),
            "return_on_assets": _cur(-200.0),
        })
        assert "Return on Equity: 200.0%" in section
        assert "Return on Assets: -200.0%" in section

    def test_other_pct_metrics_are_not_banded(self):
        # Blast radius is the two returns keys ONLY — a >200% margin (near-zero-revenue pathology)
        # is a different class, deliberately untouched by this guard.
        section = build_xbrl_narrative_section({"gross_margin": _cur(250.0)})
        assert "Gross Margin: 250.0%" in section

    def test_render_and_narrative_share_one_predicate(self):
        # Drift gate: §4's _ratio_clause and this grounding block must band with the SAME function —
        # the #621 finding was precisely these two surfaces treating the class differently.
        from app.services.ai import markdown_render
        from app.services.ai.xbrl_narrative import returns_ratio_in_band

        assert markdown_render.returns_ratio_in_band is returns_ratio_in_band


@pytest.mark.parametrize("surface", ["grounding", "render"])
@pytest.mark.parametrize("period", ["2026-04-26", "2025-12-31", None])
def test_return_basis_is_explicit_on_both_surfaces(surface, period):
    """Known end dates and missing dates never imply annualization or average balances."""
    from app.services.ai import markdown_render, xbrl_narrative
    from app.services.openai_service import openai_service

    assert markdown_render.return_ratio_basis is xbrl_narrative.return_ratio_basis
    metrics = {
        "return_on_equity": {
            "current": {"value": 29.8, "period": period},
            "prior": {"value": 22.4, "period": "2025-04-27"},
        },
        "return_on_assets": {"current": {"value": 22.5, "period": period}},
    }
    if surface == "grounding":
        text = build_xbrl_narrative_section(metrics)
        assert "period net income / period-end equity, not annualized" in text
        assert "period net income / period-end assets, not annualized" in text
    else:
        sections = {}
        openai_service._apply_structured_fallbacks(sections, {}, metrics)
        text = sections["value_drivers"]["returns_on_capital"]
        # The rendered line names the formula and an unknown numerator scope explicitly (never a
        # _PLACEHOLDER_STRINGS word), and dates the comparator it actually used.
        assert text.startswith("Period net income (numerator scope unestablished) / period-end equity, not annualized: 29.8%")
        assert "period net income (numerator scope unestablished) / period-end assets, not annualized: 22.5%" in text
        assert "(prior at 2025-04-27: 22.4%)" in text
    assert all(value in text for value in ("29.8%", "22.4%", "22.5%"))
    assert "quarter" not in text.lower() and "average" not in text.lower()
    if surface == "grounding":
        return

    # The render uses the canonical period, not a padded raw spelling.
    metrics["return_on_equity"]["prior"]["period"] = " 2025-04-27 "
    sections = {}
    openai_service._apply_structured_fallbacks(sections, {}, metrics)
    text = sections["value_drivers"]["returns_on_capital"]
    assert "(prior at 2025-04-27: 22.4%)" in text and " 2025-04-27 " not in text

    # A numeric prior without a usable period is not an honest comparator: the rendered line
    # abstains rather than reopening the bare-"prior" FIGS defect; the current ratio still renders.
    for unusable_period in (None, "", " N/A ", 20250427):
        metrics["return_on_equity"]["prior"]["period"] = unusable_period
        sections = {}
        openai_service._apply_structured_fallbacks(sections, {}, metrics)
        text = sections["value_drivers"]["returns_on_capital"]
        assert "22.4%" not in text and "prior" not in text
        assert "not annualized: 29.8%" in text


@pytest.mark.asyncio
async def test_jpm_rendered_returns_do_not_take_issuer_ratio_names(monkeypatch):
    """Issuer ROE/ROA reach the model verbatim beside the unchanged grounding block; only the
    code-rendered §4 line renames the differently-based derived ratios by formula."""
    from app.services.openai_service import openai_service

    # Retained JPM table wording with extraction whitespace/NBSPs normalized for this unit fixture.
    issuer_ratio_excerpt = (
        "Selected ratios and metrics\n"
        "Return on common equity (“ROE”) 17% 18% 17%\n"
        "Return on assets (“ROA”) 1.29% 1.43% 1.30%"
    )
    parent = {"numerator": {"raw_tag": "us-gaap:NetIncomeLoss"}}
    metrics = {
        "net_interest_income": {"current": {"value": 95_443_000_000}},
        "return_on_equity": {
            "current": {"value": 15.74007140531622, "period": "2025-12-31", **parent},
            "prior": {"value": 16.96001253052866, "period": "2024-12-31", **parent},
        },
        "return_on_assets": {
            "current": {"value": 1.289249474564397, "period": "2025-12-31", **parent},
            "prior": {"value": 1.4607473642292648, "period": "2024-12-31", **parent},
        },
    }
    sections: dict = {}
    openai_service._apply_structured_fallbacks(sections, {}, metrics)
    rendered = sections["value_drivers"]["returns_on_capital"]
    grounding = build_xbrl_narrative_section(metrics)
    captured: dict = {}

    monkeypatch.setattr(openai_service, "_parse_and_clean_text", lambda *_args: {
        "filing_sample": issuer_ratio_excerpt,
        "financial_data": {
            "revenue": [], "net_income": [], "cash_flow": [], "segments": [], "guidance": [],
        },
        "recovery_sources": (),
    })

    async def capture_request(create_kwargs, **_kwargs):
        captured.update(create_kwargs)
        return "{}"

    async def finish_without_recovery(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(openai_service, "_request_content", capture_request)
    monkeypatch.setattr(openai_service, "_assemble_structured_summary", finish_without_recovery)
    await openai_service.generate_structured_summary(
        issuer_ratio_excerpt, "JPMorgan Chase", "10-K", metrics,
        filing_excerpt=issuer_ratio_excerpt,
    )
    prompt = captured["messages"][1]["content"]

    assert rendered == (
        "Period net income attributable to the parent / period-end equity, not annualized: 15.7% "
        "(prior at 2024-12-31: 17.0%); period net income attributable to the parent / period-end "
        "assets, not annualized: 1.3% (prior at 2024-12-31: 1.5%)."
    )
    assert "Return on Equity" not in rendered and "Return on Assets" not in rendered
    # Model-facing bytes are unchanged in this tranche: the grounding block keeps its existing
    # labels and formula basis (renaming them is the held prompt tranche, thread r4080047443), and
    # the source's real issuer-defined ratios stay in the prompt verbatim; neither is erased merely
    # to avoid a naming collision.
    assert grounding in prompt
    assert (
        "- Return on Equity: 15.7% (period: 2025-12-31); prior: 17.0% (2024-12-31); "
        "basis: period net income / period-end equity, not annualized"
    ) in grounding
    assert "numerator scope" not in prompt and "attributable to the parent" not in prompt
    assert issuer_ratio_excerpt in prompt
    assert "Return on common equity (“ROE”) 17% 18% 17%" in prompt
    assert "Return on assets (“ROA”) 1.29% 1.43% 1.30%" in prompt


@pytest.mark.parametrize("surface", ["grounding", "web", "markdown", "pdf", "csv"])
@pytest.mark.parametrize("tag", [None, "issuer:PurchaseOfEquipmentAndSoftware"])
def test_selected_cash_flow_basis_survives_consumers(surface, tag):
    """A narrow cash-flow purchase amount cannot silently become issuer/discretionary FCF."""
    import csv
    import io
    import json
    from copy import deepcopy
    from app.services.ai import markdown_render, xbrl_narrative
    from app.services.export_service import ExportService
    from app.services.openai_service import openai_service
    from app.services.summary_sections import render_sections, render_sections_json, sections_to_markdown

    assert markdown_render.cash_flow_basis is xbrl_narrative.cash_flow_basis
    metrics = {
        "reporting_currency": "CNY",
        "financial_classification": {"is_financial": False},
        "operating_cash_flow": {"current": {"value": 19_000_000_000, "period": "2025-12-31"}},
        "capital_expenditures": {
            "current": {"value": -8_000_000_000, "raw_tag": tag},
            "prior": {"value": -5_000_000_000, "raw_tag": None},
        },
        "free_cash_flow": {"current": {"value": 11_000_000_000}},
    }
    original = deepcopy(metrics)
    if surface == "grounding":
        text = build_xbrl_narrative_section(metrics)
    else:
        sections = {}
        openai_service._apply_structured_fallbacks(sections, {}, metrics)
        raw = {"schema_version": 2, "sections": sections}
        rendered = render_sections(raw)
        if surface == "web":
            text = json.dumps(render_sections_json(raw))
        elif surface == "markdown":
            text = sections_to_markdown(rendered)
        elif surface == "pdf":
            text = "".join(ExportService()._render_section_html(section) for section in rendered)
        else:
            output = io.StringIO()
            for section in rendered:
                ExportService._write_section_csv(csv.writer(output), section)
            text = output.getvalue()
    assert "derived as operating cash flow minus the absolute selected capex cash-flow amount" in text
    assert "not an issuer-defined or discretionary-cash measure" in text
    assert "selected cash-flow amount, not necessarily total capital investment" in text
    assert ("current source concept: issuer:PurchaseOfEquipmentAndSoftware" in text) == (bool(tag) and surface == "grounding")
    if surface != "grounding":
        assert "issuer:PurchaseOfEquipmentAndSoftware" not in text
    assert "prior source concept:" not in text
    assert ("11,000,000,000" in text and "8,000,000,000" in text) if surface == "grounding" else ("11.0B" in text and "8.0B" in text)
    assert metrics == original


# The grounding block main (c13b069a) emits for the operand fixture below, captured from main's own
# builder. The successor extractor attaches ratio operands; the model-facing bytes must not move.
_MAIN_OPERAND_FIXTURE_GROUNDING = (
    "XBRL STANDARDIZED FINANCIAL DATA (SEC-verified; quote these figures verbatim):\n"
    "- Net Income: $100 (period: 2026-06-30); prior: $55 (2026-03-31)\n"
    "- Return on Equity: 10.0% (period: 2026-06-30); prior: 8.0% (2025-12-31); "
    "basis: period net income / period-end equity, not annualized\n"
    "- Return on Assets: 5.0% (period: 2026-06-30); prior: 4.0% (2025-12-31); "
    "basis: period net income / period-end assets, not annualized\n"
    "- Total Assets: $2,000 (period: 2026-06-30); prior: $2,000 (2025-12-31)\n"
    "- Shareholders' Equity: $1,000 (period: 2026-06-30); prior: $1,000 (2025-12-31)"
)


@pytest.mark.parametrize("tag,scope", [
    ("us-gaap:NetIncomeLoss", "attributable to the parent"),
    ("us-gaap:ProfitLoss", "including noncontrolling interests"),
    ("us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic", "available to common shareholders"),
    ("ifrs-full:ProfitLoss", "including noncontrolling interests"),
    ("ifrs-full:ProfitLossAttributableToOwnersOfParent", "attributable to owners of the parent"),
    ("issuer:AdjustedProfit", "(numerator scope unestablished)"),
    (None, "(numerator scope unestablished)"),
])
def test_return_ratios_own_their_selected_operands_across_periods(tag, scope):
    """A missing balance skips NI's immediate prior; no sibling point may supply ratio scope, and
    operand custody never reaches the model's grounding bytes."""
    from copy import deepcopy
    from app.services.edgar.xbrl_service import edgar_xbrl_service
    from app.services.openai_service import openai_service
    from app.services.summary_sections import render_sections, sections_to_markdown

    raw = {
        "net_income": [
            {"period": "2026-06-30", "period_start": "2026-04-01", "value": 100,
             "raw_tag": tag, "currency": "USD", "form": "10-Q"},
            {"period": "2026-03-31", "period_start": "2026-01-01", "value": 55,
             "raw_tag": "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic", "currency": "USD"},
            {"period": "2025-12-31", "period_start": "2025-01-01", "value": 80,
             "raw_tag": "us-gaap:NetIncomeLoss", "currency": "USD"},
        ],
        "shareholders_equity": [
            {"period": "2026-06-30", "value": 1000, "currency": "USD"},
            {"period": "2025-12-31", "value": 1000, "currency": "USD"},
        ],
        "total_assets": [
            {"period": "2026-06-30", "value": 2000, "currency": "USD"},
            {"period": "2025-12-31", "value": 2000, "currency": "USD"},
        ],
    }
    original = deepcopy(raw)
    metrics = edgar_xbrl_service.extract_standardized_metrics(raw)
    assert metrics["net_income"]["prior"]["period"] == "2026-03-31"
    for key, denominator, expected in (("return_on_equity", "shareholders_equity", 10),
                                       ("return_on_assets", "total_assets", 5)):
        ratio = metrics[key]
        assert ratio["current"]["value"] == expected
        assert ratio["prior"]["value"] == expected * .8
        assert ratio["current"]["numerator"] == metrics["net_income"]["current"]
        assert ratio["prior"]["numerator"] == metrics["net_income"]["series"][2]
        assert ratio["current"]["denominator"] == metrics[denominator]["current"]
        assert ratio["prior"]["denominator"] == metrics[denominator]["prior"]
        assert ratio["current"]["numerator"]["period_start"] == "2026-04-01"
    assert raw == original

    # Model-facing bytes: the grounding block is main's exact output whatever the operands say.
    assert build_xbrl_narrative_section(metrics) == _MAIN_OPERAND_FIXTURE_GROUNDING

    sections = {}
    openai_service._apply_structured_fallbacks(sections, {}, metrics)
    for text in (sections["value_drivers"]["returns_on_capital"],
                 sections_to_markdown(render_sections({"schema_version": 2, "sections": sections}))):
        assert f"period net income {scope} / period-end equity, not annualized: 10.0%" in text.lower()
        assert f"period net income {scope} / period-end assets, not annualized: 5.0%" in text.lower()
        # The ratio prior is the 2025-12-31 point (NetIncomeLoss), not NI's own 2026-03-31 prior.
        assert "prior at 2025-12-31: 8.0%" in text and "prior at 2025-12-31: 4.0%" in text
        assert "2026-03-31" not in text
        # A prior-basis note (the prior point's OWN NetIncomeLoss scope) appears only when it
        # differs from the current point's scope.
        note = "; period net income attributable to the parent / period-end equity, not annualized)"
        assert (note in text.lower()) is (scope != "attributable to the parent")
    # A cached derived point cannot borrow a known scope from the sibling NI metric.
    for key in ("return_on_equity", "return_on_assets"):
        metrics[key]["current"].pop("numerator")
    sections = {}
    openai_service._apply_structured_fallbacks(sections, {}, metrics)
    for text in (sections["value_drivers"]["returns_on_capital"],
                 sections_to_markdown(render_sections({"schema_version": 2, "sections": sections}))):
        assert "net income (numerator scope unestablished) / period-end equity, not annualized: 10.0%" in text.lower()
        assert "net income (numerator scope unestablished) / period-end assets, not annualized: 5.0%" in text.lower()
    assert build_xbrl_narrative_section(metrics) == _MAIN_OPERAND_FIXTURE_GROUNDING


_ANNUAL_NI = [("2025-12-31", "2025-01-01", 100.0), ("2024-12-31", "2024-01-01", 80.0),
              ("2023-12-31", "2023-01-01", 60.0)]
_ANNUAL_ASSETS = [("2025-12-31", 2000.0), ("2024-12-31", 1900.0)]
# FIGS-like 10-Q (Q2): three-month net income for Q2, Q1 and the prior-year Q2.
_Q2_NI = [("2026-06-30", "2026-04-01", 12.0), ("2026-03-31", "2026-01-01", 7.5),
          ("2025-06-30", "2025-04-01", 9.0)]
_Q2_ASSETS = [("2026-06-30", 2000.0), ("2026-03-31", 1900.0), ("2025-12-31", 1800.0)]
_PARENT = "period net income attributable to the parent / period-end"
# The aligned lines below are main's (06ad809a) own render of the same inputs, byte for byte.
_ANNUAL_ROA = f"{_PARENT} assets, not annualized: 5.0% (prior at 2024-12-31: 4.2%)"
_Q2_ROA = f"{_PARENT} assets, not annualized: 0.6% (prior at 2026-03-31: 0.4%)"


@pytest.mark.parametrize("form,net_income,equity,assets,line,grounding_roe", [
    ("10-K", _ANNUAL_NI, [("2025-12-31", 500.0), ("2024-12-31", 400.0)], _ANNUAL_ASSETS,
     f"{_PARENT} equity, not annualized: 20.0% (prior at 2024-12-31: 20.0%); {_ANNUAL_ROA}",
     "Return on Equity: 20.0% (period: 2025-12-31); prior: 20.0% (2024-12-31)"),
    ("10-K", _ANNUAL_NI, [("2025-12-31", -50.0), ("2024-12-31", 400.0), ("2023-12-31", 300.0)],
     _ANNUAL_ASSETS, _ANNUAL_ROA, "Return on Equity: 20.0% (period: 2024-12-31); prior: 20.0% (2023-12-31)"),
    ("10-K", _ANNUAL_NI, [("2025-12-31", 0.0), ("2024-12-31", 400.0), ("2023-12-31", 300.0)],
     _ANNUAL_ASSETS, _ANNUAL_ROA, "Return on Equity: 20.0% (period: 2024-12-31); prior: 20.0% (2023-12-31)"),
    ("10-K", _ANNUAL_NI, [("2024-12-31", 400.0), ("2023-12-31", 300.0)],
     _ANNUAL_ASSETS, _ANNUAL_ROA, "Return on Equity: 20.0% (period: 2024-12-31); prior: 20.0% (2023-12-31)"),
    # Assets missing at the report date: ROA's point predates net income and abstains; ROE stays.
    ("10-K", _ANNUAL_NI, [("2025-12-31", 500.0), ("2024-12-31", 400.0)],
     [("2024-12-31", 1900.0), ("2023-12-31", 1800.0)],
     f"{_PARENT} equity, not annualized: 20.0% (prior at 2024-12-31: 20.0%)",
     "Return on Equity: 20.0% (period: 2025-12-31); prior: 20.0% (2024-12-31)"),
    ("10-Q", _Q2_NI, [("2026-06-30", 520.0), ("2026-03-31", 500.0), ("2025-12-31", 450.0)], _Q2_ASSETS,
     f"{_PARENT} equity, not annualized: 2.3% (prior at 2026-03-31: 1.5%); {_Q2_ROA}",
     "Return on Equity: 2.3% (period: 2026-06-30); prior: 1.5% (2026-03-31)"),
    ("10-Q", _Q2_NI, [("2026-06-30", -20.0), ("2026-03-31", 500.0), ("2025-12-31", 450.0)], _Q2_ASSETS,
     _Q2_ROA, "Return on Equity: 1.5% (period: 2026-03-31); basis:"),
], ids=["10k-aligned", "10k-negative-equity", "10k-zero-equity", "10k-equity-missing", "10k-assets-missing",
        "10q-aligned", "10q-negative-equity"])
def test_return_ratio_not_at_net_income_period_abstains(form, net_income, equity, assets, line, grounding_roe):
    """A ratio whose current point predates net income's (the derivation skipped a non-positive or
    missing denominator) would render undated as this period's: that clause abstains. The aligned
    sibling ratio still renders, aligned inputs keep main's bytes, and the grounding is untouched."""
    from app.services.edgar.xbrl_service import edgar_xbrl_service
    from app.services.openai_service import openai_service
    from app.services.summary_sections import render_sections, sections_to_markdown

    def point(period, value, start=None):
        return {"period": period, "value": value, "currency": "USD", "form": form,
                **({"period_start": start, "raw_tag": "us-gaap:NetIncomeLoss"} if start else {})}

    metrics = edgar_xbrl_service.extract_standardized_metrics({
        "net_income": [point(p, v, s) for p, s, v in net_income],
        "shareholders_equity": [point(p, v) for p, v in equity],
        "total_assets": [point(p, v) for p, v in assets],
    })
    sections = {}
    openai_service._apply_structured_fallbacks(sections, {}, metrics)
    rendered = sections["value_drivers"]["returns_on_capital"]
    assert rendered == line[0].upper() + line[1:] + "."
    assert rendered in sections_to_markdown(render_sections({"schema_version": 2, "sections": sections}))
    # Model-facing bytes: the grounding keeps main's ROE line, which dates that point itself.
    assert f"- {grounding_roe}" in build_xbrl_narrative_section(metrics)
