"""Operator runner for the "Ask this Filing" Copilot eval (P8).

Runs the live Copilot (``copilot_service.answer_filing_question``) over the golden Q&A set and scores
each answer with the deterministic gates in ``copilot_scorers``. Like the summary runner, this is a
**manual operator task** (needs the model API + the filings/financial_fact ingested in the DB), not a
CI step — the CI rigor lives in ``tests/unit/test_copilot_evals.py``.

    cd backend && python -m evals.copilot_runner --limit 1

Writes ``evals/reports/copilot_eval_<timestamp>.{json,md}``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.database import SessionLocal
from app.models import Company, Filing
from app.services.copilot_service import answer_filing_question, snapshot_filing
from evals.copilot_schema import CopilotGoldenCase
from evals.copilot_scorers import score_copilot_answer

GOLDEN_PATH = Path(__file__).with_name("copilot_golden_set.json")
REPORTS_DIR = Path(__file__).with_name("reports")


def _load_cases(path: Path) -> List[CopilotGoldenCase]:
    data = json.loads(path.read_text())
    return [CopilotGoldenCase.from_dict(c) for c in data.get("cases", [])]


def _snapshot_for_case(case: CopilotGoldenCase):
    """Look up the ingested Filing for a golden case and return a detached snapshot (or None).

    Snapshots *inside* the open session — the same constraint the product endpoint follows — so the
    SSE generator never reads from a detached ORM instance (which would DetachedInstanceError on any
    deferred/lazy attribute once the session is closed)."""
    from sqlalchemy.orm import joinedload

    db = SessionLocal()
    try:
        filing = (
            db.query(Filing)
            .options(joinedload(Filing.content_cache), joinedload(Filing.company))
            .join(Company, Filing.company_id == Company.id)
            .filter(Company.cik == case.cik, Filing.accession_number == case.accession_number)
            .first()
        )
        return snapshot_filing(filing) if filing else None
    finally:
        db.close()


async def _answer(filing_snap, question: str) -> Tuple[str, List[dict], str, int]:
    """Drive the SSE generator to completion and return (answer, citations, kind, stripped).

    ``stripped`` is the complete event's ``misplaced_fact_markers`` — fact markers the production
    resolver removed for sitting on the wrong figure. The scorer's adjacency gate checks what
    SHIPPED; this counter tracks how often the model *attempted* a misplacement (a prompt/model
    placement-quality signal even when every violation was caught)."""
    answer, citations, kind, stripped = "", [], "answer", 0
    async for event in answer_filing_question(filing=filing_snap, question=question):
        etype = event.get("type")
        if etype == "complete":
            answer = event.get("answer", "")
            citations = event.get("citations", []) or []
            kind = event.get("kind", "answer")
            stripped = int(event.get("misplaced_fact_markers", 0) or 0)
        elif etype == "not_disclosed":
            kind = "not_disclosed"
            answer = event.get("answer", "")
        elif etype == "error":
            kind = "error"
            answer = event.get("message", "")
    return answer, citations, kind, stripped


def _source_text(filing_snap) -> str:
    cache = getattr(filing_snap, "content_cache", None)
    if cache is None:
        return ""
    return getattr(cache, "critical_excerpt", None) or getattr(cache, "markdown_content", None) or ""


async def run(limit: Optional[int] = None) -> Dict[str, Any]:
    cases = _load_cases(GOLDEN_PATH)
    if limit:
        cases = cases[:limit]

    results: List[Dict[str, Any]] = []
    answered = 0
    passed = 0

    for case in cases:
        snap = _snapshot_for_case(case)
        if snap is None:
            results.append({"ticker": case.ticker, "skipped": "filing not ingested in DB"})
            continue
        source = _source_text(snap)
        for qa in case.qa:
            ans, cites, kind, stripped = await _answer(snap, qa.question)
            if kind == "error":
                results.append({"ticker": case.ticker, "question": qa.question, "error": ans})
                continue
            score = score_copilot_answer(
                qa, answer=ans, citations=cites, kind=kind, filing_text=source
            )
            answered += 1
            passed += 1 if score.passed else 0
            results.append(
                {"ticker": case.ticker, **score.to_dict(), "stripped_misplaced_markers": stripped}
            )

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "answered": answered,
        "passed": passed,
        "pass_rate": round(passed / answered, 4) if answered else 0.0,
        "results": results,
    }
    return summary


def _write_report(summary: Dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = REPORTS_DIR / f"copilot_eval_{stamp}.json"
    json_path.write_text(json.dumps(summary, indent=2))

    lines = [
        f"# Copilot eval — {summary['timestamp']}",
        "",
        f"**Pass rate: {summary['pass_rate']:.0%}** ({summary['passed']}/{summary['answered']} answered)",
        "",
        "| Ticker | Question | Kind | Refusal✓ | Cite faithful | Fact adj | Coverage | Numeric | Gates |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in summary["results"]:
        if "skipped" in r or "error" in r:
            lines.append(f"| {r.get('ticker','?')} | {r.get('question','—')} | — | — | — | — | — | — | {r.get('skipped') or r.get('error')} |")
            continue
        q = (r["question"][:48] + "…") if len(r["question"]) > 49 else r["question"]
        gates = ", ".join(r["gate_failures"]) or "✓ pass"
        # Surface stripped-misplacement attempts next to the shipped-output adjacency score.
        adj = f"{r['fact_adjacency']:.2f}"
        if r.get("stripped_misplaced_markers"):
            adj += f" (−{r['stripped_misplaced_markers']} stripped)"
        # Coverage is WARN-level: shown per row (uncited/total figures), never a gate.
        cov = f"{r['figure_coverage']:.2f}"
        if r.get("uncited_figures"):
            cov += f" ({r['uncited_figures']}/{r['figure_count']} uncited)"
        lines.append(
            f"| {r['ticker']} | {q} | {r['kind']} | {'✓' if r['refusal_correct'] else '✗'} "
            f"| {r['citation_faithfulness']:.2f} | {adj} | {cov} | {r['numeric_recall']:.2f} | {gates} |"
        )
    md_path = REPORTS_DIR / f"copilot_eval_{stamp}.md"
    md_path.write_text("\n".join(lines) + "\n")
    return md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Ask-this-Filing Copilot eval.")
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N filings.")
    args = parser.parse_args()

    summary = asyncio.run(run(limit=args.limit))
    report = _write_report(summary)
    print(f"Pass rate: {summary['pass_rate']:.0%} ({summary['passed']}/{summary['answered']}) → {report}")


if __name__ == "__main__":
    main()
