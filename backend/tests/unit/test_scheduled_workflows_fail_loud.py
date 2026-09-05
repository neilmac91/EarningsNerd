"""Scheduled operational failures retain a visible issue; structural, no dispatches."""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCHEDULED_FAIL_LOUD = ("refresh-index-membership.yml",)


@pytest.mark.parametrize("name", SCHEDULED_FAIL_LOUD)
def test_scheduled_workflow_has_final_failure_issue(name):
    workflow = yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)
    assert any(entry.get("cron", "").strip() for entry in workflow["on"]["schedule"])
    assert workflow["permissions"]["issues"] == "write"
    for job in workflow["jobs"].values():
        step = job["steps"][-1]
        assert step.get("if") == "failure()"
        assert step["env"]["GH_TOKEN"]
        executable = "\n".join(line for line in step["run"].splitlines() if not line.lstrip().startswith("#"))
        assert "gh issue create " in executable
        assert "gh issue comment " in executable
