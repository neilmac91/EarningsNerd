"""Unit tests for the summary prompt's XBRL grounding block (roadmap 2.6 Phase B).

`build_xbrl_narrative_section` is the single point that decides which SEC-verified figures the
summary *narrative* may cite. Phase B adds the full cash-flow statement (investing/financing) and
working-capital lines to that whitelist. These tests exercise the real builder/formatter offline
(no AI call) and prove (a) the new metrics surface with correct labels/formatting, (b) the ratio
format renders a dimensionless multiple, and (c) the block is byte-for-byte unchanged for filings
that carry only the legacy metrics (so the eval baseline / flag-off behaviour can't regress).
"""

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

    def test_prior_period_yoy_appended_when_present(self):
        section = build_xbrl_narrative_section({
            "revenue": {
                "current": {"value": 391.0, "period": "2024-09-28"},
                "prior": {"value": 383.0, "period": "2023-09-30"},
            }
        })
        assert "Revenue: $391 (period: 2024-09-28); prior: $383 (2023-09-30)" in section

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
