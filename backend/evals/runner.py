"""Bake-off runner: score the baseline pipeline and candidate models on the golden set.

    cd backend && python -m evals.runner --candidates baseline,gemini-json,claude-sonnet
    cd backend && python -m evals.runner --candidates baseline --limit 3 --allow-unverified

Outputs a JSON + Markdown report under evals/reports/. Requires SEC EDGAR network access
(to fetch filings/XBRL) and the relevant provider API keys for each candidate. The baseline
candidate exercises the current openai_service pipeline end-to-end.

ADOPTION RULE (roadmap S3/S1): only promote a candidate to default if it beats the baseline on
schema-validity AND numeric accuracy AND coverage with no regression — at acceptable latency/cost.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from evals.judge import judge_summary
from evals.models import REGISTRY, ModelConfig, call_model, cost_usd
from evals.schema import GoldenFiling
from evals.scorers import parse_model_json, score_summary

GOLDEN_PATH = Path(__file__).with_name("golden_set.json")
REPORTS_DIR = Path(__file__).with_name("reports")
DEFAULT_PASS_THRESHOLD = 0.7  # aggregate a gate-passing run must clear to count as a PASS

_SYSTEM = (
    "You are a meticulous SEC-filing analyst. Extract a structured summary STRICTLY from the "
    "provided filing excerpt and XBRL financial facts. Use ONLY numbers that appear in the "
    "provided data — never estimate or invent figures. If a value is genuinely absent, say so "
    "briefly rather than guessing. Return a JSON object matching the required schema."
)


def _grounding_user_prompt(
    company: str, filing_type: str, excerpt: str, xbrl_text: str
) -> str:
    return (
        f"Company: {company}\nFiling type: {filing_type}\n\n"
        f"=== STANDARDIZED XBRL FINANCIAL FACTS ===\n{xbrl_text or '(none available)'}\n\n"
        f"=== FILING EXCERPT (critical sections) ===\n{excerpt[:90000]}\n\n"
        "Produce the structured summary now. financial_highlights.revenue / net_income / eps "
        "must quote the XBRL facts above verbatim where available."
    )


# The judge (and non-baseline candidate prompts) must see the FULL standardized-metric set the
# generator grounds on. The old 8,000-char cap truncated ~1/3 of the metrics mid-dict for a
# metric-rich filer (AAPL FY25 = 12,244 chars), so late keys (free_cash_flow, ROE/ROA, working
# capital, current ratio) fell out of the judge's view and were false-flagged as G3 hallucinations —
# the same class of judge blind-spot as the 60k→200k excerpt truncation. The full metrics JSON is
# small (~12-15k) and the judge already carries a 200k excerpt budget, so a generous cap fits every
# observed filer while still bounding a corrupted/oversized dict.
_XBRL_TEXT_CHAR_CAP = 40_000


def _xbrl_to_text(metrics: Optional[Dict[str, Any]]) -> str:
    if not metrics:
        return ""
    try:
        return json.dumps(metrics, default=str)[:_XBRL_TEXT_CHAR_CAP]
    except (TypeError, ValueError):
        return str(metrics)[:_XBRL_TEXT_CHAR_CAP]


async def _get_grounding(filing: GoldenFiling) -> Dict[str, Any]:
    """Fetch filing text + critical excerpt + XBRL metrics using the app's own services.

    Mirrors the product excerpt path (summary_generation_service.get_or_cache_excerpt): prefer
    edgartools' native section parser, fall back to the legacy regex extractor — so the bake-off
    scores exactly what production serves.
    """
    from app.services.edgar.compat import sec_edgar_service, xbrl_service
    from app.services.openai_service import openai_service
    from app.config import settings

    form = filing.filing_type.upper()
    text = await sec_edgar_service.get_filing_document(filing.document_url, timeout=30.0)

    excerpt = None
    source = "regex"
    if settings.USE_EDGARTOOLS_SECTIONS and filing.cik and filing.accession_number:
        try:
            sections = await xbrl_service.get_filing_sections(filing.accession_number, filing.cik, form)
        except Exception:  # noqa: BLE001
            sections = None
        if sections:
            built = openai_service.assemble_excerpt_from_sections(sections, form, filing_text=text)
            if built and len(built) >= 8000:
                excerpt, source = built, "edgartools"
    if not excerpt:
        excerpt = openai_service.extract_critical_sections(text or "", form) or (text or "")
    print(f"    excerpt[{filing.ticker} {form}]: {len(excerpt):,} chars (source={source})")

    metrics = None
    try:
        xbrl = await xbrl_service.get_xbrl_data(filing.accession_number, filing.cik)
        metrics = xbrl_service.extract_standardized_metrics(xbrl) if xbrl else None
    except Exception:  # noqa: BLE001
        metrics = None
    return {"filing_text": text or "", "excerpt": excerpt, "xbrl_metrics": metrics}


def _baseline_to_canonical(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Map the current pipeline's output into the canonical eval shape (best-effort).

    `financial_highlights` is passed through in the pipeline's own richer shape (a metric table +
    profitability / cash_flow / balance_sheet bullets); `validate_schema` accepts that shape, so a
    well-formed baseline scores schema-valid."""
    return {
        "executive_summary": summary.get("business_overview") or "",
        "financial_highlights": summary.get("financial_highlights") or {},
        "risk_factors": summary.get("risk_factors") or [],
        "management_discussion": summary.get("management_discussion") or "",
        "outlook": summary.get("key_changes") or "",
        # T4 follow-up: footnote evidence is verbatim-contracted but was dropped from the
        # canonical shape, so the citation-fidelity scorer could not see it. Eval-harness-internal
        # threading only — the pipeline payload contract is untouched.
        "notable_footnotes": ((summary.get("raw_summary") or {}).get("sections") or {}).get(
            "notable_footnotes"
        ) or [],
    }


async def _maybe_judge(
    judge_model: Optional[str], payload: Optional[Dict[str, Any]],
    filing: GoldenFiling, grounding: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Run the optional LLM judge (secondary signal) and return a serializable verdict."""
    if not judge_model or not isinstance(payload, dict):
        return None
    verdict = await judge_summary(
        payload, filing.company_name, filing.filing_type,
        grounding["excerpt"], _xbrl_to_text(grounding["xbrl_metrics"]), model_id=judge_model,
    )
    return {"passed": verdict.passed, "verdict": verdict.verdict,
            "mean_dimension": verdict.mean_dimension, "gate_failures": verdict.gate_failures,
            "dimensions": verdict.dimensions, "error": verdict.error}


async def _run_one(
    candidate: str, filing: GoldenFiling, grounding: Dict[str, Any],
    run_index: int = 0, judge_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Returns a serializable result dict for one (candidate, filing, run_index)."""
    import time

    base = {"candidate": candidate, "ticker": filing.ticker,
            "filing_type": filing.filing_type, "run": run_index}
    try:
        if candidate == "baseline":
            from app.services.openai_service import openai_service

            started = time.time()
            summary = await openai_service.summarize_filing(
                grounding["filing_text"], filing.company_name, filing.filing_type,
                xbrl_metrics=grounding["xbrl_metrics"], filing_excerpt=grounding["excerpt"],
            )
            latency = round(time.time() - started, 3)
            payload = _baseline_to_canonical(summary)
            # Fidelity referent = the text the model GENERATED FROM (excerpt-first) — the same
            # rule as the production gate. The raw document is a different text RENDERING than the
            # edgartools-markdown excerpt on formatting-heavy docs (FPI 20-Fs, amendments), and
            # verifying quotes against text the model never saw false-failed 5/26 filings
            # deterministically on the first readout (production audit verified all of them).
            score = score_summary(
                payload, filing.ground_truth,
                filing_text=grounding["excerpt"] or grounding["filing_text"],
            )
            judge = await _maybe_judge(judge_model, payload, filing, grounding)
            return {**base, "score": score.__dict__, "aggregate": score.aggregate(),
                    "passed_gates": score.passed_gates, "judge": judge,
                    "latency_seconds": latency, "cost_usd": 0.0, "error": None}

        cfg: ModelConfig = REGISTRY[candidate]
        user = _grounding_user_prompt(
            filing.company_name, filing.filing_type, grounding["excerpt"],
            _xbrl_to_text(grounding["xbrl_metrics"]),
        )
        raw, in_tok, out_tok, latency = await call_model(cfg, _SYSTEM, user)
        # Same excerpt-first referent as the baseline path: the candidate's prompt input IS the
        # excerpt (_grounding_user_prompt above), so quotes are judged against what it read.
        score = score_summary(
            raw, filing.ground_truth,
            filing_text=grounding["excerpt"] or grounding["filing_text"],
        )
        payload, _ = parse_model_json(raw)
        judge = await _maybe_judge(judge_model, payload, filing, grounding)
        return {**base, "score": score.__dict__, "aggregate": score.aggregate(),
                "passed_gates": score.passed_gates, "judge": judge,
                "latency_seconds": latency, "input_tokens": in_tok, "output_tokens": out_tok,
                "cost_usd": cost_usd(cfg, in_tok, out_tok), "error": None}
    except Exception as exc:  # noqa: BLE001
        return {**base, "score": None, "aggregate": 0.0, "passed_gates": False,
                "judge": None, "error": f"{type(exc).__name__}: {exc}"}


def _summarize(
    results: List[Dict[str, Any]], pass_threshold: float = DEFAULT_PASS_THRESHOLD
) -> Dict[str, Any]:
    """Aggregate per-candidate stats, including Artifact-3 consistency.

    A run PASSES when it clears the hard gates AND its aggregate >= pass_threshold. `pass_rate`
    and `aggregate_stdev` quantify the "hit and miss" problem that a single-shot mean hides."""
    by_candidate: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        by_candidate.setdefault(r["candidate"], []).append(r)

    summary: Dict[str, Any] = {}
    for candidate, rs in by_candidate.items():
        scored = [r for r in rs if r.get("score")]
        n = len(scored)
        def mean(key: str) -> float:
            # Tolerate score dicts that predate a metric (e.g. a newly-added field) — skip rather
            # than KeyError, so adding a scorer never crashes the summary of an older report.
            vals = [r["score"][key] for r in scored if key in r["score"]]
            return round(statistics.mean(vals), 4) if vals else 0.0
        aggs = [r["aggregate"] for r in scored]
        passes = [bool(r.get("passed_gates")) and r["aggregate"] >= pass_threshold for r in scored]
        judged = [r["judge"] for r in rs if r.get("judge")]
        summary[candidate] = {
            "n": len(rs),
            "errors": sum(1 for r in rs if r.get("error")),
            "mean_aggregate": round(statistics.mean(aggs), 4) if aggs else 0.0,
            "aggregate_stdev": round(statistics.pstdev(aggs), 4) if len(aggs) > 1 else 0.0,
            "pass_rate": round(sum(passes) / n, 4) if n else 0.0,
            "gate_fail_rate": round(sum(1 for r in scored if not r.get("passed_gates")) / n, 4) if n else 0.0,
            "schema_valid_rate": round(sum(1 for r in scored if r["score"]["schema_valid"]) / n, 4) if n else 0.0,
            "repaired_rate": round(sum(1 for r in scored if r["score"]["repaired"]) / n, 4) if n else 0.0,
            "mean_numeric_accuracy": mean("numeric_accuracy"),
            "mean_numeric_precision": mean("numeric_precision"),
            "mean_coverage": mean("coverage"),
            "mean_financial_depth": mean("financial_depth"),
            "mean_specificity": mean("specificity"),
            "mean_currency_consistency": mean("currency_consistency"),
            "mean_redundancy": mean("redundancy"),
            "mean_delta_consistency": mean("delta_consistency"),
            "mean_forward_quote_fidelity": mean("forward_quote_fidelity"),
            "mean_citation_fidelity": mean("citation_fidelity"),
            "judge_pass_rate": round(sum(1 for j in judged if j.get("passed")) / len(judged), 4) if judged else None,
            "total_cost_usd": round(sum(r.get("cost_usd", 0.0) for r in rs), 4),
            "mean_latency_seconds": round(statistics.mean([r["latency_seconds"] for r in rs if r.get("latency_seconds")]), 3) if any(r.get("latency_seconds") for r in rs) else 0.0,
        }
    return summary


def _write_report(summary: Dict[str, Any], results: List[Dict[str, Any]]) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (REPORTS_DIR / f"eval_{stamp}.json").write_text(
        json.dumps({"summary": summary, "results": results}, indent=2) + "\n"
    )
    lines = [f"# Summary-quality bake-off — {stamp}", "",
             "Ranked by pass_rate (gate-passing runs clearing the aggregate threshold), then mean aggregate.",
             "",
             "| candidate | n | pass_rate | agg | agg_stdev | gate_fail | schema_valid | repaired | num_recall | num_precision | coverage | depth | specificity | currency | judge_pass | $cost | latency(s) | errors |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    ranked = sorted(summary.items(),
                    key=lambda kv: (kv[1]["pass_rate"], kv[1]["mean_aggregate"]), reverse=True)
    for cand, s in ranked:
        judge_pass = "-" if s.get("judge_pass_rate") is None else s["judge_pass_rate"]
        lines.append(
            f"| {cand} | {s['n']} | {s['pass_rate']} | {s['mean_aggregate']} | {s['aggregate_stdev']} | "
            f"{s['gate_fail_rate']} | {s['schema_valid_rate']} | {s['repaired_rate']} | "
            f"{s['mean_numeric_accuracy']} | {s['mean_numeric_precision']} | {s['mean_coverage']} | {s['mean_financial_depth']} | {s.get('mean_specificity', '-')} | {s.get('mean_currency_consistency', '-')} | "
            f"{judge_pass} | {s['total_cost_usd']} | {s['mean_latency_seconds']} | {s['errors']} |"
        )
    lines += [
        "",
        "## Adoption rule",
        "Promote a candidate to default **only if** it beats `baseline` on schema-validity, numeric",
        "accuracy, AND coverage with **no hard-gate regression** (`gate_fail` not worse than baseline),",
        "AND meets the consistency target (high `pass_rate`, low `agg_stdev`) — at acceptable",
        "latency/cost. Hard gates (numeric fidelity, output hygiene) are a veto: a run that fails a",
        "gate cannot count as a PASS regardless of its aggregate. `judge_pass` is a secondary signal.",
    ]
    md_path = REPORTS_DIR / f"eval_{stamp}.md"
    md_path.write_text("\n".join(lines) + "\n")
    return md_path


DEFAULT_CONCURRENCY = 5  # headroom under EDGAR_THREAD_POOL_SIZE=4 while still parallelizing AI calls


async def _process_filing(
    f: GoldenFiling, candidates: List[str], runs: int, judge_model: Optional[str],
) -> List[Dict[str, Any]]:
    """Fetch grounding + run every (candidate, run) for one filing. Runs concurrently with other
    filings (see `main`'s semaphore-bounded gather); sequential *within* a filing since candidates
    share the same grounding data."""
    try:
        grounding = await _get_grounding(f)
    except Exception as exc:  # noqa: BLE001 — a transient fetch failure (e.g. SEC 429) on one
        # filing must not crash the whole bake-off; record it and move on.
        print(f"  ! grounding failed for {f.ticker} {f.filing_type}: {type(exc).__name__}: {exc}")
        return [
            {"candidate": cand, "ticker": f.ticker, "filing_type": f.filing_type, "run": i,
             "score": None, "aggregate": 0.0, "passed_gates": False, "judge": None,
             "error": f"grounding: {type(exc).__name__}: {exc}"}
            for cand in candidates for i in range(runs)
        ]
    out: List[Dict[str, Any]] = []
    for cand in candidates:
        for i in range(runs):
            tag = f" run {i + 1}/{runs}" if runs > 1 else ""
            print(f"  {cand} :: {f.ticker} {f.filing_type}{tag}")
            out.append(await _run_one(cand, f, grounding, run_index=i, judge_model=judge_model))
    return out


async def main(
    candidates: List[str], limit: Optional[int], allow_unverified: bool,
    runs: int = 1, pass_threshold: float = DEFAULT_PASS_THRESHOLD,
    judge_model: Optional[str] = None, forms: Optional[List[str]] = None,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> None:
    data = json.loads(GOLDEN_PATH.read_text())
    filings = [GoldenFiling.from_dict(e) for e in data["filings"]]
    runnable = [f for f in filings if f.document_url and (f.verified or allow_unverified)]
    if not runnable:
        print("No runnable golden filings. Run `python -m evals.build_golden_set` first "
              "(or pass --allow-unverified once entries have document_url).")
        return
    if forms:
        wanted = {x.strip().upper() for x in forms}
        matched = [f for f in runnable if f.filing_type.upper() in wanted]
        if not matched:
            available = sorted({f.filing_type.upper() for f in runnable})
            print(f"No runnable golden filings match --forms {sorted(wanted)}. "
                  f"Available forms: {available}.")
            return
        runnable = matched
    if limit:
        runnable = runnable[:limit]
    print(f"Running {candidates} over {len(runnable)} filings x {runs} run(s), "
          f"concurrency={concurrency}{f', judge={judge_model}' if judge_model else ''}...")

    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def _bounded(f: GoldenFiling) -> List[Dict[str, Any]]:
        async with semaphore:
            return await _process_filing(f, candidates, runs, judge_model)

    per_filing_results = await asyncio.gather(*[_bounded(f) for f in runnable])
    results: List[Dict[str, Any]] = [r for sub in per_filing_results for r in sub]

    summary = _summarize(results, pass_threshold=pass_threshold)
    md_path = _write_report(summary, results)
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"\nReport: {md_path}")


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="baseline",
                        help="comma-separated: baseline,gemini-json,claude-sonnet,claude-opus,qwen,kimi,deepseek")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--allow-unverified", action="store_true",
                        help="score entries whose ground_truth/accession aren't yet verified")
    parser.add_argument("--runs", type=int, default=1,
                        help="runs per (candidate, filing) to measure consistency / variance")
    parser.add_argument("--pass-threshold", type=float, default=DEFAULT_PASS_THRESHOLD,
                        help="aggregate a gate-passing run must clear to count as a PASS")
    parser.add_argument("--judge", default=None,
                        help="LLM-judge model id for the secondary signal (off by default). Backends: "
                             "'claude-opus-4-8' (anthropic SDK + ANTHROPIC_API_KEY; authoritative); "
                             "'cli:sonnet'/'cli:opus' (subscription CLI via `claude -p`, no API key; "
                             "local only); 'glm-5.2'/'openai:<model>' (OpenAI-compatible, "
                             "JUDGE_OPENAI_BASE_URL/JUDGE_OPENAI_API_KEY; cheap CI/fallback).")
    parser.add_argument("--forms", default=None,
                        help="comma-separated filing types to include (e.g. '20-F' or '10-K,10-Q'); "
                             "scores only matching golden entries. Cheap way to iterate on one form.")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help="max filings processed in parallel (each filing's candidates/runs stay "
                             "sequential). Bounded by EDGAR_THREAD_POOL_SIZE for the fetch side; the "
                             "AI-call side scales further. Set to 1 for the old fully-sequential behavior.")
    args = parser.parse_args()
    asyncio.run(main([c.strip() for c in args.candidates.split(",") if c.strip()],
                     args.limit, args.allow_unverified, runs=max(1, args.runs),
                     pass_threshold=args.pass_threshold, judge_model=args.judge,
                     forms=[x.strip() for x in args.forms.split(",") if x.strip()] if args.forms else None,
                     concurrency=args.concurrency))
