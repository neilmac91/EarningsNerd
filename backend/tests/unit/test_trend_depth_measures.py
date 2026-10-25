"""The depth harness's §3 measures and the auditor's view (evals/trend_depth/{report,semantics}.py, DEEPSEEK-ERRORS.md §3
"Measures" and fix 14) over stub run records, version 1 (no ``pipeline``) and version 2 (``pipeline: "v2"``).

Pins every measure on one basis for every record and arm: passes without a model repair (a failed generation counted as
not passing, and its own row), first-try errors (the model's own first output under the gate now, every record alike:
the gate's failing claims and the backstops' beyond them, each claim once), own-ID omissions and retypes, mislabels
(distinct sentences per 1,000 verified claims, from R1, R2a, R2c, R3 and Opus's substantive flags; the other probe
kinds in rows of their own; a flag on a bound counted under view 2 and every uncounted flag listed; the later view of
one auditor's two audits, and none while its re-audit failed), the calibration measures, broken net cash (the breaks
packs-v2 records, read alike for a figure cited by its withheld ID and one rebuilt from the lines packs-v2 shows; debt
and liquidity breaks; version-1 peer ranks apart), cause support from Opus's audit, form, cost (each prompt's shared
prefix over every label, so a warm repeat is priced cold), each arm's builds and the warning when they differ, the old
gate's continuity score, the several-run summary (every run, its range and the runs pooled), ``--out``, and that a
version-1 run reports its shared fields as before. Real cases read the committed packs (``_company``). And the auditor's
view 2: signed values, a bound, identical-valued twins, its version marker, and the redo of an audit made under view 1.

The stages are imported over a stub bootstrap whose records, pack directories included, live in ``tmp_path``, as in
``test_trend_depth_stages.py`` (whose fixture is copied here), so the real bootstrap never loads and no model is called.
"""
from __future__ import annotations

import asyncio
import gzip
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


COMMITTED = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10"


def _committed(ticker: str, version: str) -> dict[str, Any]:
    """A company's committed evidence pack (``packs`` or ``packs-v2``)."""
    return json.loads(gzip.decompress((COMMITTED / version / f"{ticker}.json.gz").read_bytes()))


def _company(harness: Any, ticker: str) -> None:
    """The company's committed packs, both versions, under the test's ticker: its real IDs and recorded breaks."""
    for version in ("packs", "packs-v2"):
        _write(harness.generate.RUNS.parent / version / f"{TICKER}.json", _committed(ticker, version))


def _sections(**by_section: list[str]) -> dict[str, Any]:
    """An output of the given sections' sentences, each a comparison."""
    return {"sections": [{"key": key, "title": key, "sentences": [{"type": "comparison", "text": text} for text in texts]}
                         for key, texts in by_section.items()]}


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
    assert m["first_try_scored"] == 1 and m["first_try_as_run"] == [{"ticker": TICKER, "basis": "first_pass_gate", "failures": 0}]
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


UNMATCHED = "Revenue was $99.0 billion in FY2025 [F10]."  # a figure the cited value does not match


def test_version_2_records_count_passes_omissions_and_retypes(harness: Any) -> None:
    _packs(harness)
    raw = _output(red_flags=(DEBT, UNMATCHED))  # the model's own first reply
    raw_gate = {"passed": False, "claims": 10, "verified": 8, "failed_claims": 2,
                "failures": [{"section": "red_flags", "sentence": UNMATCHED, "failure": "'$99.0 billion' matches nothing the sentence cites"},
                             {"section": "drivers", "sentence": GREW, "failure": "cause sentence cites no filing passage"}]}
    fixed = _v2(harness, raw_first_pass_gate=raw_gate, attempts=[_attempt(0, raw)],
                autocite={"added": [{"section": "red_flags", "sentence": DEBT, "claim": "$1.7 billion", "id": "D355"}], "rejected": 2},
                retyped=[{"section": "drivers", "sentence": GREW, "from": "cause", "to": "comparison"}])
    clean = {**fixed, "raw_first_pass_gate": {"passed": True, "failures": []}, "attempts": [_attempt(0, _output())],
             "autocite": {"added": [], "rejected": 0}, "retyped": []}
    patched = {**clean, "repair_kind": "patch", "first_pass_gate": raw_gate, "raw_first_pass_gate": raw_gate,
               "attempts": [_attempt(0, raw), _attempt("repair", "{}")]}
    m = _measures(harness, [fixed, clean, patched], "deepseek-flash-c")
    assert m["pipeline_v2"] == 3 and m["passes_without_repair"] == 2 and m["code_fixed_passes"] == 1
    assert m["repairs"] == {"patch": 1}
    assert m["own_id_omissions"] == 1 and m["autocite_rejected"] == 2
    assert m["autocite_added"] == [{"ticker": TICKER, "section": "red_flags", "sentence": DEBT, "claim": "$1.7 billion", "id": "D355"}]
    assert [r["to"] for r in m["retyped"]] == ["comparison"]
    rows = {name: shown for name, _, shown, *_ in harness.report.measure_rows(m)}
    assert rows["Own-ID omissions per analysis (IDs the code added)"] == "0.33 (1 in 3; 2 rejected)"
    assert m["first_try_errors"] == 2 and [a["failures"] for a in m["first_try_as_run"]] == [2, 0, 2]


GATE_ROW = "First-try gate failures per analysis: failing claims of the model's own first output, gate now (subtract gate artefacts by hand)"
BACKSTOP_ROW = "First-try backstop hits per analysis: claims the backstops fail beyond the gate's (broken net cash apart)"


def test_first_try_errors_score_the_model_s_own_first_output_on_one_basis_for_every_record(harness: Any) -> None:
    """DEEPSEEK-ERRORS.md §3's 0.68 baseline counts the gate's real failures alone. A version-2 record's as-run gate
    (``raw_first_pass_gate``, with backstops, a string per kind) and a version-1 record's (no backstops, the gate of its
    day) are two bases, so both are scored afresh: the gate's failing claims in one row, the backstops' in another."""
    _packs(harness)
    uncited = "Revenue was $99.0 billion in FY2025."  # "number(s) with no citation" and "matches nothing": one claim
    first = _output(red_flags=(DEBT, UNMATCHED, uncited))
    as_run = {**FAILED_FIRST, "failures": [{"failure": f"backstop R2a: {n}"} for n in range(7)]}
    v1 = _record(harness, "deepseek-flash-c", first_pass_output=first, first_pass_gate=FAILED_FIRST, attempts=REPAIRED)
    v2 = _v2(harness, raw_first_pass_gate=as_run, attempts=[_attempt(0, first), _attempt("repair", "{}")], repair_kind="patch")
    m1, m2 = _measures(harness, [v1], "deepseek-flash-c"), _measures(harness, [v2], "deepseek-flash-c")
    for m in (m1, m2):
        assert [(f["claim"], f["failure"]) for f in m["first_try_failures"]] == [
            ("$99.0 billion", "'$99.0 billion' matches nothing the sentence cites"),
            ("$99.0 billion", "'$99.0 billion' matches nothing the sentence cites")]
        # DEBT's two figures fail R2a; D352 is also withheld on packs-v2 (broken_debt), which is broken net cash's row.
        assert [(h["claim"], h["kinds"]) for h in m["first_try_backstop_hits"]] == [
            ("5.3%", ["U1"]), ("-$50.0 billion", ["R2a"]), ("-$89.6 billion", ["R2a"])]
        rows = {name: shown for name, _, shown, *_ in harness.report.measure_rows(m)}
        assert rows[GATE_ROW] == "2.00 (2 in 1 first outputs)" and rows[BACKSTOP_ROW] == "3.00 (3 in 1 first outputs)"
    assert m2["first_try_as_run"] == [{"ticker": TICKER, "basis": "raw_first_pass_gate", "failures": 7}]  # the cross-check
    assert "7 in 1 analyses" in "\n".join(harness.report.hand_reading("deepseek-flash-c", m2))


def test_a_claim_two_backstops_fail_counts_once(harness: Any) -> None:
    """CAT's eval-v1 DeepSeek sentence: "-35.6%" fails R2a and R2c; ``check(..., backstops=True)`` lists it twice."""
    _company(harness, "CAT")
    cat = "Net debt is 38.8% of revenue, better than the -35.6% peer median but only the 43rd percentile of seven industrials peers [D457][D1152][D1151]."
    m = _measures(harness, [_record(harness, output=_sections(balance_sheet=[cat]))])
    assert [(h["claim"], h["kinds"]) for h in m["first_try_backstop_hits"]] == [("-35.6%", ["R2a", "R2c"])]
    assert m["first_try_backstops"] == 1 and m["first_try_errors"] == 0


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


def test_the_current_gate_columns_check_a_version_2_record_with_its_backstops(harness: Any) -> None:
    """generate --pipeline v2 decides with the backstops, so "as run · current gate" must too, or one output reads
    'fail · pass' for a backstop hit alone, as if the gate had changed."""
    _packs(harness)
    output = _output(red_flags=(DEBT,))  # passes the gate; fails R2a (and broken_debt, as packs-v2 withholds D352)
    v2 = _v2(harness, output=output, first_pass_output=output)
    v1 = _record(harness, "deepseek-flash-c", output=output, first_pass_output=output)
    assert [harness.report.arm_stats([r])[key] for r in (v2, v1) for key in ("final_gate_now", "first_pass_gate_now")] == [0, 0, 1, 1]


# --- Failed generations -----------------------------------------------------------------------------------------------

FAILED_ROW = "Failed generations (the model's own: invalid replies or a refusal; each counts as not passing)"


def test_a_failed_generation_counts_as_not_passing(harness: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """A model's own failure (invalid replies, a refusal) is kept and never retried, so leaving it out of n would score
    an arm that fails to generate as if it had passed: 8 of 9 instead of 8 of 10."""
    _packs(harness)
    passed = _record(harness, label="run-a")
    failed = {"ticker": "F", "arm": "deepseek-flash", "generation_ok": False, "attempts": [_attempt(0, "nonsense", ("not JSON",))],
              "gate": {"passed": False}}
    _write(harness.generate.RUNS / "run-b" / "deepseek-flash" / "F.json", failed)
    for folder in ("packs", "packs-v2"):
        _write(harness.generate.RUNS.parent / folder / "F.json", _pack())
    _record(harness, label="run-b")
    m = _measures(harness, [passed, failed])
    rows = {name: shown for name, _, shown, *_ in harness.report.measure_rows(m)}
    assert m["analyses"] == 1 and m["failed_generations"] == 1
    assert rows["Passes without a model repair"] == "1 of 2 (50%; 1 failed generation among them)"
    assert rows[FAILED_ROW] == "1 of 2" and rows[GATE_ROW] == "0.00 (0 in 1 first outputs)"
    every_one = _measures(harness, [failed])  # an arm whose every generation failed is still reported
    assert every_one["analyses"] == 0 and every_one["failed_generations"] == 1
    assert {name: shown for name, _, shown, *_ in harness.report.measure_rows(every_one)}[FAILED_ROW] == "1 of 1"
    monkeypatch.setattr(harness.report, "eval_companies", lambda split=None: [types.SimpleNamespace(ticker=t) for t in (TICKER, "F")])
    monkeypatch.setattr(sys, "argv", ["report", "--labels", "run-a,run-b", "--systems", "deepseek-flash", "--old-gate", "none"])
    harness.report.main()
    row = next(line for line in capsys.readouterr().out.splitlines() if line.startswith(f"| {FAILED_ROW} |"))
    assert row.endswith("| 0 of 1 | 1 of 2 | 0–1 | 1 in all |")  # each run, the range and the runs pooled



# --- Mislabels, unsigned falls, calibration, form ---------------------------------------------------------------------

def _semantic_audit(harness: Any, record: dict[str, Any], folder: str, auditor: str, items: list, **fields: Any) -> None:
    _write(harness.generate.RUNS / LABEL / folder / record["arm"] / f"{TICKER}.json",
           {"auditor": auditor, "output_sha256": output_sha256(record), "items": items, **fields})


def _item(sentence: str, claim: str, label: str = "mismatch") -> dict[str, str]:
    from evals.trend_depth.factcheck import CITATION_RE

    return {"sentence": CITATION_RE.sub("", sentence).strip(), "claim": claim, "match": "m", "label": label, "reason": "r"}


MISLABEL_ROW = ("Mislabelled sentences per 1,000 verified claims: probes R1, R2a, R2c, R3 and Opus substantive flags "
                "(a sentence stating broken net cash is counted there instead)")


def test_mislabels_are_sentences_from_the_mislabel_probes_and_opus_substantive_flags(harness: Any) -> None:
    """§1.2's 9.6 per 1,000 counts distinct sentences of a wrong metric, basis, year or sign: two figures of one error
    count once, as do a probe and the auditor on it; an unsigned fall or a unitless dollar figure is its own row."""
    _packs(harness, v2=_pack())  # no break: the net-debt sentence is a mislabel only
    record = _record(harness)
    _semantic_audit(harness, record, "semantics-by-claude-opus-5-5", "claude-opus-5-5", [
        _item(DEBT, "-$89.6 billion"),  # also a probe hit on a sentence with two
        _item(GREW, "5.7%"), _item(GREW, "$31.7 billion"),  # two flags, one sentence
        _item(BOUND, "10%"),  # under view 2 the auditor read the bound: substantive
        _item(CAGR, "5.3%", "consistent"),
    ], view=2)
    _semantic_audit(harness, record, "semantics", "deepseek-v4-pro", [_item(GREW, "$31.7 billion")])  # not Opus: not counted
    m = _measures(harness, [record])
    assert (m["mislabels"], m["mislabel_claims"], m["probe_mislabels"], m["opus_mislabels"]) == (3, 5, 1, 3)
    assert m["opus_substantive"] == 4 and m["opus_audited"] == 1 and m["opus_views"] == {"2": 1}
    sources = sorted((h["claim"], h["source"]) for h in m["mislabel_list"])
    assert sources == [("$31.7 billion", "claude-opus-5-5 (view 2)"), ("-$50.0 billion", "probe R2a"),
                       ("-$89.6 billion", "probe R2a + claude-opus-5-5 (view 2)"), ("10%", "claude-opus-5-5 (view 2)"),
                       ("5.7%", "claude-opus-5-5 (view 2)")]
    assert [h["claim"] for h in m["U1"]] == ["5.3%"] and m["unitless_dollars"] == m["gap_direction"] == m["logic_slips"] == []
    shown = {name: s for name, _, s, *_ in harness.report.measure_rows(m)}
    assert shown[MISLABEL_ROW] == (f"{3 / m['verified_claims'] * 1000:.1f} (3 sentences in {m['verified_claims']} verified claims "
                                   "of 1 outputs: probes 1, Opus 3; Opus read 1 of 1, view 2 (1))")


def test_a_sentence_stating_broken_net_cash_is_counted_there_not_among_mislabels(harness: Any) -> None:
    """DE's eval-v1 DeepSeek sentence drew three Opus flags (§1.2's known false ones) and states FY2025 net debt built on
    the dropped long-term debt line: the broken-net-cash measure counts it, and the mislabels list it for reading."""
    _company(harness, "DE")
    de = "Net debt was $5.52 billion at FY2025 [D407], down from $35.8 billion in FY2021 [D226], or 12.1% of revenue [D408]."
    record = _record(harness, output=_sections(balance_sheet=[de]))
    _semantic_audit(harness, record, "semantics", "claude-opus-5-5", [_item(de, claim) for claim in ("$5.52 billion", "$35.8 billion", "12.1%")])
    m = _measures(harness, [record])
    assert (m["mislabels"], m["mislabel_claims"], m["opus_substantive"]) == (0, 3, 3)
    assert {h["also"] for h in m["mislabel_list"]} == {"also in broken net cash, counted there"}
    assert m["broken_net_cash"]["stated_as_fact"] == 1 and m["broken_net_cash"]["stated_sentences"] == 1


def test_a_net_debt_sentence_with_two_signed_figures_is_one_mislabel(harness: Any) -> None:
    """NEE's eval-v1 DeepSeek sentence prints both figures with net cash's sign under "net debt": two R2a claims."""
    _company(harness, "NEE")
    nee = "Net debt has deepened for seven consecutive years, from -$34.3 billion to -$92.2 billion, as capex outran cash flow [D9][D231][R2]."
    m = _measures(harness, [_record(harness, output=_sections(red_flags=[nee]))])
    assert (m["mislabels"], m["mislabel_claims"], m["probe_mislabels"]) == (1, 2, 1)


def test_the_probe_kinds_split_into_mislabels_rows_of_their_own_and_broken_net_cash(harness: Any) -> None:
    """Every gate kind of the probes is counted in exactly one place, so a new one must be placed (CLAUDE.md rule 12)."""
    from evals.trend_depth import probes

    report = harness.report
    placed = [*report.MISLABEL_KINDS, *report.OWN_ROW_KINDS, "broken_debt"]
    assert sorted(placed) == sorted(probes.GATE_KINDS) and len(placed) == len(set(placed))


def test_a_flag_on_a_bound_is_substantive_under_view_2_and_every_other_flag_is_listed(harness: Any) -> None:
    """CAT's operating margin (F30, 16.5%) cited for "net margin stayed above 15%": net margin is 13.1%. The gate passes
    the bound; view 2 told the auditor it was one, so the auditor's flag is a reading of the sentence. Under view 1 it is
    a bound flag, not counted but listed for reading, never dropped."""
    _company(harness, "CAT")
    wrong = "Net margin stayed above 15% in FY2025 [F30]."
    record = _record(harness, output=_sections(margins=[wrong]))
    item = _item(wrong, "15%")
    sentences = harness.generate.sentences_of(record["output"])
    pack = harness.generate.load_pack(TICKER, "deepseek-flash")
    assert [harness.semantics.classify_flag(item, sentences, pack, view) for view in (1, 2)] == ["bound", "substantive"]
    _semantic_audit(harness, record, "semantics", "claude-opus-5-5", [item], view=2)
    m = _measures(harness, [record])
    assert (m["mislabels"], m["opus_other"]) == (1, [])
    _semantic_audit(harness, record, "semantics", "claude-opus-5-5", [item])  # an eval-v1 audit: view 1
    m = _measures(harness, [record])
    assert m["mislabels"] == 0 and [(h["claim"], h["class"]) for h in m["opus_other"]] == [("15%", "bound")]
    assert "Opus flags not counted" in "\n".join(harness.report.hand_reading("deepseek-flash", m))


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


@pytest.mark.parametrize("failed", [{"error": "write_failed: no label"}, {"refused": True}, {"output_sha256": "an earlier output"}])
def test_a_re_audit_that_failed_never_falls_back_to_the_other_folder_s_earlier_view(harness: Any, failed: dict) -> None:
    """README step 0: eval-v1 copied into eval-v1-view2 leaves a view-1 Opus audit in both folders; the view-2 re-audit
    writes the same-auditor one. One that failed or was refused must leave the output unread, not bring back view 1."""
    _packs(harness)
    record = _record(harness)
    _semantic_audit(harness, record, "semantics", "claude-opus-5-5", [_item(GREW, "5.7%")])  # view 1, eval-v1's
    _semantic_audit(harness, record, "semantics-by-claude-opus-5-5", "claude-opus-5-5", [], view=2, **failed)
    m = _measures(harness, [record])
    assert (m["opus_audited"], m["opus_substantive"]) == (0, 0)


def test_of_two_finished_audits_by_one_auditor_the_later_view_counts(harness: Any) -> None:
    _packs(harness)
    record = _record(harness)
    for later, earlier in (("semantics", "semantics-by-claude-opus-5-5"), ("semantics-by-claude-opus-5-5", "semantics")):
        _semantic_audit(harness, record, earlier, "claude-opus-5-5", [_item(GREW, "5.7%")])
        _semantic_audit(harness, record, later, "claude-opus-5-5", [], view=2)
        m = _measures(harness, [record])
        assert (m["opus_audited"], m["opus_views"], m["opus_substantive"]) == (1, {"2": 1}, 0)


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

def _broken(harness: Any, ticker: str, version: str, *texts: str) -> dict[str, Any]:
    sentences = [{"section": "balance_sheet", "type": "comparison", "text": text} for text in texts]
    return harness.report.broken_net_cash(sentences, _committed(ticker, version), _committed(ticker, "packs-v2"))


# A broken figure cited by its ID (K0's eval-v1 sentences, on packs/, which still shows it) and the same figure rebuilt
# from the lines packs-v2 still shows (the review's P and C sentences): cash less the one debt line left, which the gate
# verifies as a difference. On either pack, one verdict. A liquidity break (MSFT FY2017: short-term investments missing;
# TGT: counted twice, as cash already holds them) is in scope too, though MSFT and TGT name no debt break.
BROKEN = [
    ("KO", "Net cash was $8.8 billion at FY2025, or 18.3% of revenue, against $10.3 billion of cash and investments [D442][D443][D440].",
     ["debt_break"]),
    ("KO", "Net cash was $8.8 billion in FY2025 [D440][X186].", ["debt_break"]),
    ("COP", "Net cash was $7.1 billion, or 12.1% of revenue, in FY2025, in the 100th percentile of six energy peers [D337][D338][D850][D851].",
     ["debt_break"]),
    ("COP", "Net cash was $7.1 billion at FY2025 [D335][X203].", ["debt_break"]),
    ("DE", "Net debt was $5.52 billion at FY2025 [D407], down from $35.8 billion in FY2021 [D226], or 12.1% of revenue [D408].",
     ["debt_break"]),
    ("DE", "Net debt was $5.5 billion at FY2025 [D405][X185], down from $35.8 billion in FY2021 [D226].", ["debt_break"]),
    ("MSFT", "Net debt was $78.5 billion in FY2017, cash of $7.7 billion against total debt of $86.2 billion [F151][D16].",
     ["liquidity_break"]),
    ("TGT", "Net debt was $4.3 billion, or 4.1% of revenue, better than the retail peer median of -3.5% net cash and at the 50th "
            "percentile of six peers [D410][D411][D613][D612].", ["liquidity_break"]),
    ("TGT", "Cash and short-term investments totalled $10.1 billion in FY2025 [F144][X170].", ["liquidity_break"]),
]


@pytest.mark.parametrize("version", ["packs", "packs-v2"])
@pytest.mark.parametrize("ticker, text, breaks", BROKEN)
def test_a_broken_figure_counts_alike_cited_or_rebuilt_on_either_pack(harness: Any, ticker: str, text: str, breaks: list,
                                                                       version: str) -> None:
    found = _broken(harness, ticker, version, text)
    assert found["state"] == "stated as fact" and [s["breaks"] for s in found["stated"]] == [breaks]


def test_a_disclosed_break_and_one_left_unsaid(harness: Any) -> None:
    # USB's eval-v1 DeepSeek sentence: the only break it disclosed.
    usb = _broken(harness, "USB", "packs", "Long-term debt stood at $39,829 million in FY2022, up 24.0% that year, the last year the pack reports it [F104][D158].")
    assert (usb["state"], usb["checks"], usb["stated"]) == ("disclosed", ["debt_break"], [])
    # Sonnet's NVDA disclosure beside an undisclosed restatement: the analysis discloses, the other sentence still counts.
    nvda = _broken(harness, "NVDA", "packs",
                   "FY2026 cash and investments of $10.6 billion equal cash alone, so the 83rd percentile net cash rank among six "
                   "semis peers is unreliable [D439][F150][D844].",
                   "Net cash was $2.1 billion in FY2026 [F150][D440].",
                   "Diluted EPS compounded at 7.4% against net income at 60.8%, so the EPS comparison looks unreliable [F216][F214].")
    assert nvda["state"] == "disclosed" and len(nvda["disclosed"]) == 1 and len(nvda["stated"]) == 1
    _company(harness, "NVDA")
    debt = _measures(harness, [_record(harness, output=_sections(balance_sheet=[s["sentence"] for s in nvda["disclosed"] + nvda["stated"]]))])
    assert (debt["broken_net_cash"]["stated_as_fact"], debt["broken_net_cash"]["disclosed"]) == (0, 1)
    assert debt["broken_net_cash"]["stated_sentences"] == 1  # stated without a disclosure in its own sentence
    assert _broken(harness, "NVDA", "packs-v2", "Cash rose to $10.6 billion in FY2026 [F150].")["state"] == "silent"
    assert _broken(harness, "REGN", "packs-v2", "Net cash was $1.0 billion in FY2025 [D1].") is None  # no break recorded
    # Words decide, never a cited withheld ID, which only an arm reading packs/ can cite (KO's withheld peer rank).
    assert _broken(harness, "KO", "packs", "That ranks at the 100th percentile, subject to a caveat [D793].")["disclosed"] == []


def test_broken_net_cash_rows_read_packs_v2_s_breaks_for_every_arm(harness: Any) -> None:
    """The review's KO case: K0 cites the withheld D442 on packs/; C, reading packs-v2, rebuilds the same $8.8 billion from
    the lines it shows. Counting only cited withheld IDs scored C silent by construction."""
    _company(harness, "KO")
    k0 = _record(harness, output=_sections(balance_sheet=[
        "Net cash was $8.8 billion at FY2025, or 18.3% of revenue, against $10.3 billion of cash and investments [D442][D443][D440]."]))
    c = _v2(harness, output=_sections(balance_sheet=["Net cash was $8.8 billion in FY2025 [D440][X186]."]))
    for record, system in ((k0, "deepseek-flash"), (c, "deepseek-flash-c")):
        debt = _measures(harness, [record], system)["broken_net_cash"]
        assert (debt["analyses"], debt["stated_as_fact"], debt["stated_sentences"]) == (1, 1, 1)
        assert debt["by_check"] == {"debt_break": [1, 1], "liquidity_break": [0, 0]}
    rows = {name: shown for name, _, shown, *_ in harness.report.measure_rows(_measures(harness, [c], "deepseek-flash-c"))}
    assert rows[BROKEN_ROW] == "1 of 1 (0 disclosed; debt break 1 of 1)"


def test_a_version_1_peer_rank_on_a_peer_s_broken_year_has_its_own_row(harness: Any) -> None:
    """CAT's eval-v1 DeepSeek sentence cites the version-1 peer median and rank packs-v2 replaces (peer_break): only an arm
    reading packs/ can cite them, so they are informational, never broken net cash (CAT names no break of its own)."""
    _company(harness, "CAT")
    cat = "Net debt is 38.8% of revenue, better than the -35.6% peer median but only the 43rd percentile of seven industrials peers [D457][D1152][D1151]."
    debt = _measures(harness, [_record(harness, output=_sections(balance_sheet=[cat]))])["broken_net_cash"]
    assert (debt["analyses"], debt["peer_sentences"], debt["peer_analyses"]) == (0, 1, 1)
    assert debt["list"][0]["state"] is None and debt["list"][0]["peer"][0]["breaks"] == ["peer_break"]


BROKEN_ROW = ("Broken net cash stated as fact: analyses of a company whose packs-v2 pack names a debt or liquidity break, "
              "its breaks read for every arm")


# --- Builds -----------------------------------------------------------------------------------------------------------

def test_an_arm_s_builds_are_listed_and_more_than_one_is_a_warning(harness: Any, monkeypatch: pytest.MonkeyPatch,
                                                                     capsys: pytest.CaptureFixture) -> None:
    from evals.trend_depth.records import pack_sha256

    _packs(harness)
    current = pack_sha256(harness.generate.load_pack(TICKER, "deepseek-flash-c"))
    made = {"prompt_sha256": "a" * 64, "pack_sha256": current, "snapshot_id": "s1", "pipeline": "v2"}
    _record(harness, "deepseek-flash-c", label="run-a", **made)
    one = harness.report.summarise("run-a", ["deepseek-flash-c"], None)
    assert one["splits"]["all"]["measures"]["deepseek-flash-c"]["builds"] == {"v2 · prompt aaaaaaaa · packs-v2": 1}
    assert harness.report.build_warnings({"run-a": one}, ["deepseek-flash-c"]) == []
    assert "Builds (pipeline · prompt sha256 · packs" in harness.report.render("run-a", ["deepseek-flash-c"], one)
    # The candidate edited between two runs, and packs-v2 rebuilt: r2's record names another prompt and pack.
    _record(harness, "deepseek-flash-c", label="run-b", **{**made, "prompt_sha256": "b" * 64, "pack_sha256": "c" * 64})
    monkeypatch.setattr(sys, "argv", ["report", "--labels", "run-a,run-b", "--systems", "deepseek-flash-c", "--old-gate", "none"])
    harness.report.main()
    text = capsys.readouterr().out
    warning = next(line for line in text.splitlines() if line.startswith("> **Warning:**"))
    assert text.index(warning) < text.index("## dev")  # at the top, before any measure
    assert ("run-a: v2 · prompt aaaaaaaa · packs-v2; run-b: v2 · prompt bbbbbbbb · packs-v2 (an earlier build); another pack in "
            f"one run than another for {TICKER}") in warning
    # Two runs on one prompt, each on a build of packs-v2 rebuilt since: one build name, but the company's packs differ.
    _record(harness, "deepseek-flash-c", label="run-c", **{**made, "pack_sha256": "d" * 64})
    _record(harness, "deepseek-flash-c", label="run-d", **{**made, "pack_sha256": "e" * 64})
    runs = {label: harness.report.summarise(label, ["deepseek-flash-c"], None) for label in ("run-c", "run-d")}
    assert harness.report.build_warnings(runs, ["deepseek-flash-c"])[0].endswith(
        f"run-c: v2 · prompt aaaaaaaa · packs-v2 (an earlier build); run-d: v2 · prompt aaaaaaaa · packs-v2 (an earlier build); "
        f"another pack in one run than another for {TICKER}.")
    # Within one label: a record of version 1 beside one of version 2 (a retry without --pipeline v2).
    mixed = harness.report.arm_measures("run-b", "deepseek-flash-c", [
        _record(harness, "deepseek-flash-c", label="run-b", **made),
        _record(harness, "deepseek-flash-c", label="run-b", **{**made, "pipeline": "v1"})], {})
    summary = {"splits": {"all": {"measures": {"deepseek-flash-c": mixed}}}}
    assert harness.report.build_warnings({"run-b": summary}, ["deepseek-flash-c"]) == [
        "> **Warning:** `deepseek-flash-c` in `run-b` holds records of 2 builds, pooled in its measures: v1 · prompt aaaaaaaa · "
        "packs-v2 (1); v2 · prompt aaaaaaaa · packs-v2 (1).", ""]


# --- Cost -------------------------------------------------------------------------------------------------------------

def _priced(harness: Any, label: str, reads: list[int]) -> list[dict[str, Any]]:
    """One settled analysis per first-attempt read, each on the frozen prompt's hash, as eval-v1's records are."""
    records = []
    for n, read in enumerate(reads):
        record = {**_settled(), "prompt_sha256": "f" * 64,
                  "attempts": [{**_attempt(0, "{}"), "input_tokens": 36000, "cached_input_tokens": read}]}
        _write(harness.generate.RUNS / label / "deepseek-flash" / f"C{n}.json", record)
        records.append(record)
    return records


def _settled() -> dict[str, Any]:
    output = _output()
    return {"ticker": TICKER, "arm": "deepseek-flash", "generation_ok": True, "split": "dev", "output": output, "words": 100,
            "gate": {"passed": True, "claims": 10, "verified": 10, "failed_claims": 0, "failures": []},
            "usage": {"input_tokens": 36000, "output_tokens": 100}, "latency_s": 9.0, "cost_usd": 0.001}


def test_a_warm_repeat_run_is_priced_as_a_cold_one(harness: Any) -> None:
    """eval-v1's first attempts (recorded): 15 read the frozen prompt's 1,920 tokens, five read their whole prompt, which
    dev-v4 had just sent; dev-v4's first three read 1,024, sent before the whole prompt was cached. A repeat label sent
    while every prompt is still cached reads each whole prompt: priced against its own least read, it cost about half."""
    _packs(harness)
    cold = _priced(harness, "eval-v1", [1920] * 15 + [29312, 33280, 34048, 36608, 40192])
    _priced(harness, "dev-v4", [1024, 1024, 1024, 1920, 1920])
    warm = _priced(harness, "repeat", [35000 + 64 * n for n in range(10)])
    stats = {label: harness.report.arm_stats(records) for label, records in (("eval-v1", cold), ("repeat", warm))}
    assert stats["eval-v1"]["shared_prefix_tokens"] == stats["repeat"]["shared_prefix_tokens"] == {"ffffffff": 1920}
    assert stats["repeat"]["cost_mean"] == pytest.approx(stats["eval-v1"]["cost_mean"])  # every first request read 1,920
    assert (stats["eval-v1"]["warm_first_attempts"], stats["repeat"]["warm_first_attempts"]) == ([5, 20], [10, 10])
    sonnet = {**_settled(), "arm": "claude-sonnet-5-5", "prompt_sha256": "f" * 64,
              "attempts": [{**_attempt(0, "{}"), "backend": "claude_cli", "cached_input_tokens": 30000}]}
    assert harness.report.arm_stats([sonnet])["shared_prefix_tokens"] == {}  # a Claude CLI call reads no cache
    record = _record(harness, prompt_sha256="f" * 64, attempts=[{**_attempt(0, "{}"), "cached_input_tokens": 36032}])
    rows = {name: shown for name, _, shown, *_ in harness.report.measure_rows(_measures(harness, [record]))}
    assert rows["API list cost per analysis"].endswith("(first requests read a 1,920-token shared prefix; 1 of 1 read more, priced at it)")


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


def test_out_writes_the_report_elsewhere_and_leaves_runs_untouched(harness: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                                                   capsys: pytest.CaptureFixture) -> None:
    _packs(harness)
    _record(harness)
    before = sorted(p.relative_to(harness.generate.RUNS) for p in harness.generate.RUNS.rglob("*"))
    out = tmp_path / "elsewhere"
    monkeypatch.setattr(sys, "argv", ["report", "--label", LABEL, "--systems", "deepseek-flash", "--old-gate", "none", "--out", str(out)])
    harness.report.main()
    assert (out / "REPORT.md").read_text().rstrip("\n") == capsys.readouterr().out.rstrip("\n") and (out / "summary.json").exists()
    assert sorted(p.relative_to(harness.generate.RUNS) for p in harness.generate.RUNS.rglob("*")) == before


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
