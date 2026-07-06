"""Unit tests for the companyfacts ingestion path (Multi-Period Analysis M1).

Covers the period classifier (duration windows, distance-anchored quarter labels, the fy/fp trap),
Q4 derivation, same-period derived metrics, the bulk writer (identity skip, is_latest demotion,
the D1 NULL-fiscal_period demotion), and the TTL/dedup semantics of ``ingest_companyfacts``.

Payloads are built programmatically — companyfacts items are small dicts, and explicit builders
keep each scenario's trap visible in the test itself.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.services import facts_service as svc

REV_TAG = "RevenueFromContractWithCustomerExcludingAssessedTax"


def _item(val, end, *, start=None, accn="ACC-1", fy=2024, fp="FY", form="10-K", filed="2024-02-15"):
    item = {"val": val, "end": end, "accn": accn, "fy": fy, "fp": fp, "form": form, "filed": filed}
    if start is not None:
        item["start"] = start
    return item


def _payload(usgaap):
    return {"cik": 1234567, "entityName": "TEST CO", "facts": {"us-gaap": usgaap}}


def _calendar_payload():
    """Calendar-FY company: FY2022-24 annual, 2024 Q1-Q3 discrete quarters, a 9-month YTD slice
    (must be skipped), the comparative-quarter fy/fp TRAP, and an in-progress 2025 Q1."""
    revenue = [
        _item(800.0, "2022-12-31", start="2022-01-01", accn="K22", fy=2022, filed="2023-02-15"),
        _item(1000.0, "2023-12-31", start="2023-01-01", accn="K23", fy=2023, filed="2024-02-15"),
        _item(1200.0, "2024-12-31", start="2024-01-01", accn="K24", fy=2024, filed="2025-02-15"),
        _item(280.0, "2024-03-31", start="2024-01-01", accn="Q1-24", fy=2024, fp="Q1",
              form="10-Q", filed="2024-05-05"),
        _item(300.0, "2024-06-30", start="2024-04-01", accn="Q2-24", fy=2024, fp="Q2",
              form="10-Q", filed="2024-08-05"),
        _item(310.0, "2024-09-30", start="2024-07-01", accn="Q3-24", fy=2024, fp="Q3",
              form="10-Q", filed="2024-11-05"),
        # THE TRAP: the prior-year comparative quarter inside the 2024 Q2 10-Q carries the
        # REPORTING FILING's fy/fp (2024/Q2) — for the fact's own period (2023 Q2) both would be
        # wrong to trust blindly; the window classifier must label it Q2 of fiscal 2023.
        _item(250.0, "2023-06-30", start="2023-04-01", accn="Q2-24", fy=2024, fp="Q2",
              form="10-Q", filed="2024-08-05"),
        # A 9-month YTD slice (also present in real 10-Qs) — wrong duration, never stored.
        _item(890.0, "2024-09-30", start="2024-01-01", accn="Q3-24", fy=2024, fp="Q3",
              form="10-Q", filed="2024-11-05"),
        # In-progress fiscal 2025: Q1 not inside any completed FY window → earliest-filed fp wins.
        _item(320.0, "2025-03-31", start="2025-01-01", accn="Q1-25", fy=2025, fp="Q1",
              form="10-Q", filed="2025-05-05"),
    ]
    assets = [
        _item(5000.0, "2023-12-31", accn="K23", fy=2023, filed="2024-02-15"),
        _item(6000.0, "2024-12-31", accn="K24", fy=2024, filed="2025-02-15"),
        _item(5600.0, "2024-06-30", accn="Q2-24", fy=2024, fp="Q2", form="10-Q", filed="2024-08-05"),
    ]
    return _payload({REV_TAG: {"units": {"USD": revenue}}, "Assets": {"units": {"USD": assets}}})


def _by_key(facts):
    return {(f["concept"], f["period_end"], f["fiscal_period"]): f for f in facts}


class TestNormalizeCompanyfacts:
    def test_annual_quarter_and_ytd_classification(self):
        facts, meta = svc.normalize_companyfacts(1, _calendar_payload())
        by = _by_key(facts)

        fy24 = by[("revenue", date(2024, 12, 31), "FY")]
        assert fy24["value"] == 1200.0
        assert fy24["fiscal_year"] == 2024
        assert fy24["source"] == "companyfacts"
        assert fy24["reconciled"] is True
        assert fy24["accession"] == "K24"
        assert fy24["raw_tag"] == f"us-gaap:{REV_TAG}"

        # Discrete quarters labelled by distance from fiscal year end.
        assert by[("revenue", date(2024, 3, 31), "Q1")]["value"] == 280.0
        assert by[("revenue", date(2024, 6, 30), "Q2")]["value"] == 300.0
        assert by[("revenue", date(2024, 9, 30), "Q3")]["value"] == 310.0

        # The YTD 9-month slice must NOT exist under any label.
        ytd_rows = [f for f in facts if f["concept"] == "revenue"
                    and f["period_end"] == date(2024, 9, 30) and f["value"] == 890.0]
        assert ytd_rows == []
        assert meta["unsupported_ifrs"] is False

    def test_comparative_quarter_trap_labelled_by_window_not_fp(self):
        facts, _ = svc.normalize_companyfacts(1, _calendar_payload())
        by = _by_key(facts)
        trap = by[("revenue", date(2023, 6, 30), "Q2")]
        # fp said Q2 (coincidentally right) but fy said 2024 — the window assigns fiscal 2023.
        assert trap["fiscal_year"] == 2023
        assert trap["value"] == 250.0

    def test_in_progress_year_falls_back_to_original_filer_fp(self):
        facts, _ = svc.normalize_companyfacts(1, _calendar_payload())
        by = _by_key(facts)
        q1_25 = by[("revenue", date(2025, 3, 31), "Q1")]
        assert q1_25["fiscal_year"] == 2025  # the original 10-Q's fy — trustworthy for its own period

    def test_gap_tolerant_labels_survive_missing_sibling_quarters(self):
        # IPO-year shape: only Q3 exists inside the FY window. A sorted-position scheme would call
        # it Q1; the distance-to-year-end anchor must call it Q3.
        payload = _payload({REV_TAG: {"units": {"USD": [
            _item(1000.0, "2023-12-31", start="2023-01-01", accn="K23", fy=2023, filed="2024-02-15"),
            _item(240.0, "2023-09-30", start="2023-07-01", accn="Q3-23", fy=2023, fp="Q3",
                  form="10-Q", filed="2023-11-05"),
        ]}}})
        facts, _ = svc.normalize_companyfacts(1, payload)
        by = _by_key(facts)
        assert ("revenue", date(2023, 9, 30), "Q3") in by

    def test_jan_fye_quarters_group_with_window_end_year(self):
        # Jan-FYE retailer (the WMT shape): FY ends 2024-01-31; quarters end Apr/Jul/Oct 2023.
        payload = _payload({REV_TAG: {"units": {"USD": [
            _item(6000.0, "2024-01-31", start="2023-02-01", accn="K24", fy=2024, filed="2024-03-15"),
            _item(1400.0, "2023-04-30", start="2023-02-01", accn="Q1", fy=2024, fp="Q1",
                  form="10-Q", filed="2023-06-01"),
            _item(1500.0, "2023-07-31", start="2023-05-01", accn="Q2", fy=2024, fp="Q2",
                  form="10-Q", filed="2023-09-01"),
            _item(1550.0, "2023-10-31", start="2023-08-01", accn="Q3", fy=2024, fp="Q3",
                  form="10-Q", filed="2023-12-01"),
        ]}}})
        facts, _ = svc.normalize_companyfacts(1, payload)
        by = _by_key(facts)
        assert by[("revenue", date(2023, 4, 30), "Q1")]["fiscal_year"] == 2024
        assert by[("revenue", date(2023, 10, 31), "Q3")]["fiscal_year"] == 2024
        assert by[("revenue", date(2024, 1, 31), "FY")]["fiscal_year"] == 2024

    def test_53_week_year_still_classifies_annual(self):
        payload = _payload({REV_TAG: {"units": {"USD": [
            _item(1000.0, "2024-02-03", start="2023-01-29", accn="K", fy=2023, filed="2024-03-20"),
        ]}}})  # 371-day fiscal year
        facts, _ = svc.normalize_companyfacts(1, payload)
        assert [(f["fiscal_period"], f["fiscal_year"]) for f in facts
                if f["concept"] == "revenue"] == [("FY", 2024)]

    def test_latest_filed_wins_restatement(self):
        payload = _payload({REV_TAG: {"units": {"USD": [
            _item(1000.0, "2023-12-31", start="2023-01-01", accn="K23", fy=2023, filed="2024-02-15"),
            _item(1010.0, "2023-12-31", start="2023-01-01", accn="K23A", fy=2023,
                  form="10-K/A", filed="2024-06-01"),
        ]}}})
        facts, _ = svc.normalize_companyfacts(1, payload)
        rows = [f for f in facts if f["concept"] == "revenue"]
        assert len(rows) == 1
        assert rows[0]["value"] == 1010.0
        assert rows[0]["accession"] == "K23A"

    def test_tag_migration_merges_history_with_per_period_priority(self):
        # Old years only under SalesRevenueNet; new years under the ASC-606 tag; one overlapping
        # period exists under both → the higher-priority tag's value wins that period.
        payload = _payload({
            "SalesRevenueNet": {"units": {"USD": [
                _item(700.0, "2016-12-31", start="2016-01-01", accn="K16", fy=2016, filed="2017-02-15"),
                _item(777.0, "2017-12-31", start="2017-01-01", accn="K17", fy=2017, filed="2018-02-15"),
            ]}},
            REV_TAG: {"units": {"USD": [
                _item(780.0, "2017-12-31", start="2017-01-01", accn="K18", fy=2018, filed="2019-02-15"),
                _item(820.0, "2018-12-31", start="2018-01-01", accn="K18", fy=2018, filed="2019-02-15"),
            ]}},
        })
        facts, _ = svc.normalize_companyfacts(1, payload)
        by = _by_key(facts)
        assert by[("revenue", date(2016, 12, 31), "FY")]["value"] == 700.0  # old tag's era survives
        assert by[("revenue", date(2018, 12, 31), "FY")]["value"] == 820.0
        assert by[("revenue", date(2017, 12, 31), "FY")]["value"] == 780.0  # priority tag wins overlap

    def test_instants_fy_end_labelled_fy_quarter_end_labelled_qn(self):
        facts, _ = svc.normalize_companyfacts(1, _calendar_payload())
        by = _by_key(facts)
        assert by[("total_assets", date(2024, 12, 31), "FY")]["value"] == 6000.0
        assert by[("total_assets", date(2024, 6, 30), "Q2")]["value"] == 5600.0
        assert by[("total_assets", date(2024, 12, 31), "FY")]["period_start"] is None

    def test_eps_reads_usd_per_share_unit(self):
        payload = _payload({
            REV_TAG: {"units": {"USD": [
                _item(1000.0, "2023-12-31", start="2023-01-01", accn="K23", fy=2023, filed="2024-02-15"),
            ]}},
            "EarningsPerShareBasic": {"units": {"USD/shares": [
                _item(3.25, "2023-12-31", start="2023-01-01", accn="K23", fy=2023, filed="2024-02-15"),
            ]}},
        })
        facts, _ = svc.normalize_companyfacts(1, payload)
        by = _by_key(facts)
        eps = by[("earnings_per_share", date(2023, 12, 31), "FY")]
        assert eps["value"] == 3.25
        assert eps["unit"] == "USD/shares"

    def test_ytd9_slice_powers_q4_derivation_but_is_never_stored(self):
        # FY + Q3 + YTD9 only (Q1/Q2 missing — edge of history): the YTD9 slice must never emit a
        # fact row (it ends at the SAME date as Q3), yet Q4 = FY − YTD9 must still derive.
        revenue = [
            _item(1200.0, "2024-12-31", start="2024-01-01", accn="K24", fy=2024, filed="2025-02-15"),
            _item(310.0, "2024-09-30", start="2024-07-01", accn="Q3-24", fy=2024, fp="Q3",
                  form="10-Q", filed="2024-11-05"),
            _item(890.0, "2024-09-30", start="2024-01-01", accn="Q3-24", fy=2024, fp="Q3",
                  form="10-Q", filed="2024-11-05"),
        ]
        facts, _ = svc.normalize_companyfacts(1, _payload({REV_TAG: {"units": {"USD": revenue}}}))
        by = _by_key(facts)
        # The discrete Q3 keeps its own value — the nine-month 890 never lands on any row.
        assert by[("revenue", date(2024, 9, 30), "Q3")]["value"] == 310.0
        assert all(f["value"] != 890.0 for f in facts)
        q4 = by[("revenue", date(2024, 12, 31), "Q4")]
        assert q4["value"] == pytest.approx(310.0)  # 1200 − 890
        assert q4["source"] == "derived"

    def test_rejected_negative_derived_q4_leaves_no_margins_behind(self):
        # Recast trap: FY revenue restated below the still-original-vintage YTD9 → derived Q4
        # revenue < 0 → hard-rejected. The Q4 margins computed FROM that doomed row must be
        # rejected with it (they'd pass the filter themselves — margins may be negative).
        payload = _payload({
            REV_TAG: {"units": {"USD": [
                _item(600.0, "2024-12-31", start="2024-01-01", accn="K24", filed="2025-02-15"),
                _item(740.0, "2024-09-30", start="2024-01-01", accn="Q3-24", fy=2024, fp="Q3",
                      form="10-Q", filed="2024-11-05"),  # YTD9, original vintage
            ]}},
            "NetIncomeLoss": {"units": {"USD": [
                _item(100.0, "2024-12-31", start="2024-01-01", accn="K24", filed="2025-02-15"),
                _item(90.0, "2024-09-30", start="2024-01-01", accn="Q3-24", fy=2024, fp="Q3",
                      form="10-Q", filed="2024-11-05"),  # YTD9 → derived Q4 NI = +10
            ]}},
        })
        facts, _ = svc.normalize_companyfacts(1, payload)
        by = _by_key(facts)
        assert ("revenue", date(2024, 12, 31), "Q4") not in by  # −140, rejected
        assert ("net_income", date(2024, 12, 31), "Q4") in by  # +10, kept
        # No net_margin Q4 built on the rejected revenue.
        assert ("net_margin", date(2024, 12, 31), "Q4") not in by

    def test_q4_eps_derived_end_to_end_from_payload(self):
        def year(tag_items):
            return {"units": tag_items}

        usd = lambda *items: {"USD": list(items)}  # noqa: E731
        payload = _payload({
            REV_TAG: year(usd(
                _item(4000.0, "2024-12-31", start="2024-01-01", accn="K24", filed="2025-02-15"),
                _item(1000.0, "2024-03-31", start="2024-01-01", accn="Q1", fp="Q1", form="10-Q", filed="2024-05-05"),
                _item(1000.0, "2024-06-30", start="2024-04-01", accn="Q2", fp="Q2", form="10-Q", filed="2024-08-05"),
                _item(1000.0, "2024-09-30", start="2024-07-01", accn="Q3", fp="Q3", form="10-Q", filed="2024-11-05"),
            )),
            "NetIncomeLoss": year(usd(
                _item(400.0, "2024-12-31", start="2024-01-01", accn="K24", filed="2025-02-15"),
                _item(100.0, "2024-03-31", start="2024-01-01", accn="Q1", fp="Q1", form="10-Q", filed="2024-05-05"),
                _item(100.0, "2024-06-30", start="2024-04-01", accn="Q2", fp="Q2", form="10-Q", filed="2024-08-05"),
                _item(100.0, "2024-09-30", start="2024-07-01", accn="Q3", fp="Q3", form="10-Q", filed="2024-11-05"),
            )),
            "EarningsPerShareDiluted": year({"USD/shares": [
                _item(4.0, "2024-12-31", start="2024-01-01", accn="K24", filed="2025-02-15"),
                _item(1.0, "2024-03-31", start="2024-01-01", accn="Q1", fp="Q1", form="10-Q", filed="2024-05-05"),
                _item(1.0, "2024-06-30", start="2024-04-01", accn="Q2", fp="Q2", form="10-Q", filed="2024-08-05"),
                _item(1.0, "2024-09-30", start="2024-07-01", accn="Q3", fp="Q3", form="10-Q", filed="2024-11-05"),
            ]}),
            "WeightedAverageNumberOfDilutedSharesOutstanding": year({"shares": [
                _item(100.0, "2024-12-31", start="2024-01-01", accn="K24", filed="2025-02-15"),
                _item(100.0, "2024-03-31", start="2024-01-01", accn="Q1", fp="Q1", form="10-Q", filed="2024-05-05"),
                _item(100.0, "2024-06-30", start="2024-04-01", accn="Q2", fp="Q2", form="10-Q", filed="2024-08-05"),
                _item(100.0, "2024-09-30", start="2024-07-01", accn="Q3", fp="Q3", form="10-Q", filed="2024-11-05"),
            ]}),
        })
        facts, _ = svc.normalize_companyfacts(1, payload)
        by = _by_key(facts)
        q4_eps = by[("eps_diluted", date(2024, 12, 31), "Q4")]
        # Q4 NI = 400 − 300 = 100 (derived); Q4 shares = 4×100 − 300 = 100 → EPS 1.00.
        assert q4_eps["value"] == pytest.approx(1.0)
        assert q4_eps["source"] == "derived"
        assert q4_eps["reconciled"] is False
        assert q4_eps["unit"] == "USD/shares"

    def test_ifrs_only_payload_reports_unsupported(self):
        payload = {"facts": {"ifrs-full": {"Revenue": {"units": {"EUR": []}}}}}
        facts, meta = svc.normalize_companyfacts(1, payload)
        assert facts == []
        assert meta["unsupported_ifrs"] is True

    def test_malformed_payload_yields_nothing(self):
        for bad in (None, {}, {"facts": None}, {"facts": {"us-gaap": None}}, "nope"):
            facts, meta = svc.normalize_companyfacts(1, bad)
            assert facts == []
            assert meta["unsupported_ifrs"] is False

    def test_negative_revenue_hard_rejected(self):
        payload = _payload({REV_TAG: {"units": {"USD": [
            _item(-5.0, "2023-12-31", start="2023-01-01", accn="K23", fy=2023, filed="2024-02-15"),
        ]}}})
        facts, _ = svc.normalize_companyfacts(1, payload)
        assert [f for f in facts if f["concept"] == "revenue"] == []

    def test_financial_sic_skips_generic_revenue_keeps_fi_components(self):
        payload = _payload({
            REV_TAG: {"units": {"USD": [  # a bank's ASC-606 fee subset — must NOT ingest
                _item(50.0, "2023-12-31", start="2023-01-01", accn="K23", fy=2023, filed="2024-02-15"),
            ]}},
            "InterestIncomeExpenseNet": {"units": {"USD": [
                _item(400.0, "2023-12-31", start="2023-01-01", accn="K23", fy=2023, filed="2024-02-15"),
            ]}},
        })
        facts, _ = svc.normalize_companyfacts(1, payload, financial_sic=True)
        concepts = {f["concept"] for f in facts}
        assert "revenue" not in concepts
        assert "net_interest_income" in concepts


class TestDeriveQ4:
    def _flow(self, fp, value, *, start, end, fy=2024, source="companyfacts", reconciled=True):
        return {
            "company_id": 1, "filing_id": None, "concept": "revenue", "raw_tag": "t",
            "unit": "USD", "period_start": date.fromisoformat(start),
            "period_end": date.fromisoformat(end), "fiscal_year": fy, "fiscal_period": fp,
            "value": value, "form": "10-K", "accession": "K24", "source": source,
            "reconciled": reconciled,
        }

    def _full_year(self):
        return [
            self._flow("FY", 1200.0, start="2024-01-01", end="2024-12-31"),
            self._flow("Q1", 280.0, start="2024-01-01", end="2024-03-31"),
            self._flow("Q2", 300.0, start="2024-04-01", end="2024-06-30"),
            self._flow("Q3", 310.0, start="2024-07-01", end="2024-09-30"),
        ]

    def test_q4_derived_from_fy_minus_quarters(self):
        derived = svc.derive_q4_facts(self._full_year())
        assert len(derived) == 1
        q4 = derived[0]
        assert q4["fiscal_period"] == "Q4"
        assert q4["value"] == pytest.approx(310.0)  # 1200 - 890
        assert q4["period_start"] == date(2024, 10, 1)  # Q3 end + 1 day
        assert q4["period_end"] == date(2024, 12, 31)
        assert q4["accession"] == "K24"  # the FY row's accession
        assert q4["source"] == "derived"
        assert q4["reconciled"] is False

    def test_missing_quarter_blocks_derivation(self):
        facts = [f for f in self._full_year() if f["fiscal_period"] != "Q2"]
        assert svc.derive_q4_facts(facts) == []

    def test_existing_discrete_q4_blocks_derivation(self):
        facts = self._full_year() + [
            self._flow("Q4", 311.0, start="2024-10-01", end="2024-12-31")
        ]
        assert svc.derive_q4_facts(facts) == []

    def test_eps_and_ratios_never_derived(self):
        # Plain subtraction is wrong for a per-share/ratio unit — EPS gets its own shares-based
        # derivation (derive_q4_eps_facts), never this one.
        facts = self._full_year()
        for f in facts:
            f["concept"] = "earnings_per_share"
            f["unit"] = "USD/shares"
        assert svc.derive_q4_facts(facts) == []

    def test_instants_never_derived(self):
        facts = self._full_year()
        for f in facts:
            f["period_start"] = None
        assert svc.derive_q4_facts(facts) == []

    def _ytd9_values(self, value=890.0, *, start="2024-01-01", end="2024-09-30"):
        """duration_values shape: concept -> {(period_end, klass): record}."""
        return {
            "revenue": {
                (date.fromisoformat(end), "YTD9"): {
                    "value": value,
                    "period_start": date.fromisoformat(start),
                    "period_end": date.fromisoformat(end),
                    "accession": "Q3-24",
                    "form": "10-Q",
                    "filed": "2024-11-05",
                    "raw_tag": "t",
                }
            }
        }

    def test_q4_prefers_ytd9_over_quarter_sum(self):
        # YTD9 = 895 vs ΣQ1–3 = 890: the YTD9 slice (two vintages, one filer) wins.
        derived = svc.derive_q4_facts(self._full_year(), self._ytd9_values(895.0))
        assert len(derived) == 1
        q4 = derived[0]
        assert q4["value"] == pytest.approx(305.0)  # 1200 − 895, NOT 1200 − 890
        assert q4["period_start"] == date(2024, 10, 1)  # YTD9 end + 1 day
        assert q4["source"] == "derived"
        assert q4["reconciled"] is False

    def test_ytd9_derivation_survives_missing_quarters(self):
        # The headline YTD9 win: an FY + YTD9 pair derives Q4 even when Q1/Q2 10-Qs are missing
        # (edge of companyfacts history, IPO year) — the ΣQ path would give up.
        facts = [f for f in self._full_year() if f["fiscal_period"] in ("FY", "Q3")]
        derived = svc.derive_q4_facts(facts, self._ytd9_values(890.0))
        assert len(derived) == 1
        assert derived[0]["value"] == pytest.approx(310.0)

    def test_ytd9_from_wrong_window_is_ignored(self):
        # A YTD9 slice that doesn't start with the fiscal year (here: starts mid-year) must not
        # be subtracted — the residual wouldn't be a discrete Q4. Falls back to ΣQ1–3.
        wrong = self._ytd9_values(600.0, start="2024-03-01", end="2024-11-30")
        derived = svc.derive_q4_facts(self._full_year(), wrong)
        assert len(derived) == 1
        assert derived[0]["value"] == pytest.approx(310.0)  # ΣQ fallback: 1200 − 890

    def test_ytd9_from_a_different_tag_is_ignored(self):
        # Tags within one concept can carry different accounting scopes (total vs continuing-
        # operations cash flow) — FY − YTD9 must never subtract across scopes. ΣQ fallback.
        ytd9 = self._ytd9_values(700.0)
        next(iter(ytd9["revenue"].values()))["raw_tag"] = "other-scope-tag"
        derived = svc.derive_q4_facts(self._full_year(), ytd9)
        assert len(derived) == 1
        assert derived[0]["value"] == pytest.approx(310.0)  # ΣQ fallback, not 1200 − 700


class TestDeriveQ4Eps:
    """Shares-based Q4 EPS derivation (Q4 NI ÷ [4×FY − ΣQ1–3] weighted shares)."""

    def _fact(self, concept, fp, value, *, unit="USD", fy=2024, source="companyfacts",
              reconciled=True):
        starts = {"FY": "2024-01-01", "Q1": "2024-01-01", "Q2": "2024-04-01",
                  "Q3": "2024-07-01", "Q4": "2024-10-01"}
        ends = {"FY": "2024-12-31", "Q1": "2024-03-31", "Q2": "2024-06-30",
                "Q3": "2024-09-30", "Q4": "2024-12-31"}
        return {
            "company_id": 1, "filing_id": None, "concept": concept, "raw_tag": "t", "unit": unit,
            "period_start": date.fromisoformat(starts[fp]),
            "period_end": date.fromisoformat(ends[fp]), "fiscal_year": fy, "fiscal_period": fp,
            "value": value, "form": "10-K", "accession": "K24", "source": source,
            "reconciled": reconciled,
        }

    def _consistent_year(self):
        """NI 1000/quarter (4000 FY), 1000 shares all periods, EPS exactly NI ÷ shares."""
        facts = [
            self._fact("net_income", "FY", 4000.0),
            self._fact("net_income", "Q1", 1000.0),
            self._fact("net_income", "Q2", 1000.0),
            self._fact("net_income", "Q3", 1000.0),
            self._fact("net_income", "Q4", 1000.0, source="derived", reconciled=False),
            self._fact("eps_diluted", "FY", 4.0, unit="USD/shares"),
            self._fact("eps_diluted", "Q1", 1.0, unit="USD/shares"),
            self._fact("eps_diluted", "Q2", 1.0, unit="USD/shares"),
            self._fact("eps_diluted", "Q3", 1.0, unit="USD/shares"),
        ]
        shares = {"eps_diluted": {
            (2024, "FY"): 1000.0, (2024, "Q1"): 1000.0, (2024, "Q2"): 1000.0, (2024, "Q3"): 1000.0,
        }}
        return facts, shares

    def test_q4_eps_derived_from_ni_and_shares(self):
        facts, shares = self._consistent_year()
        derived = svc.derive_q4_eps_facts(facts, shares)
        assert len(derived) == 1
        q4 = derived[0]
        assert q4["concept"] == "eps_diluted"
        assert q4["fiscal_period"] == "Q4"
        # Q4 shares = 4×1000 − 3000 = 1000; Q4 EPS = 1000 ÷ 1000.
        assert q4["value"] == pytest.approx(1.0)
        assert q4["unit"] == "USD/shares"
        assert q4["period_start"] == date(2024, 10, 1)
        assert q4["period_end"] == date(2024, 12, 31)
        assert q4["source"] == "derived"
        assert q4["reconciled"] is False

    def test_buyback_year_uses_shifting_share_counts(self):
        # Shares shrink through the year (buybacks): Q4 shares = 4×925 − (1000+950+900) = 850.
        facts = [
            self._fact("net_income", "FY", 4000.0),
            self._fact("net_income", "Q1", 1000.0),
            self._fact("net_income", "Q2", 950.0),
            self._fact("net_income", "Q3", 900.0),
            self._fact("net_income", "Q4", 1150.0, source="derived", reconciled=False),
            self._fact("eps_diluted", "FY", 4000.0 / 925.0, unit="USD/shares"),
            self._fact("eps_diluted", "Q1", 1.0, unit="USD/shares"),
            self._fact("eps_diluted", "Q2", 1.0, unit="USD/shares"),
            self._fact("eps_diluted", "Q3", 1.0, unit="USD/shares"),
        ]
        shares = {"eps_diluted": {
            (2024, "FY"): 925.0, (2024, "Q1"): 1000.0, (2024, "Q2"): 950.0, (2024, "Q3"): 900.0,
        }}
        derived = svc.derive_q4_eps_facts(facts, shares)
        assert len(derived) == 1
        assert derived[0]["value"] == pytest.approx(1150.0 / 850.0)

    def test_inconsistent_eps_ni_shares_skips_year(self):
        # A mid-year split: EPS history restated but share counts pre-split — EPS ≠ NI ÷ shares,
        # so deriving would be garbage. The consistency gate must skip the whole year.
        facts, shares = self._consistent_year()
        shares["eps_diluted"][(2024, "Q1")] = 500.0  # pre-split count: NI/shares = 2.0 ≠ EPS 1.0
        assert svc.derive_q4_eps_facts(facts, shares) == []

    def test_missing_share_count_skips_year(self):
        facts, shares = self._consistent_year()
        del shares["eps_diluted"][(2024, "Q2")]
        assert svc.derive_q4_eps_facts(facts, shares) == []

    def test_missing_q4_net_income_skips_year(self):
        facts, shares = self._consistent_year()
        facts = [f for f in facts if not (f["concept"] == "net_income" and f["fiscal_period"] == "Q4")]
        assert svc.derive_q4_eps_facts(facts, shares) == []

    def test_discrete_q4_eps_never_overwritten(self):
        facts, shares = self._consistent_year()
        facts.append(self._fact("eps_diluted", "Q4", 1.02, unit="USD/shares"))
        assert svc.derive_q4_eps_facts(facts, shares) == []

    def test_mixed_split_bases_skip_the_year(self):
        # Mid-year 10-for-1 split: FY/Q2/Q3 counts post-split, Q1 still on the original
        # pre-split 10-Q. Each period is internally consistent (Q1's EPS is pre-split too),
        # so only the cross-period spread guard can catch it.
        facts = [
            self._fact("net_income", "FY", 4000.0),
            self._fact("net_income", "Q1", 1000.0),
            self._fact("net_income", "Q2", 1000.0),
            self._fact("net_income", "Q3", 1000.0),
            self._fact("net_income", "Q4", 1000.0, source="derived", reconciled=False),
            self._fact("eps_diluted", "FY", 0.4, unit="USD/shares"),
            self._fact("eps_diluted", "Q1", 1.0, unit="USD/shares"),  # pre-split EPS
            self._fact("eps_diluted", "Q2", 0.1, unit="USD/shares"),
            self._fact("eps_diluted", "Q3", 0.1, unit="USD/shares"),
        ]
        shares = {"eps_diluted": {
            (2024, "FY"): 10_000.0, (2024, "Q1"): 1_000.0,  # pre-split count
            (2024, "Q2"): 10_000.0, (2024, "Q3"): 10_000.0,
        }}
        assert svc.derive_q4_eps_facts(facts, shares) == []

    def test_preferred_dividend_wedge_skips_the_year(self):
        # FY EPS × FY shares ≠ FY NI (preferred dividends): the whole annual wedge would land
        # on the derived Q4 numerator, so the year is skipped even though every per-period
        # check passes.
        facts = [
            self._fact("net_income", "FY", 1000.0),
            self._fact("net_income", "Q1", 320.0),
            self._fact("net_income", "Q2", 320.0),
            self._fact("net_income", "Q3", 320.0),
            self._fact("net_income", "Q4", 40.0, source="derived", reconciled=False),
            # EPS = (NI − 45 preferred) / 239 shares — each reported period within the 5% gate.
            self._fact("eps_diluted", "FY", 4.0, unit="USD/shares"),
            self._fact("eps_diluted", "Q1", 1.29, unit="USD/shares"),
            self._fact("eps_diluted", "Q2", 1.29, unit="USD/shares"),
            self._fact("eps_diluted", "Q3", 1.29, unit="USD/shares"),
        ]
        shares = {"eps_diluted": {
            (2024, "FY"): 239.0, (2024, "Q1"): 239.0, (2024, "Q2"): 239.0, (2024, "Q3"): 239.0,
        }}
        assert svc.derive_q4_eps_facts(facts, shares) == []

    def test_rounded_small_eps_tolerated_absolutely(self):
        # Filed EPS is rounded to 2 decimals: 0.05 vs an exact 0.045 is >5% relative but within
        # the one-cent absolute tolerance — must not be treated as an inconsistency.
        facts = [
            self._fact("net_income", "FY", 180.0),
            self._fact("net_income", "Q1", 45.0),
            self._fact("net_income", "Q2", 45.0),
            self._fact("net_income", "Q3", 45.0),
            self._fact("net_income", "Q4", 45.0, source="derived", reconciled=False),
            self._fact("eps_diluted", "FY", 0.18, unit="USD/shares"),
            self._fact("eps_diluted", "Q1", 0.05, unit="USD/shares"),
            self._fact("eps_diluted", "Q2", 0.05, unit="USD/shares"),
            self._fact("eps_diluted", "Q3", 0.05, unit="USD/shares"),
        ]
        shares = {"eps_diluted": {
            (2024, "FY"): 1000.0, (2024, "Q1"): 1000.0, (2024, "Q2"): 1000.0, (2024, "Q3"): 1000.0,
        }}
        derived = svc.derive_q4_eps_facts(facts, shares)
        assert len(derived) == 1
        assert derived[0]["value"] == pytest.approx(0.045)


class TestDeriveSamePeriodMetrics:
    def _fact(self, concept, value, *, fp="FY", fy=2024, end="2024-12-31", start="2024-01-01",
              unit="USD", reconciled=True, source="companyfacts"):
        return {
            "company_id": 1, "filing_id": None, "concept": concept, "raw_tag": "t", "unit": unit,
            "period_start": date.fromisoformat(start) if start else None,
            "period_end": date.fromisoformat(end), "fiscal_year": fy, "fiscal_period": fp,
            "value": value, "form": "10-K", "accession": "K24", "source": source,
            "reconciled": reconciled,
        }

    def test_margins_fcf_and_liquidity(self):
        facts = [
            self._fact("revenue", 1000.0),
            self._fact("net_income", 200.0),
            self._fact("gross_profit", 400.0),
            self._fact("operating_income", 300.0),
            self._fact("operating_cash_flow", 250.0),
            self._fact("capital_expenditures", 50.0),
            self._fact("current_assets", 600.0, start=None),
            self._fact("current_liabilities", 300.0, start=None),
        ]
        derived = {f["concept"]: f for f in svc.derive_same_period_metrics(facts)}
        assert derived["net_margin"]["value"] == pytest.approx(20.0)
        assert derived["gross_margin"]["value"] == pytest.approx(40.0)
        assert derived["operating_margin"]["value"] == pytest.approx(30.0)
        assert derived["net_margin"]["unit"] == "pure"
        assert derived["free_cash_flow"]["value"] == pytest.approx(200.0)
        assert derived["working_capital"]["value"] == pytest.approx(300.0)
        assert derived["current_ratio"]["value"] == pytest.approx(2.0)
        assert all(f["source"] == "derived" for f in derived.values())
        assert all(f["reconciled"] for f in derived.values())

    def test_derived_q4_inputs_propagate_unreconciled(self):
        facts = [
            self._fact("revenue", 310.0, fp="Q4", start="2024-10-01", reconciled=False,
                       source="derived"),
            self._fact("net_income", 62.0, fp="Q4", start="2024-10-01", reconciled=False,
                       source="derived"),
        ]
        derived = {f["concept"]: f for f in svc.derive_same_period_metrics(facts)}
        assert derived["net_margin"]["reconciled"] is False

    def test_zero_revenue_and_zero_liabilities_guarded(self):
        facts = [
            self._fact("revenue", 0.0),
            self._fact("net_income", 5.0),
            self._fact("current_assets", 10.0, start=None),
            self._fact("current_liabilities", 0.0, start=None),
        ]
        derived = {f["concept"]: f for f in svc.derive_same_period_metrics(facts)}
        assert "net_margin" not in derived
        assert "current_ratio" not in derived
        assert derived["working_capital"]["value"] == pytest.approx(10.0)


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _new_company(db, **overrides):
    from app.models import Company

    suffix = uuid.uuid4().hex[:8]
    company = Company(
        cik=suffix, ticker=("T" + suffix[:4]).upper(), name=f"Co {suffix}", **overrides
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _fact_dict(cid, concept="revenue", *, fp="FY", end=date(2023, 12, 31), unit="USD",
               accession="K23", value=100.0, source="companyfacts", reconciled=True):
    return {
        "company_id": cid, "filing_id": None, "concept": concept, "raw_tag": "t", "unit": unit,
        "period_start": None, "period_end": end, "fiscal_year": end.year, "fiscal_period": fp,
        "value": value, "form": "10-K", "accession": accession, "source": source,
        "reconciled": reconciled,
    }


@pytest.mark.requires_db
class TestUpsertFactsBulk:
    def test_insert_idempotent_and_demote(self):
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        cid = _new_company(db).id
        first = [_fact_dict(cid), _fact_dict(cid, concept="net_income", value=20.0)]
        assert svc.upsert_facts_bulk(db, first) == {"inserted": 2, "skipped": 0, "demoted": 0}
        assert svc.upsert_facts_bulk(db, first) == {"inserted": 0, "skipped": 2, "demoted": 0}

        # Restatement: same period under a new accession demotes the old row.
        restated = [_fact_dict(cid, accession="K23A", value=110.0)]
        assert svc.upsert_facts_bulk(db, restated) == {"inserted": 1, "skipped": 0, "demoted": 1}
        rows = {r.accession: r for r in db.query(FinancialFact).filter_by(
            company_id=cid, concept="revenue").all()}
        assert rows["K23"].is_latest is False
        assert rows["K23A"].is_latest is True
        db.close()

    def test_labelled_quarter_demotes_null_fiscal_period_twin(self):
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        cid = _new_company(db).id
        # Legacy 10-Q row: fiscal_period NULL (written by the per-filing path).
        legacy = _fact_dict(cid, fp=None, end=date(2024, 6, 30), accession="LEGACY-Q",
                            source="edgar_xbrl")
        svc.upsert_facts_bulk(db, [legacy])
        labelled = _fact_dict(cid, fp="Q2", end=date(2024, 6, 30), accession="Q2-24")
        result = svc.upsert_facts_bulk(db, [labelled])
        assert result["inserted"] == 1
        assert result["demoted"] == 1  # the NULL twin

        rows = {r.accession: r for r in db.query(FinancialFact).filter_by(
            company_id=cid, concept="revenue").all()}
        assert rows["LEGACY-Q"].is_latest is False
        assert rows["Q2-24"].is_latest is True
        assert rows["Q2-24"].fiscal_period == "Q2"
        db.close()


def _calendar_fetcher(calls=None):
    payload = _calendar_payload()

    async def fetch(cik):
        if calls is not None:
            calls.append(cik)
        return payload

    return fetch


@pytest.mark.requires_db
class TestIngestCompanyfacts:
    @pytest.mark.asyncio
    async def test_first_sync_inserts_and_stamps(self):
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        result = await svc.ingest_companyfacts(db, company, fetcher=_calendar_fetcher())
        assert result["synced"] is True
        assert result["refreshed"] is True
        assert result["inserted"] > 0
        assert company.facts_synced_at is not None
        assert db.query(FinancialFact).filter_by(company_id=company.id).count() == result["inserted"]
        db.close()

    @pytest.mark.asyncio
    async def test_fresh_stamp_skips_fetch(self):
        from app.database import SessionLocal

        db = SessionLocal()
        company = _new_company(db)
        calls = []
        await svc.ingest_companyfacts(db, company, fetcher=_calendar_fetcher(calls))
        result = await svc.ingest_companyfacts(db, company, fetcher=_calendar_fetcher(calls))
        assert result["refreshed"] is False
        assert len(calls) == 1
        db.close()

    @pytest.mark.asyncio
    async def test_force_refetches(self):
        from app.database import SessionLocal

        db = SessionLocal()
        company = _new_company(db)
        calls = []
        await svc.ingest_companyfacts(db, company, fetcher=_calendar_fetcher(calls))
        result = await svc.ingest_companyfacts(db, company, force=True,
                                               fetcher=_calendar_fetcher(calls))
        assert result["refreshed"] is True
        assert len(calls) == 2
        db.close()

    @pytest.mark.asyncio
    async def test_newer_filing_overrides_ttl(self):
        from app.database import SessionLocal
        from app.models import Filing

        db = SessionLocal()
        company = _new_company(db)
        calls = []
        await svc.ingest_companyfacts(db, company, fetcher=_calendar_fetcher(calls))
        db.add(Filing(
            company_id=company.id, accession_number=f"F-{uuid.uuid4().hex[:10]}",
            filing_type="10-K", filing_date=datetime.now(timezone.utc) + timedelta(minutes=1),
            document_url="https://example.com/d", sec_url="https://example.com/s",
        ))
        db.commit()
        result = await svc.ingest_companyfacts(db, company, fetcher=_calendar_fetcher(calls))
        assert result["refreshed"] is True
        assert len(calls) == 2
        db.close()

    @pytest.mark.asyncio
    async def test_fetch_failure_does_not_stamp(self):
        from app.database import SessionLocal

        db = SessionLocal()
        company = _new_company(db)

        async def failing(cik):
            return None

        result = await svc.ingest_companyfacts(db, company, fetcher=failing)
        assert result["synced"] is False
        assert company.facts_synced_at is None
        db.close()

    @pytest.mark.asyncio
    async def test_ifrs_only_stamps_and_reports_unsupported(self):
        from app.database import SessionLocal

        db = SessionLocal()
        company = _new_company(db)

        async def ifrs(cik):
            return {"facts": {"ifrs-full": {"Revenue": {"units": {"EUR": []}}}}}

        result = await svc.ingest_companyfacts(db, company, fetcher=ifrs)
        assert result["synced"] is True
        assert result["unsupported_ifrs"] is True
        assert company.facts_synced_at is not None  # don't refetch unsupported filers hourly
        db.close()

    @pytest.mark.asyncio
    async def test_financial_sic_company_skips_generic_revenue(self):
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db, sic="6022")  # a bank

        async def bank(cik):
            return _payload({
                REV_TAG: {"units": {"USD": [
                    _item(50.0, "2023-12-31", start="2023-01-01", accn="K23", fy=2023,
                          filed="2024-02-15"),
                ]}},
                "InterestIncomeExpenseNet": {"units": {"USD": [
                    _item(400.0, "2023-12-31", start="2023-01-01", accn="K23", fy=2023,
                          filed="2024-02-15"),
                ]}},
            })

        await svc.ingest_companyfacts(db, company, fetcher=bank)
        concepts = {r.concept for r in db.query(FinancialFact).filter_by(company_id=company.id)}
        assert "revenue" not in concepts
        assert "net_interest_income" in concepts
        db.close()

    @pytest.mark.asyncio
    async def test_concurrent_syncs_collapse_to_one_fetch(self):
        import asyncio

        from app.database import SessionLocal
        from app.models import Company

        db = SessionLocal()
        company = _new_company(db)
        calls = []
        gate = asyncio.Event()
        payload = _calendar_payload()

        async def slow(cik):
            calls.append(cik)
            await gate.wait()
            return payload

        db2 = SessionLocal()
        company2 = db2.get(Company, company.id)

        leader_task = asyncio.create_task(svc.ingest_companyfacts(db, company, fetcher=slow))
        await asyncio.sleep(0.05)  # leader claims the in-flight slot, blocks inside the fetch
        follower_task = asyncio.create_task(svc.ingest_companyfacts(db2, company2, fetcher=slow))
        await asyncio.sleep(0.05)  # follower parks on the leader's event
        gate.set()

        leader_result = await leader_task
        follower_result = await follower_task
        assert len(calls) == 1
        assert leader_result["refreshed"] is True
        assert follower_result["waited"] is True
        db.close()
        db2.close()
