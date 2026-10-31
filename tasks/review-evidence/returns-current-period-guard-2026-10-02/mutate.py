#!/usr/bin/env python3
"""Mutation proofs for the returns current-period guard.

Each mutation rewrites backend/app/services/ai/markdown_render.py, runs the guard's owner test file
plus the locked render file, records the pytest summary and failed node ids, then restores the file
with `git checkout --`. Tracked files must be clean before and after.

Usage (cwd = the worktree root; real provider keys unset):

    python tasks/review-evidence/returns-current-period-guard-2026-10-02/mutate.py <out.json>
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

TARGET = "backend/app/services/ai/markdown_render.py"
GUARD = "            if ni_period is not None and return_ratio_period(current) not in (None, ni_period):\n                return None\n"
TESTS = ["tests/unit/test_xbrl_narrative_section.py", "tests/unit/test_structured_markdown_render.py"]
MUTATIONS = {
    "M1_remove_guard": (GUARD, ""),
    "M2_invert_period_comparison": (GUARD, GUARD.replace(" not in (None, ni_period)", " in (None, ni_period)")),
    "M3_guard_roe_only": (GUARD, GUARD.replace("if ni_period", 'if key == "return_on_equity" and ni_period')),
}
PROVIDER_KEYS = ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_BASE_URL")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def pytest() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in PROVIDER_KEYS}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf", *TESTS],
                          cwd="backend", capture_output=True, text=True, env=env, timeout=900)
    lines = proc.stdout.strip().splitlines()
    return {"exit": proc.returncode, "summary": lines[-1] if lines else "",
            "failed": sorted(set(re.findall(r"^FAILED (.+?)(?: - .*)?$", proc.stdout, re.M)))}


def main() -> int:
    if git("status", "--porcelain", "--untracked-files=no"):
        sys.exit("tree not clean")
    original = open(TARGET).read()
    out = {"head": git("rev-parse", "HEAD").strip(), "tests": TESTS, "baseline": pytest(), "mutations": {}}
    for name, (old, new) in MUTATIONS.items():
        assert original.count(old) == 1, name
        with open(TARGET, "w") as fh:
            fh.write(original.replace(old, new))
        try:
            out["mutations"][name] = {"diff": git("diff", "--", TARGET), **pytest()}
        finally:
            git("checkout", "--", TARGET)
    out["clean_after"] = git("status", "--porcelain", "--untracked-files=no") == ""
    with open(sys.argv[1], "w") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")
    print(f"baseline: {out['baseline']['summary']}")
    for name, r in out["mutations"].items():
        print(f"{name}: {r['summary']}")
        for node in r["failed"]:
            print(f"  {node}")
    print(f"clean_after={out['clean_after']}")
    killed = all(r["exit"] != 0 for r in out["mutations"].values())
    return 0 if killed and out["baseline"]["exit"] == 0 and out["clean_after"] else 1


if __name__ == "__main__":
    sys.exit(main())
