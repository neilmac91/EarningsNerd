"""Supplementary offline replay: summary evidence surfaces vs the excerpt the model generated from.

NOT an evidence-snap audit replay: no ``evidence_snap_audit`` is retained offline (searched the
summary eval artifacts and ``tasks/review-evidence``). This reads the two retained summary eval
artifacts (``eval-*/eval_*.json``), whose rows carry the final ``raw_sections`` and the
``grounding_excerpt`` (sha256/len bound to ``coverage_inventory``). It reports, per surface, whether
each displayed/verified value is contiguous in ``normalize_for_match(grounding_excerpt)`` in full,
only after a wrapping-quote strip, or only through ``extract_quoted_span`` (the prefix-tolerant
read path). Read-time production verifies against the cached ``critical_excerpt``/``markdown_content``
rather than this excerpt, so this is a proxy referent, stated as such.

cite-fix adaptation (2026-10-02): per surface it also records, against the same referent,
* ``new_whole``          — ``verify_whole_excerpt_in_text(value)`` (the fix's helper);
* ``build_evidence``     — main's read-time verdict (``build_evidence(value)["verified"]``), unchanged
                           code that still serves footnotes and metric takeaways;
* ``enriched``           — forward quotes only: the verdict ``_enrich_forward_quotes`` now attaches
                           (whole-quote gate in front of ``build_evidence``), from the worktree code.

Usage (from the worktree's backend dir): python replay_summary_surfaces.py <scratchpad> <out.json>
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-long-enough-123")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_mock_stripe_key_12345")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_mock_stripe_webhook_12345")
os.environ.setdefault("SKIP_REDIS_INIT", "true")
for _k in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY"):
    os.environ.pop(_k, None)

from app.services import provenance_service as prov  # noqa: E402

_OPEN, _CLOSE = "\"'“‘", "\"'”’"


def _unwrap(t: str) -> str:
    t = t.strip()
    return t[1:-1].strip() if len(t) >= 2 and t[0] in _OPEN and t[-1] in _CLOSE else t


def _in(text: str, norm: str) -> bool:
    n = prov.normalize_for_match(text)
    return len(n) >= prov._MIN_VERIFIABLE_LEN and n in norm


def classify(value: str, norm: str) -> str:
    stripped = value.strip()
    if len(prov.normalize_for_match(prov.extract_quoted_span(stripped))) < prov._MIN_VERIFIABLE_LEN:
        return "too_short_to_verify"
    if _in(stripped, norm):
        return "full_contiguous"
    if _in(_unwrap(stripped), norm):
        return "full_after_wrapping_quote_strip"
    quoted = prov.extract_quoted_span(stripped)
    if quoted != stripped and _in(quoted, norm):
        return "only_inner_quoted_span"
    return "not_contiguous"


def _surfaces(sections: dict):
    rtm = sections.get("results_that_matter")
    if isinstance(rtm, dict):
        for row in rtm.get("table") or []:
            if isinstance(row, dict) and isinstance(row.get("supporting_evidence"), str) and row["supporting_evidence"].strip():
                yield "results_that_matter.supporting_evidence", row["supporting_evidence"]
    for fn in sections.get("notable_footnotes") or []:
        if isinstance(fn, dict) and isinstance(fn.get("supporting_evidence"), str) and fn["supporting_evidence"].strip():
            yield "notable_footnotes.supporting_evidence", fn["supporting_evidence"]
    fs = sections.get("forward_signals")
    if isinstance(fs, dict):
        for q in fs.get("quotes") or []:
            if isinstance(q, dict) and isinstance(q.get("quote"), str) and q["quote"].strip():
                yield "forward_signals.quotes.quote", q["quote"]
    for risk in sections.get("risks") or []:
        if isinstance(risk, dict) and isinstance(risk.get("supporting_evidence"), str) and risk["supporting_evidence"].strip():
            yield "risks.supporting_evidence(projected)", risk["supporting_evidence"]


_BASE = "https://www.sec.gov/Archives/edgar/data/0/0/doc.htm"


def _verdicts(surface: str, value: str, norm: str) -> dict:
    out = {"new_whole": prov.verify_whole_excerpt_in_text(value, norm),
           "build_evidence": prov.build_evidence(value, "ref", _BASE, norm)["verified"]}
    if surface == "forward_signals.quotes.quote":
        sections = {"forward_signals": {"source_section_ref": "ref", "quotes": [{"quote": value}]}}
        prov._enrich_forward_quotes(sections, _BASE, norm)
        ev = sections["forward_signals"]["quotes"][0]["evidence"]
        out["enriched"] = ev["verified"]
        out["enriched_equals_build_evidence"] = ev == prov.build_evidence(value, "ref", _BASE, norm)
    return out


def main(scratch: str, out_path: str) -> None:
    import subprocess
    report = {"provenance_service_sha256": hashlib.sha256(open(prov.__file__, "rb").read()).hexdigest(),
              "provenance_service_path": prov.__file__,
              "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
              "runs": []}
    totals: dict = {}
    for path in sorted(glob.glob(os.path.join(scratch, "eval-*", "eval_*.json"))):
        data = json.load(open(path))
        harness = data.get("harness") or {}
        run = {"artifact": path, "artifact_sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(),
               "source_sha": harness.get("source_sha"), "ai_evidence_snap": harness.get("ai_evidence_snap"),
               "ai_forward_quote_gate": harness.get("ai_forward_quote_gate"),
               "rows": len(data.get("results") or []), "by_surface": {}, "examples": {}}
        for r in data.get("results") or []:
            excerpt = r.get("grounding_excerpt")
            sections = r.get("raw_sections")
            if not isinstance(excerpt, str) or not excerpt or not isinstance(sections, dict):
                continue
            norm = prov.normalize_for_match(excerpt)
            for surface, value in _surfaces(sections):
                cls = classify(value, norm)
                bucket = run["by_surface"].setdefault(surface, {})
                bucket[cls] = bucket.get(cls, 0) + 1
                verdicts = _verdicts(surface, value, norm)
                vb = run.setdefault("verdicts_by_surface", {}).setdefault(surface, {})
                tb = totals.setdefault(surface, {"boundary": {}, "verdicts": {}})
                tb["boundary"][cls] = tb["boundary"].get(cls, 0) + 1
                for key, val in verdicts.items():
                    label = f"{key}={val}"
                    vb[label] = vb.get(label, 0) + 1
                    tb["verdicts"][label] = tb["verdicts"].get(label, 0) + 1
                if "enriched" in verdicts and not verdicts["enriched_equals_build_evidence"]:
                    run.setdefault("forward_quote_presentation_changes", []).append({
                        "ticker": r.get("ticker"), "value": value[:240], "class": cls, **verdicts})
                if cls in ("only_inner_quoted_span", "full_after_wrapping_quote_strip"):
                    run["examples"].setdefault(f"{surface}:{cls}", []).append({
                        "ticker": r.get("ticker"), "filing_type": r.get("filing_type"), "run": r.get("run"),
                        "accession": (r.get("coverage_inventory") or {}).get("accession"),
                        "excerpt_sha256": (r.get("coverage_inventory") or {}).get("excerpt_sha256"),
                        "value": value[:240], "quoted_span": prov.extract_quoted_span(value)[:160]})
        report["runs"].append(run)
    report["totals"] = totals
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    for run in report["runs"]:
        print(os.path.basename(run["artifact"]), "snap", run["ai_evidence_snap"], "fqg", run["ai_forward_quote_gate"])
        for s, b in sorted(run["by_surface"].items()):
            print("  ", s, b)
        for s, b in sorted(run.get("verdicts_by_surface", {}).items()):
            print("   V", s, b)
        for k, v in run["examples"].items():
            print("   EX", k, len(v), json.dumps(v[0], ensure_ascii=False)[:400])
        print("   forward-quote presentation changes:", len(run.get("forward_quote_presentation_changes", [])))
    print("TOTALS", json.dumps(report["totals"], indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
