"""Gate: retired DeepSeek model ids never reappear as literals (CLAUDE.md rule 12; ADR-0008).

`deepseek-v4-pro` was retired on 2026-09-14 and `deepseek-v4-flash*` are withdrawable aliases.
The live model id is configuration (`AI_DEFAULT_MODEL`), but it is written as a literal in the
deploy/eval workflows and a few reference files; this test keeps every such site on the canonical
id so a routing change is never silently re-introduced by a stale copy.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
RETIRED = re.compile(r"deepseek-v4-(pro|flash)")
# Files that legitimately carry the live model id as a literal; they must all agree with config.
# Workflows are deliberately NOT here: they load .github/ai-model.env (the single deploy-time
# source, W9) and must carry no model literal of their own.
LITERAL_SITES = (
    ".github/ai-model.env",
    "backend/.env.example",
    "docs/CONFIGURATION.md",
    "tasks/gcp-deploy-runbook.md",
)
MODEL_WORKFLOWS = (
    ".github/workflows/ci.yml",
    ".github/workflows/copilot-eval.yml",
    ".github/workflows/data-quality-weekly.yml",
)
LOAD_STEP = "grep -v '^#' .github/ai-model.env >> \"$GITHUB_ENV\""
SCAN_ROOTS = ("backend/app", "backend/evals", "backend/scripts", ".github/workflows", "backend/.env.example")


def _files(root: Path):
    if root.is_file():
        yield root
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".yml", ".yaml", ".sh", ".example", ".json", ".md"} \
                and ".venv" not in path.parts and "reports" not in path.parts and "baselines" not in path.parts:
            yield path


def test_no_retired_deepseek_model_id_in_code_or_workflows():
    offenders = []
    for root in SCAN_ROOTS:
        for path in _files(ROOT / root):
            for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                if RETIRED.search(line) and "retired" not in line.lower() and "ADR-0008" not in line:
                    offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()[:120]}")
    assert not offenders, "retired DeepSeek model id found:\n" + "\n".join(offenders)


@pytest.mark.parametrize("site", LITERAL_SITES)
def test_every_literal_site_carries_the_configured_default_model(site):
    from app.config import Settings

    default = Settings.model_fields["AI_DEFAULT_MODEL"].default
    text = (ROOT / site).read_text(errors="ignore")
    assert re.search(rf"AI_DEFAULT_MODEL[=:\s\"'`|]+{re.escape(default)}\b", text), (
        f"{site} does not set AI_DEFAULT_MODEL to the configured default {default!r}")


def _env_file() -> dict:
    values = {}
    for line in (ROOT / ".github/ai-model.env").read_text().splitlines():
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            values[key] = value
    return values


def test_env_file_matches_code_defaults_for_model_and_base_url():
    from app.config import Settings

    values = _env_file()
    assert values["AI_DEFAULT_MODEL"] == Settings.model_fields["AI_DEFAULT_MODEL"].default
    assert values["OPENAI_BASE_URL"] == Settings.model_fields["OPENAI_BASE_URL"].default
    assert set(values) == {"AI_DEFAULT_MODEL", "OPENAI_BASE_URL"}, "only the two provider keys belong here"


@pytest.mark.parametrize("workflow", MODEL_WORKFLOWS)
def test_workflows_load_the_env_file_and_carry_no_model_literal(workflow):
    text = (ROOT / workflow).read_text()
    assert LOAD_STEP in text, f"{workflow} must load .github/ai-model.env into GITHUB_ENV"
    assert not re.search(r"AI_DEFAULT_MODEL:\s*\S", text), f"{workflow} carries a static AI_DEFAULT_MODEL"
    assert not re.search(r"OPENAI_BASE_URL:\s*https?://", text), f"{workflow} carries a static OPENAI_BASE_URL"
    assert not re.search(r"AI_DEFAULT_MODEL=(?!\$\{AI_DEFAULT_MODEL\})\S", text), (
        f"{workflow} interpolates a model literal instead of ${{AI_DEFAULT_MODEL}}")
    for line in text.splitlines():
        # Every deploy env map that carries the model must carry both provider keys, interpolated.
        if "--update-env-vars=" in line and "AI_DEFAULT_MODEL=" in line:
            assert "AI_DEFAULT_MODEL=${AI_DEFAULT_MODEL}" in line and "OPENAI_BASE_URL=${OPENAI_BASE_URL}" in line, line.strip()[:100]
