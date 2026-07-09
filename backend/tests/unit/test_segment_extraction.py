"""T5.2 reportable-segment extraction: `segment_series_by_member` (instance_extractor) keeps the
dimensional facts the consolidated paths drop, filtered to the ASC-280 segment axis, the filing's own
reporting period, and real reportable segments; `_extract_segments` (xbrl_service) assembles the table.

The edgartools `xb.facts.query().by_concept().by_dimension().to_dataframe()` chain is mocked so these
run hermetically in CI (real-filing behavior is covered by the dev-only scratchpad verification, as with
the T4 citation readout)."""
from app.services.edgar.instance_extractor import segment_series_by_member
from app.services.edgar.xbrl_service import _extract_segments

# 10-K duration window is (320, 390) days; these spans are ~364 days.
CUR = ("2024-09-28", "2025-09-27")   # (period_start, period_end) current FY
PRI = ("2023-09-30", "2024-09-28")   # prior FY
POR = "2025-09-27"


def _row(label, span, value, currency="USD", decimals=-6, dimensioned=True):
    start, end = span
    return {
        "is_dimensioned": dimensioned,
        "dimension_member_label": label,
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

    def to_dict(self, orient):  # noqa: ARG002 - matches pandas signature
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
    """Mock edgartools XBRL: `rows_by_concept` keyed by the namespaced concept id (e.g.
    'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax')."""
    def __init__(self, rows_by_concept):
        self.facts = _FakeFacts(rows_by_concept)


_REV = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
_OPINC = "us-gaap:OperatingIncomeLoss"


def test_segment_series_multi_segment_happy_path():
    xb = _FakeXBRL({_REV: [
        _row("Americas", CUR, 178_353_000_000.0), _row("Americas", PRI, 167_045_000_000.0),
        _row("Europe", CUR, 111_032_000_000.0), _row("Europe", PRI, 101_328_000_000.0),
    ]})
    out, ccy = segment_series_by_member(
        xb, ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"], "10-K", POR
    )
    assert ccy == "USD"
    assert set(out) == {"Americas", "Europe"}
    assert out["Americas"][0] == ("2025-09-27", 178_353_000_000.0)   # current
    assert out["Americas"][1] == ("2024-09-28", 167_045_000_000.0)   # prior
    assert out["Europe"][0] == ("2025-09-27", 111_032_000_000.0)


def test_segment_series_drops_corporate_elimination_and_total_members():
    xb = _FakeXBRL({_REV: [
        _row("Americas", CUR, 178_353_000_000.0),
        _row("Europe", CUR, 111_032_000_000.0),
        _row("Corporate", CUR, 5_000_000_000.0),
        _row("Intersegment Eliminations", CUR, -3_000_000_000.0),
        _row("Total", CUR, 291_385_000_000.0),
    ]})
    out, _ = segment_series_by_member(xb, ["RevenueFromContractWithCustomerExcludingAssessedTax"], "10-K", POR)
    assert set(out) == {"Americas", "Europe"}   # corporate / elimination / total excluded


def test_segment_series_concept_fallback_ordering():
    # The filer tags segment revenue under `Revenues`; it is FIRST in the candidate list and must win.
    xb = _FakeXBRL({"us-gaap:Revenues": [
        _row("Cloud", CUR, 100_000_000_000.0), _row("Devices", CUR, 50_000_000_000.0),
    ]})
    out, _ = segment_series_by_member(
        xb, ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"], "10-K", POR
    )
    assert set(out) == {"Cloud", "Devices"}


def test_segment_series_empty_for_undimensioned_or_single_segment():
    assert segment_series_by_member(_FakeXBRL({}), ["Revenues"], "10-K", POR) == ({}, None)
    # A fact present but NOT dimensioned (consolidated) is not a segment.
    xb = _FakeXBRL({_REV: [_row("Americas", CUR, 1.0, dimensioned=False)]})
    assert segment_series_by_member(xb, ["RevenueFromContractWithCustomerExcludingAssessedTax"], "10-K", POR) == ({}, None)


def test_segment_series_requires_current_period_anchor():
    # 'Japan' reports only a prior-period fact (a dropped/renamed segment) — no anchor at period_of_report.
    xb = _FakeXBRL({_REV: [
        _row("Americas", CUR, 178_353_000_000.0),
        _row("Europe", CUR, 111_032_000_000.0),
        _row("Japan", PRI, 25_000_000_000.0),
    ]})
    out, _ = segment_series_by_member(xb, ["RevenueFromContractWithCustomerExcludingAssessedTax"], "10-K", POR)
    assert set(out) == {"Americas", "Europe"}
    assert "Japan" not in out


def test_segment_series_drops_reconciling_consolidation_axis_members():
    # Cross-tabbed facts: real operating segments carry ConsolidationItemsAxis=OperatingSegmentsMember;
    # a member on the same segment axis tagged as an intersegment elimination must be dropped even when
    # its label would evade the label filter (the phantom-segment guard).
    def _crow(label, value, consol):
        r = _row(label, CUR, value)
        r["dim_srt_ConsolidationItemsAxis"] = consol
        return r
    xb = _FakeXBRL({_REV: [
        _crow("Americas", 178_353_000_000.0, "us-gaap:OperatingSegmentsMember"),
        _crow("Europe", 111_032_000_000.0, "us-gaap:OperatingSegmentsMember"),
        _crow("Data Services", -3_000_000_000.0, "us-gaap:IntersegmentEliminationMember"),
    ]})
    out, _ = segment_series_by_member(xb, ["RevenueFromContractWithCustomerExcludingAssessedTax"], "10-K", POR)
    assert set(out) == {"Americas", "Europe"}   # elimination cross-member dropped despite a clean label


def test_segment_series_consolidation_axis_null_cell_is_kept():
    # Mixed-tagging: the DataFrame carries the ConsolidationItemsAxis column (some fact tags it) but THIS
    # fact's cell is null. None / float-NaN / pd.NA must be treated as "unconstrained → keep", never drop
    # the segment (the string-based missing check, per the Gemini finding — pd.NA breaks `val != val`).
    import pandas as pd

    def _crow(label, value, consol):
        r = _row(label, CUR, value)
        r["dim_srt_ConsolidationItemsAxis"] = consol
        return r
    for null_val in (None, float("nan"), pd.NA):
        xb = _FakeXBRL({_REV: [
            _crow("Americas", 178_353_000_000.0, "us-gaap:OperatingSegmentsMember"),
            _crow("Other Bets", 40_000_000_000.0, null_val),
        ]})
        out, _ = segment_series_by_member(xb, ["RevenueFromContractWithCustomerExcludingAssessedTax"], "10-K", POR)
        assert set(out) == {"Americas", "Other Bets"}, f"null co-axis {null_val!r} must keep the segment"


def test_segment_series_drops_additional_skip_tokens():
    xb = _FakeXBRL({_REV: [
        _row("Americas", CUR, 178_353_000_000.0),
        _row("Europe", CUR, 111_032_000_000.0),
        _row("All Other", CUR, 2_000_000_000.0),
        _row("Unallocated", CUR, 1_000_000_000.0),
        _row("Reconciling Items", CUR, 500_000_000.0),
    ]})
    out, _ = segment_series_by_member(xb, ["RevenueFromContractWithCustomerExcludingAssessedTax"], "10-K", POR)
    assert set(out) == {"Americas", "Europe"}


def test_segment_series_respects_reporting_currency():
    xb = _FakeXBRL({_REV: [
        _row("EMEA", CUR, 30_600_000_000.0, currency="EUR"),
        _row("Americas", CUR, 40_000_000_000.0, currency="EUR"),
    ]})
    out, ccy = segment_series_by_member(xb, ["RevenueFromContractWithCustomerExcludingAssessedTax"], "10-K", POR)
    assert ccy == "EUR" and set(out) == {"EMEA", "Americas"}


def test_extract_segments_assembles_ordered_table():
    xb = _FakeXBRL({
        _REV: [
            _row("Americas", CUR, 178_353_000_000.0), _row("Americas", PRI, 167_045_000_000.0),
            _row("Europe", CUR, 111_032_000_000.0), _row("Europe", PRI, 101_328_000_000.0),
        ],
        _OPINC: [_row("Americas", CUR, 72_480_000_000.0), _row("Europe", CUR, 47_739_000_000.0)],
    })
    rows = _extract_segments(xb, "10-K", POR, consolidated_revenue=289_385_000_000.0)
    assert [r["name"] for r in rows] == ["Americas", "Europe"]   # revenue-descending
    a = rows[0]
    assert a["revenue"] == 178_353_000_000.0 and a["revenue_prior"] == 167_045_000_000.0
    assert a["operating_income"] == 72_480_000_000.0 and a["period"] == "2025-09-27"
    assert a["currency"] == "USD"


def test_extract_segments_single_segment_returns_empty():
    xb = _FakeXBRL({_REV: [_row("OneCo", CUR, 100_000_000_000.0)]})
    assert _extract_segments(xb, "10-K", POR, consolidated_revenue=100_000_000_000.0) == []


def test_extract_segments_incoherent_sum_is_dropped():
    # Segment revenues sum to ~289B but consolidated is tagged 10B (a mis-tag / unit mismatch) -> drop.
    xb = _FakeXBRL({_REV: [
        _row("Americas", CUR, 178_353_000_000.0), _row("Europe", CUR, 111_032_000_000.0),
    ]})
    assert _extract_segments(xb, "10-K", POR, consolidated_revenue=10_000_000_000.0) == []   # 28.9x, high
    # Same segments, coherent consolidated -> kept.
    assert len(_extract_segments(xb, "10-K", POR, consolidated_revenue=289_000_000_000.0)) == 2


def test_extract_segments_incoherent_low_sum_is_dropped():
    # A partial capture (segments sum to ~9% of consolidated — ratio < 0.5) is a misleadingly-incomplete
    # table, so it is dropped rather than surfaced.
    xb = _FakeXBRL({_REV: [_row("A", CUR, 5_000_000_000.0), _row("B", CUR, 4_000_000_000.0)]})
    assert _extract_segments(xb, "10-K", POR, consolidated_revenue=100_000_000_000.0) == []
