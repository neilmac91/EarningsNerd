"""Offline replay: are published Copilot citation excerpts contiguous in their filing source?

Mechanical boundary check only (no financial judging, no network, no provider calls). For every
retained Copilot eval artifact (``copilot-*/copilot-eval.json``) and every published citation it
recompute, with the PRODUCTION helpers imported from the worktree under test:

* ``full``       — is the FULL displayed excerpt contiguous in ``normalize_for_match(source)``?
* ``unwrapped``  — same, after stripping ONE pair of quote marks that wrap the entire excerpt
                   (the ``forward_quote_gate._strip_wrapping_quotes`` rule; never an inner span).
* ``quoted``     — is ``extract_quoted_span(excerpt)`` (what production actually checks) contiguous?
* ``prod``       — ``verify_excerpt_in_text(excerpt, normalized_source)`` (main's Copilot verdict).
* ``new_whole``  — ``verify_whole_excerpt_in_text(excerpt, normalized_source)`` (the fix's helper).
* ``new_copilot``— ``copilot_service._verify_citations`` itself (whole excerpt AND quote-free
                   ``section_ref``), called with an empty ``referenced`` set so it never raises.

cite-fix adaptation (2026-10-02): adds the two ``new_*`` columns, imported from the worktree under
test (``/home/user/wt/cite-fix``), and counts quote marks in ``section_ref`` with the production
``_SECTION_REF_QUOTE_MARKS`` constant.

A published text citation is AFFECTED when it shipped ``verified: True`` but neither the full nor
the wrapper-stripped excerpt is contiguous: only an inner quoted span was verified while the
whole string was displayed. ``section_ref`` values are checked the same way: does the free-text
label carry a quoted span, and is that span (or the whole label) in the source?

XBRL/tool citations (``section_ref`` starting with "XBRL", the scorer's own rule) are application-
built from financial facts, never verified by ``verify_excerpt_in_text``; they are counted and
excluded from the text checks.

Usage (from the worktree's backend dir, keys unset, hermetic dummy Settings env):
    python replay_excerpt_boundaries.py <scratchpad> <out.json>
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import subprocess
import sys

# Hermetic dummy Settings (mirrors tests/conftest.py); never real credentials.
os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-long-enough-123")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_mock_stripe_key_12345")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_mock_stripe_webhook_12345")
os.environ.setdefault("SKIP_REDIS_INIT", "true")
for _k in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY"):
    os.environ.pop(_k, None)
# copilot_service imports openai_service, which constructs (never calls) a client at import. Use the
# SAME in-process dummy key tests/conftest.py sets, and a discard-port base URL so that even an
# accidental call could not leave this machine. No request is made by this script.
os.environ["OPENAI_API_KEY"] = "sk-test-key-for-mocking"
os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:9/v1"

from types import SimpleNamespace  # noqa: E402

from app.services import copilot_service  # noqa: E402
from app.services import provenance_service as prov  # noqa: E402

normalize_for_match = prov.normalize_for_match
extract_quoted_span = prov.extract_quoted_span
verify_excerpt_in_text = prov.verify_excerpt_in_text
verify_whole_excerpt_in_text = prov.verify_whole_excerpt_in_text
_SECTION_REF_QUOTE_MARKS = copilot_service._SECTION_REF_QUOTE_MARKS
_FILING = SimpleNamespace(document_url="https://www.sec.gov/Archives/edgar/data/0/0/doc.htm", sec_url=None)
_QUOTED_RE = prov._QUOTED_RE
_MIN = prov._MIN_VERIFIABLE_LEN

_OPEN = "\"'“‘"
_CLOSE = "\"'”’"
_ANY_QUOTE = set("\"“”")


def _sha(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def strip_wrapping_quotes(text: str) -> str:
    t = text.strip()
    if len(t) >= 2 and t[0] in _OPEN and t[-1] in _CLOSE:
        return t[1:-1].strip()
    return t


def contiguous(text: str, norm_source: str) -> bool:
    needle = normalize_for_match(text)
    return bool(needle) and needle in norm_source


def is_xbrl(cite: dict) -> bool:
    return str(cite.get("section_ref") or "").strip().upper().startswith("XBRL")


def check_text_citation(cite: dict, norm_source: str) -> dict:
    excerpt = str(cite.get("excerpt") or "")
    stripped = excerpt.strip()
    quoted = extract_quoted_span(excerpt)
    has_inner_quote = quoted != stripped
    full = contiguous(stripped, norm_source)
    unwrapped_text = strip_wrapping_quotes(stripped)
    unwrapped = contiguous(unwrapped_text, norm_source)
    quoted_ok = contiguous(quoted, norm_source) and len(normalize_for_match(quoted)) >= _MIN
    prod = verify_excerpt_in_text(excerpt, norm_source)
    new_whole = verify_whole_excerpt_in_text(excerpt, norm_source)
    declaration = {"n": 1, "excerpt": excerpt, "section": cite.get("section_ref")}
    new_copilot = copilot_service._verify_citations([declaration], _FILING, norm_source, set())["1"]
    published_verified = cite.get("verified") is True
    if full:
        boundary = "full_contiguous"
    elif unwrapped:
        boundary = "full_contiguous_after_wrapping_quote_strip"
    elif quoted_ok and has_inner_quote:
        boundary = "only_inner_quoted_span_contiguous"
    else:
        boundary = "not_contiguous"
    affected = published_verified and boundary in ("only_inner_quoted_span_contiguous", "not_contiguous")
    return {
        "n": cite.get("n"),
        "displayed_excerpt": excerpt,
        "verified_span": quoted,
        "has_inner_quoted_span": has_inner_quote,
        "published_verified": published_verified,
        "prod_verify_excerpt_in_text": prod,
        "new_verify_whole_excerpt_in_text": new_whole,
        "new_copilot_verified": new_copilot["verified"],
        "new_copilot_excerpt_bytes_unchanged": new_copilot["excerpt"] == excerpt.strip(),
        "new_copilot_fragment_url": new_copilot["fragment_url"],
        "main_fragment_url": prov.build_text_fragment_url(_FILING.document_url, excerpt.strip()) if prod else _FILING.document_url,
        "full_excerpt_contiguous": full,
        "full_excerpt_contiguous_after_wrapping_quote_strip": unwrapped,
        "quoted_span_contiguous": quoted_ok,
        "full_excerpt_normalized_len": len(normalize_for_match(stripped)),
        "boundary": boundary,
        "affected": affected,
    }


def check_section_ref(ref, norm_source: str) -> dict:
    if not isinstance(ref, str) or not ref.strip():
        return {"section_ref": ref, "kind": "absent"}
    m = _QUOTED_RE.search(ref)
    has_any_quote_char = any(ch in _SECTION_REF_QUOTE_MARKS for ch in ref)
    out = {
        "section_ref": ref,
        "has_quoted_span": bool(m),
        "has_any_double_quote_char": has_any_quote_char,
        "whole_label_contiguous": contiguous(ref, norm_source),
    }
    if m:
        span = m.group(1).strip()
        out["quoted_span"] = span
        out["quoted_span_contiguous"] = contiguous(span, norm_source)
        out["kind"] = "quoted_span_present" if out["quoted_span_contiguous"] else "quoted_span_ABSENT_from_source"
    else:
        out["kind"] = "plain_label"
    return out


def main(scratch: str, out_path: str) -> None:
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    report = {
        "code_binding": {
            "git_head": head,
            "provenance_service_sha256": _sha(prov.__file__),
            "copilot_service_sha256": _sha(copilot_service.__file__),
            "provenance_service_path": prov.__file__,
            "helpers": ["normalize_for_match", "extract_quoted_span", "verify_excerpt_in_text",
                        "verify_whole_excerpt_in_text", "copilot_service._verify_citations"],
            "min_verifiable_len": _MIN,
        },
        "runs": [],
    }
    norm_cache: dict[str, str] = {}
    totals = {"rows": 0, "citations": 0, "xbrl_citations": 0, "text_citations": 0,
              "text_verified_true": 0, "affected": 0, "boundary": {},
              "text_prod_verify_excerpt_in_text_true": 0, "text_new_whole_true": 0,
              "text_new_copilot_verified_true": 0, "text_new_copilot_excerpt_bytes_unchanged": 0,
              "text_verdict_changes": [], "text_fragment_url_unchanged": 0,
              "section_refs_with_quoted_span": 0, "section_refs_quoted_span_absent": 0,
              "section_refs_with_any_quote_char": 0}
    for path in sorted(glob.glob(os.path.join(scratch, "copilot-*", "copilot-eval.json"))):
        run_id = os.path.basename(os.path.dirname(path)).removeprefix("copilot-")
        data = json.load(open(path))
        run = {
            "run": run_id,
            "artifact": path,
            "artifact_sha256": _sha(path),
            "timestamp": data.get("timestamp"),
            "source_sha": data.get("source_sha"),
            "requested_model": data.get("requested_model"),
            "accepted": data.get("accepted"),
            "rows": len(data.get("results") or []),
            "citations": 0, "xbrl_citations": 0, "text_citations": 0, "text_verified_true": 0,
            "affected": 0, "boundary": {}, "section_ref": {}, "source_bindings": {},
            "text_citation_rows": [], "affected_rows": [], "rows_without_source": [],
        }
        for idx, row in enumerate(data.get("results") or []):
            ident = f"{row.get('ticker')} {row.get('question_id')} d{row.get('run_index')}"
            source = (row.get("inputs") or {}).get("source_text")
            cites = row.get("citations") or []
            if not isinstance(source, str) or not source.strip():
                run["rows_without_source"].append({"row": idx, "id": ident, "citations": len(cites)})
                continue
            src_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
            acc = row.get("accession_number") or (row.get("inputs") or {}).get("accession_number")
            run["source_bindings"].setdefault(acc, set()).add(src_sha)
            if src_sha not in norm_cache:
                norm_cache[src_sha] = normalize_for_match(source)
            norm_source = norm_cache[src_sha]
            for cite in cites:
                run["citations"] += 1
                if is_xbrl(cite):
                    run["xbrl_citations"] += 1
                    continue
                run["text_citations"] += 1
                res = check_text_citation(cite, norm_source)
                ref = check_section_ref(cite.get("section_ref"), norm_source)
                if res["published_verified"]:
                    run["text_verified_true"] += 1
                totals["text_prod_verify_excerpt_in_text_true"] += res["prod_verify_excerpt_in_text"]
                totals["text_new_whole_true"] += res["new_verify_whole_excerpt_in_text"]
                totals["text_new_copilot_verified_true"] += res["new_copilot_verified"]
                totals["text_new_copilot_excerpt_bytes_unchanged"] += res["new_copilot_excerpt_bytes_unchanged"]
                totals["text_fragment_url_unchanged"] += res["new_copilot_fragment_url"] == res["main_fragment_url"]
                if res["new_copilot_verified"] != res["prod_verify_excerpt_in_text"]:
                    totals["text_verdict_changes"].append({"run": run_id, "row": idx, "id": ident})
                run["boundary"][res["boundary"]] = run["boundary"].get(res["boundary"], 0) + 1
                run["section_ref"][ref["kind"]] = run["section_ref"].get(ref["kind"], 0) + 1
                if ref.get("has_any_double_quote_char"):
                    totals["section_refs_with_any_quote_char"] += 1
                entry = {"row": idx, "id": ident, "accession": acc, "source_sha256": src_sha,
                         "excerpt_check": res, "section_ref_check": ref}
                run["text_citation_rows"].append(entry)
                if res["affected"] or ref["kind"] == "quoted_span_ABSENT_from_source":
                    run["affected_rows"].append(entry)
                if res["affected"]:
                    run["affected"] += 1
        run["source_bindings"] = {k: sorted(v) for k, v in run["source_bindings"].items()}
        for key in ("citations", "xbrl_citations", "text_citations", "text_verified_true", "affected"):
            totals[key] += run[key]
        totals["rows"] += run["rows"]
        for k, v in run["boundary"].items():
            totals["boundary"][k] = totals["boundary"].get(k, 0) + v
        totals["section_refs_with_quoted_span"] += sum(
            v for k, v in run["section_ref"].items() if k.startswith("quoted_span"))
        totals["section_refs_quoted_span_absent"] += run["section_ref"].get("quoted_span_ABSENT_from_source", 0)
        report["runs"].append(run)
    report["totals"] = totals
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    print(json.dumps({"code_binding": report["code_binding"], "totals": totals}, indent=1))
    for run in report["runs"]:
        print(run["run"], {k: run[k] for k in ("rows", "citations", "xbrl_citations", "text_citations",
                                               "text_verified_true", "affected", "boundary", "section_ref")},
              "no_source:", len(run["rows_without_source"]))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
