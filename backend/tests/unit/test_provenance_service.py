"""Unit tests for Trace-to-Source provenance enrichment."""

import copy
import re
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote

import pytest

from app.services import metric_delta_service
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


# Each takes the place of every space between an excerpt's words. A stored filing span carries line breaks, and every
# read projects it again.
_RISK_PADDINGS = [("two spaces", "  "), ("a line break", "\n  "), ("two tabs", "\t\t"), ("a no-break space", "\u00a0 ")]


class TestRiskExcerptFloor:
    """Risks match whitespace-exact, so the floor counts what the match compares: the words, with the whitespace
    between them collapsed and every other character as written. The model's evidence and the filing span it selects
    share them, so padding of any kind, on either side, carries no short excerpt over the floor, and a stored span
    keeps its place when a read projects it again (E180)."""

    SHORT = "Supply chain risk rose."
    AT_THE_FLOOR = "Supply chain risks rose."
    LONG = "Our business depends on a limited number of suppliers."

    @pytest.mark.parametrize("pad_evidence, pad_filing, padding", [
        pytest.param(on_evidence, on_filing, padding, id=f"{side} padding, {name}")
        for side, on_evidence, on_filing in (("the model's", True, False), ("the filing's", False, True), ("both", True, True))
        for name, padding in _RISK_PADDINGS
    ])
    def test_padding_carries_no_short_excerpt_over_the_floor(self, pad_evidence, pad_filing, padding):
        evidence = self.SHORT.replace(" ", padding) if pad_evidence else self.SHORT
        filed = self.SHORT.replace(" ", padding) if pad_filing else self.SHORT
        assert len(self.SHORT) == prov._MIN_VERIFIABLE_LEN - 1
        assert max(len(evidence), len(filed)) > prov._MIN_VERIFIABLE_LEN
        filing = _filing(critical_excerpt=f"{filed}\n{self.LONG}")
        raw = {"sections": {"risk_factors": [{"supporting_evidence": evidence}, {"supporting_evidence": self.LONG}]}}

        sections = prov.project_raw_summary_risks(raw, filing, summary_filing_id=filing.id)["sections"]
        assert [risk["supporting_evidence"] for risk in sections["risk_factors"]] == [self.LONG]
        assert sections[prov.RISK_PROJECTION_KEY]["withheld_count"] == 1

    @pytest.mark.parametrize("padding", [padding for _name, padding in _RISK_PADDINGS],
                             ids=[name for name, _padding in _RISK_PADDINGS])
    def test_an_excerpt_whose_words_reach_the_floor_is_kept_however_padded(self, padding):
        assert len(self.AT_THE_FLOOR) == prov._MIN_VERIFIABLE_LEN
        filed = self.AT_THE_FLOOR.replace(" ", padding)
        filing = _filing(critical_excerpt=f"{filed}\n{self.LONG}")
        raw = {"sections": {"risk_factors": [{"supporting_evidence": self.AT_THE_FLOOR.replace(" ", padding)}]}}

        sections = prov.project_raw_summary_risks(raw, filing, summary_filing_id=filing.id)["sections"]
        assert [risk["supporting_evidence"] for risk in sections["risk_factors"]] == [filed]


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

    def test_a_stored_number_prior_is_a_shown_prior_that_leaves_the_row_unchecked(self):
        # A number is a figure the row shows, so the row cannot match on its current year alone.
        row = {"metric": "Total net sales", "current_period": "$416.2B", "prior_period": 391_035_000_000}
        out = prov.build_metric_source(row, _filing(), APPLE, None)
        assert out["source_checkable"] is False and out["source_verified"] is False

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

    @pytest.mark.parametrize("metric, key, tag", [
        ("Cash and cash equivalents", "cash_and_equivalents", "us-gaap:CashAndCashEquivalentsAtCarryingValue"),
        ("Shareholders' equity", "shareholders_equity", "us-gaap:StockholdersEquity"),
        ("Long-term debt", "long_term_debt", "us-gaap:LongTermDebtNoncurrent"),
    ])
    def test_every_balance_sheet_line_reads_its_prior_from_the_filings_earlier_instants(self, metric, key, tag):
        # Each instant concept, as total assets: the standardized prior is a quarter the same-quarter rule refuses.
        series = [{**fact, "raw_tag": tag} for fact in self.QUARTER["total_assets"]["series"]]
        quarter = {"reporting_currency": "USD", key: {"current": series[0], "prior": series[2], "series": series}}
        assert self._check(metric, "$331.5B", "$365.0B", quarter)["source_verified"] is True

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

    THIS_FILING, EARLIER_FILING = "0000320193-25-000073", "0000320193-25-000057"

    @pytest.mark.parametrize("current_accn, earlier_accn, verified", [
        # Another filing's fact of equal value proves nothing about this one's (E184).
        (THIS_FILING, EARLIER_FILING, False),
        # This filing's own comparative, as its companyfacts entries record it: the match stands.
        (THIS_FILING, THIS_FILING, True),
        # A fact that records no filing (a series stored before E184) is read as before: an accession on one side
        # alone neither proves nor refuses the other's source, for a filing that records none either.
        (None, EARLIER_FILING, True),
        (THIS_FILING, None, True),
        (None, None, True),
    ])
    def test_an_earlier_instant_another_filing_recorded_is_not_this_filings(self, current_accn, earlier_accn, verified):
        current = {**self.QUARTER["total_assets"]["current"], "raw_tag": "Assets"}
        earlier = {"period": "2024-09-28", "value": 364_980e6, "form": "10-Q", "currency": "USD", "raw_tag": "Assets"}
        current = {**current, **({"accn": current_accn} if current_accn else {})}
        earlier = {**earlier, **({"accn": earlier_accn} if earlier_accn else {})}
        quarter = {"reporting_currency": "USD", "total_assets": {
            "current": current, "prior": {**earlier, "fiscal_period": "Q4"}, "series": [current, earlier]}}
        out = self._check("Total assets", "$331.5B", "$365.0B", quarter)
        assert (out["source_checkable"], out["source_verified"]) == (verified, verified)
        assert "source_mismatched" not in out

    @pytest.mark.parametrize("current_accn, earlier_accn, verified", [
        (THIS_FILING, EARLIER_FILING, False),
        (THIS_FILING, THIS_FILING, True),
        # Held to the filing's own accession, not the current fact's: an earlier instant another filing recorded is
        # refused beside a current fact that records none, and a current fact another filing recorded is not checked.
        (None, EARLIER_FILING, False),
        (EARLIER_FILING, EARLIER_FILING, False),
        (THIS_FILING, None, True),
        (None, None, True),
        # The same filing, its dashes aside (SEC's companyfacts dashes it; a stored accession may not).
        (THIS_FILING.replace("-", ""), THIS_FILING, True),
    ])
    def test_an_earlier_instant_is_held_to_the_filings_own_accession(self, current_accn, earlier_accn, verified):
        current = {**self.QUARTER["total_assets"]["current"], "raw_tag": "Assets"}
        earlier = {"period": "2024-09-28", "value": 364_980e6, "form": "10-Q", "currency": "USD", "raw_tag": "Assets"}
        current = {**current, **({"accn": current_accn} if current_accn else {})}
        earlier = {**earlier, **({"accn": earlier_accn} if earlier_accn else {})}
        quarter = {"reporting_currency": "USD", "total_assets": {
            "current": current, "prior": {**earlier, "fiscal_period": "Q4"}, "series": [current, earlier]}}
        out = self._check_filed("Total assets", "$331.5B", "$365.0B", quarter, self.THIS_FILING)
        assert (out["source_checkable"], out["source_verified"]) == (verified, verified)
        assert "source_mismatched" not in out

    APPLE_10K = "0000320193-25-000079"

    def _check_filed(self, metric, current, prior, xbrl, accession):
        filing = SimpleNamespace(**vars(_filing()), accession_number=accession)
        return prov.build_metric_source(
            {"metric": metric, "current_period": current, "prior_period": prior}, filing, xbrl, None,
        )

    @staticmethod
    def _recorded(key, current_accn, prior_accn, xbrl=APPLE):
        entry = xbrl[key]
        return {**xbrl, key: {
            **entry,
            "current": {**entry["current"], **({"accn": current_accn} if current_accn else {})},
            "prior": {**entry["prior"], **({"accn": prior_accn} if prior_accn else {})},
        }}

    @pytest.mark.parametrize("key, metric, current, equal, other", [
        ("revenue", "Total net sales", "$416.2B", "$391.0B", "$383.3B"),
        ("operating_income", "Operating income", "$133.1B", "$123.2B", "$114.3B"),
    ])
    def test_a_comparable_prior_another_filing_recorded_is_neither_matched_nor_swapped_in(
        self, key, metric, current, equal, other,
    ):
        # The comparable prior (comparable_facts) compares no filing: an annual prior another filing recorded read
        # "Matches filing" where its value was equal, and was swapped in where it differed (E184's correctness lens).
        # Neither now: the row is left unchecked, never matched on another filing's figure.
        elsewhere = self._recorded(key, self.APPLE_10K, self.EARLIER_FILING)
        for prior in (equal, other):
            out = self._check_filed(metric, current, prior, elsewhere, self.APPLE_10K)
            assert (out["source_checkable"], out["source_verified"]) == (False, False), prior
            assert "source_mismatched" not in out
        own = self._recorded(key, self.APPLE_10K, self.APPLE_10K)
        assert self._check_filed(metric, current, equal, own, self.APPLE_10K)["source_verified"] is True
        assert self._check_filed(metric, current, other, own, self.APPLE_10K)["source_mismatched"] == ["prior_period"]

    def test_a_current_fact_another_filing_recorded_is_not_checked(self):
        out = self._check_filed("Total net sales", "$416.2B", "—", self._recorded("revenue", self.EARLIER_FILING, None),
                                self.APPLE_10K)
        assert (out["source_checkable"], out["source_verified"]) == (False, False)

    def test_a_filing_that_records_no_accession_reads_its_facts_as_before(self):
        # Characterized, not proven: with no accession of its own to hold them to, a filing's facts read as before.
        elsewhere = self._recorded("revenue", self.EARLIER_FILING, self.EARLIER_FILING)
        assert self._check("Total net sales", "$416.2B", "$391.0B", elsewhere)["source_verified"] is True

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
        ("Cash and cash equivalents", "cash_and_equivalents", "us-gaap:Cash", "$8.0B", "unchecked"),  # may leave out its equivalents
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
        # "Revenues" is the top line, which may add other income to net sales (Walmart's membership fees), or
        # interest expense back to net revenues (Raymond James's FY2024: $14,923M of revenues, $12,821M net).
        ("Net sales", "revenue", "us-gaap:Revenues", "unchecked"),
        ("Net Sales", "revenue", "us-gaap:Revenues", "unchecked"),  # in any case
        ("Net revenues", "revenue", "us-gaap:Revenues", "unchecked"),
        ("Total net revenue", "revenue", "us-gaap:Revenues", "unchecked"),
        ("Total revenues", "revenue", "us-gaap:Revenues", "replaced"),
        ("Revenue", "revenue", "us-gaap:Revenues", "replaced"),
        # A contract-revenue tag may be the top line beside a narrower net sales line: Costco's FY2026 Q3 10-Q tags
        # its $70,527M of total revenue so, beside $69,154M of net sales. A total ("Total net sales", Apple's) is
        # the top line, and a tag named for a net line is that line.
        ("Net sales", "revenue", REVENUE_TAG, "unchecked"),
        ("Total net sales", "revenue", REVENUE_TAG, "replaced"),
        ("Total revenue", "revenue", REVENUE_TAG, "replaced"),
        ("Net sales", "revenue", "us-gaap:SalesRevenueNet", "replaced"),
        ("Total net revenue", "revenue", "us-gaap:RevenuesNetOfInterestExpense", "replaced"),  # a bank's own total
        ("Revenue", "revenue", None, "unchecked"),  # the companyfacts path records no revenue tag
        # "Net income" names the consolidated total or the parent's share (test below), so no tag qualifies.
        ("Net income", "net_income", "us-gaap:ProfitLoss", "unchecked"),
        ("Net income", "net_income", "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic", "unchecked"),
        ("Net income", "net_income", "us-gaap:NetIncomeLoss", "unchecked"),
        ("Net income", "net_income", "ifrs-full:ProfitLossAttributableToOwnersOfParent", "unchecked"),
        ("Operating cash flow", "operating_cash_flow",
         "us-gaap:NetCashProvidedByUsedInOperatingActivitiesContinuingOperations", "unchecked"),
        ("Operating cash flow", "operating_cash_flow", "us-gaap:NetCashProvidedByUsedInOperatingActivities", "replaced"),
        # A "net" label narrows revenue alone: the statement's own cash-flow line names its filed line.
        ("Net cash provided by operating activities", "operating_cash_flow", "us-gaap:NetCashProvidedByUsedInOperatingActivities", "replaced"),
        ("Net cash from operating activities", "operating_cash_flow", "ifrs-full:CashFlowsFromUsedInOperatingActivities", "replaced"),
        ("Operating income", "operating_income", None, "replaced"),  # one scope across its candidates
    ])
    def test_a_period_figure_is_replaced_only_by_the_line_its_label_names(self, metric, key, tag, outcome):
        fact = {**_annual(10_000e6, "2025-09-27", "2024-09-29"), **({"raw_tag": tag} if tag else {})}
        out = self._check(metric, "$8.0B", "—", {"reporting_currency": "USD", key: {"current": fact}})
        assert (out["source_verified"], out["source_checkable"], out.get("source_mismatched")) == self.OUTCOMES[outcome]

    def test_costcos_net_sales_are_never_replaced_by_its_total_revenue(self):
        # The eval baselines' own rows (COST, FY2026 Q3): the standardized revenue fact is the total.
        fact = {**_annual(70_527e6, "2026-05-10", "2026-02-16"), "raw_tag": REVENUE_TAG}
        fh = {"table": [{"metric": "Total revenue", "current_period": "$70,527M", "prior_period": "—"},
                        {"metric": "Net sales", "current_period": "$69,154M", "prior_period": "—",
                         "commentary": "Net sales rose on comparable sales growth."}]}
        total, net = prov.enrich_financial_highlights(fh, _filing(), {"reporting_currency": "USD", "revenue": {"current": fact}})["table"]
        assert total["source_verified"] is True
        assert (net["current_period"], net["commentary"], net["source_checkable"]) == ("$69,154M", "Net sales rose on comparable sales growth.", False)
        assert "source_replaced" not in net and "commentary_withheld" not in net

    @pytest.mark.parametrize("metric, total, share, filed, currency", [
        # Alibaba's FY2026 20-F: net income CNY 102,127M, of which CNY 103,592M attributable to it (NetIncomeLoss).
        ("Net income", "CNY 102,127M", "CNY 103,592M", 103_592e6, "CNY"),
        # Ford's Q1 2026 10-Q: net income $2,551M, attributable $2,548M.
        ("Net income (loss)", "$2,551M", "$2,548M", 2_548e6, "USD"),
        # Procter & Gamble's FY2024 10-K: net earnings $14,974M, attributable $14,879M.
        ("Net earnings", "$14,974M", "$14,879M", 14_879e6, "USD"),
        ("Net profit", "$14,974M", "$14,879M", 14_879e6, "USD"),
    ])
    def test_net_income_is_matched_but_never_replaced(self, metric, total, share, filed, currency):
        # With noncontrolling interests the consolidated total and the parent's share differ, and the 20-F prompt asks
        # for the total: a correct total must not be replaced by the parent's share and marked as matching.
        fact = {**_annual(filed, "2025-12-31", "2025-01-01"), "currency": currency, "raw_tag": "us-gaap:NetIncomeLoss"}
        xbrl = {"reporting_currency": currency, "net_income": {"current": fact}}
        out = self._check(metric, total, "—", xbrl)
        assert (out["source_verified"], out["source_checkable"], out.get("source_mismatched")) == self.OUTCOMES["unchecked"]
        assert self._check(metric, share, "—", xbrl)["source_verified"] is True

    def test_a_prior_of_another_line_is_never_replaced(self):
        # Each period is held to the line its label names: a current figure that matches lets no differing prior of a
        # restricted-cash total be replaced.
        tag = "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
        cash = {"current": {"period": "2025-09-27", "value": 10_000e6, "form": "10-K", "currency": "USD", "raw_tag": tag},
                "prior": {"period": "2024-09-28", "value": 9_000e6, "form": "10-K", "currency": "USD", "raw_tag": tag}}
        out = self._check("Cash and cash equivalents", "$10.0B", "$8.0B", {"reporting_currency": "USD", "cash_and_equivalents": cash})
        assert (out["source_verified"], out["source_checkable"], out.get("source_mismatched")) == self.OUTCOMES["unchecked"]

    def test_a_cash_figure_of_another_line_is_shown_as_the_summary_wrote_it(self):
        restricted = {"period": "2025-09-27", "value": 10_000e6, "form": "10-K", "currency": "USD",
                      "raw_tag": "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"}
        fh = {"table": [{"metric": "Cash and cash equivalents", "current_period": "$8.0B", "commentary": "Cash fell to $8.0B."}]}
        row = prov.enrich_financial_highlights(fh, _filing(), {"reporting_currency": "USD", "cash_and_equivalents": {"current": restricted}})["table"][0]
        assert (row["current_period"], row["commentary"], row["source_checkable"]) == ("$8.0B", "Cash fell to $8.0B.", False)
        assert "source_replaced" not in row and "commentary_withheld" not in row

    @pytest.mark.parametrize("form", ["10-Q", "10-Q/A", "6-K", None])
    def test_an_interim_balance_sheet_prior_is_matched_never_replaced_without_fiscal_labels(self, form):
        # Without fiscal labels any two instants pass as comparable, and the standardized prior is the previous
        # quarter end: a correct year-end or last year's quarter-end prior must not be replaced by it. Any form but an
        # annual one is read so, a fact that names none included.
        unlabeled = [{**{key: value for key, value in fact.items() if key not in ("fiscal_period", "form")},
                      **({"form": form} if form else {})}
                     for fact in self.QUARTER["total_assets"]["series"]]
        quarter = {"reporting_currency": "USD", "total_assets": {"current": unlabeled[0], "prior": unlabeled[1], "series": unlabeled}}
        assert self._check("Total assets", "$331.5B", "$365.0B", quarter)["source_verified"] is True
        stated_nowhere = self._check("Total assets", "$331.5B", "$356.0B", quarter)
        assert stated_nowhere["source_checkable"] is False and "source_mismatched" not in stated_nowhere

    @pytest.mark.parametrize("form", ["10-K", "10-K/A", "20-F", "40-F"])
    def test_an_annual_balance_sheet_prior_is_still_replaced(self, form):
        annual = {"reporting_currency": "USD", "total_assets": {
            "current": {"period": "2025-09-27", "value": 359_241e6, "form": form, "currency": "USD"},
            "prior": {"period": "2024-09-28", "value": 364_980e6, "form": form, "currency": "USD"}}}
        assert self._check("Total assets", "$359.2B", "$365.0B", annual)["source_verified"] is True
        assert self._check("Total assets", "$359.2B", "$356.0B", annual)["source_mismatched"] == ["prior_period"]

    def test_a_figure_dated_to_another_period_is_not_checked(self):
        # Code-written bank rows date their figures; a figure dated to the filed fact's own period is checked.
        assert self._check("Total net sales", "$416.2B (2025-09-27)", "$391.0B (2024-09-28)")["source_verified"] is True
        for current, prior in [("$416.2B", "$383.3B (2023-09-30)"), ("$391.0B (2024-09-28)", "—")]:
            other_year = self._check("Total net sales", current, prior)
            assert other_year["source_checkable"] is False and "source_mismatched" not in other_year

    @pytest.mark.parametrize("shown", ["$416,161", "416,161", "(1.2)", "$950"])
    def test_a_figure_that_states_no_scale_is_not_checked(self, shown):
        # In millions, as a statement prints it, or in any other unit: the scale cannot be told.
        out = self._check("Total net sales", shown)
        assert out["source_checkable"] is False and "source_mismatched" not in out

    def test_a_prior_that_states_no_scale_is_not_checked(self):
        out = self._check("Total net sales", "$416.2B", "391,035")
        assert out["source_checkable"] is False and "source_mismatched" not in out

    def test_a_whole_figure_without_a_scale_word_is_still_checked(self):
        assert self._check("Total net sales", "$416,161,000,000")["source_verified"] is True
        assert self._check("Total net sales", "$416,000,000,000")["source_mismatched"] == ["current_period"]

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

    @pytest.mark.parametrize("current, prior", [("$416.2B", "€391.0B"), ("€416.2B", "$391.0B")])
    def test_a_prior_in_a_currency_the_data_cannot_confirm_leaves_the_row_unchecked(self, current, prior):
        # The guard reads each compared period: beside data that names no currency, a figure in euros in either
        # period is neither matched nor replaced, though the other period's dollar figure matches.
        filed = {period: {**fact, "currency": None} for period, fact in APPLE["revenue"].items()}
        xbrl = {"revenue": filed}
        assert self._check("Total net sales", current, prior, xbrl)["source_checkable"] is False
        fh = {"table": [{"metric": "Total net sales", "current_period": current, "prior_period": prior}]}
        row = prov.enrich_financial_highlights(fh, _filing(), xbrl)["table"][0]
        assert (row["current_period"], row["prior_period"], row["source_verified"]) == (current, prior, False)
        assert "source_replaced" not in row

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
        # Nor against a renminbi fact.
        renminbi = {"reporting_currency": "CNY", "revenue": {
            period: {**fact, "currency": "CNY"} for period, fact in self.YEN["revenue"].items()}}
        assert self._check("Total net sales", "¥45.1T", "¥37.2T", renminbi)["source_verified"] is True

    # The plain aliases read the statement lines the strict mapper owns none of: most main's substring check read, and the
    # rest lines the prompts name or the eval baselines write ("Income from operations", "Profit for the year"), each on
    # its own concept; a dropped or mistyped alias leaves its line silently "Linked, not checked".
    @pytest.mark.parametrize("metric, key", [
        ("Net revenue", "revenue"), ("Net revenues", "revenue"), ("Net operating revenue", "revenue"),
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
        ("Operating (loss) income", "operating_income"),
        ("Net income (loss)", "net_income"), ("Net income/(loss)", "net_income"), ("Net (loss) income", "net_income"),
        ("Net earnings", "net_income"), ("Profit for the year", "net_income"), ("Profit/(loss) for the year", "net_income"),
        ("Net cash from operating activities", "operating_cash_flow"),
        ("Net profit", "net_income"), ("Earnings attributable to shareholders", "net_income"),
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
        # Words that start like a month, a quarter followed by a figure, and a figure after a Note list.
        "Operating income declined 8% on weaker demand.",
        "Decreased 12% year over year.",
        "Margin 38% held flat.",
        "Q4 25% of sales came from Services.",
        "H2 15% growth.",
        "See Note 3, 25% of revenue.",
        "FY25 rose 12%; Item 7, 8.5% of it from Services.",
        # An amount that reads like a year, with no scale word after it.
        "Each seat brought in $2025.",
        # A unit after a listed number, a month's day or a quarter's year makes it an amount.
        "See Note 7, 120 million in restructuring charges.",
        "Item 7 - 12 percent growth in Services.",
        "In June 25 percent of sales came from Services.",
        "Margins widened Dec 15 bps.",
        "Q4 2025 million in Services sales.",
        # A word that starts like a month, a quarter beside a count, and a month's day before a percent.
        "Openings decreased 40 year over year.",
        "Q4 25 new stores opened.",
        "Revenue rose in March 8% on services.",
        # A thousands group, a scale written in lower case and percentage points after a listed number.
        "As described in Note 12, 1,250 positions were eliminated.",
        "See Note 7, 2b impairment charges.",
        "See Note 3, 4 percentage points came from pricing.",
        # Each unit the pattern knows, where it alone decides: after a month's day or a figure shaped like a year,
        # which would otherwise read as a date.
        "In June 25 per cent of sales came from Services.",
        "Margins widened Dec 15 basis points.",
        "Margins widened Dec 15 bp.",
        "Margins widened Dec 15 pp.",
        "Margins widened Dec 15 ppts.",
        "Margins widened Dec 15 ppt.",
        "Margins widened Dec 15 pts.",
        "Margins widened Dec 15 percentage points.",
        "Margins widened Dec 15 BPS.",
        "Shipments were 2025 thousand units.",
        "Operating income was 2025 billion yen.",
        "Assets reached 2025 trillion won.",
        "Charges were 2025 mn.",
        "Charges were 2025 bn.",
        "Assets reached 2025 tn.",
        "Charges were 2025 m.",
        "Shipments were 2025 k units.",
        "Charges were 2025 b.",
        "Assets reached 2025 t.",
        # A listed number's letter is a capital ("Item 7A"); a lower-case one is a scale.
        "See Note 2b impairment charges.",
        # A count after a listed number: past two digits, or where the list neither goes on nor ends.
        "As described in Note 12, 250 positions were eliminated.",
        "As described in Note 12, 25 positions were eliminated.",
        "Item 7, 40 stores opened.",
        "Item 7 and 250 stores opened.",
        "Note 4, 3 K-cups sold.",
        "Note 4, 3 M&A deals closed.",
        # A count a dash joins to a word after a listed number ("40-store"): a dash before a number goes on with the list
        # ("Notes 3, 4-5"), and a spaced hyphen or en dash ends its clause, as a colon does.
        "Per Item 7, 40-store expansion drove growth.",
        "Per Note 9, 10-year notes refinanced the revolver.",
        "Per Item 7, 12-percent growth in Services.",
        # A spaced em dash does not end the list, so the number before it reads as a figure, the safe way.
        "See Notes 3, 4 — leases rose.",
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
        "Balances held at December 31, 2025 and June 30, 2025.",
        "Q4 '25 demand held; Items 7 and 7A explain it.",
        # An initial is no scale: M&A, T-Mobile.
        "Q4 M&A activity added scale.",
        "FY2025 M&A spending rose.",
        "Services grew on Q3 T-Mobile demand.",
        # A calendar year, a quarter's year after a curly apostrophe, the other form names, and each list separator.
        "CY2025 operating income rose.",
        "Q4’25 demand held.",
        "The 6-K and the 8-K agree.",
        "The S-1 and the S-4 describe it.",
        "See Items 7 & 8.",
        "See Notes 3 to 5.",
        "See Notes 3–5.",
        "See Items 7-8.",
        "See Notes 3, 4 and 5.",
        # An abbreviation joined to a name is no unit: property, plant and equipment.
        "FY2025 PP&E additions rose on data center builds.",
        "Q4 PP&E purchases rose.",
        "June 30 PP&E balances rose.",
        "Note 9 PP&E rose.",
        "Items 7 and 7A explain the 10-K's Q4 PP&E-led capex.",
        "FY2025 BP-led demand rose.",
        "Q4 MN-based plants ran full.",
        "Q4 TN-based plant ran full.",
        # A list after a comma goes on, or its clause ends.
        "See Notes 3, 4.",
        "Leases grew (see Notes 3, 4) on new stores.",
        "See Items 7, 7A; the 10-K explains it.",
        "Notes 3, 4: leases and debt.",
        "Notes 3, 4, 5 and 6 explain it.",
        "See Notes 3, 4-5.",
        "See Notes 3, 4–5 for leases.",
        "See Items 7, 7A – Market Risk.",
        "See Notes 3, 4 - leases rose.",
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

    @pytest.mark.parametrize("current, shown", [("$54M", "$55,000,000"), ("$55.0M", "$55.0M")])
    def test_the_heros_change_is_the_tables_at_a_rounding_boundary(self, current, shown):
        # A prior shown as "$50.0M" matches a filed 50,040,000 and stays, beside a current figure the check replaces
        # or matches. The table's change is computed from the filed pair, and so is the normalized fact the hero
        # reads: from the display text it would read +10.0%.
        xbrl = {"reporting_currency": "USD", "revenue": {
            "current": {**_annual(55_000_000, "2025-09-27", "2024-09-29"), "raw_tag": REVENUE_TAG},
            "prior": {**_annual(50_040_000, "2024-09-28", "2023-10-01"), "raw_tag": REVENUE_TAG}}}
        fh = {"table": [{"metric": "Revenue", "current_period": current, "prior_period": "$50.0M"}],
              "normalized": {"metrics": [{"metric": "Revenue", "currentPeriod": current, "priorPeriod": "$50.0M", "deltaPercent": 10.0}]}}
        out = prov.enrich_financial_highlights(fh, _filing(), xbrl)
        row, fact = out["table"][0], out["normalized"]["metrics"][0]
        assert (row["current_period"], row["prior_period"], row["change_display"]) == (shown, "$50.0M", "+9.9%")
        assert f"+{fact['deltaPercent']:.1f}%" == row["change_display"]
        assert (fact["currentPeriod"], fact["currentValue"], fact["priorValue"]) == (shown, 55_000_000, 50_040_000)

    def test_two_rows_of_one_name_each_refresh_their_own_fact(self):
        # Generation writes the facts in the table's order (attach_normalized_facts), so the second "Revenue" fact is
        # the second row's: the hero never takes one row's figure beside the other's change.
        fh = {"table": [{"metric": "Revenue", "current_period": "$400.0B", "prior_period": "$391.0B"},
                        {"metric": "Revenue", "current_period": "$416.2B", "prior_period": "$391.0B"}],
              "normalized": {"metrics": [{"metric": "Revenue", "currentPeriod": "$400.0B", "priorPeriod": "$391.0B", "deltaPercent": 2.3},
                                         {"metric": "Revenue", "currentPeriod": "$416.2B", "priorPeriod": "$391.0B", "deltaPercent": 6.4}]}}
        out = prov.enrich_financial_highlights(fh, _filing(), APPLE)
        assert [row["current_period"] for row in out["table"]] == ["$416,161,000,000", "$416.2B"]
        assert [(fact["currentPeriod"], round(fact["deltaPercent"], 1)) for fact in out["normalized"]["metrics"]] == [
            ("$416,161,000,000", 6.4), ("$416.2B", 6.4)]

    def test_each_fact_refreshes_from_the_row_of_its_own_name(self):
        # Generation skips a row with no name (attach_normalized_facts), and a fact may outlive its row, so a fact is
        # paired with its row by name, never by position: past a nameless row, and beside a fact whose row is gone,
        # each fact would take its neighbour's row.
        gone = {"metric": "Revenue", "currentPeriod": "$12.0B", "priorPeriod": "$11.0B", "deltaPercent": 9.1}
        fh = {"table": [{"metric": "", "current_period": "$1.0B"},
                        {"metric": "Operating income", "current_period": "$132,100M", "prior_period": "$123,216M"},
                        {"metric": "Total net sales", "current_period": "$416.2B", "prior_period": "$391.0B"}],
              "normalized": {"metrics": [{"metric": "Operating income", "currentPeriod": "$132,100M", "priorPeriod": "$123,216M", "deltaPercent": 7.2},
                                         dict(gone),
                                         {"metric": "Total net sales", "currentPeriod": "$416.2B", "priorPeriod": "$391.0B", "deltaPercent": 6.4}]}}
        operating, kept, sales = prov.enrich_financial_highlights(fh, _filing(), APPLE)["normalized"]["metrics"]
        assert kept == gone
        assert [(fact["metric"], fact["currentPeriod"], round(fact["deltaPercent"], 1)) for fact in (operating, sales)] == [
            ("Operating income", "$133,050,000,000", 8.0), ("Total net sales", "$416.2B", 6.4)]
        assert (sales["currentValue"], sales["priorValue"]) == (416_161e6, 391_035e6)

    def test_a_fact_named_by_its_rows_capitalised_key_pairs_with_that_row(self):
        # attach_normalized_facts names a fact by its row's "metric" or "Metric", so the second "Revenue" fact is the
        # second row's: the first, a row the check never reads, keeps the fact generation stored.
        first = {"metric": "Revenue", "currentPeriod": "$400.0B", "priorPeriod": "$391.0B", "deltaPercent": 2.3}
        fh = {"table": [{"Metric": "Revenue", "current_period": "$400.0B", "prior_period": "$391.0B"},
                        {"metric": "Revenue", "current_period": "$416.2B", "prior_period": "$391.0B"}],
              "normalized": {"metrics": [dict(first),
                                         {"metric": "Revenue", "currentPeriod": "$416.2B", "priorPeriod": "$391.0B", "deltaPercent": 6.4}]}}
        kept, bound = prov.enrich_financial_highlights(fh, _filing(), APPLE)["normalized"]["metrics"]
        assert kept == first
        assert (bound["currentPeriod"], bound["currentValue"], bound["priorValue"]) == ("$416.2B", 416_161e6, 391_035e6)

    def test_a_row_whose_name_is_not_text_leaves_the_facts_as_stored(self):
        fh = {"table": [{"metric": ["Revenue"], "current_period": "$416.2B"}],
              "normalized": {"metrics": [{"metric": "Revenue", "currentPeriod": "$416.2B"}]}}
        assert prov.enrich_financial_highlights(fh, _filing(), APPLE)["normalized"]["metrics"] == [{"metric": "Revenue", "currentPeriod": "$416.2B"}]

    def test_a_fact_whose_row_the_binder_did_not_compute_is_kept(self):
        # A row the check cannot bind (a segment line) keeps the fact generation stored.
        stored = {"metric": "Services net sales", "currentPeriod": "$109.2B", "priorPeriod": "$96.2B", "deltaPercent": 13.5}
        fh = {"table": [{"metric": "Services net sales", "current_period": "$109.2B", "prior_period": "$96.2B"}],
              "normalized": {"metrics": [dict(stored)]}}
        assert prov.enrich_financial_highlights(fh, _filing(), APPLE)["normalized"]["metrics"][0] == stored

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
    prompt's Metric table (its metric, or a filing line name it quotes for the model to report), to the 6-K earnings
    prompt's headline lines, or to the narrative's grounding block is either read by ``source_metric_key`` or named
    below with why, and a label named below is one the check still leaves unread. The debt line's run-time label is
    read where it is the one the grounding gives the filing's own balance (the last case)."""

    # Concepts the check covers that it deliberately leaves unchecked.
    UNCHECKED = {"free_cash_flow": "computed, not filed", "capital_expenditures": "filers sign it either way"}
    # Prompt labels no one filed concept answers.
    UNMAPPED = {
        "eps": "per-share figures are never checked",
        "eps (diluted)": "per-share figures are never checked",
        "eps / per-ads": "per-share figures are never checked",
        "diluted eps": "per-share figures are never checked",
        "earnings per share": "per-share figures are never checked",
        "earnings per share - diluted": "per-share figures are never checked",
        "earnings per share — diluted": "per-share figures are never checked",
        "earnings per ads": "per-share figures are never checked",
        "total debt": "the current portion plus long-term debt: no one filed concept",
        "current portion of long-term debt": "the current portion alone: no standardized concept",
        "cash": "cash alone may exclude its equivalents",
    }
    # Where-to-find-it cells also name the statements a line sits in, which are no line of their own.
    STATEMENT_TITLE = re.compile(r"^(?:(?:condensed|consolidated|combined|interim)\s+)*(?:statements?\s+of\b|balance\s+sheets?\b)", re.IGNORECASE)
    # A prompt names headline lines in prose, each with the names it allows for it, as the 6-K earnings prompt does:
    # "- Revenue (or total net sales), net income (or …)". A bullet is read whole, its continuation lines with it.
    BULLET = re.compile(r"^[ \t]*[-*][ \t]+(.+(?:\n[ \t]+(?![-*][ \t]|\d+\.[ \t])\S.*)*)", re.MULTILINE)
    SYNONYMS = re.compile(r"([A-Za-z][A-Za-z ]*?)\s*\(or\s+([^)]+)\)")
    # A name a cell quotes, in double quotes or in single ones that no letter abuts (never an apostrophe).
    QUOTED = re.compile(r'["“]([^"”]+)["”]|(?<![A-Za-z])[\'‘]([^\'’]+)[\'’](?![A-Za-z])')

    def test_the_narratives_dollar_labels_map_to_their_own_concepts(self):
        from app.services.ai.xbrl_narrative import _XBRL_NARRATIVE_SPEC

        checked = set(prov._SOURCE_KEY_LABELS) - prov._NEVER_CHECKED_KEYS - set(self.UNCHECKED)
        pairs = [(label, key) for label, key, kind in _XBRL_NARRATIVE_SPEC if kind == "usd" and key in checked]
        assert len(pairs) >= 10, "the scan reads the grounding block"
        assert [(label, prov.source_metric_key(label)) for label, _ in pairs] == pairs

    @classmethod
    def table_labels(cls, text: str) -> set[str]:
        """A prompt's Metric-table labels: each row's metric and the filing line names its next cell quotes."""
        labels: set[str] = set()
        # A table's first row is its header; only a table headed "Metric" or "Metrics" lists metrics, indented or
        # not. Its first column names the metric, and its second may quote the filing's own line names, which the
        # model reports a row by.
        metric_table, previous = False, ""
        for line in (raw.strip() for raw in text.splitlines()):
            if line.startswith("|"):
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                first = cells[0].replace("*", "").strip()
                if not previous.startswith("|"):
                    metric_table = first.casefold() in {"metric", "metrics"}
                elif metric_table and first and not set(first) <= set("-: "):
                    labels.add(first)
                    quoted = [double or single for double, single in cls.QUOTED.findall(cells[1])] if len(cells) > 1 else []
                    labels.update(name for name in quoted if not cls.STATEMENT_TITLE.search(name))
            previous = line
        return labels

    @classmethod
    def headline_labels(cls, text: str) -> set[str]:
        """The headline lines a prompt names in prose, each with the names it allows for it."""
        labels: set[str] = set()
        for bullet in cls.BULLET.findall(text):
            for line, others in cls.SYNONYMS.findall(" ".join(re.sub(r"[*`]", "", bullet).split())):
                labels.update(name.strip() for name in [line, *others.split("/")])
        return labels

    def test_each_prompts_standard_metric_is_read_or_named(self):
        prompts = sorted((Path(__file__).resolve().parents[2] / "prompts").glob("*.md"))
        labels = set().union(*(self.table_labels(prompt.read_text()) | self.headline_labels(prompt.read_text()) for prompt in prompts))
        assert {"Revenue", "Cash & Equivalents", "Total Debt", "Cash", "Net earnings", "Profit for the year"} <= labels, (
            "the scan reads the prompts' metric tables and the line names they quote"
        )
        assert {"total net sales", "net profit", "earnings attributable to shareholders"} <= labels, (
            "and the 6-K earnings prompt's headline lines"
        )
        unread = sorted(label for label in labels
                        if prov.source_metric_key(label) is None and label.casefold() not in self.UNMAPPED)
        assert unread == []

    def test_the_label_reader_reads_every_table_form(self):
        text = "\n".join([
            "  | **Metrics** | Where |", "  |---|---|", '  | Revenue | "Total net sales" |', "",
            "| metric | where |", "|---|---|", "| Net income | bottom line |", "",
            "| Metric | Where |", "|---|---|", '| Cash | “Cash and equivalents”, the "Consolidated Balance Sheets", "Cash per statement" |', "",
            "| Metric | Where |", "|---|---|", "| Net sales | 'Net sales', ‘Total net revenues’, the company's line, the segment's total |", "",
            "| Segment | where |", "|---|---|", "| Services | Note 13 |",
            "- Revenue (or total net sales), net income (or net profit / earnings attributable to shareholders),",
            "  margins (or operating",
            "  margin), and growth versus the prior period.",
            "- **Operating profit** (or **EBIT**) where the filing states it.",
            "* Gross profit (or gross margin dollars) where stated.",
            "- Item 18 (or the older Item 17) holds the statements.",
        ])
        assert self.table_labels(text) == {
            "Revenue", "Total net sales", "Net income", "Cash", "Cash and equivalents", "Cash per statement", "Net sales", "Total net revenues"}
        assert self.headline_labels(text) == {
            "Revenue", "total net sales", "net income", "net profit", "earnings attributable to shareholders", "margins",
            "operating margin", "Operating profit", "EBIT", "Gross profit", "gross margin dollars"}

    def test_each_label_named_above_is_still_left_unread(self):
        # The other way round (lessons/arch-structural-gates-over-prose-rules.md): an excused label that starts mapping
        # is a figure the check reads and may mark as matching, "Total Debt" beside long-term debt's filed value, so its
        # excuse goes with it.
        from app.services.ai.xbrl_narrative import _XBRL_NARRATIVE_SPEC

        assert [label for label in self.UNMAPPED if prov.source_metric_key(label) is not None] == []
        unchecked = [prov._SOURCE_KEY_LABELS[key] for key in self.UNCHECKED]
        unchecked += [label for label, key, _kind in _XBRL_NARRATIVE_SPEC if key in self.UNCHECKED]
        assert len(unchecked) >= 4, "each unchecked concept's own label and its grounding labels"
        assert [label for label in unchecked if prov.source_metric_key(label) is not None] == []

    @pytest.mark.parametrize("tag", ["us-gaap:LongTermDebtNoncurrent", "us-gaap:LongTermDebt", "ifrs-full:NoncurrentBorrowings",
                                     "acme:TermLoans", None])
    def test_the_debt_lines_run_time_label_is_read_only_for_the_filings_own_balance(self, tag):
        # The grounding labels the debt line by the scope of its own fact at run time (debt_balance_label), never the
        # spec's static "Long-term Debt" the test above reads, so that label names the very fact this check reads, as
        # main checked it by substring: a figure that matches reads as matching, one that differs is left unchecked,
        # as long-term debt always is (_EXACT_SCOPE_TAGS). Another scope's label, which the grounding prints on its
        # component lines, names another line, and is read for none.
        from app.services.ai.debt_scope import build_debt_scope_view, debt_balance_label
        from app.services.edgar.debt_concepts import SCOPE_PHRASE

        fact = {"period": "2025-09-27", "value": 10_000e6, "form": "10-K", "currency": "USD", **({"raw_tag": tag} if tag else {})}
        xbrl = {"reporting_currency": "USD", "long_term_debt": {"current": fact}}
        label = debt_balance_label(build_debt_scope_view(xbrl))

        def check(metric, shown):
            return prov.build_metric_source({"metric": metric, "current_period": shown, "prior_period": "—"}, _filing(), xbrl, None)

        assert check(label, "$10.0B")["source_verified"] is True, label
        # Case, spacing and the kind of dash are not the label: a model may write the grounding's "—" as "-" or "–".
        for written in (f"  {label.upper()} ", label.replace(" ", "  "), label.replace(" — ", " - "), label.replace(" — ", "–"), label.replace(" — ", "—"),
                        label.replace(" — ", " -- "), label.replace(" — ", " \u2212 ")):
            assert check(written, "$10.0B")["source_verified"] is True, written
        differs = check(label, "$12.0B")
        assert differs["source_checkable"] is False and "source_mismatched" not in differs
        others = [f"Debt — {phrase}" for phrase in SCOPE_PHRASE.values()] + ["Debt Balance (maturity scope unavailable)"]
        assert [other for other in others if other != label and check(other, "$10.0B")["source_checkable"]] == []

    def test_the_swap_reads_the_debt_line_by_the_key_the_check_read(self, monkeypatch):
        # The run-time debt label maps through the grounding, not the label map, so the swap takes the check's own key:
        # were a debt tag ever a line its label names, a differing figure would be replaced, never raise.
        from app.services.ai.debt_scope import build_debt_scope_view, debt_balance_label

        monkeypatch.setitem(prov._EXACT_SCOPE_TAGS, "long_term_debt", frozenset({"LongTermDebtNoncurrent"}))
        fact = {"period": "2025-09-27", "value": 10_000e6, "form": "10-K", "currency": "USD", "raw_tag": "us-gaap:LongTermDebtNoncurrent"}
        xbrl = {"reporting_currency": "USD", "long_term_debt": {"current": fact}}
        label = debt_balance_label(build_debt_scope_view(xbrl))
        row = prov.enrich_financial_highlights({"table": [{"metric": label, "current_period": "$12.0B"}]}, _filing(), xbrl)["table"][0]
        assert (row["current_period"], row["source_replaced"]) == ("$10,000,000,000", {"current_period": "$12.0B"})


class TestScopeTagsHoldTheirSources:
    """Every tag an extraction path records for a concept the check covers is classified: a line its labels name
    (``_EXACT_SCOPE_TAGS``, which a differing figure is replaced by), or another scope, with why. A concept with one
    scope across its candidates has them pinned. A candidate added to an extractor fails here until it is classified."""

    # The candidates a concept's labels name no line of: a figure that differs from one is never replaced.
    OTHER_SCOPE = {
        "revenue": {
            "GrossInvestmentIncomeOperating": "a fund's investment income, which no revenue label names",
            "InvestmentIncomeOperating": "a fund's investment income",
            "InvestmentIncomeOperatingNet": "a fund's investment income, after expenses",
            "InvestmentIncomeNet": "a fund's investment income, after expenses",
        },
        "net_income": {
            "NetIncomeLoss": "the parent's share, where the label may name the consolidated total",
            "ProfitLoss": "the consolidated total, where the label may name the parent's share",
            "NetIncomeLossAvailableToCommonStockholdersBasic": "what is left for common stockholders",
            "ProfitLossAttributableToOwnersOfParent": "the parent's share (IFRS)",
        },
        "operating_cash_flow": {"NetCashProvidedByUsedInOperatingActivitiesContinuingOperations": "continuing operations alone"},
        "cash_and_equivalents": {
            "CashCashEquivalentsAndShortTermInvestments": "adds short-term investments",
            "Cash": "may leave out its equivalents",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": "adds restricted cash",
        },
        "shareholders_equity": {
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": "adds noncontrolling interests",
            "Equity": "IFRS total equity, which adds noncontrolling interests",
        },
        "long_term_debt": {
            "LongTermDebtNoncurrent": "noncurrent alone, where the label may add current maturities",
            "LongTermDebt": "with current maturities, where the label may mean noncurrent alone",
            "NoncurrentBorrowings": "noncurrent alone (IFRS)",
        },
    }
    # A concept whose candidates share one scope: a differing figure is replaced by any of them.
    ONE_SCOPE = {
        "gross_profit": {"GrossProfit"},
        "operating_income": {"OperatingIncomeLoss", "ProfitLossFromOperatingActivities"},
        "total_assets": {"Assets"},
        "net_interest_income": {"InterestIncomeExpenseNet"},
        "noninterest_income": {"NoninterestIncome"},
        "premiums_earned": {"PremiumsEarnedNet"},
        "net_investment_income": {"NetInvestmentIncome"},
    }

    @staticmethod
    def recorded_candidates() -> dict[str, set[str]]:
        """Every tag a path may record as ``raw_tag``: the instance extractor's candidates and financial profiles'
        anchors (``xbrl_instance.py`` records a tag for some keys only), and the companyfacts path's candidates: cash,
        whose tag it records, and the inline lists (revenue, net income, total assets among them), whose tag it does
        not today (E184). Classifying each errs on the safe side."""
        from app.services.edgar.instance.concepts import DURATION_CONCEPTS, INSTANT_CONCEPTS
        from app.services.edgar.instance.financial_profiles import FINANCIAL_PROFILES
        from app.services.edgar.xbrl_companyfacts import CASH_TAG_CANDIDATES

        out: dict[str, set[str]] = {}
        for table in (DURATION_CONCEPTS, INSTANT_CONCEPTS):
            for key, tags in table.items():
                out.setdefault(key, set()).update(tags)
        for profile in FINANCIAL_PROFILES:
            for key, anchors, _standard_concept in profile["selectors"]:
                out.setdefault(key, set()).update(anchors)
        out.setdefault("cash_and_equivalents", set()).update(CASH_TAG_CANDIDATES)
        for key, tags in TestScopeTagsHoldTheirSources.companyfacts_inline_candidates().items():
            out.setdefault(key, set()).update(tags)
        return out

    @staticmethod
    def companyfacts_inline_candidates() -> dict[str, set[str]]:
        """The companyfacts path's inline candidate lists, read from its source: each ``append_items(result, accession,
        "<key>", select_fact_data(us_gaap, accession, [<tags>], ...))`` in ``parse_company_facts``, so a tag added there
        is classified with no list to keep in step."""
        import ast
        import inspect

        from app.services.edgar import xbrl_companyfacts

        out: dict[str, set[str]] = {}
        for node in ast.walk(ast.parse(inspect.getsource(xbrl_companyfacts.parse_company_facts))):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "append_items" and len(node.args) == 4):
                continue
            key, select = node.args[2], node.args[3]
            if isinstance(key, ast.Constant) and isinstance(select, ast.Call) and len(select.args) >= 3:
                tags = select.args[2]
                assert isinstance(tags, ast.List), f"{key.value}: read its candidates from a literal list"
                out.setdefault(key.value, set()).update(element.value for element in tags.elts)
        return out

    def test_the_companyfacts_inline_lists_are_read(self):
        candidates = self.companyfacts_inline_candidates()
        assert {"revenue", "net_income", "total_assets"} <= set(candidates)
        assert candidates["total_assets"] == {"Assets"}
        assert "RevenueFromContractWithCustomerExcludingAssessedTax" in candidates["revenue"]
        assert "NetIncomeLoss" in candidates["net_income"]

    def test_each_concept_the_check_covers_is_classified(self):
        covered = (set(metric_delta_service._STRICT_XBRL_KEYS.values()) | set(prov._SOURCE_EXTRA_KEYS.values())) - prov._NEVER_CHECKED_KEYS
        assert covered == set(prov._EXACT_SCOPE_TAGS) | set(self.ONE_SCOPE)
        assert set(self.OTHER_SCOPE) <= set(prov._EXACT_SCOPE_TAGS)

    def test_each_tag_a_path_records_is_a_named_line_or_another_scope(self):
        candidates = self.recorded_candidates()
        for key, named in prov._EXACT_SCOPE_TAGS.items():
            other = set(self.OTHER_SCOPE.get(key, {}))
            assert candidates[key] - named - other == set(), f"{key}: classify each new candidate"
            assert named & other == set(), key
        for key, tags in self.ONE_SCOPE.items():
            assert candidates[key] == tags, f"{key}: a new candidate may be another scope"

    def test_each_candidate_keeps_its_tag_and_filing_through_normalisation(self):
        # The figure check reads a fact's scope from its tag and its source from its filing: normalise_series, which
        # every standardized series passes through, keeps both for every candidate a path records (E184).
        from app.services.edgar.xbrl_standardized import normalise_series

        for key, tags in self.recorded_candidates().items():
            for tag in sorted(tags):
                entry = {"period": "2025-06-28", "value": 1.0, "form": "10-Q", "currency": "USD",
                         "raw_tag": f"us-gaap:{tag}", "accn": "0000320193-25-000073"}
                [kept] = normalise_series([entry])
                assert (kept["raw_tag"], kept["accn"]) == (entry["raw_tag"], entry["accn"]), (key, tag)

    def test_the_companyfacts_path_records_each_facts_filing(self):
        # Each companyfacts entry names the filing that reported it, the cash entry its tag too, and normalisation keeps
        # them: the series match can refuse another filing's fact.
        from app.services.edgar.xbrl_companyfacts import parse_company_facts
        from app.services.edgar.xbrl_standardized import normalise_series

        accn = "0000320193-25-000073"
        fact = {"end": "2025-06-28", "val": 5.0, "form": "10-Q", "accn": accn, "fy": 2025, "fp": "Q3", "filed": "2025-08-01"}
        us_gaap = {"Assets": {"units": {"USD": [fact]}},
                   "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [fact]}},
                   "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
                       {**fact, "start": "2025-03-30"}]}},
                   "NetIncomeLoss": {"units": {"USD": [{**fact, "start": "2025-03-30"}]}}}
        parsed = parse_company_facts({"facts": {"us-gaap": us_gaap}}, accn)
        for key in ("total_assets", "cash_and_equivalents", "revenue", "net_income"):
            [kept] = normalise_series(parsed[key])
            assert kept["accn"] == accn, key
        assert normalise_series(parsed["cash_and_equivalents"])[0]["raw_tag"] == "us-gaap:CashAndCashEquivalentsAtCarryingValue"


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

    FORGED_EVIDENCE = {"verified": True, "excerpt": "We expect", "fragment_url": "https://evil.example/#:~:text=We"}

    @pytest.mark.parametrize("cached", [None, "   "])
    def test_cites_no_passage_without_filing_text_to_search(self, cached):
        # No cached filing text: the passes must not crash, and no passage is cited at all, since a "Quote not
        # found" or "Section linked" chip would report a search that never ran (the frontend review of #1530). A
        # quote's or footnote's evidence the stored JSON carries is the model's, so it is dropped too.
        raw = self._raw()
        raw["sections"]["results_that_matter"]["table"][0]["commentary_evidence"] = {"verified": True, "excerpt": "x"}
        for item in [*raw["sections"]["forward_signals"]["quotes"], *raw["sections"]["notable_footnotes"]]:
            item["evidence"] = dict(self.FORGED_EVIDENCE)
        out = prov.enrich_raw_summary(raw, _filing(critical_excerpt=cached))
        assert all("evidence" not in quote for quote in out["sections"]["forward_signals"]["quotes"])
        assert all("evidence" not in footnote for footnote in out["sections"]["notable_footnotes"])
        assert "commentary_evidence" not in out["sections"]["results_that_matter"]["table"][0]
        rendered = [block for section in prov.render_sections_json(out) for block in section["blocks"]]
        assert {"quote", "table", "metrics"} <= {block["kind"] for block in rendered}
        assert not any(block.get("evidence") or any(block.get("row_evidence") or []) for block in rendered)
        assert not any(row.get("commentary_evidence") for block in rendered for row in block.get("metric_rows") or [])

    @pytest.mark.parametrize("cached", [None, "SRC"])
    def test_a_v1_footnote_keeps_no_stored_evidence(self, cached):
        # v1 footnotes render through v2's table (``_footnotes_table_block``), and no pass searches them, so the
        # stored JSON's own evidence would show a found passage; footnotes alone still reach the drop.
        raw = {"schema_version": 1, "sections": {"notable_footnotes": [
            {"item": "Leases", "impact": "Higher", "evidence": dict(self.FORGED_EVIDENCE)}]}}
        out = prov.enrich_raw_summary(raw, _filing(critical_excerpt=self.SRC if cached else None))
        assert "evidence" not in out["sections"]["notable_footnotes"][0]
        tables = [block for section in prov.render_sections_json(out) for block in section["blocks"] if block["kind"] == "table"]
        assert [table["rows"] for table in tables] == [[["Leases", "Higher"]]]
        assert not any(evidence for table in tables for evidence in table.get("row_evidence") or [])

    def test_a_footnote_with_nothing_to_cite_keeps_no_stored_evidence(self):
        raw = self._raw()
        raw["sections"]["notable_footnotes"] = [{"item": "Leases", "impact": "None", "evidence": dict(self.FORGED_EVIDENCE)}]
        raw["sections"]["forward_signals"]["quotes"].append({"speaker": "CFO", "evidence": dict(self.FORGED_EVIDENCE)})
        out = prov.enrich_raw_summary(raw, _filing(critical_excerpt=self.SRC))
        assert "evidence" not in out["sections"]["notable_footnotes"][0]
        assert "evidence" not in out["sections"]["forward_signals"]["quotes"][-1]

    @pytest.mark.parametrize("surfaces", [("forward_signals",), ("notable_footnotes",), ("forward_signals", "notable_footnotes")])
    def test_quotes_and_footnotes_enriched_without_risks_or_metrics_table(self, surfaces):
        # Guard regression: a v2 summary with ONLY quotes, ONLY footnotes, or both (no risks list, no metrics table)
        # must still get citation enrichment — the pre-T4 early-return only checked risks/metrics. And with no filing
        # text to search, each one's stored evidence is dropped, never returned as found.
        given = {
            "forward_signals": {
                "source_section_ref": "Item 7",
                "quotes": [{"speaker": "CEO", "quote": "We expect double-digit revenue growth in fiscal 2025."}],
            },
            "notable_footnotes": [
                {"item": "SBC", "impact": "up", "supporting_evidence": "Stock-based compensation expense was recognized over the vesting period"},
            ],
        }
        item = {"forward_signals": lambda section: section["quotes"][0], "notable_footnotes": lambda section: section[0]}
        raw = {"schema_version": 2, "sections": {name: copy.deepcopy(given[name]) for name in surfaces}}
        out = prov.enrich_raw_summary(copy.deepcopy(raw), _filing(critical_excerpt=self.SRC))
        assert [item[name](out["sections"][name])["evidence"]["verified"] for name in surfaces] == [True] * len(surfaces)
        for name in surfaces:
            item[name](raw["sections"][name])["evidence"] = dict(self.FORGED_EVIDENCE)
        out = prov.enrich_raw_summary(raw, _filing(critical_excerpt=None))
        assert [name for name in surfaces if "evidence" in item[name](out["sections"][name])] == []

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
