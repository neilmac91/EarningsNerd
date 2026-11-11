"""The daily DeepSeek balance check fails below its floor, and its failure opens an issue (F75).

Nothing in the app caps model spend, and the provider balance is prepaid: when it runs out, new summaries, Ask this
Filing answers and analysis narratives stop for every reader (docs/ops/closed-beta-acceptance.md, section 5). Until
2026-11-11 the balance was read only by hand. ``.github/workflows/deepseek-balance.yml`` now also runs daily, fails
below a floor (the ``DEEPSEEK_BALANCE_FLOOR_USD`` repository variable, USD 5 when unset) and reports that as an issue,
while a dispatch still succeeds on any readable balance, so a readback before paid work is not refused.

No workflow is dispatched and nothing is fetched: the step's own script runs here against a stand-in for the provider's
answer. What this cannot see: that GitHub starts the schedule, the secret's value, and the issue the report step opens.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "deepseek-balance.yml"
SCRIPT = re.compile(r"python3 - <<'PY'\n(?P<code>.*)\nPY\s*\Z", re.S)


def _workflow() -> dict:
    # BaseLoader keeps every scalar a string, so the `on` key is not read as a boolean.
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _script() -> str:
    step = _workflow()["jobs"]["balance"]["steps"][0]
    match = SCRIPT.search(step["run"])
    assert match, "the balance step must stay one `python3 - <<'PY'` script, which this test runs"
    return match.group("code")


def _balance(usd: str | None, available: bool = True) -> dict:
    rows = [{"currency": "CNY", "total_balance": "0.00", "granted_balance": "0.00", "topped_up_balance": "0.00"}]
    if usd is not None:
        rows.append({"currency": "USD", "total_balance": usd, "granted_balance": "0.00", "topped_up_balance": usd})
    return {"is_available": available, "balance_infos": rows}


def _check(monkeypatch, capsys, payload: dict, event: str, floor: str = "5") -> tuple[int, str, str]:
    """Run the step's script on one provider answer; its exit code, stdout and stderr."""

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, limit):
            return json.dumps(payload).encode()

    class Opener:
        def open(self, request, timeout):
            assert request.full_url == "https://api.deepseek.com/user/balance"
            return Response()

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "stand-in")
    monkeypatch.setenv("BALANCE_FLOOR_USD", floor)
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    code = 0
    try:
        exec(compile(_script(), str(WORKFLOW), "exec"), {"__name__": "__main__"})  # noqa: S102 - the workflow's own step
    except SystemExit as exit_:
        code = int(exit_.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_a_scheduled_run_passes_above_the_floor_and_prints_the_balance(monkeypatch, capsys):
    code, out, _ = _check(monkeypatch, capsys, _balance("15.14"), "schedule")
    assert code == 0
    assert json.loads(out.splitlines()[0])["balance_infos"][1]["total_balance"] == "15.14"
    assert "::error::" not in out and "::warning::" not in out


@pytest.mark.parametrize(
    ("payload", "floor"),
    [(_balance("4.99"), "5"), (_balance("15.14"), "20"), (_balance("0"), "5"), (_balance("15.14", available=False), "5")],
)
def test_a_scheduled_run_fails_below_the_floor_or_when_the_provider_says_unavailable(monkeypatch, capsys, payload, floor):
    code, out, _ = _check(monkeypatch, capsys, payload, "schedule", floor)
    assert code == 1
    assert "::error::DeepSeek balance USD" in out and "top up" in out


def test_a_dispatch_only_warns_below_the_floor_so_a_readback_still_succeeds(monkeypatch, capsys):
    code, out, _ = _check(monkeypatch, capsys, _balance("4.99"), "workflow_dispatch")
    assert code == 0
    assert "::warning::DeepSeek balance USD 4.99 is below the floor of USD 5" in out and "::error::" not in out


def test_a_balance_with_no_usd_row_says_the_floor_is_unchecked(monkeypatch, capsys):
    code, out, _ = _check(monkeypatch, capsys, _balance(None), "schedule")
    assert code == 0
    assert "::notice::No USD balance row" in out


@pytest.mark.parametrize("floor", ["", "five", "-1", "nan", "inf"])
def test_a_floor_that_is_not_a_non_negative_number_fails_the_run(monkeypatch, capsys, floor):
    code, _, err = _check(monkeypatch, capsys, _balance("15.14"), "schedule", floor)
    assert code == 1
    assert "Balance floor is not a non-negative number" in err


def test_the_schedule_runs_daily_and_only_its_failure_opens_an_issue():
    workflow = _workflow()
    assert [entry["cron"] for entry in workflow["on"]["schedule"]] == ["41 5 * * *"]
    assert "workflow_dispatch" in workflow["on"]
    # No scope by default: only the report job may write, and only issues.
    assert workflow["permissions"] == {}
    assert "permissions" not in workflow["jobs"]["balance"]
    report = workflow["jobs"]["report-low-balance"]
    assert report["permissions"] == {"issues": "write"}
    assert report["needs"] == "balance"
    assert report["if"] == "always() && github.event_name == 'schedule' && needs.balance.result != 'success'"
    env = workflow["jobs"]["balance"]["steps"][0]["env"]
    assert env["BALANCE_FLOOR_USD"] == "${{ vars.DEEPSEEK_BALANCE_FLOOR_USD || '5' }}"
