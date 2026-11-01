"""The eval harness's own model inputs carry no standardized fact's filing (E184).

E184 keeps each standardized fact's ``accn`` (the filing that recorded it) so the figure check can refuse another
filing's fact. Production's grounding prints none, so ``evals.runner._model_metrics`` drops it from the inputs the
harness builds itself: a candidate's prompt (``_xbrl_to_text``), the judge's ground truth (``_maybe_judge``, and
``judge_report`` through it) and the acceptance decision's frozen judge input (``acceptance_ai_decision._judge_input_sha``).
The baseline candidate's generation is production's own (``summarize_filing``, whose prompt builders pick fields one by
one) and the Copilot eval reads the raw extraction; neither reads this projection.

Each input is held to main's bytes: main's ``_model_metrics`` dropped only the applicability metadata, and main's
``normalise_series`` dropped ``accn``, so main's input for a filing is that formula over the metrics this branch builds
from the same raw XBRL without the facts' ``accn``. All three inputs are held so on two raw shapes, one with every
family ``extract_standardized_metrics`` builds today and the recorded companyfacts sample; the judge's text alone on
the 78 standardized groundings a tracked baseline report retained. A family added later is held once it emits on
``RAW`` (or on the sample), whatever key it copies a fact under; one that needs a raw key, a value or a period shape
``RAW`` lacks (a bank-only or loss-only family, say) is outside the fixture until ``RAW`` gains it.
"""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.edgar.xbrl_service import EdgarXBRLService
from app.services.edgar.xbrl_standardized import extract_standardized_metrics
from evals import runner
from evals.acceptance_ai_decision import _judge_input_sha
from evals.judge import build_judge_messages
from evals.schema import GoldenFiling

ACCN = "0000320193-25-000079"
EVALS = Path(runner.__file__).resolve().parent
# Raw keys whose lists are annotations, not facts: extracted as they stand, before E184 as after.
ANNOTATIONS = ("segments", "debt_observations")
# Metrics keys that are no standardized metric: passed through as extracted, or dropped as applicability metadata.
PASSED_THROUGH = (*ANNOTATIONS, "financing_comparison_source", "reporting_currency", "financial_classification")
# The acceptance decision's judge input, as acceptance_worker records a summarizer call.
CANONICAL = {"business_overview": "x"}
COMPANY, FORM, EXCERPT = "Apple Inc.", "10-K", "excerpt"


def _fact(period: str, value: float, **extra) -> dict:
    return {"period": period, "value": value, "form": "10-K", "currency": "USD", "accn": ACCN, "raw_tag": None,
            **extra}


def _annual(current: float, prior: float) -> list[dict]:
    return [_fact("2025-09-27", current, fiscal_year=2025, fiscal_period="FY", period_start="2024-09-29"),
            _fact("2024-09-28", prior, fiscal_year=2024, fiscal_period="FY", period_start="2023-10-01")]


def _instant(current: float, prior: float) -> list[dict]:
    return [_fact("2025-09-27", current), _fact("2024-09-28", prior)]


def _financing_point(value: float, start: str, end: str) -> dict:
    """financing_source._point's shape."""
    return {"value": value, "period_start": start, "period_end": end, "currency": "USD",
            "raw_tag": "us-gaap:NetCashProvidedByUsedInFinancingActivities", "entity_identifier": "0000320193",
            "entity_scheme": "http://www.sec.gov/CIK", "context_refs": ["c-1"], "scope": "issuer_undimensioned"}


# Every family extract_standardized_metrics builds today: the headline and statement series (an institution's revenue
# components and the shareholder returns among them), net margin, working capital and the current ratio, free cash
# flow, the margins, ROE and ROA (whose points copy their operands whole), the per-ADS EPS, and what it passes through
# in its producers' shapes: segments, the debt observations (recording their own filing, as before E184), the
# financing source, the reporting currency and the applicability metadata.
RAW = {
    "revenue": _annual(416_161e6, 391_035e6),
    "net_income": _annual(112_010e6, 93_736e6),
    "earnings_per_share": _annual(7.49, 6.11),
    "eps_diluted": _annual(7.46, 6.08),
    "operating_cash_flow": _annual(111_482e6, 118_254e6),
    "capital_expenditures": _annual(-12_715e6, -9_447e6),
    "investing_cash_flow": _annual(15_195e6, 2_935e6),
    "financing_cash_flow": _annual(-120_686e6, -121_983e6),
    "dividends_paid": _annual(15_421e6, 15_234e6),
    "share_repurchases": _annual(90_711e6, 94_949e6),
    "gross_profit": _annual(195_201e6, 180_683e6),
    "operating_income": _annual(133_050e6, 123_216e6),
    "net_interest_income": _annual(1_200e6, 1_100e6),
    "noninterest_income": _annual(900e6, 850e6),
    "premiums_earned": _annual(700e6, 650e6),
    "net_investment_income": _annual(300e6, 280e6),
    "total_assets": _instant(359_241e6, 364_980e6),
    "total_liabilities": _instant(285_508e6, 308_030e6),
    "cash_and_equivalents": _instant(35_934e6, 29_943e6),
    "shareholders_equity": _instant(73_733e6, 56_950e6),
    "long_term_debt": _instant(78_328e6, 85_750e6),
    "current_assets": _instant(147_957e6, 152_987e6),
    "current_liabilities": _instant(165_631e6, 176_392e6),
    "ads_ratio": {"ordinary_per_ads": 8.0},
    "segments": [{"name": "Americas", "revenue": 178_353e6, "revenue_prior": 167_045e6, "operating_income": 71_960e6,
                  "period": "2025-09-27", "currency": "USD"}],
    "debt_observations": [{"concept": "us-gaap:LongTermDebt", "scope": "total", "basis": "carrying",
                           "value": 98_657e6, "instant": "2025-09-27", "currency": "USD", "unit_ref": "usd",
                           "context_ref": "c-2", "entity_identifier": "0000320193",
                           "entity_scheme": "http://www.sec.gov/CIK", "decimals": "-6", "accn": ACCN, "form": "10-K"}],
    "financing_comparison_source": {"accession": ACCN, "form": "10-K", "period_of_report": "2025-09-27",
                                    "current": _financing_point(-120_686e6, "2024-09-29", "2025-09-27"),
                                    "prior": _financing_point(-121_983e6, "2023-10-01", "2024-09-28")},
    "reporting_currency": "USD",
    "financial_classification": {"is_financial": False},
}


def _without_fact_accession(raw: dict) -> dict:
    """The raw XBRL with no fact recording its filing; the annotations and the financing source as they stand."""
    return {key: [{k: v for k, v in fact.items() if k != "accn"} for fact in value]
            if isinstance(value, list) and key not in ANNOTATIONS else copy.deepcopy(value)
            for key, value in raw.items()}


def _main_inputs(metrics: dict) -> tuple[str, str, str]:
    """The bytes main's harness handed a model of these metrics: its ``_model_metrics`` dropped only the applicability
    metadata. A candidate's prompt text, the judge's ground truth, and the hash of the acceptance decision's input."""
    xbrl = json.dumps({key: value for key, value in metrics.items() if key != "financial_classification"}, default=str)
    _, user = build_judge_messages(runner._baseline_to_canonical(CANONICAL), COMPANY, FORM, EXCERPT, xbrl)
    return xbrl[:runner._XBRL_TEXT_CHAR_CAP], xbrl, hashlib.sha256(user.encode("utf-8")).hexdigest()


async def _model_inputs(monkeypatch, metrics: dict) -> tuple[str, str, str]:
    """The same three inputs as the harness builds them now."""
    seen = []

    async def judge_summary(payload, company, filing_type, excerpt, xbrl_text, *, model_id):
        seen.append(xbrl_text)
        return SimpleNamespace(passed=True, verdict="PASS", mean_dimension=5.0, gate_failures=[], dimensions={},
                               error=None)

    monkeypatch.setattr(runner, "judge_summary", judge_summary)
    filing = GoldenFiling(ticker="AAPL", cik="320193", accession_number=ACCN, filing_type=FORM,
                          document_url="https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/",
                          company_name=COMPANY)
    verdict = await runner._maybe_judge("judge", {"executive_summary": "x"}, filing,
                                        {"xbrl_metrics": metrics, "excerpt": EXCERPT})
    assert verdict["input_complete"] and len(seen) == 1
    call = {"args": ["text", COMPANY, FORM], "kwargs": {"filing_excerpt": EXCERPT, "xbrl_metrics": metrics}}
    return runner._xbrl_to_text(metrics), seen[0], _judge_input_sha(CANONICAL, {"summarizer_calls": [call]})


@pytest.mark.asyncio
async def test_every_model_input_reads_main_s_bytes(monkeypatch):
    with_accn = extract_standardized_metrics(RAW)
    before = extract_standardized_metrics(_without_fact_accession(RAW))
    # The premise, so this cannot pass on a shape that never carried a filing: E184's facts record it, a ratio's
    # copied operands included, and without it none does.
    assert with_accn["revenue"]["current"]["accn"] == ACCN
    assert with_accn["return_on_equity"]["current"]["numerator"]["accn"] == ACCN
    assert with_accn["return_on_assets"]["series"][1]["denominator"]["accn"] == ACCN
    assert with_accn["earnings_per_share"]["per_ads"]
    assert ACCN not in json.dumps({k: v for k, v in before.items() if k not in PASSED_THROUGH})
    assert await _model_inputs(monkeypatch, with_accn) == _main_inputs(before)


@pytest.mark.asyncio
async def test_the_recorded_companyfacts_sample_reads_main_s_bytes(monkeypatch):
    sample = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "companyfacts_sample.json").read_text())
    raw = EdgarXBRLService()._parse_company_facts(sample, "0001789012-24-000031")
    with_accn = extract_standardized_metrics(raw)
    assert with_accn["net_income"]["current"]["accn"] == "0001789012-24-000031"
    assert with_accn["return_on_assets"]["current"]["numerator"]["accn"] == "0001789012-24-000031"
    before = extract_standardized_metrics(_without_fact_accession(raw))
    assert await _model_inputs(monkeypatch, with_accn) == _main_inputs(before)


def test_a_retained_grounding_without_accession_reads_exactly_main_s_bytes():
    # The 78 groundings a tracked baseline report retained (before E184, so no fact records its filing; 24 of their
    # metrics carry a per-ADS EPS): the projection is main's applicability filter on each, byte for byte.
    report = json.loads((EVALS / "baselines" / "eval_20260905T111951Z.json").read_text())
    groundings = [row["xbrl_grounding"] for row in report["results"] if isinstance(row.get("xbrl_grounding"), dict)]
    assert len(groundings) == 78
    assert sum("per_ads" in entry for g in groundings for entry in g.values() if isinstance(entry, dict)) == 24
    for grounding in groundings:
        assert json.dumps(runner._model_metrics(grounding), default=str) == _main_inputs(grounding)[1]


def test_the_projection_keeps_every_value_and_what_it_passes_through_as_extracted():
    metrics = extract_standardized_metrics(RAW)
    projected = runner._model_metrics(metrics)
    assert "financial_classification" not in projected
    # The debt observations recorded their filing before E184 too, and the grounding's debt line reads it there.
    for key in ("debt_observations", "segments", "financing_comparison_source", "reporting_currency"):
        assert projected[key] == metrics[key], key
    assert projected["debt_observations"][0]["accn"] == ACCN
    # Each standardized metric is itself without "accn", at every depth it was copied to, and nothing else.
    for key, entry in metrics.items():
        if key in PASSED_THROUGH:
            continue
        assert "accn" not in json.dumps(projected[key]), key
        assert projected[key] == json.loads(json.dumps(entry).replace(f', "accn": "{ACCN}"', "")), key
    # Only a standardized metric (a series, its first two facts again as current and prior) is projected: anything
    # else passes as extracted, even a current point that records its filing.
    annotation = {"current": {"value": 1.0, "accn": ACCN}, "prior": {"value": 2.0, "accn": ACCN}}
    assert runner._model_metrics({"annotation": annotation}) == {"annotation": annotation}


@pytest.mark.asyncio
async def test_the_projection_leaves_the_retained_grounding_whole(monkeypatch):
    # One grounding serves every candidate of a filing, and the baseline's row retains it (runner's "xbrl_grounding"):
    # the object a bake-off candidate's prompt and the judge read. Current and prior are the series' own first points,
    # so a projection that wrote in place would strip what the report keeps. The acceptance decision reads its own
    # frozen grounding.json; here it reads the same object too.
    metrics = extract_standardized_metrics(RAW)
    retained = copy.deepcopy(metrics)
    await _model_inputs(monkeypatch, metrics)
    assert metrics == retained
    assert metrics["revenue"]["series"][0]["accn"] == ACCN
