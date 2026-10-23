"""Unit tests for Trace-to-Source provenance enrichment."""

import copy
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote

import pytest

from app.services import provenance_service as prov


def _filing(document_url="https://www.sec.gov/Archives/edgar/data/320193/000.../aapl.htm",
            sec_url="https://www.sec.gov/Archives/edgar/data/320193/000.../",
            critical_excerpt=None, markdown_content=None, filing_id=42):
    cache = None
    if critical_excerpt is not None or markdown_content is not None:
        cache = SimpleNamespace(
            filing_id=filing_id,
            critical_excerpt=critical_excerpt,
            markdown_content=markdown_content,
        )
    return SimpleNamespace(id=filing_id, document_url=document_url, sec_url=sec_url, content_cache=cache)


# The tag the extractor records for Apple's total net sales (``edgar/instance/concepts.py`` candidates, ``raw_tag``).
REVENUE_TAG = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"


class TestExtractQuotedSpan:
    def test_pulls_straight_quoted_span(self):
        assert (
            prov.extract_quoted_span('Item 1A: "Supply chain constraints persisted through Q3."')
            == "Supply chain constraints persisted through Q3."
        )

    def test_pulls_curly_quoted_span(self):
        assert prov.extract_quoted_span("Item 1A: “Revenue is concentrated in two customers.”") == (
            "Revenue is concentrated in two customers."
        )

    def test_falls_back_to_whole_string(self):
        assert prov.extract_quoted_span("See Item 1A of the 10-K") == "See Item 1A of the 10-K"

    def test_empty(self):
        assert prov.extract_quoted_span("") == ""


class TestNormalizeForMatch:
    """T5.4 typography folds: filings typeset curly quotes/apostrophes and en/em dashes; model
    output types ASCII. One normalizer serves every verbatim check in the product (T4 evidence,
    copilot citations, the forward-quote gate), so the folds are pinned here once."""

    def test_folds_curly_apostrophes_and_quotes(self):
        assert prov.normalize_for_match("the company’s “record” results") == (
            prov.normalize_for_match("the company's \"record\" results")
        )

    def test_folds_dashes(self):
        assert prov.normalize_for_match("authorization — $110 billion – net") == (
            "authorization - $110 billion - net"
        )

    def test_folds_nonbreaking_hyphen_and_minus(self):
        # Gemini on #623: filings hyphenate with U+2011 and sign negatives with U+2212.
        assert prov.normalize_for_match("year‑over‑year decline of −4.2%") == (
            "year-over-year decline of -4.2%"
        )

    def test_deletes_invisible_typography(self):
        # Soft hyphens / zero-width chars are HTML hyphenation artifacts: the logical text (and any
        # model output) simply doesn't contain them, so they are removed, not folded.
        assert prov.normalize_for_match(
            "restruc\u00adturing\u200b charge\ufeff and\u200c growth\u200d"
        ) == "restructuring charge and growth"

    def test_lowercase_and_whitespace_collapse_unchanged(self):
        # The pre-T5.4 behavior this normalizer always had must be byte-identical.
        assert prov.normalize_for_match("  Supply\nChain\t CONSTRAINTS ") == "supply chain constraints"

    def test_typography_drift_now_verifies_in_source(self):
        # End-to-end through verify_excerpt_in_text: curly source, straight excerpt.
        source = prov.normalize_for_match("Management noted the company’s backlog — $12 billion.")
        assert prov.verify_excerpt_in_text('"the company\'s backlog - $12 billion"', source) is True


class TestVerifyExcerptInText:
    SOURCE = "ITEM 1A. RISK FACTORS\nSupply chain constraints persisted through Q3 of fiscal 2024."

    def _norm(self):
        return prov.normalize_for_match(self.SOURCE)

    def test_verifies_quoted_excerpt_case_and_whitespace_insensitive(self):
        evidence = 'Item 1A: "Supply   chain constraints persisted through Q3"'
        assert prov.verify_excerpt_in_text(evidence, self._norm()) is True

    def test_unverified_when_not_present(self):
        assert prov.verify_excerpt_in_text('"A totally fabricated sentence not in the filing"', self._norm()) is False

    def test_unverified_when_too_short(self):
        # Below the min-length gate -> never claimed as verified even if technically a substring.
        assert prov.verify_excerpt_in_text('"Q3"', self._norm()) is False

    def test_unverified_without_source_text(self):
        assert prov.verify_excerpt_in_text('"Supply chain constraints persisted through Q3"', None) is False

    def test_non_string_evidence_is_safe(self):
        # Legacy/malformed records may carry a non-string excerpt; must not raise.
        assert prov.verify_excerpt_in_text(["not", "a", "string"], self._norm()) is False


class TestVerifyWholeExcerptInText:
    """Surfaces that DISPLAY the whole excerpt as filing text (Copilot citations, forward quotes)
    verify all of it: only a quote pair wrapping the entire value is stripped, never an inner span."""

    SOURCE = prov.normalize_for_match(
        "ITEM 1A. RISK FACTORS\nSupply chain constraints persisted through Q3 of fiscal 2024. "
        "The Company’s “Tier 1” suppliers remain concentrated in Asia."
    )

    @pytest.mark.parametrize("excerpt", [
        "Supply chain constraints persisted through Q3",
        '"Supply chain constraints persisted through Q3"',
        "“Supply chain constraints persisted through Q3”",
        "  SUPPLY chain   constraints\npersisted through Q3 ",
        "The Company's \"Tier 1\" suppliers remain concentrated",
        "constraints persisted th",  # exactly the floor
    ])
    def test_whole_excerpt_contiguous_in_source_verifies(self, excerpt):
        assert prov.verify_whole_excerpt_in_text(excerpt, self.SOURCE) is True

    @pytest.mark.parametrize("excerpt", [
        '"Supply chain constraints persisted through Q3" and ended in Q4',
        '""Supply chain constraints persisted through Q3""',  # one wrapping pair only
        "constraints persisted t",  # contiguous, one character under the floor
        "",
        ["not", "a", "string"],
    ])
    def test_anything_else_is_unverified(self, excerpt):
        assert prov.verify_whole_excerpt_in_text(excerpt, self.SOURCE) is False

    def test_inner_quoted_span_never_stands_in_for_the_excerpt(self):
        evidence = 'Item 1A: "Supply   chain constraints persisted through Q3"'
        # Summary evidence is prefix-tolerant by design; the whole-excerpt verifier is not.
        assert prov.verify_excerpt_in_text(evidence, self.SOURCE) is True
        assert prov.verify_whole_excerpt_in_text(evidence, self.SOURCE) is False

    def test_floor_is_the_shared_constant_and_source_is_required(self):
        assert len(prov.normalize_for_match("constraints persisted th")) == prov._MIN_VERIFIABLE_LEN
        assert prov.verify_whole_excerpt_in_text("Supply chain constraints persisted through Q3", None) is False
        assert prov.verify_whole_excerpt_in_text("Supply chain constraints persisted through Q3", "") is False


class TestBuildTextFragmentUrl:
    def test_appends_encoded_fragment(self):
        url = prov.build_text_fragment_url(
            "https://sec.gov/x.htm", 'Item 1A: "Supply chain constraints persisted through Q3."'
        )
        assert url.startswith("https://sec.gov/x.htm#:~:text=")
        fragment = url.split("#:~:text=", 1)[1]
        # Round-trips back to a leading snippet of the quoted span.
        assert unquote(fragment).startswith("Supply chain constraints")

    def test_limits_fragment_word_count(self):
        long = '"' + " ".join(f"word{i}" for i in range(40)) + '"'
        url = prov.build_text_fragment_url("https://sec.gov/x.htm", long)
        assert unquote(url.split("#:~:text=", 1)[1]).split(" ").__len__() <= prov._FRAGMENT_MAX_WORDS

    def test_no_base_url(self):
        assert prov.build_text_fragment_url("", "anything") == ""


class TestEnrichRawSummary:
    def _raw(self):
        return {
            "sections": {
                "risk_factors": [
                    {
                        "summary": "Supply concentration",
                        "supporting_evidence": "Supply chain constraints persisted through Q3",
                        "source_section_ref": "Item 1A. Risk Factors",
                    }
                ],
                "executive_snapshot": "unchanged",
            }
        }

    def test_enriches_and_does_not_mutate_input(self):
        raw = self._raw()
        filing = _filing(critical_excerpt="Supply chain constraints persisted through Q3 of 2024.")
        out = prov.enrich_raw_summary(raw, filing, summary_filing_id=filing.id)

        risk = out["sections"]["risk_factors"][0]
        assert risk["source_verified"] is True
        assert "#:~:text=" in risk["source_url"]
        # Original input untouched.
        assert "source_url" not in raw["sections"]["risk_factors"][0]
        # Other sections preserved.
        assert out["sections"]["executive_snapshot"] == "unchanged"

    def test_tolerates_missing_sections(self):
        assert prov.enrich_raw_summary({"foo": "bar"}, _filing()) == {"foo": "bar"}
        assert prov.enrich_raw_summary(None, _filing()) is None
        filing = _filing()
        empty = prov.enrich_raw_summary({"sections": {}}, filing, summary_filing_id=filing.id)
        assert empty["sections"]["risk_factors"] == []
        assert empty["sections"][prov.RISK_PROJECTION_KEY]["verified_count"] == 0

    def test_uses_markdown_when_no_critical_excerpt(self):
        raw = self._raw()
        filing = _filing(markdown_content="...Supply chain constraints persisted through Q3...")
        out = prov.enrich_raw_summary(raw, filing, summary_filing_id=filing.id)
        assert out["sections"]["risk_factors"][0]["source_verified"] is True

    def test_enriches_v2_sections_via_schema_version(self):
        """v2 rows (schema_version=2) carry `risks` / `results_that_matter`; enrichment must add the
        same per-row provenance (source_url/source_verified/xbrl_concept) the MetricSourceLink chips
        render. A v1-keyed guard silently no-ops on v2 and nothing else measures it — this is the
        structural gate for that regression (repo rule 12)."""
        raw = {
            "schema_version": 2,
            "sections": {
                "results_that_matter": {
                    "source_section_ref": "Item 8. Financial Statements",
                    "table": [{"metric": "Total Revenue", "current_period": "$391.0B"}],
                },
                "risks": [{
                    "summary": "Supply concentration",
                    "supporting_evidence": "Supply chain constraints persisted through Q3",
                    "source_section_ref": "Item 1A. Risk Factors",
                }],
            },
        }
        filing = _filing(critical_excerpt="Supply chain constraints persisted through Q3 of 2024.")
        xbrl = {"revenue": {"current": {"value": 391035000000.0}}}
        out = prov.enrich_raw_summary(
            raw, filing, xbrl_standardized=xbrl, summary_filing_id=filing.id
        )

        row = out["sections"]["results_that_matter"]["table"][0]
        assert row["source_verified"] is True and row["xbrl_concept"] == "Revenue"
        assert row["source_url"]  # MetricSourceLink chip target present
        assert out["sections"]["risks"][0]["source_verified"] is True
        # Input not mutated.
        assert "source_url" not in raw["sections"]["results_that_matter"]["table"][0]


class TestEnrichSummaryProvenance:
    def test_shapes_response_and_enriches_both_paths(self):
        risk = {
            "summary": "r",
            "supporting_evidence": "Supply chain constraints persisted through Q3",
            "source_section_ref": "Item 1A. Risk Factors",
        }
        fh = {
            "source_section_ref": "Item 8. Financial Statements",
            "table": [{"metric": "Total Revenue", "current_period": "$391.0B"}],
        }
        summary = SimpleNamespace(
            id=7,
            filing_id=42,
            business_overview="bo",
            financial_highlights=copy.deepcopy(fh),
            risk_factors=[copy.deepcopy(risk)],
            management_discussion="md",
            key_changes="kc",
            raw_summary={
                "sections": {
                    "risk_factors": [copy.deepcopy(risk)],
                    "financial_highlights": copy.deepcopy(fh),
                }
            },
        )
        filing = _filing(critical_excerpt="Supply chain constraints persisted through Q3 of 2024.")
        xbrl = {"revenue": {"current": {"value": 391035000000.0}}}
        out = prov.enrich_summary_provenance(summary, filing, xbrl)

        assert out["id"] == 7 and out["filing_id"] == 42
        # Risk-factor provenance (verified against cached text).
        assert out["risk_factors"][0]["source_verified"] is True
        assert out["raw_summary"]["sections"]["risk_factors"][0]["source_verified"] is True
        # Metric provenance (verified against SEC XBRL) on both surfaces.
        assert out["financial_highlights"]["table"][0]["source_verified"] is True
        assert out["financial_highlights"]["table"][0]["xbrl_concept"] == "Revenue"
        assert out["raw_summary"]["sections"]["financial_highlights"]["table"][0]["source_verified"] is True

    def test_no_filing_is_safe(self):
        summary = SimpleNamespace(
            id=1, filing_id=1, business_overview=None, financial_highlights=None,
            risk_factors=None, management_discussion=None, key_changes=None, raw_summary=None,
        )
        out = prov.enrich_summary_provenance(summary, None)
        assert out["risk_factors"] is None and out["raw_summary"] is None
        assert out["financial_highlights"] is None


class TestMapMetricToXbrlKey:
    # The substring mapper the bank guards and the no-total-bank revenue drop read (ai/bank_guards.py). The figure check
    # reads whole labels instead (source_metric_key; TestFigureCheck holds its aliases).
    def test_maps_common_names(self):
        assert prov.map_metric_to_xbrl_key("Total Revenue")[0] == "revenue"
        assert prov.map_metric_to_xbrl_key("Net sales")[0] == "revenue"
        assert prov.map_metric_to_xbrl_key("Total assets")[0] == "total_assets"
        assert prov.map_metric_to_xbrl_key("Free cash flow")[0] == "free_cash_flow"
        assert prov.map_metric_to_xbrl_key("Cash and cash equivalents")[0] == "cash_and_equivalents"

    def test_net_income_not_confused_with_revenue(self):
        assert prov.map_metric_to_xbrl_key("Net income")[0] == "net_income"
        assert prov.map_metric_to_xbrl_key("Net earnings")[0] == "net_income"

    def test_excludes_eps_and_margins(self):
        # Small/derived numbers are not value-verifiable, so they are intentionally unmapped.
        assert prov.map_metric_to_xbrl_key("Diluted EPS") is None
        assert prov.map_metric_to_xbrl_key("Gross margin") is None
        assert prov.map_metric_to_xbrl_key("Operating margin") is None

    def test_unmapped_and_non_string(self):
        assert prov.map_metric_to_xbrl_key("Backlog") is None
        assert prov.map_metric_to_xbrl_key(None) is None
        assert prov.map_metric_to_xbrl_key(123) is None


class TestBuildMetricSource:
    XBRL = {
        # A shown prior is checked too, so the revenue row's prior has its filed fact (Apple FY2023, 383,285).
        "revenue": {"current": {"period": "2024-09-28", "value": 391035000000.0, "form": "10-K", "raw_tag": REVENUE_TAG},
                    "prior": {"period": "2023-09-30", "value": 383285000000.0, "form": "10-K", "raw_tag": REVENUE_TAG}},
        "net_income": {"current": {"value": 93736000000.0}},
        "total_assets": {"current": {"value": 364980000000.0}},
    }

    def test_verified_when_xbrl_value_appears(self):
        row = {"metric": "Total Revenue", "current_period": "$391.0B", "prior_period": "$383.3B"}
        out = prov.build_metric_source(row, _filing(), self.XBRL, "Item 8. Financial Statements")
        assert out["source_verified"] is True
        assert out["source_checkable"] is True
        assert out["xbrl_concept"] == "Revenue"
        assert out["source_section_ref"] == "Item 8. Financial Statements"
        assert out["source_url"].endswith("aapl.htm")

    def test_unverified_when_value_does_not_match(self):
        row = {"metric": "Revenue", "current_period": "$999.9B"}
        out = prov.build_metric_source(row, _filing(), self.XBRL, None)
        assert out["source_verified"] is False
        # Checked and not matched: this row counts against the tally's matched share.
        assert out["source_checkable"] is True
        assert out["xbrl_concept"] is None
        assert out["source_url"].endswith("aapl.htm")  # still linked, just not "verified"

    def test_unmapped_metric_gets_link_only(self):
        row = {"metric": "Diluted EPS", "current_period": "$6.13"}
        out = prov.build_metric_source(row, _filing(), self.XBRL, None)
        assert out["source_verified"] is False
        # Never checked (per-share figures are unmapped): no tally may count it as a failed match.
        assert out["source_checkable"] is False
        assert out["source_url"].endswith("aapl.htm")

    def test_no_xbrl_data(self):
        row = {"metric": "Total Revenue", "current_period": "$391.0B"}
        out = prov.build_metric_source(row, _filing(), None, None)
        assert out["source_verified"] is False
        assert out["source_checkable"] is False

    def test_small_value_not_verified(self):
        # Below the million threshold the rendering match is ambiguous -> never claimed verified.
        xbrl = {"net_income": {"current": {"value": 1234.0}}}
        row = {"metric": "Net income", "current_period": "1,234"}
        out = prov.build_metric_source(row, _filing(), xbrl, None)
        assert out["source_verified"] is False
        assert out["source_checkable"] is False


def _annual(value, end, start):
    return {"value": value, "period": end, "period_start": start, "form": "10-K", "currency": "USD"}


# Apple's FY2025 10-K (accession 0000320193-25-000079): the filed pairs, in USD.
APPLE = {
    "reporting_currency": "USD",
    "revenue": {"current": {**_annual(416_161e6, "2025-09-27", "2024-09-29"), "raw_tag": REVENUE_TAG},
                "prior": {**_annual(391_035e6, "2024-09-28", "2023-10-01"), "raw_tag": REVENUE_TAG}},
    "operating_income": {"current": _annual(133_050e6, "2025-09-27", "2024-09-29"),
                         "prior": _annual(123_216e6, "2024-09-28", "2023-10-01")},
    "free_cash_flow": {"current": _annual(98_767e6, "2025-09-27", "2024-09-29")},
}


class TestFigureCheck:
    """The figure check reads a row's whole label and its numbers' own scale and precision (2026-10-22)."""

    def _check(self, metric, current, prior="—", xbrl=APPLE):
        return prov.build_metric_source(
            {"metric": metric, "current_period": current, "prior_period": prior}, _filing(), xbrl, None,
        )

    @pytest.mark.parametrize("shown", ["$416.2B", "$416.16B", "$416,161M", "$416,161,000,000"])
    def test_any_rounding_of_the_filed_value_matches(self, shown):
        out = self._check("Total net sales", shown)
        assert out["source_verified"] is True
        assert out["xbrl_concept"] == "Revenue"

    @pytest.mark.parametrize("shown", ["$416.2M", "$416.9B", "$4,416.2B", "$41.6B"])
    def test_a_wrong_scale_or_digit_does_not_match(self, shown):
        # The substring check this replaced read "$416.2M", "$416.9B" and "$4,416.2B" as matched.
        out = self._check("Total net sales", shown)
        assert out["source_checkable"] is True
        assert out["source_verified"] is False
        assert out["source_mismatched"] == ["current_period"]

    def test_the_prior_period_is_checked_too(self):
        out = self._check("Total net sales", "$416.2B", "$383.3B")
        assert out["source_verified"] is False
        assert out["source_mismatched"] == ["prior_period"]
        assert self._check("Total net sales", "$416.2B", "$391.0B")["source_verified"] is True

    @pytest.mark.parametrize("prior", [
        _annual(94_930e6, "2024-09-28", "2024-06-30"),  # a quarter beside an annual current
        None,  # no prior filed at all
    ])
    def test_a_row_whose_shown_prior_cannot_be_compared_is_not_checked(self, prior):
        # "Matches filing" covers every figure a row shows (Codex on #1530): a prior the filing's data holds no
        # comparable period for leaves the row unchecked, never matched on its current year alone.
        revenue = {"current": APPLE["revenue"]["current"], **({"prior": prior} if prior else {})}
        out = self._check("Total net sales", "$416.2B", "$391.0B", {**APPLE, "revenue": revenue})
        assert out["source_checkable"] is False
        assert out["source_verified"] is False
        assert "source_filed" not in out and "source_mismatched" not in out

    @pytest.mark.parametrize("prior", ["$383.3B (FY2024)", "~$383.3B", "$383.3B*", "383.3B USD", "FY24: $383.3B"])
    def test_a_prior_that_states_a_figure_it_cannot_read_leaves_the_row_unchecked(self, prior):
        # A prior written around its number is still shown: the row cannot match on its current year alone.
        out = self._check("Total net sales", "$416.2B", prior)
        assert out["source_checkable"] is False and out["source_verified"] is False

    @pytest.mark.parametrize("prior", ["—", "n/a", "Not disclosed", "N/A (new in 2025)", "", None])
    def test_a_prior_cell_without_a_figure_is_not_a_shown_prior(self, prior):
        assert self._check("Total net sales", "$416.2B", prior)["source_verified"] is True

    def test_a_stored_number_is_never_checked_or_replaced(self):
        # A JSON number states no scale: a correct 416161000000 must not read as a figure to correct.
        row = {"metric": "Total net sales", "current_period": 416_161_000_000, "prior_period": "$391.0B"}
        out = prov.build_metric_source(row, _filing(), APPLE, None)
        assert out["source_checkable"] is False and "source_mismatched" not in out

    # A 10-Q's balance sheet sets the quarter-end beside the last fiscal year-end (Apple's Q3 FY25 10-Q). The
    # standardized prior is the series' next period, which the same-quarter rule refuses (Q4 against Q3).
    QUARTER = {"reporting_currency": "USD", "total_assets": {
        "current": {"period": "2025-06-28", "value": 331_495e6, "form": "10-Q", "fiscal_period": "Q3", "currency": "USD"},
        "prior": {"period": "2024-09-28", "value": 364_980e6, "form": "10-Q", "fiscal_period": "Q4", "currency": "USD"},
        "series": [
            {"period": "2025-06-28", "value": 331_495e6, "form": "10-Q", "fiscal_period": "Q3", "currency": "USD"},
            {"period": "2025-03-29", "value": 331_233e6, "form": "10-Q", "fiscal_period": "Q2", "currency": "USD"},
            {"period": "2024-09-28", "value": 364_980e6, "form": "10-Q", "fiscal_period": "Q4", "currency": "USD"},
        ],
    }}

    def test_a_balance_sheet_prior_is_checked_against_the_filings_own_earlier_instants(self):
        out = self._check("Total assets", "$331.5B", "$365.0B", self.QUARTER)
        assert out["source_verified"] is True
        assert out["source_filed"] == {"current_period": "$331,495 million", "prior_period": "$364,980 million"}

    def test_a_wrong_quarter_end_is_still_replaced_beside_a_prior_the_filing_states(self):
        out = self._check("Total assets", "$313.5B", "$365.0B", self.QUARTER)
        assert out["source_mismatched"] == ["current_period"]

    def test_a_balance_sheet_prior_the_filing_states_nowhere_leaves_the_row_unchecked(self):
        # The summary may mean another date, so nothing is matched and nothing is replaced.
        out = self._check("Total assets", "$313.5B", "$356.0B", self.QUARTER)
        assert out["source_checkable"] is False and "source_mismatched" not in out

    def test_a_prior_that_repeats_the_current_quarter_end_is_not_read_against_it(self):
        # The series holds the current instant too: a prior the summary copied from the current year is no
        # earlier date the filing states.
        out = self._check("Total assets", "$331.5B", "$331.5B", self.QUARTER)
        assert out["source_checkable"] is False and out["source_verified"] is False

    @pytest.mark.parametrize("field, other", [("currency", "EUR"), ("raw_tag", "AssetsNet"), ("form", "10-K")])
    def test_an_earlier_instant_of_another_currency_tag_or_form_is_not_the_concepts(self, field, other):
        current = {**self.QUARTER["total_assets"]["current"], "raw_tag": "Assets"}
        earlier = {"period": "2024-09-28", "value": 364_980e6, "form": "10-Q", "currency": "USD", "raw_tag": "Assets",
                   field: other}
        quarter = {"reporting_currency": "USD", "total_assets": {
            "current": current, "prior": {**earlier, "fiscal_period": "Q4"}, "series": [current, earlier]}}
        assert self._check("Total assets", "$331.5B", "$365.0B", quarter)["source_checkable"] is False

    # A concept's extraction candidates differ in scope (edgar/instance/concepts.py), and the extractor records the
    # winner as raw_tag. A figure is replaced only by the line its label names; one that differs from another line is
    # not shown wrong, and the row is left unchecked (the expert review of #1530).
    OUTCOMES = {"matched": (True, True, None), "replaced": (False, True, ["current_period"]), "unchecked": (False, False, None)}

    @pytest.mark.parametrize("metric, key, tag, shown, outcome", [
        # "Long-term debt" names no single scope: noncurrent, or with its current maturities.
        ("Long-term debt", "long_term_debt", "us-gaap:LongTermDebtNoncurrent", "$12.0B", "unchecked"),
        ("Long-term debt", "long_term_debt", "us-gaap:LongTermDebt", "$12.0B", "unchecked"),
        ("Long-term debt", "long_term_debt", "us-gaap:LongTermDebtNoncurrent", "$10.0B", "matched"),
        # A cash total with restricted cash or short-term investments is another line.
        ("Cash and cash equivalents", "cash_and_equivalents",
         "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "$8.0B", "unchecked"),
        ("Cash and cash equivalents", "cash_and_equivalents", "us-gaap:CashCashEquivalentsAndShortTermInvestments", "$8.0B", "unchecked"),
        ("Cash and cash equivalents", "cash_and_equivalents",
         "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "$10.0B", "matched"),
        ("Cash and cash equivalents", "cash_and_equivalents", "us-gaap:CashAndCashEquivalentsAtCarryingValue", "$8.0B", "replaced"),
        ("Cash & equivalents", "cash_and_equivalents", None, "$8.0B", "unchecked"),
        # Equity with noncontrolling interests is another line; the instance extractor records no equity tag.
        ("Shareholders' equity", "shareholders_equity",
         "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "$8.0B", "unchecked"),
        ("Shareholders' equity", "shareholders_equity", None, "$8.0B", "unchecked"),
        ("Shareholders' equity", "shareholders_equity", "us-gaap:StockholdersEquity", "$8.0B", "replaced"),
    ])
    def test_a_balance_sheet_figure_is_replaced_only_by_the_line_its_label_names(self, metric, key, tag, shown, outcome):
        fact = {"period": "2025-09-27", "value": 10_000e6, "form": "10-K", "currency": "USD", **({"raw_tag": tag} if tag else {})}
        out = self._check(metric, shown, "—", {"reporting_currency": "USD", key: {"current": fact}})
        assert (out["source_verified"], out["source_checkable"], out.get("source_mismatched")) == self.OUTCOMES[outcome]

    @pytest.mark.parametrize("metric, key, tag, outcome", [
        # "Revenues" is the top line, which may add other income to net sales (Walmart's membership fees).
        ("Net sales", "revenue", "us-gaap:Revenues", "unchecked"),
        ("Total revenues", "revenue", "us-gaap:Revenues", "replaced"),
        ("Net sales", "revenue", REVENUE_TAG, "replaced"),
        ("Revenue", "revenue", None, "unchecked"),  # the companyfacts path records no revenue tag
        ("Net income", "net_income", "us-gaap:ProfitLoss", "unchecked"),  # adds noncontrolling interests
        ("Net income", "net_income", "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic", "unchecked"),
        ("Net income", "net_income", "us-gaap:NetIncomeLoss", "replaced"),
        ("Operating cash flow", "operating_cash_flow",
         "us-gaap:NetCashProvidedByUsedInOperatingActivitiesContinuingOperations", "unchecked"),
        ("Operating cash flow", "operating_cash_flow", "us-gaap:NetCashProvidedByUsedInOperatingActivities", "replaced"),
        ("Operating income", "operating_income", None, "replaced"),  # one scope across its candidates
    ])
    def test_a_period_figure_is_replaced_only_by_the_line_its_label_names(self, metric, key, tag, outcome):
        fact = {**_annual(10_000e6, "2025-09-27", "2024-09-29"), **({"raw_tag": tag} if tag else {})}
        out = self._check(metric, "$8.0B", "—", {"reporting_currency": "USD", key: {"current": fact}})
        assert (out["source_verified"], out["source_checkable"], out.get("source_mismatched")) == self.OUTCOMES[outcome]

    def test_a_cash_figure_of_another_line_is_shown_as_the_summary_wrote_it(self):
        restricted = {"period": "2025-09-27", "value": 10_000e6, "form": "10-K", "currency": "USD",
                      "raw_tag": "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"}
        fh = {"table": [{"metric": "Cash and cash equivalents", "current_period": "$8.0B", "commentary": "Cash fell to $8.0B."}]}
        row = prov.enrich_financial_highlights(fh, _filing(), {"reporting_currency": "USD", "cash_and_equivalents": {"current": restricted}})["table"][0]
        assert (row["current_period"], row["commentary"], row["source_checkable"]) == ("$8.0B", "Cash fell to $8.0B.", False)
        assert "source_replaced" not in row and "commentary_withheld" not in row

    def test_a_durations_prior_is_never_read_from_the_series(self):
        # Only instants: a P&L line's series mixes durations under one period end.
        quarter = {**APPLE, "revenue": {
            "current": {**APPLE["revenue"]["current"], "fiscal_period": "Q3"},
            "prior": {**APPLE["revenue"]["prior"], "fiscal_period": "Q2"},
            "series": [APPLE["revenue"]["current"], APPLE["revenue"]["prior"]]}}
        assert self._check("Total net sales", "$416.2B", "$391.0B", quarter)["source_checkable"] is False

    YEN = {"reporting_currency": "JPY", "revenue": {
        "current": {**_annual(45_095_325e6, "2025-03-31", "2024-04-01"), "currency": "JPY", "raw_tag": "ifrs-full:Revenue"},
        "prior": {**_annual(37_154_298e6, "2024-03-31", "2023-04-01"), "currency": "JPY", "raw_tag": "ifrs-full:Revenue"}}}

    @pytest.mark.parametrize("filed, shown, verified, checkable", [
        ("USD", "¥416.2B", False, True),  # a bare yen is not a dollar: replaced by the filed figure
        ("EUR", "¥416.2B", False, True),
        ("USD", "€416.2B", False, True),
        (None, "€416.2B", False, False),  # the filing's data names no currency: neither matched nor replaced
        (None, "¥416.2B", False, False),
        (None, "$416.2B", True, True),  # the dollar the backend assumes then
        (None, "416.2B", True, True),
    ])
    def test_a_display_is_checked_in_the_filings_currency(self, filed, shown, verified, checkable):
        current = {**APPLE["revenue"]["current"], "currency": filed}
        xbrl = {"revenue": {"current": current}, **({"reporting_currency": filed} if filed else {})}
        out = self._check("Total net sales", shown, "—", xbrl)
        assert (out["source_verified"], out["source_checkable"]) == (verified, checkable)

    def test_the_reporting_currency_stands_in_for_a_fact_that_names_none(self):
        # companyfacts facts carry no currency of their own.
        xbrl = {"reporting_currency": "EUR", "revenue": {"current": {**APPLE["revenue"]["current"], "currency": None}}}
        assert self._check("Total net sales", "€416.2B", "—", xbrl)["source_verified"] is True
        assert self._check("Total net sales", "$416.2B", "—", xbrl)["source_mismatched"] == ["current_period"]

    def test_a_row_that_shows_no_prior_is_checked_on_its_current_year(self):
        out = self._check("Total net sales", "$416.2B", "—", {**APPLE, "revenue": {"current": APPLE["revenue"]["current"]}})
        assert out["source_verified"] is True
        assert set(out["source_filed"]) == {"current_period"}

    def test_names_each_compared_period_as_filed(self):
        out = self._check("Total net sales", "$416.2B", "$391.0B")
        assert out["source_filed"] == {"current_period": "$416,161 million", "prior_period": "$391,035 million"}

    @pytest.mark.parametrize("metric", ["Services net sales", "Products net sales", "Revenue growth"])
    def test_a_segment_or_qualified_line_is_never_checked(self, metric):
        # A substring map compared "Services net sales" with total revenue and read a correct figure as a miss.
        out = self._check(metric, "$109,158M", "$96,169M")
        assert out["source_checkable"] is False
        assert out["source_verified"] is False

    def test_a_computed_figure_is_never_checked(self):
        assert self._check("Free cash flow", "$98.8B")["source_checkable"] is False

    def test_a_display_in_another_currency_does_not_match(self):
        out = self._check("Total net sales", "CNY 416.2B")
        assert out["source_verified"] is False

    def test_a_bare_yen_sign_is_checked_by_its_number(self):
        # "¥" names no single currency (JPY or CNY), so it is no evidence against a JPY fact: a correct
        # figure must not read as one to replace, and a wrong one is still caught.
        assert self._check("Total net sales", "¥45.1T", "¥37.2T", self.YEN)["source_verified"] is True
        assert self._check("Total net sales", "¥45.9T", "¥37.2T", self.YEN)["source_mismatched"] == ["current_period"]

    # The plain aliases keep the statement lines main checked by substring (the strict mapper owns none of these), each
    # on its own concept; a dropped or mistyped alias leaves its line silently "Linked, not checked".
    @pytest.mark.parametrize("metric, key", [
        ("Net revenue", "revenue"), ("Net revenues", "revenue"),
        ("Income from operations", "operating_income"),
        ("Total assets", "total_assets"),
        ("Cash and cash equivalents", "cash_and_equivalents"), ("Cash & cash equivalents", "cash_and_equivalents"),
        ("Cash and equivalents", "cash_and_equivalents"),
        ("Operating cash flow", "operating_cash_flow"), ("Cash flow from operations", "operating_cash_flow"),
        ("Cash from operations", "operating_cash_flow"),
        ("Net cash provided by operating activities", "operating_cash_flow"),
        ("Shareholders’ equity", "shareholders_equity"), ("Stockholders' equity", "shareholders_equity"),
        ("Total shareholders' equity", "shareholders_equity"), ("Total stockholders’ equity", "shareholders_equity"),
        ("Long-term debt", "long_term_debt"), ("Long term debt", "long_term_debt"),
        ("Cash & Equivalents", "cash_and_equivalents"),
        ("Net Operating Revenues", "revenue"), ("Total net revenue", "revenue"), ("Total net revenues", "revenue"),
        ("Gross profit (loss)", "gross_profit"), ("Total gross profit", "gross_profit"),
        ("Operating income (loss)", "operating_income"), ("Operating income/(loss)", "operating_income"),
    ])
    def test_each_plain_alias_is_checked_against_its_own_concept(self, metric, key):
        assert prov.source_metric_key(metric) == key
        assert prov.source_metric_key(f"  {metric.upper()} ") == key  # case and spacing are not the label
        filed = {"current": _annual(123_456e6, "2025-09-27", "2024-09-29"), "prior": _annual(98_765e6, "2024-09-28", "2023-10-01")}
        out = self._check(metric, "$123.5B", "$98.8B", {"reporting_currency": "USD", key: filed})
        assert out["source_verified"] is True

    def test_a_figure_that_is_not_a_number_is_not_checkable(self):
        assert self._check("Total net sales", "Not disclosed")["source_checkable"] is False


class TestFiledFigureSwap:
    """A checkable figure that differs from the filed one is replaced by it (the founder's call, 2026-10-22)."""

    def _enrich(self, *rows, normalized=None):
        fh = {"source_section_ref": "Item 8. Financial Statements", "table": [dict(r) for r in rows]}
        if normalized is not None:
            fh["normalized"] = normalized
        return prov.enrich_financial_highlights(fh, _filing(), APPLE)

    def test_the_filed_figure_replaces_the_summarys(self):
        out = self._enrich({"metric": "Operating income", "current_period": "$132,100M", "prior_period": "$123,216M",
                            "change_display": "+7.2%", "change_direction": "up", "change_tone": "gain"})
        row = out["table"][0]
        assert row["current_period"] == "$133,050,000,000"
        assert row["prior_period"] == "$123,216M"
        assert row["source_replaced"] == {"current_period": "$132,100M"}
        assert row["source_verified"] is True
        assert row["xbrl_concept"] == "Operating income"
        assert "source_mismatched" not in row
        # The change is recomputed from the filed pair, never kept from the summary's figures.
        assert row["change_display"] == "+8.0%"

    @pytest.mark.parametrize("commentary", [
        "Operating income increased 7.2% YoY.",
        "Operating income reached $132.1B in fiscal 2025.",
        "Up 8% on Q4 Services demand.",
        "Operating income was $2025 million.",
        "Operating income was 2025 million.",
    ])
    def test_a_takeaway_that_states_a_number_is_withheld(self, commentary):
        row = self._enrich({"metric": "Operating income", "current_period": "$132,100M", "prior_period": "$123,216M",
                            "commentary": commentary,
                            "supporting_evidence": "Operating income increased during 2025."})["table"][0]
        assert row["commentary"] == ""
        assert row["commentary_withheld"] == "figure_replaced"
        assert "supporting_evidence" not in row

    @pytest.mark.parametrize("commentary", [
        "Higher Services sales drove the increase.",
        "Services grew faster in 2025 than in 2024.",
        "FY2025 operating income rose on stronger Q4 demand.",
        "Item 7 attributes the increase to Services; see Note 13.",
        "FY25 operating income rose on Q4'25 demand.",
        "The 1H25 and H1 2025 trend held in Q3 FY25.",
        "The 10-K and the 20-F agree; see Notes 3 and 4.",
        "Higher than at Sept. 27, 2025.",
        "Higher than in the 1990s.",
        "fy2025 operating income rose; see note 13 and item 7.",
        "q4 demand lifted the 10-k's operating income.",
    ])
    def test_a_takeaway_that_names_no_figure_stays(self, commentary):
        # Years, quarters and the filing's own Items and Notes are not figures the swap replaced.
        row = self._enrich({"metric": "Operating income", "current_period": "$132,100M", "prior_period": "$123,216M",
                            "commentary": commentary})["table"][0]
        assert row["current_period"] == "$133,050,000,000"
        assert row["commentary"] == commentary
        assert "commentary_withheld" not in row

    FORGED = {
        "source_mismatched": ["current_period"],
        "source_filed": {"current_period": "$999,999 million"},
        "source_replaced": {"current_period": "$1.0B"},
        "commentary_withheld": "figure_replaced",
        "commentary_evidence": {"excerpt": "Sales reached $416.2B.", "section_ref": "Item 7", "verified": True,
                                "fragment_url": "https://example.com/forged"},
    }

    @pytest.mark.parametrize("row, xbrl", [
        ({"metric": "Total net sales", "current_period": "$416.2B"}, None),  # no XBRL for the filing
        ({"metric": "Backlog", "current_period": "$12.0B"}, APPLE),  # a label the check does not map
        ({"metric": "Total net sales", "current_period": "$416.2B", "prior_period": "$391.0B"}, APPLE),  # it matches
    ])
    def test_a_stored_rows_own_evidence_keys_are_ignored(self, row, xbrl):
        # A stored row is the model's JSON. Keys only enrichment may write must neither drive a swap the
        # check never asked for (once a 500: the swap indexed XBRL the row has none of) nor reach the reader.
        stored = {**row, **self.FORGED, "commentary": "Sales reached $416.2B."}
        fh = {"source_section_ref": "Item 8. Financial Statements", "table": [stored],
              "normalized": {"metrics": [{"metric": row["metric"], "currentPeriod": row["current_period"]}]}}
        out = prov.enrich_financial_highlights(fh, _filing(), xbrl)
        enriched = out["table"][0]
        assert enriched["current_period"] == row["current_period"]
        assert enriched["commentary"] == "Sales reached $416.2B."
        for key in ("source_mismatched", "source_replaced", "commentary_withheld", "commentary_evidence"):
            assert key not in enriched
        assert enriched.get("source_filed") != self.FORGED["source_filed"]
        assert out["normalized"]["metrics"][0]["currentPeriod"] == row["current_period"]

    def test_the_stored_row_is_never_rewritten(self):
        # The swap is read-time, per request: the summary as stored keeps its own figure and takeaway.
        fh = {"table": [{"metric": "Operating income", "current_period": "$132,100M", "prior_period": "$123,216M",
                         "commentary": "Operating income increased 7.2% YoY."}]}
        stored = copy.deepcopy(fh)
        assert prov.enrich_financial_highlights(fh, _filing(), APPLE)["table"][0]["current_period"] == "$133,050,000,000"
        assert fh == stored

    def test_a_matching_or_unchecked_row_is_left_alone(self):
        out = self._enrich(
            {"metric": "Total net sales", "current_period": "$416,161M", "prior_period": "$391,035M"},
            {"metric": "Services net sales", "current_period": "$109,158M", "prior_period": "$96,169M"},
        )
        assert [r["current_period"] for r in out["table"]] == ["$416,161M", "$109,158M"]
        assert all("source_replaced" not in r for r in out["table"])

    def test_the_heros_change_is_the_tables_at_a_rounding_boundary(self):
        # A prior shown as "$50.0M" matches a filed 50,040,000 and stays. The table's change is computed from the filed
        # pair, and so is the normalized fact the hero reads: from the display text it would read +10.0%.
        xbrl = {"reporting_currency": "USD", "revenue": {
            "current": {**_annual(55_000_000, "2025-09-27", "2024-09-29"), "raw_tag": REVENUE_TAG},
            "prior": {**_annual(50_040_000, "2024-09-28", "2023-10-01"), "raw_tag": REVENUE_TAG}}}
        fh = {"table": [{"metric": "Revenue", "current_period": "$54M", "prior_period": "$50.0M"}],
              "normalized": {"metrics": [{"metric": "Revenue", "currentPeriod": "$54M", "priorPeriod": "$50.0M", "deltaPercent": 8.0}]}}
        out = prov.enrich_financial_highlights(fh, _filing(), xbrl)
        row, fact = out["table"][0], out["normalized"]["metrics"][0]
        assert (row["current_period"], row["prior_period"], row["change_display"]) == ("$55,000,000", "$50.0M", "+9.9%")
        assert f"+{fact['deltaPercent']:.1f}%" == row["change_display"]
        assert (fact["currentValue"], fact["priorValue"]) == (55_000_000, 50_040_000)

    def test_the_stored_normalized_fact_follows_the_swap(self):
        stale = {"metric": "Operating income", "currentPeriod": "$132,100M", "priorPeriod": "$123,216M", "deltaPercent": 7.2}
        out = self._enrich({"metric": "Operating income", "current_period": "$132,100M", "prior_period": "$123,216M"},
                           normalized={"metrics": [stale]})
        fact = out["normalized"]["metrics"][0]
        assert fact["currentPeriod"] == "$133,050,000,000"
        assert round(fact["deltaPercent"], 1) == 8.0


class TestLabelsTheModelIsGiven:
    """Every label the model is handed for a line the figure check covers is one the check reads (the backend review
    of #1530: the prompts' own "Cash & Equivalents" went unchecked, though main had checked it). A label added to a
    prompt or to the narrative's grounding block is either read by ``source_metric_key`` or named below with why."""

    # Concepts the check covers that it deliberately leaves unchecked.
    UNCHECKED = {"free_cash_flow": "computed, not filed", "capital_expenditures": "filers sign it either way"}
    # Prompt labels no one filed concept answers.
    UNMAPPED = {
        "eps": "per-share figures are never checked",
        "eps (diluted)": "per-share figures are never checked",
        "eps / per-ads": "per-share figures are never checked",
        "total debt": "the current portion plus long-term debt: no one filed concept",
        "cash": "cash alone may exclude its equivalents",
    }

    def test_the_narratives_dollar_labels_map_to_their_own_concepts(self):
        from app.services.ai.xbrl_narrative import _XBRL_NARRATIVE_SPEC

        checked = set(prov._SOURCE_KEY_LABELS) - prov._NEVER_CHECKED_KEYS - set(self.UNCHECKED)
        pairs = [(label, key) for label, key, kind in _XBRL_NARRATIVE_SPEC if kind == "usd" and key in checked]
        assert len(pairs) >= 10, "the scan reads the grounding block"
        assert [(label, prov.source_metric_key(label)) for label, _ in pairs] == pairs

    def test_each_prompts_standard_metric_is_read_or_named(self):
        prompts = sorted((Path(__file__).resolve().parents[2] / "prompts").glob("*.md"))
        labels = set()
        for prompt in prompts:
            # A table's first row is its header; only a table headed "Metric" lists metrics.
            metric_table, previous = False, ""
            for line in prompt.read_text().splitlines():
                if line.startswith("|"):
                    first = line.strip("|").split("|")[0].replace("*", "").strip()
                    if not previous.startswith("|"):
                        metric_table = first == "Metric"
                    elif metric_table and first and not set(first) <= set("-: "):
                        labels.add(first)
                previous = line
        assert {"Revenue", "Cash & Equivalents", "Total Debt", "Cash"} <= labels, "the scan reads the prompts' metric tables"
        unread = sorted(label for label in labels
                        if prov.source_metric_key(label) is None and label.casefold() not in self.UNMAPPED)
        assert unread == []


class TestRefreshNormalized:
    def test_a_swapped_row_with_non_text_fields_still_refreshes_its_fact(self):
        # The model's other fields may be any JSON; the normalized fact takes text only.
        fh = {"table": [{"metric": "Operating income", "current_period": "$132,100M", "prior_period": {"value": 1},
                         "commentary": ["a", "list"]}],
              "normalized": {"metrics": [{"metric": "Operating income", "currentPeriod": "$132,100M"}]}}
        out = prov.enrich_financial_highlights(fh, _filing(), APPLE)
        assert out["normalized"]["metrics"][0]["currentPeriod"] == "$133,050,000,000"


class TestStandardizedXbrl:
    """The filing's own XBRL, read once for the page and the exports alike; a failure leaves rows unchecked."""

    def test_reads_the_filings_stored_xbrl(self, monkeypatch):
        from app.services.edgar.compat import xbrl_service

        stored = object()
        monkeypatch.setattr(xbrl_service, "extract_standardized_metrics", lambda data: APPLE if data is stored else None)
        assert prov.standardized_xbrl(SimpleNamespace(id=42, xbrl_data=stored)) is APPLE

    def test_no_stored_xbrl_reads_nothing(self, monkeypatch):
        from app.services.edgar.compat import xbrl_service

        monkeypatch.setattr(xbrl_service, "extract_standardized_metrics", lambda data: pytest.fail("read without XBRL"))
        assert prov.standardized_xbrl(None) is None
        assert prov.standardized_xbrl(SimpleNamespace(id=42, xbrl_data=None)) is None

    def test_a_failed_extraction_never_fails_the_read(self, monkeypatch, caplog):
        from app.services.edgar.compat import xbrl_service

        def broken(data):
            raise ValueError("malformed facts")

        monkeypatch.setattr(xbrl_service, "extract_standardized_metrics", broken)
        assert prov.standardized_xbrl(SimpleNamespace(id=42, xbrl_data={"facts": {}})) is None
        assert "XBRL standardization for provenance failed" in caplog.text


class TestEnrichFinancialHighlights:
    XBRL = {"revenue": {"current": {"value": 391035000000.0}}}

    def test_enriches_rows_and_propagates_section_ref_without_mutating(self):
        fh = {
            "source_section_ref": "Item 8. Financial Statements",
            "table": [
                {"metric": "Total Revenue", "current_period": "$391.0B"},
                {"metric": "Backlog", "current_period": "n/a"},
            ],
        }
        out = prov.enrich_financial_highlights(fh, _filing(), self.XBRL)
        assert out["table"][0]["source_verified"] is True
        assert out["table"][0]["source_section_ref"] == "Item 8. Financial Statements"
        assert out["table"][1]["source_verified"] is False  # unmapped metric, link only
        assert out["table"][1]["source_url"].endswith("aapl.htm")
        # Original input untouched.
        assert "source_verified" not in fh["table"][0]

    def test_tolerates_missing_table(self):
        assert prov.enrich_financial_highlights({"notes": "x"}, _filing(), self.XBRL) == {"notes": "x"}
        assert prov.enrich_financial_highlights(None, _filing(), self.XBRL) is None


class TestBuildEvidence:
    """T4: the generalized block/row citation dict (exact-verify, honest labeling, filing-only)."""

    SRC = prov.normalize_for_match(
        "The Company expects operating margin to expand in fiscal 2025. "
        "Net sales were $383,285 million for the year."
    )
    BASE = "https://www.sec.gov/Archives/edgar/data/320193/000/aapl.htm"

    def test_verbatim_excerpt_verifies_and_deep_links(self):
        ev = prov.build_evidence(
            "operating margin to expand in fiscal 2025", "Item 7. MD&A", self.BASE, self.SRC
        )
        assert ev["verified"] is True
        assert ev["fragment_url"].startswith(self.BASE + "#:~:text=")
        assert ev["section_ref"] == "Item 7. MD&A"
        assert ev["excerpt"] == "operating margin to expand in fiscal 2025"

    def test_unfound_excerpt_is_cited_not_verified(self):
        ev = prov.build_evidence(
            "a sentence that is nowhere in the filing text", "Item 7", self.BASE, self.SRC
        )
        assert ev["verified"] is False
        assert ev["fragment_url"] == self.BASE  # section-level link, no #:~:text= fragment
        assert "#:~:text=" not in ev["fragment_url"]

    def test_empty_excerpt_is_unverified(self):
        ev = prov.build_evidence("", "Item 7", self.BASE, self.SRC)
        assert ev["verified"] is False
        assert ev["excerpt"] is None

    def test_no_base_url_yields_none(self):
        ev = prov.build_evidence("operating margin to expand in fiscal 2025", "Item 7", "", self.SRC)
        assert ev["fragment_url"] is None

    def test_blank_section_ref_normalized_to_none(self):
        ev = prov.build_evidence("operating margin to expand in fiscal 2025", "   ", self.BASE, self.SRC)
        assert ev["section_ref"] is None


class TestV2CitationEnrichment:
    """T4: enrich_raw_summary generalizes trace-to-source to quotes, footnotes, and metric takeaways."""

    SRC = (
        "We expect double-digit revenue growth in fiscal 2025. "
        "Stock-based compensation expense was recognized over the vesting period. "
        "Revenue increased driven by higher services net sales."
    )

    def _raw(self):
        return {
            "schema_version": 2,
            "sections": {
                "forward_signals": {
                    "source_section_ref": "Item 7. MD&A",
                    "quotes": [
                        {"speaker": "CEO", "quote": "We expect double-digit revenue growth in fiscal 2025.", "context": "MD&A"},
                        {"speaker": "CFO", "quote": "A totally invented sentence not in the filing.", "context": "MD&A"},
                    ],
                },
                "notable_footnotes": [
                    {
                        "item": "Stock-based compensation",
                        "impact": "Expense recognized over vesting",
                        "supporting_evidence": "Stock-based compensation expense was recognized over the vesting period",
                        "source_section_ref": "Note 5",
                    }
                ],
                "results_that_matter": {
                    "source_section_ref": "Item 8",
                    "table": [
                        {
                            "metric": "Revenue",
                            "current_period": "$383.3B",
                            "commentary": "Grew on services strength",
                            "supporting_evidence": "Revenue increased driven by higher services net sales",
                        }
                    ],
                },
            },
        }

    def test_quotes_footnotes_and_takeaways_are_cited(self):
        out = prov.enrich_raw_summary(self._raw(), _filing(critical_excerpt=self.SRC))
        quotes = out["sections"]["forward_signals"]["quotes"]
        assert quotes[0]["evidence"]["verified"] is True
        assert "#:~:text=" in quotes[0]["evidence"]["fragment_url"]
        assert quotes[0]["evidence"]["section_ref"] == "Item 7. MD&A"
        # A fabricated quote is honestly labeled Cited (not Verified), section link only.
        assert quotes[1]["evidence"]["verified"] is False
        assert "#:~:text=" not in quotes[1]["evidence"]["fragment_url"]

        fn = out["sections"]["notable_footnotes"][0]
        assert fn["evidence"]["verified"] is True

        row = out["sections"]["results_that_matter"]["table"][0]
        assert row["commentary_evidence"]["verified"] is True
        # The number provenance (source_*) and the takeaway citation are independent fields.
        assert "source_verified" in row and "commentary_evidence" in row

    def test_a_takeaway_passage_never_borrows_the_tables_section(self):
        # The table's section is where its figures come from; the live Apple example labelled Item 7
        # sentences "Item 8. Financial Statements" by inheriting it. A passage names its section only
        # when its own excerpt leads with one.
        raw = self._raw()
        raw["sections"]["results_that_matter"]["source_section_ref"] = "Item 8. Financial Statements"
        row = raw["sections"]["results_that_matter"]["table"][0]
        quoted = row["supporting_evidence"]
        out = prov.enrich_raw_summary(raw, _filing(critical_excerpt=self.SRC))
        evidence = out["sections"]["results_that_matter"]["table"][0]["commentary_evidence"]
        assert evidence["verified"] is True and evidence["section_ref"] is None
        assert out["sections"]["results_that_matter"]["table"][0]["source_section_ref"] == "Item 8. Financial Statements"

        row["supporting_evidence"] = f'Item 7. MD&A: "{quoted}"'
        out = prov.enrich_raw_summary(raw, _filing(critical_excerpt=self.SRC))
        assert out["sections"]["results_that_matter"]["table"][0]["commentary_evidence"]["section_ref"] == "Item 7. MD&A"

    def _enrich_one_quote(self, quote):
        raw = self._raw()
        raw["sections"]["forward_signals"]["quotes"] = [{"speaker": "CEO", "quote": quote}]
        out = prov.enrich_raw_summary(raw, _filing(critical_excerpt=self.SRC))
        return out["sections"]["forward_signals"]["quotes"][0]["evidence"]

    def test_whole_verbatim_quote_is_verified_with_build_evidence_output(self):
        quote = "“We expect double-digit revenue growth in fiscal 2025.”"
        ev = self._enrich_one_quote(quote)
        assert ev == prov.build_evidence(
            quote, "Item 7. MD&A", _filing().document_url, prov.normalize_for_match(self.SRC)
        )
        assert ev["verified"] is True and "#:~:text=We%20expect" in ev["fragment_url"]

    def test_quote_contiguous_only_through_an_inner_quoted_span_is_unverified(self):
        # The page displays the whole quote, so a real inner span cannot vouch for invented text.
        quote = 'The CEO promised a special dividend and said "We expect double-digit revenue growth in fiscal 2025."'
        premise = prov.build_evidence(
            quote, "Item 7. MD&A", _filing().document_url, prov.normalize_for_match(self.SRC)
        )
        assert premise["verified"] is True  # the prefix-tolerant builder alone would verify it
        assert self._enrich_one_quote(quote) == {
            "excerpt": None, "section_ref": "Item 7. MD&A", "verified": False,
            "fragment_url": _filing().document_url,
        }

    def test_footnote_evidence_for_a_prefixed_excerpt_is_unchanged(self):
        # Footnotes display only the verified quoted span, so build_evidence's prefix tolerance stays.
        span = "Stock-based compensation expense was recognized over the vesting period"
        raw = self._raw()
        raw["sections"]["notable_footnotes"][0]["supporting_evidence"] = f'Note 5 states: "{span}"'
        out = prov.enrich_raw_summary(raw, _filing(critical_excerpt=self.SRC))
        assert out["sections"]["notable_footnotes"][0]["evidence"] == {
            "excerpt": span, "section_ref": "Note 5", "verified": True,
            "fragment_url": prov.build_text_fragment_url(_filing().document_url, span),
        }

    def test_enrichment_is_non_mutating(self):
        raw = self._raw()
        before = copy.deepcopy(raw)
        prov.enrich_raw_summary(raw, _filing(critical_excerpt=self.SRC))
        assert raw == before

    def test_v1_rows_get_no_block_citations(self):
        raw = {
            "schema_version": 1,
            "sections": {"risk_factors": [{"summary": "x", "supporting_evidence": "y is a longer evidence line"}]},
        }
        out = prov.enrich_raw_summary(raw, _filing(critical_excerpt=self.SRC))
        # v1 path never touches forward_signals / footnote evidence (those are v2-only surfaces).
        assert "forward_signals" not in out["sections"]

    @pytest.mark.parametrize("cached", [None, "   "])
    def test_cites_no_passage_without_filing_text_to_search(self, cached):
        # No cached filing text: the passes must not crash, and no passage is cited at all, since a "Quote not
        # found" or "Section linked" chip would report a search that never ran (the frontend review of #1530).
        raw = self._raw()
        raw["sections"]["results_that_matter"]["table"][0]["commentary_evidence"] = {"verified": True, "excerpt": "x"}
        out = prov.enrich_raw_summary(raw, _filing(critical_excerpt=cached))
        assert all("evidence" not in quote for quote in out["sections"]["forward_signals"]["quotes"])
        assert all("evidence" not in footnote for footnote in out["sections"]["notable_footnotes"])
        assert "commentary_evidence" not in out["sections"]["results_that_matter"]["table"][0]

    def test_quotes_and_footnotes_enriched_without_risks_or_metrics_table(self):
        # Guard regression: a v2 summary with ONLY quotes + footnotes (no risks list, no metrics table)
        # must still get citation enrichment — the pre-T4 early-return only checked risks/metrics.
        raw = {
            "schema_version": 2,
            "sections": {
                "forward_signals": {
                    "source_section_ref": "Item 7",
                    "quotes": [{"speaker": "CEO", "quote": "We expect double-digit revenue growth in fiscal 2025."}],
                },
                "notable_footnotes": [
                    {"item": "SBC", "impact": "up", "supporting_evidence": "Stock-based compensation expense was recognized over the vesting period"},
                ],
            },
        }
        out = prov.enrich_raw_summary(raw, _filing(critical_excerpt=self.SRC))
        assert out["sections"]["forward_signals"]["quotes"][0]["evidence"]["verified"] is True
        assert out["sections"]["notable_footnotes"][0]["evidence"]["verified"] is True

    def test_footnote_without_excerpt_or_ref_gets_no_chip(self):
        # A footnote with neither a supporting excerpt nor a section ref must NOT get a bare "Cited" chip
        # pointing at the filing root (that's noise, not provenance).
        raw = {
            "schema_version": 2,
            "sections": {"notable_footnotes": [{"item": "Bare footnote", "impact": "some impact"}]},
        }
        out = prov.enrich_raw_summary(raw, _filing(critical_excerpt=self.SRC))
        assert "evidence" not in out["sections"]["notable_footnotes"][0]


class TestPunctuationSpacingFold:
    """ADR-0008 Copilot readout: the ASML 20-F source carried spaces before commas that the model
    tidied when quoting; the fold is symmetric and must never tolerate a word-level change."""

    SOURCE = ("Total net sales rose by €4.4 billion , or 15.6% , reflecting an increase in net system "
              "sales of 12.4% , and an increase in net service and field option sales. Net income for 2025 "
              "amounted to €9,609.4 million , representing 29.4% of total net sales and €24.73 basic net "
              "income per ordinary share. ( see Note 5 ) ")

    def test_tidied_excerpt_verifies_against_spaced_source(self):
        source = prov.normalize_for_match(self.SOURCE)
        assert prov.verify_excerpt_in_text(
            "Total net sales rose by €4.4 billion, or 15.6%, reflecting an increase in net system sales of 12.4%",
            source)
        assert prov.verify_excerpt_in_text(
            "Net income for 2025 amounted to €9,609.4 million, representing 29.4% of total net sales and "
            "€24.73 basic net income per ordinary share.", source)
        assert prov.verify_excerpt_in_text("(see Note 5)", source) is False  # below the length floor
        assert prov.normalize_for_match("( see Note 5 ) ") == prov.normalize_for_match("(see Note 5)")

    def test_fold_is_symmetric_and_word_level_changes_still_fail(self):
        source = prov.normalize_for_match(self.SOURCE)
        # Spaced excerpt against a tidy source verifies too (symmetry).
        tidy = prov.normalize_for_match("Net income for 2025 amounted to €9,609.4 million, representing 29.4% of total net sales")
        assert prov.verify_excerpt_in_text("Net income for 2025 amounted to €9,609.4 million , representing 29.4% of total net sales", tidy)
        # A dropped word, a reordered clause, or a changed figure is still not verbatim.
        assert prov.verify_excerpt_in_text("Total net sales rose by €4.4 billion, reflecting an increase in net system sales of 12.4%", source) is False
        assert prov.verify_excerpt_in_text("Net income for 2025 amounted to €9,609.5 million, representing 29.4% of total net sales", source) is False
        # Whitespace inside words / between words is not folded away.
        assert prov.normalize_for_match("net sales") != prov.normalize_for_match("netsales")
