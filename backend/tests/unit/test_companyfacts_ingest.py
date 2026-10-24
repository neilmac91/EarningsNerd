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


def _with_later_usd_quarter(payload):
    """A USD 6-K filed after the CNY 20-Fs, its quarter and the comparative one (two period-ends)."""
    payload["facts"]["us-gaap"][REV_TAG]["units"]["USD"].extend(_QUARTER_WITH_COMPARATIVE)
    return payload


def _with_older_year_cny_amendment(payload):
    """A CNY 20-F/A restating FY2023-24 revenue, filed after the USD 20-F for FY2025."""
    payload["facts"]["us-gaap"][REV_TAG]["units"]["CNY"].extend(
        _item(value * 1.01, end, start=start, accn="20FA-2024", fy=2024, form="20-F/A", filed="2025-09-01")
        for (_fy, start, end, _rate), value in zip(_CNY_YEARS[1:], _CNY_REVENUE[1:]))
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
        # tag or unit: a shares item under a tag no concept reads still names its filing.
        from app.services.facts.currency import PayloadView, companyfacts_currencies, payload_view

        payload = _switched_to_usd_payload()
        payload["facts"]["us-gaap"]["SomeShareCount"] = {"units": {"shares": [
            _item(5.0, "2025-06-30", accn="6K-2026Q1", form="6-K", filed="2025-08-30")]}}
        view = payload_view(payload)
        assert view[:2] == companyfacts_currencies(payload["facts"]["us-gaap"])
        assert view == PayloadView("USD", frozenset({"20F-2022", "20F-2023", "20F-2024"}),
                                   frozenset({"20F-2022", "20F-2023", "20F-2024", "20F-2025", "6K-2026Q1"}),
                                   "2025-08-30")
        assert payload_view({"facts": {}}) == PayloadView("USD", frozenset(), frozenset(), "")


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

        result = svc._persist_companyfacts_payload(db, fpi, _cny_payload())
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
        again = svc._persist_companyfacts_payload(db, fpi, _cny_payload())
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

        svc._persist_companyfacts_payload(db, fpi, payload())
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

        again = svc._persist_companyfacts_payload(db, fpi, payload())
        assert (again["inserted"], again["demoted"]) == (0, 0)
        usd_filer = _new_company(db)  # ratios from USD operands are the upsert's alone
        assert svc._persist_companyfacts_payload(db, usd_filer, payload(("USD", "USD/shares")))["demoted"] == 0
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
        svc._persist_companyfacts_payload(db, fpi, payload)
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

        first = svc._persist_companyfacts_payload(db, fpi, _cny_payload())
        before = stored()
        second = svc._persist_companyfacts_payload(db, fpi, _with_stray_usd_amendment(_cny_payload()))
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
        svc._persist_companyfacts_payload(db, company, _switched_to_usd_payload(switched=False))
        native = {r.id for r in db.query(FinancialFact).filter_by(company_id=company.id) if r.unit.startswith("CNY")}
        result = svc._persist_companyfacts_payload(db, company, _switched_to_usd_payload())
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

        again = svc._persist_companyfacts_payload(db, company, _switched_to_usd_payload())
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
        svc._persist_companyfacts_payload(db, company, payload(switched=False))
        svc._persist_companyfacts_payload(db, company, payload())
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

    def test_a_stale_payload_after_a_switch_changes_nothing_and_a_fresh_one_finds_the_series_whole(self):
        # CNY 20-Fs, the USD 20-F for FY2025, then the pre-switch payload again (a delayed SEC
        # response, or another process's older fetch), then the current one. The stale payload's
        # newest filing is 20F-2024 (filed 2024-07-22) and it does not name 20F-2025 (filed
        # 2025-07-23), so its sync demotes none of 20F-2025's rows, ratios included, and the fresh
        # sync finds the series as the first USD sync left it. Without that, the stale sync demoted
        # every USD row, FY2025 too, and the fresh one, whose identities were all stored, restored none.
        from app.database import SessionLocal
        from app.models import FinancialFact

        db = SessionLocal()
        company = _new_company(db)

        def current():
            rows = [r for r in db.query(FinancialFact).filter_by(company_id=company.id) if r.is_latest]
            revenue = sorted((r.period_end.year, r.unit, r.accession) for r in rows
                             if (r.concept, r.fiscal_period) == ("revenue", "FY"))
            return revenue, sorted({r.unit for r in rows}), sorted(r.id for r in rows)

        svc._persist_companyfacts_payload(db, company, _switched_to_usd_payload(switched=False))
        svc._persist_companyfacts_payload(db, company, _switched_to_usd_payload())
        switched = current()
        assert switched[:2] == ([(year, "USD", "20F-2025") for year in (2023, 2024, 2025)],
                                ["USD", "USD/shares", "pure"])
        stale = svc._persist_companyfacts_payload(db, company, _switched_to_usd_payload(switched=False))
        assert (stale["inserted"], stale["demoted"]) == (0, 0)
        assert current() == switched
        fresh = svc._persist_companyfacts_payload(db, company, _switched_to_usd_payload())
        assert (fresh["inserted"], fresh["demoted"]) == (0, 0)
        assert current() == switched
        db.close()

    def test_a_sync_before_companyfacts_shows_a_new_filing_never_demotes_that_filings_own_rows(self):
        # A CNY-synced company files its first USD 20-F, and the per-filing writer stores that
        # filing's rows (filing_id set, a Filing row dated 2025-07-23, no filed_at of their own).
        # The new Filing lets the next coverage request bypass the sync TTL, but SEC's companyfacts
        # does not show the filing yet: the payload is the CNY one, newest filed 2024-07-22. Its
        # sync demotes none of the new filing's rows, its USD-derived margins included; the sync
        # that names 20F-2025 then reads the series in USD.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"  # accession numbers are unique across companies
        svc._persist_companyfacts_payload(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        filing = Filing(company_id=company.id, accession_number=f"20F-2025{tag}", filing_type="20-F",
                        filing_date=datetime(2025, 7, 23, tzinfo=timezone.utc),
                        document_url="https://example.com/d", sec_url="https://example.com/s")
        db.add(filing)
        db.commit()
        own = [{**f, "source": "edgar_xbrl", "filing_id": filing.id, "provenance": {**f["provenance"], "filed_at": None}}
               for f in svc.normalize_companyfacts(company.id, _suffixed(_switched_to_usd_payload(), tag))[0]
               if f["accession"] == filing.accession_number]
        svc.upsert_facts_bulk(db, own)
        ids = {r.id for r in db.query(FinancialFact).filter_by(filing_id=filing.id)}
        assert {r.unit for r in db.query(FinancialFact).filter(FinancialFact.id.in_(ids))} == {
            "USD", "USD/shares", "pure"}

        stale = svc._persist_companyfacts_payload(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        assert (stale["inserted"], stale["demoted"]) == (0, 0)
        assert all(r.is_latest for r in db.query(FinancialFact).filter(FinancialFact.id.in_(ids)))

        svc._persist_companyfacts_payload(db, company, _suffixed(_switched_to_usd_payload(), tag))
        current = [r for r in db.query(FinancialFact).filter_by(company_id=company.id) if r.is_latest]
        assert {r.unit for r in current} == {"USD", "USD/shares", "pure"}
        assert ids <= {r.id for r in current}
        db.close()

    @pytest.mark.parametrize("seeded, known", [
        (_switched_to_usd_payload, ()),
        (lambda: _switched_to_usd_payload(switched=False), ("20F-2023",)),
    ], ids=["main-after-the-switch", "usd-lists-before-the-switch-with-a-known-filing"])
    def test_a_switch_to_usd_demotes_the_convenience_rows_earlier_syncs_stored(self, seeded, known):
        # Earlier syncs stored each CNY 20-F's USD convenience year under that 20-F's accession:
        # main kept the USD list after a switch, and before #1365 every sync read the USD lists
        # only. Those rows are in the series currency, but their filings report in CNY, so the
        # sync demotes them. FY2022, which the USD report does not present, is then a gap, not
        # 20F-2022's translation at 6.34 (FY2023 growth -7.8% where the filer reported +1.8%).
        # With 20F-2023 stored locally and 20F-2025 not, the upsert keeps 20F-2023's FY2023 figures
        # current and stores the restated ones behind them; the sync demotes 20F-2023's and
        # promotes the restated rows in their place.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact
        from app.services import trend_analysis_service

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        for accession in known:
            db.add(Filing(company_id=company.id, accession_number=f"{accession}{tag}", filing_type="20-F",
                          filing_date=datetime(2023, 7, 21, tzinfo=timezone.utc),
                          document_url="https://example.com/d", sec_url="https://example.com/s"))
        db.commit()
        svc.upsert_facts_bulk(db, svc.normalize_companyfacts(company.id, _usd_lists(_suffixed(seeded(), tag)))[0])
        convenience = {f"20F-{fy}{tag}" for fy in (2022, 2023, 2024)}
        seeded_rows = {r.id for r in db.query(FinancialFact).filter_by(company_id=company.id)
                       if r.is_latest and r.accession in convenience and r.unit != "pure"}
        assert seeded_rows

        result = svc._persist_companyfacts_payload(db, company, _suffixed(_switched_to_usd_payload(), tag))
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

    @pytest.mark.parametrize("payload, stored_unit, synced_unit", [
        (_switched_to_usd_payload, "CNY", "USD"),
        (lambda: _switched_to_usd_payload(switched=False), "USD", "CNY"),
    ], ids=["usd-series-demotes-a-cny-row", "cny-series-demotes-a-usd-row"])
    def test_a_sync_demotes_a_filing_owned_row_in_another_currency_and_leaves_other_concepts(
        self, payload, stored_unit, synced_unit,
    ):
        # The per-filing writer stored 20F-2024's FY2024 revenue in the other currency (opening the
        # old filing after a switch, or a per-concept tie), with a filing_id: the sync demotes it
        # whatever its source or filing. Its gross profit, a concept the payload does not carry, is
        # left alone.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
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

        svc._persist_companyfacts_payload(db, company, _suffixed(payload(), tag))
        rows = db.query(FinancialFact).filter_by(company_id=company.id, period_end=date(2024, 3, 31),
                                                 fiscal_period="FY").all()

        def current(concept):
            return sorted((r.unit, r.source) for r in rows if r.concept == concept and r.is_latest)

        assert current("revenue") == [(synced_unit, "companyfacts")]
        assert current("gross_profit") == [(stored_unit, "edgar_xbrl")]
        db.close()

    def test_a_usd_series_leaves_a_legacy_derived_ratio_current_as_usd_derived(self):
        # A net margin stored before operands were recorded (no provenance), derived and with no
        # filing owner, was computed from the USD lists. In a USD series it is no other-currency
        # ratio: where a known filing date keeps it current, the batch's own margin stays behind it.
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

        result = svc._persist_companyfacts_payload(db, company, payload)
        margins = db.query(FinancialFact).filter_by(company_id=company.id, concept="net_margin",
                                                    period_end=date(2023, 12, 31)).all()
        assert sorted((r.accession.removesuffix(tag), r.is_latest) for r in margins) == [("K23", False), ("K23A", True)]
        assert result["demoted"] == 0
        db.close()

    def test_a_sync_never_promotes_a_row_the_repair_quarantined(self):
        # The journaled repair rolled back two rows it had inserted under the USD 20-F's identities,
        # FY2023 revenue and net margin, so they are stored not current and unavailable; only a
        # reviewed reapplication restores one. The switch sync skips both identities. It demotes the
        # CNY revenue and finds the key empty, and it would replace the CNY-derived margin a known
        # filing date kept current, but it promotes neither quarantined row: FY2023 revenue is a gap.
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        tag = f"-{uuid.uuid4().hex[:8]}"
        db.add(Filing(company_id=company.id, accession_number=f"20F-2024{tag}", filing_type="20-F",
                      filing_date=datetime(2024, 7, 22, tzinfo=timezone.utc),
                      document_url="https://example.com/d", sec_url="https://example.com/s"))
        db.commit()
        svc._persist_companyfacts_payload(db, company, _suffixed(_switched_to_usd_payload(switched=False), tag))
        fy2023 = (date(2023, 3, 31), "FY")
        rolled_back = [
            {**f, "provenance": {**f["provenance"], "validation": "unavailable", "reasons": ["repair_rolled_back"]}}
            for f in svc.normalize_companyfacts(company.id, _suffixed(_switched_to_usd_payload(), tag))[0]
            if f["concept"] in ("revenue", "net_margin") and (f["period_end"], f["fiscal_period"]) == fy2023]
        assert len(rolled_back) == 2
        svc.upsert_facts_bulk(db, rolled_back)
        quarantined = db.query(FinancialFact).filter_by(company_id=company.id, accession=f"20F-2025{tag}").all()
        for row in quarantined:
            row.is_latest = False
        db.commit()

        svc._persist_companyfacts_payload(db, company, _suffixed(_switched_to_usd_payload(), tag))
        rows = db.query(FinancialFact).filter_by(company_id=company.id, period_end=fy2023[0], fiscal_period="FY").all()
        assert sorted((r.concept, r.unit, r.accession.removesuffix(tag)) for r in rows
                      if r.is_latest and r.concept in ("revenue", "net_margin")) == [("net_margin", "pure", "20F-2024")]
        assert not any(r.is_latest for r in quarantined)
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
