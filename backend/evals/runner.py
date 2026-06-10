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

from evals.models import REGISTRY, ModelConfig, call_model, cost_usd
from evals.schema import GoldenFiling, GroundTruthFact
from evals.scorers import score_summary

GOLDEN_PATH = Path(__file__).with_name("golden_set.json")
REPORTS_DIR = Path(__file__).with_name("reports")

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


def _xbrl_to_text(metrics: Optional[Dict[str, Any]]) -> str:
    if not metrics:
        return ""
    try:
        return json.dumps(metrics, default=str)[:8000]
    except (TypeError, ValueError):
        return str(metrics)[:8000]


async def _get_grounding(filing: GoldenFiling) -> Dict[str, Any]:
    """Fetch filing text + critical excerpt + XBRL metrics using the app's own services."""
    from app.services.edgar.compat import sec_edgar_service, xbrl_service
    from app.services.openai_service import openai_service

    text = await sec_edgar_service.get_filing_document(filing.document_url, timeout=30.0)
    excerpt = openai_service.extract_critical_sections(text or "", filing.filing_type.upper()) or (text or "")
    metrics = None
    try:
        xbrl = await xbrl_service.get_xbrl_data(filing.accession_number, filing.cik)
        metrics = xbrl_service.extract_standardized_metrics(xbrl) if xbrl else None
    except Exception:  # noqa: BLE001
        metrics = None
    return {"filing_text": text or "", "excerpt": excerpt, "xbrl_metrics": metrics}


def _baseline_to_canonical(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Map the current pipeline's output into the canonical eval shape (best-effort).

    The baseline does not enforce the canonical schema, so it will typically score as
    schema-invalid here — that gap is exactly what S1 aims to close, and is the honest
    baseline to beat."""
    return {
        "executive_summary": summary.get("business_overview") or "",
        "financial_highlights": summary.get("financial_highlights") or {},
        "risk_factors": summary.get("risk_factors") or [],
        "management_discussion": summary.get("management_discussion") or "",
        "outlook": summary.get("key_changes") or "",
    }


async def _run_one(
    candidate: str, filing: GoldenFiling, grounding: Dict[str, Any]
) -> Dict[str, Any]:
    """Returns a serializable result dict for one (candidate, filing)."""
    import time

    base = {"candidate": candidate, "ticker": filing.ticker, "filing_type": filing.filing_type}
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
            score = score_summary(payload, filing.ground_truth)
            cfg = REGISTRY["baseline"]
            return {**base, "score": score.__dict__, "aggregate": score.aggregate(),
                    "latency_seconds": latency, "cost_usd": 0.0, "error": None}

        cfg: ModelConfig = REGISTRY[candidate]
        user = _grounding_user_prompt(
            filing.company_name, filing.filing_type, grounding["excerpt"],
            _xbrl_to_text(grounding["xbrl_metrics"]),
        )
        raw, in_tok, out_tok, latency = await call_model(cfg, _SYSTEM, user)
        score = score_summary(raw, filing.ground_truth)
        return {**base, "score": score.__dict__, "aggregate": score.aggregate(),
                "latency_seconds": latency, "input_tokens": in_tok, "output_tokens": out_tok,
                "cost_usd": cost_usd(cfg, in_tok, out_tok), "error": None}
    except Exception as exc:  # noqa: BLE001
        return {**base, "score": None, "aggregate": 0.0, "error": f"{type(exc).__name__}: {exc}"}


def _summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-candidate stats."""
    by_candidate: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        by_candidate.setdefault(r["candidate"], []).append(r)

    summary: Dict[str, Any] = {}
    for candidate, rs in by_candidate.items():
        scored = [r for r in rs if r.get("score")]
        n = len(scored)
        def mean(key: str) -> float:
            vals = [r["score"][key] for r in scored] if scored else []
            return round(statistics.mean(vals), 4) if vals else 0.0
        summary[candidate] = {
            "n": len(rs),
            "errors": sum(1 for r in rs if r.get("error")),
            "mean_aggregate": round(statistics.mean([r["aggregate"] for r in scored]), 4) if scored else 0.0,
            "schema_valid_rate": round(sum(1 for r in scored if r["score"]["schema_valid"]) / n, 4) if n else 0.0,
            "repaired_rate": round(sum(1 for r in scored if r["score"]["repaired"]) / n, 4) if n else 0.0,
            "mean_numeric_accuracy": mean("numeric_accuracy"),
            "mean_coverage": mean("coverage"),
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
             "| candidate | n | agg | schema_valid | repaired | numeric_acc | coverage | $cost | latency(s) | errors |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for cand, s in sorted(summary.items(), key=lambda kv: kv[1]["mean_aggregate"], reverse=True):
        lines.append(
            f"| {cand} | {s['n']} | {s['mean_aggregate']} | {s['schema_valid_rate']} | "
            f"{s['repaired_rate']} | {s['mean_numeric_accuracy']} | {s['mean_coverage']} | "
            f"{s['total_cost_usd']} | {s['mean_latency_seconds']} | {s['errors']} |"
        )
    lines += ["", "Adoption rule: promote a candidate only if it beats `baseline` on schema-validity,",
              "numeric accuracy, AND coverage with no regression, at acceptable latency/cost."]
    md_path = REPORTS_DIR / f"eval_{stamp}.md"
    md_path.write_text("\n".join(lines) + "\n")
    return md_path


async def main(candidates: List[str], limit: Optional[int], allow_unverified: bool) -> None:
    data = json.loads(GOLDEN_PATH.read_text())
    filings = [GoldenFiling.from_dict(e) for e in data["filings"]]
    runnable = [f for f in filings if f.document_url and (f.verified or allow_unverified)]
    if limit:
        runnable = runnable[:limit]
    if not runnable:
        print("No runnable golden filings. Run `python -m evals.build_golden_set` first "
              "(or pass --allow-unverified once entries have document_url).")
        return
    print(f"Running {candidates} over {len(runnable)} filings...")

    results: List[Dict[str, Any]] = []
    for f in runnable:
        grounding = await _get_grounding(f)
        for cand in candidates:
            print(f"  {cand} :: {f.ticker} {f.filing_type}")
            results.append(await _run_one(cand, f, grounding))

    summary = _summarize(results)
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
    args = parser.parse_args()
    asyncio.run(main([c.strip() for c in args.candidates.split(",") if c.strip()],
                     args.limit, args.allow_unverified))
