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
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.export_service import ExportService
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION
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
    # Both derived cash owners now require affirmative nonfinancial classification.
    absent = {key: value for key, value in metrics.items() if key != "financial_classification"}
    assert ("cash_conversion" in filled(metrics).get("earnings_quality", {})) is eligible
    assert "cash_conversion" not in filled(absent).get("earnings_quality", {})
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
    assert "cash_conversion" not in filled(RETAINED_METRICS).get("earnings_quality", {})
    assert "cash_conversion" in filled(METRICS)["earnings_quality"]


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


# Exact selected current rows/classification from PR842 results 6 (JPM) and 32 (COIN).
RETAINED_FINANCIAL = {'JPM': {'net_income': {'current': {'period': '2025-12-31', 'value': 57048000000.0, 'form': '10-K', 'currency': 'USD', 'period_start': '2025-01-01', 'raw_tag': None}}, 'operating_cash_flow': {'current': {'period': '2025-12-31', 'value': -147782000000.0, 'form': '10-K', 'currency': 'USD', 'period_start': '2025-01-01', 'raw_tag': None}}, 'investing_cash_flow': {'current': {'period': '2025-12-31', 'value': -265565000000.0, 'form': '10-K', 'currency': 'USD', 'period_start': '2025-01-01', 'raw_tag': None}}, 'financing_cash_flow': {'current': {'period': '2025-12-31', 'value': 269533000000.0, 'form': '10-K', 'currency': 'USD', 'period_start': '2025-01-01', 'raw_tag': None}}, 'net_interest_income': {'current': {'period': '2025-12-31', 'value': 95443000000.0, 'form': '10-K', 'currency': None, 'raw_tag': 'us-gaap:InterestIncomeExpenseNet'}}, 'noninterest_income': {'current': {'period': '2025-12-31', 'value': 87004000000.0, 'form': '10-K', 'currency': None, 'raw_tag': 'us-gaap:NoninterestIncome'}}, 'reporting_currency': 'USD', 'financial_classification': {'is_financial': True, 'sic': '6021', 'profile': 'bank', 'business_category': 'Bank'}}, 'COIN': {'net_income': {'current': {'period': '2026-03-31', 'value': -394117000.0, 'form': '10-Q', 'currency': 'USD', 'fiscal_year': 2026, 'fiscal_period': 'Q1', 'period_start': '2026-01-01', 'raw_tag': None}}, 'operating_cash_flow': {'current': {'period': '2026-03-31', 'value': 182744000.0, 'form': '10-Q', 'currency': 'USD', 'fiscal_year': 2026, 'fiscal_period': 'Q1', 'period_start': '2026-01-01', 'raw_tag': None}}, 'investing_cash_flow': {'current': {'period': '2026-03-31', 'value': -239064000.0, 'form': '10-Q', 'currency': 'USD', 'fiscal_year': 2026, 'fiscal_period': 'Q1', 'period_start': '2026-01-01', 'raw_tag': None}}, 'financing_cash_flow': {'current': {'period': '2026-03-31', 'value': -864907000.0, 'form': '10-Q', 'currency': 'USD', 'fiscal_year': 2026, 'fiscal_period': 'Q1', 'period_start': '2026-01-01', 'raw_tag': None}}, 'reporting_currency': 'USD', 'financial_classification': {'is_financial': True, 'sic': '6199', 'profile': 'financial_generic', 'business_category': 'Operating Company'}}}


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["COIN", "JPM", "nonfinancial", "unknown", "bank_veto"])
async def test_cash_card_applicability_preserves_basic_flows_across_surfaces(monkeypatch, case):
    metrics = copy.deepcopy(RETAINED_FINANCIAL[case if case in RETAINED_FINANCIAL else "COIN"])
    if case == "nonfinancial" or case == "bank_veto":
        # Controlled eligibility only; never relabel the actual retained COIN observation.
        metrics["financial_classification"] = {"is_financial": False}
    elif case == "unknown":
        metrics.pop("financial_classification")
    if case == "bank_veto":
        metrics["net_interest_income"] = {"current": {"value": 1}}
    eligible = case == "nonfinancial"
    supplied = {"metadata": {}, "sections": {
        "earnings_quality": {"cash_conversion": "UNTRUSTED MODEL CARD", "red_flags": ["Preserved disclosure."]},
    }}
    service = OpenAIService()

    async def request(*args, **kwargs):
        return json.dumps(supplied)

    monkeypatch.setattr(service, "_request_content", request)
    result = await service.summarize_filing("Selected source.", case, "10-Q",
        xbrl_metrics=metrics, filing_excerpt="Selected source.")
    raw = result["raw_summary"]
    eq = raw["sections"]["earnings_quality"]
    assert ("cash_conversion" in eq) is eligible
    assert eq["red_flags"] == ["Preserved disclosure."]
    raw["schema_version"] = SUMMARY_SCHEMA_VERSION
    summary = SimpleNamespace(raw_summary=raw, id=1, filing_id=1, business_overview=result["business_overview"],
        financial_highlights={}, risk_factors=[], management_discussion="", key_changes="",
        schema_version=SUMMARY_SCHEMA_VERSION, prompt_version=None)
    filing = SimpleNamespace(company=SimpleNamespace(name=case), filing_type="10-Q",
        filing_date=None, period_end_date=None, sec_url="", document_url="")
    rendered = render_sections(raw)
    exporter = ExportService()
    texts = [service._partial_markdown_preview(json.dumps(supplied), metrics),
        sections_to_markdown(rendered), exporter.generate_pdf_html(summary, filing),
        exporter.generate_csv(summary, filing), json.dumps([s.to_dict() for s in rendered])]
    for text in texts:
        assert "UNTRUSTED MODEL CARD" not in text
        assert ("Operating cash flow was positive despite a net loss." in text) is eligible
        assert "Preserved disclosure." in text
        for amount in (("$-147.8B", "$-265.6B", "$269.5B") if case == "JPM"
                       else ("$182.7M", "$-239.1M", "$-864.9M")):
            assert amount in text
