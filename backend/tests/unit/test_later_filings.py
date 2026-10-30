"""The later-filing places and the producer's evidence against the page's reader (MPA WP5a-B).

Two checks, both against F1's reader, ``frontend/features/analysis/lib/laterFilings.ts``, which stays the source of
truth (its spec is ``frontend/tests/unit/later-filings.spec.tsx``):

1. The places twin. ``trend_analysis/later_filings.later_filing_places`` computes the places of every case in the
   shared fixture ``backend/tests/fixtures/analysis_later_filings.json`` exactly as its ``expected`` gives them, the
   values and the comparisons alike, as the page's ``laterFilingPlaces`` does over the same cases; and the dataset the
   producer builds from WP5b's REGN shape gives the places the fixture's REGN case plants.
2. The decoder. ``_decode`` below is a Python port of the page's ``decodeLaterFilings`` and its checks
   (``checkFirstReported``, ``checkInputs``, ``carriesFinding``, ``checkPoint``, ``scaleSteps``, ``day``), as of F1's
   a9ab712bc. Every dataset the producer builds here, the REGN shape and each finding's, passes it as JSON; so does
   every shared case, which the page admits; and planted breaks of each rule fail it. When the page's rules change,
   this port follows them; it never decides them.
"""
from __future__ import annotations

import copy
import json
import math
import re
from datetime import date
from pathlib import Path

import pytest

from app.services.trend_analysis.later_filings import later_filing_places
from tests.unit import test_first_reports as first_reports
from tests.unit.test_companyfacts_own_report_history import _REVENUE, _items, _payload
from tests.unit.test_first_reports import _build, _net_income, _synced

# test_first_reports' fixtures: its tables, and a session whose filing rows leave with the test.
_tables, db = first_reports._tables, first_reports.db

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


# --- the port of laterFilings.ts decodeLaterFilings ----------------------------------------------------------------

class Rejection(ValueError):
    pass


def _present(value):
    return value is not None


def _finite(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise Rejection(f"{field} must be a finite number")
    return value


def _text(value, field):
    if not isinstance(value, str) or not value:
        raise Rejection(f"{field} must be a nonempty string")
    return value


def _day(value, field):
    if not _present(value):
        return
    try:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        date.fromisoformat(value)
    except ValueError:
        raise Rejection(f"{field} must be a YYYY-MM-DD day or null")


def scale_steps(own, shown):
    if own == 0 or shown == 0 or (own > 0) != (shown > 0):
        return None
    steps = math.floor(math.log10(abs(shown / own)) / 3 + 0.5)  # Math.round
    if steps == 0 or abs(steps) > 3:
        return None
    expected = own * 1000 ** steps
    return steps if abs(shown - expected) <= abs(expected) * 1e-9 else None


def _check_first_reported(first, figure, where):
    if not isinstance(first, dict):
        raise Rejection(f"{where}.first_reported must be an object")
    shown = _finite(figure.get("value"), f"{where}.value beside first_reported")
    value = _finite(first.get("value"), f"{where}.first_reported.value")
    if value == shown:
        raise Rejection(f"{where}.first_reported.value equals the value shown")
    if _text(first.get("unit"), f"{where}.first_reported.unit") != figure.get("unit"):
        raise Rejection(f"{where}.first_reported.unit is not the figure's unit")
    accession = _text(first.get("accession"), f"{where}.first_reported.accession")
    if isinstance(figure.get("accession"), str) and accession == figure["accession"]:
        raise Rejection(f"{where}.first_reported.accession is the shown filing's")
    if _present(first.get("form")):
        _text(first["form"], f"{where}.first_reported.form")
    if _present(first.get("source_url")) and not isinstance(first["source_url"], str):
        raise Rejection(f"{where}.first_reported.source_url must be a string or null")
    _day(first.get("filed_at"), f"{where}.first_reported.filed_at")
    _day(first.get("later_filed_at"), f"{where}.first_reported.later_filed_at")
    finding = first.get("disagreement")
    if _present(finding) and finding not in ("opposite_sign", "scale"):
        raise Rejection(f"{where}.first_reported.disagreement is unsupported")
    if finding == "opposite_sign" and shown != -value:
        raise Rejection(f"{where}.first_reported is no exact sign flip")
    if finding == "scale" and scale_steps(value, shown) is None:
        raise Rejection(f"{where}.first_reported is no exact factor of 1,000")


def _annual_only(annual, field):
    if not annual:
        raise Rejection(f"{field}: only an annual run carries later-filing evidence (D5)")


def _check_inputs(provenance, annual, where):
    if not isinstance(provenance, dict) or not isinstance(provenance.get("inputs"), list):
        return
    for index, operand in enumerate(provenance["inputs"]):
        at = f"{where}.inputs[{index}]"
        if _present((operand or {}).get("first_reported")):
            _annual_only(annual, f"{at}.first_reported")
            _check_first_reported(operand["first_reported"], operand, at)
        _check_inputs((operand or {}).get("provenance"), annual, at)


def _finds(figure):
    """``carriesFinding``: a sign or scale finding in a year's evidence, its own or an input's at any depth."""
    if not isinstance(figure, dict):
        return False
    first, provenance = figure.get("first_reported"), figure.get("provenance")
    if isinstance(first, dict) and _present(first.get("disagreement")):
        return True
    inputs = provenance.get("inputs") if isinstance(provenance, dict) else None
    return isinstance(inputs, list) and any(_finds(operand) for operand in inputs)


def _year_before(key):
    match = re.fullmatch(r"FY(\d{4})", key or "")
    return f"FY{int(match.group(1)) - 1}" if match else key


def _check_point(point, series, by_period, annual, where):
    if not isinstance(point, dict):
        return
    if _present(point.get("first_reported")):
        _annual_only(annual, f"{where}.first_reported")
        if (point.get("provenance") or {}).get("method") == "calculated":
            raise Rejection(f"{where}.first_reported sits on a calculated figure")
        unit = point["unit"] if _present(point.get("unit")) else series.get("unit")
        _check_first_reported(point["first_reported"],
                              {"value": point.get("value"), "unit": unit, "accession": point.get("accession")}, where)
    if "qoq_first_reported" in point:
        raise Rejection(f"{where}.qoq_first_reported: no QoQ carries later-filing evidence (D5)")
    if "yoy_first_reported" in point:
        first = point["yoy_first_reported"]
        _annual_only(annual, f"{where}.yoy_first_reported")
        if point.get("yoy") != "nm":
            raise Rejection(f"{where}.yoy_first_reported sits beside a yoy that is not n/m")
        if first is not None and first != "nm":
            _finite(first, f"{where}.yoy_first_reported")
        if not isinstance(point.get("period"), str):
            raise Rejection(f"{where}.period must be a string beside yoy_first_reported")
        if (_finds(point) or _finds(by_period.get(_year_before(point.get("period"))))) and first != "nm":
            raise Rejection(f"{where}.yoy_first_reported must be n/m across a sign or scale finding")
    _check_inputs(point.get("provenance"), annual, where)
    _check_inputs(point.get("yoy_provenance"), annual, f"{where}.yoy_provenance")
    _check_inputs(point.get("qoq_provenance"), annual, f"{where}.qoq_provenance")


def _decode(dataset):
    annual = dataset.get("mode") == "annual"
    for index, series in enumerate(dataset.get("series") or []):
        points = series.get("points") or []
        by_period = {point["period"]: point for point in points if isinstance(point, dict)}
        for number, point in enumerate(points):
            _check_point(point, series, by_period, annual, f"series[{index}].points[{number}]")
        _check_inputs(series.get("cagr_provenance"), annual, f"series[{index}].cagr_provenance")
        _check_inputs(series.get("window_pp_provenance"), annual, f"series[{index}].window_pp_provenance")
    return dataset


def _wire(dataset):
    return json.loads(json.dumps(dataset, default=str))


def _scale_assets():
    return _items({2017: {2016: 9_520.2e6, 2017: 11_734.5e6}, 2018: {2017: 11_734.5e6, 2018: 15_163.8e6},
                   2019: {2018: 15_163.8e3, 2019: 17_163.4e6}, 2020: {2019: 17_163.4e6, 2020: 19_994.1e6},
                   2021: {2020: 19_994.1e6, 2021: 25_434.7e6}}, instant=True)


PRODUCED = {
    "regn": lambda: _payload(),
    "a-sign-flip": lambda: _payload(tags=_net_income({2018: -2_444.4e6})),
    "a-scale-factor": lambda: _payload(assets=_scale_assets()),
    "an-inputs-finding": lambda: _payload(_items({**_REVENUE, 2020: {**_REVENUE[2020], 2018: 6_710.8e3}})),
}


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_the_port_admits_every_shared_case_the_page_admits(case):
    # The shared cases are the page's admitted wire shapes (later-filings.spec.tsx renders each): a port that
    # refused one would be stricter than the page.
    assert _decode(copy.deepcopy(case["dataset"])) == case["dataset"]


@pytest.mark.requires_db
class TestTheProducersDatasetsDecode:
    @pytest.mark.parametrize("shape", list(PRODUCED))
    @pytest.mark.parametrize("start", ["FY2017", "FY2018"])
    def test_every_dataset_the_producer_builds_passes_the_pages_decoder(self, db, shape, start):
        dataset = _wire(_build(db, _synced(db, PRODUCED[shape]()), start, "FY2021"))
        assert _decode(dataset) == dataset
        assert any("first_reported" in point for series in dataset["series"] for point in series["points"])

    def test_the_regn_dataset_gives_the_places_the_shared_fixture_plants(self, db):
        regn = next(case for case in CASES if case["name"] == "regn_own_reports_beside_later_comparatives")
        assert later_filing_places(_build(db, _synced(db, _payload()))) == regn["expected"]

    @pytest.mark.parametrize("brk, message", [
        (lambda d: _at(d, "net_income", "FY2018").update(yoy_first_reported=0.1), "must be n/m across"),
        (lambda d: _at(d, "net_income", "FY2019").update(yoy_first_reported=None), "must be n/m across"),
        (lambda d: _at(d, "net_margin", "FY2018").update(first_reported={"value": 1.0}), "calculated figure"),
        (lambda d: _at(d, "net_income", "FY2018")["first_reported"].update(disagreement="scale"), "factor of 1,000"),
        (lambda d: _at(d, "net_income", "FY2018")["first_reported"].update(filed_at="2019-02-07T00:00:00Z"), "YYYY-MM-DD"),
        (lambda d: _at(d, "net_income", "FY2018")["first_reported"].update(value=-2_444.4e6), "equals the value"),
        (lambda d: _at(d, "net_income", "FY2017").update(yoy="nm", yoy_first_reported=None, qoq_first_reported=None),
         "QoQ"),
        (lambda d: d.update(mode="quarterly"), "only an annual run"),
    ], ids=["a-number-across-a-finding", "null-across-a-finding", "on-a-calculated-figure", "a-false-finding",
            "a-timestamp", "an-equal-value", "a-qoq", "a-quarterly-run"])
    def test_the_port_refuses_each_planted_break(self, db, brk, message):
        dataset = _wire(_build(db, _synced(db, PRODUCED["a-sign-flip"]())))
        broken = copy.deepcopy(dataset)
        brk(broken)
        with pytest.raises(Rejection, match=message):
            _decode(broken)


def _at(dataset, concept, period):
    series = next(series for series in dataset["series"] if series["concept"] == concept)
    return next(point for point in series["points"] if point["period"] == period)
