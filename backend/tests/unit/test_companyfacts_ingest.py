"""Unit tests for the companyfacts ingestion path (Multi-Period Analysis M1).

Covers the period classifier (duration windows, distance-anchored quarter labels, the fy/fp trap),
Q4 derivation, same-period derived metrics, the bulk writer (identity skip, is_latest demotion,
the D1 NULL-fiscal_period demotion), the TTL/dedup semantics of ``ingest_companyfacts``, and the
reporting-currency pick for a foreign US-GAAP filer (its USD convenience rows demoted, never kept current).

Payloads are built programmatically — companyfacts items are small dicts, and explicit builders
keep each scenario's trap visible in the test itself.
"""

import json
import os
import subprocess
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

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
                if f["concept"] == "revenue"] == [("FY", 2023)]  # issuer's original annual FY

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

    def test_eps_is_reported_only_even_with_complete_shares_and_income(self):
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
        assert ("eps_diluted", date(2024, 12, 31), "Q4") not in by
        # A reported Q4, including one differing from the synthetic estimate, survives.
        payload["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"].append(
            _item(1.02, "2024-12-31", start="2024-10-01", accn="E24", filed="2025-02-15")
        )
        facts, _ = svc.normalize_companyfacts(1, payload)
        q4 = _by_key(facts)[("eps_diluted", date(2024, 12, 31), "Q4")]
        assert q4["value"] == 1.02
        assert q4["provenance"]["method"] == "reported"

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
            "provenance": {"version": 1, "method": "reported", "validation": "passed",
                           "reasons": [], "filed_at": "2025-02-15", "inputs": []},
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
        assert q4["reconciled"] is True

    def test_missing_quarter_blocks_derivation(self):
        facts = [f for f in self._full_year() if f["fiscal_period"] != "Q2"]
        assert svc.derive_q4_facts(facts) == []

    def test_existing_discrete_q4_blocks_derivation(self):
        facts = self._full_year() + [
            self._flow("Q4", 311.0, start="2024-10-01", end="2024-12-31")
        ]
        assert svc.derive_q4_facts(facts) == []

    def test_eps_and_ratios_never_derived(self):
        # Neither per-share amounts nor ratios can be quarterized by subtraction.
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
        assert q4["reconciled"] is True

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


# --- Native reporting currency (P13): a US-GAAP filer that reports in CNY ----------------------
#
# The shape `facts/currency.py::_reporting_currency` documents: every 20-F tags this year and
# its comparatives in the reporting currency, and this year again as a USD convenience translation
# at that year's rate, so companyfacts holds a CNY list and a USD list for the same line. CNY fell
# against the dollar over these years, so the convenience history shrinks while CNY revenue grows.

_CNY_YEARS = (  # fiscal year, start, end, CNY per USD at that year's 20-F
    (2022, "2021-04-01", "2022-03-31", 6.3393),
    (2023, "2022-04-01", "2023-03-31", 6.8676),
    (2024, "2023-04-01", "2024-03-31", 7.2203),
)
_CNY_REVENUE = (800_000e6, 814_400e6, 882_000e6)  # +1.8%, then +8.3%, as reported
_CNY_EPS = (2.82, 3.46, 3.91)


def _cny_units(values, *, instant=False, per_share=False):
    """One tag's CNY list (each 20-F's year plus comparatives) and its USD convenience list."""
    native, convenience = [], []
    for i, (fy, start, end, rate) in enumerate(_CNY_YEARS):
        accn, filed = f"20F-{fy}", f"{fy}-07-2{i}"
        shown = list(zip(_CNY_YEARS, values))[max(0, i - (1 if instant else 2)): i + 1]
        for (_fy, s, e, _rate), value in shown:
            native.append(_item(value, e, start=None if instant else s, accn=accn, fy=fy,
                                form="20-F", filed=filed))
        convenience.append(_item(round(values[i] / rate, 2 if per_share else 0), end,
                                 start=None if instant else start, accn=accn, fy=fy,
                                 form="20-F", filed=filed))
    suffix = "/shares" if per_share else ""
    return {"units": {f"CNY{suffix}": native, f"USD{suffix}": convenience}}


def _cny_payload():
    return _payload({
        REV_TAG: _cny_units(_CNY_REVENUE),
        "NetIncomeLoss": _cny_units((60_000e6, 70_000e6, 80_000e6)),
        "NetCashProvidedByUsedInOperatingActivities": _cny_units((140_000e6, 190_000e6, 180_000e6)),
        "PaymentsToAcquirePropertyPlantAndEquipment": _cny_units((50_000e6, 35_000e6, 32_000e6)),
        "Assets": _cny_units((1_690_000e6, 1_750_000e6, 1_760_000e6), instant=True),
        "EarningsPerShareDiluted": _cny_units(_CNY_EPS, per_share=True),
    })


def _cny_quarterly(fy_value, q1, q2, q3, ytd9=None):
    items = [
        _item(fy_value, "2024-12-31", start="2024-01-01", accn="K24", filed="2025-03-15"),
        _item(q1, "2024-03-31", start="2024-01-01", accn="Q1-24", fp="Q1", form="10-Q",
              filed="2024-05-05"),
        _item(q2, "2024-06-30", start="2024-04-01", accn="Q2-24", fp="Q2", form="10-Q",
              filed="2024-08-05"),
        _item(q3, "2024-09-30", start="2024-07-01", accn="Q3-24", fp="Q3", form="10-Q",
              filed="2024-11-05"),
    ]
    if ytd9 is not None:
        items.append(_item(ytd9, "2024-09-30", start="2024-01-01", accn="Q3-24", fp="Q3",
                           form="10-Q", filed="2024-11-05"))
    usd = [_item(round(fy_value / 7.1), "2024-12-31", start="2024-01-01", accn="K24",
                 filed="2025-03-15")]
    return {"units": {"CNY": items, "USD": usd}}


def _cny_quarterly_payload():
    return _payload({
        REV_TAG: _cny_quarterly(1200.0, 280.0, 300.0, 310.0, ytd9=895.0),
        "NetIncomeLoss": _cny_quarterly(120.0, 28.0, 30.0, 31.0),
    })


_USD_YEAR = (2025, "2024-04-01", "2025-03-31")  # the first fiscal year a switcher reports in USD


def _switched_to_usd_payload(*, switched=True):
    """``_cny_payload`` with FY2021 in 20F-2022 too, so every CNY 20-F presents comparatives. When
    ``switched``, a FY2025 20-F then reports every tag in USD: FY2023-24 restated at 7 CNY a dollar
    and FY2025 5% up (its balance sheet FY2024-25), with no CNY figure."""
    payload = _cny_payload()
    starts = {end: start for _fy, start, end, _rate in _CNY_YEARS} | {_USD_YEAR[2]: _USD_YEAR[1]}
    for node in payload["facts"]["us-gaap"].values():
        (_native_unit, native), (_usd_unit, usd) = node["units"].items()
        instant = "start" not in native[0]
        comparative = {**native[0], "val": native[0]["val"] * 0.9, "end": "2021-03-31"}
        native.append(comparative if instant else {**comparative, "start": "2020-04-01"})
        if switched:
            first = "2024-03-31" if instant else "2023-03-31"
            restated = {item["end"]: item["val"] / 7 for item in native
                        if item["accn"] == "20F-2024" and item["end"] >= first}
            restated[_USD_YEAR[2]] = restated["2024-03-31"] * 1.05
            usd += [_item(value, end, start=None if instant else starts[end], accn="20F-2025", fy=2025,
                          form="20-F", filed="2025-07-23") for end, value in sorted(restated.items())]
    return payload


_QUARTER_WITH_COMPARATIVE = [  # a 6-K for Q1 FY2025 in USD, filed after 20F-2024, with Q1 FY2024
    _item(31.0e9, "2024-06-30", start="2024-04-01", accn="6K-2025Q1", fy=2025, fp="Q1", form="6-K",
          filed="2024-08-20"),
    _item(29.0e9, "2023-06-30", start="2023-04-01", accn="6K-2025Q1", fy=2025, fp="Q1", form="6-K",
          filed="2024-08-20"),
]


class TestNativeReportingCurrency:
    def test_cny_reporter_is_stored_as_reported_not_from_usd_convenience(self):
        facts, meta = svc.normalize_companyfacts(1, _cny_payload())
        by = _by_key(facts)
        revenue = [by[("revenue", date(fy, 3, 31), "FY")] for fy in (2022, 2023, 2024)]
        assert [(f["unit"], f["value"]) for f in revenue] == [("CNY", v) for v in _CNY_REVENUE]
        assert {f["unit"] for f in facts} == {"CNY", "CNY/shares", "pure"}
        assert by[("total_assets", date(2024, 3, 31), "FY")]["value"] == 1_760_000e6
        assert by[("eps_diluted", date(2024, 3, 31), "FY")]["unit"] == "CNY/shares"
        # A derived amount carries its operands' currency, never a USD default.
        fcf = by[("free_cash_flow", date(2024, 3, 31), "FY")]
        assert (fcf["unit"], fcf["value"]) == ("CNY", 148_000e6)
        assert meta["unsupported_ifrs"] is False

    def test_cny_quarters_derive_in_the_series_currency(self):
        # A calendar-year filer whose 10-Qs report in CNY: Q4 = FY − YTD9 (revenue) and
        # FY − ΣQ1–3 (net income, no YTD9) derive exactly as a USD series would.
        facts, _ = svc.normalize_companyfacts(1, _cny_quarterly_payload())
        by = _by_key(facts)
        revenue_q4 = by[("revenue", date(2024, 12, 31), "Q4")]
        assert (revenue_q4["unit"], revenue_q4["value"]) == ("CNY", pytest.approx(305.0))
        assert revenue_q4["provenance"]["formula"] == "FY - YTD9"
        income_q4 = by[("net_income", date(2024, 12, 31), "Q4")]
        assert (income_q4["unit"], income_q4["value"]) == ("CNY", pytest.approx(31.0))
        assert income_q4["provenance"]["formula"] == "FY - (Q1 + Q2 + Q3)"

    def test_an_excluded_quarter_keeps_its_operands_currency(self):
        # An independently restated FY (another accession) cannot pair with the 10-Q's YTD9, so
        # Q4 is excluded; the operands quarterly_fact_repair reads stay in the series currency.
        def ocf(value, end, accn, filed, fp="FY", form="10-K"):
            return _item(value, end, start="2024-01-01", accn=accn, fp=fp, form=form, filed=filed)

        payload = _payload({"NetCashProvidedByUsedInOperatingActivities": {"units": {"CNY": [
            ocf(190.0, "2024-03-31", "Q1-24", "2024-05-05", fp="Q1", form="10-Q"),
            ocf(380.0, "2024-06-30", "Q2-24", "2024-08-05", fp="Q2", form="10-Q"),
            ocf(630.0, "2024-09-30", "Q3-24", "2024-11-05", fp="Q3", form="10-Q"),
            ocf(910.0, "2024-12-31", "K24", "2025-03-15"),
            ocf(1000.0, "2024-12-31", "K24A", "2025-04-01"),
        ]}}})
        facts, meta = svc.normalize_companyfacts(1, payload)
        assert ("operating_cash_flow", date(2024, 12, 31), "Q4") not in _by_key(facts)
        excluded = next(e for e in meta["quarterly_exclusions"] if e["fiscal_period"] == "Q4")
        assert excluded["reason"] == "incompatible_vintages"
        assert {operand["unit"] for operand in excluded["inputs"]} == {"CNY"}

    def test_a_filer_that_switched_to_usd_is_read_from_its_usd_report_only(self):
        # CNY 20-Fs for FY2019-23 (each with two comparatives and a USD convenience year), then a
        # FY2024 20-F that reports in USD with FY2022-23 restated. CNY covers more period-ends, but
        # the latest annual report is USD, so the series is USD. The CNY 20-Fs report in another
        # currency and are never read, so their USD convenience years (FY2019-21) are not stored:
        # the history holds the years the USD report presents, never a translation beside them.
        cny = {year: 500e9 + 50e9 * (year - 2017) for year in range(2017, 2024)}
        cny_items, usd_items = [], []
        for fy in range(2019, 2024):
            accn, filed = f"20F-{fy}", f"{fy + 1}-04-20"
            cny_items += [_item(cny[y], f"{y}-12-31", start=f"{y}-01-01", accn=accn, fy=fy,
                                form="20-F", filed=filed) for y in (fy - 2, fy - 1, fy)]
            usd_items.append(_item(round(cny[fy] / 7), f"{fy}-12-31", start=f"{fy}-01-01",
                                   accn=accn, fy=fy, form="20-F", filed=filed))
        restated = {2022: 105e9, 2023: 110e9, 2024: 118e9}
        usd_items += [_item(value, f"{y}-12-31", start=f"{y}-01-01", accn="20F-2024", fy=2024,
                            form="20-F", filed="2025-04-20") for y, value in restated.items()]
        payload = _payload({REV_TAG: {"units": {"CNY": cny_items, "USD": usd_items}}})
        facts, _ = svc.normalize_companyfacts(1, payload)
        revenue = {f["period_end"].year: (f["unit"], f["value"]) for f in facts
                   if f["concept"] == "revenue" and f["fiscal_period"] == "FY"}
        assert {unit for unit, _value in revenue.values()} == {"USD"}
        assert {year: revenue[year][1] for year in restated} == restated
        assert set(revenue) == set(restated)

    @pytest.mark.parametrize("convenience", [False, True], ids=["no-usd-year", "usd-convenience-year"])
    def test_a_filer_that_switched_from_usd_is_read_in_its_new_currency(self, convenience):
        # 10-Ks for FY2017-22 in USD (each with two comparatives), then FY2023-24 20-Fs in CNY with
        # FY2021-22 restated and, in the second case, each 20-F's own year again in USD at that
        # year's rate. The latest annual report is CNY, so the series is CNY: the 10-Ks report in
        # another currency and are never read, and neither is a 20-F's USD convenience year. The
        # history holds the years the CNY reports present, FY2021-24, not USD years beside them.
        usd = {year: 100e9 + 10e9 * (year - 2015) for year in range(2015, 2023)}
        cny = {2021: 7 * usd[2021], 2022: 7 * usd[2022], 2023: 1_200e9, 2024: 1_300e9}
        usd_items = [_item(usd[y], f"{y}-12-31", start=f"{y}-01-01", accn=f"10K-{fy}", fy=fy,
                           filed=f"{fy + 1}-02-20")
                     for fy in range(2017, 2023) for y in (fy - 2, fy - 1, fy)]
        cny_items = [_item(cny[y], f"{y}-12-31", start=f"{y}-01-01", accn=f"20F-{fy}", fy=fy,
                           form="20-F", filed=f"{fy + 1}-04-20")
                     for fy in (2023, 2024) for y in (fy - 2, fy - 1, fy)]
        if convenience:
            usd_items += [_item(round(cny[fy] / rate), f"{fy}-12-31", start=f"{fy}-01-01", accn=f"20F-{fy}",
                                fy=fy, form="20-F", filed=f"{fy + 1}-04-20")
                          for fy, rate in ((2023, 7.10), (2024, 7.30))]
        payload = _payload({REV_TAG: {"units": {"USD": usd_items, "CNY": cny_items}}})
        facts, _ = svc.normalize_companyfacts(1, payload)
        revenue = {f["period_end"].year: (f["unit"], f["value"]) for f in facts
                   if f["concept"] == "revenue" and f["fiscal_period"] == "FY"}
        assert revenue == {year: ("CNY", value) for year, value in cny.items()}

    @pytest.mark.parametrize("stray", [
        [_item(130.0e9, "2025-03-31", start="2024-04-01", accn="20FA-2025", fy=2025, form="20-F/A",
               filed="2025-08-01")],
        _QUARTER_WITH_COMPARATIVE,
    ], ids=["one-year-annual-amendment", "later-quarterly-report"])
    def test_a_stray_usd_report_does_not_flip_a_native_series(self, stray):
        # USD revenue dated after every CNY period: one year from an amendment, or a later quarterly
        # report with its comparative quarter. The amendment presents no comparatives and the 6-K is
        # no annual report, while the latest 20-F is both, so the series stays CNY, read exactly as
        # without the stray. The 6-K spans two period-ends, so only the annual rank keeps it out.
        payload = _cny_payload()
        payload["facts"]["us-gaap"][REV_TAG]["units"]["USD"].extend(stray)
        assert svc.normalize_companyfacts(1, payload) == svc.normalize_companyfacts(1, _cny_payload())

    def test_an_older_years_amendment_filed_after_the_newer_annual_report_does_not_decide(self):
        # A CNY 20-F/A restating FY2023-24, filed after the USD 20-F for FY2025. It is an annual
        # report presenting comparatives, filed last, but the latest period it reports is FY2024:
        # the USD report, which reports FY2025, still decides, and the amendment is not read.
        payload = _with_older_year_cny_amendment(_switched_to_usd_payload())
        assert svc.normalize_companyfacts(1, payload) == svc.normalize_companyfacts(1, _switched_to_usd_payload())

    @pytest.mark.parametrize("stray", [
        _item(900.0, "2024-12-31", start="2024-01-01", accn="K24", filed="2025-02-15"),
        # Dated after every USD period-end, so it alone reaches the latest one.
        _item(900.0, "2025-09-30", start="2025-07-01", accn="Q3-25", fy=2025, fp="Q3", form="10-Q",
              filed="2025-11-05"),
    ], ids=["inside-the-usd-span", "after-every-usd-period"])
    def test_usd_filer_ignores_a_stray_minority_currency_list(self, stray):
        # One EUR item never takes the series, whatever its date. Inside K24 it loses that filing's
        # vote to K24's two USD items; in a 10-Q of its own, that 10-Q is EUR but no annual report,
        # so the latest 10-K still decides and the 10-Q is not read. The history is read as before.
        payload = _calendar_payload()
        payload["facts"]["us-gaap"][REV_TAG]["units"]["EUR"] = [stray]
        assert svc.normalize_companyfacts(1, payload) == svc.normalize_companyfacts(1, _calendar_payload())

    @pytest.mark.parametrize("unusable", [
        {"val": None}, {"val": float("nan")}, {"val": float("inf")}, {"start": None},
        {"start": "2023-10-01"},  # six months: a cumulative slice ends there, not the fiscal year
        {"start": "2023-12-01"},  # four months: no duration class at all
    ], ids=["no-value", "nan", "infinite", "no-start", "six-month-span", "unclassified-span"])
    def test_a_native_year_the_collector_drops_is_missing_not_read_from_usd(self, unusable):
        # The CNY list's only FY2024 revenue item is one the collector drops, or keys as another
        # span. 20F-2024 still reports in CNY, so the series stays CNY: FY2024 revenue is missing,
        # never filled from that 20-F's USD convenience translation, and no year is read in USD.
        payload = _cny_payload()
        payload["facts"]["us-gaap"][REV_TAG]["units"]["CNY"][-1].update(unusable)  # 20F-2024's own year
        facts, _ = svc.normalize_companyfacts(1, payload)
        revenue = {f["period_end"].year: (f["unit"], f["value"]) for f in facts
                   if f["concept"] == "revenue" and f["fiscal_period"] == "FY"}
        assert revenue == {fy: ("CNY", value) for (fy, *_rest), value in zip(_CNY_YEARS[:2], _CNY_REVENUE[:2])}
        assert {f["unit"] for f in facts} == {"CNY", "CNY/shares", "pure"}

    def test_a_native_list_still_wins_on_the_periods_both_lists_keep(self):
        # Items the collector drops are read for no period: a valueless, later-filed copy of the CNY
        # FY2024 item, and a USD item with no start in a 6-K of its own. The series stays CNY and every
        # native year is read. This passes however the dropped items vote (the 6-K is no annual
        # report); TestFilingCurrencies[nothing-kept] pins that they cast no vote.
        payload = _cny_payload()
        units = payload["facts"]["us-gaap"][REV_TAG]["units"]
        units["CNY"].append({**units["CNY"][-1], "val": None, "filed": "2024-08-01"})
        units["USD"].append(_item(130e9, "2025-03-31", accn="6K-2025", fy=2025, form="6-K", filed="2025-05-20"))
        facts, _ = svc.normalize_companyfacts(1, payload)
        revenue = {f["period_end"].year: (f["unit"], f["value"]) for f in facts
                   if f["concept"] == "revenue" and f["fiscal_period"] == "FY"}
        assert revenue == {fy: ("CNY", value) for (fy, *_rest), value in zip(_CNY_YEARS, _CNY_REVENUE)}

    def test_the_normalizers_read_a_native_filer_without_settings_orm_or_edgar(self, tmp_path):
        # A fresh interpreter with no Settings env (no SECRET_KEY): importing the pure normalizers
        # and reading the annual and quarterly CNY shapes, where filing_currencies picks each filing's
        # currency and the Q4 derivations match intervals, must load none of these, at import time
        # or at call time. Only the interpreter's own PATH, HOME and library path are passed.
        child = (
            "import json, sys\n"
            "from app.services.facts import companyfacts, concepts, currency, quarterly\n"
            "runs = [companyfacts.normalize_companyfacts(1, payload)[0] for payload in json.load(sys.stdin)]\n"
            "heavy = ('app.config', 'app.database', 'app.models', 'app.services.edgar', 'sqlalchemy')\n"
            "print(json.dumps({\n"
            "    'revenue': sorted([f['unit'], f['value']] for f in runs[0] if f['concept'] == 'revenue'),\n"
            "    'q4': sorted([f['concept'], f['unit']] for f in runs[1]\n"
            "                 if f['fiscal_period'] == 'Q4' and f['concept'] in ('revenue', 'net_income')),\n"
            "    'loaded': sorted(m for m in sys.modules for h in heavy if m == h or m.startswith(h + '.')),\n"
            "}))\n"
        )
        env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(tmp_path)}
        if os.environ.get("LD_LIBRARY_PATH"):  # setup-python's shared libpython on CI runners
            env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        probe = subprocess.run(
            [sys.executable, "-c", child], input=json.dumps([_cny_payload(), _cny_quarterly_payload()]),
            capture_output=True, text=True, timeout=60, cwd=Path(__file__).resolve().parents[2], env=env,
        )
        assert probe.returncode == 0, probe.stderr[-1500:]
        result = json.loads(probe.stdout)
        assert result["revenue"] == [["CNY", value] for value in _CNY_REVENUE]
        assert result["q4"] == [["net_income", "CNY"], ["revenue", "CNY"]]
        assert result["loaded"] == []


def _with_stray_usd_amendment(payload):
    """A 20-F/A that tags one later year of revenue in USD and nothing else."""
    payload["facts"]["us-gaap"][REV_TAG]["units"]["USD"].append(_item(
        130.0e9, "2025-03-31", start="2024-04-01", accn="20FA-2025", fy=2025, form="20-F/A", filed="2025-08-01"))
    return payload


def _with_stray_eur_item(payload):
    """One EUR revenue item inside the USD 10-K for FY2024 (the inside-the-usd-span stray)."""
    payload["facts"]["us-gaap"][REV_TAG]["units"]["EUR"] = [
        _item(900.0, "2024-12-31", start="2024-01-01", accn="K24", filed="2025-02-15")]
    return payload


_QUARTER_ACCESSION = {"6-K": "6K-2025Q1", "10-Q": "10Q-2025Q1"}


def _with_later_usd_quarter(payload, form="6-K"):
    """A USD 6-K (or 10-Q) filed after the CNY 20-Fs and before the USD one, its quarter and the
    comparative one (two period-ends): the switch's first report in the new currency."""
    payload["facts"]["us-gaap"][REV_TAG]["units"]["USD"].extend(
        {**item, "form": form, "accn": _QUARTER_ACCESSION[form]} for item in _QUARTER_WITH_COMPARATIVE)
    return payload


def _with_older_year_cny_amendment(payload, filed="2025-09-01"):
    """A CNY 20-F/A restating FY2023-24 revenue, filed after the USD 20-F for FY2025 (or on ``filed``)."""
    payload["facts"]["us-gaap"][REV_TAG]["units"]["CNY"].extend(
        _item(value * 1.01, end, start=start, accn="20FA-2024", fy=2024, form="20-F/A", filed=filed)
        for (_fy, start, end, _rate), value in zip(_CNY_YEARS[1:], _CNY_REVENUE[1:]))
    return payload


def _with_the_first_20f_in_eur(payload):
    """``_switched_to_usd_payload``'s 20F-2022 reporting in EUR: its CNY and CNY/shares items (FY2022 and its
    FY2021 comparative) move to EUR lists, its USD convenience year stays, so its own currency is a third one."""
    for node in payload["facts"]["us-gaap"].values():
        for unit in [unit for unit in node["units"] if unit.startswith("CNY")]:
            first = [item for item in node["units"][unit] if item["accn"] == "20F-2022"]
            node["units"][unit] = [item for item in node["units"][unit] if item["accn"] != "20F-2022"]
            node["units"]["EUR" + unit[3:]] = first
    return payload


_LATE_REPORTS = {  # an old-currency report filed after 20F-2025: its accession, its rows' label, each year's period-end
    "20-F/A": ("20FA-2024", "FY", {2023: date(2023, 3, 31), 2024: date(2024, 3, 31)}),
    "10-Q/A": ("10QA-2025Q2", "Q2", {2023: date(2023, 9, 30), 2024: date(2024, 9, 30)}),
}


def _store_late_cny_report(db, company, tag, form, concepts=("revenue", "net_income"), years=(2023, 2024), *,
                           per_share=False, filed=date(2025, 9, 1)):
    """Store, as the per-filing writer does, an old-currency report of ``_switched_to_usd_payload``'s switcher filed
    on ``filed`` (by default 2025-09-01, after its USD 20-F for FY2025): a CNY 20-F/A restating FY2023-24, or a CNY
    10-Q/A for Q2 and its comparative quarter (Q-labelled, as a domestic filer that switched from CAD to USD files one
    after its first USD 10-K; the vote reads neither the form nor the code). Its ``concepts`` are in CNY and its capex
    in USD, which its per-concept pick read so, at ``years``, and with ``per_share`` its diluted EPS in USD/shares too
    (per-share rows do not vote); its rows are current. With ``filed`` None it has no Filing row and its rows no
    ``filed_at``: undated. Returns its accession, untagged."""
    from app.models import Filing

    accession, period, ends = _LATE_REPORTS[form]
    filing = Filing(company_id=company.id, accession_number=f"{accession}{tag}", filing_type=form,
                    filing_date=datetime(filed.year, filed.month, filed.day, tzinfo=timezone.utc),
                    document_url="https://example.com/d", sec_url="https://example.com/s") if filed else None
    if filing is not None:
        db.add(filing)
        db.commit()
    cny = {"revenue": _CNY_REVENUE[1:], "net_income": (70_000e6, 80_000e6)}
    rows = [(concept, "CNY", year, value * 1.01) for concept in concepts for year, value in zip((2023, 2024), cny[concept])]
    rows += [("capital_expenditures", "USD", year, value) for year, value in ((2023, 4.9e9), (2024, 4.4e9))]
    rows += [("eps_diluted", "USD/shares", year, value) for year, value in ((2023, 0.55), (2024, 0.60)) if per_share]
    svc.upsert_facts_bulk(db, [{**_fact_dict(company.id, concept, fp=period, end=ends[year], unit=unit, value=value,
                                              accession=f"{accession}{tag}", source="edgar_xbrl"),
                                "filing_id": filing.id if filing else None, "form": form}
                               for concept, unit, year, value in rows if year in years])
    return accession


def _with_late_cny_report(payload, form):
    """The payload naming ``_store_late_cny_report``'s report: its CNY revenue items, so it reads that report's own
    currency as CNY."""
    if form == "20-F/A":
        return _with_older_year_cny_amendment(payload)
    accession, period, ends = _LATE_REPORTS[form]
    payload["facts"]["us-gaap"][REV_TAG]["units"]["CNY"].extend(
        _item(value * 1.01, end.isoformat(), start=end.replace(month=7, day=1).isoformat(), accn=accession, fy=2025,
              fp=period, form=form, filed="2025-09-01") for end, value in zip(ends.values(), _CNY_REVENUE[1:]))
    return payload


class TestFilingCurrencies:
    """The per-filing pick on its own: the series currency, and the filings the collector never reads."""

    @pytest.mark.parametrize("build, expected", [
        (_calendar_payload, ("USD", set())),
        # K24 tags two USD items (FY2024 revenue, its year-end assets) and one EUR item: USD. (A tie
        # would leave K24 undetermined with the same result; instant-items-vote pins the count.)
        (lambda: _with_stray_eur_item(_calendar_payload()), ("USD", set())),
        # 20F-2022 tags its one year in CNY and in USD: a tie, so undetermined and not excluded.
        (_cny_payload, ("CNY", set())),
        # A one-year amendment cannot decide: the latest 20-F presenting comparatives does.
        (lambda: _with_stray_usd_amendment(_cny_payload()), ("CNY", {"20FA-2025"})),
        # A two-period USD 6-K filed after the latest 20-F presents comparatives, but is no annual report.
        (lambda: _with_later_usd_quarter(_cny_payload()), ("CNY", {"6K-2025Q1"})),
        (lambda: _switched_to_usd_payload(switched=False), ("CNY", set())),
        (_switched_to_usd_payload, ("USD", {"20F-2022", "20F-2023", "20F-2024"})),
        # A CNY 20-F/A restating FY2023-24, filed last: the report of the latest period still decides.
        (lambda: _with_older_year_cny_amendment(_switched_to_usd_payload()),
         ("USD", {"20F-2022", "20F-2023", "20F-2024", "20FA-2024"})),
        # A 10-K filer that reports in CAD, with no USD list at all.
        (lambda: _payload({REV_TAG: {"units": {"CAD": [
            _item(10.0, "2023-12-31", start="2023-01-01", accn="K24", filed="2025-02-15"),
            _item(12.0, "2024-12-31", start="2024-01-01", accn="K24", filed="2025-02-15"),
        ]}}}), ("CAD", set())),
        # K24 tags its revenue once in CAD and once in USD, a tie that its CAD balance sheet (two
        # year-ends) breaks: instants vote, so K24 is CAD and decides.
        (lambda: _payload({
            REV_TAG: {"units": {"CAD": [_item(12.0, "2024-12-31", start="2024-01-01", accn="K24")],
                                "USD": [_item(9.0, "2024-12-31", start="2024-01-01", accn="K24")]}},
            "Assets": {"units": {"CAD": [_item(50.0, "2023-12-31", accn="K24"),
                                         _item(55.0, "2024-12-31", accn="K24")]}},
        }), ("CAD", set())),
        # One filing that tags its one year in two currencies decides nothing: the domestic default.
        (lambda: _payload({REV_TAG: {"units": {
            "CNY": [_item(7.0, "2024-12-31", start="2024-01-01", accn="K24")],
            "USD": [_item(1.0, "2024-12-31", start="2024-01-01", accn="K24")],
        }}}), ("USD", set())),
        # No kept amount item: per-share lists do not vote, and an unusable item counts for none.
        (lambda: _payload({"EarningsPerShareDiluted": {"units": {"CNY/shares": [
            _item(3.9, "2024-12-31", start="2024-01-01", accn="K24")]}},
            REV_TAG: {"units": {"CNY": [_item(None, "2024-12-31", start="2024-01-01", accn="K24")]}}}),
         ("USD", set())),
    ], ids=["usd-filer", "usd-filer-stray-eur-item", "cny-reporter", "stray-usd-amendment",
            "later-two-period-quarterly-report", "before-a-switch", "switched-to-usd",
            "older-year-amendment-filed-later", "cad-10-k-filer", "instant-items-vote", "one-tied-filing",
            "nothing-kept"])
    def test_the_series_takes_the_latest_annual_reports_currency(self, build, expected):
        from app.services.facts.concepts import COMPANYFACTS_DURATION_TAGS, COMPANYFACTS_INSTANT_TAGS
        from app.services.facts.currency import filing_currencies

        usgaap = build()["facts"]["us-gaap"]
        currency, foreign = filing_currencies(usgaap, COMPANYFACTS_DURATION_TAGS, COMPANYFACTS_INSTANT_TAGS)
        assert (currency, set(foreign)) == expected

    def test_the_payload_view_carries_the_collectors_pick_and_every_filing_it_names(self):
        # The demotion reads the collector's own pick, and every accession the payload names in any
        # taxonomy, tag or unit: a shares item under a tag no concept reads still names its filing.
        from app.services.facts.currency import PayloadView, companyfacts_currencies, payload_view

        payload = _switched_to_usd_payload()
        payload["facts"]["us-gaap"]["SomeShareCount"] = {"units": {"shares": [
            _item(5.0, "2025-06-30", accn="6K-2026Q1", form="6-K", filed="2025-08-30")]}}
        # Another taxonomy names its filings too, and never votes: the pick reads us-gaap alone.
        payload["facts"]["ifrs-full"] = {"Revenue": {"units": {"EUR": [
            _item(9.0e9, "2025-12-31", start="2025-01-01", accn="IFRS-2026", form="20-F", filed="2026-03-01")]}}}
        # It also carries each determined filing's own currency, the deciding filing's rank, and each named
        # filing's own filed date, by which the sync dates a batch row (a calculation too).
        view = payload_view(payload)
        assert view[:2] == companyfacts_currencies(payload["facts"]["us-gaap"])
        filed = {"20F-2022": "2022-07-20", "20F-2023": "2023-07-21", "20F-2024": "2024-07-22", "20F-2025": "2025-07-23",
                 "6K-2026Q1": "2025-08-30", "IFRS-2026": "2026-03-01"}
        assert view == PayloadView("USD", frozenset({"20F-2022", "20F-2023", "20F-2024"}), frozenset(filed), "2026-03-01",
                                   {"20F-2022": "CNY", "20F-2023": "CNY", "20F-2024": "CNY", "20F-2025": "USD"},
                                   (True, True, date(2025, 3, 31), "2025-07-23"), filed)
        assert payload_view({"facts": {}}) == PayloadView("USD", frozenset(), frozenset(), "", {}, None, {})


@pytest.mark.requires_db
class TestNativeReportingCurrencySync:
    def test_sync_supersedes_usd_convenience_rows_and_stays_out_of_usd_peer_ranking(self):
        from app.database import SessionLocal
        from app.models import FinancialFact
        from app.services import trend_analysis_service
        from app.services.peers_service import get_peers

        db = SessionLocal()
        sic = f"SIC{uuid.uuid4().hex[:8]}"
        fpi, usd_peer = _new_company(db, sic=sic), _new_company(db, sic=sic)
        for company in (fpi, usd_peer):  # get_peers resolves a ticker in the worker's shared DB
            company.ticker = f"T{uuid.uuid4().hex.upper()}"
        db.commit()
        # The USD peer shares the FPI's period end, so only the company scope keeps it current.
        svc.upsert_facts_bulk(db, [_fact_dict(usd_peer.id, end=date(2024, 3, 31), value=120_000e6,
                                              accession="US-K24")])
        # What a sync stored before it read the reporting currency: each year's convenience rows.
        legacy = [_fact_dict(fpi.id, concept, unit=unit, end=date(fy, 3, 31),
                             value=round(native / rate, digits), accession=f"20F-{fy}")
                  for concept, unit, values, digits in (("revenue", "USD", _CNY_REVENUE, 0),
                                                        ("eps_diluted", "USD/shares", _CNY_EPS, 2))
                  for (fy, _start, _end, rate), native in zip(_CNY_YEARS, values)]
        # A USD row at another key (a legacy NULL-fiscal_period twin) has no native twin.
        other_key = _fact_dict(fpi.id, fp=None, end=date(2024, 3, 31), value=1.0, accession="Q-2024")
        svc.upsert_facts_bulk(db, [*legacy, other_key])

        result = _checked_sync(db, fpi, _cny_payload())
        dataset = trend_analysis_service.build_dataset(db, fpi, "annual", "FY2022", "FY2024")
        series = next(s for s in dataset["series"] if s["concept"] == "revenue")
        assert series["unit"] == "CNY"
        assert [p["value"] for p in series["points"]] == list(_CNY_REVENUE)
        assert [p.get("yoy") for p in series["points"]] == [
            None,
            pytest.approx(_CNY_REVENUE[1] / _CNY_REVENUE[0] - 1),
            pytest.approx(_CNY_REVENUE[2] / _CNY_REVENUE[1] - 1),
        ]

        usd_panel = get_peers(db, usd_peer.ticker, "revenue")
        assert usd_panel["unit"] == "USD"
        assert fpi.ticker not in [p["ticker"] for p in usd_panel["peers"]]
        assert get_peers(db, fpi.ticker, "revenue")["unit"] == "CNY"

        assert result["demoted"] == len(legacy)
        rows = db.query(FinancialFact).filter(
            FinancialFact.company_id.in_((fpi.id, usd_peer.id))).all()

        def states(concept, fp="FY", company_id=fpi.id):
            return {(r.unit, r.is_latest) for r in rows
                    if (r.company_id, r.concept, r.fiscal_period) == (company_id, concept, fp)}

        assert states("revenue") == {("USD", False), ("CNY", True)}
        assert states("eps_diluted") == {("USD/shares", False), ("CNY/shares", True)}
        assert states("revenue", fp=None) == {("USD", True)}  # another key: left alone
        assert states("revenue", company_id=usd_peer.id) == {("USD", True)}  # another company
        usd_rows = [r for r in rows if r.company_id == fpi.id and r.unit.startswith("USD")]
        assert len(usd_rows) == len(legacy) + 1  # demoted, never deleted

        # A re-sync of the same payload is a no-op.
        before = sorted((r.id, r.unit, r.value, r.is_latest)
                        for r in db.query(FinancialFact).filter_by(company_id=fpi.id))
        again = _checked_sync(db, fpi, _cny_payload())
        assert (again["inserted"], again["demoted"]) == (0, 0)
        assert again["skipped"] == result["inserted"]
        after = sorted((r.id, r.unit, r.value, r.is_latest)
                       for r in db.query(FinancialFact).filter_by(company_id=fpi.id))
        assert after == before
        db.close()

    @pytest.mark.parametrize("recorded", [True, False], ids=["recorded-operands", "before-provenance"])
    def test_sync_promotes_native_ratios_over_usd_ones_a_known_older_filing_kept_current(self, recorded):
        # A pre-fix sync read only the USD lists, so it stored each year's net margin from that
        # year's USD operands, under that year's 20-F. With 20F-2022 stored locally and 20F-2024
        # not, the upsert keeps the FY2022 margin current (a known filing date outranks an unknown
        # one) and stores the native one, from 20F-2024, behind it. A newer native calculation
        # stored locally (20F-2025) is not USD-derived, so it stays the FY2023 margin. FY2024's
        # native margin has the stored row's own identity, so the upsert skips it; ingestion never
        # rewrites an identity, and the journaled repair recomputes that row. A sync before
        # 2026-10-10 recorded no operands, and its derived ratios with no filing owner read USD lists.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact
        from app.services import trend_analysis_service
        from app.services.quarterly_fact_repair import repair_company

        db = SessionLocal()
        fpi, other = _new_company(db), _new_company(db)
        fpi.cik = str(uuid.uuid4().int % 10**10)  # the repair matches the payload's CIK
        tag = f"-{uuid.uuid4().hex[:8]}"  # accession numbers are unique across companies

        def payload(units=("CNY", "CNY/shares", "USD", "USD/shares")):
            data = {**_cny_payload(), "cik": int(fpi.cik)}
            for node in data["facts"]["us-gaap"].values():
                node["units"] = {unit: items for unit, items in node["units"].items() if unit in units}
                for item in (item for items in node["units"].values() for item in items):
                    item["accn"] += tag
            return data

        filings = {fy: Filing(company_id=fpi.id, accession_number=f"20F-{fy}{tag}", filing_type="20-F",
                              filing_date=datetime(fy, 7, 20, tzinfo=timezone.utc),
                              document_url="https://example.com/d", sec_url="https://example.com/s")
                   for fy in (2022, 2023, 2025)}
        db.add_all(filings.values())
        db.commit()
        usd_only = svc.normalize_companyfacts(fpi.id, payload(("USD", "USD/shares")))[0]
        svc.upsert_facts_bulk(db, [f if recorded else {**f, "provenance": None} for f in usd_only])
        native = {f["fiscal_year"]: f for f in svc.normalize_companyfacts(fpi.id, payload())[0]
                  if f["concept"] == "net_margin"}
        newer = {**native[2023], "accession": f"20F-2025{tag}", "value": 8.6}
        if not recorded:  # then only the per-filing path stored one, in the filing's own currency
            newer.update(source="edgar_xbrl", filing_id=filings[2025].id, provenance=None)
        # An earlier native calculation from a filing not stored locally: behind the legacy row,
        # and not this batch's own.
        svc.upsert_facts_bulk(db, [newer, {**native[2022], "accession": f"20F-2023A{tag}", "value": 7.4}])
        # Another company's rows that the session has not committed yet are not this sync's.
        usd_margin = next(f for f in usd_only if (f["concept"], f["fiscal_year"]) == ("net_margin", 2022))
        svc.upsert_facts_bulk(db, [{**usd_margin, "company_id": other.id}], commit=False)

        _checked_sync(db, fpi, payload())
        dataset = trend_analysis_service.build_dataset(db, fpi, "annual", "FY2022", "FY2024")
        margin = next(s for s in dataset["series"] if s["concept"] == "net_margin")
        points = [(p["value"], {i["unit"] for i in p["provenance"]["inputs"]}) for p in margin["points"][:2]]
        assert points == [(7.5, {"CNY"}), (8.6, {"CNY"} if recorded else set())]  # USD-derived: 7.4999999997
        rows = db.query(FinancialFact).filter_by(company_id=fpi.id, concept="net_margin").all()
        assert sorted((r.period_end.year, r.accession.removesuffix(tag), r.is_latest) for r in rows) == [
            (2022, "20F-2022", False), (2022, "20F-2023A", False), (2022, "20F-2024", True),
            (2023, "20F-2023", False), (2023, "20F-2024", False), (2023, "20F-2025", True),
            (2024, "20F-2024", True),
        ]  # demoted, never deleted
        same_filing = next(r for r in rows if r.period_end.year == 2024)
        stored = {i["unit"] for i in (same_filing.provenance or {}).get("inputs", ())}
        assert stored == ({"USD"} if recorded else set())  # never rewritten
        assert [r.is_latest for r in db.query(FinancialFact).filter_by(company_id=other.id)] == [True]

        plan = repair_company(db, fpi.id, payload(), dry_run=True)
        fixed = next(c["after"] for c in plan["changes"] if c["fact_id"] == same_filing.id)
        assert {i["unit"] for i in fixed["provenance"]["inputs"]} == {"CNY"}

        again = _checked_sync(db, fpi, payload())
        assert (again["inserted"], again["demoted"]) == (0, 0)
        usd_filer = _new_company(db)  # ratios from USD operands are the upsert's alone
        assert _checked_sync(db, usd_filer, payload(("USD", "USD/shares")), final=True)["demoted"] == 0
        db.close()

    def test_a_native_year_the_collector_drops_leaves_a_gap_not_a_usd_point(self):
        # Over the USD revenue a pre-fix sync stored, the CNY list's only FY2024 item has no value.
        # The series is CNY, so the sync demotes every one of those USD rows, never deleting one, and
        # FY2024 is a gap rather than a USD point inside a CNY series (a YoY of -85.0%).
        from app.database import SessionLocal
        from app.models import FinancialFact
        from app.services import trend_analysis_service

        db = SessionLocal()
        fpi = _new_company(db)
        usd = [round(value / rate, 0) for (_fy, _start, _end, rate), value in zip(_CNY_YEARS, _CNY_REVENUE)]
        svc.upsert_facts_bulk(db, [_fact_dict(fpi.id, end=date(fy, 3, 31), value=value, accession=f"20F-{fy}")
                                   for (fy, *_rest), value in zip(_CNY_YEARS, usd)])
        payload = _cny_payload()
        payload["facts"]["us-gaap"][REV_TAG]["units"]["CNY"][-1]["val"] = None
        _checked_sync(db, fpi, payload, final=True)
        dataset = trend_analysis_service.build_dataset(db, fpi, "annual", "FY2022", "FY2024")
        series = next(s for s in dataset["series"] if s["concept"] == "revenue")
        assert (series["unit"], [p["value"] for p in series["points"]]) == ("CNY", [*_CNY_REVENUE[:2], None])
        rows = db.query(FinancialFact).filter_by(company_id=fpi.id, concept="revenue").all()
        assert sorted((r.unit, r.is_latest) for r in rows) == [("CNY", True)] * 2 + [("USD", False)] * 3
        db.close()

    def test_a_stray_usd_amendment_after_a_native_sync_changes_nothing(self):
        # A 20-F/A that tags one later year in USD neither flips the series nor demotes a row: the
        # second sync stores nothing new, and Multi-Period growth stays as reported (+1.8%, +8.3%),
        # not the convenience translations' -6.0% and +3.0%.
        from app.database import SessionLocal
        from app.models import FinancialFact
        from app.services import trend_analysis_service

        db = SessionLocal()
        fpi = _new_company(db)

        def stored():
            return sorted((r.id, r.unit, r.value, r.is_latest)
                          for r in db.query(FinancialFact).filter_by(company_id=fpi.id))

        first = _checked_sync(db, fpi, _cny_payload(), final=True)
        before = stored()
        second = _checked_sync(db, fpi, _with_stray_usd_amendment(_cny_payload()), final=True)
        assert (second["inserted"], second["skipped"], second["demoted"]) == (0, first["inserted"], 0)
        assert stored() == before
        dataset = trend_analysis_service.build_dataset(db, fpi, "annual", "FY2022", "FY2024")
        series = next(s for s in dataset["series"] if s["concept"] == "revenue")
        assert (series["unit"], [p["value"] for p in series["points"]]) == ("CNY", list(_CNY_REVENUE))
        assert [p.get("yoy") for p in series["points"]] == [
            None,
            pytest.approx(_CNY_REVENUE[1] / _CNY_REVENUE[0] - 1),
            pytest.approx(_CNY_REVENUE[2] / _CNY_REVENUE[1] - 1),
        ]
        db.close()

    def test_a_switch_to_usd_demotes_every_native_row_and_reads_only_the_usd_report(self):
        # A sync of the CNY 20-Fs, then a FY2025 20-F that reports in USD. The series is now USD:
        # the CNY 20-Fs are not read (their USD convenience years included), and every current CNY
        # row of those concepts is demoted, at any period, never deleted. Without that, the CNY and
        # USD rows would both be current at FY2023-24, since is_latest is kept per unit.
        from app.database import SessionLocal
        from app.models import FinancialFact
        from app.services import trend_analysis_service

        db = SessionLocal()
        company = _new_company(db)
        _checked_sync(db, company, _switched_to_usd_payload(switched=False), final=True)
        native = {r.id for r in db.query(FinancialFact).filter_by(company_id=company.id) if r.unit.startswith("CNY")}
        result = _checked_sync(db, company, _switched_to_usd_payload(), final=True)
        rows = db.query(FinancialFact).filter_by(company_id=company.id).all()
        current = [r for r in rows if r.is_latest]
        assert {r.unit for r in current} == {"USD", "USD/shares", "pure"}
        keys = [(r.concept, r.period_end, r.fiscal_period) for r in current]
        assert len(keys) == len(set(keys))  # one current row, so one currency, per key
        assert {r.id for r in rows if r.unit.startswith("CNY")} == native  # demoted, never deleted
        assert not any(r.is_latest for r in rows if r.id in native)
        assert result["demoted"] == len(native) + 2  # and the FY2023-24 margins the upsert replaced
        assert {r.period_end.year for r in rows if (r.concept, r.unit) == ("revenue", "USD")} == {2023, 2024, 2025}

        dataset = trend_analysis_service.build_dataset(db, company, "annual", "FY2023", "FY2025")
        series = next(s for s in dataset["series"] if s["concept"] == "revenue")
        assert series["unit"] == "USD"
        assert [p["value"] for p in series["points"]] == pytest.approx(
            [_CNY_REVENUE[1] / 7, _CNY_REVENUE[2] / 7, _CNY_REVENUE[2] / 7 * 1.05])

        again = _checked_sync(db, company, _switched_to_usd_payload(), final=True)
        assert (again["inserted"], again["demoted"]) == (0, 0)
        db.close()

    def test_a_switch_to_usd_promotes_usd_ratios_over_native_ones_a_known_filing_kept_current(self):
        # The mirror of the native-ratio promotion above. 20F-2024 is stored locally, so the FY2023-24
        # margins the first sync computed from its CNY operands outrank the USD 20-F's (an unknown
        # filing date), and the upsert stores the USD calculations behind them. The sync demotes the
        # CNY-derived margins and promotes the batch's own. A margin at a period the USD report does
        # not present is no calculation of this batch, so it is left as it is.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"  # accession numbers are unique across companies

        def payload(**kwargs):
            data = _switched_to_usd_payload(**kwargs)
            for node in data["facts"]["us-gaap"].values():
                for item in (item for items in node["units"].values() for item in items):
                    item["accn"] += tag
            return data

        db.add(Filing(company_id=company.id, accession_number=f"20F-2024{tag}", filing_type="20-F",
                      filing_date=datetime(2024, 7, 22, tzinfo=timezone.utc),
                      document_url="https://example.com/d", sec_url="https://example.com/s"))
        db.commit()
        _checked_sync(db, company, payload(switched=False), final=True)
        _checked_sync(db, company, payload(), final=True)
        rows = db.query(FinancialFact).filter_by(company_id=company.id, concept="net_margin").all()

        def operands(row):
            return {i["unit"] for i in (row.provenance or {}).get("inputs", ())}

        assert sorted((r.period_end.year, r.accession.removesuffix(tag), *operands(r), r.is_latest) for r in rows) == [
            (2021, "20F-2022", "CNY", True), (2022, "20F-2024", "CNY", True),
            (2023, "20F-2024", "CNY", False), (2023, "20F-2025", "USD", True),
            (2024, "20F-2024", "CNY", False), (2024, "20F-2025", "USD", True),
            (2025, "20F-2025", "USD", True),
        ]  # demoted, never deleted
        db.close()

    @pytest.mark.parametrize("form", ["6-K", "10-Q"])
    def test_a_stale_payload_after_a_switch_leaves_the_newer_report_and_a_fresh_one_finds_the_series_whole(self, form):
        # CNY 20-Fs, then the USD 20-F for FY2025 with the switch's first USD report, a quarterly
        # report filed before it (2024-08-20), then the pre-switch payload again (a delayed SEC
        # response, or another process's older fetch), then the current one. The stale payload does
        # not name 20F-2025 (filed 2025-07-23, after its newest filing, the quarterly report), an
        # annual report whose current rows read USD over FY2023-25, so it proves the payload older
        # than the switch: the sync stores nothing and demotes every current amount or per-share row
        # in another currency than USD, here none. It demotes none of 20F-2025's rows, ratios
        # included, and leaves the quarterly report's two Q1 rows current, though it names that
        # report and its own currency is not the stale CNY series'; its own CNY rows stay stored, not
        # current, at the periods only it presents (FY2021-22, and the FY2023 balance sheet), where
        # they would read CNY beside USD FY2023-25. The fresh sync then finds the series as the first
        # USD sync left it. Without the guard the stale sync demotes every USD row; without the
        # switch it demotes the Q1 rows and makes those CNY rows current (the check that no concept
        # spans two currencies fails first).
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        quarter = _QUARTER_ACCESSION[form]

        def payload(switched=True):
            return _with_later_usd_quarter(_switched_to_usd_payload(switched=switched), form)

        _checked_sync(db, company, payload(switched=False))
        _checked_sync(db, company, payload())
        rows = [r for r in db.query(FinancialFact).filter_by(company_id=company.id) if r.is_latest]
        assert sorted((r.period_end.year, r.fiscal_period, r.unit, r.accession) for r in rows if r.concept == "revenue") == [
            (2023, "FY", "USD", "20F-2025"), (2023, "Q1", "USD", quarter), (2024, "FY", "USD", "20F-2025"),
            (2024, "Q1", "USD", quarter), (2025, "FY", "USD", "20F-2025")]
        assert sorted({r.unit for r in rows}) == ["USD", "USD/shares", "pure"]
        switched = _current_rows(db, company.id)

        stale = _checked_sync(db, company, payload(switched=False))
        _one_currency_per_concept(db, company.id)
        assert _current_rows(db, company.id) == switched
        assert (stale["inserted"], stale["skipped"], stale["demoted"]) == (0, 0, 0)
        fresh = _checked_sync(db, company, payload(), final=True)
        assert (fresh["inserted"], fresh["demoted"]) == (0, 0)
        assert _current_rows(db, company.id) == switched
        db.close()

    @pytest.mark.parametrize("extra", ["as-synced", "with-a-later-cny-amendment", "with-a-stray-eur-row",
                                       "with-a-stray-eur-row-in-the-new-report"])
    def test_a_sync_before_companyfacts_shows_a_new_currencys_annual_report_reads_only_that_currency(self, extra):
        # A CNY-synced company files its first USD 20-F, and the per-filing writer stores that filing's rows
        # (filing_id set, a Filing row dated 2025-07-23, no filed_at of their own). The per-filing writer
        # keeps is_latest per unit, so CNY and USD are both current at FY2023-24. The new Filing lets the next
        # coverage request bypass the sync TTL, but SEC's companyfacts does not show the filing yet: the
        # payload is the CNY one, filed before it, alone, with a 20-F/A restating FY2024 revenue in CNY (filed
        # 2024-09-01), or after the per-filing writer stored an old 20-F's FY2022 cash flow in EUR, or the new
        # 20-F's FY2024 one (its per-concept pick, beside its USD row). The new filing is an annual report
        # whose current rows read USD over FY2023-25, so it proves the payload older than the switch: the sync
        # stores nothing (the amendment neither) and demotes every current amount or per-share row in another
        # currency than USD (the EUR row too), protected or not, and keeps every row of the new filing
        # current, its USD-derived margins included. That is the set the sync that names 20F-2025 converges
        # to: USD FY2023-25, FY2021-22 a gap. Leaving the per-filing writer's state read FY2023 revenue in USD
        # after FY2022 in CNY, a YoY of -85.5%.
        from app.database import SessionLocal
        from app.models import FinancialFact
        from app.services import trend_analysis_service

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"  # accession numbers are unique across companies
        stale_payload = _switched_to_usd_payload(switched=False)
        if extra == "with-a-later-cny-amendment":
            stale_payload["facts"]["us-gaap"][REV_TAG]["units"]["CNY"].append(_item(
                _CNY_REVENUE[2] * 1.01, "2024-03-31", start="2023-04-01", accn="20FA-2024", fy=2024,
                form="20-F/A", filed="2024-09-01"))
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        if extra.startswith("with-a-stray-eur-row"):
            owner, year = ("20F-2025", 2024) if extra.endswith("new-report") else ("20F-2022", 2022)
            svc.upsert_facts_bulk(db, [_fact_dict(company.id, "operating_cash_flow", end=date(year, 3, 31), unit="EUR",
                                                  value=24_000e6, accession=f"{owner}{tag}", source="edgar_xbrl")])
        filing = _store_per_filing(db, company, _suffixed(_switched_to_usd_payload(), tag), f"20F-2025{tag}", "20-F",
                                   "2025-07-23")
        ids = {r.id for r in db.query(FinancialFact).filter_by(filing_id=filing.id)}
        assert {r.unit for r in db.query(FinancialFact).filter(FinancialFact.id.in_(ids))} == {
            "USD", "USD/shares", "pure"}
        other = [r.id for r in db.query(FinancialFact).filter_by(company_id=company.id, is_latest=True)
                 if r.fiscal_period and not r.unit.startswith("USD") and r.unit != "pure"]
        stored = db.query(FinancialFact).filter_by(company_id=company.id).count()

        stale = _checked_sync(db, company, _suffixed(stale_payload, tag))
        _one_currency_per_concept(db, company.id)
        assert db.query(FinancialFact).filter_by(company_id=company.id).count() == stored  # nothing stored
        assert (stale["inserted"], stale["skipped"], stale["demoted"]) == (0, 0, len(other))
        assert all(r.is_latest for r in db.query(FinancialFact).filter(FinancialFact.id.in_(ids)))
        current = _current_rows(db, company.id)
        assert {unit for *_key, unit, _accession in current} == {"USD", "USD/shares", "pure"}
        assert sorted(end.year for concept, end, period, *_rest in current if (concept, period) == ("revenue", "FY")) == [
            2023, 2024, 2025]
        dataset = trend_analysis_service.build_dataset(db, company, "annual", "FY2021", "FY2025")
        series = next(s for s in dataset["series"] if s["concept"] == "revenue")
        assert (series["unit"], [p["value"] for p in series["points"]][:2]) == ("USD", [None, None])
        assert [p["value"] for p in series["points"]][2:] == pytest.approx(
            [_CNY_REVENUE[1] / 7, _CNY_REVENUE[2] / 7, _CNY_REVENUE[2] / 7 * 1.05])

        fresh = _checked_sync(db, company, _suffixed(_switched_to_usd_payload(), tag), final=True)
        assert (fresh["inserted"], fresh["demoted"]) == (0, 0)
        assert _current_rows(db, company.id) == current
        db.close()

    def test_a_new_currency_quarterly_reports_own_rows_are_current_once_the_annual_report_switches(self):
        # A user opens the switch's first USD report, a 10-Q filed (2024-08-20) before the USD 20-F,
        # while the series is still CNY: the per-filing writer stores its two Q1 revenue rows in USD.
        # The next sync's payload names the 10-Q, whose own currency is not its CNY series', so it
        # demotes them. The USD sync after the annual report presents those very identities, skips
        # them, and promotes them, since no row is current at their keys. (A 6-K's per-filing rows
        # carry no fiscal period, so the sync leaves them alone; a 10-Q's are labelled.)
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"

        def payload(switched=True):
            return _suffixed(_with_later_usd_quarter(_switched_to_usd_payload(switched=switched), "10-Q"), tag)

        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))  # before the 10-Q
        filing = Filing(company_id=company.id, accession_number=f"10Q-2025Q1{tag}", filing_type="10-Q",
                        filing_date=datetime(2024, 8, 20, tzinfo=timezone.utc),
                        document_url="https://example.com/d", sec_url="https://example.com/s")
        db.add(filing)
        db.commit()
        svc.upsert_facts_bulk(db, [{**f, "source": "edgar_xbrl", "filing_id": filing.id}
                                   for f in svc.normalize_companyfacts(company.id, payload())[0]
                                   if f["accession"] == filing.accession_number])

        def own():
            return sorted((r.concept, r.period_end.year, r.fiscal_period, r.unit, r.is_latest)
                          for r in db.query(FinancialFact).filter_by(filing_id=filing.id))

        assert own() == [("revenue", 2023, "Q1", "USD", True), ("revenue", 2024, "Q1", "USD", True)]
        assert _checked_sync(db, company, payload(switched=False))["demoted"] == 2
        assert own() == [("revenue", 2023, "Q1", "USD", False), ("revenue", 2024, "Q1", "USD", False)]
        _checked_sync(db, company, payload(), final=True)
        assert own() == [("revenue", 2023, "Q1", "USD", True), ("revenue", 2024, "Q1", "USD", True)]
        db.close()

    def test_a_stale_payload_after_a_first_sync_past_the_switch_never_leaves_two_currencies_current(self):
        # A company first synced after its switch, then the stale pre-switch payload, which would
        # store its CNY identities for the first time. 20F-2025 (filed 2025-07-23, after the payload's
        # newest, and not named by it) is an annual report whose current rows read USD over FY2023-25,
        # so it proves the payload older than the switch: the sync stores none of the payload's 32
        # rows. Stored current, the CNY amounts at FY2021-22 would read CNY beside USD FY2023-25, and
        # margins computed in CNY would stand at periods the USD report does not present; stored not
        # current, they would hold identities a later sync skips and never promotes. The fresh sync
        # then finds the series as the first sync left it.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        _checked_sync(db, company, _switched_to_usd_payload())
        first = _current_rows(db, company.id)
        assert {accession for *_key, accession in first} == {"20F-2025"}
        stored = db.query(FinancialFact).filter_by(company_id=company.id).count()

        stale = _checked_sync(db, company, _switched_to_usd_payload(switched=False))
        _one_currency_per_concept(db, company.id)
        assert _current_rows(db, company.id) == first
        assert (stale["inserted"], stale["skipped"], stale["demoted"]) == (0, 0, 0)
        assert db.query(FinancialFact).filter_by(company_id=company.id).count() == stored
        fresh = _checked_sync(db, company, _switched_to_usd_payload(), final=True)
        assert (fresh["inserted"], fresh["demoted"]) == (0, 0)
        assert _current_rows(db, company.id) == first
        db.close()

    def test_a_payload_older_than_a_switch_changes_no_ratio_beside_a_newer_one(self):
        # The upsert keeps one current ratio per key, so no writer leaves the stale payload's own
        # margin current beside the newer filing's; here one is set current anyway, at FY2023 under
        # 20F-2024 beside 20F-2025's. The stale CNY payload predates the switch 20F-2025 proves, so its
        # sync stores nothing, demotes only amount and per-share rows in another currency than USD
        # (none here), and replaces no ratio: that margin stays current until the fresh sync, which
        # demotes it (computed from CNY operands) and keeps 20F-2025's.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        _checked_sync(db, company, _switched_to_usd_payload())
        fy2023 = {"concept": "net_margin", "period_end": date(2023, 3, 31), "fiscal_period": "FY"}
        stale_margin = next(f for f in svc.normalize_companyfacts(company.id, _switched_to_usd_payload(switched=False))[0]
                            if all(f[key] == value for key, value in fy2023.items()))
        svc.upsert_facts_bulk(db, [stale_margin])  # no Filing rows, so it demotes 20F-2025's
        margins = db.query(FinancialFact).filter_by(company_id=company.id, **fy2023).all()
        for row in margins:
            row.is_latest = True
        db.commit()
        before = _current_rows(db, company.id)

        stale = _checked_sync(db, company, _switched_to_usd_payload(switched=False))
        _one_currency_per_concept(db, company.id)
        assert _current_rows(db, company.id) == before
        assert sorted((r.accession, r.is_latest) for r in margins) == [("20F-2024", True), ("20F-2025", True)]
        assert (stale["inserted"], stale["skipped"], stale["demoted"]) == (0, 0, 0)
        _checked_sync(db, company, _switched_to_usd_payload(), final=True)
        assert sorted((r.accession, r.is_latest) for r in margins) == [("20F-2024", False), ("20F-2025", True)]
        db.close()

    def test_a_ratio_a_newer_filing_holds_is_the_only_one_current_there(self):
        # The rule that a protected row holds its key is by kind, amounts and ratios, for a payload in the
        # newer filing's own currency. A filer reporting in CNY synced with K24 (filed 2025-02-15), then a payload
        # that lags it (newest K23, 2024-02-15): K24's rows, not named and filed after it, are protected. The
        # writers keep one current row per key and unit, and one ratio per key, so none leaves the lagging
        # payload's own FY2023 revenue or margin (K23) current beside K24's; here both are set current
        # anyway. The lagging sync skips their identities and demotes both: K24's are the current ones. (A filer
        # in USD alone is main's, which leaves that hand-built state as found: the USD-only corpus below.)
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        _checked_sync(db, company, _in_currency(_lagging_usd_payload(fresh=True), "CNY"), usd_only=False)
        fy2023 = {"period_end": date(2023, 12, 31), "fiscal_period": "FY"}
        own = [f for f in svc.normalize_companyfacts(company.id, _in_currency(_lagging_usd_payload(fresh=False), "CNY"))[0]
               if f["concept"] in ("net_margin", "revenue") and all(f[key] == value for key, value in fy2023.items())]
        svc.upsert_facts_bulk(db, own)  # no Filing rows, so it demotes K24's
        rows = db.query(FinancialFact).filter(FinancialFact.company_id == company.id,
                                              FinancialFact.concept.in_(("net_margin", "revenue"))).filter_by(**fy2023).all()
        for row in rows:
            row.is_latest = True
        db.commit()

        lagging = _checked_sync(db, company, _in_currency(_lagging_usd_payload(fresh=False), "CNY"))
        assert sorted((r.concept, r.accession, r.is_latest) for r in rows) == [
            ("net_margin", "K23", False), ("net_margin", "K24", True), ("revenue", "K23", False), ("revenue", "K24", True)]
        assert (lagging["inserted"], lagging["demoted"]) == (2, 2)  # K23's FY2023 income and EPS, behind K24's
        db.close()

    @pytest.mark.parametrize("form", ["10-Q", "20-F"])
    def test_a_newer_filing_in_another_currency_with_no_current_row_proves_no_switch(self, form):
        # A CNY filer's first USD report: the switch's first quarterly report (a 10-Q filed 2024-08-20,
        # its two Q1 rows), or the USD 20-F for FY2025 (filed 2025-07-23). The per-filing writer stored
        # its rows, and none is current any more (a sync that named the 10-Q demoted them, as in the
        # test above; set here by hand). A payload that does not name it and is older (newest
        # 2024-07-22) finds no current row of it, so even the annual report proves no switch: the sync
        # reads its CNY series and makes it current, as any first sync does.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        usd = _suffixed(_with_later_usd_quarter(_switched_to_usd_payload(), "10-Q"), tag)  # where it is read
        accession, filed = (f"10Q-2025Q1{tag}", "2024-08-20") if form == "10-Q" else (f"20F-2025{tag}", "2025-07-23")
        filing = _store_per_filing(db, company, usd, accession, form, filed)
        own = db.query(FinancialFact).filter_by(filing_id=filing.id).all()
        for row in own:
            row.is_latest = False
        db.commit()

        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        assert not any(r.is_latest for r in own)
        assert sorted((r.period_end.year, r.unit) for r in db.query(FinancialFact).filter_by(
            company_id=company.id, concept="revenue", fiscal_period="FY", is_latest=True)) == [
            (2021, "CNY"), (2022, "CNY"), (2023, "CNY"), (2024, "CNY")]
        db.close()

    @pytest.mark.parametrize("shape", ["one-period-annual-report", "one-period-in-its-own-currency", "tied-annual-report"])
    def test_a_newer_annual_report_that_could_not_decide_the_series_proves_no_switch(self, shape):
        # A CNY-synced company, then the per-filing writer stores a newer 20-F (filed 2025-07-23) that
        # filing_currencies would not let decide: one that tags its own year only (FY2025, in USD), or
        # its own year in USD and FY2024 revenue alone in CNY (its USD rows span one period-end), or
        # one whose amount rows split evenly, revenue and net income in USD and both cash flows in CNY
        # (its diluted EPS in USD/shares does not vote). A tie leaves its currency undetermined, and one
        # period-end presents no comparatives, so a lagging CNY payload proves no switch: its sync keeps
        # the CNY series and demotes that 20-F's USD rows, which are outside the CNY view.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))

        def edit(fact):
            if shape == "one-period-in-its-own-currency" and (fact["concept"], fact["period_end"]) == (
                    "revenue", date(2024, 3, 31)):
                return {**fact, "unit": "CNY", "value": fact["value"] * 7}
            if shape.startswith("one-period"):
                return fact if fact["period_end"] == date(2025, 3, 31) else None
            if fact["concept"] in ("operating_cash_flow", "capital_expenditures"):
                return {**fact, "unit": "CNY", "value": fact["value"] * 7}
            return fact if fact["concept"] in ("revenue", "net_income", "eps_diluted") else None

        filing = _store_per_filing(db, company, _suffixed(_switched_to_usd_payload(), tag), f"20F-2025{tag}", "20-F",
                                   "2025-07-23", edit)
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _one_currency_per_concept(db, company.id)
        rows = db.query(FinancialFact).filter_by(filing_id=filing.id).all()
        assert not any(r.is_latest for r in rows if r.unit.startswith("USD"))
        assert sorted((r.period_end.year, r.unit) for r in db.query(FinancialFact).filter_by(
            company_id=company.id, concept="revenue", fiscal_period="FY", is_latest=True)) == [
            (2021, "CNY"), (2022, "CNY"), (2023, "CNY"), (2024, "CNY")]
        db.close()

    def test_the_newer_annual_report_that_reports_the_latest_period_decides_a_switch(self):
        # A CNY-synced company, then the per-filing writer stores the USD 20-F for FY2025 (filed
        # 2025-07-23; its rows carry no form, so its Filing row's type names it an annual report) and a
        # CNY 20-F/A restating FY2023-24 revenue, filed after it (2025-09-01). A lagging CNY payload
        # names neither, so both are protected and both could decide. As in
        # filing_currencies, the one reporting the latest period decides, though the amendment was
        # filed last: the USD report, so the payload predates a switch. The sync stores nothing and
        # demotes every current amount or per-share row in another currency than USD, the amendment's
        # rows included (outside the USD view; the sync that names both demotes them too).
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _store_per_filing(db, company, _suffixed(_switched_to_usd_payload(), tag), f"20F-2025{tag}", "20-F", "2025-07-23",
                          lambda fact: {**fact, "form": None})
        amendment = Filing(company_id=company.id, accession_number=f"20FA-2024{tag}", filing_type="20-F/A",
                           filing_date=datetime(2025, 9, 1, tzinfo=timezone.utc),
                           document_url="https://example.com/d", sec_url="https://example.com/s")
        db.add(amendment)
        db.commit()
        svc.upsert_facts_bulk(db, [{**_fact_dict(company.id, end=date(fy, 3, 31), unit="CNY", value=value * 1.01,
                                                  accession=amendment.accession_number, source="edgar_xbrl"),
                                    "filing_id": amendment.id, "form": "20-F/A"}
                                   for fy, value in ((2023, _CNY_REVENUE[1]), (2024, _CNY_REVENUE[2]))])

        def revenue():
            return sorted((r.period_end.year, r.unit, r.accession.removesuffix(tag)) for r in db.query(FinancialFact)
                          .filter_by(company_id=company.id, concept="revenue", fiscal_period="FY", is_latest=True))

        stale = _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _one_currency_per_concept(db, company.id)
        assert (stale["inserted"], stale["skipped"]) == (0, 0)
        assert revenue() == [(year, "USD", "20F-2025") for year in (2023, 2024, 2025)]
        current = _current_rows(db, company.id)
        _checked_sync(db, company, _suffixed(_with_older_year_cny_amendment(_switched_to_usd_payload()), tag), final=True)
        assert _current_rows(db, company.id) == current
        db.close()

    @pytest.mark.parametrize("years, form", [((2023, 2024), "20-F/A"), ((2023, 2024), "10-K/A"), ((2024, 2025), "20-F/A")],
                             ids=["older-years-20-F/A", "older-years-10-K/A", "the-latest-year-20-F/A"])
    def test_a_newer_amendment_in_the_old_currency_proves_a_switch_only_if_it_reports_the_latest_period(self, years, form):
        # A switcher synced in USD from its 20-F for FY2025 (filed 2025-07-23). The per-filing writer then
        # stores a CNY amendment filed 2025-09-01, restating FY2023-24 revenue or FY2024-25, and its rows
        # are current: that sync demoted every CNY row. A lagging payload, the USD one, does not name it.
        # Its own deciding report is 20F-2025 (FY2025). As in filing_currencies, an amendment restating
        # older years never decides over it, so it proves no switch: the sync reads USD and demotes the
        # amendment's CNY rows, the set the sync that names the amendment converges to. One that also
        # restates FY2025 was filed later, so it decides (a tie on period-end goes to the later filing):
        # the payload predates the switch back to CNY, and its sync keeps only CNY current, amounts a
        # subset of the fresh sync's. Ranking the newer filings only against each other let the
        # older-year amendment prove a switch, and the lagging sync wiped every concept but its revenue.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        accession = f"20FA-{years[-1]}"
        values = {2023: _CNY_REVENUE[1], 2024: _CNY_REVENUE[2], 2025: _CNY_REVENUE[2] * 1.05}

        def payload(named):
            data = _switched_to_usd_payload()
            data["facts"]["us-gaap"][REV_TAG]["units"]["CNY"].extend(
                _item(values[fy] * 1.01, f"{fy}-03-31", start=f"{fy - 1}-04-01", accn=accession, fy=years[-1], form=form,
                      filed="2025-09-01") for fy in years if named)
            return _suffixed(data, tag)

        def amounts():
            return {row for row in _current_rows(db, company.id) if row[3] != "pure"}

        _checked_sync(db, company, payload(named=False))
        amendment = Filing(company_id=company.id, accession_number=f"{accession}{tag}", filing_type=form,
                           filing_date=datetime(2025, 9, 1, tzinfo=timezone.utc),
                           document_url="https://example.com/d", sec_url="https://example.com/s")
        db.add(amendment)
        db.commit()
        svc.upsert_facts_bulk(db, [{**_fact_dict(company.id, end=date(fy, 3, 31), unit="CNY", value=values[fy] * 1.01,
                                                  accession=amendment.accession_number, source="edgar_xbrl"),
                                    "filing_id": amendment.id, "form": form} for fy in years])
        own = db.query(FinancialFact).filter_by(filing_id=amendment.id).all()
        assert all(r.is_latest for r in own)

        lagging = _checked_sync(db, company, payload(named=False))
        _one_currency_per_concept(db, company.id)
        after_lagging, amounts_after_lagging = _current_rows(db, company.id), amounts()
        amendment_current = [r.is_latest for r in own]
        _checked_sync(db, company, payload(named=True), final=True)
        if years[-1] == 2024:
            assert after_lagging == _current_rows(db, company.id)
            assert (lagging["demoted"], amendment_current) == (2, [False, False])
        else:
            assert (lagging["inserted"], lagging["skipped"]) == (0, 0)
            assert {(concept, unit) for concept, _end, _period, unit, _accession in amounts_after_lagging} == {
                ("revenue", "CNY")}
            assert amounts_after_lagging <= amounts()
        db.close()

    @pytest.mark.parametrize("seeded", ["usd-lists-then-the-per-filing-writer", "main-after-the-switch",
                                        "usd-lists-then-the-per-filing-writers-own-rule",
                                        "usd-lists-then-the-per-filing-writer-a-first-20-f-in-eur"])
    def test_a_stale_payload_across_a_switch_demotes_the_convenience_rows_earlier_syncs_stored(self, seeded):
        # Earlier syncs stored each CNY 20-F's USD convenience year under that 20-F: before #1365 every sync
        # read the USD lists only, and main kept the USD list after a switch, 20F-2025's rows among them.
        # Where main did not read it, the per-filing writer stores the USD 20-F for FY2025 (filed 2025-07-23),
        # through the bulk writer's rule or its own (``upsert_facts``, under which a companyfacts row with no
        # Filing row counts as newer, so 20F-2025's FY2023-24 rows are stored behind the convenience rows and
        # only FY2025 is current, with no free cash flow derived here; its rows vote, current or not). Then a
        # payload that predates the switch is synced. 20F-2025 proves the switch, so the sync stores nothing;
        # the convenience rows are in USD, but this payload reads their filings in another currency, so it
        # demotes them too, as the sync that names 20F-2025 does: FY2022 is a gap, not 20F-2022's translation
        # at 6.34 (FY2023 growth -7.8% where the filer reported +1.8%). Demoting only the rows outside USD
        # left them current. In the last case 20F-2022 reports in EUR, a third currency (neither the payload's
        # CNY nor the switch's USD), so its USD row is demoted though that filing is foreign to the payload:
        # demoting only under filings the payload reads in its own currency left FY2022 current.
        from app.database import SessionLocal
        from app.models import FinancialFact
        from app.services import trend_analysis_service

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"

        def payload(switched):
            data = _switched_to_usd_payload(switched=switched)
            return _suffixed(_with_the_first_20f_in_eur(data) if seeded.endswith("in-eur") else data, tag)

        seed = payload(switched=seeded == "main-after-the-switch")
        svc.upsert_facts_bulk(db, svc.normalize_companyfacts(company.id, _usd_lists(seed))[0])
        if seeded != "main-after-the-switch":
            own_rule = seeded.endswith("own-rule")
            _store_per_filing(db, company, payload(switched=True), f"20F-2025{tag}", "20-F",
                              "2025-07-23", lambda fact: None if own_rule and fact["concept"] == "free_cash_flow" else fact,
                              writer=svc.upsert_facts if own_rule else None)
        stored = db.query(FinancialFact).filter_by(company_id=company.id).count()

        def amounts():
            return {row for row in _current_rows(db, company.id) if row[3] != "pure"}

        stale = _checked_sync(db, company, payload(switched=False))
        _one_currency_per_concept(db, company.id)
        assert (stale["inserted"], stale["skipped"], db.query(FinancialFact).filter_by(company_id=company.id).count()) == (
            0, 0, stored)
        after_stale = _current_rows(db, company.id)
        assert {accession.removesuffix(tag) for *_key, unit, accession in after_stale if unit != "pure"} == {"20F-2025"}
        dataset = trend_analysis_service.build_dataset(db, company, "annual", "FY2022", "FY2025")
        series = next(s for s in dataset["series"] if s["concept"] == "revenue")
        assert (series["unit"], [p["value"] for p in series["points"]][:2]) == (
            "USD", [None, None if seeded.endswith("own-rule") else pytest.approx(_CNY_REVENUE[1] / 7)])
        amounts_after_stale = amounts()

        _checked_sync(db, company, payload(switched=True), final=True)
        if seeded.endswith("own-rule"):  # 20F-2025's FY2023-24 rows stay behind until the fresh sync promotes them
            assert sorted(end.year for concept, end, *_rest in amounts_after_stale if concept == "revenue") == [2025]
            assert amounts_after_stale < amounts()
        else:
            assert after_stale == _current_rows(db, company.id)
        db.close()

    @pytest.mark.parametrize("own_rows, years, form", [
        (("revenue", "net_income"), (2023, 2024), "20-F/A"), (("revenue", "net_income"), (2023,), "20-F/A"),
        (("revenue", "net_income"), (2023, 2024), "10-Q/A"), (("revenue",), (2023, 2024), "20-F/A"),
        ((), (2023, 2024), "20-F/A"),
    ], ids=["more-rows-in-its-own-currency", "one-year-more-rows-in-its-own-currency",
            "a-10-Q/A-more-rows-in-its-own-currency", "tied", "only-its-usd-rows-stored"])
    def test_a_stale_payload_across_a_switch_reads_an_unnamed_filings_currency_from_its_stored_rows(self, own_rows, years,
                                                                                                    form):
        # A CNY-synced switcher. The per-filing writer stores the USD 20-F for FY2025 (filed 2025-07-23), then a
        # CNY 20-F/A restating FY2023-24 (or FY2023 alone), or a CNY 10-Q/A's two Q2 quarters, filed 2025-09-01,
        # whose capex its per-concept pick read in USD: filed last, those USD rows are current (the 20-F/A's
        # ahead of 20F-2025's). A lagging CNY payload names neither; 20F-2025 proves the switch, and the sync
        # that names the late report reads it in CNY and demotes its USD rows as convenience translations. This
        # payload cannot read that filing, so the sync reads its own currency from its stored rows, annual report
        # or not: where more are in CNY than in USD, its USD capex is demoted too, a gap and a subset of the fresh
        # sync's rows, whether or not that report could decide the series itself (a 10-Q/A, or a 20-F/A
        # restating a single year, never could). Where they tie, or hold only its USD rows, nothing stored
        # outvotes USD, so its USD capex stays current until the sync that names it: a window with a wrong number
        # (FY2025 capex growth against the 20-F/A's FY2024), which that sync closes.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _store_per_filing(db, company, _suffixed(_switched_to_usd_payload(), tag), f"20F-2025{tag}", "20-F", "2025-07-23")
        accession = _store_late_cny_report(db, company, tag, form, own_rows, years)
        _accession, period, ends = _LATE_REPORTS[form]

        def capex():
            return sorted((r.period_end, r.fiscal_period, r.unit, r.accession.removesuffix(tag)) for r in db.query(
                FinancialFact).filter_by(company_id=company.id, concept="capital_expenditures", is_latest=True))

        def amounts():
            return {row for row in _current_rows(db, company.id) if row[3] != "pure"}

        stray = [(ends[year], period, "USD", accession) for year in years]
        kept = [(date(year, 3, 31), "FY", "USD", "20F-2025") for year in (2023, 2024, 2025)
                if (date(year, 3, 31), "FY") not in {key[:2] for key in stray}]  # 20F-2025's rows the late report never displaced
        assert set(stray) <= set(capex())
        stale = _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _one_currency_per_concept(db, company.id)
        capex_after_stale, amounts_after_stale = capex(), amounts()
        _checked_sync(db, company, _suffixed(_with_late_cny_report(_switched_to_usd_payload(), form), tag), final=True)
        assert (stale["inserted"], stale["skipped"]) == (0, 0)
        assert capex() == [(date(year, 3, 31), "FY", "USD", "20F-2025") for year in (2023, 2024, 2025)]
        if own_rows == ("revenue", "net_income"):
            assert capex_after_stale == kept
            assert amounts_after_stale <= amounts()
        else:  # the window: FY2023-24 capex reads the 20-F/A's USD rows until the fresh sync
            assert capex_after_stale == sorted([*stray, *kept])
            assert {(concept, end.year, accession.removesuffix(tag))
                    for concept, end, _period, _unit, accession in amounts_after_stale - amounts()} == {
                ("capital_expenditures", year, "20FA-2024") for year in (2023, 2024)}
        db.close()

    @pytest.mark.parametrize("form, filed", [
        ("20-F/A", date(2025, 9, 1)), ("20-F/A", date(2025, 7, 23)), ("10-Q/A", date(2025, 9, 1)),
        ("10-Q/A", date(2025, 7, 23)), ("10-Q/A", None),  # an undated 20-F/A is stored behind 20F-2025's dated rows
    ], ids=["20-F/A-filed-after-the-payload", "20-F/A-filed-on-the-payloads-newest-date", "10-Q/A-filed-after-the-payload",
            "10-Q/A-filed-on-the-payloads-newest-date", "10-Q/A-undated"])
    @pytest.mark.parametrize("stale_first", [False, True], ids=["lagging-only", "stale-then-lagging"])
    def test_a_payload_lagging_a_newer_old_currency_report_demotes_its_convenience_rows_as_the_fresh_sync_does(
            self, stale_first, form, filed):
        # A switcher synced in USD from its 20-F for FY2025 (filed 2025-07-23). The per-filing writer then stores
        # an old-currency report filed 2025-09-01, a CNY 20-F/A restating FY2023-24 or a CNY 10-Q/A for two Q2
        # quarters, whose capex and diluted EPS its per-concept picks read in USD and USD/shares: those rows are
        # current. The sync the new Filing row triggers runs before companyfacts shows that report: its payload
        # names 20F-2025, so the series is USD and nothing proves a switch, but not the report. More of the
        # report's stored amount rows are in CNY than in USD, so, as the sync that names it reads them, its USD
        # capex and USD/shares EPS are convenience translations: none is protected and the sync demotes each.
        # 20F-2025's own rows then hold the 20-F/A's periods, which the payload presents; the 10-Q/A's Q2
        # quarters, which no payload presents, are a gap after both syncs. Protecting every newer row in USD left
        # the 20-F/A's translation current until that sync (FY2025 capex growth +9.1% against its 4.4bn, where
        # 20F-2025's restated 4.571bn gives +5.0%), while a stale pre-switch payload synced first demoted it, so
        # the order of two syncs decided the number. Both orders now end as the fresh sync does. So do they for
        # a report filed the payload's newest day, or one with no Filing row and no filed_at (undated), not known
        # to be newer and never protected: its stored rows vote too, so its Q2 translations, at keys no batch
        # presents, are demoted rather than left current.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _store_per_filing(db, company, _suffixed(_switched_to_usd_payload(), tag), f"20F-2025{tag}", "20-F", "2025-07-23")
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(), tag), final=True)
        accession = _store_late_cny_report(db, company, tag, form, per_share=True, filed=filed)
        _accession, period, ends = _LATE_REPORTS[form]

        def capex():
            return sorted((r.period_end, r.fiscal_period, r.unit, r.accession.removesuffix(tag)) for r in db.query(
                FinancialFact).filter_by(company_id=company.id, concept="capital_expenditures", is_latest=True))

        late = {(concept, end, period, unit, f"{accession}{tag}") for end in ends.values()
                for concept, unit in (("capital_expenditures", "USD"), ("eps_diluted", "USD/shares"))}
        assert late <= _current_rows(db, company.id)
        if stale_first:
            _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(), tag))
        _one_currency_per_concept(db, company.id)
        capex_after_lagging, after_lagging = capex(), _current_rows(db, company.id)
        _checked_sync(db, company, _suffixed(_with_late_cny_report(_switched_to_usd_payload(), form), tag), final=True)
        assert capex_after_lagging == [(date(year, 3, 31), "FY", "USD", "20F-2025") for year in (2023, 2024, 2025)]
        assert not late & after_lagging
        assert after_lagging == _current_rows(db, company.id)
        db.close()

    @pytest.mark.parametrize("order", ["fresh-only", "lagging-then-fresh", "stale-then-lagging-then-fresh",
                                       "lagging-then-lagging-naming-an-earlier-restatement-then-fresh",
                                       "stale-then-lagging-naming-an-earlier-restatement-then-fresh"])
    def test_a_lagging_sync_makes_a_newer_restatement_current_where_it_sits_behind_a_convenience_row(self, order):
        # The switcher of the test above, with two filings after 20F-2025 that a lagging payload does not name: a
        # USD 20-F/A (A, filed 2025-08-15) restating FY2024 capex at 4.6bn, then the CNY 20-F/A (filed 2025-09-01)
        # whose capex pick read USD, so its 4.4bn is current ahead of the restatement. The lagging sync demotes that
        # capex as a convenience translation. The restatement is protected, not current, and holds FY2024: the
        # sync makes it, the newest protected row there, current, never 20F-2025's superseded 4.571bn. A later
        # lagging payload may also name a USD 20-F/A filed between them (C, 2025-08-01, 4.55bn) that no writer
        # stored: the upsert stores C's row current where nothing current there is protected (after a stale sync's
        # demotion), and the sync demotes it for A's. The fresh sync's winner there is A's stored row. Before round
        # 10 the lagging sync left FY2024 a gap, and C's older 4.55bn went current through the upsert; before round
        # 9 it made 20F-2025's row current and the fresh sync, skipping A's identity, kept it for good. Every order
        # ends as the fresh sync alone does.
        from app.database import SessionLocal

        def with_c(payload):
            payload["facts"]["us-gaap"]["PaymentsToAcquirePropertyPlantAndEquipment"]["units"]["USD"].append(_item(
                4.55e9, "2024-03-31", start="2023-04-01", accn="20FA-C", fy=2025, form="20-F/A", filed="2025-08-01"))
            return payload

        db = SessionLocal()
        ends = {}
        for run in dict.fromkeys(("fresh-only", order)):
            company = _new_company(db)
            tag = f"-{uuid.uuid4().hex[:8]}"
            _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
            _store_per_filing(db, company, _suffixed(_switched_to_usd_payload(), tag), f"20F-2025{tag}", "20-F", "2025-07-23")
            _checked_sync(db, company, _suffixed(_switched_to_usd_payload(), tag), final=True)
            _store_filing_rows(db, company, f"20FA-2025{tag}", "20-F/A", "2025-08-15", [
                ("capital_expenditures", "USD", date(2024, 3, 31), 4.6e9),
                ("revenue", "USD", date(2024, 3, 31), 118_000e6), ("revenue", "USD", date(2025, 3, 31), 124_000e6)])
            _store_late_cny_report(db, company, tag, "20-F/A")
            steps = run.split("-then-")
            for step in steps[:-1]:
                lagging = with_c(_switched_to_usd_payload()) if "earlier-restatement" in step else _switched_to_usd_payload()
                _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False) if step == "stale" else lagging, tag))
                _one_currency_per_concept(db, company.id)
                if step != "stale":
                    assert {row[1:] for row in _untagged(_current_rows(db, company.id), tag)
                            if row[0] == "capital_expenditures"} == {
                        (date(2023, 3, 31), "FY", "USD", "20F-2025"), (date(2024, 3, 31), "FY", "USD", "20FA-2025"),
                        (date(2025, 3, 31), "FY", "USD", "20F-2025")}
            fresh = _with_usd_restatement(_with_late_cny_report(_switched_to_usd_payload(), "20-F/A"))
            _checked_sync(db, company, _suffixed(with_c(fresh) if "earlier-restatement" in run else fresh, tag), final=True)
            ends[run] = _untagged(_current_rows(db, company.id), tag)
        assert ("capital_expenditures", date(2024, 3, 31), "FY", "USD", "20FA-2025") in ends["fresh-only"]
        assert ends[order] == ends["fresh-only"]
        db.close()

    @pytest.mark.parametrize("order", ["fresh-only", "lagging-then-fresh"])
    def test_the_sync_naming_a_newer_report_whose_stored_picks_misvote_makes_its_restatement_current(self, order):
        # A USD filer synced through K24 and Q1-24 (Q1 2024 revenue 250). The per-filing writer then stores its
        # 10-Q for Q1 2025 (Q1-25, filed 2025-05-05), whose per-concept picks read revenue in USD (Q1 2025 at 300,
        # Q1 2024 restated at 260) but net income and operating cash flow in EUR: its stored rows vote EUR, while
        # the payload naming it reads it in USD. A lagging sync, which does not name it, reads it from that vote,
        # so its USD revenue is a convenience translation there: demoted, and Q1-24's 250 holds Q1 2024 until the
        # sync that names Q1-25 (the window: a wrong number). That sync's winner there is Q1-25's stored 260: it is
        # made current and Q1-24's row demoted. Before, that sync skipped the stored identity, found the key held
        # and left 250 current for good, where the fresh sync alone gives 260.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        ends = {}
        for run in dict.fromkeys(("fresh-only", order)):
            company = _new_company(db)
            tag = f"-{uuid.uuid4().hex[:8]}"

            def q1_2024():
                return [(float(r.value), r.accession.removesuffix(tag)) for r in db.query(FinancialFact).filter_by(
                    company_id=company.id, concept="revenue", period_end=date(2024, 3, 31), is_latest=True)]

            _checked_sync(db, company, _suffixed(_usd_quarterly_payload(named=False), tag), final=True)
            _store_filing_rows(db, company, f"Q1-25{tag}", "10-Q", "2025-05-05", [
                (concept, unit, end, value) for concept, unit, values in (
                    ("revenue", "USD", (260.0, 300.0)), ("net_income", "EUR", (23.4, 27.0)),
                    ("operating_cash_flow", "EUR", (40.0, 45.0)))
                for end, value in zip((date(2024, 3, 31), date(2025, 3, 31)), values)], fp="Q1")
            if run != "fresh-only":
                _checked_sync(db, company, _suffixed(_usd_quarterly_payload(named=False), tag))
                assert q1_2024() == [(250.0, "Q1-24")]  # the window
            _checked_sync(db, company, _suffixed(_usd_quarterly_payload(named=True), tag), final=True)
            assert q1_2024() == [(260.0, "Q1-25")]
            ends[run] = _untagged(_current_rows(db, company.id), tag)
        assert ends[order] == ends["fresh-only"]
        db.close()

    @pytest.mark.parametrize("order", ["fresh-only", "lagging-then-fresh", "lagging-naming-an-earlier-amendment-then-fresh",
                                       "lagging-behind-both-amendments-then-fresh"])
    def test_a_non_usd_filers_newest_amendment_is_current_where_the_per_filing_writer_stored_it_behind(self, order):
        # A filer reporting in CNY synced through K24 (FY2024 revenue 1200), a companyfacts row with no Filing row.
        # The per-filing writer then stores its 10-K/A (K24A, filed 2025-04-01) restating FY2024 at 1300: its own
        # rule counts a current companyfacts row with no Filing row as newer (``upsert_facts``), so 1300 is stored
        # behind 1200, and its diluted EPS 1.30 behind 1.20 (its net margin, a derived row, is not, and is current).
        # A lagging sync, which does not name K24A, finds K24A's rows protected and not current there: it makes
        # each, the newest protected row at its key, current and demotes K24's, in its demoted count. A lagging
        # payload may also name an earlier 10-K/A (K24B, filed 2025-03-01, 1250) that no writer stored: the upsert
        # stores K24B's row current, since nothing current there is protected, and the sync demotes it for K24A's
        # (an insert is not counted). Where the per-filing writer stored K24B after K24A, both behind K24's row,
        # the newest protected row is K24A's, the later filed, though K24B's has the higher id. The sync that
        # names K24A has K24A's stored row as its winner there. A filer in USD alone is main's: 1200 stays current
        # for good (the USD-only corpus below; the follow-up in tasks/todo.md).
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        earlier = order.startswith("lagging-naming") or order.startswith("lagging-behind-both")

        def cny(payload):
            return _suffixed(_in_currency(payload, "CNY"), tag)

        def fy2024(concept="revenue"):
            return sorted((round(float(r.value), 2), r.accession.removesuffix(tag), r.is_latest) for r in db.query(
                FinancialFact).filter_by(company_id=company.id, concept=concept, period_end=date(2024, 12, 31)))

        def with_k24b(payload):
            payload["facts"]["us-gaap"][REV_TAG]["units"]["USD"].append(_item(
                1250.0, "2024-12-31", start="2024-01-01", accn="K24B", fy=2024, form="10-K/A", filed="2025-03-01"))
            return payload

        def amended():  # K24A restates FY2024 diluted EPS too, a per-share row stored behind K24's as its revenue is
            payload = _with_amendment(_lagging_usd_payload(fresh=True))
            payload["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"].append(_item(
                1.3, "2024-12-31", start="2024-01-01", accn="K24A", fy=2024, form="10-K/A", filed="2025-04-01"))
            return payload

        _checked_sync(db, company, cny(_lagging_usd_payload(fresh=True)), final=True, usd_only=False)
        _store_per_filing(db, company, cny(amended()), f"K24A{tag}", "10-K/A", "2025-04-01", writer=svc.upsert_facts)
        assert fy2024() == [(1200.0, "K24", True), (1300.0, "K24A", False)]
        assert fy2024("eps_diluted") == [(1.2, "K24", True), (1.3, "K24A", False)]
        assert fy2024("net_margin") == [(9.23, "K24A", True), (10.0, "K24", False)]
        both = order.startswith("lagging-behind-both")
        if both:
            _store_per_filing(db, company, cny(with_k24b(_lagging_usd_payload(fresh=True))), f"K24B{tag}",
                              "10-K/A", "2025-03-01", writer=svc.upsert_facts)
            assert [row for row in fy2024() if row[2]] == [(1200.0, "K24", True)]
        if order != "fresh-only":
            lagging = _lagging_usd_payload(fresh=True)
            lagged = _checked_sync(db, company, cny(with_k24b(lagging) if earlier and not both else lagging))
            assert (lagged["inserted"], lagged["demoted"]) == ((2, 2) if earlier and not both else (0, 2))
            assert [row for row in fy2024() + fy2024("eps_diluted") if row[2]] == [(1300.0, "K24A", True), (1.3, "K24A", True)]
        fresh = amended()
        result = _checked_sync(db, company, cny(with_k24b(fresh) if earlier else fresh), final=True)
        assert [row for row in fy2024() + fy2024("eps_diluted") if row[2]] == [(1300.0, "K24A", True), (1.3, "K24A", True)]
        assert [row for row in fy2024("net_margin") if row[2]] == [(9.23, "K24A", True)]
        assert result["demoted"] == (2 if order == "fresh-only" else 0)
        db.close()

    def test_a_lagging_sync_never_leaves_its_own_row_current_where_the_newest_protected_row_is_quarantined(self):
        # The test above (a filer reporting in CNY) with K24A's FY2024 revenue quarantined by the journaled repair
        # (rolled back), stored not current. The lagging payload names K24B: the upsert stores K24B's 1250 current
        # and demotes K24's 1200, since nothing current there is protected. The newest protected row is never made
        # current, so the key is left as found, but the sync's own insert there is demoted: here a gap, never the
        # payload's older figure where a newer filing's row sits. Leaving the insert would show 1250 there until
        # the sync naming K24A. (Where the batch's own row was current before, it stays: left as found.)
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_in_currency(_lagging_usd_payload(fresh=True), "CNY"), tag), final=True)
        _store_per_filing(db, company, _suffixed(_in_currency(_with_amendment(_lagging_usd_payload(fresh=True)), "CNY"), tag),
                          f"K24A{tag}", "10-K/A", "2025-04-01", writer=svc.upsert_facts)
        row = db.query(FinancialFact).filter_by(company_id=company.id, accession=f"K24A{tag}", concept="revenue").one()
        row.provenance = {**row.provenance, "validation": "unavailable", "reasons": ["repair_rolled_back"]}
        db.commit()
        lagging = _lagging_usd_payload(fresh=True)
        lagging["facts"]["us-gaap"][REV_TAG]["units"]["USD"].append(_item(
            1250.0, "2024-12-31", start="2024-01-01", accn="K24B", fy=2024, form="10-K/A", filed="2025-03-01"))
        result = _checked_sync(db, company, _suffixed(_in_currency(lagging, "CNY"), tag), usd_only=False)
        assert sorted((float(r.value), r.accession.removesuffix(tag), r.is_latest) for r in db.query(FinancialFact).filter_by(
            company_id=company.id, concept="revenue", period_end=date(2024, 12, 31))) == [
            (1200.0, "K24", False), (1250.0, "K24B", False), (1300.0, "K24A", False)]
        assert (result["inserted"], result["demoted"]) == (2, 1)
        db.close()

    @pytest.mark.parametrize("older", ["filing-rows", "no-filing-rows"])
    @pytest.mark.parametrize("order", ["per-filing-then-sync", "sync-per-filing-then-sync",
                                       "sync-per-filing-then-lagging-then-sync"])
    def test_a_calculation_is_dated_by_its_own_filing_never_by_its_latest_operand(self, order, older):
        # ``_fcf_scenario`` for a filer in CNY. The batch's FY2023 free cash flow (300: K23's operating cash flow less
        # K24's capex) is dated by K23's own filing (its Filing row, else its filed date in the payload, 2024-02-15),
        # so K24's own 280, filed after it, holds the key at every sync. Dated by its latest operand (K24's
        # 2025-02-15, the date of K24's own row) the mixed 300 went current over K24's 280 wherever K23 has no Filing
        # row. Operating cash flow stays where the writers and the held key put it: K24's 480, or K23's 500 where the
        # per-filing writer stored K24's behind K23's undated companyfacts row and no lagging sync held the key (the
        # recorded older figure, as on main).
        from app.database import SessionLocal

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        ocf = ("K23", 500.0) if (order, older) == ("sync-per-filing-then-sync", "no-filing-rows") else ("K24", 480.0)
        assert _fcf_scenario(db, company, tag, "CNY", order, older) == [
            ("capital_expenditures", "K24", 200.0), ("free_cash_flow", "K24", 280.0), ("operating_cash_flow", *ocf)]
        db.close()

    @pytest.mark.parametrize("k24_stored", [True, False], ids=["k24-identity-stored", "k24-identity-new"])
    @pytest.mark.parametrize("k24a_filing_row", [False, True], ids=["k24a-no-filing-row", "k24a-filing-row"])
    def test_a_newer_filings_row_dated_by_its_provenance_holds_its_key_where_the_upsert_inserts(
            self, k24_stored, k24a_filing_row):
        # ``_same_day_stale_scenario`` for a filer in CNY. Filed on the stale payload's newest date, K24A is not
        # protected, but it is filed strictly after the batch's FY2024 winner, K24 (2025-02-15), so its rows hold the
        # key: its revenue, and its net margin (120 over 1300). Where the stale sync inserts K24's identity for the
        # first time, the upsert stores K24's rows behind K24A's (``Guard.later``, a ratio too): its own rule counts a
        # Filing-dated row only, so it demoted K24A's companyfacts rows, and K24's superseded 1200 showed until the
        # sync naming K24A, its 10.0 margin for good (no sync converges a ratio). The gate reads the newer row from
        # the state before the sync, so it sees that case too.
        from app.database import SessionLocal

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        fresh, stale = _same_day_stale_scenario(db, company, tag, "CNY", k24_stored, k24a_filing_row,
                                                ("net_margin", "revenue"))
        assert fresh == stale == [("net_margin", "K24A", 9.23), ("revenue", "K24A", 1300.0)]
        db.close()

    @pytest.mark.parametrize("shape, expected", [
        ("unpresented", [("net_income", "K24", 120.0), ("net_margin", "K24A", 9.23), ("revenue", "K24A", 1300.0)]),
        ("dated-by-provenance", [("net_income", "K24", 120.0), ("net_margin", "K24A", 9.23), ("revenue", "K24A", 1300.0)]),
        ("same-day-tie", [("net_income", "K24", 120.0), ("net_margin", "K24B", 9.16), ("revenue", "K24B", 1310.0)]),
        ("ratio", [("net_income", "K25", 130.0), ("net_margin", "K25", 10.74), ("revenue", "K25", 1210.0)]),
        ("ratio-unpresented", [("net_income", "K25", 130.0), ("net_margin", "K25", 10.74), ("revenue", "K25", 1210.0)]),
    ], ids=["unpresented", "dated-by-provenance", "same-day-tie", "ratio", "ratio-unpresented"])
    def test_a_held_key_holds_its_newest_protected_row_presented_or_not_a_ratio_too(self, shape, expected):
        # ``_held_key_scenario`` for a filer in CNY. At each key where a protected row sits, the one current row of its
        # kind is the newest protected row: latest filed (a Filing row's date, else its provenance's, so K24A's
        # companyfacts row outranks K24's per-filing row), then the higher accession, as the writers break a same-day
        # tie (K24B over K24A, though K24A's row was stored later), at a key the payload does not present too (FY2024
        # in a payload of K22 and K23), and for a ratio (K25's margin, stored behind K24's, beside K25's amounts).
        from app.database import SessionLocal

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        assert _held_key_scenario(db, company, tag, "CNY", shape) == expected
        db.close()

    def test_a_stored_calculation_is_dated_by_its_own_filing_too(self):
        # A filer in CNY. A first sync stores FY2023 free cash flow 300 under K23 (K23's operating cash flow 500 less
        # K24's capex 200, so its provenance filed_at is K24's 2025-02-15). Then a 10-K/A of FY2023 (K23A, filed
        # 2024-06-01) restates that cash flow at 510 under the first tag, so the batch's free cash flow there is
        # K23A's 310, which the second sync makes current. Here K23's 300 is set current again and K23A's row not
        # current (a state built by hand, as the ratio test's). The sync dates K23's stored row by its own filing (its
        # date in the payload, 2024-02-15), not by its later operand: K23A's 310, filed after it, is made current.
        # This pins the date rule's stored-row leg: with the batch row dated by its filing and the stored row by its
        # provenance (mutation A3r), K23's mixed 300 read as a newer filing's row and held the period.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"

        def items(values, accession, fiscal_year, filed, form="10-K"):
            return [_item(value, f"{year}-12-31", start=f"{year}-01-01", accn=accession, fy=fiscal_year, form=form,
                          filed=filed) for year, value in values]

        def payload(*, k23a):
            ocf = items(((2022, 400.0), (2023, 500.0)), "K23", 2023, "2024-02-15")
            ocf += items(((2023, 510.0),), "K23A", 2023, "2024-06-01", "10-K/A") if k23a else []
            return _suffixed(_in_currency(_payload({
                "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": ocf}},
                _OCF_CONTINUING: {"units": {"USD": items(((2023, 480.0), (2024, 600.0)), "K24", 2024, "2025-02-15")}},
                "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": items(
                    ((2022, 150.0), (2023, 200.0)), "K23", 2023, "2024-02-15") + items(
                    ((2023, 200.0), (2024, 250.0)), "K24", 2024, "2025-02-15")}}}), "CNY"), tag)

        def fcf():
            return sorted((r.accession.removesuffix(tag), float(r.value), r.is_latest) for r in db.query(FinancialFact)
                          .filter_by(company_id=company.id, concept="free_cash_flow", period_end=date(2023, 12, 31)))

        _checked_sync(db, company, payload(k23a=False), final=True, usd_only=False)
        _checked_sync(db, company, payload(k23a=True), final=True)
        assert fcf() == [("K23", 300.0, False), ("K23A", 310.0, True)]
        for row in db.query(FinancialFact).filter_by(company_id=company.id, concept="free_cash_flow",
                                                     period_end=date(2023, 12, 31)):
            row.is_latest = row.accession == f"K23{tag}"
        db.commit()
        _checked_sync(db, company, payload(k23a=True), final=True)
        assert fcf() == [("K23", 300.0, False), ("K23A", 310.0, True)]
        db.close()

    def test_a_lagging_sync_keeps_a_tied_newer_reports_row_in_its_currency_until_the_sync_that_names_it(self):
        # The window the vote leaves: the late CNY 20-F/A of the test above, storing CNY revenue and USD capex for
        # FY2023-24, ties (two rows each), so its stored rows vote no currency. A lagging payload that does not name
        # it cannot read it as a convenience translation: its USD capex is protected and stays current, a wrong
        # number (FY2025 growth against the translation), until the sync that names it reads it in CNY, demotes
        # that capex and makes 20F-2025's own rows current. Counting a tie as another currency would demote it
        # here too, where the vote cannot tell.
        from app.database import SessionLocal

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _store_per_filing(db, company, _suffixed(_switched_to_usd_payload(), tag), f"20F-2025{tag}", "20-F", "2025-07-23")
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(), tag), final=True)
        _store_late_cny_report(db, company, tag, "20-F/A", ("revenue",))

        def capex():
            return sorted((row[1].year, row[4].removesuffix(tag)) for row in _current_rows(db, company.id)
                          if row[0] == "capital_expenditures")

        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(), tag))
        assert capex() == [(2023, "20FA-2024"), (2024, "20FA-2024"), (2025, "20F-2025")]
        _checked_sync(db, company, _suffixed(_with_late_cny_report(_switched_to_usd_payload(), "20-F/A"), tag), final=True)
        assert capex() == [(2023, "20F-2025"), (2024, "20F-2025"), (2025, "20F-2025")]
        db.close()

    def test_a_native_series_lagging_a_newer_usd_quarterly_report_demotes_its_native_capex_as_the_fresh_sync_does(self):
        # The mirror on a CNY series. The per-filing writer stores a newer 10-Q (filed 2025-05-05; Q1 of FY2026 and
        # its comparative) with revenue and net income in USD and capex read in CNY. A lagging CNY payload does not
        # name it: its stored rows vote USD, so its CNY capex is a convenience translation and the sync demotes it,
        # as the sync that names it (by its USD revenue) does. A quarterly report never decides the series, which
        # stays CNY. Reading the vote only for a sync in USD left that capex current until the second sync.
        from app.database import SessionLocal

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        ends = (date(2024, 6, 30), date(2025, 6, 30))
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag), final=True)
        _store_filing_rows(db, company, f"10Q-2026Q1{tag}", "10-Q", "2025-05-05", [
            (concept, unit, end, value) for concept, unit, values in (
                ("revenue", "USD", (31.0e9, 33.0e9)), ("net_income", "USD", (3.1e9, 3.3e9)),
                ("capital_expenditures", "CNY", (9.0e9, 9.5e9))) for end, value in zip(ends, values)], fp="Q1")
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _one_currency_per_concept(db, company.id)
        after_lagging = _current_rows(db, company.id)
        assert not {row for row in after_lagging if row[2] == "Q1"}
        fresh = _switched_to_usd_payload(switched=False)
        fresh["facts"]["us-gaap"][REV_TAG]["units"]["USD"].extend(
            _item(value, end.isoformat(), start=end.replace(month=4, day=1).isoformat(), accn="10Q-2026Q1", fy=2026,
                  fp="Q1", form="10-Q", filed="2025-05-05") for end, value in zip(ends, (31.0e9, 33.0e9)))
        _checked_sync(db, company, _suffixed(fresh, tag), final=True)
        assert after_lagging == _current_rows(db, company.id)
        db.close()

    @pytest.mark.parametrize("dated", [True, False], ids=["filed-on-the-payloads-newest-date", "no-filing-date"])
    def test_a_filing_not_known_to_be_newer_never_proves_a_switch(self, dated):
        # A CNY-synced switcher whose USD 20-F for FY2025 the per-filing writer stored under a Filing dated the
        # pre-switch payload's newest day (2024-07-22), or with no Filing row and no filed_at. Every filing the
        # payload does not name votes, so its USD rows read as convenience translations of nothing the CNY series
        # reads, but it is not known to be newer than the payload, so it proves no switch: the sync stores the
        # payload and keeps the CNY series current. A proof from such a filing would make the sync store nothing
        # and keep only USD current.
        from app.database import SessionLocal

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        payload = _suffixed(_switched_to_usd_payload(), tag)
        if dated:
            _store_per_filing(db, company, payload, f"20F-2025{tag}", "20-F", "2024-07-22")
        else:
            svc.upsert_facts_bulk(db, [{**f, "source": "edgar_xbrl", "provenance": {**f["provenance"], "filed_at": None}}
                                       for f in svc.normalize_companyfacts(company.id, payload)[0]
                                       if f["accession"] == f"20F-2025{tag}"])
        assert ("revenue", date(2025, 3, 31), "FY", "USD", f"20F-2025{tag}") in _current_rows(db, company.id)
        result = _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        assert result["skipped"] > 0
        assert _current_amount_units(db, company.id)[("revenue", date(2024, 3, 31), "FY")] == ["CNY"]
        db.close()

    def test_a_proven_switch_leaves_rows_with_no_fiscal_period_alone(self):
        # A sync never touches a row with no fiscal period, which no growth series reads, on a proven switch
        # too: a CNY-synced company holds a current CNY revenue row with no fiscal period (as a 6-K's
        # per-filing rows carry none), the per-filing writer stores the USD 20-F for FY2025, and a lagging CNY
        # payload proves the switch. Its sync demotes every labelled CNY row and leaves that one current: no
        # sync makes a row with no fiscal period current again.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        svc.upsert_facts_bulk(db, [_fact_dict(company.id, fp=None, end=date(2024, 9, 30), unit="CNY", value=230_000e6,
                                              accession=f"6K-2025Q2{tag}", source="edgar_xbrl")])
        _store_per_filing(db, company, _suffixed(_switched_to_usd_payload(), tag), f"20F-2025{tag}", "20-F", "2025-07-23")

        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        current = db.query(FinancialFact).filter_by(company_id=company.id, concept="revenue", is_latest=True).all()
        assert sorted((r.period_end.year, r.fiscal_period or "", r.unit) for r in current) == [
            (2023, "FY", "USD"), (2024, "", "CNY"), (2024, "FY", "USD"), (2025, "FY", "USD")]
        db.close()

    def test_a_newer_annual_reports_currency_needs_more_rows_than_any_other_not_a_majority(self):
        # A CNY-synced company, then the per-filing writer stores a newer 20-F whose amount rows read three
        # currencies: revenue, net income and total assets in USD (8 rows over FY2023-25), both cash
        # flows in CNY (6) and free cash flow in EUR (3). USD carries more of them than any other, though
        # not half, so it is the filing's own currency, as filing_currencies counts: a lagging CNY payload
        # predates a switch, and its sync keeps only USD current.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        units = {"operating_cash_flow": "CNY", "capital_expenditures": "CNY", "free_cash_flow": "EUR"}
        _store_per_filing(db, company, _suffixed(_switched_to_usd_payload(), tag), f"20F-2025{tag}", "20-F", "2025-07-23",
                          lambda fact: {**fact, "unit": units.get(fact["concept"], fact["unit"])})

        stale = _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _one_currency_per_concept(db, company.id)
        assert (stale["inserted"], stale["skipped"]) == (0, 0)
        assert sorted((r.concept, r.period_end.year) for r in db.query(FinancialFact).filter_by(
            company_id=company.id, fiscal_period="FY", is_latest=True) if r.concept in ("revenue", "operating_cash_flow")) == [
            ("revenue", 2023), ("revenue", 2024), ("revenue", 2025)]
        db.close()

    @pytest.mark.parametrize("stray", ["capital_expenditures", "eps_diluted"])
    def test_a_newer_annual_report_in_the_series_currency_keeps_it_and_its_stray_concept_is_demoted(self, stray):
        # A CNY-synced company, then the per-filing writer stores a CNY 20-F for FY2025 (filed
        # 2025-07-23; FY2023-24 as 20F-2024 reported them), one concept of which its per-concept pick
        # read in USD (the stray: capital expenditure, or diluted EPS in USD/shares). A lagging CNY
        # payload does not name it. Its amount rows read CNY by majority, so it proves no switch, and
        # it holds its periods in the CNY view; its stray rows are outside that view, so the sync
        # demotes them. The CNY series reads FY2021-25, the stray concept FY2021-24 in CNY (FY2025 a
        # gap). Counting any one current row in another currency as a switch left the stray current
        # beside CNY.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))

        def as_a_cny_report(fact):  # 20F-2025's figures at 7 CNY a dollar, but for the stray concept
            if fact["unit"] == "pure":
                return None
            return fact if fact["concept"] == stray else {**fact, "unit": fact["unit"].replace("USD", "CNY"),
                                                          "value": fact["value"] * 7}

        filing = _store_per_filing(db, company, _suffixed(_switched_to_usd_payload(), tag), f"20F-2025{tag}", "20-F",
                                   "2025-07-23", as_a_cny_report)
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _one_currency_per_concept(db, company.id)

        def current(concept):
            return sorted((r.period_end.year, r.unit.partition("/")[0]) for r in db.query(FinancialFact).filter_by(
                company_id=company.id, concept=concept, fiscal_period="FY", is_latest=True))

        assert current("revenue") == [(year, "CNY") for year in range(2021, 2026)]
        assert current(stray) == [(year, "CNY") for year in range(2021, 2025)]
        assert [r.is_latest for r in db.query(FinancialFact).filter_by(filing_id=filing.id, concept=stray)] == [False] * 3
        db.close()

    @pytest.mark.parametrize("form", ["10-Q", "6-K"])
    def test_a_new_currency_quarterly_report_never_switches_a_lagging_sync_and_its_annual_report_does(self, form):
        # A CNY-synced company, then the per-filing writer stores the switch's first USD report, a 10-Q
        # or 6-K filed 2024-08-20 (its two Q1 rows). A lagging CNY payload does not name it: a quarterly
        # report proves no switch (it would not decide filing_currencies either), so the sync keeps the
        # CNY series and demotes the report's rows, which are outside the CNY view. Then the per-filing
        # writer stores the USD 20-F for FY2025, and the same lagging payload proves the switch: its
        # sync stores nothing and demotes every CNY row, so the series reads USD FY2023-25. The sync
        # that names both makes the quarterly report's rows current again.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        usd = _suffixed(_with_later_usd_quarter(_switched_to_usd_payload(), form), tag)
        quarterly = _store_per_filing(db, company, usd, f"{_QUARTER_ACCESSION[form]}{tag}", form, "2024-08-20")

        def revenue():
            return sorted((r.period_end.year, r.fiscal_period, r.unit) for r in db.query(FinancialFact).filter_by(
                company_id=company.id, concept="revenue", is_latest=True))

        def quarters():
            return [r.is_latest for r in db.query(FinancialFact).filter_by(filing_id=quarterly.id)]

        assert quarters() == [True, True]
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _one_currency_per_concept(db, company.id)
        assert (revenue(), quarters()) == ([(year, "FY", "CNY") for year in range(2021, 2025)], [False, False])

        _store_per_filing(db, company, usd, f"20F-2025{tag}", "20-F", "2025-07-23")
        switched = _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _one_currency_per_concept(db, company.id)
        assert (switched["inserted"], switched["skipped"]) == (0, 0)
        assert (revenue(), quarters()) == ([(year, "FY", "USD") for year in range(2023, 2026)], [False, False])
        _checked_sync(db, company, usd, final=True)
        assert quarters() == [True, True]
        db.close()

    def test_a_stale_payloads_amendment_beside_a_newer_quarterly_report_is_current_after_both_syncs(self):
        # A CNY-synced company, then the per-filing writer stores the switch's first USD report, a 10-Q
        # filed 2024-08-20 (its two Q1 rows). Then a payload that lags it and carries a CNY 20-F/A
        # (filed 2024-08-01) restating FY2023-24 revenue that no earlier sync stored, then the payload
        # that names the 10-Q. A quarterly report proves no switch, so the lagging sync reads its CNY
        # view: the 10-Q's USD rows, outside it, are demoted, and the amendment's rows are stored current
        # over 20F-2024's. They stay current after the sync that names the 10-Q. Leaving them stored not
        # current stranded the amendment: a later sync skips a stored identity, and 20F-2024's row held
        # the key against its promotion.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        quarterly = _store_per_filing(db, company, _suffixed(_with_later_usd_quarter(_switched_to_usd_payload(), "10-Q"), tag),
                                      f"10Q-2025Q1{tag}", "10-Q", "2024-08-20")

        def payload(named):
            data = _with_older_year_cny_amendment(_switched_to_usd_payload(switched=False), filed="2024-08-01")
            return _suffixed(_with_later_usd_quarter(data, "10-Q") if named else data, tag)

        def revenue():
            return sorted((r.period_end.year, r.accession.removesuffix(tag)) for r in db.query(FinancialFact).filter_by(
                company_id=company.id, concept="revenue", fiscal_period="FY", is_latest=True))

        amended = [(2021, "20F-2022"), (2022, "20F-2024"), (2023, "20FA-2024"), (2024, "20FA-2024")]
        _checked_sync(db, company, payload(named=False))
        _one_currency_per_concept(db, company.id)
        assert revenue() == amended
        assert not any(r.is_latest for r in db.query(FinancialFact).filter_by(filing_id=quarterly.id))
        _checked_sync(db, company, payload(named=True), final=True)
        assert revenue() == amended
        db.close()

    def test_a_stale_payloads_recast_beside_a_newer_filings_stray_row_is_current_after_both_syncs(self):
        # A USD filer synced through its FY2023 10-K (K23). The per-filing writer stores its next 10-Q
        # (Q1-24, filed 2024-05-05), whose net income the per-concept pick read in EUR (a stray). A
        # payload that lags the 10-Q carries a 10-K/A (K23A, filed 2024-03-01) recasting FY2023 revenue
        # from 1000 to 950, then the payload that names the 10-Q. A stray proves no switch: the lagging
        # sync demotes the EUR row, outside the USD view, and stores the recast current, which stays
        # current after the sync that names the 10-Q.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_lagging_usd_payload(fresh=False), tag))
        filing = Filing(company_id=company.id, accession_number=f"Q1-24{tag}", filing_type="10-Q",
                        filing_date=datetime(2024, 5, 5, tzinfo=timezone.utc),
                        document_url="https://example.com/d", sec_url="https://example.com/s")
        db.add(filing)
        db.commit()
        svc.upsert_facts_bulk(db, [{**_fact_dict(company.id, concept, fp="Q1", end=date(2024, 3, 31), unit=unit, value=value,
                                                  accession=filing.accession_number, source="edgar_xbrl"),
                                    "filing_id": filing.id, "form": "10-Q"}
                                   for concept, unit, value in (("revenue", "USD", 280.0), ("net_income", "EUR", 26.0))])

        def payload(named):
            data = _lagging_usd_payload(fresh=False)
            usgaap = data["facts"]["us-gaap"]
            usgaap[REV_TAG]["units"]["USD"].append(_item(950.0, "2023-12-31", start="2023-01-01", accn="K23A", fy=2023,
                                                         form="10-K/A", filed="2024-03-01"))
            for name, value in ((REV_TAG, 280.0), ("NetIncomeLoss", 28.0)) if named else ():
                usgaap[name]["units"]["USD"].append(_item(value, "2024-03-31", start="2024-01-01", accn="Q1-24", fy=2024,
                                                          fp="Q1", form="10-Q", filed="2024-05-05"))
            return _suffixed(data, tag)

        def fy2023():
            return sorted((r.accession.removesuffix(tag), float(r.value), r.is_latest) for r in db.query(FinancialFact)
                          .filter_by(company_id=company.id, concept="revenue", period_end=date(2023, 12, 31)))

        _checked_sync(db, company, payload(named=False))
        _one_currency_per_concept(db, company.id)
        assert fy2023() == [("K23", 1000.0, False), ("K23A", 950.0, True)]
        assert [(r.unit, r.is_latest) for r in db.query(FinancialFact).filter_by(filing_id=filing.id, concept="net_income")] == [
            ("EUR", False)]
        _checked_sync(db, company, payload(named=True), final=True)
        assert fy2023() == [("K23", 1000.0, False), ("K23A", 950.0, True)]
        db.close()

    @pytest.mark.parametrize("newer_rows", ["an-earlier-sync", "the-per-filing-writer"])
    def test_a_same_currency_payload_older_than_a_stored_filing_still_syncs_the_years_before_it(self, newer_rows):
        # A CNY filer's 10-K for FY2024 (K24, filed 2025-02-15) is stored, by a sync that named it or
        # by the per-filing writer (a Filing row, no filed_at of its own), and then a payload that lags
        # it is synced (a delayed SEC response, or the sync a new Filing triggers before companyfacts
        # shows it). K24's rows hold their keys, its diluted EPS (CNY/shares, in the CNY view) too: K23's
        # FY2023 figures are stored behind K24's restated ones, which stay current, on the upsert's path
        # too where K24's date is only its rows' filed_at. A newer filing in the payload's own currency
        # proves no currency switch, so the sync still makes its own rows current where no row is: FY2022,
        # which the per-filing writer did not store. The sync that names K24 then finds every period it
        # presents held, in CNY. A filer in USD alone is main's: the lagging sync's K23 1000 replaces K24's
        # 1050 where K24 has no Filing row, for good (the USD-only corpus below; the follow-up in tasks/todo.md).
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        def lagging(fresh):
            return _suffixed(_in_currency(_lagging_usd_payload(fresh=fresh), "CNY"), tag)

        if newer_rows == "an-earlier-sync":
            _checked_sync(db, company, lagging(True), usd_only=False)
        else:
            filing = Filing(company_id=company.id, accession_number=f"K24{tag}", filing_type="10-K",
                            filing_date=datetime(2025, 2, 15, tzinfo=timezone.utc),
                            document_url="https://example.com/d", sec_url="https://example.com/s")
            db.add(filing)
            db.commit()
            svc.upsert_facts_bulk(db, [{**f, "source": "edgar_xbrl", "filing_id": filing.id}
                                       for f in svc.normalize_companyfacts(company.id, lagging(True))[0]
                                       if f["accession"] == filing.accession_number])

        def revenue():
            return sorted((r.period_end.year, r.accession.removesuffix(tag), float(r.value), r.is_latest)
                          for r in db.query(FinancialFact).filter_by(company_id=company.id, concept="revenue"))

        k24 = {r.id for r in db.query(FinancialFact).filter_by(company_id=company.id, accession=f"K24{tag}", is_latest=True)}
        assert {r.unit for r in db.query(FinancialFact).filter(FinancialFact.id.in_(k24))} == {"CNY", "CNY/shares", "pure"}
        _checked_sync(db, company, lagging(False), usd_only=False)
        assert revenue() == [(2022, "K22", 800.0, True), (2023, "K23", 1000.0, False), (2023, "K24", 1050.0, True),
                             (2024, "K24", 1200.0, True)]
        assert k24 <= {r.id for r in db.query(FinancialFact).filter_by(company_id=company.id, is_latest=True)}
        _checked_sync(db, company, lagging(True), final=True)
        assert revenue() == [(2022, "K22", 800.0, True), (2023, "K23", 1000.0, False), (2023, "K24", 1050.0, True),
                             (2024, "K24", 1200.0, True)]
        db.close()

    def test_an_unprotected_row_another_filing_keeps_current_yields_its_key_to_the_batchs_own(self):
        # After the CNY sync, the per-filing writer stores FY2024 revenue in USD under a 20-F/A that
        # the payload does not name, filed 2025-06-01: before the switch payload's newest
        # (2025-07-23), so not protected. The switch sync's upsert stores 20F-2025's FY2024 revenue
        # behind it (a known filing date outranks an unknown one). 20F-2025, filed later, restates
        # FY2024: its row is the batch's winner there, so the sync makes it current and demotes the
        # 20-F/A's row, one current row at the period. Before, that row held the key and the newer
        # filing's figure stayed behind it.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        filing = Filing(company_id=company.id, accession_number=f"20FA-X{tag}", filing_type="20-F/A",
                        filing_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
                        document_url="https://example.com/d", sec_url="https://example.com/s")
        db.add(filing)
        db.commit()
        svc.upsert_facts_bulk(db, [{**_fact_dict(company.id, end=date(2024, 3, 31), value=126_000e6,
                                                  accession=filing.accession_number, source="edgar_xbrl"),
                                    "filing_id": filing.id}])

        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(), tag))
        rows = db.query(FinancialFact).filter_by(company_id=company.id, concept="revenue",
                                                 period_end=date(2024, 3, 31), fiscal_period="FY").all()
        assert sorted((r.unit, r.accession.removesuffix(tag), r.is_latest) for r in rows) == [
            ("CNY", "20F-2024", False), ("USD", "20F-2025", True), ("USD", "20FA-X", False)]
        db.close()

    @pytest.mark.parametrize("currency", ["USD", "CNY"])
    @pytest.mark.parametrize("order", ["per-filing-then-sync", "sync-per-filing-then-sync",
                                       "sync-per-filing-then-lagging-then-sync", "without-filing-rows"])
    def test_a_newer_filings_restatement_under_a_lower_priority_tag_stays_current_at_every_sync(self, order, currency):
        # A filer (in USD, or in CNY) whose FY2024 10-K (K24, filed 2025-02-15) moves revenue from the ASC 606 element to ``Revenues``
        # and diluted EPS to ``EarningsPerShareBasicAndDiluted`` after a 2:1 split, restating FY2023 (revenue 1050,
        # net income 105, EPS 2.50) where K23 reported 1000, 100 and 5.00. Companyfacts' collector takes a period
        # from the first registry tag with data, so the batch's FY2023 revenue and EPS are K23's, while the
        # per-filing writer, whose registry puts ``Revenues`` first, stores K24's restatement under its Filing row.
        # The upsert's filing-date rule keeps K24's rows current (a known later Filing date), and so does the sync:
        # a current row of a filing filed after the batch row's is left as found, at every sync, a lagging one
        # included (it holds K24's rows as protected). So FY2024 growth reads +14.3% (revenue) and +20% (EPS), and
        # the FY2023 margin, K24's 10%, sits beside K24's own amounts. Making the batch's row current there showed
        # K23's 1000 and 5.00 (+20.0% and -40%) and K24's margin beside K23's revenue. Without Filing rows for K22
        # and K23, the per-filing writer's own rule stores K24's restatement behind K23's undated companyfacts rows,
        # and no sync makes a named filing's row current over the batch's: K23's revenue and EPS stay, as on main.
        # In CNY, net income, whose batch winner is K24's own row, converges to 105, so K24's 10% margin sits
        # beside K23's 1000 (the recorded ratio gap). In USD the sync is main's (``usd_only``): net income stays
        # K23's 100, behind which the per-filing writer stored K24's 105 (the follow-up in tasks/todo.md).
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"

        def items(tag_values, accn, fy, filed):
            return [_item(value, f"{year}-12-31", start=f"{year}-01-01", accn=accn, fy=fy, filed=filed)
                    for year, value in tag_values]

        def payload(*, k24):
            usgaap = {REV_TAG: {"units": {"USD": items(((2022, 800.0),), "K22", 2022, "2023-02-15")
                                          + items(((2022, 800.0), (2023, 1000.0)), "K23", 2023, "2024-02-15")}},
                      "NetIncomeLoss": {"units": {"USD": items(((2022, 80.0), (2023, 100.0)), "K23", 2023, "2024-02-15")}},
                      "EarningsPerShareDiluted": {"units": {"USD/shares": items(((2022, 4.0), (2023, 5.0)), "K23", 2023,
                                                                                "2024-02-15")}}}
            if k24:
                usgaap["Revenues"] = {"units": {"USD": items(((2023, 1050.0), (2024, 1200.0)), "K24", 2024, "2025-02-15")}}
                usgaap["NetIncomeLoss"]["units"]["USD"] += items(((2023, 105.0), (2024, 120.0)), "K24", 2024, "2025-02-15")
                usgaap["EarningsPerShareBasicAndDiluted"] = {"units": {"USD/shares": items(
                    ((2023, 2.5), (2024, 3.0)), "K24", 2024, "2025-02-15")}}
            return _suffixed(_in_currency(_payload(usgaap), currency), tag)

        def filing(accession, filed, period_end=None):
            row = Filing(company_id=company.id, accession_number=f"{accession}{tag}", filing_type="10-K",
                         filing_date=datetime.fromisoformat(filed).replace(tzinfo=timezone.utc), period_end_date=period_end,
                         document_url="https://example.com/d", sec_url="https://example.com/s")
            db.add(row)
            db.commit()
            return row

        def per_filing_k24():  # the post-summary hook's writer, with K24's own XBRL picks
            def series(values, tag_name):
                return [{"period": f"{year}-12-31", "period_start": f"{year}-01-01", "value": value, "currency": currency,
                         "raw_tag": f"us-gaap:{tag_name}", "form": "10-K"} for year, value in values]
            standardized = {"reporting_currency": currency, **{concept: {"series": points, "current": points[-1]} for concept, points in (
                ("revenue", series(((2023, 1050.0), (2024, 1200.0)), "Revenues")),
                ("net_income", series(((2023, 105.0), (2024, 120.0)), "NetIncomeLoss")),
                ("eps_diluted", series(((2023, 2.5), (2024, 3.0)), "EarningsPerShareBasicAndDiluted")),
                ("net_margin", series(((2023, 10.0), (2024, 10.0)), "")))}}
            svc.process_filing_facts(db, filing("K24", "2025-02-15", date(2024, 12, 31)), standardized=standardized)

        def fy2023():
            return [(r.concept, round(float(r.value), 2), r.accession.removesuffix(tag)) for r in db.query(
                FinancialFact).filter_by(company_id=company.id, period_end=date(2023, 12, 31), fiscal_period="FY",
                                         is_latest=True).order_by(FinancialFact.concept)
                    if r.concept in ("eps_diluted", "net_income", "net_margin", "revenue")]

        expected = [("eps_diluted", 2.5, "K24"), ("net_income", 105.0, "K24"), ("net_margin", 10.0, "K24"),
                    ("revenue", 1050.0, "K24")]
        if order == "without-filing-rows":  # K23's figures where main shows them; net income converges to K24's
            expected = [("eps_diluted", 5.0, "K23"), ("net_income", 100.0, "K23"), ("net_margin", 10.0, "K24"),
                        ("revenue", 1000.0, "K23")]
        else:
            filing("K22", "2023-02-15")
            filing("K23", "2024-02-15")
        usd_only = currency == "USD"
        if order != "per-filing-then-sync":
            _checked_sync(db, company, payload(k24=False), final=True, usd_only=usd_only)
        per_filing_k24()
        assert fy2023() == expected
        if "lagging" in order:
            _checked_sync(db, company, payload(k24=False), usd_only=usd_only)
            assert fy2023() == expected
        if order == "without-filing-rows" and not usd_only:
            expected[1] = ("net_income", 105.0, "K24")
        for _sync in range(2):
            _checked_sync(db, company, payload(k24=True), final=True, usd_only=usd_only)
            assert fy2023() == expected
        db.close()

    @pytest.mark.parametrize("filed", [datetime(2024, 8, 20, tzinfo=timezone.utc), datetime(2025, 7, 23, tzinfo=timezone.utc),
                                       None],
                             ids=["filed-before-the-payloads-newest", "filed-on-the-payloads-newest-date", "no-filing-date"])
    def test_a_row_of_an_unnamed_filing_not_known_to_be_newer_is_demoted(self, filed):
        # After the CNY sync, the per-filing writer stores FY2024 revenue in USD under a 10-K/A that
        # the payload does not name: with a Filing dated 2024-08-20, before the switch payload's
        # newest (2025-07-23), or dated that same day, or with no Filing row and no filed_at. None is
        # known to be newer than the payload, so none is protected, and the switch sync's upsert,
        # which knows 20F-2025's date (2025-07-23), demotes it for 20F-2025's restated row: only
        # 20F-2025's USD row is current there. Protecting every unnamed row, every dated one, one filed
        # on the payload's newest date or an undated one would keep the older figure current instead.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        db.add(Filing(company_id=company.id, accession_number=f"20F-2025{tag}", filing_type="20-F",
                      filing_date=datetime(2025, 7, 23, tzinfo=timezone.utc),
                      document_url="https://example.com/d", sec_url="https://example.com/s"))
        owned = {"source": "edgar_xbrl"}
        if filed is not None:
            filing = Filing(company_id=company.id, accession_number=f"10KA-OLD{tag}", filing_type="10-K/A",
                            filing_date=filed, document_url="https://example.com/d", sec_url="https://example.com/s")
            db.add(filing)
            db.commit()
            owned["filing_id"] = filing.id
        db.commit()
        svc.upsert_facts_bulk(db, [{**_fact_dict(company.id, end=date(2024, 3, 31), value=126_000e6,
                                                  accession=f"10KA-OLD{tag}"), **owned}])

        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(), tag))
        rows = db.query(FinancialFact).filter_by(company_id=company.id, concept="revenue",
                                                 period_end=date(2024, 3, 31), fiscal_period="FY").all()
        assert sorted((r.unit, r.accession.removesuffix(tag)) for r in rows if r.is_latest) == [("USD", "20F-2025")]
        db.close()

    def test_a_same_day_filing_the_payload_does_not_name_yields_to_the_batchs_row(self):
        # After the CNY sync, the per-filing writer stores the USD 20-F for FY2025 (20F-2025, filed 2025-07-23), then
        # a USD 20-F/A the payload does not name, filed the same day, restating FY2024 revenue: the writers break a
        # same-day tie by accession, so the 20-F/A's row is current over 20F-2025's stored one. Filed on the
        # payload's newest date, it is not protected, and it is not filed after the batch row's filing: the switch
        # sync, which skips 20F-2025's stored identity, makes 20F-2025's row current and demotes the 20-F/A's. Only
        # a row of a filing filed strictly after the batch row's own holds its key.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        _store_per_filing(db, company, _suffixed(_switched_to_usd_payload(), tag), f"20F-2025{tag}", "20-F", "2025-07-23")
        filing = Filing(company_id=company.id, accession_number=f"20FA-SAMEDAY{tag}", filing_type="20-F/A",
                        filing_date=datetime(2025, 7, 23, tzinfo=timezone.utc),
                        document_url="https://example.com/d", sec_url="https://example.com/s")
        db.add(filing)
        db.commit()
        svc.upsert_facts_bulk(db, [{**_fact_dict(company.id, end=date(2024, 3, 31), value=126_000e6,
                                                  accession=filing.accession_number, source="edgar_xbrl"),
                                    "filing_id": filing.id}])

        def fy2024():
            return sorted((r.accession.removesuffix(tag), r.is_latest) for r in db.query(FinancialFact).filter_by(
                company_id=company.id, concept="revenue", period_end=date(2024, 3, 31), fiscal_period="FY", unit="USD"))

        assert fy2024() == [("20F-2025", False), ("20FA-SAMEDAY", True)]
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(), tag))
        assert fy2024() == [("20F-2025", True), ("20FA-SAMEDAY", False)]
        db.close()

    @pytest.mark.parametrize("currency", ["USD", "CNY"])
    def test_a_sync_never_promotes_a_quarter_beside_its_current_unlabelled_twin(self, currency):
        # A filer in USD (main's sync), or in CNY. A 10-Q/A's per-filing row for the Q2 2024 quarter carries no
        # fiscal period (its DEI focus was missing) and is current; its Filing row is dated 2025-04-01, after the
        # Q2-24 10-Q that companyfacts names for that quarter and before the payload's newest. The upsert
        # stores the batch's labelled Q2 row behind it (the D1 rule, and a known filing date outranks
        # an unknown one), so no labelled row is current there. The sync does not promote the batch's
        # row: that would leave two current rows for one quarter.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        filing = Filing(company_id=company.id, accession_number=f"Q2-24A{tag}", filing_type="10-Q/A",
                        filing_date=datetime(2025, 4, 1, tzinfo=timezone.utc),
                        document_url="https://example.com/d", sec_url="https://example.com/s")
        db.add(filing)
        db.commit()
        svc.upsert_facts_bulk(db, [{**_fact_dict(company.id, fp=None, end=date(2024, 6, 30), value=300.0, unit=currency,
                                                  accession=filing.accession_number, source="edgar_xbrl"),
                                    "filing_id": filing.id}])

        result = _checked_sync(db, company, _suffixed(_in_currency(_calendar_payload(), currency), tag),
                               usd_only=currency == "USD")
        rows = db.query(FinancialFact).filter_by(company_id=company.id, concept="revenue",
                                                 period_end=date(2024, 6, 30)).all()
        assert sorted((r.fiscal_period or "", r.accession.removesuffix(tag), r.is_latest) for r in rows) == [
            ("", "Q2-24A", True), ("Q2", "Q2-24", False)]
        assert result["demoted"] == 0
        db.close()

    @pytest.mark.parametrize("currency", ["USD", "CNY"])
    def test_a_quarter_whose_unlabelled_twin_is_current_is_left_as_found_beside_it(self, currency):
        # A filer in USD (main's sync), or in CNY, synced through Q2 2024 (Q2-24's labelled row current). A 10-Q/A's per-filing row for that
        # quarter then carries no fiscal period (its DEI focus was missing) and is current too: a row with no
        # fiscal period never demotes a labelled one. The next sync finds the quarter's unlabelled
        # twin in its unit current, so it leaves the quarter as found: the labelled row stays current, never a
        # gap, and the twin, which no sync touches, is current beside it as on main.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_in_currency(_calendar_payload(), currency), tag), final=True)
        filing = Filing(company_id=company.id, accession_number=f"Q2-24A{tag}", filing_type="10-Q/A",
                        filing_date=datetime(2025, 4, 1, tzinfo=timezone.utc),
                        document_url="https://example.com/d", sec_url="https://example.com/s")
        db.add(filing)
        db.commit()
        svc.upsert_facts_bulk(db, [{**_fact_dict(company.id, fp=None, end=date(2024, 6, 30), value=300.0, unit=currency,
                                                  accession=filing.accession_number, source="edgar_xbrl"),
                                    "filing_id": filing.id}])
        _checked_sync(db, company, _suffixed(_in_currency(_calendar_payload(), currency), tag), usd_only=currency == "USD")
        rows = db.query(FinancialFact).filter_by(company_id=company.id, concept="revenue", period_end=date(2024, 6, 30)).all()
        assert sorted((r.fiscal_period or "", r.accession.removesuffix(tag), r.is_latest) for r in rows) == [
            ("", "Q2-24A", True), ("Q2", "Q2-24", True)]
        db.close()

    def test_an_unlabelled_twin_in_another_unit_never_holds_a_quarter(self):
        # The unlabelled-twin rule is per unit, as the bulk writer's D1 rule is. A USD filer's Q2 2024
        # revenue row is stored and not current (a stale payload's demotion; set here by hand), and a
        # 10-Q/A's per-filing row for that quarter carries no fiscal period and was read in EUR
        # (dated 2025-04-01, before the payload's newest). A sync leaves rows with no fiscal period
        # alone, and that twin is in another unit, so it does not hold the quarter: the sync makes the
        # batch's own Q2 row current again.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_calendar_payload(), tag))
        db.query(FinancialFact).filter_by(company_id=company.id, concept="revenue", period_end=date(2024, 6, 30),
                                          fiscal_period="Q2").one().is_latest = False
        filing = Filing(company_id=company.id, accession_number=f"Q2-24A{tag}", filing_type="10-Q/A",
                        filing_date=datetime(2025, 4, 1, tzinfo=timezone.utc),
                        document_url="https://example.com/d", sec_url="https://example.com/s")
        db.add(filing)
        db.commit()
        svc.upsert_facts_bulk(db, [{**_fact_dict(company.id, fp=None, end=date(2024, 6, 30), unit="EUR", value=280.0,
                                                  accession=filing.accession_number, source="edgar_xbrl"),
                                    "filing_id": filing.id}])

        _checked_sync(db, company, _suffixed(_calendar_payload(), tag))
        rows = db.query(FinancialFact).filter_by(company_id=company.id, concept="revenue",
                                                 period_end=date(2024, 6, 30)).all()
        assert sorted((r.fiscal_period or "", r.unit, r.accession.removesuffix(tag), r.is_latest) for r in rows) == [
            ("", "EUR", "Q2-24A", True), ("Q2", "USD", "Q2-24", True)]
        db.close()

    def test_a_filing_companyfacts_names_only_under_ifrs_full_is_not_taken_for_a_newer_one(self):
        # A US-GAAP filer that later reports under IFRS, in EUR: companyfacts names that 20-F only
        # under ifrs-full, which the collector does not read. The per-filing writer stored its EUR
        # FY2023 revenue (a Filing row dated 2025-03-01, after every us-gaap item). The payload names
        # the filing, so its rows are not those of a filing companyfacts does not show yet: the sync
        # demotes the EUR row beside the USD one, as any row in another currency.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        payload = _suffixed(_payload({REV_TAG: {"units": {"USD": [
            _item(800.0, "2022-12-31", start="2022-01-01", accn="K22", fy=2022, filed="2023-02-15"),
            _item(1000.0, "2023-12-31", start="2023-01-01", accn="K23", fy=2023, filed="2024-02-15"),
        ]}}}), tag)
        payload["facts"]["ifrs-full"] = {"Revenue": {"units": {"EUR": [
            _item(900.0, end, start=start, accn=f"IFRS24{tag}", form="20-F", filed="2025-03-01")
            for start, end in (("2023-01-01", "2023-12-31"), ("2024-01-01", "2024-12-31"))]}}}
        filing = Filing(company_id=company.id, accession_number=f"IFRS24{tag}", filing_type="20-F",
                        filing_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
                        document_url="https://example.com/d", sec_url="https://example.com/s")
        db.add(filing)
        db.commit()
        svc.upsert_facts_bulk(db, [{**_fact_dict(company.id, unit="EUR", value=900.0, accession=filing.accession_number,
                                                  source="edgar_xbrl"), "filing_id": filing.id}])

        result = _checked_sync(db, company, payload, final=True)
        rows = db.query(FinancialFact).filter_by(company_id=company.id, concept="revenue",
                                                 period_end=date(2023, 12, 31)).all()
        assert sorted((r.unit, r.accession.removesuffix(tag), r.is_latest) for r in rows) == [
            ("EUR", "IFRS24", False), ("USD", "K23", True)]
        assert (result["inserted"], result["demoted"]) == (2, 1)
        db.close()

    @pytest.mark.parametrize("seeded, known", [
        (_switched_to_usd_payload, {}),
        (lambda: _switched_to_usd_payload(switched=False), {"20F-2023": date(2023, 7, 21)}),
        (lambda: _switched_to_usd_payload(switched=False), {"20F-2023": date(2025, 8, 1)}),
    ], ids=["main-after-the-switch", "usd-lists-before-the-switch-with-a-known-filing",
            "usd-lists-before-the-switch-with-a-known-filing-dated-after-the-payload"])
    def test_a_switch_to_usd_demotes_the_convenience_rows_earlier_syncs_stored(self, seeded, known):
        # Earlier syncs stored each CNY 20-F's USD convenience year under that 20-F's accession:
        # main kept the USD list after a switch, and before #1365 every sync read the USD lists
        # only. Those rows are in the series currency, but their filings report in CNY, so the
        # sync demotes them. FY2022, which the USD report does not present, is then a gap, not
        # 20F-2022's translation at 6.34 (FY2023 growth -7.8% where the filer reported +1.8%).
        # With 20F-2023 stored locally and 20F-2025 not, the upsert keeps 20F-2023's FY2023 figures
        # current and stores the restated ones behind them; the sync demotes 20F-2023's and
        # promotes the restated rows in their place. The last case dates that Filing row after the
        # payload's newest filing (a state built by hand: a Filing row takes SEC's filing date, the
        # one companyfacts reports). The payload names 20F-2023, so none of its rows is protected.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact
        from app.services import trend_analysis_service

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        for accession, filed in known.items():
            db.add(Filing(company_id=company.id, accession_number=f"{accession}{tag}", filing_type="20-F",
                          filing_date=datetime.combine(filed, datetime.min.time(), tzinfo=timezone.utc),
                          document_url="https://example.com/d", sec_url="https://example.com/s"))
        db.commit()
        svc.upsert_facts_bulk(db, svc.normalize_companyfacts(company.id, _usd_lists(_suffixed(seeded(), tag)))[0])
        convenience = {f"20F-{fy}{tag}" for fy in (2022, 2023, 2024)}
        seeded_rows = {r.id for r in db.query(FinancialFact).filter_by(company_id=company.id)
                       if r.is_latest and r.accession in convenience and r.unit != "pure"}
        assert seeded_rows

        result = _checked_sync(db, company, _suffixed(_switched_to_usd_payload(), tag), final=True)
        rows = db.query(FinancialFact).filter_by(company_id=company.id).all()
        current = [r for r in rows if r.is_latest]
        keys = [(r.concept, r.period_end, r.fiscal_period) for r in current]
        assert len(keys) == len(set(keys))  # one current row per key
        assert [r for r in current if r.accession in convenience and r.unit != "pure"] == []
        assert {r.id for r in rows} >= seeded_rows  # demoted, never deleted
        assert sorted((r.period_end.year, r.unit, r.accession.removesuffix(tag)) for r in current
                      if (r.concept, r.fiscal_period) == ("revenue", "FY")) == [
            (year, "USD", "20F-2025") for year in (2023, 2024, 2025)]
        if not known:  # main's reading already held 20F-2025's rows: the sync only demotes
            assert (result["inserted"], result["demoted"]) == (0, len(seeded_rows))

        dataset = trend_analysis_service.build_dataset(db, company, "annual", "FY2022", "FY2025")
        series = next(s for s in dataset["series"] if s["concept"] == "revenue")
        assert series["unit"] == "USD"
        assert [p["value"] for p in series["points"]][0] is None
        assert [p["value"] for p in series["points"]][1:] == pytest.approx(
            [_CNY_REVENUE[1] / 7, _CNY_REVENUE[2] / 7, _CNY_REVENUE[2] / 7 * 1.05])
        db.close()

    @pytest.mark.parametrize("payload, stored_unit, synced_unit, synced_first", [
        (_switched_to_usd_payload, "CNY", "USD", False),
        (lambda: _switched_to_usd_payload(switched=False), "USD", "CNY", False),
        (lambda: _switched_to_usd_payload(switched=False), "USD", "CNY", True),
    ], ids=["usd-series-demotes-a-cny-row", "cny-series-demotes-a-usd-row", "cny-series-demotes-a-usd-row-stored-after-it"])
    def test_a_sync_demotes_a_filing_owned_row_in_another_currency_and_leaves_other_concepts(
        self, payload, stored_unit, synced_unit, synced_first,
    ):
        # The per-filing writer stored 20F-2024's FY2024 revenue in the other currency (opening the
        # old filing after a switch, or a per-concept tie), with a filing_id: the sync demotes it
        # whatever its source or filing. Its gross profit, a concept the payload does not carry, is
        # left alone. Where an earlier sync stored the payload's own row under 20F-2024 first, the row
        # the sync makes current is that one, in its unit, never the other unit's row of that filing.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        if synced_first:
            _checked_sync(db, company, _suffixed(payload(), tag), final=True)
        filing = Filing(company_id=company.id, accession_number=f"20F-2024{tag}", filing_type="20-F",
                        filing_date=datetime(2024, 7, 22, tzinfo=timezone.utc),
                        document_url="https://example.com/d", sec_url="https://example.com/s")
        db.add(filing)
        db.commit()
        owned = {"source": "edgar_xbrl", "filing_id": filing.id}
        svc.upsert_facts_bulk(db, [
            {**_fact_dict(company.id, concept, end=date(2024, 3, 31), unit=stored_unit, accession=filing.accession_number,
                          value=value), **owned}
            for concept, value in (("revenue", 882_000e6), ("gross_profit", 330_000e6))])

        _checked_sync(db, company, _suffixed(payload(), tag), final=True)
        rows = db.query(FinancialFact).filter_by(company_id=company.id, period_end=date(2024, 3, 31),
                                                 fiscal_period="FY").all()

        def current(concept):
            return sorted((r.unit, r.source) for r in rows if r.concept == concept and r.is_latest)

        assert current("revenue") == [(synced_unit, "companyfacts")]
        assert current("gross_profit") == [(stored_unit, "edgar_xbrl")]
        db.close()

    def test_a_usd_filers_per_share_row_in_another_currency_runs_the_currency_step(self):
        # A USD filer whose per-filing writer read its FY2024 diluted EPS in EUR/shares (a stray per-concept pick)
        # beside the USD/shares figure companyfacts carries. A stored per-share row in another currency involves
        # another currency as an amount row does, so the sync runs the currency step and demotes it; counting amount
        # units alone left it current beside the USD EPS, two currencies at one period.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _store_filing_rows(db, company, f"K24{tag}", "10-K", "2025-02-15", [
            ("eps_diluted", "EUR/shares", date(2024, 12, 31), 1.1)])
        _checked_sync(db, company, _suffixed(_lagging_usd_payload(fresh=True), tag), final=True, usd_only=False)
        assert sorted((r.unit, r.is_latest) for r in db.query(FinancialFact).filter_by(
            company_id=company.id, concept="eps_diluted", period_end=date(2024, 12, 31))) == [
            ("EUR/shares", False), ("USD/shares", True)]
        db.close()

    @pytest.mark.parametrize("filing", ["its-usd-10-ks", "a-10-q-of-its-own"])
    def test_a_usd_series_carrying_a_list_in_another_currency_involves_it_only_where_a_filing_reads_it(self, filing):
        # A USD filer whose payload also tags net income in EUR. Inside its USD 10-Ks (every period again, so main's
        # per-concept pick read the EUR list), each 10-K reads USD, more of its amount items being in USD: no filing
        # reads another currency and no row is stored in one, so the sync is main's, its EUR list notwithstanding.
        # In a 10-Q of its own (Q1-25), that 10-Q reads EUR (``PayloadView.own``), so the sync involves another
        # currency and runs the currency step. Either way the series reads USD and the 10-Q's item is not read.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        payload = _lagging_usd_payload(fresh=True)
        units = payload["facts"]["us-gaap"]["NetIncomeLoss"]["units"]
        units["EUR"] = [{**item, "val": item["val"] * 0.9} for item in units["USD"]] if filing == "its-usd-10-ks" else [
            _item(27.0, "2025-03-31", start="2025-01-01", accn="Q1-25", fy=2025, fp="Q1", form="10-Q", filed="2025-05-05")]
        _checked_sync(db, company, _suffixed(payload, tag), final=True, usd_only=filing == "its-usd-10-ks")
        assert sorted((r.period_end.year, r.unit, r.accession.removesuffix(tag)) for r in db.query(FinancialFact)
                      .filter_by(company_id=company.id, concept="net_income", is_latest=True)) == [
            (2022, "USD", "K22"), (2023, "USD", "K24"), (2024, "USD", "K24")]
        db.close()

    def test_a_usd_filers_row_in_another_currency_of_a_concept_outside_the_batch_leaves_its_sync_mains(self):
        # A USD filer whose per-filing writer stored FY2024 gross profit in EUR, a concept its companyfacts payload
        # does not carry. The currency step reads, votes on and demotes the batch's concepts only, so a row of
        # another concept gives it nothing to correct: the gate reads the stored units of the batch's concepts
        # alone, the sync is main's, and the EUR row stays current.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _store_filing_rows(db, company, f"K24{tag}", "10-K", "2025-02-15", [
            ("gross_profit", "EUR", date(2024, 12, 31), 330.0)])
        _checked_sync(db, company, _suffixed(_lagging_usd_payload(fresh=True), tag), final=True, usd_only=True)
        assert [(r.unit, r.is_latest) for r in db.query(FinancialFact).filter_by(
            company_id=company.id, concept="gross_profit")] == [("EUR", True)]
        db.close()

    @pytest.mark.parametrize("involved", [False, True], ids=["usd-only", "a-stored-eur-row"])
    def test_a_usd_series_leaves_a_legacy_derived_ratio_current_as_usd_derived(self, involved):
        # A net margin stored before operands were recorded (no provenance), derived and with no
        # filing owner, was computed from the USD lists. In a USD series it is no other-currency
        # ratio: where a known filing date keeps it current, the batch's own margin stays behind it. A sync in
        # USD alone is main's; with a stored EUR row (not current) the currency step runs, with the same result.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        payload = _calendar_payload()
        payload["facts"]["us-gaap"]["NetIncomeLoss"] = {"units": {"USD": [
            _item(100.0, "2023-12-31", start="2023-01-01", accn="K23", fy=2023, filed="2024-02-15")]}}
        payload = _suffixed(payload, tag)
        db.add(Filing(company_id=company.id, accession_number=f"K23A{tag}", filing_type="10-K/A",
                      filing_date=datetime(2024, 3, 1, tzinfo=timezone.utc),
                      document_url="https://example.com/d", sec_url="https://example.com/s"))
        db.commit()
        legacy = {**_fact_dict(company.id, "net_margin", unit="pure", accession=f"K23A{tag}", value=9.5,
                               source="derived"), "provenance": None}
        svc.upsert_facts_bulk(db, [legacy])
        if involved:
            svc.upsert_facts_bulk(db, [_fact_dict(company.id, end=date(2022, 12, 31), unit="EUR", value=700.0,
                                                  accession=f"EUR22{tag}", source="edgar_xbrl")])
            db.query(FinancialFact).filter_by(company_id=company.id, unit="EUR").one().is_latest = False
            db.commit()

        result = _checked_sync(db, company, payload, usd_only=not involved)
        margins = db.query(FinancialFact).filter_by(company_id=company.id, concept="net_margin",
                                                    period_end=date(2023, 12, 31)).all()
        assert sorted((r.accession.removesuffix(tag), r.is_latest) for r in margins) == [("K23", False), ("K23A", True)]
        assert result["demoted"] == 0
        db.close()

    @pytest.mark.parametrize("currency", ["USD", "CNY"])
    def test_a_quarantined_winner_leaves_the_row_current_beside_it_as_found(self, currency):
        # A filer in USD (main's sync), or in CNY, synced through K24 (FY2024 revenue 1200). The journaled repair
        # quarantined the row its 10-K/A (K24A, 1300) has under the payload's identity, a rolled-back insert, stored
        # not current. The sync naming K24A skips that identity and never promotes it, so it leaves FY2024 as found:
        # K24's 1200 stays current, never a gap, as the repair's rollback left it.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        _checked_sync(db, company, _suffixed(_in_currency(_lagging_usd_payload(fresh=True), currency), tag), final=True)
        amended = _suffixed(_in_currency(_with_amendment(_lagging_usd_payload(fresh=True)), currency), tag)
        svc.upsert_facts_bulk(db, [
            {**f, "provenance": {**f["provenance"], "validation": "unavailable", "reasons": ["repair_rolled_back"]}}
            for f in svc.normalize_companyfacts(company.id, amended)[0]
            if f["accession"] == f"K24A{tag}" and f["concept"] == "revenue"])
        for row in db.query(FinancialFact).filter_by(company_id=company.id, accession=f"K24A{tag}"):
            row.is_latest = False
        db.query(FinancialFact).filter_by(company_id=company.id, accession=f"K24{tag}", concept="revenue",
                                          period_end=date(2024, 12, 31)).one().is_latest = True
        db.commit()
        _checked_sync(db, company, amended, final=True, usd_only=currency == "USD")
        assert sorted((float(r.value), r.accession.removesuffix(tag), r.is_latest) for r in db.query(FinancialFact).filter_by(
            company_id=company.id, concept="revenue", period_end=date(2024, 12, 31))) == [
            (1200.0, "K24", True), (1300.0, "K24A", False)]
        db.close()

    @pytest.mark.parametrize("reason", ["repair_rolled_back", "legacy_period_label_mismatch"])
    def test_a_sync_never_promotes_a_row_the_repair_quarantined(self, reason):
        # The journaled repair quarantined two rows under the USD 20-F's identities, FY2023 revenue
        # and net margin: rows it had inserted and then rolled back, which only a reviewed
        # reapplication restores, or rows it withheld for another reason. They are stored not current
        # and unavailable. The switch sync skips both identities. It demotes the CNY revenue and finds
        # the key empty, and it would replace the CNY-derived margin a known filing date kept current,
        # but it promotes neither quarantined row: FY2023 revenue is a gap, whatever the reason.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        db.add(Filing(company_id=company.id, accession_number=f"20F-2024{tag}", filing_type="20-F",
                      filing_date=datetime(2024, 7, 22, tzinfo=timezone.utc),
                      document_url="https://example.com/d", sec_url="https://example.com/s"))
        db.commit()
        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag), final=True)
        fy2023 = (date(2023, 3, 31), "FY")
        rolled_back = [
            {**f, "provenance": {**f["provenance"], "validation": "unavailable", "reasons": [reason]}}
            for f in svc.normalize_companyfacts(company.id, _suffixed(_switched_to_usd_payload(), tag))[0]
            if f["concept"] in ("revenue", "net_margin") and (f["period_end"], f["fiscal_period"]) == fy2023]
        assert len(rolled_back) == 2
        svc.upsert_facts_bulk(db, rolled_back)
        quarantined = db.query(FinancialFact).filter_by(company_id=company.id, accession=f"20F-2025{tag}").all()
        for row in quarantined:
            row.is_latest = False
        db.commit()

        _checked_sync(db, company, _suffixed(_switched_to_usd_payload(), tag), final=True)
        rows = db.query(FinancialFact).filter_by(company_id=company.id, period_end=fy2023[0], fiscal_period="FY").all()
        assert sorted((r.concept, r.unit, r.accession.removesuffix(tag)) for r in rows
                      if r.is_latest and r.concept in ("revenue", "net_margin")) == [("net_margin", "pure", "20F-2024")]
        assert not any(r.is_latest for r in quarantined)
        db.close()

    @pytest.mark.parametrize("shape", ["k24a-amendment", "k24a-quarantined", "older-payload", "derived-fcf",
                                       "same-day-stale", "held-keys"])
    def test_a_usd_only_sync_is_mains(self, shape):
        # The USD-only corpus: the shapes the tests above pin for a filer in CNY, run for a filer in USD alone, every
        # order and with Filing rows and without, amounts, per-share rows and ratios. Each sync goes through
        # ``_checked_sync(usd_only=True)``, which asserts main's contract for it: the upsert protects no row, and the
        # currency step demotes none and touches none. These end states are therefore main's, its convergence
        # defects on USD filers included (the follow-up in tasks/todo.md): an amendment the per-filing writer stored
        # behind its original's companyfacts row stays behind (K24's 1200, or K24B's 1250 where a lagging payload
        # inserted it), and a lagging payload's K23 1000 replaces K24's 1050 for good where K24 has no Filing row.
        # The tag migration, the unlabelled twins, the quarantined winner and the legacy ratio run in USD through
        # their own parameter; the hand-built two-current state of the ratio test is no state a writer leaves.
        from app.database import SessionLocal

        db = SessionLocal()

        def run(scenario):
            company = _new_company(db)
            return scenario(company, f"-{uuid.uuid4().hex[:8]}")

        def k24a(order):  # test_a_non_usd_filers_newest_amendment_..., in USD
            def scenario(company, tag):
                def lagging(k24b=False):
                    payload = _lagging_usd_payload(fresh=True)
                    if k24b:
                        payload["facts"]["us-gaap"][REV_TAG]["units"]["USD"].append(_item(
                            1250.0, "2024-12-31", start="2024-01-01", accn="K24B", fy=2024, form="10-K/A", filed="2025-03-01"))
                    return payload

                _checked_sync(db, company, _suffixed(lagging(), tag), final=True, usd_only=True)
                _store_per_filing(db, company, _suffixed(_with_amendment(lagging()), tag), f"K24A{tag}", "10-K/A",
                                  "2025-04-01", writer=svc.upsert_facts)
                if order == "behind-both":
                    _store_per_filing(db, company, _suffixed(lagging(k24b=True), tag), f"K24B{tag}", "10-K/A",
                                      "2025-03-01", writer=svc.upsert_facts)
                if order != "fresh-only":
                    _checked_sync(db, company, _suffixed(lagging(k24b=order == "naming-k24b"), tag), usd_only=True)
                fresh = _with_amendment(lagging(k24b=order != "fresh-only" and order != "lagging"))
                _checked_sync(db, company, _suffixed(fresh, tag), final=True, usd_only=True)
                return _current_fy(db, company, tag, ("eps_diluted", "revenue"), 2024)
            return scenario

        if shape == "k24a-amendment":
            k24 = [("eps_diluted", "K24", 1.2), ("revenue", "K24", 1200.0)]
            assert {order: run(k24a(order)) for order in ("fresh-only", "lagging", "naming-k24b", "behind-both")} == {
                "fresh-only": k24, "lagging": k24, "naming-k24b": [("eps_diluted", "K24", 1.2), ("revenue", "K24B", 1250.0)],
                "behind-both": k24}
        elif shape == "k24a-quarantined":  # test_a_lagging_sync_never_leaves_its_own_row_current_..., in USD
            def quarantined(company, tag):
                from app.models import FinancialFact

                _checked_sync(db, company, _suffixed(_lagging_usd_payload(fresh=True), tag), final=True, usd_only=True)
                _store_per_filing(db, company, _suffixed(_with_amendment(_lagging_usd_payload(fresh=True)), tag),
                                  f"K24A{tag}", "10-K/A", "2025-04-01", writer=svc.upsert_facts)
                row = db.query(FinancialFact).filter_by(company_id=company.id, accession=f"K24A{tag}", concept="revenue").one()
                row.provenance = {**row.provenance, "validation": "unavailable", "reasons": ["repair_rolled_back"]}
                db.commit()
                lagging = _lagging_usd_payload(fresh=True)
                lagging["facts"]["us-gaap"][REV_TAG]["units"]["USD"].append(_item(
                    1250.0, "2024-12-31", start="2024-01-01", accn="K24B", fy=2024, form="10-K/A", filed="2025-03-01"))
                _checked_sync(db, company, _suffixed(lagging, tag), usd_only=True)
                return _current_fy(db, company, tag, ("revenue",), 2024)

            assert run(quarantined) == [("revenue", "K24B", 1250.0)]
        elif shape == "older-payload":  # test_a_same_currency_payload_older_than_a_stored_filing_..., in USD
            def older(newer_rows):
                def scenario(company, tag):
                    if newer_rows == "an-earlier-sync":
                        _checked_sync(db, company, _suffixed(_lagging_usd_payload(fresh=True), tag), usd_only=True)
                    else:
                        _store_per_filing(db, company, _suffixed(_lagging_usd_payload(fresh=True), tag), f"K24{tag}",
                                          "10-K", "2025-02-15")
                    _checked_sync(db, company, _suffixed(_lagging_usd_payload(fresh=False), tag), usd_only=True)
                    _checked_sync(db, company, _suffixed(_lagging_usd_payload(fresh=True), tag), final=True, usd_only=True)
                    return _current_fy(db, company, tag, ("revenue",), 2023)
                return scenario

            assert run(older("an-earlier-sync")) == [("revenue", "K23", 1000.0)]
            assert run(older("the-per-filing-writer")) == [("revenue", "K24", 1050.0)]
        elif shape == "derived-fcf":
            for order in ("per-filing-then-sync", "sync-per-filing-then-sync", "sync-per-filing-then-lagging-then-sync"):
                for filing_rows in ("filing-rows", "no-filing-rows"):
                    end = run(lambda company, tag: _fcf_scenario(db, company, tag, "USD", order, filing_rows))
                    assert ("free_cash_flow", "K24", 280.0) in end
        elif shape == "same-day-stale":
            for k24_stored in (True, False):
                for k24a_filing_row in (False, True):
                    _fresh, stale = run(lambda company, tag: _same_day_stale_scenario(
                        db, company, tag, "USD", k24_stored, k24a_filing_row))
                    newest = k24_stored or k24a_filing_row  # main's upsert demotes an undated newer row on insert
                    assert stale == [("revenue", "K24A", 1300.0) if newest else ("revenue", "K24", 1200.0)]
        else:
            for held in ("unpresented", "dated-by-provenance", "same-day-tie", "ratio", "ratio-unpresented"):
                end = run(lambda company, tag: _held_key_scenario(db, company, tag, "USD", held))
                assert [row for row in end if row[0] == "revenue"] == [
                    ("revenue", "K24A", 1300.0) if held == "dated-by-provenance" else ("revenue", "K24", 1200.0)]
        db.close()


def _suffixed(payload, tag):
    """The payload with ``tag`` appended to every accession (accession numbers are unique across companies)."""
    for node in payload["facts"]["us-gaap"].values():
        for item in (item for items in node["units"].values() for item in items):
            item["accn"] += tag
    return payload


def _usd_lists(payload):
    """Only the payload's USD and USD/shares lists: what a sync read before #1365."""
    for node in payload["facts"]["us-gaap"].values():
        node["units"] = {unit: items for unit, items in node["units"].items() if unit in ("USD", "USD/shares")}
    return payload


def _in_currency(payload, currency):
    """The payload with its USD and USD/shares lists relabelled ``currency``: the same filer reporting in it. A
    filer in USD alone is main's (``Guard.usd_only``); in another currency every sync runs the currency step."""
    for node in payload["facts"]["us-gaap"].values():
        node["units"] = {unit.replace("USD", currency, 1): items for unit, items in node["units"].items()}
    return payload


def _lagging_usd_payload(*, fresh):
    """A USD filer's revenue, net income and diluted EPS for FY2022 (K22) and FY2023 (K23, filed
    2024-02-15); when ``fresh``, also its 10-K for FY2024 (K24, filed 2025-02-15), restating FY2023 (revenue
    1050). Without it, the payload lags K24: what SEC's companyfacts returns before it shows that 10-K."""
    lists = {tag: [_item(value, f"{year}-12-31", start=f"{year}-01-01", accn=f"K{year % 100}", fy=year,
                         filed=f"{year + 1}-02-15") for year, value in zip((2022, 2023), values)]
             for tag, values in ((REV_TAG, (800.0, 1000.0)), ("NetIncomeLoss", (80.0, 100.0)),
                                 ("EarningsPerShareDiluted", (0.8, 1.0)))}
    if fresh:
        for tag, values in ((REV_TAG, (1050.0, 1200.0)), ("NetIncomeLoss", (105.0, 120.0)),
                            ("EarningsPerShareDiluted", (1.05, 1.2))):
            lists[tag] += [_item(value, f"{year}-12-31", start=f"{year}-01-01", accn="K24", fy=2024, filed="2025-02-15")
                           for year, value in zip((2023, 2024), values)]
    return _payload({tag: {"units": {"USD/shares" if tag == "EarningsPerShareDiluted" else "USD": items}}
                     for tag, items in lists.items()})


def _with_amendment(payload):
    """The payload naming a 10-K/A (K24A, filed 2025-04-01) that restates FY2024 revenue at 1300."""
    payload["facts"]["us-gaap"][REV_TAG]["units"]["USD"].append(
        _item(1300.0, "2024-12-31", start="2024-01-01", accn="K24A", fy=2024, form="10-K/A", filed="2025-04-01"))
    return payload


def _with_usd_restatement(payload):
    """The payload naming a USD 20-F/A of ``_switched_to_usd_payload``'s switcher (20FA-2025, filed 2025-08-15)
    that restates FY2024 capex at 4.6bn and presents FY2024-25 revenue."""
    usgaap = payload["facts"]["us-gaap"]
    usgaap["PaymentsToAcquirePropertyPlantAndEquipment"]["units"]["USD"].append(
        _item(4.6e9, "2024-03-31", start="2023-04-01", accn="20FA-2025", fy=2025, form="20-F/A", filed="2025-08-15"))
    usgaap[REV_TAG]["units"]["USD"] += [
        _item(value, end, start=start, accn="20FA-2025", fy=2025, form="20-F/A", filed="2025-08-15")
        for end, start, value in (("2024-03-31", "2023-04-01", 118_000e6), ("2025-03-31", "2024-04-01", 124_000e6))]
    return payload


def _usd_quarterly_payload(*, named):
    """A USD filer's revenue and net income for FY2023 (K23), FY2024 (K24) and Q1 2024 (Q1-24, revenue 250), and
    its FY2023 operating cash flow; when ``named``, also its 10-Q for Q1 2025 (Q1-25, filed 2025-05-05): Q1 2025
    revenue 300 with Q1 2024 restated at 260, its net income in USD and again in EUR, so the payload reads Q1-25 in
    USD."""
    def item(value, end, start, accn, *, fy, fp="FY", form="10-K", filed):
        return _item(value, end, start=start, accn=accn, fy=fy, fp=fp, form=form, filed=filed)

    revenue = [item(1000.0, "2023-12-31", "2023-01-01", "K23", fy=2023, filed="2024-02-15"),
               item(1100.0, "2024-12-31", "2024-01-01", "K24", fy=2024, filed="2025-02-15"),
               item(250.0, "2024-03-31", "2024-01-01", "Q1-24", fy=2024, fp="Q1", form="10-Q", filed="2024-05-05")]
    net_income = [item(value / 10, end, start, accn, fy=fy, fp=fp, form=form, filed=filed)
                  for value, end, start, accn, fy, fp, form, filed in (
                      (1000.0, "2023-12-31", "2023-01-01", "K23", 2023, "FY", "10-K", "2024-02-15"),
                      (1100.0, "2024-12-31", "2024-01-01", "K24", 2024, "FY", "10-K", "2025-02-15"),
                      (250.0, "2024-03-31", "2024-01-01", "Q1-24", 2024, "Q1", "10-Q", "2024-05-05"))]
    eur = []
    if named:
        for end, start, value in (("2024-03-31", "2024-01-01", 260.0), ("2025-03-31", "2025-01-01", 300.0)):
            q1 = {"start": start, "accn": "Q1-25", "fy": 2025, "fp": "Q1", "form": "10-Q", "filed": "2025-05-05"}
            revenue.append(item(value, end, **q1))
            net_income.append(item(value / 10, end, **q1))
            eur.append(item(value / 10 * 0.9, end, **q1))
    return _payload({REV_TAG: {"units": {"USD": revenue}},
                     "NetIncomeLoss": {"units": {"USD": net_income, **({"EUR": eur} if eur else {})}},
                     "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [
                         item(150.0, "2023-12-31", "2023-01-01", "K23", fy=2023, filed="2024-02-15")]}}})


def _new_filing(db, company, accession, form, filed, period_end=None):
    """A Filing row of type ``form`` dated ``filed`` (ISO)."""
    from app.models import Filing

    filing = Filing(company_id=company.id, accession_number=accession, filing_type=form, period_end_date=period_end,
                    filing_date=datetime.fromisoformat(filed).replace(tzinfo=timezone.utc),
                    document_url="https://example.com/d", sec_url="https://example.com/s")
    db.add(filing)
    db.commit()
    return filing


def _per_filing_10k(db, company, accession, form, filed, currency, concepts):
    """Store, as the post-summary hook's per-filing writer does (``process_filing_facts``, its own rule), a 10-K's
    ``concepts`` ({concept: (tag, ((year, value), ...))}, calendar years) in ``currency`` under a Filing row."""
    standardized = {"reporting_currency": currency, **{concept: {"series": [
        {"period": f"{year}-12-31", "period_start": f"{year}-01-01", "value": value, "currency": currency,
         "raw_tag": f"us-gaap:{tag}" if tag else None, "form": form} for year, value in points],
        "current": None} for concept, (tag, points) in concepts.items()}}
    for concept in concepts:
        standardized[concept]["current"] = standardized[concept]["series"][-1]
    svc.process_filing_facts(db, _new_filing(db, company, accession, form, filed, date(2024, 12, 31)),
                             standardized=standardized)


def _current_fy(db, company, tag, concepts, year):
    """The current rows of ``concepts`` for calendar ``year``'s fiscal year, each as (concept, accession, value)."""
    from app.models import FinancialFact

    return sorted((r.concept, r.accession.removesuffix(tag), round(float(r.value), 2)) for r in db.query(
        FinancialFact).filter(FinancialFact.company_id == company.id, FinancialFact.concept.in_(concepts),
                              FinancialFact.period_end == date(year, 12, 31), FinancialFact.fiscal_period == "FY",
                              FinancialFact.is_latest.is_(True)))


_OCF_CONTINUING = "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"
_CASH_FLOWS = ("operating_cash_flow", "capital_expenditures", "free_cash_flow")


def _fcf_scenario(db, company, tag, currency, order, older):
    """A filer in ``currency`` whose FY2024 10-K (K24, filed 2025-02-15) recasts FY2023 operating cash flow (500 to
    480) under the continuing-operations element only, a lower-priority tag. The batch's FY2023 cash flow is K23's
    500 (the first tag with data), its capex K24's 200 (same tag, latest filed), so its free cash flow is 300 under
    K23's accession with K24's date as its provenance filed_at (the later operand). The per-filing writer stores
    K24's own FY2023 figures (480, 200, 280). ``older`` "filing-rows" gives K23 a Filing row. Runs ``order`` and
    returns the current FY2023 cash flows after the last of two syncs naming K24."""
    usd_only = currency == "USD"

    def items(values, accession, fiscal_year, filed):
        return [_item(value, f"{year}-12-31", start=f"{year}-01-01", accn=accession, fy=fiscal_year, filed=filed)
                for year, value in values]

    def payload(*, k24):
        capex = items(((2022, 150.0), (2023, 200.0)), "K23", 2023, "2024-02-15")
        usgaap = {"NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": items(
            ((2022, 400.0), (2023, 500.0)), "K23", 2023, "2024-02-15")}},
            "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": capex}}}
        if k24:
            usgaap[_OCF_CONTINUING] = {"units": {"USD": items(((2023, 480.0), (2024, 600.0)), "K24", 2024, "2025-02-15")}}
            capex += items(((2023, 200.0), (2024, 250.0)), "K24", 2024, "2025-02-15")
        return _suffixed(_in_currency(_payload(usgaap), currency), tag)

    if older == "filing-rows":
        _new_filing(db, company, f"K23{tag}", "10-K", "2024-02-15")
    if order != "per-filing-then-sync":
        _checked_sync(db, company, payload(k24=False), final=True, usd_only=usd_only)
    _per_filing_10k(db, company, f"K24{tag}", "10-K", "2025-02-15", currency, {
        "operating_cash_flow": (_OCF_CONTINUING, ((2023, 480.0), (2024, 600.0))),
        "capital_expenditures": ("PaymentsToAcquirePropertyPlantAndEquipment", ((2023, 200.0), (2024, 250.0))),
        "free_cash_flow": ("", ((2023, 280.0), (2024, 350.0)))})
    if "lagging" in order:
        _checked_sync(db, company, payload(k24=False), usd_only=usd_only)
    for _sync in range(2):
        _checked_sync(db, company, payload(k24=True), final=True, usd_only=usd_only)
    return _current_fy(db, company, tag, _CASH_FLOWS, 2023)


def _same_day_stale_scenario(db, company, tag, currency, k24_stored, k24a_filing_row, concepts=("revenue",)):
    """A filer in ``currency``. K24A (a 10-K/A filed 2025-05-05) restates FY2024 revenue at 1300 over K24's 1200 and
    is current, a companyfacts row (with a Filing row where ``k24a_filing_row``); where ``k24_stored`` an earlier sync
    stored K24's FY2024 identity. Then a stale payload whose newest filing is a 10-Q filed that same day (Q1-25) does
    not name K24A. Returns the current FY2024 rows of ``concepts`` after the fresh sync and after the stale one."""
    usd_only = currency == "USD"

    def payload(*, k24a):
        data = _lagging_usd_payload(fresh=True)
        usd = data["facts"]["us-gaap"][REV_TAG]["units"]["USD"]
        if k24a:
            usd.append(_item(1300.0, "2024-12-31", start="2024-01-01", accn="K24A", fy=2024, form="10-K/A", filed="2025-05-05"))
        usd.append(_item(300.0, "2025-03-31", start="2025-01-01", accn="Q1-25", fy=2025, fp="Q1", form="10-Q",
                         filed="2025-05-05"))
        return _suffixed(_in_currency(data, currency), tag)

    if k24a_filing_row:
        _new_filing(db, company, f"K24A{tag}", "10-K/A", "2025-05-05")
    if k24_stored:
        _checked_sync(db, company, _suffixed(_in_currency(_lagging_usd_payload(fresh=True), currency), tag), final=True,
                      usd_only=usd_only)
    _checked_sync(db, company, payload(k24a=True), final=True, usd_only=usd_only)
    fresh = _current_fy(db, company, tag, concepts, 2024)
    _checked_sync(db, company, payload(k24a=False), usd_only=usd_only)
    return fresh, _current_fy(db, company, tag, concepts, 2024)


def _held_key_scenario(db, company, tag, currency, shape):
    """A filer in ``currency`` synced through K24 (FY2024 revenue 1200, net income 120), then rows of filings a later
    payload does not name, which it protects, behind or beside K24's at FY2024. ``shape``: "unpresented" (the
    per-filing writer stores K24A's 1300, filed 2025-04-01, behind K24's undated row; the stale payload names K22 and
    K23 only, so FY2024 is not presented), "dated-by-provenance" (the fresh sync names K24A, a companyfacts row dated
    only by its provenance, and the per-filing writer stores K24's own row, Filing 2025-02-15, behind it), "same-day-
    tie" (two 10-K/As filed 2025-04-01, K24B's 1310 then K24A's 1300, both stored behind K24's row; a lagging payload
    names K24), "ratio" and "ratio-unpresented" (the per-filing writer stores K24's rows, margin 10.0, under its Filing
    row; the fresh sync names K25, filed 2026-02-15 with no Filing row, restating FY2024 at 1210 and 130, so its 10.74
    margin is stored behind K24's; then a payload without K25, or with K23 only). Returns the current FY2024 revenue,
    net income and net margin after the last sync."""
    usd_only = currency == "USD"

    def cur(payload):
        return _suffixed(_in_currency(payload, currency), tag)

    def amended(accession, value):
        data = _lagging_usd_payload(fresh=True)
        data["facts"]["us-gaap"][REV_TAG]["units"]["USD"].append(_item(
            value, "2024-12-31", start="2024-01-01", accn=accession, fy=2024, form="10-K/A", filed="2025-04-01"))
        return data

    def with_k25(*, k25, k23_only=False):  # each 10-K's year and its comparative: K23, K24 and, with k25, K25
        filings = (2023,) if k23_only else (2023, 2024, 2025) if k25 else (2023, 2024)
        values = {REV_TAG: {2023: (800.0, 1000.0), 2024: (1000.0, 1200.0), 2025: (1210.0, 1400.0)},
                  "NetIncomeLoss": {2023: (80.0, 100.0), 2024: (100.0, 120.0), 2025: (130.0, 150.0)}}
        return cur(_payload({name: {"units": {"USD": [
            _item(value, f"{year}-12-31", start=f"{year}-01-01", accn=f"K{fy % 100}", fy=fy, filed=f"{fy + 1}-02-15")
            for fy in filings for year, value in zip((fy - 1, fy), by_filing[fy])]}} for name, by_filing in values.items()}))

    if shape.startswith("ratio"):
        _per_filing_10k(db, company, f"K24{tag}", "10-K", "2025-02-15", currency, {
            "revenue": (REV_TAG, ((2023, 1000.0), (2024, 1200.0))), "net_income": ("NetIncomeLoss", ((2023, 100.0), (2024, 120.0))),
            "net_margin": ("", ((2023, 10.0), (2024, 10.0)))})
        _checked_sync(db, company, with_k25(k25=True), final=True, usd_only=usd_only)
        _checked_sync(db, company, with_k25(k25=False, k23_only=shape.endswith("unpresented")), usd_only=usd_only)
    elif shape == "dated-by-provenance":
        _checked_sync(db, company, cur(amended("K24A", 1300.0)), final=True, usd_only=usd_only)
        _store_per_filing(db, company, cur(_lagging_usd_payload(fresh=True)), f"K24{tag}", "10-K", "2025-02-15",
                          writer=svc.upsert_facts)
        _checked_sync(db, company, cur(_lagging_usd_payload(fresh=False)), usd_only=usd_only)
    else:
        _checked_sync(db, company, cur(_lagging_usd_payload(fresh=True)), final=True, usd_only=usd_only)
        for accession, value in (("K24B", 1310.0), ("K24A", 1300.0)) if shape == "same-day-tie" else (("K24A", 1300.0),):
            _store_per_filing(db, company, cur(amended(accession, value)), f"{accession}{tag}", "10-K/A", "2025-04-01",
                              writer=svc.upsert_facts)
        _checked_sync(db, company, cur(_lagging_usd_payload(fresh=shape == "same-day-tie")), usd_only=usd_only)
    return _current_fy(db, company, tag, ("net_income", "net_margin", "revenue"), 2024)


def _store_filing_rows(db, company, accession, form, filed, rows, fp="FY"):
    """Store ``rows`` ((concept, unit, period_end, value) at ``fp``) as the per-filing writer does, under a Filing of
    type ``form`` dated ``filed``, through the bulk writer's rule."""
    from app.models import Filing

    filing = Filing(company_id=company.id, accession_number=accession, filing_type=form,
                    filing_date=datetime.fromisoformat(filed).replace(tzinfo=timezone.utc),
                    document_url="https://example.com/d", sec_url="https://example.com/s")
    db.add(filing)
    db.commit()
    svc.upsert_facts_bulk(db, [{**_fact_dict(company.id, concept, fp=fp, end=end, unit=unit, value=value,
                                              accession=accession, source="edgar_xbrl"),
                                "filing_id": filing.id, "form": form} for concept, unit, end, value in rows])


def _untagged(rows, tag):
    """``_current_rows``' rows with ``tag`` stripped from each accession, so two companies' states compare."""
    return {(*row[:4], row[4].removesuffix(tag)) for row in rows}


def _store_per_filing(db, company, payload, accession, form, filed, edit=lambda fact: fact, writer=None):
    """Store, as the per-filing writer does, the rows ``payload`` normalizes under ``accession``, each passed
    through ``edit`` (None drops it): filing_id set, a Filing row of type ``form`` dated ``filed``, no filed_at
    of their own, through the bulk writer's rule unless ``writer`` is given. Either keeps is_latest per unit.
    Returns the Filing."""
    from app.models import Filing

    filing = Filing(company_id=company.id, accession_number=accession, filing_type=form,
                    filing_date=datetime.fromisoformat(filed).replace(tzinfo=timezone.utc),
                    document_url="https://example.com/d", sec_url="https://example.com/s")
    db.add(filing)
    db.commit()
    rows = (edit({**f, "source": "edgar_xbrl", "filing_id": filing.id, "provenance": {**f["provenance"], "filed_at": None}})
            for f in svc.normalize_companyfacts(company.id, payload)[0] if f["accession"] == accession)
    (writer or svc.upsert_facts_bulk)(db, [row for row in rows if row is not None])
    return filing


def _current_rows(db, company_id):
    """The company's current rows, each as (concept, period_end, fiscal_period, unit, accession)."""
    from app.models import FinancialFact

    return {(r.concept, r.period_end, r.fiscal_period, r.unit, r.accession)
            for r in db.query(FinancialFact).filter_by(company_id=company_id, is_latest=True)}


def _one_currency_per_concept(db, company_id):
    """Assert that no concept's current amount or per-share rows span two currencies, at any periods: a
    growth figure across them would compare one currency with another."""
    from app.models import FinancialFact
    from app.services.facts.currency import is_amount_unit

    spans = {}
    for row in db.query(FinancialFact).filter_by(company_id=company_id, is_latest=True):
        if is_amount_unit(row.unit.partition("/")[0]):
            spans.setdefault(row.concept, set()).add(row.unit.partition("/")[0])
    assert {concept: sorted(units) for concept, units in spans.items() if len(units) > 1} == {}


def _checked_sync(db, company, payload, *, final=False, usd_only=None):
    """Persist ``payload`` and check the sync's invariants, whatever earlier syncs or the per-filing writer left.
    No key holds two current amount or per-share rows, so never two currencies (``_current_amount_units``). A sync
    that involves no currency but USD (``Guard.usd_only``; ``usd_only`` asserts which a sync is) is main's: the
    upsert protects no row, and the currency step demotes none and touches none (every row's is_latest, pending
    inserts included, is the same after it as before). Otherwise, outside a proven switch, which stores and
    promotes nothing, in an amount or per-share unit: a key where a protected row sits (``currency.protected_rows``,
    read before the sync), current or not, presented or not, holds the newest protected row there (latest filed,
    then the higher accession, then by id) as its one current such row; each other key the batch presents holds the
    batch's own row (its winner's unit and accession, so in the series currency), unless a row of a filing filed
    strictly after the winner's own filing (each by its Filing row's date, else its filing's ``filed`` in the
    payload, else its provenance ``filed_at``), in the winner's unit and under a filing not ``_foreign`` to the
    series, was current before the sync: that row stays current. There, and where the row to make current is
    quarantined or a quarter's unlabelled twin in its unit is current, the key is left as found (no row current
    there that was not current before). ``final``, a sync whose payload names every stored filing (checked), also
    proves no switch and leaves no key to a protected row."""
    from unittest import mock

    from app.models import Filing, FinancialFact
    from app.services.facts import ingest
    from app.services.facts.concepts import _is_financial_sic
    from app.services.facts.currency import _foreign, payload_view, protected_rows

    facts = svc.normalize_companyfacts(company.id, payload, financial_sic=_is_financial_sic(company.sic))[0]
    view = payload_view(payload)
    guard = protected_rows(db, facts, view)
    assert usd_only is None or guard.usd_only == usd_only
    stored = {accession for (accession,) in db.query(FinancialFact.accession).filter_by(company_id=company.id)}
    assert not final or stored <= view.known  # a final sync's payload names every stored filing
    before = _amount_rows(db, company.id)
    seen = {}

    def upsert(session, batch, **kwargs):
        seen["protected"] = kwargs["protected"]
        return real_upsert(session, batch, **kwargs)

    def step(session, batch, payload_view_, sync_guard):
        rows = [*session.query(FinancialFact).filter_by(company_id=company.id),
                *(row for row in session.new if isinstance(row, FinancialFact))]
        was = [(row, row.is_latest) for row in rows]
        seen["demoted"] = real_step(session, batch, payload_view_, sync_guard)
        seen["touched"] = [row.id for row, latest in was if row.is_latest != latest] + [
            row for row in session.new if isinstance(row, FinancialFact) and row not in rows]
        return seen["demoted"]

    real_upsert, real_step = ingest.upsert_facts_bulk, ingest.demote_convenience_rows
    with mock.patch.object(ingest, "upsert_facts_bulk", upsert), mock.patch.object(ingest, "demote_convenience_rows", step):
        result = svc._persist_companyfacts_payload(db, company, payload)
    _current_amount_units(db, company.id)
    if guard.usd_only:  # main's: the upsert's call as main made it, and a currency step that changes nothing
        assert (seen["protected"], seen["demoted"], seen["touched"]) == (frozenset(), 0, [])
        return result
    assert not (final and guard.switch)  # a payload naming every stored filing proves no switch
    if guard.switch is None:
        after = _amount_rows(db, company.id)
        dates = {accession: stamp.isoformat()[:10] for accession, stamp in db.query(
            Filing.accession_number, Filing.filing_date).filter_by(company_id=company.id) if stamp is not None}

        def filed(accession, filed_at):
            return dates.get(accession) or view.filed.get(accession) or str(filed_at or "")[:10]

        held = {}
        for key, rows in after.items():
            for row in sorted((row for row in rows if row[3] in guard.ids),
                              key=lambda row: (filed(row[1], row[5]), row[1], row[3])):
                held[key] = row
        assert not (final and held)  # nor leaves a key to a protected row
        twins = {(*key[:2], row[0]) for key, rows in after.items() if key[2] is None for row in rows if row[2]}
        winners = {(f["concept"], f["period_end"], f["fiscal_period"]): (f["unit"], f["accession"], filed(
            f["accession"], None)) for f in facts if _is_amount(f["unit"]) and f["fiscal_period"]}
        wrong = {}
        for key in {*winners, *held}:
            found = [row[:2] for row in after.get(key, ()) if row[2]]
            kept = {row[:2] for row in before.get(key, ()) if row[2]}
            pick = held.get(key) or next(row for row in after[key] if row[:2] == winners[key][:2])
            newer = [] if key in held else [
                row[:2] for row in before.get(key, ()) if row[2] and row[0] == winners[key][0]
                and filed(row[1], row[5]) > winners[key][2] and not _foreign(row[1], view.currency, view, guard.own)]
            if newer or pick[4] or key[2] in ("Q1", "Q2", "Q3", "Q4") and (*key[:2], pick[0]) in twins:
                if not set(found) <= kept:
                    wrong[key] = ("left as found", found, sorted(kept))
            elif found != [pick[:2]]:
                wrong[key] = ("the newest protected row" if key in held else "the batch's own row", found, pick[:2])
            if set(newer) - set(found):
                wrong[key] = ("a newer filing's current row yielded", sorted(set(newer) - set(found)))
        assert wrong == {}
    return result


def _is_amount(unit):
    from app.services.facts.currency import is_amount_unit

    return is_amount_unit(unit.partition("/")[0])


def _amount_rows(db, company_id):
    """The company's amount and per-share rows by key (concept, period_end, fiscal_period), each as (unit,
    accession, is_latest, id, quarantined, provenance filed_at)."""
    from app.models import FinancialFact

    rows = {}
    for row in db.query(FinancialFact).filter_by(company_id=company_id):
        if _is_amount(row.unit):
            provenance = row.provenance if isinstance(row.provenance, dict) else {}
            rows.setdefault((row.concept, row.period_end, row.fiscal_period), []).append(
                (row.unit, row.accession, bool(row.is_latest), row.id, provenance.get("validation") == "unavailable",
                 provenance.get("filed_at")))
    return rows


def _current_amount_units(db, company_id):
    """The currency of each current amount or per-share row, by key (concept, period_end,
    fiscal_period), after asserting that no key holds two."""
    from app.models import FinancialFact
    from app.services.facts.currency import is_amount_unit

    held = {}
    for row in db.query(FinancialFact).filter_by(company_id=company_id, is_latest=True):
        if row.fiscal_period is not None and is_amount_unit(row.unit.partition("/")[0]):
            held.setdefault((row.concept, row.period_end, row.fiscal_period), []).append(row.unit.partition("/")[0])
    assert {key: units for key, units in held.items() if len(units) > 1} == {}
    return held
