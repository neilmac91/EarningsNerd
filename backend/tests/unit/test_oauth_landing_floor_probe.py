"""Structural gate (rule 12) for the frontend floor #2014 set (docs/DEPLOYMENT.md, "OAuth session handoff"); no
workflow is dispatched and nothing is fetched.

Since #2014 every Google and Apple sign-in hands its session off through the frontend's ``/auth/complete``, so a
production frontend without that page fails every OAuth sign-in. In the repository, ``test_frontend_links_resolve.py``
fails a commit whose frontend loses the page. Nothing in the repository can stop a rollback made in Vercel's
dashboard, so in production the floor rests on the daily smoke (``prod-smoke.yml``), which opens the page and expects
its failure notice. This holds that probe in place:

- the smoke job runs the browser spec against production, unfiltered, and no condition can skip the step; without
  ``SMOKE_BASE_URL`` the spec's describe-level skip would pass every case;
- the spec opens ``/auth/complete`` and expects the landing page's own failure route, read from the page;
- the failure issue names the page, so a red run says what failed.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "frontend/tests/e2e/prod-smoke.spec.ts"
LANDING_PAGE = ROOT / "frontend/app/auth/complete/page.tsx"
PRODUCTION = "https://earningsnerd.io"
LANDING_TEST = re.compile(
    r"\n  test\('the OAuth landing page is served[^']*', async \(\{ page \}\) => \{\n(?P<body>.*?)\n  \}\)\n", re.S
)


def _workflow() -> dict:
    return yaml.load((ROOT / ".github/workflows/prod-smoke.yml").read_text(), Loader=yaml.BaseLoader)


def test_the_daily_smoke_runs_the_browser_spec_against_production():
    workflow = _workflow()
    assert any(entry.get("cron", "").strip() for entry in workflow["on"]["schedule"])
    steps = workflow["jobs"]["smoke"]["steps"]
    probes = [step for step in steps if "playwright test" in step.get("run", "")]
    assert len(probes) == 1, "one step runs the production browser spec"
    probe = probes[0]
    assert probe.get("env", {}).get("SMOKE_BASE_URL") == PRODUCTION
    assert "if" not in probe and "continue-on-error" not in probe
    commands = [line.strip() for line in probe["run"].splitlines() if line.strip() and not line.strip().startswith("#")]
    # The last command, with no -g, --grep or project filter: every case of the spec runs.
    assert commands[-1] == "npx playwright test prod-smoke"


def test_the_spec_opens_the_landing_page_and_expects_its_own_failure_route():
    spec = SPEC.read_text()
    # One skip, the describe's own without SMOKE_BASE_URL (the workflow sets it); no case is skipped, fixed or focused.
    assert re.findall(r"\btest(?:\.describe)?\.(?:skip|fixme|only|fail)\(", spec) == ["test.skip("]
    assert "test.skip(!SMOKE_BASE_URL," in spec
    found = LANDING_TEST.search(spec)
    assert found, "the production smoke no longer checks the OAuth landing page"
    body = found.group("body")
    assert "page.goto(new URL('/auth/complete', SMOKE_BASE_URL).toString()" in body
    assert "expect(landing?.status()).toBe(200)" in body
    route = re.search(r"^const HANDOFF_FAILED = '([^']+)'$", LANDING_PAGE.read_text(), re.M)
    assert route, "the landing page's failure route moved; read it from where it is now"
    expected = re.search(r"await expect\(page\)\.toHaveURL\(/(?P<pattern>.+)/, \{", body)
    assert expected, "the landing check no longer waits for a route"
    # The spec's pattern is a JavaScript regular expression; its escapes read the same in Python.
    assert re.search(expected.group("pattern"), PRODUCTION + route.group(1))
    assert not re.search(expected.group("pattern"), PRODUCTION + "/waitlist")


def test_the_failure_issue_names_the_landing_page():
    issue = _workflow()["jobs"]["report-failure"]["steps"][-1]["run"]
    assert "the OAuth landing page /auth/complete is served" in issue
