"""Mutation proofs: each mutation breaks one guarded rule and must turn its named gate red.

Applies one mutation at a time to the backend of the checkout this file sits in, runs the Copilot
test owners, records the pytest summary and FAILED lines, then restores the file with
``git checkout --``. Offline; provider keys are unset for the pytest child. Usage:
    python run_mutations.py <python with pytest> <out.txt>
"""
from __future__ import annotations

import os
import subprocess
import sys

BACKEND = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "backend"))
SERVICE = "app/services/copilot_service.py"
SCORER = "evals/copilot_scorers.py"
TESTS = ["tests/unit/test_copilot.py", "tests/unit/test_copilot_evals.py",
         "tests/unit/test_copilot_live_regressions.py", "tests/unit/test_copilot_prose_quotations.py"]

MUTATIONS = {
    "M1 scorer back on verify_excerpt_in_text": ("test_citation_faithfulness_matches_copilot_publication", [
        (SCORER, "normalize_for_match, verify_whole_excerpt_in_text", "normalize_for_match, verify_excerpt_in_text"),
        (SCORER, "if not verify_whole_excerpt_in_text(", "if not verify_excerpt_in_text("),
    ]),
    "M2 scorer drops the label clause": ("test_citation_faithfulness_matches_copilot_publication", [
        (SCORER, " or section_label_is_quoted(label):", ":"),
    ]),
    "M3 section_ref narrowed back to three marks": ("test_section_ref_rule_withholds_exactly_decision_f_marks", [
        (SERVICE, "return isinstance(label, str) and _QUOTE_MARK_RE.search(label) is not None",
         "return isinstance(label, str) and any(mark in label for mark in '\"“”')"),
    ]),
    "M4 separate drifting literal (F gains U+2033)": ("test_section_ref_rule_withholds_exactly_decision_f_marks", [
        (SERVICE, "return isinstance(label, str) and _QUOTE_MARK_RE.search(label) is not None",
         "return isinstance(label, str) and re.search('[\"\\uff02\\u201c\\u201d\\u201e\\u201f]', label) is not None"),
        (SERVICE, "_QUOTE_MARK_RE = re.compile('[\"\\uff02\\u201c\\u201d\\u201e\\u201f]')",
         "_QUOTE_MARK_RE = re.compile('[\"\\uff02\\u201c\\u201d\\u201e\\u201f\\u2033]')"),
    ]),
}


def pytest(python):
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_BASE_URL")}
    out = subprocess.run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *TESTS], cwd=BACKEND, env=env,
                         capture_output=True, text=True).stdout.splitlines()
    failed = sorted({line.split(" - ")[0].removeprefix("FAILED ") for line in out if line.startswith("FAILED")})
    return out[-1], failed


def main(python, out_path):
    lines = []
    summary, failed = pytest(python)
    lines += ["== baseline (unmutated)", summary, *failed]
    for name, (named_test, edits) in MUTATIONS.items():
        for path, old, new in edits:
            full = os.path.join(BACKEND, path)
            text = open(full, encoding="utf-8").read()
            assert text.count(old) == 1, (name, old)
            open(full, "w", encoding="utf-8").write(text.replace(old, new))
        summary, failed = pytest(python)
        subprocess.run(["git", "checkout", "--", SERVICE, SCORER], cwd=BACKEND, check=True)
        killed = any(named_test in f for f in failed)
        lines += [f"== {name}: named gate {named_test} {'FAILED (killed)' if killed else 'PASSED (survived)'}",
                  summary, *failed]
    summary, failed = pytest(python)
    lines += ["== restored", summary, *failed]
    status = subprocess.run(["git", "status", "--short", "--", "."], cwd=BACKEND, capture_output=True, text=True)
    lines += ["== git status --short backend/ after restore:", status.stdout.strip() or "(clean)"]
    open(out_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
