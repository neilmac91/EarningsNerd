"""Unit tests for Trace-to-Source provenance enrichment."""

import copy
from types import SimpleNamespace
from urllib.parse import unquote

from app.services import provenance_service as prov


def _filing(document_url="https://www.sec.gov/Archives/edgar/data/320193/000.../aapl.htm",
            sec_url="https://www.sec.gov/Archives/edgar/data/320193/000.../",
            critical_excerpt=None, markdown_content=None):
    cache = None
    if critical_excerpt is not None or markdown_content is not None:
        cache = SimpleNamespace(
            critical_excerpt=critical_excerpt, markdown_content=markdown_content
        )
    return SimpleNamespace(document_url=document_url, sec_url=sec_url, content_cache=cache)


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


class TestBuildRiskSource:
    SOURCE = "Supply chain constraints persisted through Q3 of fiscal 2024."

    def test_verified_builds_text_fragment_link(self):
        risk = {
            "summary": "Supply concentration",
            "supporting_evidence": 'Item 1A: "Supply chain constraints persisted through Q3"',
            "source_section_ref": "Item 1A. Risk Factors",
        }
        out = prov.build_risk_source(risk, _filing(), prov.normalize_for_match(self.SOURCE))
        assert out["source_verified"] is True
        assert "#:~:text=" in out["source_url"]
        assert out["source_section_ref"] == "Item 1A. Risk Factors"

    def test_unverified_links_to_plain_document(self):
        risk = {
            "summary": "Some risk",
            "supporting_evidence": '"This sentence is not anywhere in the filing text at all"',
            "source_section_ref": "Item 1A. Risk Factors",
        }
        out = prov.build_risk_source(risk, _filing(), prov.normalize_for_match(self.SOURCE))
        assert out["source_verified"] is False
        assert "#:~:text=" not in out["source_url"]
        assert out["source_url"].endswith("aapl.htm")

    def test_falls_back_to_sec_url_when_no_document_url(self):
        risk = {"summary": "r", "supporting_evidence": "x", "source_section_ref": None}
        filing = _filing(document_url=None)
        out = prov.build_risk_source(risk, filing, None)
        assert out["source_url"] == filing.sec_url

    def test_no_url_when_filing_has_no_links(self):
        out = prov.build_risk_source(
            {"supporting_evidence": "x"}, _filing(document_url=None, sec_url=None), None
        )
        assert out["source_url"] is None


class TestEnrichRawSummary:
    def _raw(self):
        return {
            "sections": {
                "risk_factors": [
                    {
                        "summary": "Supply concentration",
                        "supporting_evidence": 'Item 1A: "Supply chain constraints persisted through Q3"',
                        "source_section_ref": "Item 1A. Risk Factors",
                    }
                ],
                "executive_snapshot": "unchanged",
            }
        }

    def test_enriches_and_does_not_mutate_input(self):
        raw = self._raw()
        filing = _filing(critical_excerpt="Supply chain constraints persisted through Q3 of 2024.")
        out = prov.enrich_raw_summary(raw, filing)

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
        assert prov.enrich_raw_summary({"sections": {}}, _filing()) == {"sections": {}}

    def test_uses_markdown_when_no_critical_excerpt(self):
        raw = self._raw()
        filing = _filing(markdown_content="...Supply chain constraints persisted through Q3...")
        out = prov.enrich_raw_summary(raw, filing)
        assert out["sections"]["risk_factors"][0]["source_verified"] is True


class TestEnrichSummaryProvenance:
    def test_shapes_response_and_enriches_both_paths(self):
        risk = {
            "summary": "r",
            "supporting_evidence": 'Item 1A: "Supply chain constraints persisted through Q3"',
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
        "revenue": {"current": {"period": "2024-09-28", "value": 391035000000.0, "form": "10-K"}},
        "net_income": {"current": {"value": 93736000000.0}},
        "total_assets": {"current": {"value": 364980000000.0}},
    }

    def test_verified_when_xbrl_value_appears(self):
        row = {"metric": "Total Revenue", "current_period": "$391.0B", "prior_period": "$383.3B"}
        out = prov.build_metric_source(row, _filing(), self.XBRL, "Item 8. Financial Statements")
        assert out["source_verified"] is True
        assert out["xbrl_concept"] == "Revenue"
        assert out["source_section_ref"] == "Item 8. Financial Statements"
        assert out["source_url"].endswith("aapl.htm")

    def test_unverified_when_value_does_not_match(self):
        row = {"metric": "Revenue", "current_period": "$999.9B"}
        out = prov.build_metric_source(row, _filing(), self.XBRL, None)
        assert out["source_verified"] is False
        assert out["xbrl_concept"] is None
        assert out["source_url"].endswith("aapl.htm")  # still linked, just not "verified"

    def test_unmapped_metric_gets_link_only(self):
        row = {"metric": "Diluted EPS", "current_period": "$6.13"}
        out = prov.build_metric_source(row, _filing(), self.XBRL, None)
        assert out["source_verified"] is False
        assert out["source_url"].endswith("aapl.htm")

    def test_no_xbrl_data(self):
        row = {"metric": "Total Revenue", "current_period": "$391.0B"}
        out = prov.build_metric_source(row, _filing(), None, None)
        assert out["source_verified"] is False

    def test_small_value_not_verified(self):
        # Below the million threshold the rendering match is ambiguous -> never claimed verified.
        xbrl = {"net_income": {"current": {"value": 1234.0}}}
        row = {"metric": "Net income", "current_period": "1,234"}
        out = prov.build_metric_source(row, _filing(), xbrl, None)
        assert out["source_verified"] is False


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
