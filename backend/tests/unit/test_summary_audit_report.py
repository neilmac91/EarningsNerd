"""Persisted audit families have independent, honest snapshot denominators."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models import Base, Company, Filing, Summary
from app.services import data_quality_service as quality
from app.services import email_service


@pytest.fixture
def sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'audits.sqlite'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def forward():
    return {"checked": 2, "verified": 1, "near_miss": 1, "armed": False,
            "unverified": [{"speaker": "CEO", "score": 95.0}], "dropped": []}


def snap():
    return {"checked": 3, "exact": 1, "armed": False, "min_score": 92.0,
            "would_snap": [{"surface": "results_that_matter", "label": "Revenue", "score": 95.0,
                            "original": "almost a source quote", "candidate": "a source quote"}],
            "snapped": [], "left": [{"surface": "notable_footnotes", "score": 0.0}]}


def store(db, rows):
    co = Company(cik="1", ticker="ONE", name="One", sic="6021")
    db.add(co)
    db.flush()
    for index, raw in enumerate(rows):
        filing = Filing(company_id=co.id, accession_number=f"audit-{index}", filing_type="10-K",
                        filing_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
                        sec_url="https://example.test/", document_url="https://example.test/filing.htm")
        db.add(filing)
        db.flush()
        db.add(Summary(filing_id=filing.id, raw_summary=raw))
    db.commit()


def test_each_audit_family_uses_its_own_valid_snapshot_population(sessions):
    armed = snap()
    armed.update(checked=2, armed=True, snapped=armed["would_snap"], would_snap=[], left=[])
    empty_forward = dict(checked=0, verified=0, near_miss=0, armed=False, unverified=[], dropped=[])
    rows = [
        {"sections": {"large_prose": "never load this" * 1000},
         "quality": {"tier": "full", "reasons": [], "figures_untraceable": [], "machine_sections_only": False},
         "forward_quote_audit": forward(), "evidence_snap_audit": snap()},
        {"quality": {"tier": "partial", "reasons": ["gap", "gap", "thin"],
                     "figures_untraceable": ["1000000", "1000000", "2000000"], "machine_sections_only": True},
         "evidence_snap_audit": armed},
        {"quality": {"tier": "full", "reasons": []}, "forward_quote_audit": empty_forward},
        {},
        {"quality": {"tier": "mystery", "reasons": "bad", "figures_untraceable": "bad", "machine_sections_only": 1},
         "forward_quote_audit": {**forward(), "checked": True}, "evidence_snap_audit": {**snap(), "exact": -1}},
    ]
    with sessions() as db:
        store(db, rows)
        statements = []
        event.listen(db, "do_orm_execute", lambda state: statements.append(state.statement))
        result = quality.summary_audit_counts(db)
        partials = quality.partial_reason_counts(db)
    assert result["snapshot_population"] == 5
    families = result["families"]
    for name in ("figure_trace", "machine_sections_only", "forward_quotes", "evidence_snap"):
        family = families[name]
        assert (family["recorded"], family["missing"], family["malformed"], family["unavailable"]) == (2, 2, 1, 3)
    assert families["figure_trace"]["counts"] == {"unique_figures": 2}
    assert families["figure_trace"]["flagged"] == 1 and families["figure_trace"]["flagged_pct"] == 50.0
    assert families["machine_sections_only"]["counts"] == {"machine_only": 1}
    assert families["quality"]["recorded"] == 3 and families["quality"]["counts"] == {"partial": 1}
    assert families["forward_quotes"]["counts"] == {"checked": 2, "verified": 1, "unverified": 1,
                                                  "near_miss": 1, "other_unverified": 0, "dropped": 0}
    assert families["evidence_snap"]["counts"] == {"checked": 5, "exact": 2, "would_snap": 1, "snapped": 1, "left": 1}
    expected_reasons = [{"sic_prefix": "60", "reason": reason, "count": 1} for reason in ("gap", "thin")]
    assert result["partial_reasons_by_sic"] == expected_reasons
    assert sorted(partials, key=lambda row: row["reason"]) == expected_reasons
    for statement in statements:
        assert not any(column.compare(Summary.raw_summary.expression) for column in statement.selected_columns)
    assert len(statements) == 2  # each projection is one bounded query, with no lazy Summary loads
    html, text = email_service.render_data_quality_report({"summary_audits": result})
    for rendered in (html, text):
        assert "recorded 2 / snapshots 5" in rendered
        assert "unavailable 3 (missing 2, malformed 1)" in rendered
        assert "would snap=1" in rendered and "snapped=1" in rendered
        assert "snapshots with untraceable figures: 1 (50.0% of recorded)" in rendered
        assert "snapshots with unrepaired evidence: 1 (50.0% of recorded)" in rendered
        assert "not weekly generation attempts" in rendered
        assert "does not prove grounding was available" in rendered


@pytest.mark.parametrize("family, field, value", [
    ("forward_quote_audit", "checked", -1), ("forward_quote_audit", "checked", 2.0),
    ("forward_quote_audit", "verified", True), ("forward_quote_audit", "near_miss", 2),
    ("forward_quote_audit", "unverified", "not a list"), ("forward_quote_audit", "unverified", [{}]),
    ("forward_quote_audit", "armed", "false"), ("forward_quote_audit", "dropped", [{"speaker": "CEO", "quote": "text"}]),
    ("evidence_snap_audit", "checked", True), ("evidence_snap_audit", "exact", -1),
    ("evidence_snap_audit", "would_snap", "not a list"), ("evidence_snap_audit", "snapped", [{}]),
    ("evidence_snap_audit", "left", [{"surface": "notable_footnotes", "score": float("nan")}]),
    ("evidence_snap_audit", "armed", True),
])
def test_malformed_family_does_not_add_a_recorded_zero(sessions, family, field, value):
    audit = forward() if family == "forward_quote_audit" else snap()
    audit[field] = value
    with sessions() as db:
        store(db, [{family: audit}])
        result = quality.summary_audit_counts(db)
    key = "forward_quotes" if family == "forward_quote_audit" else "evidence_snap"
    assert result["families"][key] == {"recorded": 0, "missing": 0, "malformed": 1,
                                     "flagged": 0, "counts": {}, "unavailable": 1, "flagged_pct": None}


def test_missing_and_zero_population_are_unavailable_in_both_renderers(sessions):
    with sessions() as db:
        empty = quality.summary_audit_counts(db)
        store(db, [{"quality": "malformed metadata"}])
        malformed = quality.summary_audit_counts(db)
    assert empty["snapshot_population"] == 0
    assert all(f["recorded"] == 0 and f["flagged_pct"] is None for f in empty["families"].values())
    assert all(malformed["families"][k]["malformed"] == 1 for k in ("quality", "figure_trace", "machine_sections_only"))
    for report in ({}, {"summary_audits": empty}):
        html, text = email_service.render_data_quality_report(deepcopy(report))
        for rendered in (html, text):
            assert "counts unavailable" in rendered
            assert "Weekly judged generation readout" in rendered
