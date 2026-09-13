"""Retained MELI source metadata and lead text, with actual generation/render owners."""
import copy
import json
from types import SimpleNamespace

import pytest

from app.services.openai_service import OpenAIService
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.export_service import ExportService
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION
from app.services.ai.fi_signals import fi_components_present

# Exact selected cash metrics and lead strings from PR833 third assessment results 50/51.
METRICS = json.loads(r'''{"operating_cash_flow": {"current": {"period": "2025-12-31", "value": 12116000000.0, "form": "10-K", "currency": "USD", "period_start": "2025-01-01", "raw_tag": null}, "prior": {"period": "2024-12-31", "value": 7918000000.0, "form": "10-K", "currency": "USD", "period_start": "2024-01-01", "raw_tag": null}, "change": {"absolute": 4198000000.0, "percentage": 53.02, "direction": "increase"}, "series": [{"period": "2025-12-31", "value": 12116000000.0, "form": "10-K", "currency": "USD", "period_start": "2025-01-01", "raw_tag": null}, {"period": "2024-12-31", "value": 7918000000.0, "form": "10-K", "currency": "USD", "period_start": "2024-01-01", "raw_tag": null}, {"period": "2023-12-31", "value": 5140000000.0, "form": "10-K", "currency": "USD", "period_start": "2023-01-01", "raw_tag": null}]}, "capital_expenditures": {"current": {"period": "2025-12-31", "value": 1343000000.0, "form": "10-K", "currency": "USD", "period_start": "2025-01-01", "raw_tag": "us-gaap:PaymentsToAcquireProductiveAssets"}, "prior": {"period": "2024-12-31", "value": 860000000.0, "form": "10-K", "currency": "USD", "period_start": "2024-01-01", "raw_tag": "us-gaap:PaymentsToAcquireProductiveAssets"}, "change": {"absolute": 483000000.0, "percentage": 56.16, "direction": "increase"}, "series": [{"period": "2025-12-31", "value": 1343000000.0, "form": "10-K", "currency": "USD", "period_start": "2025-01-01", "raw_tag": "us-gaap:PaymentsToAcquireProductiveAssets"}, {"period": "2024-12-31", "value": 860000000.0, "form": "10-K", "currency": "USD", "period_start": "2024-01-01", "raw_tag": "us-gaap:PaymentsToAcquireProductiveAssets"}, {"period": "2023-12-31", "value": 509000000.0, "form": "10-K", "currency": "USD", "period_start": "2023-01-01", "raw_tag": "us-gaap:PaymentsToAcquireProductiveAssets"}]}, "free_cash_flow": {"current": {"period": "2025-12-31", "value": 10773000000.0, "form": "10-K"}, "prior": {"period": "2024-12-31", "value": 7058000000.0, "form": "10-K"}, "change": {"absolute": 3715000000.0, "percentage": 52.64, "direction": "increase"}, "series": [{"period": "2025-12-31", "value": 10773000000.0, "form": "10-K"}, {"period": "2024-12-31", "value": 7058000000.0, "form": "10-K"}, {"period": "2023-12-31", "value": 4631000000.0, "form": "10-K"}]}, "reporting_currency": "USD"}''')
LEADS = json.loads(r'''[{"headline": "Net revenues and financial income rose 39.1% to $28.9B in FY2025, while net income grew 4.5% to $2.0B and diluted EPS reached $39.40 as gross margin contracted 1.6 pts to 44.5%.", "key_takeaways": ["Net revenues and financial income increased 39.1% to $28.9B, with Fintech revenues up 46.2% to $12.6B and Commerce revenues up 34.0% to $16.3B.", "Net income rose 4.5% to $2.0B and diluted EPS increased to $39.40 from $37.69, as operating margin declined to 11.1% from 12.7%.", "Operating cash flow increased 53.0% to $12.1B, while total assets grew 69.3% to $42.7B and loans receivable, net, rose to $9.4B.", "Provision for doubtful accounts increased 66.4% to $3.1B, driven by 61% growth in credit originations."], "what_changed": "The filing reflects a reclassification of certain Mercado Pago financial results into net revenues and cost of net revenues, and reports a 39.1% revenue increase alongside margin compression from a lower free-shipping threshold in Brazil and higher credit-loss provisions.", "tone": "neutral", "source_section_ref": "Item 7. MD&A"}, {"headline": "MercadoLibre reported net revenues and financial income of $28.9B for FY2025, up 39.1% YoY, with net income of $2.0B and diluted EPS of $39.40.", "key_takeaways": ["Net revenues and financial income rose 39.1% to $28.9B, driven by a 46.2% increase in Fintech revenues to $12.6B and a 34.0% increase in Commerce revenues to $16.3B.", "Net income increased 4.5% to $2.0B while diluted EPS rose to $39.40 from $37.69, as operating margin declined to 11.1% from 12.7%.", "Operating cash flow increased to $12.1B from $7.9B, and free cash flow (OCF less capex) rose to $10.8B from $7.1B.", "Total assets grew to $42.7B from $25.2B, with loans receivable, net increasing to $9.4B from $4.9B."], "what_changed": "The filing reflects a change in presentation of certain financial results, reclassifying interest income and expenses related to Mercado Pago's regulated operations from 'Other income (expenses)' to 'Net services revenues and financial income' and 'Cost of net revenues and financial expenses,' with 2023 results recast for consistency.", "tone": "neutral", "source_section_ref": "Item 7. MD&A"}]''')
MIXED_LEADS = json.loads(r'''[{"headline": "Net revenues and financial income rose 39.1% to $28.9B in FY2025, but net income grew only 4.5% to $2.0B as gross margin compressed to 44.5% and the provision for doubtful accounts climbed 66.4%.", "key_takeaways": ["Net revenues and financial income of $28.9B (+39.1% YoY) with Fintech revenues up 46.2% to $12.6B and Commerce revenues up 34.0% to $16.3B.", "Net income of $2.0B (+4.5% YoY) and diluted EPS of $39.40, with net margin falling to 6.9% from 9.2%.", "Operating cash flow of $12.1B and free cash flow of $10.8B, while total assets grew to $42.7B from $25.2B."], "what_changed": "Fintech overtook Commerce as the faster-growing revenue stream and the company reclassified certain Mercado Pago financial results into revenue and cost of revenue, recasting 2023 comparatives.", "tone": "neutral", "source_section_ref": "Item 7. MD&A"}, {"headline": "Net revenues and financial income rose 39.1% to $28.9B in FY2025, but net income grew only 4.5% to $2.0B as gross margin fell to 44.5% and the provision for doubtful accounts climbed 66.4%.", "key_takeaways": ["Net revenues and financial income of $28.9B (+39.1% YoY) with Fintech revenues up 46.2% to $12.6B and Commerce revenues up 34.0% to $16.3B.", "Net income of $2.0B (+4.5% YoY) and diluted EPS of $39.40, with net margin compressing to 6.9% from 9.2%.", "Operating cash flow of $12.1B (+53.0% YoY) and free cash flow of $10.8B, while total assets grew 69.3% to $42.7B.", "Provision for doubtful accounts rose 66.4% to $3.1B, tied to 61% originations growth, and the effective tax rate rose to 29.7% from 21.4%."], "what_changed": "FY2025 marks a shift toward fintech-led revenue growth and heavier credit provisioning, with gross and operating margins contracting versus FY2024 despite 39.1% top-line growth.", "tone": "neutral", "source_section_ref": "Item 7. MD&A - Results of operations"}]''')
CLAIM = LEADS[1]["key_takeaways"][2]


def filled(metrics=None, lead=None):
    service = object.__new__(OpenAIService)
    sections = {"the_print": copy.deepcopy(LEADS[1] if lead is None else lead)}
    service._apply_structured_fallbacks(sections, {}, copy.deepcopy(METRICS if metrics is None else metrics))
    return sections


def assert_owned(text):
    assert "Conventional free cash flow was $10.8B for 2025-01-01 to 2025-12-31" in text
    assert "compared with $7.1B for 2024-01-01 to 2024-12-31" in text
    assert "not an issuer-defined or discretionary-cash measure" in text
    assert CLAIM not in text


@pytest.mark.asyncio
@pytest.mark.parametrize("input_lead", [LEADS[1], *MIXED_LEADS])
async def test_retained_claim_reaches_final_preview_and_four_surfaces(monkeypatch, input_lead):
    service = OpenAIService()
    supplied = {"metadata": {}, "sections": {"the_print": copy.deepcopy(input_lead)}}

    async def request(*args, **kwargs):
        return json.dumps(supplied)

    monkeypatch.setattr(service, "_request_content", request)
    result = await service.summarize_filing("Selected filing source.", "MercadoLibre", "10-K",
                                            xbrl_metrics=copy.deepcopy(METRICS), filing_excerpt="Selected filing source.")
    raw = result["raw_summary"]
    lead = raw["sections"]["the_print"]
    assert_owned(lead["key_takeaways"][2])
    original_claim = input_lead["key_takeaways"][2]
    if ", while " in original_claim:
        suffix = original_claim[original_claim.index(", while "):]
        assert lead["key_takeaways"][2].endswith(suffix)
        assert ")., while" not in lead["key_takeaways"][2]
    for key in ("headline", "what_changed", "tone", "source_section_ref"):
        assert lead[key] == input_lead[key]
    assert lead["key_takeaways"][:2] == input_lead["key_takeaways"][:2]
    assert lead["key_takeaways"][3:] == input_lead["key_takeaways"][3:]
    assert_owned(service._partial_markdown_preview(json.dumps(supplied), copy.deepcopy(METRICS)))
    raw["schema_version"] = SUMMARY_SCHEMA_VERSION
    summary = SimpleNamespace(raw_summary=raw, id=1, filing_id=1, business_overview=result["business_overview"],
                              financial_highlights={}, risk_factors=[], management_discussion="", key_changes="",
                              schema_version=SUMMARY_SCHEMA_VERSION, prompt_version=None)
    filing = SimpleNamespace(company=SimpleNamespace(name="MercadoLibre"), filing_type="10-K",
                             filing_date=None, period_end_date=None, sec_url="", document_url="")
    exporter = ExportService()
    rendered = render_sections(raw)
    for text in (sections_to_markdown(rendered), exporter.generate_pdf_html(summary, filing),
                 exporter.generate_csv(summary, filing), json.dumps([section.to_dict() for section in rendered], ensure_ascii=False)):
        assert_owned(text)


def test_retained_unrelated_lead_stays_byte_identical():
    assert filled(lead=LEADS[0])["the_print"] == LEADS[0]


@pytest.mark.parametrize("key", ["headline", "what_changed", "whatChanged", "key_takeaways", "keyTakeaways", "string"])
def test_every_rendered_lead_slot_uses_same_owner(key):
    lead = CLAIM if key == "string" else {key: ["Unrelated useful statement.", CLAIM] if "akeaways" in key else CLAIM}
    rendered = filled(lead=lead)["the_print"]
    value = rendered if key == "string" else rendered[key]
    if isinstance(value, list):
        assert value[0] == "Unrelated useful statement."
        value = value[1]
    assert_owned(value)


@pytest.mark.parametrize("mutation", ["missing_currency", "wrong_currency", "start", "end", "missing_capex", "bad_formula"])
def test_uncertified_selected_components_never_reauthor(mutation):
    metrics = copy.deepcopy(METRICS)
    if mutation == "missing_currency":
        metrics.pop("reporting_currency")
    elif mutation == "wrong_currency":
        metrics["capital_expenditures"]["prior"]["currency"] = "EUR"
    elif mutation == "start":
        metrics["capital_expenditures"]["current"]["period_start"] = "2025-10-01"
    elif mutation == "end":
        metrics["free_cash_flow"]["prior"]["period"] = "2023-12-31"
    elif mutation == "missing_capex":
        metrics.pop("capital_expenditures")
    else:
        metrics["free_cash_flow"]["current"]["value"] += 1000000
    assert filled(metrics)["the_print"] == LEADS[1]


@pytest.mark.parametrize("claim", [CLAIM.replace("$10.8B", "$11.8B"), CLAIM.replace("$10.8B", "EUR 10.8B"),
                                   CLAIM.replace("free cash flow", "adjusted free cash flow"),
                                   CLAIM + " This proves discretionary cash expanded."])
def test_ineligible_whole_claim_is_not_substring_rewritten(claim):
    assert filled(lead={"headline": claim})["the_print"]["headline"] == claim


def test_standalone_conventional_claim_and_bank_suppression():
    standalone = "Free cash flow (OCF less capex) rose to $10.8B from $7.1B."
    assert_owned(filled(lead={"headline": standalone})["the_print"]["headline"])
    metrics = copy.deepcopy(METRICS)
    metrics["net_interest_income"] = {"current": {"value": 100}}
    metrics["interest_expense"] = {"current": {"value": 50}}
    assert fi_components_present(metrics)
    assert filled(metrics)["the_print"] == LEADS[1]


@pytest.mark.parametrize("change", ["wrong_growth", "wrong_sign", "quarterly", "different_start", "extra_clause"])
def test_mixed_cash_growth_requires_its_own_real_annual_operands(change):
    claim = MIXED_LEADS[1]["key_takeaways"][2]
    metrics = copy.deepcopy(METRICS)
    if change == "wrong_growth":
        claim = claim.replace("53.0%", "54.0%")
    elif change == "wrong_sign":
        claim = claim.replace("+53.0%", "-53.0%")
    elif change == "quarterly":
        for key in ("operating_cash_flow", "capital_expenditures"):
            for period, year in (("current", 2025), ("prior", 2024)):
                metrics[key][period]["period_start"] = f"{year}-10-01"
    elif change == "different_start":
        for key in ("operating_cash_flow", "capital_expenditures"):
            metrics[key]["prior"]["period_start"] = "2023-12-30"
    else:
        claim += " This certifies discretionary cash."
    assert filled(metrics, {"headline": claim})["the_print"]["headline"] == claim


def test_preserved_assets_suffix_is_not_claimed_as_certified():
    # Even deliberately different asset figures are retained verbatim: only the cash prefix is owned.
    for original in MIXED_LEADS:
        claim = original["key_takeaways"][2].replace("$42.7B", "$999.0B")
        output = filled(lead={"headline": claim})["the_print"]["headline"]
        assert_owned(output)
        assert output.endswith(claim[claim.index(", while "):])


@pytest.mark.parametrize("claim", [
    "Operating cash flow was $12.1B, up from $7.9B, and free cash flow (OCF minus capex) was $10.8B, up from $7.1B.",
    "Operating cash flow rose to $12.1B from $7.9B, and free cash flow (OCF less capex) reached $10.8B versus $7.1B.",
])
def test_latest_retained_current_prior_connectors(claim):
    # Exact second PR837 MELI takeaway text; operands equal the retained METRICS above.
    assert_owned(filled(lead={"headline": claim})["the_print"]["headline"])
    wrong = claim.replace("$10.8B", "$11.8B")
    assert filled(lead={"headline": wrong})["the_print"]["headline"] == wrong
