"""Scheduled operational failures retain a visible issue; structural, no dispatches."""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCHEDULED_FAIL_LOUD = ("refresh-index-membership.yml", "prod-smoke.yml")


@pytest.mark.parametrize("name", SCHEDULED_FAIL_LOUD)
def test_scheduled_workflow_has_final_failure_issue(name):
    workflow = yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)
    assert any(entry.get("cron", "").strip() for entry in workflow["on"]["schedule"])
    assert workflow["permissions"]["issues"] == "write"
    jobs = workflow["jobs"]
    if name == "prod-smoke.yml":
        worker = jobs["smoke"]
        reporter = jobs["report-failure"]
        assert worker["timeout-minutes"] == "15"
        assert reporter["needs"] == "smoke"
        assert reporter["if"] == "always() && needs.smoke.result != 'success'"
        assert 0 < int(reporter["timeout-minutes"]) <= 5
        upload = worker["steps"][-1]
        assert upload["uses"].startswith("actions/upload-artifact@")
        assert upload["if"] == "always()"
        step = reporter["steps"][-1]
        assert "if" not in step
        assert step["env"]["GH_REPO"] == "${{ github.repository }}"
        assert step["env"]["SMOKE_RESULT"] == "${{ needs.smoke.result }}"
        issue_steps = [step]
    else:
        issue_steps = [job["steps"][-1] for job in jobs.values()]
        for step in issue_steps:
            assert step.get("if") == "failure()"
    for step in issue_steps:
        assert step["env"]["GH_TOKEN"]
        executable = "\n".join(line for line in step["run"].splitlines() if not line.lstrip().startswith("#"))
        assert "gh issue create " in executable
        assert "gh issue comment " in executable
