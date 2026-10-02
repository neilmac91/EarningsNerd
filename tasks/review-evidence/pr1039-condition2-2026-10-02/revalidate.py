#!/usr/bin/env python3
"""Offline revalidation of rendered `value_drivers.returns_on_capital` lines (item B, PR #1039).

Merge condition 2: every rendered returns line in the hosted eval-baseline report is compared
against that run's own retained `xbrl_grounding` operands for value, numerator scope, current and
prior dates, and duration; a sequential prior must read as dated, not YoY; every
`(numerator scope unestablished)` clause is listed.

Usage (cwd = the B worktree's backend/; real provider keys unset):

    python revalidate.py <hosted_eval_report.json> <out.json>
        [--backend DIR]       B backend whose `app` is imported (default: the current directory)
        [--main-backend DIR]  optional main backend (e.g. a `git archive` copy) rendered in a
                              subprocess, for "lines changed versus main"; omitted -> null counts
        [--main-label TEXT]   provenance text recorded for the main renderer

Where the hosted line lives
---------------------------
`results[i].raw_sections` is `summary["raw_summary"]["sections"]` (evals/runner.py:465), the same
`sections_info` dict the pipeline persists as `raw_summary["sections"]` (openai_service.py:1010)
after every final binder has run. Its `value_drivers.returns_on_capital` is written only by
`_apply_structured_fallbacks` (ai/markdown_render.py:593, inside `_assemble_structured_summary`).
Every user surface projects that one field through `summary_sections._v2_value_drivers` (`_clean`,
one paragraph block): the web's `rendered_sections` (provenance_service.py:797 ->
`render_sections_json`), PDF/CSV export (export_service.py:33, :128), and the persisted Markdown
`business_overview` (openai_service.py:995-999, :1214), which the report retains as
`results[i].payload.executive_summary` (runner.py:186). The script checks both hosted copies:
the field byte-for-byte against a re-render, and the Markdown line byte-for-byte against the
re-rendered Markdown line.

The re-render follows scratchpad/review-942s/replay2.py: `_apply_structured_fallbacks` on a deep
copy of `raw_sections` with the result's own `xbrl_grounding`, then `render_sections` +
`sections_to_markdown`. The returns line depends only on the metrics, so equality proves the
hosted line is exactly what B's renderer produces from the retained operands.

Exit status: 0 when every check passes; 1 when any check fails, a hosted line differs from the
re-render, or an undated / mis-dated prior renders; 2 on a usage or environment error.

No network: provider keys are removed from the environment before `app` is imported (a fixed
non-credential test key, as in tests/conftest.py, lets the client object construct), and every
socket connect raises. Bytecode writing is disabled so the worktree stays untouched.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import copy  # noqa: E402
import datetime as dt  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
from collections import Counter  # noqa: E402
from typing import Any, Dict, List, Optional, Tuple  # noqa: E402

PROVIDER_KEYS = ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY",
                 "ANTHROPIC_BASE_URL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_FALLBACK_API_KEY",
                 "OPENAI_FALLBACK_BASE_URL")
CODE_UNDER_TEST = ("app/services/ai/markdown_render.py", "app/services/ai/xbrl_narrative.py",
                   "app/services/financial_basis.py", "app/services/edgar/xbrl_service.py")
RATIOS = (("return_on_equity", "equity"), ("return_on_assets", "assets"))
UNESTABLISHED = "(numerator scope unestablished)"
SEQUENTIAL_GAP_DAYS = 300
YOY_WORDS = re.compile(r"(?i)\b(yoy|year[- ]over[- ]year|prior[- ]year|last year|a year earlier)\b")


# --------------------------------------------------------------------------------------------
# Offline environment
# --------------------------------------------------------------------------------------------
def offline_environment() -> Dict[str, str]:
    """Strip provider credentials, set hermetic placeholders, block every socket connect."""
    removed = {k: "unset-by-caller" if k not in os.environ else "removed" for k in PROVIDER_KEYS}
    for key in PROVIDER_KEYS:
        os.environ.pop(key, None)
    os.environ["OPENAI_API_KEY"] = "sk-test-key-for-mocking"  # tests/conftest.py placeholder
    os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:9/offline-blocked"
    os.environ["SECRET_KEY"] = "offline-revalidation-secret-key-0123456789abcdef"
    os.environ["SKIP_REDIS_INIT"] = "true"
    os.environ["PWNED_PASSWORD_CHECK_ENABLED"] = "false"
    os.environ["DATABASE_URL"] = "sqlite://"
    os.environ["ENVIRONMENT"] = "development"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

    def _blocked(*_a, **_k):
        raise RuntimeError("revalidate.py is offline: network access is blocked")

    socket.socket.connect = _blocked  # type: ignore[assignment]
    socket.socket.connect_ex = _blocked  # type: ignore[assignment]
    socket.create_connection = _blocked  # type: ignore[assignment]
    socket.getaddrinfo = _blocked  # type: ignore[assignment]
    return removed


def die(message: str) -> None:
    """Usage / environment error: exit 2, distinct from a check failure (exit 1)."""
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


def import_renderer(backend: str) -> Dict[str, Any]:
    backend = os.path.abspath(backend)
    if not os.path.isfile(os.path.join(backend, "app/services/ai/markdown_render.py")):
        die(f"{backend} is not a backend directory (no app/services/ai/markdown_render.py)")
    sys.path.insert(0, backend)
    os.chdir(backend)
    import app  # noqa: F401
    from app.services.openai_service import openai_service
    from app.services.ai.xbrl_narrative import build_xbrl_narrative_section
    from app.services.summary_sections import render_sections, sections_to_markdown, _clean
    from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION
    app_file = os.path.abspath(sys.modules["app"].__file__)
    if not app_file.startswith(backend + os.sep):
        die(f"imported app from {app_file}, expected under {backend}")
    return {"svc": openai_service, "grounding": build_xbrl_narrative_section, "render": render_sections,
            "md": sections_to_markdown, "clean": _clean, "schema": SUMMARY_SCHEMA_VERSION,
            "app_file": app_file}


def result_key(res: Dict[str, Any]) -> str:
    return f"{res.get('ticker')} {res.get('filing_type')} run{res.get('run')}"


def rerender(r: Dict[str, Any], res: Dict[str, Any]) -> Dict[str, Any]:
    """Replay2's re-render: fallbacks over a deep copy of raw_sections with the run's own metrics."""
    xg = res.get("xbrl_grounding")
    rs = res.get("raw_sections")
    out: Dict[str, Any] = {"grounding": r["grounding"](copy.deepcopy(xg)) if isinstance(xg, dict) else None,
                           "line": None, "sections": None, "markdown": None}
    if isinstance(rs, dict):
        s = copy.deepcopy(rs)
        r["svc"]._apply_structured_fallbacks(s, {}, copy.deepcopy(xg) if isinstance(xg, dict) else None)
        out["line"] = (s.get("value_drivers") or {}).get("returns_on_capital")
        out["sections"] = s
        out["markdown"] = r["md"](r["render"]({"schema_version": r["schema"], "sections": s}))
    return out


def render_worker(backend: str, report_path: str, out_path: str) -> None:
    """Subprocess entry: render every baseline result under `backend` (used for main)."""
    offline_environment()
    r = import_renderer(backend)
    report = json.load(open(report_path))
    rows = {}
    for res in report.get("results") or []:
        if res.get("candidate", "baseline") != "baseline":
            continue
        rows[result_key(res)] = rerender(r, res)
    json.dump({"app_file": r["app_file"], "rows": rows}, open(out_path, "w"), default=str)


# --------------------------------------------------------------------------------------------
# Parsing the rendered line (independent of the renderer's own string builders)
# --------------------------------------------------------------------------------------------
_CLAUSE = (r"period net income (?P<scope{n}>\(numerator scope unestablished\)|[^/:;()]+?) / period-end (?P<den{n}>equity|assets), not annualized: "
           r"(?P<val{n}>-?\d+\.\d)%"
           r"(?: \(prior at (?P<pdate{n}>[^:()]+): (?P<pval{n}>-?\d+\.\d)%"
           r"(?:; (?P<pbasis{n}>period net income (?P<pscope{n}>\(numerator scope unestablished\)|[^/:;()]+?) / period-end (?P=den{n}), not annualized))?\))?")
LINE_RE = re.compile("^" + _CLAUSE.format(n=1) + "(?:; " + _CLAUSE.format(n=2) + r")?\.$")
# A code-rendered returns line in Markdown: B's format anywhere on the line, or main's format at the
# start of a line (model prose that merely mentions "return on equity" is not a code-owned line).
B_FORMAT_RE = re.compile(r"/ period-end (equity|assets), not annualized: -?\d")
MAIN_FORMAT_START_RE = re.compile(r"^Return on (equity|assets) (was )?-?\d")
MAIN_CLAUSE_RE = re.compile(r"(?i)return on (equity|assets) (?:was )?(-?\d+\.\d)%(?: \(prior (-?\d+\.\d)%\))?")


def parse_line(line: str) -> Optional[List[Dict[str, Optional[str]]]]:
    if not isinstance(line, str) or not line or not line[0].isupper():
        return None
    m = LINE_RE.match(line[0].lower() + line[1:])
    if not m:
        return None
    clauses = []
    for n in (1, 2):
        if m.group(f"den{n}") is None:
            continue
        clauses.append({f: m.group(f"{f}{n}") for f in ("scope", "den", "val", "pdate", "pval", "pbasis", "pscope")})
    return clauses


def parse_main_line(line: Any) -> Dict[str, Dict[str, Optional[str]]]:
    if not isinstance(line, str):
        return {}
    return {m.group(1).lower(): {"val": m.group(2), "pval": m.group(3)} for m in MAIN_CLAUSE_RE.finditer(line)}


# --------------------------------------------------------------------------------------------
# Source checks
# --------------------------------------------------------------------------------------------
def iso_date(value: Any) -> Optional[dt.date]:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def duration(point: Any) -> Tuple[Optional[List[Any]], Optional[int], Optional[str]]:
    if not isinstance(point, dict):
        return None, None, None
    start, end = point.get("period_start"), point.get("period")
    pair = [start, end]
    ds, de = iso_date(start), iso_date(end)
    if ds is None or de is None:
        return pair, None, None
    days = (de - ds).days + 1
    for lo, hi, name in ((80, 100, "quarter"), (170, 195, "half"), (260, 285, "nine_months"), (350, 380, "annual")):
        if lo <= days <= hi:
            return pair, days, name
    return pair, days, f"other:{days}"


def num(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def recompute(point: Any) -> Tuple[Optional[float], List[str]]:
    """value = numerator / denominator * 100 from the point's own operand copies."""
    if not isinstance(point, dict):
        return None, ["point missing"]
    n, d = point.get("numerator"), point.get("denominator")
    if not isinstance(n, dict) or not isinstance(d, dict):
        return None, ["operand copies missing"]
    nv, dv = num(n.get("value")), num(d.get("value"))
    if nv is None or dv is None:
        return None, ["operand value missing"]
    if dv <= 0:
        return None, ["denominator not positive"]
    return (nv / dv) * 100, []


def same_float(a: Any, b: Optional[float]) -> bool:
    a = num(a)
    return a is not None and b is not None and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)


def operand_periods(point: Dict[str, Any]) -> bool:
    n, d = point.get("numerator") or {}, point.get("denominator") or {}
    return isinstance(point.get("period"), str) and n.get("period") == point.get("period") == d.get("period")


def check_clause(key: str, ratio: str, metric: Dict[str, Any], clause: Dict[str, Optional[str]],
                 ni_metric: Any, line: str, net_income_basis, in_band, ratio_period) -> Dict[str, Any]:
    fails: List[str] = []
    cur = metric.get("current") if isinstance(metric.get("current"), dict) else {}
    n_cur = cur.get("numerator") if isinstance(cur.get("numerator"), dict) else {}
    d_cur = cur.get("denominator") if isinstance(cur.get("denominator"), dict) else {}
    value, why = recompute(cur)
    fails += [f"current {w}" for w in why]
    rendered_ok = value is not None and clause["val"] == f"{value:.1f}"
    stored_ok = same_float(cur.get("value"), value)
    if value is not None and not rendered_ok:
        fails.append(f"current value renders {clause['val']}% but operands give {value:.1f}%")
    if value is not None and not stored_ok:
        fails.append("stored current ratio differs from operand recomputation")
    periods_ok = operand_periods(cur)
    if not periods_ok:
        fails.append("current operand periods differ from the ratio period")
    if iso_date(cur.get("period")) is None:
        fails.append(f"current ratio period is not an ISO date: {cur.get('period')!r}")
    n_dur, n_days, n_class = duration(n_cur)
    scope = net_income_basis(n_cur.get("raw_tag")) or UNESTABLISHED
    if clause["scope"] != scope:
        fails.append(f"scope renders {clause['scope']!r}, numerator concept {n_cur.get('raw_tag')!r} gives {scope!r}")
    ni_cur = ni_metric.get("current") if isinstance(ni_metric, dict) else None
    row: Dict[str, Any] = {
        "ratio": ratio, "current_period": cur.get("period"),
        "numerator_tag": n_cur.get("raw_tag"), "denominator_tag": d_cur.get("raw_tag"),
        "numerator_duration": n_dur, "numerator_duration_days": n_days, "numerator_duration_class": n_class,
        "current_value_recomputed": round(value, 1) if value is not None else None,
        "current_value_rendered": clause["val"],
        "current_value_rendered_ok": rendered_ok, "current_value_stored_matches_operands": stored_ok,
        "operand_periods_match": periods_ok,
        "scope": scope, "scope_rendered": clause["scope"], "scope_label_present": clause["scope"] == scope,
        "numerator_unestablished": scope == UNESTABLISHED,
        "numerator_is_sibling_ni_current": isinstance(ni_cur, dict) and n_cur == ni_cur,
    }
    prior = metric.get("prior") if isinstance(metric.get("prior"), dict) else None
    rendered = clause["pdate"] is not None
    prior_fields = dict.fromkeys((
        "prior_period", "prior_numerator_tag", "prior_numerator_duration", "prior_numerator_duration_days",
        "prior_numerator_duration_class", "prior_value_recomputed", "prior_value_rendered", "prior_value_rendered_ok",
        "prior_in_band", "prior_dated", "prior_rendered", "prior_date_rendered", "prior_date_matches_period",
        "prior_operand_periods_match", "prior_numerator_duration_class_match", "prior_numerator_is_sibling_ni_prior",
        "gap_days", "sequential", "prior_reads_dated_not_yoy", "prior_scope", "prior_basis_note",
        "prior_basis_note_expected", "prior_basis_note_correct", "prior_drop_reason"))
    row.update(prior_fields)
    if prior is None:
        if rendered:
            fails.append("prior renders but the ratio has no prior point")
    else:
        n_pri = prior.get("numerator") if isinstance(prior.get("numerator"), dict) else {}
        p_value, p_why = recompute(prior)
        p_period = prior.get("period")
        band_ok = in_band(prior.get("value"))
        renderer_dated = ratio_period(prior) is not None
        dated = iso_date(p_period) is not None
        expected = band_ok and renderer_dated
        ni_pri = ni_metric.get("prior") if isinstance(ni_metric, dict) else None
        p_dur, p_days, p_class = duration(n_pri)
        p_scope = net_income_basis(n_pri.get("raw_tag")) or UNESTABLISHED
        # Descriptive facts for every prior point, rendered or dropped.
        p_periods_ok = operand_periods(prior)
        class_ok = n_class is not None and p_class == n_class
        cd, pd = iso_date(cur.get("period")), iso_date(p_period)
        gap = (cd - pd).days if cd and pd else None
        sequential = gap is not None and gap < SEQUENTIAL_GAP_DAYS
        row.update({
            "prior_period": p_period, "prior_numerator_tag": n_pri.get("raw_tag"),
            "prior_numerator_duration": p_dur, "prior_numerator_duration_days": p_days,
            "prior_numerator_duration_class": p_class,
            "prior_value_recomputed": round(p_value, 1) if p_value is not None else None,
            "prior_in_band": band_ok, "prior_dated": dated, "prior_rendered": rendered,
            "prior_operand_periods_match": p_periods_ok, "prior_numerator_duration_class_match": class_ok,
            "prior_numerator_is_sibling_ni_prior": isinstance(ni_pri, dict) and n_pri == ni_pri,
            "gap_days": gap, "sequential": sequential,
            "prior_scope": p_scope, "prior_basis_note": clause["pbasis"] is not None,
        })
        if rendered:
            if not band_ok:
                fails.append("out-of-band prior renders")
            if not dated:
                fails.append(f"undated prior renders (period {p_period!r} is not an ISO date)")
            date_ok = clause["pdate"] == p_period
            if not date_ok:
                fails.append(f"mis-dated prior: renders 'prior at {clause['pdate']}', prior point period {p_period!r}")
            fails += [f"prior {w}" for w in p_why]
            p_rendered_ok = p_value is not None and clause["pval"] == f"{p_value:.1f}"
            if p_value is not None and not p_rendered_ok:
                fails.append(f"prior value renders {clause['pval']}% but operands give {p_value:.1f}%")
            if p_value is not None and not same_float(prior.get("value"), p_value):
                fails.append("stored prior ratio differs from operand recomputation")
            if not p_periods_ok:
                fails.append("prior operand periods differ from the prior ratio period")
            if not class_ok:
                fails.append(f"prior numerator duration class {p_class!r} differs from current {n_class!r}")
            reads_dated = date_ok and dated and not YOY_WORDS.search(line)
            if not reads_dated:
                fails.append("prior does not read as dated (or the line carries YoY wording)")
            note_expected = p_scope != scope
            note_present = clause["pbasis"] is not None
            note_ok = note_present == note_expected and (not note_present or clause["pscope"] == p_scope)
            if not note_ok:
                fails.append(f"prior basis note present={note_present} expected={note_expected} "
                             f"(rendered scope {clause['pscope']!r}, prior concept gives {p_scope!r})")
            row.update({
                "prior_value_rendered": clause["pval"], "prior_value_rendered_ok": p_rendered_ok,
                "prior_date_rendered": clause["pdate"], "prior_date_matches_period": date_ok,
                "prior_reads_dated_not_yoy": reads_dated,
                "prior_basis_note_expected": note_expected, "prior_basis_note_correct": note_ok,
            })
        else:
            if expected:
                fails.append("an in-band, dated prior point is not rendered")
            row["prior_drop_reason"] = ("out_of_band" if not band_ok else "undated" if not renderer_dated else None)
    row["failures"] = fails
    return row


def check_line(key: str, line: Any, xg: Any, net_income_basis, in_band, ratio_period
               ) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    """Return (source_checks, line-level failures, clauses expected but dropped for an out-of-band current)."""
    xg = xg if isinstance(xg, dict) else {}
    expected = []
    dropped_current = []
    for ratio, den in RATIOS:
        metric = xg.get(ratio)
        cur = metric.get("current") if isinstance(metric, dict) and isinstance(metric.get("current"), dict) else None
        if cur is None:
            continue
        if in_band(cur.get("value")):
            expected.append((ratio, den))
        else:
            dropped_current.append({"key": key, "ratio": ratio, "current_value": cur.get("value"),
                                    "current_period": cur.get("period")})
    fails: List[str] = []
    if line is None:
        if expected:
            fails.append(f"no returns line, but in-band ratios exist: {[r for r, _ in expected]}")
        return [], fails, dropped_current
    clauses = parse_line(line)
    if clauses is None:
        return [], [f"line does not parse as the B returns format: {line!r}"], dropped_current
    got = [c["den"] for c in clauses]
    if got != [den for _, den in expected]:
        fails.append(f"clauses rendered {got} but in-band ratios are {[den for _, den in expected]}")
    checks = []
    for clause in clauses:
        ratio = "return_on_equity" if clause["den"] == "equity" else "return_on_assets"
        metric = xg.get(ratio)
        if not isinstance(metric, dict):
            fails.append(f"{ratio} clause renders without a {ratio} metric")
            continue
        checks.append(check_clause(key, ratio, metric, clause, xg.get("net_income"), line,
                                   net_income_basis, in_band, ratio_period))
    return checks, fails, dropped_current


# --------------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------------
def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_info(path: str) -> Dict[str, Any]:
    def run(*args: str) -> Optional[str]:
        try:
            return subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, check=True,
                                  timeout=30).stdout.strip()
        except Exception:  # noqa: BLE001 - provenance is best-effort (an archive has no .git)
            return None
    head = run("rev-parse", "HEAD")
    status = run("status", "--porcelain", "--ignored") if head else None
    return {"head": head, "clean_including_ignored": (status == "") if head else None}


def md_returns_lines(md: Any) -> List[str]:
    if not isinstance(md, str):
        return []
    return [ln for ln in md.splitlines() if B_FORMAT_RE.search(ln) or MAIN_FORMAT_START_RE.match(ln)]


def main(argv: List[str]) -> int:
    if len(argv) >= 2 and argv[1] == "--render-worker":
        render_worker(argv[2], argv[3], argv[4])
        return 0
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("report")
    ap.add_argument("out")
    ap.add_argument("--backend", default=os.getcwd())
    ap.add_argument("--main-backend")
    ap.add_argument("--main-label")
    args = ap.parse_args(argv[1:])
    report_path, out_path = os.path.abspath(args.report), os.path.abspath(args.out)
    backend = os.path.abspath(args.backend)
    main_backend = os.path.abspath(args.main_backend) if args.main_backend else None
    script_path = os.path.abspath(__file__)

    provider_env = offline_environment()
    report = json.load(open(report_path))
    report_sha = sha256_file(report_path)
    missing = [p for p in CODE_UNDER_TEST if not os.path.isfile(os.path.join(backend, p))]
    if missing:
        die(f"{backend} lacks B's code under test: {missing}")
    git_before = git_info(backend)
    code_sha = {p: sha256_file(os.path.join(backend, p)) for p in CODE_UNDER_TEST}

    main_rows: Optional[Dict[str, Any]] = None
    main_app_file = None
    if main_backend:
        with tempfile.TemporaryDirectory(dir=os.path.dirname(out_path)) as tmp:
            tmp_out = os.path.join(tmp, "main-render.json")
            env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH",)}
            proc = subprocess.run([sys.executable, script_path, "--render-worker", main_backend, report_path, tmp_out],
                                  cwd=main_backend, env=env, capture_output=True, text=True, timeout=1800)
            if proc.returncode != 0:
                sys.stderr.write(proc.stdout + proc.stderr)
                die("main render worker failed")
            payload = json.load(open(tmp_out))
            main_rows, main_app_file = payload["rows"], payload["app_file"]

    r = import_renderer(backend)
    try:
        from app.services.financial_basis import net_income_basis
        from app.services.ai.xbrl_narrative import (RETURNS_RATIO_BAND_PCT, return_ratio_period,
                                                    returns_ratio_in_band)
    except ImportError as exc:
        die(f"{backend} is not B's renderer: {exc}")

    results = report.get("results") or []
    c: Dict[str, Any] = {
        "results": 0, "results_skipped_non_baseline": 0, "results_with_error": [],
        "grounding_block_identical_main_vs_successor": None, "grounding_block_changed": None,
        "returns_lines_changed": None, "results_without_returns_line": [],
        "other_section_fields_changed": None, "markdown_lines_changed_outside_returns_line": None,
        "successor_line_equals_hosted_line": 0, "hosted_markdown_line_equals_rerender": 0,
        "lines_by_numerator_scope": Counter(),
        "lines_with_dated_prior_successor": 0, "lines_with_prior_main": None,
        "ratio_clauses_checked": 0,
        "clauses_value_recomputed_from_operands": 0, "clauses_stored_value_matches_operands": 0,
        "clauses_scope_label_matches_numerator_concept": 0, "clauses_operand_periods_match": 0,
        "clauses_numerator_unestablished": 0, "clauses_dropped_current_out_of_band": [],
        "clauses_with_prior_point": 0, "prior_clauses_rendered_dated": 0,
        "prior_clauses_date_matches_prior_period": 0, "prior_clauses_value_recomputed_from_operands": 0,
        "prior_clauses_operand_periods_match": 0, "prior_numerator_duration_class_match": 0,
        "prior_clauses_dropped_out_of_band": 0, "prior_clauses_dropped_out_of_band_same_as_main": None,
        "prior_clauses_dropped_undated": 0, "prior_clauses_sequential": 0,
        "prior_clauses_sequential_read_dated_not_yoy": 0,
        "prior_gap_days": Counter(), "prior_numerator_is_ni_prior": 0,
        "prior_basis_notes": 0, "prior_basis_notes_correct": 0,
        "numerator_denominator_concepts": Counter(),
        "numerator_duration_classes": Counter(),
        "clauses_current_not_ni_current": 0,
    }
    failures: List[Dict[str, Any]] = []
    unestablished: List[Dict[str, Any]] = []
    sequential: List[Dict[str, Any]] = []
    dropped_priors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    lines_out: List[Dict[str, Any]] = []
    main_compare = main_rows is not None
    if main_compare:
        c.update(grounding_block_identical_main_vs_successor=0, grounding_block_changed=0, returns_lines_changed=0,
                 other_section_fields_changed=0, markdown_lines_changed_outside_returns_line=0,
                 lines_with_prior_main=0, prior_clauses_dropped_out_of_band_same_as_main=0)

    for res in results:
        if res.get("candidate", "baseline") != "baseline":
            c["results_skipped_non_baseline"] += 1
            continue
        key = result_key(res)
        c["results"] += 1
        if res.get("error") or not isinstance(res.get("raw_sections"), dict):
            c["results_with_error"].append(key)
            failures.append({"key": key, "reason": f"no retained sections to check (error: {res.get('error')!r})"})
            continue
        xg = res.get("xbrl_grounding")
        hosted = (res["raw_sections"].get("value_drivers") or {}).get("returns_on_capital")
        hosted_md = (res.get("payload") or {}).get("executive_summary")
        rr = rerender(r, res)
        line = rr["line"]

        # Hosted field and hosted Markdown line versus the re-render.
        if hosted == line:
            c["successor_line_equals_hosted_line"] += 1
        else:
            failures.append({"key": key, "reason": "hosted line differs from re-render", "hosted": hosted,
                             "rerender": line})
        host_md_lines, rer_md_lines = md_returns_lines(hosted_md), md_returns_lines(rr["markdown"])
        expected_md = [r["clean"](line)] if line else []
        # Other sections may legitimately differ (the hosted render envelope carries context keys the
        # re-render omits), so compare only the code-rendered returns line(s).
        if host_md_lines == rer_md_lines == expected_md:
            c["hosted_markdown_line_equals_rerender"] += 1
        else:
            failures.append({"key": key, "reason": "hosted Markdown returns line differs from re-render",
                             "hosted_markdown_lines": host_md_lines, "rerender_markdown_lines": rer_md_lines})

        main_row = main_rows.get(key) if main_compare else None
        main_line = main_row.get("line") if main_row else None
        if main_compare:
            if main_row is None:
                failures.append({"key": key, "reason": "main render missing for this result"})
            else:
                same_g = main_row["grounding"] == rr["grounding"]
                c["grounding_block_identical_main_vs_successor" if same_g else "grounding_block_changed"] += 1
                if main_line != line:
                    c["returns_lines_changed"] += 1
                if isinstance(main_line, str) and "(prior " in main_line:
                    c["lines_with_prior_main"] += 1
                ms, ss = main_row["sections"] or {}, rr["sections"] or {}
                for sec in sorted(set(ms) | set(ss)):
                    a, b = ms.get(sec), ss.get(sec)
                    if isinstance(a, dict) and isinstance(b, dict):
                        for fld in sorted(set(a) | set(b)):
                            if (sec, fld) != ("value_drivers", "returns_on_capital") and a.get(fld) != b.get(fld):
                                c["other_section_fields_changed"] += 1
                    elif a != b:
                        c["other_section_fields_changed"] += 1
                drop = {main_line, line} - {None}
                ml = [x for x in (main_row["markdown"] or "").splitlines() if x not in drop]
                sl = [x for x in (rr["markdown"] or "").splitlines() if x not in drop]
                if ml != sl:
                    c["markdown_lines_changed_outside_returns_line"] += 1

        checks, line_fails, dropped_current = check_line(key, line, xg, net_income_basis,
                                                         returns_ratio_in_band, return_ratio_period)
        c["clauses_dropped_current_out_of_band"] += dropped_current
        failures += [{"key": key, "reason": f} for f in line_fails]
        if line is None:
            c["results_without_returns_line"].append(key)
            continue
        main_clauses = parse_main_line(main_line)
        scopes = {ch["scope"] for ch in checks}
        c["lines_by_numerator_scope"][scopes.pop() if len(scopes) == 1 else "mixed" if scopes else "none"] += 1
        if any(ch["prior_rendered"] for ch in checks):
            c["lines_with_dated_prior_successor"] += 1
        for ch in checks:
            c["ratio_clauses_checked"] += 1
            failures += [{"key": key, "ratio": ch["ratio"], "reason": f} for f in ch["failures"]]
            c["clauses_value_recomputed_from_operands"] += bool(ch["current_value_rendered_ok"])
            c["clauses_stored_value_matches_operands"] += bool(ch["current_value_stored_matches_operands"])
            c["clauses_scope_label_matches_numerator_concept"] += bool(ch["scope_label_present"])
            c["clauses_operand_periods_match"] += bool(ch["operand_periods_match"])
            c["numerator_denominator_concepts"][f"{ch['numerator_tag']} | {ch['denominator_tag']}"] += 1
            c["numerator_duration_classes"][str(ch["numerator_duration_class"])] += 1
            if not ch["numerator_is_sibling_ni_current"]:
                c["clauses_current_not_ni_current"] += 1
                warnings.append({"key": key, "ratio": ch["ratio"], "current_period": ch["current_period"],
                                 "note": "ratio current numerator is not the net-income metric's current point "
                                         "(README known limitation: stale current; not a check failure)"})
            if ch["numerator_unestablished"]:
                c["clauses_numerator_unestablished"] += 1
                unestablished.append({"key": key, "ratio": ch["ratio"], "numerator_tag": ch["numerator_tag"],
                                      "line": line})
            if ch["prior_period"] is None and ch["prior_in_band"] is None:
                continue
            c["clauses_with_prior_point"] += 1
            c["prior_numerator_is_ni_prior"] += bool(ch["prior_numerator_is_sibling_ni_prior"])
            if ch["prior_rendered"]:
                c["prior_clauses_rendered_dated"] += bool(ch["prior_dated"] and ch["prior_date_matches_period"])
                c["prior_clauses_date_matches_prior_period"] += bool(ch["prior_date_matches_period"])
                c["prior_clauses_value_recomputed_from_operands"] += bool(ch["prior_value_rendered_ok"])
                c["prior_clauses_operand_periods_match"] += bool(ch["prior_operand_periods_match"])
                c["prior_numerator_duration_class_match"] += bool(ch["prior_numerator_duration_class_match"])
                c["prior_gap_days"][str(ch["gap_days"])] += 1
                c["prior_basis_notes"] += bool(ch["prior_basis_note"])
                c["prior_basis_notes_correct"] += bool(ch["prior_basis_note_correct"])
                if ch["sequential"]:
                    c["prior_clauses_sequential"] += 1
                    c["prior_clauses_sequential_read_dated_not_yoy"] += bool(ch["prior_reads_dated_not_yoy"])
                    sequential.append({"key": key, "ratio": ch["ratio"], "current_period": ch["current_period"],
                                       "prior_period": ch["prior_period"], "gap_days": ch["gap_days"],
                                       "rendered": f"prior at {ch['prior_date_rendered']}: {ch['prior_value_rendered']}%",
                                       "reads_dated_not_yoy": ch["prior_reads_dated_not_yoy"]})
            else:
                reason = ch["prior_drop_reason"]
                if reason == "out_of_band":
                    c["prior_clauses_dropped_out_of_band"] += 1
                    if main_compare:
                        den = "equity" if ch["ratio"] == "return_on_equity" else "assets"
                        if (main_clauses.get(den) or {}).get("pval") is None:
                            c["prior_clauses_dropped_out_of_band_same_as_main"] += 1
                elif reason == "undated":
                    c["prior_clauses_dropped_undated"] += 1
                dropped_priors.append({"key": key, "ratio": ch["ratio"], "reason": reason,
                                       "prior_period": ch["prior_period"],
                                       "prior_value_recomputed": ch["prior_value_recomputed"]})
        lines_out.append({"key": key, "main": main_line if main_compare else None,
                          "changed_vs_main": (main_line != line) if main_compare else None,
                          "successor": line, "hosted": hosted, "hosted_equals_rerender": hosted == line,
                          "source_checks": checks})

    for k, v in list(c.items()):
        if isinstance(v, Counter):
            c[k] = dict(sorted(v.items(), key=lambda kv: (-kv[1], kv[0])))
    git_after = git_info(backend)
    out = {
        "purpose": ("Offline, provider-free revalidation of every rendered value_drivers.returns_on_capital line "
                    "in a hosted eval-baseline report against the run's own retained xbrl_grounding operands "
                    "(item B, PR #1039, merge condition 2)."),
        "source": {"report": report_path, "report_sha256": report_sha,
                   "harness_source_sha": (report.get("harness") or {}).get("source_sha"),
                   "harness_model": (report.get("harness") or {}).get("model")},
        "renderers": {
            "successor": {"backend": backend, "app_file": r["app_file"], "git": git_before,
                          "git_after_run": git_after, "code_under_test_sha256": code_sha},
            "main": ({"backend": main_backend, "label": args.main_label, "app_file": main_app_file}
                     if main_compare else None),
        },
        "script": {"path": script_path, "sha256": sha256_file(script_path)},
        "environment": {"provider_keys": provider_env, "network": "socket connect/getaddrinfo blocked",
                        "python": sys.version.split()[0], "band_pct": RETURNS_RATIO_BAND_PCT,
                        "sequential_gap_days_below": SEQUENTIAL_GAP_DAYS},
        "hosted_line_location": {
            "field": "results[i].raw_sections.value_drivers.returns_on_capital",
            "markdown": "results[i].payload.executive_summary (the persisted business_overview Markdown)",
            "why_user_facing": ("raw_sections is raw_summary['sections'] (evals/runner.py:465), the persisted "
                                "sections after every final binder (openai_service.py:1010). The field is written "
                                "only by _apply_structured_fallbacks (ai/markdown_render.py:593). Web "
                                "rendered_sections (provenance_service.py:797), PDF/CSV export (export_service.py:33, "
                                ":128) and the Markdown business_overview (openai_service.py:995-999, :1214) all "
                                "project it through summary_sections._v2_value_drivers."),
        },
        "method": ("For each baseline result: _apply_structured_fallbacks(deepcopy(raw_sections), {}, "
                   "deepcopy(xbrl_grounding)) then render_sections + sections_to_markdown under the successor "
                   "backend (and, when given, the main backend in a subprocess). The hosted field and Markdown "
                   "line must equal the re-render byte for byte. Each clause of the line is parsed by regex and "
                   "compared with the ratio point's own numerator/denominator operand copies: value "
                   "(numerator / denominator x 100, one decimal), operand periods equal to the ratio period, "
                   "numerator duration, scope = net_income_basis(numerator raw_tag) or "
                   "'(numerator scope unestablished)', and the prior: rendered only if in the band and dated, "
                   "'prior at <date>' equal to the prior point's period (ISO date), same numerator duration "
                   "class, basis note iff the prior numerator scope differs. No model or network call."),
        "counts": c,
        "count_names_vs_replay_r_returns": {
            "successor_line_equals_retained_r_line": "successor_line_equals_hosted_line",
            "changed_lines": "every result with a returns line (changed_vs_main marks the change)",
            "prior_gap_days": "rendered priors only, as in replay-r-returns.json",
        },
        "failures": failures,
        "unestablished_clauses": unestablished,
        "sequential_priors": sequential,
        "dropped_priors": dropped_priors,
        "warnings": warnings,
        "changed_lines": lines_out,
    }
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
        fh.write("\n")
    if git_before != git_after:
        print("error: the successor worktree changed during the run", file=sys.stderr)
        return 2
    status = 1 if failures else 0
    print(f"results={c['results']} lines={len(lines_out)} clauses={c['ratio_clauses_checked']} "
          f"failures={len(failures)} unestablished={c['clauses_numerator_unestablished']} exit={status}")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
