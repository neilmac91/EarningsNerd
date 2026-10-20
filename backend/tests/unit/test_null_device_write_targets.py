"""Gate for lessons/test-never-point-a-written-file-at-dev-null.md: no tracked code gives git the null device
as a file it writes.

Git writes its config and its index through a lock file that it renames over the target. As root, which cloud
sessions are, a write through GIT_CONFIG_GLOBAL, GIT_CONFIG_SYSTEM, GIT_CONFIG or GIT_INDEX_FILE naming the null
device, or through `git config --file` naming it, therefore replaces the device with an ordinary file.
tests/conftest.py's `_null_device_survives` sees that only in a root run, after the damage; this gate finds the
pattern in source on any runner, CI's included. The null device counts when wrapped in calls
(`str(os.devnull)`, `Path("/dev/null")`). A variable that holds it, a linker's `-o` and an atomic writer's
target stay review-checked, with `_null_device_survives` behind them in a root run; curl's `-o` writes in place
and leaves the device alone.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
NULL = r"(?:[\w.]+\(\s*['\"]?)*(?:os\.devnull|/dev/null)"  # wrapped in calls or not: str(os.devnull)
FORBIDDEN = re.compile(
    rf"GIT_(?:CONFIG(?:_GLOBAL|_SYSTEM)?|INDEX_FILE)\W{{0,8}}{NULL}"  # a variable naming a file git writes
    rf"|\bconfig\W{{1,6}}(?:--file|-f)\W{{0,6}}{NULL}"  # git config --file
)
CODE = {".py", ".sh", ".bash", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".json", ".js", ".mjs", ".cjs", ".ts", ".tsx"}


def _tracked_code() -> list[Path]:
    """Every tracked code file but this one, whose cases name the pattern on purpose. Prose (Markdown) may
    describe it."""
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    paths = [ROOT / name for name in listed.decode("utf-8").split("\0") if name]
    return [path for path in paths if (path.suffix in CODE or path.name == "Dockerfile")
            and path.resolve() != Path(__file__).resolve() and path.is_file()]


def test_no_tracked_code_gives_git_the_null_device_to_write():
    hits = []
    for path in _tracked_code():
        text = path.read_text(encoding="utf-8", errors="replace")
        hits += [f"{path.relative_to(ROOT)}:{text.count(chr(10), 0, match.start()) + 1}: {match.group(0)}"
                 for match in FORBIDDEN.finditer(text)]
    assert not hits, (
        "Git renames its lock file over a config or index file it writes, which as root replaces the null "
        "device. Give git an empty file in the test's own temp directory instead "
        "(lessons/test-never-point-a-written-file-at-dev-null.md):\n" + "\n".join(hits))


@pytest.mark.parametrize("text", [
    '"GIT_CONFIG_GLOBAL": os.devnull',
    "env={**os.environ, 'GIT_CONFIG_SYSTEM': '/dev/null'}",
    'monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)',
    'env["GIT_INDEX_FILE"] = os.devnull',
    "GIT_CONFIG=/dev/null git config user.name x",
    "GIT_CONFIG_GLOBAL: /dev/null",  # a workflow step's env
    'subprocess.run(["git", "config", "--file", os.devnull, "a.b", "c"])',
    "git config -f /dev/null a.b c",
    "git config --file=/dev/null a.b c",
    'env["GIT_CONFIG_GLOBAL"] = str(os.devnull)',
    '"GIT_INDEX_FILE": os.fspath(Path("/dev/null"))',
    'subprocess.run(["git", "config", "--file", str(os.devnull), "a.b", "c"])',
])
def test_the_gate_finds_each_form(text):
    assert FORBIDDEN.search(text)


@pytest.mark.parametrize("text", [
    "curl -sS -o /dev/null -w '%{http_code}' https://example.com",  # writes in place
    "GIT_CONFIG_NOSYSTEM=1 git status",
    "git -c core.hooksPath=/dev/null commit -m x",  # a path git reads
    "GIT_CONFIG_KEY_0=core.excludesFile GIT_CONFIG_VALUE_0=/dev/null git check-ignore x",  # a value, not a file
    'env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig")',
    '"GIT_CONFIG_GLOBAL": str(write_config(tmp_path)), "NULL": os.devnull',
    "make build > /dev/null 2>&1",
])
def test_the_gate_passes_what_leaves_the_device_alone(text):
    assert not FORBIDDEN.search(text)
