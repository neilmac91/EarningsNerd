"""Unit tests for Trace-to-Source provenance enrichment."""

import copy
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


CNY_REVENUE = 941_168_000_000.0
USD_REVENUE = 391_035_000_000.0
BANK_NII = 95_443_000_000.0


def _revenue_facts(value, point_currency, reporting_currency):
    """Standardized metrics whose revenue point carries ``point_currency`` (None leaves it off, as the
    statement path does) on a filing whose ``reporting_currency`` is ``reporting_currency``."""
    current = {"value": value, "period": "2025-03-31"}
    if point_currency is not None:
        current["currency"] = point_currency
    metrics = {"revenue": {"current": current}}
    if reporting_currency is not None:
        metrics["reporting_currency"] = reporting_currency
    return metrics


class TestBuildMetricSourceCurrency:
    """The chip verifies a figure only in the matched fact's currency (F61 call 1).

    The fact's currency is its own point's, else the filing's ``reporting_currency``, else USD, the
    backend's domestic default (``money_prefix_for(None)`` writes "$"). The cell's label is read with
    the display grammar, scalar by scalar and in the cell's own case. A cell that names no currency
    still verifies on its number alone. A refused row stays checkable, so the tally counts it.
    """

    @pytest.mark.parametrize("value, point, reporting, cell", [
        pytest.param(CNY_REVENUE, "CNY", "CNY", "$941.2B", id="cny-fact-in-dollars"),
        pytest.param(CNY_REVENUE, "CNY", "CNY", "US$941.2B", id="cny-fact-in-us-dollars"),
        pytest.param(CNY_REVENUE, "USD", "USD", "CNY 941.2B", id="usd-fact-in-cny"),
        pytest.param(USD_REVENUE, "USD", "USD", "CNY 391.0B", id="usd-fact-in-cny-391"),
        pytest.param(USD_REVENUE, "USD", "USD", "RMB 391.0B", id="usd-fact-in-rmb"),
        # The point names no currency, so the filing's reporting currency decides.
        pytest.param(CNY_REVENUE, None, "CNY", "$941.2B", id="filing-cny-in-dollars"),
        # Nothing names one, so the domestic default (USD) decides.
        pytest.param(CNY_REVENUE, None, None, "CNY 941.2B", id="unknown-in-cny"),
        # A bare "¥" is JPY or CNY, so it names no code; the exact-delta binder refuses it the same way.
        pytest.param(CNY_REVENUE, "CNY", "CNY", "¥941.2B", id="cny-fact-in-bare-yen"),
        # Not one scalar, so the whole-cell reader names nothing; the scalar that renders it says "$".
        pytest.param(CNY_REVENUE, "CNY", "CNY", "$941.2 billion, up 8.3%", id="cny-fact-in-dollar-prose"),
        # AED reads in capitals only, so a lowercased cell would read it as unlabelled.
        pytest.param(CNY_REVENUE, "USD", "USD", "AED 941.2B", id="usd-fact-in-capital-only-code"),
        # The rendering figure is unlabelled, and the only label in the cell is another currency's.
        pytest.param(CNY_REVENUE, "CNY", "CNY", "941.2B, or US$130.4B", id="unlabelled-beside-dollars"),
    ])
    def test_a_figure_labelled_in_another_currency_is_checked_but_never_verified(
        self, value, point, reporting, cell
    ):
        row = {"metric": "Revenue", "current_period": cell}
        out = prov.build_metric_source(row, _filing(), _revenue_facts(value, point, reporting), None)
        assert (out["source_checkable"], out["source_verified"], out["xbrl_concept"]) == (True, False, None)

    @pytest.mark.parametrize("value, point, reporting, cell", [
        pytest.param(CNY_REVENUE, "CNY", "CNY", "CNY 941.2B", id="cny-in-cny"),
        pytest.param(CNY_REVENUE, "CNY", "CNY", "RMB 941.2B", id="cny-in-rmb"),
        pytest.param(CNY_REVENUE, "CNY", "CNY", "RMB 941.2B (≈US$130.4B, convenience translation)",
                     id="cny-with-labelled-convenience"),
        pytest.param(CNY_REVENUE, "CNY", "CNY", "941.2B", id="cny-unlabelled"),
        pytest.param(CNY_REVENUE, None, "CNY", "CNY 941.2B", id="filing-cny-in-cny"),
        pytest.param(USD_REVENUE, "USD", "USD", "$391.0B", id="usd-in-dollars"),
        pytest.param(USD_REVENUE, "USD", "USD", "US$391.0B", id="usd-in-us-dollars"),
        pytest.param(USD_REVENUE, "usd", None, "usd 391.0b", id="usd-in-lowercase-code"),
        pytest.param(USD_REVENUE, None, None, "$391.0B", id="unknown-in-dollars"),
        pytest.param(USD_REVENUE, None, None, "391.0B", id="unknown-unlabelled"),
        # The statement-path bank cell (test_bank_component_coverage.py): a grouped figure and its date.
        pytest.param(BANK_NII, None, "USD", "$95,443,000,000 (2025-12-31)", id="bank-grouped-with-date"),
    ])
    def test_a_figure_in_its_facts_currency_or_unlabelled_is_verified(self, value, point, reporting, cell):
        row = {"metric": "Revenue", "current_period": cell}
        out = prov.build_metric_source(row, _filing(), _revenue_facts(value, point, reporting), None)
        assert (out["source_checkable"], out["source_verified"], out["xbrl_concept"]) == (True, True, "Revenue")

    MATRIX = ["USD", "CNY", "EUR", "JPY", "AED"]

    @pytest.mark.parametrize("label", MATRIX)
    @pytest.mark.parametrize("fact", MATRIX)
    def test_a_figure_is_sec_verified_only_in_its_facts_currency(self, fact, label):
        """Rule 12 gate for "a figure is never SEC-verified in another currency": every fact currency
        against every label ``money_prefix_for`` writes. Before the check all 25 were verified."""
        from app.utils.numbers import money_prefix_for

        cell = f"{money_prefix_for(label)}941.2B"
        out = prov.build_metric_source(
            {"metric": "Revenue", "current_period": cell}, _filing(), _revenue_facts(CNY_REVENUE, fact, fact), None
        )
        assert out["source_checkable"] is True
        assert out["source_verified"] is (fact == label), cell


def test_the_summary_read_verifies_a_cny_filings_figure_only_in_cny():
    """``GET /api/summaries/filing/{id}`` builds the chip from the filing's stored XBRL, whose points
    carry their currency: a CNY filing's "$941.2B" revenue row is checked but not verified, and its
    "CNY 941.2B" row is verified."""
    from fastapi.testclient import TestClient

    from app.database import SessionLocal
    from app.models import Filing, Summary
    from main import app
    from tests.support.summary_stream_harness import seed_company_filing

    xbrl = {"reporting_currency": "CNY", "revenue": [{
        "period": "2025-03-31", "start": "2024-04-01", "value": CNY_REVENUE, "currency": "CNY",
        "form": "20-F", "fy": 2025, "fp": "FY", "accn": "stored",
    }]}
    filings = {}
    for cell in ("$941.2B", "CNY 941.2B"):
        filing_id = seed_company_filing(filing_type="20-F")
        with SessionLocal() as db:
            db.get(Filing, filing_id).xbrl_data = xbrl
            db.add(Summary(filing_id=filing_id, business_overview="Stored analysis.", raw_summary={"sections": {}},
                           financial_highlights={"table": [
                               {"metric": "Revenue", "current_period": cell, "prior_period": "", "commentary": "x"}]}))
            db.commit()
        filings[cell] = filing_id

    with TestClient(app) as client:
        rows = {cell: client.get(f"/api/summaries/filing/{filing_id}").json()["financial_highlights"]["table"][0]
                for cell, filing_id in filings.items()}

    def chip(row):
        return row["current_period"], row["source_checkable"], row["source_verified"], row["xbrl_concept"]

    assert chip(rows["$941.2B"]) == ("$941.2B", True, False, None)
    assert chip(rows["CNY 941.2B"]) == ("CNY 941.2B", True, True, "Revenue")


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
