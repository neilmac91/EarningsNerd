"""Unit tests for the EDGAR full-text search (EFTS) integration."""

import httpx
import pytest

from app.integrations.sec_api import (
    SECFullTextSearchClient,
    _build_urls,
    _coerce_int,
    _first_str,
    _parse_display_name,
)

# A representative EFTS response. `root_form` is the canonical form even when the
# matched document is an exhibit (`file_type` = "EX-21.1").
SAMPLE_PAYLOAD = {
    "hits": {
        "total": {"value": 2, "relation": "eq"},
        "hits": [
            {
                "_id": "0000320193-23-000106:aapl-20230930.htm",
                "_source": {
                    "ciks": ["0000320193"],
                    "display_names": ["Apple Inc. (AAPL) (CIK 0000320193)"],
                    "root_form": "10-K",
                    "file_type": "10-K",
                    "file_date": "2023-11-03",
                    "period_ending": "2023-09-30",
                },
            },
            {
                "_id": "0001045810-24-000029:nvda-20240128.htm",
                "_source": {
                    "ciks": ["0001045810"],
                    "display_names": ["NVIDIA CORP (NVDA) (CIK 0001045810)"],
                    "root_form": "10-K",
                    "file_type": "EX-21.1",
                    "file_date": "2024-02-21",
                    "period_ending": "2024-01-28",
                },
            },
        ],
    }
}


class TestParseResponse:
    def test_valid_payload(self):
        result = SECFullTextSearchClient._parse_response("going concern", SAMPLE_PAYLOAD)

        assert result.query == "going concern"
        assert result.total == 2
        assert len(result.hits) == 2

        aapl = result.hits[0]
        assert aapl.accession_no == "0000320193-23-000106"
        assert aapl.document == "aapl-20230930.htm"
        assert aapl.form == "10-K"
        assert aapl.filed_date == "2023-11-03"
        assert aapl.period_ending == "2023-09-30"
        assert aapl.cik == "0000320193"
        assert aapl.company == "Apple Inc."
        assert aapl.ticker == "AAPL"
        assert aapl.sec_url == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/"
        assert aapl.document_url == aapl.sec_url + "aapl-20230930.htm"

    def test_root_form_preferred_over_exhibit_file_type(self):
        result = SECFullTextSearchClient._parse_response("q", SAMPLE_PAYLOAD)
        nvda = result.hits[1]
        # Matched doc is an exhibit, but the filing's form is the 10-K.
        assert nvda.form == "10-K"
        assert nvda.ticker == "NVDA"

    def test_empty_payloads(self):
        assert SECFullTextSearchClient._parse_response("q", {}).total == 0
        assert SECFullTextSearchClient._parse_response("q", {}).hits == []

        payload = {"hits": {"total": {"value": 0}, "hits": []}}
        res = SECFullTextSearchClient._parse_response("q", payload)
        assert res.total == 0
        assert res.hits == []

    def test_invalid_payloads(self):
        assert SECFullTextSearchClient._parse_response("q", None).hits == []
        assert SECFullTextSearchClient._parse_response("q", "nope").hits == []
        assert SECFullTextSearchClient._parse_response("q", {"hits": "bad"}).total == 0


class TestParseHit:
    def test_id_without_document(self):
        hit = SECFullTextSearchClient._parse_hit(
            {
                "_id": "0000320193-23-000106",
                "_source": {"ciks": ["0000320193"], "root_form": "8-K", "file_date": "2023-01-01"},
            }
        )
        assert hit is not None
        assert hit.accession_no == "0000320193-23-000106"
        assert hit.document is None
        assert hit.sec_url.endswith("/000032019323000106/")
        assert hit.document_url == hit.sec_url  # no document → index URL

    def test_missing_or_bad_id_returns_none(self):
        assert SECFullTextSearchClient._parse_hit({"_source": {}}) is None
        assert SECFullTextSearchClient._parse_hit({"_id": ""}) is None
        assert SECFullTextSearchClient._parse_hit(None) is None
        assert SECFullTextSearchClient._parse_hit("nope") is None

    def test_falls_back_to_file_type_when_no_root_form(self):
        hit = SECFullTextSearchClient._parse_hit(
            {
                "_id": "0000320193-23-000106:doc.htm",
                "_source": {"ciks": ["0000320193"], "file_type": "424B5"},
            }
        )
        assert hit is not None
        assert hit.form == "424B5"


class TestDisplayNameParsing:
    def test_with_ticker(self):
        assert _parse_display_name("Apple Inc. (AAPL) (CIK 0000320193)") == ("Apple Inc.", "AAPL")

    def test_dotted_class_ticker(self):
        assert _parse_display_name("BERKSHIRE HATHAWAY INC (BRK.A) (CIK 0001067983)") == (
            "BERKSHIRE HATHAWAY INC",
            "BRK.A",
        )

    def test_share_class_parentheses_not_truncated(self):
        # A parenthesised share class in the name must be preserved, not eaten.
        assert _parse_display_name("Alphabet Inc. (Class A) (GOOGL) (CIK 0001652044)") == (
            "Alphabet Inc. (Class A)",
            "GOOGL",
        )

    def test_non_ticker_token_folded_into_name(self):
        # A trailing parenthesised phrase that isn't ticker-shaped stays in the name.
        assert _parse_display_name("Foo Trust (Series 2020) (CIK 0001234567)") == (
            "Foo Trust (Series 2020)",
            None,
        )

    def test_without_ticker_only_cik(self):
        # Funds / individuals often have only the CIK group, no ticker.
        assert _parse_display_name("SOME TRUST (CIK 0001234567)") == ("SOME TRUST", None)

    def test_empty(self):
        assert _parse_display_name(None) == (None, None)
        assert _parse_display_name("") == (None, None)


class TestBuildUrls:
    def test_strips_zeros_and_joins(self):
        sec_url, doc_url = _build_urls("0000320193", "0000320193-23-000106", "aapl-20230930.htm")
        assert sec_url == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/"
        assert doc_url == sec_url + "aapl-20230930.htm"

    def test_no_document_falls_back_to_index(self):
        sec_url, doc_url = _build_urls("0000320193", "0000320193-23-000106", None)
        assert doc_url == sec_url

    def test_missing_inputs(self):
        assert _build_urls(None, "0000320193-23-000106", "x.htm") == (None, None)
        assert _build_urls("0000320193", "", "x.htm") == (None, None)


class TestBuildParams:
    def test_minimal(self):
        assert SECFullTextSearchClient._build_params("test", None, None, None, None, 0) == {
            "q": "test"
        }

    def test_full(self):
        params = SECFullTextSearchClient._build_params(
            "test", "10-K,10-Q", "2023-01-01", "2023-12-31", "0000320193", 20
        )
        assert params == {
            "q": "test",
            "forms": "10-K,10-Q",
            "startdt": "2023-01-01",
            "enddt": "2023-12-31",
            "ciks": "0000320193",
            "from": 20,
        }


class TestHelpers:
    def test_coerce_int(self):
        assert _coerce_int(5) == 5
        assert _coerce_int("5") == 5
        assert _coerce_int(None) is None
        assert _coerce_int("x") is None

    def test_first_str(self):
        assert _first_str(["a", "b"]) == "a"
        assert _first_str([" ", "b"]) == "b"
        assert _first_str([]) is None
        assert _first_str("not a list") is None
        assert _first_str(None) is None


class TestSearchAsync:
    @pytest.mark.asyncio
    async def test_returns_parsed_results_and_sends_request(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["user_agent"] = request.headers.get("user-agent")
            return httpx.Response(200, json=SAMPLE_PAYLOAD)

        client = SECFullTextSearchClient(transport=httpx.MockTransport(handler))
        result = await client.search(query="going concern", forms="10-K", from_offset=10)

        assert result.total == 2
        assert len(result.hits) == 2
        assert result.hits[0].ticker == "AAPL"

        assert "going" in captured["url"]
        assert "forms=10-K" in captured["url"]
        assert "from=10" in captured["url"]
        assert captured["user_agent"]  # SEC-required descriptive UA present

    @pytest.mark.asyncio
    async def test_raises_on_server_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "boom"})

        client = SECFullTextSearchClient(transport=httpx.MockTransport(handler))
        with pytest.raises(httpx.HTTPStatusError):
            await client.search(query="x")

    @pytest.mark.asyncio
    async def test_rate_limited_raises(self, monkeypatch):
        import app.integrations.sec_api as sec_api_module
        from app.services.sec_rate_limiter import SECRateLimiter, SECRateLimitError

        # Fast limiter so the retry loop doesn't sleep for real seconds.
        fast_limiter = SECRateLimiter(max_retries=2, base_backoff_seconds=0.001)
        monkeypatch.setattr(sec_api_module, "sec_rate_limiter", fast_limiter)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "rate limited"})

        client = SECFullTextSearchClient(transport=httpx.MockTransport(handler))
        with pytest.raises(SECRateLimitError):
            await client.search(query="x")
