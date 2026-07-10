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
                    "supporting_evidence": 'Item 1A: "Supply chain constraints persisted through Q3"',
                    "source_section_ref": "Item 1A. Risk Factors",
                }],
            },
        }
        filing = _filing(critical_excerpt="Supply chain constraints persisted through Q3 of 2024.")
        xbrl = {"revenue": {"current": {"value": 391035000000.0}}}
        out = prov.enrich_raw_summary(raw, filing, xbrl_standardized=xbrl)

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

    def test_tolerates_missing_source_text(self):
        # No cached filing text -> nothing verifies, but the passes must not crash and must degrade to
        # section-level "Cited".
        out = prov.enrich_raw_summary(self._raw(), _filing())
        assert out["sections"]["forward_signals"]["quotes"][0]["evidence"]["verified"] is False

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
