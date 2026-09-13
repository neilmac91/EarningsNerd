"""Explicit company applicability through source extraction and the real cash presentation owner."""
import copy
import inspect
import json
from functools import cached_property
from types import SimpleNamespace

import pytest
from edgar.entity.core import Company

from app.config import settings
from app.services.edgar import xbrl_service
from app.services.edgar.instance_extractor import cash_financial_classification
from app.services.copilot_service import _compact_xbrl_block
from app.services.openai_service import OpenAIService
from evals.runner import _xbrl_to_text
from tests.unit.test_financing_source import ACC, CIK, instance_xml, parsed_filing
from tests.unit.test_cash_claims import LEADS, METRICS, RETAINED_METRICS, assert_owned, filled


@pytest.mark.parametrize("sic,category,profile,expected", [
    ("7372", "Operating Company", None, False),
    ("6021", "Bank", None, True),
    ("6311", "Insurance Company", "insurer", True),
    ("6799", "BDC", "bdc", True),
    ("6282", "Investment Manager", "financial_generic", True),
    ("6021", None, None, True),
    ("7372", "Insurance Company", None, True),
    ("7372", "Operating Company", "insurer", True),
    ("7372", None, None, None),
    (None, "Operating Company", None, None),
    ("", "Operating Company", None, None),
    ("0000", "Operating Company", None, None),
    ("9999", "Operating Company", None, None),
    ("9995", "Operating Company", None, None),
    ("7372garbage", "Operating Company", None, None),
    (True, "Operating Company", None, None),
])
def test_explicit_classification_not_missing_bank_inference(sic, category, profile, expected):
    company = SimpleNamespace(**({"business_category": category} if category is not None else {}))
    result = cash_financial_classification(company, sic, profile)
    assert result["is_financial"] is expected


def test_sdk_category_is_really_cached_and_unavailable_property_is_not_invoked():
    assert isinstance(inspect.getattr_static(Company, "business_category"), cached_property)

    class Unavailable:
        @property
        def business_category(self):
            raise AssertionError("must not trigger lazy classification")

    assert cash_financial_classification(Unavailable(), "7372")["is_financial"] is None


def source_metrics(monkeypatch, sic, category, profile):
    extra = "".join(
        f'<us-gaap:{concept} contextRef="{ref}" unitRef="usd" decimals="0">{value}</us-gaap:{concept}>'
        for concept, values in (
            ("NetCashProvidedByUsedInOperatingActivities", (12116000000, 7918000000)),
            ("PaymentsToAcquireProductiveAssets", (1343000000, 860000000)),
        ) for ref, value in zip(("c", "p"), values)
    )
    filing, _ = parsed_filing(instance_xml(extra=extra))
    company = SimpleNamespace(sic=sic, **({"business_category": category} if category is not None else {}))
    resolutions = []

    def resolve(*args):
        resolutions.append(args)
        return company, [filing]

    monkeypatch.setattr(xbrl_service, "resolve_filing_by_accession", resolve)
    monkeypatch.setattr(settings, "USE_STATEMENT_FINANCIALS", True)
    monkeypatch.setattr(settings, "RICHER_FINANCIALS_ENABLED", True)
    # The classification/profile inputs are explicit controls, not claims about this fixture issuer.
    monkeypatch.setattr(xbrl_service, "extract_financial_statement_metrics",
                        lambda *args: (profile, {}, ()) if profile else None)
    raw = xbrl_service._extract_from_filing_instance_sync(CIK, ACC)
    assert len(resolutions) == 1
    metrics = xbrl_service.EdgarXBRLService().extract_standardized_metrics(raw)
    assert metrics["financial_classification"] == raw["financial_classification"]
    assert "series" not in metrics["financial_classification"]
    return raw, metrics


@pytest.mark.asyncio
@pytest.mark.parametrize("sic,category,profile,eligible", [
    ("7372", "Operating Company", None, True),
    ("6311", "Insurance Company", "insurer", False),
    ("6799", "BDC", "bdc", False),
    ("6282", "Investment Manager", "financial_generic", False),
    (None, "Operating Company", None, False),
    ("9999", "Operating Company", None, False),
    ("7372", None, None, False),
])
async def test_selected_source_to_final_preview_rejects_financial_and_unknown(monkeypatch, sic, category, profile, eligible):
    raw, metrics = source_metrics(monkeypatch, sic, category, profile)
    assert not {"net_interest_income", "noninterest_income"}.intersection(metrics)
    assert metrics["free_cash_flow"]["current"]["value"] == 10773000000
    service = OpenAIService()
    supplied = {"metadata": {}, "sections": {"the_print": copy.deepcopy(LEADS[1])}}

    requests = []

    async def request(*args, **kwargs):
        requests.append(copy.deepcopy(args[0]))
        return json.dumps(supplied)

    monkeypatch.setattr(service, "_request_content", request)
    result = await service.summarize_filing("Selected source.", "Controlled company", "10-K",
                                            xbrl_metrics=metrics, filing_excerpt="Selected source.")
    actual = result["raw_summary"]["sections"]["the_print"]["key_takeaways"][2]
    preview = service._partial_markdown_preview(json.dumps(supplied), metrics)
    if eligible:
        assert_owned(actual)
        assert_owned(preview)
    else:
        assert actual == LEADS[1]["key_takeaways"][2]
        assert "Conventional free cash flow was" not in preview
    # The pre-existing cash card is unchanged; classification governs only the new lead qualifier.
    absent = {key: value for key, value in metrics.items() if key != "financial_classification"}
    assert filled(metrics)["earnings_quality"] == filled(absent)["earnings_quality"]
    with_classification = requests[:]
    requests.clear()
    await service.summarize_filing("Selected source.", "Controlled company", "10-K",
                                   xbrl_metrics=absent, filing_excerpt="Selected source.")
    assert len(requests) > 1  # Both generator and ordinary missing-section recovery were exercised.
    assert with_classification == requests
    assert _xbrl_to_text(metrics) == _xbrl_to_text(absent)
    assert _compact_xbrl_block(raw) == _compact_xbrl_block({k: v for k, v in raw.items() if k != "financial_classification"})


def test_exact_retained_metrics_remain_unknown_without_retrofitted_evidence():
    assert "financial_classification" not in RETAINED_METRICS
    assert filled(RETAINED_METRICS)["the_print"] == LEADS[1]
    assert filled(RETAINED_METRICS)["earnings_quality"] == filled(METRICS)["earnings_quality"]


@pytest.mark.asyncio
async def test_persisted_preclassification_metrics_return_without_fetch(monkeypatch):
    payload = {"revenue": [{"period": "2025-12-31", "value": 100, "form": "10-K"}]}
    service = xbrl_service.EdgarXBRLService()
    monkeypatch.setattr(service, "_persisted_xbrl", lambda *args: payload)

    async def forbidden(*args):
        raise AssertionError("historical data must not force a source fetch")

    monkeypatch.setattr(service, "_fetch_xbrl_data", forbidden)
    raw = await service.get_xbrl_data(ACC, CIK)
    assert raw is payload
    assert "financial_classification" not in service.extract_standardized_metrics(raw)
