"""Every relative link in a review-evidence README resolves to a file the repository tracks.

`.gitignore` excludes `*.log`, so a gate log written next to its README silently stays out of the
commit while the README still links it. A reviewer then cannot inspect the claimed evidence.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "tasks" / "review-evidence"
LINK = re.compile(r"\]\(([^)\s]+)\)")


def _tracked() -> set[str] | None:
    """Tracked paths when git metadata is available; otherwise None (fall back to existence)."""
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        return None
    listed = subprocess.run(["git", "ls-files", "-z", "tasks/review-evidence"], cwd=ROOT,  # noqa: S603, S607
                            capture_output=True, check=True).stdout.decode()
    return {path for path in listed.split("\0") if path}


def test_review_evidence_readme_links_resolve_to_tracked_files() -> None:
    tracked = _tracked()
    broken = []
    for readme in sorted(EVIDENCE.glob("**/README.md")):
        for target in LINK.findall(readme.read_text(encoding="utf-8")):
            if re.match(r"[a-z]+:", target) or target.startswith("#"):
                continue
            path = (readme.parent / target.split("#")[0]).resolve()
            try:
                relative = path.relative_to(ROOT).as_posix()
            except ValueError:
                broken.append(f"{readme.relative_to(ROOT)}: {target} (outside the repository)")
                continue
            inside_evidence = relative.startswith("tasks/review-evidence/")
            if tracked is not None and inside_evidence and path.is_file():
                present = relative in tracked
            else:
                present = path.exists()
            if not present:
                broken.append(f"{readme.relative_to(ROOT)}: {target}")
    assert not broken, "review-evidence links to untracked or missing files (force-add ignored logs):\n" + "\n".join(broken)
