"""Classify every retained Copilot generation in a corpus of copilot-eval reports (offline).

Each generation's raw candidate is fed through the production scanner, citation parser and
``_verify_citations`` (main's code), so the verdict and its class (published evidence, regenerable
mismatch, terminal) are production's own. Alongside it the script records WHY each referenced text
citation fails: missing declaration, duplicate declaration, quoted label, under the 24-character floor,
elided, or a long mismatch. No provider call, no network, no database.

Usage (from anywhere): python -I classify_corpus.py <backend_dir> <out.jsonl> <report.json> [...]
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from types import SimpleNamespace

BACKEND = sys.argv[1]
sys.path.insert(0, BACKEND)
os.environ.setdefault("SECRET_KEY", "offline-classifier-0123456789abcdef0123456789")
os.environ.setdefault("SKIP_REDIS_INIT", "true")
for key in ("DEEPSEEK_API_KEY", "OPENAI_BASE_URL"):
    os.environ.pop(key, None)
os.environ["OPENAI_API_KEY"] = "offline-classifier-makes-no-provider-call"  # the client wants one at import

import logging  # noqa: E402

logging.disable(logging.CRITICAL)

from app.services import citation_markers  # noqa: E402
from app.services.copilot import envelope  # noqa: E402
from app.services.copilot.exceptions import _RegenerableEvidenceMismatch, _UnpublishableAnswer  # noqa: E402
from app.services.copilot_service import _COPILOT_MARKER_RE, _SentinelScanner  # noqa: E402
from app.services.provenance_service import (  # noqa: E402
    _MIN_VERIFIABLE_LEN,
    normalize_for_match,
    strip_wrapping_quotes,
    verify_whole_excerpt_in_text,
)

ELLIPSIS = re.compile(r"\.\.\.|…")
FILING = SimpleNamespace(document_url="https://www.sec.gov/Archives/edgar/data/1/1/x.htm", sec_url=None)
_norm_cache: dict[str, str] = {}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalized(source: str) -> str:
    key = sha(source)
    if key not in _norm_cache:
        _norm_cache[key] = normalize_for_match(source)
    return _norm_cache[key]


def citation_reasons(cite: dict, norm_source: str) -> list[str]:
    excerpt = cite["excerpt"].strip()
    label = cite.get("section") or cite.get("section_ref")
    reasons = []
    if envelope.section_label_is_quoted(label):
        reasons.append("quoted_label")
    if not verify_whole_excerpt_in_text(excerpt, norm_source):
        core = normalize_for_match(strip_wrapping_quotes(excerpt))
        if len(core) < _MIN_VERIFIABLE_LEN:
            reasons.append("short")
        elif ELLIPSIS.search(excerpt):
            reasons.append("elided")
        else:
            reasons.append("mismatch")
    return reasons


def classify(candidate: str, source: str) -> dict:
    scanner = _SentinelScanner()
    scanner.feed(candidate)
    scanner.flush()
    out: dict = {"mode": scanner.mode}
    if scanner.mode == "not_disclosed":
        return out
    if scanner.mode != "citations":
        out["stage"] = "missing_envelope"
        return out
    try:
        citations, _followups = envelope._parse_citations("".join(scanner.citation_buffer))
    except _UnpublishableAnswer as exc:
        out["stage"] = "parse"
        out["parse_error"] = str(exc)
        return out
    answer = "".join(scanner.answer_parts).strip()
    answer = citation_markers.expand_citation_marker_groups(
        answer, ref_re=citation_markers.COPILOT_GROUP_MEMBER_RE,
        normalize=citation_markers.copilot_normalize_ref, require_re=citation_markers.MARKER_REF_RE,
    )
    referenced = {re.sub(r"\s+", "", m.group(1)).upper() for m in _COPILOT_MARKER_RE.finditer(answer)}
    text_refs = sorted(k for k in referenced if not k.startswith("F"))
    fact_refs = sorted(k for k in referenced if k.startswith("F"))
    norm_source = normalized(source)
    by_key: dict[str, list[dict]] = {}
    for cite in citations:
        by_key.setdefault(str(cite["n"]), []).append(cite)
    per_ref = {}
    for key in text_refs:
        decls = by_key.get(key, [])
        reasons: list[str] = []
        if not decls:
            reasons.append("missing")
        if len({json.dumps(d, sort_keys=True) for d in decls}) > 1:
            reasons.append("collision")
        for d in decls:
            reasons.extend(r for r in citation_reasons(d, norm_source) if r not in reasons)
        per_ref[key] = {
            "reasons": reasons,
            "excerpts": [{"text": d["excerpt"][:200], "norm_len": len(normalize_for_match(strip_wrapping_quotes(d["excerpt"].strip()))),
                          "verified": verify_whole_excerpt_in_text(d["excerpt"].strip(), norm_source)} for d in decls],
        }
    unreferenced_verified = [str(c["n"]) for c in citations if str(c["n"]) not in referenced
                             and verify_whole_excerpt_in_text(c["excerpt"].strip(), norm_source)]
    try:
        envelope._verify_citations(citations, FILING, norm_source, referenced)
        verdict = "ok"
    except _RegenerableEvidenceMismatch:
        verdict = "regenerable"
    except _UnpublishableAnswer:
        verdict = "terminal"
    out.update({
        "stage": "verify", "verify": verdict, "text_refs": text_refs, "fact_refs": fact_refs,
        "n_declarations": len(citations), "per_ref": per_ref, "unreferenced_verified": unreferenced_verified,
        "failing_reasons": sorted({r for v in per_ref.values() for r in v["reasons"]}),
    })
    return out


def generations(row: dict) -> list[dict]:
    trace = row.get("tool_trace") or {}
    gens = trace.get("generation_attempts")
    if gens:
        return [{"index": g.get("generation_index", i), "candidate": "".join(g.get("candidate_deltas") or []),
                 "withheld": g.get("withheld_reasons") or [],
                 "system": (g.get("initial_messages") or [{}])[0].get("content", "")} for i, g in enumerate(gens)]
    msgs = trace.get("initial_messages") or (row.get("inputs") or {}).get("initial_messages") or [{}]
    return [{"index": 0, "candidate": "".join(trace.get("candidate_deltas") or []),
             "withheld": trace.get("withheld_reasons") or [], "system": msgs[0].get("content", ""), "aggregate": True}]


def main() -> None:
    out_path = sys.argv[2]
    seen_reports: set[str] = set()
    with open(out_path, "w") as out:
        for path in sys.argv[3:]:
            try:
                report = json.load(open(path))
            except (OSError, ValueError) as exc:
                print(f"skip {path}: {exc}", file=sys.stderr)
                continue
            ident = sha(json.dumps([report.get("timestamp"), report.get("source_sha"), report.get("summary")], sort_keys=True))
            if ident in seen_reports:
                continue
            seen_reports.add(ident)
            base = os.path.basename(path)
            for row in report.get("results", []):
                source = (row.get("inputs") or {}).get("source_text") or ""
                gens = generations(row)
                for gen in gens:
                    rec = {
                        "report": base, "timestamp": report.get("timestamp"), "source_sha": report.get("source_sha"),
                        "ticker": row.get("ticker"), "accession": row.get("accession_number"),
                        "question_id": row.get("question_id"), "run_index": row.get("run_index"),
                        "gen_index": gen["index"], "n_gens": len(gens), "aggregate": gen.get("aggregate", False),
                        "row_complete": row.get("terminal_complete"), "row_error": (row.get("error") or {}).get("withheld_reason")
                        or (row.get("error") or {}).get("type"),
                        "recorded_withheld": gen["withheld"], "system_sha": sha(gen["system"])[:12],
                        "evidence_retry_prompt": "previous candidate failed source matching" in gen["system"],
                        "source_text_sha": sha(source)[:12], "source_len": len(source),
                    }
                    rec.update(classify(gen["candidate"], source) if gen["candidate"] else {"mode": "no_candidate"})
                    out.write(json.dumps(rec) + "\n")
    print(f"reports={len(seen_reports)}", file=sys.stderr)


if __name__ == "__main__":
    main()
