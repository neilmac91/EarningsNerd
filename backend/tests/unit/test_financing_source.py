"""Financing provenance from an actual parsed instance through the existing winning extraction."""
from types import SimpleNamespace

import pytest
from edgar.xbrl import XBRL

from app.config import settings
from app.services.edgar import xbrl_service
from app.services.edgar.instance_extractor import duration_series_with_starts
from app.services.edgar.financing_source import financing_comparison_source

ACC = "0001099590-25-000001"
CIK = "0001099590"
CONCEPT = "NetCashProvidedByUsedInFinancingActivities"


def instance_xml(*, current=2904, prior=1959, older=-267, prior_start="2024-01-01",
                 qualifier="", prior_entity=CIK, prior_currency="USD", concept=CONCEPT,
                 extra=""):
    contexts = []
    for ref, year, start, entity in [
        ("c", 2025, "2025-01-01", CIK), ("p", 2024, prior_start, prior_entity),
        ("o", 2023, "2023-01-01", CIK),
    ]:
        segment = qualifier if ref == "p" and "segment" in qualifier else ""
        scenario = qualifier if ref == "p" and "scenario" in qualifier else ""
        contexts.append(
            f'<context id="{ref}"><entity><identifier scheme="http://www.sec.gov/CIK">'
            f'{entity}</identifier>{segment}</entity><period><startDate>{start}</startDate>'
            f'<endDate>{year}-12-31</endDate></period>{scenario}</context>')
    return ('<xbrl xmlns="http://www.xbrl.org/2003/instance" '
            'xmlns:us-gaap="http://fasb.org/us-gaap/2025" '
            'xmlns:iso4217="http://www.xbrl.org/2003/iso4217" '
            'xmlns:xbrldi="http://xbrl.org/2006/xbrldi">'
            + ''.join(contexts)
            + '<unit id="usd"><measure>iso4217:USD</measure></unit>'
            + f'<unit id="priorunit"><measure>iso4217:{prior_currency}</measure></unit>'
            + '<us-gaap:Revenues contextRef="c" unitRef="usd" decimals="0">10000</us-gaap:Revenues>'
            + ''.join(f'<us-gaap:{concept} contextRef="{ref}" unitRef="{unit}" decimals="0">'
                      f'{value}</us-gaap:{concept}>'
                      for ref, unit, value in [("c", "usd", current), ("p", "priorunit", prior),
                                               ("o", "usd", older)])
            + extra + '</xbrl>')


def parsed_filing(xml, *, cached=True):
    xb = XBRL()
    xb.parser.parse_instance_content(xml)
    attachment = SimpleNamespace(document_type="EX-101.INS", extension=".xml",
                                 sgml_document=SimpleNamespace(content=xml))
    filing = SimpleNamespace(form="10-K", period_of_report="2025-12-31", xbrl=lambda: xb)
    if cached:
        filing._sgml = SimpleNamespace(attachments=SimpleNamespace(data_files=[attachment]))
    return filing, xb


def extract(monkeypatch, xml, *, cached=True):
    filing, xb = parsed_filing(xml, cached=cached)
    monkeypatch.setattr(settings, "RICHER_FINANCIALS_ENABLED", True)
    company = SimpleNamespace(sic="7372", is_financial_institution=lambda: False)
    monkeypatch.setattr(xbrl_service, "resolve_filing_by_accession", lambda *a: (company, [filing]))
    raw = xbrl_service._extract_from_filing_instance_sync(CIK, ACC)
    return raw, filing, xb


@pytest.mark.parametrize("current,prior", [(2904, 1959), (2, -1), (-2, 1), (-2, -1), (0, 0)])
def test_selected_financing_pair_survives_standardization_without_direction_inference(monkeypatch, current, prior):
    raw, _filing, _xb = extract(monkeypatch, instance_xml(current=current, prior=prior))
    sidecar = raw["financing_comparison_source"]
    assert sidecar["accession"] == ACC and sidecar["period_of_report"] == "2025-12-31"
    assert sidecar["current"] == {
        "value": float(current), "period_start": "2025-01-01", "period_end": "2025-12-31",
        "currency": "USD", "raw_tag": f"us-gaap:{CONCEPT}", "entity_identifier": CIK,
        "entity_scheme": "http://www.sec.gov/CIK", "context_refs": ["c"],
        "scope": "issuer_undimensioned",
    }
    assert sidecar["prior"]["value"] == float(prior)
    assert sidecar["prior"]["context_refs"] == ["p"]
    assert sidecar["prior"]["period_end"] == "2024-12-31"
    normalized = xbrl_service.EdgarXBRLService().extract_standardized_metrics(raw)
    assert normalized["financing_comparison_source"] == sidecar
    assert normalized["financing_cash_flow"]["current"]["value"] == float(current)
    assert "series" not in normalized["financing_comparison_source"]
    from app.services.facts_service import normalize_standardized_to_facts
    facts = normalize_standardized_to_facts(1, 1, ACC, "10-K", normalized)
    assert all(point["concept"] != "financing_comparison_source" for point in facts)


@pytest.mark.parametrize("qualifier", [
    '<scenario><xbrldi:explicitMember dimension="us-gaap:SomeAxis">us-gaap:SomeMember</xbrldi:explicitMember></scenario>',
    '<scenario><xbrldi:typedMember dimension="us-gaap:SomeAxis"><us-gaap:Member>x</us-gaap:Member></xbrldi:typedMember></scenario>',
    '<segment><us-gaap:OtherQualifier>parent-only</us-gaap:OtherQualifier></segment>',
])
def test_unparsed_context_qualifiers_do_not_certify_or_substitute_older_period(monkeypatch, qualifier):
    raw, _filing, _xb = extract(monkeypatch, instance_xml(qualifier=qualifier))
    # SDK can omit these qualifiers. Ordinary metric selection stays intact; positive certification abstains.
    assert raw["financing_cash_flow"][1]["value"] == 1959
    assert "financing_comparison_source" not in raw


def test_missing_cached_xml_never_fetches_a_descriptor(monkeypatch):
    raw, filing, xb = extract(monkeypatch, instance_xml(), cached=False)
    assert "financing_comparison_source" not in raw
    assert raw["financing_cash_flow"][0]["value"] == 2904
    selected = []
    duration_series_with_starts(xb, [CONCEPT], "10-K", "2025-12-31", selected_sources=selected)
    # A URL-only attachment must never have its content getter invoked.
    class Remote:
        document_type, extension, sgml_document = "EX-101.INS", ".xml", None

        @property
        def content(self):
            pytest.fail("extra source request")
    filing._sgml = SimpleNamespace(attachments=SimpleNamespace(data_files=[Remote()]))
    assert financing_comparison_source(filing, selected, accession=ACC, form="10-K",
                                      period_of_report="2025-12-31", cik=CIK) is None


def test_conflicting_issuer_context_abstains(monkeypatch):
    raw, _filing, _xb = extract(monkeypatch, instance_xml(prior_entity="0000000001"))
    assert raw["financing_cash_flow"][1]["value"] == 1959
    assert "financing_comparison_source" not in raw


def test_continuing_operations_identity_is_preserved(monkeypatch):
    concept = CONCEPT + "ContinuingOperations"
    raw, _filing, _xb = extract(monkeypatch, instance_xml(concept=concept))
    assert raw["financing_comparison_source"]["current"]["raw_tag"] == f"us-gaap:{concept}"


def test_ambiguous_duplicate_source_duration_stays_unavailable(monkeypatch):
    extra = (f'<context id="p2"><entity><identifier scheme="http://www.sec.gov/CIK">{CIK}'
             '</identifier></entity><period><startDate>2024-01-05</startDate>'
             '<endDate>2024-12-31</endDate></period></context>'
             f'<us-gaap:{CONCEPT} contextRef="p2" unitRef="usd" decimals="0">1959</us-gaap:{CONCEPT}>')
    raw, _filing, _xb = extract(monkeypatch, instance_xml(extra=extra))
    assert raw["financing_cash_flow"][1]["value"] == 1959
    assert "period_start" not in raw["financing_cash_flow"][1]
    assert "financing_comparison_source" not in raw


def test_source_identity_mismatch_abstains_without_alternate_selection():
    filing, xb = parsed_filing(instance_xml())
    selected = []
    duration_series_with_starts(xb, [CONCEPT], "10-K", "2025-12-31", selected_sources=selected)
    for field, bad in [("currency", "EUR"), ("raw_tag", "us-gaap:Revenues"),
                       ("period_start", "2024-10-01")]:
        corrupted = [{**point} for point in selected]
        corrupted[1][field] = bad
        assert financing_comparison_source(filing, corrupted, accession=ACC, form="10-K",
                                          period_of_report="2025-12-31", cik=CIK) is None
