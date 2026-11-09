"""Structural gate (rule 12) for the frontend floor #2014 set (docs/DEPLOYMENT.md, "OAuth session handoff"); no
workflow is dispatched and nothing is fetched.

Since #2014 every Google and Apple sign-in hands its session off through the frontend's ``/auth/complete``, so a
production frontend without that page fails every OAuth sign-in. In the repository, ``test_frontend_links_resolve.py``
fails a commit whose frontend loses the page. Nothing in the repository can stop a rollback made in Vercel's
dashboard, so in production the floor rests on the daily smoke (``prod-smoke.yml``), which opens the page and expects
its failure route. Nothing else in CI runs that spec (its describe-level skip passes every case without
``SMOKE_BASE_URL``, which the e2e shards do not set), so this pins the probe as written; an edit to it changes this
test too, and is argued in review:

- the smoke job's browser step, exactly: no condition, the production URL, and the same commands, unfiltered;
- the spec's read of ``SMOKE_BASE_URL``, its one skip (the describe's own, without that URL), and the landing case's
  statements, comments aside; the route it waits for is the landing page's own failure route, read from the page;
- the runner's config filters no case (no grep, grep-invert, ignore, match or projects key);
- the failure issue lists the page among the checks the smoke makes.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "frontend/tests/e2e/prod-smoke.spec.ts"
LANDING_PAGE = ROOT / "frontend/app/auth/complete/page.tsx"
RUNNER_CONFIG = ROOT / "frontend/playwright.config.ts"
PRODUCTION = "https://earningsnerd.io"
PROBE_COMMANDS = [
    'if [[ ! "$SMOKE_FILING_PATH" =~ ^/filing/[A-Za-z0-9._-]+$ ]]; then',
    "echo 'filing_path must be a local /filing/<id> route'",
    "exit 1",
    "fi",
    "npx playwright test prod-smoke",
]
LANDING_TEST = re.compile(
    r"\n  test\('the OAuth landing page is served[^']*', async \(\{ page \}\) => \{\n(?P<body>.*?)\n  \}\)\n", re.S
)
LANDING_BODY = (
    "const landing = await page.goto(new URL('/auth/complete', SMOKE_BASE_URL).toString(), { "
    "waitUntil: 'domcontentloaded', timeout: 45000, }) "
    "expect(landing?.status()).toBe(200) "
    r"await expect(page).toHaveURL(/\/login\?error=oauth_handoff_failed$/, { timeout: 45000 })"
)


def _workflow() -> dict:
    return yaml.load((ROOT / ".github/workflows/prod-smoke.yml").read_text(), Loader=yaml.BaseLoader)


def _code(source: str) -> str:
    """The spec without its comments; strings are kept whole, so a ``//`` inside one is not a comment."""
    out, i, n = [], 0, len(source)
    while i < n:
        if source.startswith("//", i):
            end = source.find("\n", i)
            i = n if end < 0 else end
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = n if end < 0 else end + 2
        elif source[i] in "'\"`":
            j = i + 1
            while j < n and source[j] != source[i]:
                j += 2 if source[j] == "\\" else 1
            out.append(source[i:j + 1])
            i = j + 1
        else:
            out.append(source[i])
            i += 1
    return "".join(out)


def test_code_drops_comments_and_keeps_strings():
    assert _code("a // b\nc /* d */ e") == "a \nc  e"
    assert _code("x('https://earningsnerd.io') // gone") == "x('https://earningsnerd.io') "
    assert _code("/* test('the OAuth landing page is served', ...) */") == ""


def test_the_daily_smoke_runs_the_browser_spec_against_production():
    workflow = _workflow()
    assert any(entry.get("cron", "").strip() for entry in workflow["on"]["schedule"])
    job = workflow["jobs"]["smoke"]
    assert "if" not in job and "continue-on-error" not in job
    probes = [step for step in job["steps"] if "playwright test" in step.get("run", "")]
    assert len(probes) == 1, "one step runs the production browser spec"
    probe = probes[0]
    assert set(probe) == {"name", "working-directory", "env", "run"}, "no condition, timeout or error swallowing"
    assert probe["working-directory"] == "frontend"
    assert set(probe["env"]) == {"SMOKE_BASE_URL", "SMOKE_FILING_PATH"} and probe["env"]["SMOKE_BASE_URL"] == PRODUCTION
    commands = [line.strip() for line in probe["run"].splitlines() if line.strip() and not line.strip().startswith("#")]
    # Every command, not only the last: nothing before it may unset the URL or trap the exit, and no -g, --grep or
    # project filter narrows the run.
    assert commands == PROBE_COMMANDS


def test_the_spec_opens_the_landing_page_and_expects_its_own_failure_route():
    code = _code(SPEC.read_text())
    assert re.findall(r"^const SMOKE_BASE_URL = .*$", code, re.M) == ["const SMOKE_BASE_URL = process.env.SMOKE_BASE_URL"]
    assert re.findall(r"\bSMOKE_BASE_URL\s*=(?!=)", code) == ["SMOKE_BASE_URL ="], "the URL is assigned once"
    # One skip, the describe's own without SMOKE_BASE_URL (the workflow sets it); no case is skipped, fixed, focused,
    # failed or slowed, in any form (test.info().skip(...) included).
    assert re.findall(r"\.\s*(?:skip|fixme|only|fail|slow)\s*\(", code) == [".skip("]
    assert code.count("test.skip(!SMOKE_BASE_URL, ") == 1
    found = LANDING_TEST.search(code)
    assert found, "the production smoke no longer checks the OAuth landing page"
    assert " ".join(found.group("body").split()) == LANDING_BODY
    route = re.search(r"^const HANDOFF_FAILED = '([^']+)'$", LANDING_PAGE.read_text(), re.M)
    assert route, "the landing page's failure route moved; read it from where it is now"
    pattern = re.search(r"toHaveURL\(/(?P<pattern>.+)/, \{", found.group("body")).group("pattern")
    # The spec's pattern is a JavaScript regular expression; its escapes read the same in Python.
    assert re.search(pattern, PRODUCTION + route.group(1))
    assert not re.search(pattern, PRODUCTION + "/waitlist")


def test_the_runner_config_filters_no_case():
    code = _code(RUNNER_CONFIG.read_text())
    assert "testDir: './tests/e2e'," in code
    for key in ("grep", "grepInvert", "testIgnore", "testMatch", "projects"):
        assert not re.search(rf"\b{key}\s*:", code), f"playwright.config.ts sets {key}, which can drop the landing case"


def test_the_failure_issue_names_the_landing_page():
    issue = _workflow()["jobs"]["report-failure"]["steps"][-1]["run"]
    assert "the OAuth landing page /auth/complete is served" in issue
