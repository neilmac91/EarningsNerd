"""Unit tests for the P3 financial-facts normalizer + writer."""

import uuid
from datetime import date

import pytest

from app.services import facts_service as svc


class TestNormalize:
    def test_units_periods_and_fiscal_year(self):
        standardized = {
            "revenue": {"current": {"period": "2024-09-28", "value": 391035000000.0}},
            "earnings_per_share": {"current": {"period": "2024-09-28", "value": 6.13}},
            "net_margin": {"current": {"period": "2024-09-28", "value": 24.3}},
        }
        facts = svc.normalize_standardized_to_facts(1, 10, "0000320193-24-000123", "10-K", standardized)
        by = {f["concept"]: f for f in facts}
        assert by["revenue"]["unit"] == "USD"
        assert by["earnings_per_share"]["unit"] == "USD/shares"
        assert by["net_margin"]["unit"] == "pure"
        assert by["revenue"]["period_end"] == date(2024, 9, 28)
        assert by["revenue"]["fiscal_year"] == 2024
        assert by["revenue"]["fiscal_period"] == "FY"
        assert by["revenue"]["accession"] == "0000320193-24-000123"
        assert by["revenue"]["value"] == 391035000000.0
        assert by["revenue"]["source"] == "edgar_xbrl"

    def test_multi_period_series_emits_one_fact_per_period(self):
        standardized = {
            "revenue": {
                "current": {"period": "2024-09-28", "value": 391.0},
                "series": [
                    {"period": "2024-09-28", "value": 391.0, "form": "10-K"},
                    {"period": "2023-09-30", "value": 383.0, "form": "10-K"},
                    {"period": "2022-09-24", "value": 394.0, "form": "10-K"},
                ],
            },
        }
        facts = svc.normalize_standardized_to_facts(1, 10, "acc", "10-K", standardized)
        assert [f["period_end"] for f in facts] == [
            date(2024, 9, 28), date(2023, 9, 30), date(2022, 9, 24)
        ]
        assert [f["value"] for f in facts] == [391.0, 383.0, 394.0]
        assert all(f["concept"] == "revenue" and f["fiscal_period"] == "FY" for f in facts)

    def test_series_point_form_overrides_filing_form(self):
        # A point's own form drives its fiscal_period (e.g. a 10-Q period inside a mixed series).
        standardized = {
            "revenue": {"series": [{"period": "2024-03-31", "value": 90.0, "form": "10-Q"}]},
        }
        facts = svc.normalize_standardized_to_facts(1, 10, "acc", "10-K", standardized)
        assert facts[0]["fiscal_period"] is None  # 10-Q point → no FY
        assert facts[0]["form"] == "10-Q"

    def test_10q_has_no_fiscal_period(self):
        facts = svc.normalize_standardized_to_facts(
            1, 10, "acc", "10-Q", {"revenue": {"current": {"period": "2024-03-31", "value": 90.0}}}
        )
        assert facts[0]["fiscal_period"] is None

    def test_skips_malformed_entries(self):
        standardized = {
            "no_current": {"prior": {"period": "2023-09-30", "value": 1.0}},
            "no_value": {"current": {"period": "2024-09-28"}},
            "non_numeric": {"current": {"period": "2024-09-28", "value": "lots"}},
            "boolean": {"current": {"period": "2024-09-28", "value": True}},  # bool excluded
            "bad_date": {"current": {"period": "not-a-date", "value": 5.0}},
            "good": {"current": {"period": "2024-09-28", "value": 5.0}},
        }
        facts = svc.normalize_standardized_to_facts(1, 10, "acc", "10-K", standardized)
        assert [f["concept"] for f in facts] == ["good"]

    def test_unmapped_concept_defaults_to_usd(self):
        facts = svc.normalize_standardized_to_facts(
            1, 10, "acc", "10-K", {"some_future_metric": {"current": {"period": "2024-09-28", "value": 1.0}}}
        )
        assert facts[0]["unit"] == "USD"

    def test_empty_or_malformed_inputs(self):
        good = {"revenue": {"current": {"period": "2024-09-28", "value": 1.0}}}
        assert svc.normalize_standardized_to_facts(1, 10, None, "10-K", good) == []  # no accession
        assert svc.normalize_standardized_to_facts(1, 10, "acc", "10-K", None) == []
        assert svc.normalize_standardized_to_facts(1, 10, "acc", "10-K", "nope") == []


def _gatefact(concept, value, period_end=date(2024, 9, 28)):
    return {
        "company_id": 1,
        "filing_id": None,
        "concept": concept,
        "unit": "USD",
        "period_end": period_end,
        "fiscal_year": 2024,
        "fiscal_period": "FY",
        "value": value,
        "form": "10-K",
        "accession": "ACC",
        "source": "edgar_xbrl",
    }


class TestReconcileGate:
    """Pure, no-DB tests for the local-invariant reconciliation gate (§3.5)."""

    def test_clean_facts_all_reconciled(self):
        accepted, rejected = svc.reconcile_facts(
            [_gatefact("revenue", 100.0), _gatefact("net_income", 20.0)]
        )
        assert rejected == []
        assert all(f["reconciled"] for f in accepted)

    def test_negative_revenue_hard_rejected_but_loss_kept(self):
        # Negative revenue is impossible (drop); a negative net_income is a legitimate loss (keep).
        accepted, rejected = svc.reconcile_facts(
            [_gatefact("revenue", -5.0), _gatefact("net_income", -2.0)]
        )
        assert [f["concept"] for f in rejected] == ["revenue"]
        assert [f["concept"] for f in accepted] == ["net_income"]
        assert accepted[0]["reconciled"] is True

    def test_zero_where_prior_nonzero_flagged(self):
        accepted, _ = svc.reconcile_facts(
            [_gatefact("revenue", 0.0)], prior_values={"revenue": 100.0}
        )
        assert accepted[0]["reconciled"] is False

    def test_standalone_zero_revenue_ok(self):
        accepted, rejected = svc.reconcile_facts([_gatefact("revenue", 0.0)])
        assert rejected == []
        assert accepted[0]["reconciled"] is True

    def test_eps_sign_mismatch_flags_eps_only(self):
        # Net loss but positive EPS -> parse error (the MU class). Flag the EPS rows, not net_income.
        accepted, _ = svc.reconcile_facts(
            [
                _gatefact("net_income", -50.0),
                _gatefact("earnings_per_share", 1.2),
                _gatefact("eps_diluted", 1.1),
            ]
        )
        by = {f["concept"]: f for f in accepted}
        assert by["earnings_per_share"]["reconciled"] is False
        assert by["eps_diluted"]["reconciled"] is False
        assert by["net_income"]["reconciled"] is True

    def test_diluted_exceeds_basic_flagged(self):
        accepted, _ = svc.reconcile_facts(
            [
                _gatefact("net_income", 100.0),
                _gatefact("earnings_per_share", 2.0),
                _gatefact("eps_diluted", 2.5),  # diluted should never exceed basic
            ]
        )
        by = {f["concept"]: f for f in accepted}
        assert by["eps_diluted"]["reconciled"] is False
        assert by["earnings_per_share"]["reconciled"] is True

    def test_magnitude_swing_flagged(self):
        accepted, _ = svc.reconcile_facts(
            [_gatefact("revenue", 10000.0)], prior_values={"revenue": 100.0}
        )
        assert accepted[0]["reconciled"] is False  # 100x jump = likely scale bug

    def test_within_one_order_of_magnitude_ok(self):
        accepted, _ = svc.reconcile_facts(
            [_gatefact("revenue", 150.0)], prior_values={"revenue": 100.0}
        )
        assert accepted[0]["reconciled"] is True

    def test_period_mismatch_flagged(self):
        accepted, _ = svc.reconcile_facts(
            [_gatefact("revenue", 100.0, period_end=date(2024, 9, 28))],
            period_of_report=date(2024, 6, 30),
        )
        assert accepted[0]["reconciled"] is False

    def test_period_match_ok(self):
        accepted, _ = svc.reconcile_facts(
            [_gatefact("revenue", 100.0, period_end=date(2024, 9, 28))],
            period_of_report=date(2024, 9, 28),
        )
        assert accepted[0]["reconciled"] is True

    # --- multi-period batches (PR-C feeds these; checks must be period-aware) -------------

    def test_cross_concept_checks_are_per_period(self):
        # 2023 is a clean profit; 2024 is a loss with a positive EPS (sign mismatch). The
        # mismatch must flag only 2024's EPS — not 2023's, which shares the batch.
        facts = [
            _gatefact("net_income", 50.0, date(2023, 9, 30)),
            _gatefact("earnings_per_share", 1.0, date(2023, 9, 30)),
            _gatefact("net_income", -50.0, date(2024, 9, 28)),
            _gatefact("earnings_per_share", 1.0, date(2024, 9, 28)),
        ]
        accepted, _ = svc.reconcile_facts(facts)
        by = {(f["concept"], f["period_end"]): f for f in accepted}
        assert by[("earnings_per_share", date(2023, 9, 30))]["reconciled"] is True
        assert by[("earnings_per_share", date(2024, 9, 28))]["reconciled"] is False

    def test_prior_chains_within_multi_period_batch(self):
        # Each year is compared to the year before it from WITHIN the batch (not to a single
        # earliest-period cutoff): 2024's 50x jump vs 2023 is flagged; 2023 vs 2022 is fine.
        facts = [
            _gatefact("revenue", 100.0, date(2022, 9, 30)),
            _gatefact("revenue", 120.0, date(2023, 9, 30)),
            _gatefact("revenue", 6000.0, date(2024, 9, 28)),
        ]
        accepted, _ = svc.reconcile_facts(facts)
        by = {f["period_end"]: f for f in accepted}
        assert by[date(2022, 9, 30)]["reconciled"] is True  # no prior
        assert by[date(2023, 9, 30)]["reconciled"] is True  # 120 vs 100
        assert by[date(2024, 9, 28)]["reconciled"] is False  # 6000 vs 120 (chained prior)

    def test_period_check_flags_only_latest_period(self):
        facts = [
            _gatefact("revenue", 90.0, date(2023, 9, 30)),  # comparative prior period
            _gatefact("revenue", 100.0, date(2024, 9, 28)),  # current period
        ]
        # Filing reports the 2024 period — both fine; the comparative 2023 row is not flagged.
        ok, _ = svc.reconcile_facts(facts, period_of_report=date(2024, 9, 28))
        assert all(f["reconciled"] for f in ok)
        # Filing's reported period disagrees with the latest fact → flag the latest period only.
        flagged, _ = svc.reconcile_facts(facts, period_of_report=date(2024, 6, 30))
        by = {f["period_end"]: f for f in flagged}
        assert by[date(2023, 9, 30)]["reconciled"] is True  # comparative, never flagged
        assert by[date(2024, 9, 28)]["reconciled"] is False  # latest != period_of_report


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _new_company(db):
    from app.models import Company

    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=suffix, ticker=("T" + suffix[:4]).upper(), name=f"Co {suffix}")
    db.add(company)
    db.commit()
    db.refresh(company)
    return company.id


@pytest.mark.requires_db
class TestUpsert:
    def test_insert_then_idempotent(self):
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        cid = _new_company(db)
        facts = svc.normalize_standardized_to_facts(
            cid,
            None,
            "ACC1",
            "10-K",
            {
                "revenue": {"current": {"period": "2024-09-28", "value": 100.0}},
                "net_income": {"current": {"period": "2024-09-28", "value": 20.0}},
            },
        )
        assert svc.upsert_facts(db, facts) == {"inserted": 2, "skipped": 0, "rejected": 0}

        rows = db.query(FinancialFact).filter_by(company_id=cid).all()
        assert len(rows) == 2
        assert all(r.is_latest for r in rows)
        assert all(r.reconciled for r in rows)  # clean facts pass the gate

        # Re-upserting the identical facts is a no-op (idempotent on the identity key).
        assert svc.upsert_facts(db, facts) == {"inserted": 0, "skipped": 2, "rejected": 0}
        assert db.query(FinancialFact).filter_by(company_id=cid).count() == 2
        db.close()

    def test_restatement_flips_is_latest(self):
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        cid = _new_company(db)
        base = {
            "company_id": cid,
            "filing_id": None,
            "concept": "revenue",
            "unit": "USD",
            "period_end": date(2024, 9, 28),
            "fiscal_year": 2024,
            "fiscal_period": "FY",
            "form": "10-K",
            "source": "edgar_xbrl",
        }
        svc.upsert_facts(db, [{**base, "value": 100.0, "accession": "ACC1"}])
        # A restatement: same period under a new accession with a corrected value.
        svc.upsert_facts(db, [{**base, "value": 110.0, "accession": "ACC2", "form": "10-K/A"}])

        rows = {
            r.accession: r
            for r in db.query(FinancialFact).filter_by(company_id=cid, concept="revenue").all()
        }
        assert len(rows) == 2  # original + restatement coexist (audit trail preserved)
        assert not rows["ACC1"].is_latest  # original demoted
        assert rows["ACC2"].is_latest  # restatement is current
        assert float(rows["ACC2"].value) == 110.0
        db.close()


@pytest.mark.requires_db
class TestUpsertReconciliation:
    def test_upsert_persists_flag_and_drops_impossible(self):
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        cid = _new_company(db)
        base = {
            "company_id": cid,
            "filing_id": None,
            "unit": "USD",
            "fiscal_period": "FY",
            "form": "10-K",
            "source": "edgar_xbrl",
        }
        # Prior year: clean revenue of 100.
        svc.upsert_facts(db, [
            {**base, "concept": "revenue", "period_end": date(2023, 9, 30),
             "fiscal_year": 2023, "value": 100.0, "accession": "R23"},
        ])
        # Current year: revenue collapses to 0 (parse miss vs prior → flagged) and an
        # impossible negative total_assets (→ hard-rejected, not stored).
        res = svc.upsert_facts(db, [
            {**base, "concept": "revenue", "period_end": date(2024, 9, 28),
             "fiscal_year": 2024, "value": 0.0, "accession": "R24"},
            {**base, "concept": "total_assets", "period_end": date(2024, 9, 28),
             "fiscal_year": 2024, "value": -5.0, "accession": "R24"},
        ])
        assert res["inserted"] == 1
        assert res["rejected"] == 1

        rev24 = db.query(FinancialFact).filter_by(
            company_id=cid, concept="revenue", accession="R24"
        ).first()
        assert rev24 is not None and rev24.reconciled is False  # stored but flagged
        assert db.query(FinancialFact).filter_by(
            company_id=cid, concept="total_assets"
        ).count() == 0  # impossible value never stored
        db.close()


_BACKFILL_STD = {
    "revenue": {"current": {"period": "2024-09-28", "value": 100.0}},
    "net_income": {"current": {"period": "2024-09-28", "value": 20.0}},
}


def _fake_extract(xbrl):
    # Only our marked filing yields metrics, so the test is isolated from any other filings that
    # may carry xbrl_data in the shared test DB.
    if isinstance(xbrl, dict) and xbrl.get("mark") == "X":
        return _BACKFILL_STD
    return {}


@pytest.mark.requires_db
class TestBackfill:
    def test_backfill_populates_facts_and_is_idempotent(self):
        from datetime import datetime

        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        cid = _new_company(db)
        filing = Filing(
            company_id=cid,
            accession_number=f"ACC-bf-{uuid.uuid4().hex[:8]}",
            filing_type="10-K",
            filing_date=datetime(2024, 11, 1),
            document_url="https://sec.example/x.htm",
            sec_url="https://sec.example/",
            xbrl_data={"mark": "X"},
        )
        db.add(filing)
        db.commit()

        stats = svc.backfill_facts(db, extract=_fake_extract, cross_check=False)
        assert stats["facts_inserted"] == 2  # revenue + net_income from our filing
        assert db.query(FinancialFact).filter_by(company_id=cid).count() == 2

        # Re-running is a no-op (idempotent on the identity key).
        stats2 = svc.backfill_facts(db, extract=_fake_extract, cross_check=False)
        assert stats2["facts_inserted"] == 0
        assert stats2["facts_skipped"] >= 2
        db.close()

    def test_stamps_processed_and_incremental_skips(self):
        from datetime import datetime

        from app.database import SessionLocal
        from app.models import Filing

        db = SessionLocal()
        cid = _new_company(db)
        filing = Filing(
            company_id=cid,
            accession_number=f"ACC-inc-{uuid.uuid4().hex[:8]}",
            filing_type="10-K",
            filing_date=datetime(2024, 11, 1),
            document_url="https://sec.example/x.htm",
            sec_url="https://sec.example/",
            xbrl_data={"mark": "X"},
        )
        db.add(filing)
        db.commit()

        svc.backfill_facts(db, extract=_fake_extract, cross_check=False)
        db.refresh(filing)
        assert filing.processed_facts_at is not None  # stamped after normalization
        stamped_at = filing.processed_facts_at

        # An incremental pass skips already-stamped filings (timestamp unchanged).
        svc.backfill_facts(db, extract=_fake_extract, only_unprocessed=True, cross_check=False)
        db.refresh(filing)
        assert filing.processed_facts_at == stamped_at
        db.close()


_COMPANYFACTS = {
    "facts": {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        {"start": "2024-01-01", "end": "2024-12-31", "val": 1000.0, "form": "10-K"},
                        {"start": "2024-10-01", "end": "2024-12-31", "val": 250.0, "form": "10-K"},  # Q4 → skip
                        {"start": "2023-01-01", "end": "2023-12-31", "val": 900.0, "form": "10-K"},
                    ]
                }
            },
            "NetIncomeLoss": {"units": {"USD": [
                {"start": "2024-01-01", "end": "2024-12-31", "val": 100.0},
            ]}},
            "Assets": {"units": {"USD": [{"end": "2024-12-31", "val": 5000.0}]}},  # instant
        }
    }
}


class TestExtractAuthoritative:
    def test_picks_annual_durations_and_instants(self):
        auth = svc.extract_authoritative_values(_COMPANYFACTS)
        assert auth[("revenue", date(2024, 12, 31))] == 1000.0  # annual, not the Q4 250
        assert auth[("revenue", date(2023, 12, 31))] == 900.0
        assert auth[("net_income", date(2024, 12, 31))] == 100.0
        assert auth[("total_assets", date(2024, 12, 31))] == 5000.0

    def test_malformed_returns_empty(self):
        assert svc.extract_authoritative_values(None) == {}
        assert svc.extract_authoritative_values({"facts": {}}) == {}


def _cfact(concept, value, reconciled=True, period_end=date(2024, 12, 31)):
    return {
        "concept": concept,
        "period_end": period_end,
        "value": value,
        "reconciled": reconciled,
        "source": "edgar_xbrl",
    }


class TestCrossCheckFacts:
    def setup_method(self):
        self.auth = svc.extract_authoritative_values(_COMPANYFACTS)

    def test_within_tolerance_confirms_value(self):
        out = svc.cross_check_facts([_cfact("revenue", 1005.0)], self.auth)  # 0.5% off
        assert out[0]["value"] == 1005.0  # unchanged
        assert out[0]["reconciled"] is True
        assert out[0]["source"] == "edgar_xbrl"

    def test_mismatch_replaces_with_authoritative(self):
        out = svc.cross_check_facts([_cfact("revenue", 1.0)], self.auth)  # scale bug
        assert out[0]["value"] == 1000.0
        assert out[0]["source"] == "companyfacts"
        assert out[0]["reconciled"] is True

    def test_confirmation_clears_invariant_flag(self):
        out = svc.cross_check_facts([_cfact("revenue", 1000.0, reconciled=False)], self.auth)
        assert out[0]["reconciled"] is True  # authoritative confirms → flag cleared

    def test_no_authoritative_for_period_unchanged(self):
        f = _cfact("revenue", 42.0, reconciled=False, period_end=date(2022, 12, 31))
        out = svc.cross_check_facts([f], self.auth)
        assert out[0]["value"] == 42.0 and out[0]["reconciled"] is False

    def test_non_headline_concept_unchanged(self):
        f = _cfact("gross_profit", 7.0, reconciled=False)
        out = svc.cross_check_facts([f], self.auth)
        assert out[0]["value"] == 7.0 and out[0]["reconciled"] is False

    def test_empty_authoritative_is_noop(self):
        f = _cfact("revenue", 1.0)
        assert svc.cross_check_facts([f], {}) == [f]


@pytest.mark.requires_db
class TestBackfillCrossCheck:
    def test_backfill_corrects_headline_via_companyfacts(self):
        from datetime import datetime

        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        cid = _new_company(db)
        filing = Filing(
            company_id=cid,
            accession_number=f"ACC-cc-{uuid.uuid4().hex[:8]}",
            filing_type="10-K",
            filing_date=datetime(2025, 2, 1),
            document_url="https://sec.example/x.htm",
            sec_url="https://sec.example/",
            xbrl_data={"mark": "CC"},
        )
        db.add(filing)
        db.commit()

        def _extract(xbrl):  # parsed revenue is scale-bugged for FY2024
            if isinstance(xbrl, dict) and xbrl.get("mark") == "CC":
                return {"revenue": {"current": {"period": "2024-12-31", "value": 1.0}}}
            return {}

        def _fetcher(_cik):
            return _COMPANYFACTS

        svc.backfill_facts(db, extract=_extract, companyfacts_fetcher=_fetcher)

        row = db.query(FinancialFact).filter_by(company_id=cid, concept="revenue").first()
        assert row is not None
        assert float(row.value) == 1000.0  # corrected to the authoritative companyfacts value
        assert row.source == "companyfacts"
        assert row.reconciled is True
        db.close()


@pytest.mark.requires_db
class TestGetFundamentals:
    def test_returns_per_concept_series_oldest_first(self):
        from app.database import SessionLocal
        from app.models import Company

        db = SessionLocal()
        suffix = uuid.uuid4().hex[:8]
        company = Company(cik=suffix, ticker=("F" + suffix[:4]).upper(), name=f"Fund {suffix}")
        db.add(company)
        db.commit()
        db.refresh(company)

        common = {"concept": "revenue", "unit": "USD", "fiscal_period": "FY", "form": "10-K",
                  "company_id": company.id, "filing_id": None, "source": "edgar_xbrl"}
        svc.upsert_facts(db, [
            {**common, "period_end": date(2023, 9, 30), "fiscal_year": 2023, "value": 80.0, "accession": "A23"},
        ])
        svc.upsert_facts(db, [
            {**common, "period_end": date(2024, 9, 28), "fiscal_year": 2024, "value": 100.0, "accession": "A24"},
        ])

        out = svc.get_fundamentals(db, company.ticker.lower())  # case-insensitive
        assert out["ticker"] == company.ticker
        revenue = next(c for c in out["concepts"] if c["concept"] == "revenue")
        assert revenue["unit"] == "USD"
        assert [p["value"] for p in revenue["points"]] == [80.0, 100.0]  # oldest → newest
        assert [p["fiscal_year"] for p in revenue["points"]] == [2023, 2024]
        db.close()

    def test_unknown_ticker_returns_none(self):
        from app.database import SessionLocal

        db = SessionLocal()
        assert svc.get_fundamentals(db, "NOPE-NOT-A-TICKER") is None
        db.close()
