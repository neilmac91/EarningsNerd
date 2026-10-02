"""Mutation proofs M1-M8 for the cite-fix change. Applies each mutation to the committed code in
/home/user/wt/cite-fix, runs the owner tests, records the failing count and names, restores the file
with `git checkout --`, and asserts `git status --porcelain` is clean before the next mutation."""
import json
import os
import re
import subprocess
import sys

WT = "/home/user/wt/cite-fix"
BE = WT + "/backend"
SP = "/tmp/claude-0/-home-user-EarningsNerd/4aaef390-9924-5295-aa90-251d71b700b2/scratchpad"
PROV = "backend/app/services/provenance_service.py"
COP = "backend/app/services/copilot_service.py"
OWNERS = ["tests/unit/test_copilot.py", "tests/unit/test_copilot_prose_quotations.py",
          "tests/unit/test_provenance_service.py", "tests/unit/test_forward_quote_gate.py"]

WHOLE_BODY = """    needle = normalize_for_match(strip_wrapping_quotes(excerpt))
    if len(needle) < _MIN_VERIFIABLE_LEN:
        return False
    return needle in normalized_source"""

MUTATIONS = [
    ("M1", "Copilot back on verify_excerpt_in_text", "regression must fail", [
        (COP, "    strip_wrapping_quotes,\n    verify_whole_excerpt_in_text,\n)",
              "    strip_wrapping_quotes,\n    verify_excerpt_in_text,\n    verify_whole_excerpt_in_text,\n)"),
        (COP, "verified = verify_whole_excerpt_in_text(excerpt, normalized_source) and not (",
              "verified = verify_excerpt_in_text(excerpt, normalized_source) and not ("),
    ], "test_service_withholds_excerpt_verified_only_by_inner_quoted_span"),
    ("M2", "drop normalization in the helper", "folded control must fail", [
        (PROV, "    needle = normalize_for_match(strip_wrapping_quotes(excerpt))\n    if len(needle) < _MIN_VERIFIABLE_LEN:\n        return False\n    return needle in normalized_source\n\n\ndef build_text_fragment_url",
               "    needle = strip_wrapping_quotes(excerpt)\n    if len(needle) < _MIN_VERIFIABLE_LEN:\n        return False\n    return needle in normalized_source\n\n\ndef build_text_fragment_url"),
    ], "test_service_publishes_typography_and_whitespace_folded_excerpt"),
    ("M3", "drop the wrapping-quote strip in the helper", "wrapped control must fail", [
        (PROV, "    needle = normalize_for_match(strip_wrapping_quotes(excerpt))\n    if len(needle) < _MIN_VERIFIABLE_LEN:\n        return False\n    return needle in normalized_source\n\n\ndef build_text_fragment_url",
               "    needle = normalize_for_match(excerpt.strip())\n    if len(needle) < _MIN_VERIFIABLE_LEN:\n        return False\n    return needle in normalized_source\n\n\ndef build_text_fragment_url"),
    ], "test_service_publishes_excerpt_wrapped_in_one_quote_pair"),
    ("M4", "helper uses extract_quoted_span", "regression must fail", [
        (PROV, "    needle = normalize_for_match(strip_wrapping_quotes(excerpt))\n    if len(needle) < _MIN_VERIFIABLE_LEN:\n        return False\n    return needle in normalized_source\n\n\ndef build_text_fragment_url",
               "    needle = normalize_for_match(extract_quoted_span(excerpt))\n    if len(needle) < _MIN_VERIFIABLE_LEN:\n        return False\n    return needle in normalized_source\n\n\ndef build_text_fragment_url"),
    ], "test_service_withholds_excerpt_verified_only_by_inner_quoted_span"),
    ("M5", "drop the floor in the helper", "below-floor control must fail", [
        (PROV, WHOLE_BODY + "\n\n\ndef build_text_fragment_url",
               "    needle = normalize_for_match(strip_wrapping_quotes(excerpt))\n    return bool(needle) and needle in normalized_source\n\n\ndef build_text_fragment_url"),
    ], "test_service_withholds_referenced_excerpt_below_the_floor"),
    ("M6", "whole-excerpt applied globally inside verify_excerpt_in_text", "a provenance prefix test must fail", [
        (PROV, "    needle = normalize_for_match(extract_quoted_span(excerpt))\n    if len(needle) < _MIN_VERIFIABLE_LEN:\n        return False\n    return needle in normalized_source\n\n\ndef strip_wrapping_quotes",
               "    needle = normalize_for_match(strip_wrapping_quotes(excerpt))\n    if len(needle) < _MIN_VERIFIABLE_LEN:\n        return False\n    return needle in normalized_source\n\n\ndef strip_wrapping_quotes"),
    ], "test_verifies_quoted_excerpt_case_and_whitespace_insensitive"),
    ("M7", "remove the section_ref guard", "its test must fail", [
        (COP, "        verified = verify_whole_excerpt_in_text(excerpt, normalized_source) and not (\n            section_ref and any(mark in section_ref for mark in _SECTION_REF_QUOTE_MARKS)\n        )\n",
              "        verified = verify_whole_excerpt_in_text(excerpt, normalized_source)\n"),
    ], "test_service_withholds_referenced_citation_whose_section_ref_has_a_quote_mark"),
    ("M8", "_enrich_forward_quotes back on plain build_evidence", "forward-quote test must fail", [
        (PROV, "                text if whole else None, section_ref, base_url, normalized_source",
               "                text, section_ref, base_url, normalized_source"),
    ], "test_quote_contiguous_only_through_an_inner_quoted_span_is_unverified"),
]


def git(*args):
    return subprocess.run(["git", *args], cwd=WT, capture_output=True, text=True, check=True).stdout


def run_owners():
    env = {k: v for k, v in os.environ.items()
           if k not in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY")}
    proc = subprocess.run(["/home/user/venv/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                           "-W", "ignore", "-rf", *OWNERS], cwd=BE, env=env, capture_output=True, text=True)
    db = os.path.join(BE, "earningsnerd.db")
    if os.path.exists(db):
        os.rename(db, os.path.join(SP, "stale-dbs", f"earningsnerd.cite-fix-mut.{os.getpid()}.{len(os.listdir(SP + '/stale-dbs'))}.db"))
    tail = [ln for ln in proc.stdout.splitlines() if re.search(r"\d+ (passed|failed)", ln)]
    failed = sorted({ln.split(" ", 1)[1].split(" - ")[0] for ln in proc.stdout.splitlines() if ln.startswith("FAILED ")})
    return proc.returncode, (tail[-1] if tail else proc.stdout[-500:]), failed


def main():
    assert git("status", "--porcelain") == "", "worktree must be clean"
    head = git("rev-parse", "HEAD").strip()
    results = []
    for mid, what, expect, edits, must_fail in MUTATIONS:
        touched = []
        for rel, old, new in edits:
            path = os.path.join(WT, rel)
            src = open(path, encoding="utf-8").read()
            assert src.count(old) == 1, (mid, rel, old[:60])
            open(path, "w", encoding="utf-8").write(src.replace(old, new))
            touched.append(rel)
        diff = git("diff", "--stat")
        rc, tail, failed = run_owners()
        git("checkout", "--", *sorted(set(touched)))
        clean = git("status", "--porcelain") == ""
        hit = any(must_fail in name for name in failed)
        row = {"id": mid, "mutation": what, "expectation": expect, "exit": rc, "summary": tail,
               "failed_count": len(failed), "failed": failed, "required_test": must_fail,
               "required_test_failed": hit, "diffstat": diff.strip().splitlines()[-1] if diff.strip() else "",
               "restored_clean": clean}
        results.append(row)
        print(f"{mid} | {what} | {tail} | required {must_fail} failed={hit} | clean={clean}", flush=True)
        for name in failed:
            print("    FAILED", name, flush=True)
        assert clean, mid
    rc, tail, failed = run_owners()
    print("POST-RESTORE owners:", tail, "failed:", failed)
    json.dump({"head": head, "results": results, "post_restore": {"exit": rc, "summary": tail, "failed": failed}},
              open(os.path.join(SP, "cite-fix", "mutations.json"), "w"), indent=1)
    sys.exit(0 if all(r["required_test_failed"] and r["restored_clean"] for r in results) and rc == 0 else 1)


if __name__ == "__main__":
    main()
