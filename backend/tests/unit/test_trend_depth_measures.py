"""The depth harness's §3 measures and the auditor's view (evals/trend_depth/{report,semantics}.py, DEEPSEEK-ERRORS.md §3
"Measures" and fix 14) over stub run records, version 1 (no ``pipeline``) and version 2 (``pipeline: "v2"``).

Pins: passes without a model repair, first-try gate errors (a version-2 record's raw first-pass gate; a version-1
record's first pass under the gate now), own-ID omissions and retypes, mislabels per 1,000 verified claims (probe hits
plus Opus's substantive flags, each counted once), unsigned falls, the calibration measures, broken net cash (cited
withheld or broken-year figures, stated or disclosed), cause support from Opus's audit, form, the old gate's
continuity score, the several-run summary (every run, its range and the runs pooled), and that a version-1 run reports
its shared fields as before. And the auditor's view 2: signed values, a bound, identical-valued twins, its version
marker, and the redo of an audit made under view 1.

The stages are imported over a stub bootstrap whose records, pack directories included, live in ``tmp_path``, as in
``test_trend_depth_stages.py`` (whose fixture is copied here), so the real bootstrap never loads and no model is called.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from evals.trend_depth.providers import CallResult
from evals.trend_depth.records import output_sha256

STAGES = ("generate", "judge", "causes", "semantics", "report")
LABEL, TICKER = "test", "T"
SECTIONS = ("arc", "drivers", "margins", "cash", "balance_sheet", "red_flags", "watch")


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    stub = types.ModuleType("evals.trend_depth.bootstrap")
    stub.RECORDS = tmp_path
    stub.BACKEND = Path(__file__).resolve().parents[2]
    stub.PRODUCTION_MODEL = "stub"
    monkeypatch.setitem(sys.modules, "evals.trend_depth.bootstrap", stub)
    for name in (*STAGES, "gold"):
        monkeypatch.delitem(sys.modules, f"evals.trend_depth.{name}", raising=False)
    stages = types.SimpleNamespace(**{name: importlib.import_module(f"evals.trend_depth.{name}") for name in STAGES})

    async def no_call(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("this test sends no model call")

    for module in (stages.judge, stages.causes, stages.generate):
        monkeypatch.setattr(module, "call", no_call)
    monkeypatch.setattr(stages.generate, "PROMPT_DRAFT", "")  # a TREND_DEPTH_PROMPT in the shell changes nothing here
    monkeypatch.setattr(stages.report, "eval_companies", lambda split=None: [types.SimpleNamespace(ticker=TICKER)])
    yield stages
    for name in [n for n in sys.modules if n.split(".")[-1] in (*STAGES, "gold") and n.startswith("evals.trend_depth.")]:
        del sys.modules[name]  # the next test imports them afresh, over its own records


def _write(path: Path, record: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record))


NET_CASH = "Net cash (cash and investments less debt)"
ROWS = (  # (id, label, period, value, unit, series): DUK's net debt and COP's revenue CAGR as recorded in their packs
    ("D14", NET_CASH, "FY2016", -49_990_000_000.0, "usd", "net_cash"),
    ("D352", NET_CASH, "FY2025", -89_591_000_000.0, "usd", "net_cash"),
    ("D353", "Net cash % of revenue", "FY2025", -282.3, "pct", "net_cash_to_revenue"),
    ("F8", "Revenue", "FY2023", 48_522_000_000.0, "usd", "revenue"),
    ("D274", "Revenue growth", "FY2023", -20.519582630346115, "pct", "g:revenue"),
    ("D844", "Revenue 3-year CAGR", "FY2022..FY2025", -5.314358606609759, "pct", "cagr3:revenue"),
    ("D1", "Revenue growth", "FY2025", 5.667, "pct", "g:revenue"),
    ("F10", "Revenue", "FY2025", 31_700_000_000.0, "usd", "revenue"),
)


def _pack(**extra: Any) -> dict[str, Any]:
    return {"split": "dev", "profile": "p", "window": "FY2016..FY2025", "snapshot_id": "s1",
            "values": {r[0]: {"id": r[0], "label": r[1], "period": r[2], "value": r[3], "unit": r[4]} for r in ROWS},
            "series_keys": {f"{r[5]}|{r[2]}": r[0] for r in ROWS},
            "passages": [{"id": "P1", "fiscal_year": "FY2025", "text": "Revenue rose on higher retail prices."}],
            "red_flags": [{"id": "R3", "evidence": ["D352"], "detail": "Net debt rose 9 years in a row."}],
            "data_checks": [], **extra}


def _packs(harness: Any, v2: dict[str, Any] | None = None) -> None:
    """packs/ without a debt break; packs-v2/ naming FY2025's debt line broken and withholding net cash built on it."""
    records = harness.generate.RUNS.parent
    _write(records / "packs" / f"{TICKER}.json", _pack())
    _write(records / "packs-v2" / f"{TICKER}.json", v2 or _pack(
        data_checks=[{"kind": "debt_break", "period": "FY2025", "detail": "Long-term debt not reported after FY2024."}],
        withheld={"D352": "debt_break", "D353": "debt_break", "R3": "debt_break"}))


DEBT = "Net debt has deepened for nine straight years, from -$50.0 billion to -$89.6 billion [D14][D352][R3]."
CAGR = "Revenue then fell 20.5% in FY2023 on lower realized prices, and the three years to FY2025 show a 5.3% CAGR [F8][D274][D844]."
GREW = "Revenue grew 5.7% to $31.7 billion in FY2025 [D1][F10]."
BOUND = "Revenue growth stayed below 10% in FY2025 [D1]."


def _output(*, red_flags: tuple = (DEBT,), extra: dict[str, list] | None = None) -> dict[str, Any]:
    sentences: dict[str, list] = {
        "arc": [("fact", CAGR)],
        "drivers": [("comparison", GREW), ("cause", "Revenue rose on higher retail prices [P1]."), ("comparison", BOUND)],
        "margins": [("comparison", "Revenue growth of 5.7% leaves little room for error in FY2025 [D1].")],
        "cash": [("fact", "Revenue was $31.7 billion in FY2025 [F10].")],
        "balance_sheet": [("fact", "Revenue was $31.7 billion in FY2025 [F10].")],
        "red_flags": [("comparison", text) for text in red_flags] + [("judgement", "That pace is a sign of strain.")],
        "watch": [("comparison", "Free cash flow margin will likely remain under the window low in the FY2026 10-K."),
                  ("comparison", "A fall below 5.7% revenue growth would confirm the slowdown [D1].")],
        **(extra or {}),
    }
    return {"sections": [{"key": key, "title": key, "sentences": [{"type": t, "text": x} for t, x in sentences[key]]}
                         for key in SECTIONS]}


def _attempt(index: Any, raw: Any, problems: tuple = ()) -> dict[str, Any]:
    return {"attempt": index, "backend": "openai_compat", "input_tokens": 1000, "cached_input_tokens": 0, "output_tokens": 100,
            "latency_s": 9.0, "cost_usd": 0.001, "problems": list(problems), "raw": raw if isinstance(raw, str) else json.dumps(raw)}


REPAIRED = [_attempt(0, "{}"), _attempt("repair", "{}")]
FAILED_FIRST = {"passed": False, "claims": 10, "verified": 9, "failed_claims": 1, "failures": []}


def _record(harness: Any, system: str = "deepseek-flash", label: str = LABEL, **fields: Any) -> dict[str, Any]:
    output = fields.pop("output", None) or _output()
    record = {"ticker": TICKER, "arm": system, "generation_ok": True, "split": "dev", "output": output, "words": 100,
              "gate": {"passed": True, "claims": 10, "verified": 10, "failed_claims": 0, "failures": []},
              "attempts": [_attempt(0, output)], "usage": {"input_tokens": 1000, "output_tokens": 100}, "latency_s": 9.0,
              "cost_usd": 0.001, **fields}
    _write(harness.generate.RUNS / label / system / f"{TICKER}.json", record)
    return record


def _measures(harness: Any, records: list[dict[str, Any]], system: str = "deepseek-flash", old_gate: Any = None) -> dict[str, Any]:
    report = harness.report
    return report.arm_measures(LABEL, system, records, report.arm_stats(records), old_gate)


# --- Version-1 records ------------------------------------------------------------------------------------------------

def test_a_version_1_record_is_measured_from_its_first_pass_under_the_gate_now(harness: Any) -> None:
    _packs(harness)
    first = _output(red_flags=(DEBT, "Revenue was $99.0 billion in FY2025 [F10]."))  # a figure the cited value does not match
    repaired = _record(harness, first_pass_output=first, first_pass_gate=FAILED_FIRST, attempts=REPAIRED)
    m = _measures(harness, [repaired])
    assert m["pipeline_v2"] == 0 and m["passes_without_repair"] == 0 and m["repairs"] == {"version 1": 1}
    assert m["first_try_basis"] == {"gate now": 1}
    assert [f["failure"] for f in m["first_try_failures"]] == ["'$99.0 billion' matches nothing the sentence cites"]
    assert m["own_id_omissions"] == 0 and m["autocite_added"] == [] and m["retyped"] == []
    unrepaired = _record(harness)
    m = _measures(harness, [unrepaired])
    assert m["passes_without_repair"] == 1 and m["first_try_errors"] == 0  # its one output is its first try


def test_a_version_1_run_reports_its_shared_fields_as_before(harness: Any) -> None:
    _packs(harness)
    record = _record(harness)
    summary = harness.report.summarise(LABEL, ["deepseek-flash"], None)
    block = summary["splits"]["all"]
    assert block["arms"]["deepseek-flash"] == harness.report.arm_stats([record])  # the measures are added beside, never mixed in
    assert set(block) == {"companies", "arms", "judge", "causes", "semantics", "measures"}
    rows = {name: shown for name, _, shown, *_ in harness.report.measure_rows(block["measures"]["deepseek-flash"])}
    assert rows["Own-ID omissions per analysis (IDs the code added)"] == "—"  # a version-1 record has none to count
    assert "Passes without a model repair" in harness.report.render(LABEL, ["deepseek-flash"], summary)


# --- Version-2 records ------------------------------------------------------------------------------------------------

def _v2(harness: Any, **fields: Any) -> dict[str, Any]:
    return _record(harness, "deepseek-flash-c", pipeline="v2", **fields)


def test_version_2_records_count_passes_raw_first_try_errors_omissions_and_retypes(harness: Any) -> None:
    _packs(harness)
    raw_gate = {"passed": False, "claims": 10, "verified": 8, "failed_claims": 2,
                "failures": [{"section": "red_flags", "sentence": DEBT, "failure": "'1.7' matches nothing the sentence cites"},
                             {"section": "drivers", "sentence": GREW, "failure": "cause sentence cites no filing passage"}]}
    fixed = _v2(harness, raw_first_pass_gate=raw_gate,
                autocite={"added": [{"section": "red_flags", "sentence": DEBT, "claim": "$1.7 billion", "id": "D355"}], "rejected": 2},
                retyped=[{"section": "drivers", "sentence": GREW, "from": "cause", "to": "comparison"}])
    clean = {**fixed, "raw_first_pass_gate": {"passed": True, "failures": []}, "autocite": {"added": [], "rejected": 0}, "retyped": []}
    patched = {**clean, "repair_kind": "patch", "first_pass_gate": raw_gate,
               "attempts": [*fixed["attempts"], _attempt("repair", "{}")]}
    m = _measures(harness, [fixed, clean, patched], "deepseek-flash-c")
    assert m["pipeline_v2"] == 3 and m["passes_without_repair"] == 2 and m["code_fixed_passes"] == 1
    assert m["repairs"] == {"patch": 1}
    assert m["first_try_basis"] == {"raw_first_pass_gate": 3} and m["first_try_errors"] == 2  # the recorded raw gate, not the gate now
    assert m["own_id_omissions"] == 1 and m["autocite_rejected"] == 2
    assert m["autocite_added"] == [{"ticker": TICKER, "section": "red_flags", "sentence": DEBT, "claim": "$1.7 billion", "id": "D355"}]
    assert [r["to"] for r in m["retyped"]] == ["comparison"]
    rows = {name: shown for name, _, shown, *_ in harness.report.measure_rows(m)}
    assert rows["Own-ID omissions per analysis (IDs the code added)"] == "0.33 (1 in 3; 2 rejected)"
    assert rows["Real first-try gate errors per analysis (subtract gate artefacts by hand)"] == "0.67 (2 in 3)"


def test_the_old_gate_scores_the_model_s_own_first_output(harness: Any) -> None:
    """A version-2 first pass carries the code's fixes, so the old gate reads the first reply in the attempts."""
    _packs(harness)
    raw = _output(red_flags=("RAW",))
    fixed = _output(red_flags=("FIXED",))
    seen: list[str] = []

    class Gate:
        @staticmethod
        def check(sentences: list, pack: dict) -> dict:
            texts = [s["text"] for s in sentences if s["section"] == "red_flags"]
            seen.append(texts[0])
            return {"passed": texts[0] != "RAW"}

    record = _v2(harness, output=fixed, first_pass_output=fixed, raw_first_pass_gate=FAILED_FIRST,
                 attempts=[_attempt(0, "nonsense", ("not JSON",)), _attempt(1, raw)])
    m = _measures(harness, [record], "deepseek-flash-c", ("abc1234", Gate))
    assert seen == ["RAW", "FIXED"] and m["old_gate"] == {"commit": "abc1234", "first_try": 0, "final": 1}
    v1 = _record(harness, output=fixed, first_pass_output=raw, first_pass_gate=FAILED_FIRST,
                 attempts=[_attempt(0, fixed), _attempt("repair", "{}")])
    seen.clear()
    _measures(harness, [v1], "deepseek-flash", ("abc1234", Gate))
    assert seen == ["RAW", "FIXED"]  # a version-1 record's first pass is its own


# --- Mislabels, unsigned falls, calibration, form ---------------------------------------------------------------------

def _semantic_audit(harness: Any, record: dict[str, Any], folder: str, auditor: str, items: list, **fields: Any) -> None:
    _write(harness.generate.RUNS / LABEL / folder / record["arm"] / f"{TICKER}.json",
           {"auditor": auditor, "output_sha256": output_sha256(record), "items": items, **fields})


def _item(sentence: str, claim: str, label: str = "mismatch") -> dict[str, str]:
    from evals.trend_depth.factcheck import CITATION_RE

    return {"sentence": CITATION_RE.sub("", sentence).strip(), "claim": claim, "match": "m", "label": label, "reason": "r"}


def test_mislabels_are_probe_hits_plus_opus_substantive_flags_each_claim_once(harness: Any) -> None:
    _packs(harness)
    record = _record(harness)
    _semantic_audit(harness, record, "semantics-by-claude-opus-5-5", "claude-opus-5-5", [
        _item(DEBT, "-$89.6 billion"),  # also a probe hit: one mislabel, both sources named
        _item(GREW, "5.7%"),  # substantive: counted
        _item(BOUND, "10%"),  # a bound the value satisfies: not substantive
        _item(GREW, "$31.7 billion", "consistent"),
    ], view=2)
    _semantic_audit(harness, record, "semantics", "deepseek-v4-pro", [_item(GREW, "$31.7 billion")])  # not Opus: not counted
    m = _measures(harness, [record])
    assert m["probe_mislabels"] == 3 and m["opus_substantive"] == 2 and m["opus_audited"] == 1 and m["opus_views"] == {"2": 1}
    sources = sorted((h["claim"], h["source"]) for h in m["mislabel_list"])
    assert sources == [("-$50.0 billion", "probe R2a"), ("-$89.6 billion", "probe R2a + claude-opus-5-5 (view 2)"),
                       ("5.3%", "probe U1"), ("5.7%", "claude-opus-5-5 (view 2)")]
    assert m["mislabels"] == 4 and m["verified_claims"] > 0
    shown = {name: s for name, _, s, *_ in harness.report.measure_rows(m)}
    per_1000 = 4 / m["verified_claims"] * 1000
    assert shown["Mislabels per 1,000 verified claims: probes plus Opus substantive flags"].startswith(f"{per_1000:.1f} (4 in ")
    assert [h["claim"] for h in m["unsigned_falls"]] == ["5.3%"] and m["logic_slips"] == []


def test_an_opus_audit_in_the_default_folder_counts_once_and_a_stale_one_not_at_all(harness: Any) -> None:
    _packs(harness)
    record = _record(harness)
    _semantic_audit(harness, record, "semantics", "deepseek-v4-pro", [_item(GREW, "5.7%")])  # another auditor's: not counted
    assert (_measures(harness, [record])["opus_audited"], _measures(harness, [record])["opus_substantive"]) == (0, 0)
    _semantic_audit(harness, record, "semantics", "claude-opus-5-5", [_item(GREW, "5.7%")])  # deepseek-flash's default auditor
    assert _measures(harness, [record])["opus_substantive"] == 1
    _semantic_audit(harness, record, "semantics-by-claude-opus-5-5", "claude-opus-5-5", [_item(GREW, "5.7%")])  # the same audit copied
    assert _measures(harness, [record])["opus_substantive"] == 1
    for folder in ("semantics", "semantics-by-claude-opus-5-5"):
        _semantic_audit(harness, record, folder, "claude-opus-5-5", [_item(GREW, "5.7%")], output_sha256="an earlier output")
    assert _measures(harness, [record])["opus_audited"] == 0


def test_calibration_form_cause_support_and_cost_flow_into_the_measures(harness: Any) -> None:
    _packs(harness)
    record = _record(harness)
    _write(harness.generate.RUNS / LABEL / "causes" / "deepseek-flash" / f"{TICKER}.json",
           {"auditor": "claude-opus-5-5", "output_sha256": output_sha256(record), "items": [{"label": "supported"}, {"label": "partial"}]})
    m = _measures(harness, [record])
    assert m["judgement_outside_watch"] == [1, 9] and m["evaluative"] == [1, 6] and m["watch_forecasts"] == [1, 2]
    assert [h["words"] for h in m["evaluative_list"]] == [["little room"]]
    assert m["cause_support"] == {"audited": 1, "supported": 1, "partial": 1, "unsupported": 0} and m["causes_per_analysis"] == 1
    assert m["form"]["all_sections"] == 1 and m["form"]["sentences_max"] == 11 and m["form"]["within_target"] == 1
    assert (m["cost_mean"], m["latency_p50"]) == (pytest.approx(0.00021), 9.0)


# --- Broken net cash --------------------------------------------------------------------------------------------------

def test_broken_net_cash_is_a_cited_withheld_figure_stated_without_disclosing_the_break(harness: Any) -> None:
    _packs(harness)
    stated = _measures(harness, [_record(harness)])["broken_net_cash"]
    assert (stated["analyses"], stated["stated_as_fact"], stated["disclosed"]) == (1, 1, 0)
    assert [s["ids"] for s in stated["list"][0]["stated"]] == [["D352", "R3"]]
    disclosed = _output(red_flags=(DEBT, "Long-term debt is not reported after FY2024, so FY2025 net debt is incomplete [D352]."))
    m = _measures(harness, [_record(harness, output=disclosed)])["broken_net_cash"]
    assert (m["stated_as_fact"], m["disclosed"]) == (0, 1) and m["list"][0]["state"] == "disclosed"
    unrelated = _output(red_flags=("Revenue data is missing for FY2016 [F10].",))  # disclosure words on no debt figure
    assert _measures(harness, [_record(harness, output=unrelated)])["broken_net_cash"]["list"][0]["state"] == "silent"


def test_a_pack_without_a_debt_break_is_not_counted_and_one_that_withholds_nothing_uses_its_series(harness: Any) -> None:
    _packs(harness, v2=_pack())  # no debt_break check
    assert _measures(harness, [_record(harness)])["broken_net_cash"]["analyses"] == 0
    bank = _pack(data_checks=[{"kind": "debt_break", "period": "FY2025"}])  # a bank's: a break, nothing withheld
    assert harness.report.broken_ids(bank) == {"D352", "D353"}
    _packs(harness, v2=bank)
    assert _measures(harness, [_record(harness)])["broken_net_cash"]["stated_as_fact"] == 1


# --- Several runs -----------------------------------------------------------------------------------------------------

def test_several_runs_show_every_run_its_range_and_the_runs_pooled(harness: Any, monkeypatch: pytest.MonkeyPatch,
                                                                   capsys: pytest.CaptureFixture) -> None:
    _packs(harness)
    _record(harness, label="run-a")
    _record(harness, label="run-b", attempts=REPAIRED, first_pass_output=_output(), first_pass_gate=FAILED_FIRST)
    monkeypatch.setattr(sys, "argv", ["report", "--labels", "run-a,run-b", "--systems", "deepseek-flash", "--old-gate", "none"])
    harness.report.main()
    text = (harness.generate.RUNS / "run-a+run-b" / "REPORT.md").read_text()
    assert text.rstrip("\n") == capsys.readouterr().out.rstrip("\n")
    row = next(line for line in text.splitlines() if line.startswith("| Passes without a model repair |"))
    assert row == "| Passes without a model repair | at least 85% pooled; no run below 80% | 1 of 1 (100%) | 0 of 1 (0%) | 0%–100% | 50% |"
    unsigned = next(line for line in text.splitlines() if line.startswith("| Unsigned falls (probe U1) |"))
    assert unsigned.endswith("| 1 | 1 | 1–1 | 2 in all |")
    summary = json.loads((harness.generate.RUNS / "run-a+run-b" / "summary.json").read_text())
    assert set(summary["runs"]) == {"run-a", "run-b"} and not (harness.generate.RUNS / "run-a" / "REPORT.md").exists()
    # Pooled over all the runs' analyses, not the mean of the runs' shares: 1 of 1 and 1 of 2 pool to 67%, not 75%.
    assert harness.report._pooled([(1, 1, 100), (1, 2, 100)], harness.report._percent) == "67%"


# --- The auditor's view (fix 14) --------------------------------------------------------------------------------------

def _view_pack() -> dict[str, Any]:
    rows = [("X147", "Share repurchases (cash)", "FY2025", 2_017_400_000.0, "usd", []),
            ("D441", "Buybacks plus dividends", "FY2025", 2_017_400_000.0, "usd", ["X147"]),
            ("F105", "Free cash flow", "FY2025", 3_194_000_000.0, "usd", []),
            ("D442", "Buybacks plus dividends % of free cash flow", "FY2025", 63.166, "pct", ["D441", "F105"]),
            ("D13", "Total debt", "FY2025", 0.0, "usd", []), ("X126", "Asset impairment charges", "FY2025", 0.0, "usd", []),
            ("D1147", "Free cash flow margin: percentile vs peers (n=7)", "FY2025", 42.857, "pctile", []),
            ("D1151", "Net cash % of revenue: percentile vs peers (n=7)", "FY2025", 42.857, "pctile", []),
            ("D352", NET_CASH, "FY2025", -89_591_000_000.0, "usd", []),
            ("D437", "Free cash flow / net income", "FY2025", 0.404, "x", []),
            ("D387", "Free cash flow / net income", "FY2024", 0.446, "x", []),
            ("D443", "Revenue growth minus operating-cost growth", "FY2025", -0.35, "pp", [])]
    return {"values": {r[0]: {"label": r[1], "period": r[2], "value": r[3], "unit": r[4], "inputs": r[5]} for r in rows},
            "passages": [], "red_flags": []}


def test_the_view_shows_signed_values_twins_and_a_calculation_s_result(harness: Any) -> None:
    describe, pack = harness.semantics._describe, _view_pack()
    assert describe("cited", ["D352"], pack) == f"cited: D352 = {NET_CASH}, FY2025, -$89.59 billion"
    assert describe("cited", ["D441"], pack) == ("cited: D441 = Buybacks plus dividends, FY2025, $2.02 billion; "
                                                 "same value as X147 = Share repurchases (cash)")
    assert describe("cited", ["D442"], pack) == ("cited: D442 = Buybacks plus dividends % of free cash flow, FY2025, 63.17%; its input "
                                                 "D441 = Buybacks plus dividends has the same value as X147 = Share repurchases (cash)")
    assert describe("cited", ["D13"], pack).endswith("$0.00") and "same value" not in describe("cited", ["D1147"], pack)
    assert describe("growth D437/D387", ["D437", "D387"], pack).startswith("growth D437/D387 = -9.42%: D437 = ")
    assert describe("reversed D443", ["D443"], pack).startswith("reversed D443 = +0.35pp: ")
    assert harness.semantics._bound({"qualifier": "at_most"}).startswith(" (a bound: the sentence says the value is at most")
    assert harness.semantics._bound({"qualifier": "approx"}) == ""


def _auditor_replies(harness: Any, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    sent: list[str] = []

    async def auditor(arm: Any, system: str, user: str, **kwargs: Any) -> CallResult:
        sent.append(user)
        return CallResult('{"items": [{"n": 1, "label": "consistent", "reason": "r"}]}', 1000, 0, 100, 0, 1.0, 0.25,
                          "claude_cli", "m", {"stop_reason": "end_turn"})

    monkeypatch.setattr(harness.causes, "call", auditor)
    return sent


def test_an_audit_records_its_view_and_one_under_an_earlier_view_is_redone_or_copied(harness: Any,
                                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _auditor_replies(harness, monkeypatch)
    _packs(harness)
    output = _output(red_flags=("Net debt was $89.6 billion in FY2025 [D352].",))
    record = _record(harness, output=output)
    runs = harness.generate.RUNS / LABEL
    default, same = (runs / "semantics" / "deepseek-flash" / f"{TICKER}.json",
                     runs / "semantics-by-claude-opus-5-5" / "deepseek-flash" / f"{TICKER}.json")
    view_1 = {"auditor": "claude-opus-5-5", "output_sha256": output_sha256(record), "items": [], "cost_usd": 0.5}
    _write(default, view_1)
    _write(same, {**view_1, "copied_from": "semantics"})
    asyncio.run(harness.semantics.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    redone = json.loads(default.read_text())
    assert redone["view"] == 2 and redone["prior_cost_usd"] == 0.5 and redone["cost_usd"] == 0.25 and len(sent) == 1
    assert f"{NET_CASH}, FY2025, -$89.59 billion" in sent[0] and "Values are signed" in harness.semantics.SYSTEM
    asyncio.run(harness.semantics.run(LABEL, ["deepseek-flash"], [TICKER], 1, "claude-opus-5-5"))
    copied = json.loads(same.read_text())
    assert len(sent) == 1, "the other folder's current-view audit of this output is copied, never bought again"
    assert copied["view"] == 2 and copied["copied_from"] == "semantics" and copied["prior_cost_usd"] == 0.0
    asyncio.run(harness.semantics.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    assert len(sent) == 1  # a current-view audit of an unchanged output stands


def test_a_refusal_under_an_earlier_view_is_kept(harness: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _auditor_replies(harness, monkeypatch)
    _packs(harness)
    record = _record(harness, output=_output(red_flags=("Net debt was $89.6 billion in FY2025 [D352].",)))
    path = harness.generate.RUNS / LABEL / "semantics" / "deepseek-flash" / f"{TICKER}.json"
    _write(path, {"auditor": "claude-opus-5-5", "output_sha256": output_sha256(record), "items": [], "refused": True})
    asyncio.run(harness.semantics.run(LABEL, ["deepseek-flash"], [TICKER], 1))
    assert sent == [] and "view" not in json.loads(path.read_text())


def test_the_report_shows_each_semantic_audit_s_view(harness: Any) -> None:
    _packs(harness)
    record = _record(harness)
    _semantic_audit(harness, record, "semantics", "claude-opus-5-5", [_item(GREW, "5.7%", "consistent")])
    support = harness.report.semantic_support(LABEL, ["deepseek-flash"], [TICKER])
    assert support["deepseek-flash"]["views"] == {"1": 1}  # eval-v1's audits carry no marker: view 1
