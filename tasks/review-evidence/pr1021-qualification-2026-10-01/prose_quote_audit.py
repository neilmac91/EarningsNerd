"""Offline, zero-cost prose-quotation + grounding audit of a retained Copilot eval artifact (copilot-eval.json).

Usage: python3 prose_quote_audit.py <copilot-eval.json> [...]
Exit 0 = clean; exit 1 = at least one composed quotation (or unusable input) -> acceptance FAIL;
exit 2 = no composed quotation, but at least one grounding escalation row -> founder decides, never an
automatic pass.

A "composed quotation" is a double-quoted span (>= 8 chars) in the published answer prose whose
whitespace/quote/dash-normalized, lower-cased text is not a contiguous substring of that row's
retained inputs.source_text. Same normalization as the skeptic audit (analysis/skeptic1021/quotes_all.py).
Citation excerpts are already verified by the service; this audits the prose the scorer never checks.

Grounding escalations (recorded per row; the scorer treats all of these as advisory, so an 18/18 run
can contain them):
- uncited_answer_rows: the answer states figures (score.figure_count > 0) but carries zero verified
  citations, e.g. a tool-less answer whose [F1]/[F2] markers were never issued and were stripped.
- uncited_figure_rows: score.uncited_figures > 0.
- tool_less_rows: tool_trace.tool_results is empty (no filing tool was executed for the answer).
"""
import json
import re
import sys

FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def norm(text):
    return re.sub(r"\s+", " ", (text or "").translate(FOLD).strip().lower())


def audit(path):
    report = json.load(open(path))
    hits, answers, missing_source = [], 0, []
    uncited_answers, uncited_figures, tool_less = [], [], []
    for row in report["results"]:
        answer = row.get("answer") or ""
        if not answer:
            continue
        answers += 1
        score = row.get("score") or {}
        key = {"ticker": row.get("ticker"), "question_id": row.get("question_id"),
               "run_index": row.get("run_index"), "passed": score.get("passed")}
        citations = row.get("citations") or []
        verified = sum(1 for c in citations if c.get("verified"))
        trace = row.get("tool_trace") if isinstance(row.get("tool_trace"), dict) else {}
        detail = dict(key, figure_count=score.get("figure_count"), uncited_figures=score.get("uncited_figures"),
                      citations=len(citations), verified_citations=verified,
                      tool_results=len(trace.get("tool_results") or []))
        if (score.get("figure_count") or 0) > 0 and verified == 0:
            uncited_answers.append(detail)
        if (score.get("uncited_figures") or 0) > 0:
            uncited_figures.append(detail)
        if not trace.get("tool_results"):
            tool_less.append(detail)
        source = (row.get("inputs") or {}).get("source_text")
        if not source:
            missing_source.append((row.get("ticker"), row.get("run_index")))
            continue
        normalized = norm(source)
        composed = [q for q in re.findall(r'"([^"]{8,})"', answer.translate(FOLD)) if norm(q) not in normalized]
        if composed:
            hits.append(dict(key, composed_quotes=composed))
    return {"artifact": path, "summary": report.get("summary"), "answers": answers,
            "rows_without_source_text": missing_source, "composed_quote_rows": hits,
            "grounding_escalations": {"uncited_answer_rows": uncited_answers,
                                      "uncited_figure_rows": uncited_figures,
                                      "tool_less_rows": tool_less}}


if __name__ == "__main__":
    results = [audit(p) for p in sys.argv[1:]]
    print(json.dumps(results, indent=1, ensure_ascii=False))
    bad = any(r["composed_quote_rows"] or r["rows_without_source_text"] for r in results) or not results
    escalate = any(any(r["grounding_escalations"].values()) for r in results)
    sys.exit(1 if bad else 2 if escalate else 0)
