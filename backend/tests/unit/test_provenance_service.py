"""Unit tests for Trace-to-Source provenance enrichment."""

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

    def test_verifies_quoted_excerpt_case_and_whitespace_insensitive(self):
        evidence = 'Item 1A: "Supply   chain constraints persisted through Q3"'
        assert prov.verify_excerpt_in_text(evidence, self.SOURCE) is True

    def test_unverified_when_not_present(self):
        assert prov.verify_excerpt_in_text('"A totally fabricated sentence not in the filing"', self.SOURCE) is False

    def test_unverified_when_too_short(self):
        # Below the min-length gate -> never claimed as verified even if technically a substring.
        assert prov.verify_excerpt_in_text('"Q3"', self.SOURCE) is False

    def test_unverified_without_source_text(self):
        assert prov.verify_excerpt_in_text('"Supply chain constraints persisted through Q3"', None) is False


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
        out = prov.build_risk_source(risk, _filing(), self.SOURCE)
        assert out["source_verified"] is True
        assert "#:~:text=" in out["source_url"]
        assert out["source_section_ref"] == "Item 1A. Risk Factors"

    def test_unverified_links_to_plain_document(self):
        risk = {
            "summary": "Some risk",
            "supporting_evidence": '"This sentence is not anywhere in the filing text at all"',
            "source_section_ref": "Item 1A. Risk Factors",
        }
        out = prov.build_risk_source(risk, _filing(), self.SOURCE)
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
        summary = SimpleNamespace(
            id=7,
            filing_id=42,
            business_overview="bo",
            financial_highlights={"table": []},
            risk_factors=[
                {
                    "summary": "r",
                    "supporting_evidence": 'Item 1A: "Supply chain constraints persisted through Q3"',
                    "source_section_ref": "Item 1A. Risk Factors",
                }
            ],
            management_discussion="md",
            key_changes="kc",
            raw_summary={
                "sections": {
                    "risk_factors": [
                        {
                            "summary": "r",
                            "supporting_evidence": 'Item 1A: "Supply chain constraints persisted through Q3"',
                            "source_section_ref": "Item 1A. Risk Factors",
                        }
                    ]
                }
            },
        )
        filing = _filing(critical_excerpt="Supply chain constraints persisted through Q3 of 2024.")
        out = prov.enrich_summary_provenance(summary, filing)

        assert out["id"] == 7 and out["filing_id"] == 42
        assert out["risk_factors"][0]["source_verified"] is True
        assert out["raw_summary"]["sections"]["risk_factors"][0]["source_verified"] is True

    def test_no_filing_is_safe(self):
        summary = SimpleNamespace(
            id=1, filing_id=1, business_overview=None, financial_highlights=None,
            risk_factors=None, management_discussion=None, key_changes=None, raw_summary=None,
        )
        out = prov.enrich_summary_provenance(summary, None)
        assert out["risk_factors"] is None and out["raw_summary"] is None
