"""Characterization test (anchor T9) for the SEC company-facts fallback parser.

Everywhere else the fallback parser is exercised with hand-built single-concept
dicts (see ``test_statement_extraction.py::test_company_facts_*``). This test
instead feeds a checked-in, realistic *recorded* SEC ``companyfacts`` payload
(``tests/fixtures/companyfacts_sample.json`` — a multi-filing, multi-period,
multi-concept document for a fictional large-cap issuer) through the PRODUCTION
parser ``EdgarXBRLService._parse_company_facts`` and pins the extracted metrics.

Production call sequence (from ``_fallback_to_company_facts``):

    data = <companyfacts JSON>                     # facts.us-gaap.<Concept>.units.<unit>[]
    result = service._parse_company_facts(data, target_accession)

``_parse_company_facts`` returns a dict of six metric buckets::

    {"revenue", "net_income", "total_assets",
     "total_liabilities", "cash_and_equivalents", "earnings_per_share"}

each a list of ``{"period", "value", "form", "accn"}`` newest-period-first.
``select_fact_data`` is a nested helper inside ``_parse_company_facts`` (concept
selection) and is not called directly. ``extract_standardized_metrics`` is the
real downstream consumer that shapes the buckets into current/prior/change/series.

The fixture is designed so the run exercises the parser's three non-trivial
behaviors on realistic data:
  * target-accession restriction — only the FY2023 10-K's reported periods surface,
    even though the payload also carries the FY2022 10-K's facts;
  * stale-concept anti-shadowing — the live
    ``RevenueFromContractWithCustomerExcludingAssessedTax`` tag wins over the
    retired ``Revenues`` tag (last used FY2019);
  * EPS candidate order — Basic is preferred over Diluted on a period-end tie.
"""

import json
from pathlib import Path

import pytest

from app.services.edgar.xbrl_service import EdgarXBRLService

pytestmark = pytest.mark.unit

# The fixture's most recent 10-K (FY2023). Its facts are the ones the parser must
# surface; the payload also contains the prior FY2022 10-K + retired-tag history.
TARGET_ACCESSION = "0001789012-24-000031"

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "companyfacts_sample.json"


@pytest.fixture(scope="module")
def companyfacts() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


@pytest.fixture
def parsed(companyfacts: dict) -> dict:
    return EdgarXBRLService()._parse_company_facts(companyfacts, TARGET_ACCESSION)


def test_output_schema_is_the_six_metric_buckets(parsed: dict):
    """The parser returns exactly these buckets, in this order, each a list."""
    assert list(parsed.keys()) == [
        "revenue",
        "net_income",
        "total_assets",
        "total_liabilities",
        "cash_and_equivalents",
        "earnings_per_share",
    ]
    assert all(isinstance(v, list) for v in parsed.values())


def test_revenue_series_matches_fixture(parsed: dict):
    # Full-dict equality pins period + value + form + accn together. The live
    # contract-revenue tag is chosen; the retired `Revenues` tag (FY2019, 12.88B)
    # is NOT allowed to shadow it, and only the target 10-K's three reported
    # income-statement years surface (FY2020 exists under the prior filing but is
    # dropped by the target-accession restriction).
    assert parsed["revenue"] == [
        {"period": "2023-12-31", "value": 24_318_000_000, "form": "10-K", "accn": TARGET_ACCESSION},
        {"period": "2022-12-31", "value": 21_704_000_000, "form": "10-K", "accn": TARGET_ACCESSION},
        {"period": "2021-12-31", "value": 18_225_000_000, "form": "10-K", "accn": TARGET_ACCESSION},
    ]


def test_net_income_series_matches_fixture(parsed: dict):
    assert parsed["net_income"] == [
        {"period": "2023-12-31", "value": 3_142_000_000, "form": "10-K", "accn": TARGET_ACCESSION},
        {"period": "2022-12-31", "value": 2_588_000_000, "form": "10-K", "accn": TARGET_ACCESSION},
        {"period": "2021-12-31", "value": 2_001_000_000, "form": "10-K", "accn": TARGET_ACCESSION},
    ]


def test_total_assets_series_matches_fixture(parsed: dict):
    # Balance-sheet (instant) facts: the 10-K reports two year-end snapshots.
    assert parsed["total_assets"] == [
        {"period": "2023-12-31", "value": 38_905_000_000, "form": "10-K", "accn": TARGET_ACCESSION},
        {"period": "2022-12-31", "value": 34_220_000_000, "form": "10-K", "accn": TARGET_ACCESSION},
    ]


def test_eps_series_prefers_basic_over_diluted(parsed: dict):
    # EPS uses USD/shares units. On a period-end tie the candidate order
    # (EarningsPerShareBasic before EarningsPerShareDiluted) keeps Basic, so the
    # 2023 figure is 6.34 (Basic), NOT 6.21 (Diluted).
    eps = parsed["earnings_per_share"]
    assert [e["period"] for e in eps] == ["2023-12-31", "2022-12-31", "2021-12-31"]
    assert [e["value"] for e in eps] == pytest.approx([6.34, 5.20, 4.01])
    assert all(e["form"] == "10-K" and e["accn"] == TARGET_ACCESSION for e in eps)
    diluted_values = {6.21, 5.09, 3.92}
    assert not diluted_values.intersection(e["value"] for e in eps)


def test_fallback_parser_ignores_liabilities_and_cash(parsed: dict):
    """Characterization of a genuine limitation: the fallback parser declares
    `total_liabilities` and `cash_and_equivalents` buckets but never populates
    them, even though the fixture supplies `Liabilities` and
    `CashAndCashEquivalentsAtCarryingValue` facts across two periods."""
    assert parsed["total_liabilities"] == []
    assert parsed["cash_and_equivalents"] == []


def test_extract_standardized_metrics_shapes_current_prior_change(parsed: dict):
    """The downstream consumer turns the buckets into current/prior/change/series.
    Pins the FY2023-vs-FY2022 deltas the summary UI renders."""
    metrics = EdgarXBRLService().extract_standardized_metrics(parsed)

    revenue = metrics["revenue"]
    assert revenue["current"] == {
        "period": "2023-12-31", "value": 24_318_000_000,
        "form": "10-K", "currency": None, "raw_tag": None,
    }
    assert revenue["prior"]["period"] == "2022-12-31"
    assert revenue["prior"]["value"] == 21_704_000_000
    assert revenue["change"]["direction"] == "increase"
    assert revenue["change"]["absolute"] == 2_614_000_000
    assert revenue["change"]["percentage"] == pytest.approx(12.04, abs=0.01)
    assert len(revenue["series"]) == 3

    # Net margin is derived from the revenue + net-income buckets that the fallback
    # parser produced (3.142B / 24.318B for FY2023).
    assert metrics["net_margin"]["current"]["value"] == pytest.approx(12.92, abs=0.01)

    # Liabilities/cash were never extracted, so no such downstream metrics exist.
    assert "total_liabilities" not in metrics
    assert "cash_and_equivalents" not in metrics
