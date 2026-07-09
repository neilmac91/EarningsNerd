"""T5.3 shareholder-returns extraction: `dividends_paid` + `share_repurchases` duration concepts
(cash-flow-statement payments, live-verified across AAPL/MSFT/ASML/TSM/NVO — see the DURATION_CONCEPTS
comment for the excluded trap tags) flow through `duration_series_currency_concept` and
`extract_standardized_metrics` exactly like capex.

The edgartools query chain is mocked (the test_segment_extraction pattern) so these run hermetically."""
from app.services.edgar.instance_extractor import (
    DIVIDEND_COMPONENT_CONCEPTS,
    DURATION_CONCEPTS,
    dividend_component_sum_series,
    duration_series_currency_concept,
)
from app.services.edgar.xbrl_service import edgar_xbrl_service

CUR = ("2024-09-28", "2025-09-27")
PRI = ("2023-09-30", "2024-09-28")
POR = "2025-09-27"


def _row(span, value, currency="USD", decimals=-6, dimensioned=False):
    start, end = span
    return {
        "is_dimensioned": dimensioned,
        "period_start": start,
        "period_end": end,
        "numeric_value": value,
        "currency": currency,
        "decimals": decimals,
    }


class _FakeDF:
    def __init__(self, records):
        self._records = list(records)
        self.empty = not self._records

    def to_dict(self, orient):  # noqa: ARG002
        return list(self._records)


class _FakeQuery:
    def __init__(self, rows_by_concept):
        self._rows_by_concept = rows_by_concept
        self._concept = None

    def by_concept(self, concept, exact=False):  # noqa: ARG002
        self._concept = concept
        return self

    def by_dimension(self, axis, value=None):  # noqa: ARG002
        return self

    def to_dataframe(self):
        return _FakeDF(self._rows_by_concept.get(self._concept, []))


class _FakeFacts:
    def __init__(self, rows_by_concept):
        self._rows_by_concept = rows_by_concept

    def query(self):
        return _FakeQuery(self._rows_by_concept)


class _FakeXBRL:
    def __init__(self, rows_by_concept):
        self.facts = _FakeFacts(rows_by_concept)


def test_registry_carries_verified_candidates_and_excludes_trap_tags():
    """Rule-12 pin on the live-verified candidate lists. Totals-only in DURATION_CONCEPTS —
    per-class components live in DIVIDEND_COMPONENT_CONCEPTS and are SUMMED, never
    first-candidate-wins (a component is a disjoint subset, not an alternative spelling; WFC-class
    filers tag common+preferred with no total, and common-only-as-total understates by 16%).
    The trap tags are wrong-by-construction: `DividendsCommonStockCash` is dividends DECLARED, not
    paid (MSFT: 24,678M declared vs 24,082M paid); ifrs `DividendsPaid` is the equity-statement
    distribution (TSM: 531,618M vs 466,779M cash); `StockRepurchasedAndRetiredDuringPeriodValue`
    is the equity-statement measure (AAPL: 89,300M vs 90,711M cash paid)."""
    div = DURATION_CONCEPTS["dividends_paid"]
    buy = DURATION_CONCEPTS["share_repurchases"]
    assert div == ["PaymentsOfDividends", "PaymentsOfOrdinaryDividends",
                   "DividendsPaidClassifiedAsFinancingActivities"]
    assert DIVIDEND_COMPONENT_CONCEPTS == ["PaymentsOfDividendsCommonStock",
                                           "PaymentsOfDividendsPreferredStockAndPreferenceStock"]
    assert buy == ["PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfEquity",
                   "PaymentsToAcquireOrRedeemEntitysShares"]
    for trap in ("DividendsCommonStockCash", "DividendsPaid",
                 "StockRepurchasedAndRetiredDuringPeriodValue", "PurchaseOfTreasuryShares"):
        assert trap not in div and trap not in buy and trap not in DIVIDEND_COMPONENT_CONCEPTS


def test_dividends_first_candidate_wins_with_prior_period():
    # AAPL/JPM-style: the GAAP TOTAL is tagged; later candidates never consulted.
    xb = _FakeXBRL({"us-gaap:PaymentsOfDividends": [
        _row(CUR, 15_421_000_000.0), _row(PRI, 15_234_000_000.0),
    ]})
    series, currency, concept = duration_series_currency_concept(
        xb, DURATION_CONCEPTS["dividends_paid"], "10-K", POR
    )
    assert concept == "PaymentsOfDividends" and currency == "USD"
    assert series[0] == (POR, 15_421_000_000.0) and series[1][1] == 15_234_000_000.0


def test_dividend_components_summed_for_wfc_class_filers():
    """WFC-class (live-reproduced by the adversarial review): common + preferred tagged as separate
    components, NO total. The components are summed per period — 5,434M + 1,050M = 6,484M — instead
    of reporting the common-only subset as the unqualified total."""
    xb = _FakeXBRL({
        "us-gaap:PaymentsOfDividendsCommonStock": [
            _row(CUR, 5_434_000_000.0), _row(PRI, 5_109_000_000.0),
        ],
        "us-gaap:PaymentsOfDividendsPreferredStockAndPreferenceStock": [
            _row(CUR, 1_050_000_000.0), _row(PRI, 1_133_000_000.0),
        ],
    })
    series, currency = dividend_component_sum_series(xb, "10-K", POR)
    assert currency == "USD"
    assert series[0] == (POR, 6_484_000_000.0)
    assert series[1] == (PRI[1], 6_242_000_000.0)


def test_dividend_component_sum_with_single_component():
    # MSFT-style: only the common component exists (no preferred in the capital structure) — the
    # sole component IS the total.
    xb = _FakeXBRL({"us-gaap:PaymentsOfDividendsCommonStock": [_row(CUR, 24_082_000_000.0)]})
    series, currency = dividend_component_sum_series(xb, "10-K", POR)
    assert series == [(POR, 24_082_000_000.0)] and currency == "USD"


def test_dividend_component_sum_never_mixes_currencies():
    xb = _FakeXBRL({
        "us-gaap:PaymentsOfDividendsCommonStock": [_row(CUR, 5_000_000_000.0, currency="USD")],
        "us-gaap:PaymentsOfDividendsPreferredStockAndPreferenceStock": [
            _row(CUR, 1_000_000_000.0, currency="EUR"),
        ],
    })
    series, currency = dividend_component_sum_series(xb, "10-K", POR)
    assert series == [(POR, 5_000_000_000.0)] and currency == "USD"  # EUR component dropped, not summed


def test_dividends_resolve_under_ifrs_namespace():
    # TSM-style: ifrs-full DividendsPaidClassifiedAsFinancingActivities, native TWD.
    xb = _FakeXBRL({"ifrs-full:DividendsPaidClassifiedAsFinancingActivities": [
        _row(("2025-01-01", "2025-12-31"), 466_779_200_000.0, currency="TWD"),
    ]})
    series, currency, concept = duration_series_currency_concept(
        xb, DURATION_CONCEPTS["dividends_paid"], "20-F", "2025-12-31"
    )
    assert concept == "DividendsPaidClassifiedAsFinancingActivities"
    assert currency == "TWD" and series[0][1] == 466_779_200_000.0


def test_buybacks_skip_dimensioned_and_out_of_window_rows():
    xb = _FakeXBRL({"us-gaap:PaymentsForRepurchaseOfCommonStock": [
        _row(CUR, 90_711_000_000.0),
        _row(CUR, 40_000_000_000.0, dimensioned=True),          # segment/class-tagged twin: skipped
        _row(("2025-06-29", "2025-09-27"), 24_000_000_000.0),   # Q4 duration inside FY: out of window
    ]})
    series, _, _ = duration_series_currency_concept(
        xb, DURATION_CONCEPTS["share_repurchases"], "10-K", POR
    )
    assert series == [(POR, 90_711_000_000.0)]


def test_absent_concepts_yield_empty_series():
    # TSLA-style: neither metric tagged — clean degrade, no keys downstream.
    xb = _FakeXBRL({})
    for key in ("dividends_paid", "share_repurchases"):
        series, currency, concept = duration_series_currency_concept(
            xb, DURATION_CONCEPTS[key], "10-K", POR
        )
        assert series == [] and currency is None and concept is None


def test_roe_not_derived_for_negative_equity_filers():
    """Adversarial-review finding: a NEGATIVE-equity filer (buyback-driven deficits — SBUX, MCD, BA)
    sign-flips ROE, rendering a profitable company deeply negative and a loss-maker confidently
    positive. The derivation now requires a POSITIVE denominator ("only derive from clean inputs"),
    so those periods are skipped; ROA (positive assets) still derives."""
    raw = {
        "net_income": [{"period": "2025-12-31", "value": 3_800_000_000.0, "form": "10-K"}],
        "shareholders_equity": [{"period": "2025-12-31", "value": -7_400_000_000.0, "form": "10-K"}],
        "total_assets": [{"period": "2025-12-31", "value": 31_000_000_000.0, "form": "10-K"}],
        "revenue": [{"period": "2025-12-31", "value": 36_000_000_000.0, "form": "10-K"}],
    }
    metrics = edgar_xbrl_service.extract_standardized_metrics(raw)
    assert "return_on_equity" not in metrics
    assert round(metrics["return_on_assets"]["current"]["value"], 1) == 12.3


def test_standardized_metrics_emit_shareholder_return_entries():
    """The pass-through loop turns Stage-A series into {current, prior, change, series} — the same
    entry shape every other standardized metric carries (the filler consumes raw_current/raw_prior)."""
    raw = {
        "dividends_paid": [
            {"period": POR, "value": 15_421_000_000.0, "form": "10-K", "currency": "USD"},
            {"period": "2024-09-28", "value": 15_234_000_000.0, "form": "10-K", "currency": "USD"},
        ],
        "share_repurchases": [
            {"period": POR, "value": 90_711_000_000.0, "form": "10-K", "currency": "USD"},
        ],
    }
    metrics = edgar_xbrl_service.extract_standardized_metrics(raw)
    div = metrics["dividends_paid"]
    assert div["current"]["value"] == 15_421_000_000.0 and div["prior"]["value"] == 15_234_000_000.0
    assert div["change"]["direction"] == "increase"
    assert metrics["share_repurchases"]["current"]["value"] == 90_711_000_000.0
    assert "prior" not in metrics["share_repurchases"] or not metrics["share_repurchases"].get("prior")
