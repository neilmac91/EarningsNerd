"""Keep engineering agent instructions on the supported stack (CLAUDE rule 12)."""
from pathlib import Path
import re

AGENTS = Path(__file__).resolve().parents[3] / ".claude" / "agents"
REQUIRED_ENGINEERING_FILES = {
    "engineering/ai-engineer.md",
    "engineering/api-architect.md",
    "engineering/backend-developer.md",
    "engineering/database-specialist.md",
    "engineering/devops-automator.md",
    "engineering/frontend-developer.md",
    "engineering/infrastructure-maintainer.md",
}
OBSOLETE_STACK = re.compile(
    r"Firebase|Firestore|Alembic|Celery|\bVite\b|React Router|GPT-4|GPT-3\.5|"
    r"AsyncSession|create_async_engine|/api/v1|render\.yaml|\bon Render\b|"
    r"\bRender dashboard\b|\bDeploy to Render\b",
    re.IGNORECASE,
)
# Existing non-engineering debt; remove entries when corrected, never add engineering files.
LEGACY_FILES = {
    "README.md",
    "product/competitive-analyst.md",
    "project-management/dependency-mapper.md",
    "project-management/task-tracker.md",
    "testing/integration-tester.md",
    "testing/performance-tester.md",
    "testing/qa-engineer.md",
    "testing/security-auditor.md",
}


def test_agent_files_use_supported_stack_outside_frozen_legacy_files():
    for phrase in ("render the chart", "section rendering", "JSON rendering"):
        assert not OBSOLETE_STACK.search(phrase), f"Benign rendering phrase matched: {phrase}"
    paths = sorted(AGENTS.rglob("*.md"))
    assert paths, f"Agent documentation scan is empty: {AGENTS}"
    missing = REQUIRED_ENGINEERING_FILES - {
        path.relative_to(AGENTS).as_posix() for path in paths
    }
    assert not missing, f"Required engineering briefs are missing: {sorted(missing)}"
    found = {}
    for path in paths:
        lines = [
            number
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if OBSOLETE_STACK.search(line)
        ]
        if lines:
            found[path.relative_to(AGENTS).as_posix()] = lines
    engineering = {name: lines for name, lines in found.items() if name.startswith("engineering/")}
    assert not engineering, f"Engineering briefs teach an obsolete stack: {engineering}"
    unexpected = {name: lines for name, lines in found.items() if name not in LEGACY_FILES}
    assert not unexpected, f"New obsolete-stack agent documentation: {unexpected}"
    stale = LEGACY_FILES - found.keys()
    assert not stale, f"Remove corrected/deleted files from LEGACY_FILES: {sorted(stale)}"
