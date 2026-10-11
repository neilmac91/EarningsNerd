"""Structural gate (rule 12) for docs/PRICING_OFFER.md's machine checks; no workflow is dispatched.

- ``price-agreement.yml`` runs on every pull request that changes the module exporting
  ``PRO_PRICING``, reads production's public charge report and fails while checkout would charge more
  than the new page shows (the backend-first step order).
- ``prod-smoke.yml`` compares the same report with ``main``'s offer every day, even when its browser
  probe failed, so a disagreement in either direction (a higher Price restored under a lower page
  included) opens its failure issue.
- The agreement script compares with the module the workflow watches.

The script's verdicts are pinned by ``frontend/tests/unit/pricingAgreement.spec.ts`` and the report by
``test_serving_prices.py``.
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
PRICES = "frontend/app/pricing/prices.ts"
REPORT_URL = "https://api.earningsnerd.io/api/subscriptions/prices"


def _workflow(name: str) -> dict:
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


def _last_command(run: str) -> str:
    return [line.strip() for line in run.splitlines() if line.strip()][-1]


def test_the_watched_module_is_the_offer_the_script_compares():
    assert "export const PRO_PRICING" in (ROOT / PRICES).read_text()
    script = (ROOT / "frontend/scripts/check-pricing-agreement.mjs").read_text()
    assert "import { PRO_PRICING } from '../app/pricing/prices.ts'" in script


def test_a_pull_request_that_changes_the_offer_is_checked_against_production():
    workflow = _workflow("price-agreement.yml")
    assert set(workflow["on"]) == {"pull_request"}
    assert workflow["on"]["pull_request"]["paths"] == [PRICES]
    job = workflow["jobs"]["checkout-charges-no-more"]
    assert "if" not in job and "continue-on-error" not in job
    read, check = job["steps"][-2:]
    assert REPORT_URL in read["run"] and "curl -fsS" in read["run"] and "if" not in read
    assert check["working-directory"] == "frontend" and "if" not in check
    assert _last_command(check["run"]) == (
        'npm run -s check:pricing -- --serving --publishing "$RUNNER_TEMP/serving-prices.json"'
    )


def test_production_agreement_is_checked_daily():
    workflow = _workflow("prod-smoke.yml")
    assert any(entry.get("cron", "").strip() for entry in workflow["on"]["schedule"])
    steps = workflow["jobs"]["smoke"]["steps"]
    probe = next(step for step in steps if step.get("name") == "Probe price agreement")
    assert probe["if"] == "${{ !cancelled() }}" and "continue-on-error" not in probe
    assert REPORT_URL in probe["run"] and "curl -fsS" in probe["run"]
    assert _last_command(probe["run"]) == "npm run -s check:pricing -- --serving ../smoke-evidence/serving-prices.json"
    assert steps.index(probe) == len(steps) - 2  # the evidence upload stays last
    assert "checkout charges what the pricing page shows" in workflow["jobs"]["report-failure"]["steps"][-1]["run"]
