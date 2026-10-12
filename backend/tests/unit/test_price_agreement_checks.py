"""Structural gate (rule 12) for docs/PRICING_OFFER.md's machine checks; no workflow is dispatched.

- ci.yml's ``price-agreement`` job runs on a pull request unless ci-scope positively says the offer
  (the module exporting ``PRO_PRICING``) is unchanged. It reads production's public charge report
  and fails while checkout would charge more than the offer the checked merge publishes: the
  backend-first step order. On a pull request, being skipped only on that positive "unchanged" (a
  skip counts as passing) is what lets the founder make it a required check; a failed or missing
  scope runs it, and its guard fails. Nothing in it is advisory. Pushes and manual runs skip it.
- ``prod-smoke.yml`` compares the same report with the offer the live pricing page publishes every
  day, even when its browser probe failed, so a disagreement in either direction (a higher Price
  bound under a lower page, or a frontend rollback) opens its failure issue.
- The agreement script compares with the module ci-scope watches.

ci-scope's classification runs on real histories in ``test_ci_cost_controls.py``; the script's
verdicts are pinned by ``frontend/tests/unit/pricingAgreement.spec.ts`` and the report by
``test_serving_prices.py``.
"""
import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
PRICES = "frontend/app/pricing/prices.ts"
REPORT_URL = "https://api.earningsnerd.io/api/subscriptions/prices"
JOB_IF = (
    "${{ always() && !cancelled() && github.event_name == 'pull_request' && "
    "!(needs.ci-scope.result == 'success' && needs.ci-scope.outputs.prices_changed == 'false') }}"
)


def _workflow(name: str) -> dict:
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


def _last_command(run: str) -> str:
    return [line.strip() for line in run.splitlines() if line.strip()][-1]


def test_the_watched_module_is_the_offer_the_script_compares():
    assert "export const PRO_PRICING" in (ROOT / PRICES).read_text()
    script = (ROOT / "frontend/scripts/check-pricing-agreement.mjs").read_text()
    assert "import { PRO_PRICING } from '../app/pricing/prices.ts'" in script
    scope = _workflow("ci.yml")["jobs"]["ci-scope"]
    assert scope["outputs"]["prices_changed"] == "${{ steps.scope.outputs.prices_changed }}"
    assert f"{PRICES}) PRICES_CHANGED=true ;;" in scope["steps"][-1]["run"]


def test_a_pull_request_that_changes_the_offer_is_checked_against_production(tmp_path):
    ci = _workflow("ci.yml")
    job = ci["jobs"]["price-agreement"]
    assert job["needs"] == ["ci-scope"] and job["if"] == JOB_IF
    assert "continue-on-error" not in job
    assert all("if" not in step and "continue-on-error" not in step for step in job["steps"])
    guard, *_, read, check = job["steps"]
    assert guard["env"] == {
        "SCOPE_RESULT": "${{ needs.ci-scope.result }}",
        "PRICES_CHANGED": "${{ needs.ci-scope.outputs.prices_changed }}",
    }
    for state, value in (("success", "true"), ("success", "false"), ("success", ""), ("success", "bogus"),
                         ("failure", ""), ("failure", "true"), ("cancelled", "true"), ("skipped", "")):
        result = subprocess.run(
            ["bash", "-e", "-c", guard["run"]], capture_output=True, text=True,
            env={**os.environ, "SCOPE_RESULT": state, "PRICES_CHANGED": value}, timeout=10, check=False,
        )
        assert (result.returncode == 0) == (state == "success" and value == "true"), (state, value)
    assert REPORT_URL in read["run"] and "curl -fsS" in read["run"]
    checkout = next(step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["with"] == {"persist-credentials": "false"}  # the checked merge, no other ref
    assert check["working-directory"] == "frontend"
    assert "git rev-parse --verify 'HEAD^{commit}')\" != \"$GITHUB_SHA\"" in check["run"]
    assert _last_command(check["run"]) == (
        'npm run -s check:pricing -- --serving --publishing "$RUNNER_TEMP/serving-prices.json"'
    )
    # main never runs it, so a check that depends on production never holds back a deploy.
    assert "price-agreement" not in ci["jobs"]["deploy-backend"]["needs"]


def test_production_agreement_with_the_live_page_is_checked_daily():
    workflow = _workflow("prod-smoke.yml")
    assert any(entry.get("cron", "").strip() for entry in workflow["on"]["schedule"])
    steps = workflow["jobs"]["smoke"]["steps"]
    probe = next(step for step in steps if step.get("name") == "Probe price agreement")
    assert probe["if"] == "${{ !cancelled() }}" and "continue-on-error" not in probe
    run = probe["run"]
    assert REPORT_URL in run and "https://www.earningsnerd.io/pricing -o ../smoke-evidence/pricing.html" in run
    assert _last_command(run) == (
        "npm run -s check:pricing -- --serving --page ../smoke-evidence/pricing.html "
        "../smoke-evidence/serving-prices.json"
    )
    assert steps.index(probe) == len(steps) - 2  # the evidence upload stays last
    issue = workflow["jobs"]["report-failure"]["steps"][-1]["run"]
    assert "checkout charges what the live pricing page shows" in issue
