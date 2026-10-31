"""The later-filing places' backend twin against the page's reader (MPA WP5a-X).

``trend_analysis/later_filings.later_filing_places`` computes the places of every case in the shared fixture
``backend/tests/fixtures/analysis_later_filings.json`` exactly as its ``expected`` gives them, the values and the
comparisons alike, as the page's ``laterFilingPlaces`` (``frontend/features/analysis/lib/laterFilings.ts``) does over
the same cases in ``frontend/tests/unit/later-filings.spec.tsx``, which stays the source of truth. The exports' line
(``analysis_export_metadata.later_filing_entry``) prints these places; ``test_export_later_filings.py`` reads them in
both files.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.services.trend_analysis.later_filings import later_filing_places

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "analysis_later_filings.json"
CASES = json.loads(FIXTURE.read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_the_places_twin_gives_each_shared_cases_expected_places(case):
    assert later_filing_places(case["dataset"]) == case["expected"]


def test_the_fixture_holds_values_and_comparisons_to_tell_apart():
    # A twin that counted calculated figures, or every n/m, would still pass a fixture without these.
    regn = next(case for case in CASES if case["name"] == "regn_own_reports_beside_later_comparatives")
    assert regn["expected"]["values"] != regn["expected"]["comparisons"]
    assert any(case["expected"]["comparisons"] == [] and any(
        point.get("yoy") == "nm" for series in case["dataset"]["series"] for point in series["points"])
        for case in CASES)


def test_a_dataset_without_the_fields_has_no_places_whatever_it_lacks():
    """An older snapshot exports as it did before the line: the twin reads no label or concept of a point that carries
    neither field, so a series or a period that lacks them, or a dataset with no series or periods, gives no places."""
    dataset = deepcopy(next(case for case in CASES if case["name"] == "no_evidence")["dataset"])
    for series in dataset["series"]:
        del series["label"], series["concept"]
    assert later_filing_places(dataset) == {"values": [], "comparisons": []}
    assert later_filing_places({}) == later_filing_places({"series": None, "periods": None}) == {"values": [], "comparisons": []}


def test_a_comparison_counts_only_where_its_yoy_reads_n_m():
    """laterFilings.ts basisChanged: a YoY counts by its growth as first reported only where it reads n/m, as on the
    page; the fixture cannot carry the key beside a number, which the page's decoder refuses."""
    case = next(case for case in CASES if case["name"] == "evidence_with_no_change_of_basis")
    dataset = deepcopy(case["dataset"])
    point = next(point for series in dataset["series"] for point in series["points"]
                 if (series["concept"], point["period"]) == ("total_assets", "FY2019"))
    assert isinstance(point["yoy"], float)
    point["yoy_first_reported"] = 0.12
    assert later_filing_places(dataset) == case["expected"]
