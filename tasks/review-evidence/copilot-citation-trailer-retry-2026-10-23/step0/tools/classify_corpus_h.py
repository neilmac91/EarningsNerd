"""Classify every retained Copilot generation in a corpus of copilot-eval reports (offline).

Each generation's raw candidate is fed through the production scanner, citation parser and
``_verify_citations`` (main's code), so the verdict and its class (published evidence, regenerable
mismatch, terminal) are production's own. Alongside it the script records WHY each referenced text
citation fails: missing declaration, duplicate declaration, quoted label, under the 24-character floor,
elided, or a long mismatch. No provider call, no network, no database.

Step-0 adaptation for PR #1551 (H's code, app code = d4d9c510): see the "H:" comments. It also records
H's own first-generation verdict (``h_*`` fields): the stages replayed offline through H's code
(scanner fed delta by delta, ``_admit_not_disclosed``, ``_parse_citations``, ``_verify_citations``)
and, for a candidate that passes ``_verify_citations``, the run's recorded withhold reason for the
stages after it (claim repair and resolution need the run's database; quotation check on the
resolved answer). ``_RegenerableCitationTrailer`` (new in H) is a parse-stage class of its own.

Usage (from anywhere): python -I classify_corpus_h.py <backend_dir> <out.jsonl> <report.json> [...]
"""
from __future__ import annotations

import asyncio
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
from app.services import copilot_service  # noqa: E402  # H: _admit_not_disclosed, chooser inputs
from app.services.copilot import envelope  # noqa: E402
from app.services.copilot import prompt  # noqa: E402  # H: the chooser (_retry_guidance)
from app.services.copilot.exceptions import (  # noqa: E402
    _RegenerableCitationTrailer,  # H: new class; ImportError here means the backend is not H's
    _RegenerableEvidenceMismatch,
    _UnpublishableAnswer,
)
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
# H: the reasons production raises before or at _verify_citations; any other recorded reason comes from a
# later stage (resolution, final-citation check, quotation check) that this offline replay does not run.
PRE_VERIFY_REASON_PREFIXES = (
    "Missing citation envelope", "Incomplete citation array", "Unclosed citation fence", "Duplicate citation field",
    "Non-JSON citation value", "Citation declaration is not an array", "Invalid citation declaration",
    "Unexpected citation trailer", "Unverified or ambiguous referenced citation",
    "Answer prose precedes not-disclosed verdict", "Missing not-disclosed followups envelope",
    "Empty not-disclosed reason", "Contradictory not-disclosed envelope", "Incomplete not-disclosed followups array",
    "Invalid not-disclosed followups array",
)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalized(source: str) -> str:
    key = sha(source)
    if key not in _norm_cache:
        _norm_cache[key] = normalize_for_match(source)
    return _norm_cache[key]


def chooser(exc: Exception) -> str:
    """H: what H's chooser does with this first-generation rejection (no candidate text is read)."""
    guidance = prompt._retry_guidance(exc, copilot_service._RETRYABLE_QUOTATION_FAILURES)
    if not guidance:
        return "terminal"
    if isinstance(exc, _RegenerableEvidenceMismatch):
        return "retry_citation"
    if isinstance(exc, _RegenerableCitationTrailer):
        return "retry_trailer"
    return "retry_quotation"


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


def classify(deltas: list[str], source: str) -> dict:
    scanner = _SentinelScanner()
    for delta in deltas:  # H: fed delta by delta, as the service does (it skips empty deltas)
        if delta:
            scanner.feed(delta)
    scanner.flush()
    out: dict = {"mode": scanner.mode}
    norm_source = normalized(source)
    if scanner.mode == "not_disclosed":
        # H: replay the service's own not-disclosed admission (offline: envelope + quotation check).
        try:
            asyncio.run(copilot_service._admit_not_disclosed(scanner, norm_source))
            out.update({"stage": "not_disclosed", "h_exc": None})
        except _UnpublishableAnswer as exc:
            out.update({"stage": "not_disclosed", "h_exc": exc})
        return out
    if scanner.mode != "citations":
        out["stage"] = "missing_envelope"
        out["h_exc"] = _UnpublishableAnswer("Missing citation envelope")  # H: _admit_answer's first check
        return out
    try:
        citations, _followups = envelope._parse_citations("".join(scanner.citation_buffer))
    except _UnpublishableAnswer as exc:
        out["stage"] = "parse"
        out["parse_error"] = str(exc)
        out["parse_class"] = type(exc).__name__  # H: _RegenerableCitationTrailer vs the terminal base class
        out["h_exc"] = exc
        return out
    answer = "".join(scanner.answer_parts).strip()
    answer = citation_markers.expand_citation_marker_groups(
        answer, ref_re=citation_markers.COPILOT_GROUP_MEMBER_RE,
        normalize=citation_markers.copilot_normalize_ref, require_re=citation_markers.MARKER_REF_RE,
    )
    referenced = {re.sub(r"\s+", "", m.group(1)).upper() for m in _COPILOT_MARKER_RE.finditer(answer)}
    text_refs = sorted(k for k in referenced if not k.startswith("F"))
    fact_refs = sorted(k for k in referenced if k.startswith("F"))
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
    h_exc = None
    try:
        envelope._verify_citations(citations, FILING, norm_source, referenced)
        verdict = "ok"
    except _RegenerableEvidenceMismatch as exc:
        verdict = "regenerable"
        h_exc = exc
    except _UnpublishableAnswer as exc:
        verdict = "terminal"
        h_exc = exc
    quotation_preresolve = None
    if verdict == "ok":
        # H: diagnostic only, never a verdict. The service runs this check on the RESOLVED answer (after claim
        # repair and marker numbering, which need the run's database); here it runs on the answer before
        # resolution, to cross-check the recorded post-verify reason.
        try:
            copilot_service._withhold_unsupported_quotations(norm_source, answer, _followups)
        except _UnpublishableAnswer as exc:
            quotation_preresolve = str(exc)
    out.update({
        "quotation_preresolve": quotation_preresolve,
        "stage": "verify", "verify": verdict, "text_refs": text_refs, "fact_refs": fact_refs,
        "n_declarations": len(citations), "per_ref": per_ref, "unreferenced_verified": unreferenced_verified,
        "failing_reasons": sorted({r for v in per_ref.values() for r in v["reasons"]}),
        "h_exc": h_exc,
    })
    return out


def h_verdict(rec: dict, gen: dict, exc: Exception | None, row_published_now: bool) -> dict:
    """H: production's verdict on this generation under H's code; see the module docstring."""
    recorded = gen["withheld"]
    if gen["provider_error"]:
        return {"h_evaluable": False, "h_status": "provider_error"}
    if exc is not None:
        reason = str(exc)
        detail = "+".join(rec.get("failing_reasons") or []) if rec.get("stage") == "verify" else ""
        label = f"{reason} [{detail}]" if detail else reason
        agree = bool(recorded) and recorded[-1] == reason
        return {"h_evaluable": True, "h_status": "rejected", "h_rejected": True, "h_reason": reason, "h_label": label,
                "h_class": type(exc).__name__, "h_chooser": chooser(exc), "h_source": "replay",
                "recorded_agrees": agree}
    if recorded:
        reason = recorded[-1]
        if reason.startswith(PRE_VERIFY_REASON_PREFIXES):
            # The run's code withheld it at a stage H's replay passes: a code difference, not H's verdict.
            return {"h_evaluable": True, "h_status": "published_by_h_replay_but_recorded_pre_verify",
                    "h_rejected": False, "recorded_agrees": False}
        stand_in = _UnpublishableAnswer(reason)
        return {"h_evaluable": True, "h_status": "rejected", "h_rejected": True, "h_reason": reason,
                "h_label": f"{reason} (recorded, post-verify)", "h_class": "_UnpublishableAnswer",
                "h_chooser": chooser(stand_in), "h_source": "recorded", "recorded_agrees": True}
    if row_published_now:
        return {"h_evaluable": True, "h_status": "published", "h_rejected": False, "recorded_agrees": True}
    return {"h_evaluable": False, "h_status": "no_verdict_recorded"}  # an exception outside the boundary


def generations(row: dict) -> list[dict]:
    trace = row.get("tool_trace") or {}
    gens = trace.get("generation_attempts")
    if gens:
        out = []
        for i, g in enumerate(gens):
            msgs = g.get("initial_messages") or [{}]
            out.append({"index": g.get("generation_index", i), "deltas": list(g.get("candidate_deltas") or []),
                        "withheld": g.get("withheld_reasons") or [],
                        "system": msgs[0].get("content", "") if msgs[0].get("role") == "system" else "",
                        "provider_error": any(c.get("type") == "error" for c in g.get("provider_controls") or [])})
        return out
    msgs = trace.get("initial_messages") or (row.get("inputs") or {}).get("initial_messages") or [{}]
    return [{"index": 0, "deltas": list(trace.get("candidate_deltas") or []),
             "withheld": trace.get("withheld_reasons") or [], "system": msgs[0].get("content", ""), "aggregate": True,
             "provider_error": any(c.get("type") == "error" for c in trace.get("provider_controls") or [])}]


def main() -> None:
    out_path = sys.argv[2]
    seen_reports: dict[str, str] = {}
    with open(out_path, "w") as out:
        for path in sys.argv[3:]:
            try:
                report = json.load(open(path))
            except (OSError, ValueError) as exc:
                print(f"skip {path}: {exc}", file=sys.stderr)
                continue
            ident = sha(json.dumps([report.get("timestamp"), report.get("source_sha"), report.get("summary")], sort_keys=True))
            if ident in seen_reports:
                print(f"duplicate {path} of {seen_reports[ident]}", file=sys.stderr)  # H: name the duplicate
                continue
            seen_reports[ident] = path
            base = path  # H: the full path, since every artifact's report has the same basename
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
                        "provider_error": gen["provider_error"],
                    }
                    candidate = "".join(gen["deltas"])
                    result = classify(gen["deltas"], source) if candidate else {"mode": "no_candidate"}
                    exc = result.pop("h_exc", None)
                    if not candidate and not gen["provider_error"] and gen["withheld"]:
                        # H: an empty stream that reached admission fails its first check; without a recorded
                        # reason the stream raised instead (a stream failure, not a withhold).
                        exc = _UnpublishableAnswer("Missing citation envelope")
                    rec.update(result)
                    # The generation published iff it is the row's last generation and the row completed.
                    published_now = bool(row.get("terminal_complete")) and gen["index"] == gens[-1]["index"]
                    rec.update(h_verdict(rec, gen, exc, published_now))
                    out.write(json.dumps(rec) + "\n")
    print(f"reports={len(seen_reports)}", file=sys.stderr)


if __name__ == "__main__":
    main()
