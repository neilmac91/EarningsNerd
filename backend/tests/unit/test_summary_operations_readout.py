"""The actual bounded Ops reader with its psql boundary stubbed; no live database or services."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("summary_operations_readout", ROOT / "ops/summary_readout/readout.py")
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)
PRIVATE = "private-reader-sentinel@example.invalid/source?credential=withheld"


def snapshot():
    def row(filing):
        return {
            "filing_id": filing, "identity": "matched", "job_present": True,
            "generation": 2, "attempts": 1, "system_funded": False,
            "status": "running", "stage": "fetching", "charge_state": "reserved",
            "error_recorded": False, "active_owner": True, "lease_state": "live",
            "result_reference": "absent", "reservation_reference": "live",
            "charged_month_shape": "absent",
            "times": {key: {"state": "bounded", "seconds_from_snapshot": 30 if key == "lease_until" else -30}
                      for key in reader.TIMES},
        }
    counts = dict.fromkeys(reader.COUNTERS, 0)
    counts.update(retained=2, running=2, truncated=False, oldest_age_seconds_capped=30)
    return {"schema_version": 1, "read_only": "on", "isolation": "repeatable read",
            "observed_at": "2026-10-30T21:00:00+00:00", "filings": [row(45003), row(45004)],
            "active_jobs": counts,
            "sec_coordinator": {"present": True, "times": {
                key: {"state": "bounded", "seconds_from_snapshot": 4}
                for key in ("next_admission", "cooldown")}}}


def fake_psql(monkeypatch, data=None, *, raw=None, error=b"", code=0):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        kwargs["stdout"].write(raw if raw is not None else json.dumps(data or snapshot()).encode())
        kwargs["stderr"].write(error)
        return SimpleNamespace(returncode=code)
    monkeypatch.setattr(reader.subprocess, "run", run)
    return calls


def test_reader_runs_only_fixed_sql_with_bounded_readonly_client_and_private_artifact(monkeypatch, tmp_path, capfd):
    calls = fake_psql(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(reader.sys, "argv", ["readout.py"])
    assert reader.main() == 0
    artifact = tmp_path / reader.OUTPUT_FILE
    result = json.loads(artifact.read_text())
    assert artifact.stat().st_mode & 0o777 == 0o600
    assert result["state"] == "observed_snapshot" and result["read_only"] is True
    assert result["limits"]["filing_ids"] == [45003, 45004]
    assert "not a read of deployed Settings" in result["limits"]["threshold_scope"]
    assert "no user_usage counters" in result["limits"]["receipt_scope"]
    command, kwargs = calls[0]
    assert command == ["psql", "--no-psqlrc", "--no-password", "--quiet", "--tuples-only", "--no-align",
                       "--set=ON_ERROR_STOP=1", "--set=VERBOSITY=sqlstate", "--file", str(reader.SQL_FILE)]
    assert kwargs["timeout"] == 25
    assert kwargs["env"]["PGCONNECT_TIMEOUT"] == "5"
    assert kwargs["env"]["PGOPTIONS"].endswith("-c default_transaction_read_only=on -c statement_timeout=15s -c lock_timeout=2s")
    assert json.loads(capfd.readouterr().out) == result


@pytest.mark.parametrize("location", ["root", "row", "times", "coordinator", "active", "enum"])
def test_no_unknown_or_private_database_field_reaches_stdout_or_artifact(location, monkeypatch, tmp_path, capfd):
    data = snapshot()
    containers = {"root": data, "row": data["filings"][0], "times": data["filings"][0]["times"],
                  "coordinator": data["sec_coordinator"], "active": data["active_jobs"]}
    if location == "enum":
        data["filings"][0]["stage"] = PRIVATE
    else:
        containers[location]["private_extra"] = PRIVATE
    fake_psql(monkeypatch, data)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(reader.sys, "argv", ["readout.py"])
    assert reader.main() == 1
    artifact = (tmp_path / reader.OUTPUT_FILE).read_text()
    captured = capfd.readouterr()
    assert PRIVATE not in artifact + captured.out + captured.err
    assert json.loads(artifact)["reason"] == "unreadable_response"


@pytest.mark.parametrize("code,expected", [(b"42501", "permission_denied"), (b"42P01", "missing_schema"),
    (b"42703", "schema_mismatch"), (b"57014", "statement_timeout"), (b"55P03", "lock_timeout"),
    (b"25006", "read_only_violation"), (b"XXXXX", "database_read_failed")])
def test_database_errors_have_closed_classes_without_raw_stderr(code, expected, monkeypatch, tmp_path, capfd):
    fake_psql(monkeypatch, raw=PRIVATE.encode(), error=b"ERROR: " + code + b" " + PRIVATE.encode(), code=1)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(reader.sys, "argv", ["readout.py"])
    assert reader.main() == 1
    captured = capfd.readouterr()
    saved = (tmp_path / reader.OUTPUT_FILE).read_text()
    assert PRIVATE not in captured.out + captured.err + saved
    assert json.loads(saved)["reason"] == expected


@pytest.mark.parametrize("exception,reason", [(FileNotFoundError(PRIVATE), "client_unavailable"),
    (OSError(PRIVATE), "local_read_failed"),
    (reader.subprocess.TimeoutExpired(PRIVATE, 25, output=PRIVATE, stderr=PRIVATE), "process_timeout")])
def test_client_failures_are_closed(exception, reason, monkeypatch):
    def fail(*args, **kwargs):
        raise exception
    monkeypatch.setattr(reader.subprocess, "run", fail)
    assert reader.collect_snapshot()["reason"] == reason


@pytest.mark.parametrize("raw,reason", [(b"x" * (32768 + 1), "output_limit"),
    (b"\xff", "unreadable_response"), (b'{"schema_version":1,"schema_version":1}', "unreadable_response"),
    (b"NaN", "unreadable_response"), (b"{}\n{}", "unreadable_response"),
    (b"[" * 12000 + b"0" + b"]" * 12000, "unreadable_response")],
    ids=["oversized", "invalid-encoding", "duplicate-key", "nonfinite", "extra-json", "deep-nesting"])
def test_output_size_encoding_duplicates_and_extra_json_fail_closed(raw, reason, monkeypatch, tmp_path, capfd):
    fake_psql(monkeypatch, raw=raw)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(reader.sys, "argv", ["readout.py"])
    assert reader.main() == 1
    saved = json.loads((tmp_path / reader.OUTPUT_FILE).read_text())
    captured = capfd.readouterr()
    assert saved["state"] == "UNVERIFIED" and saved["reason"] == reason
    assert json.loads(captured.out) == saved and captured.err == ""


@pytest.mark.parametrize("path,value", [(("read_only",), "off"), (("isolation",), "read committed"),
    (("active_jobs", "retained"), True), (("active_jobs", "retained"), 1001),
    (("active_jobs", "truncated"), True), (("active_jobs", "queued"), 4),
    (("active_jobs", "oldest_age_seconds_capped"), None), (("observed_at",), PRIVATE),
    (("observed_at",), "2026-10-30T21:00:00")])
def test_unbounded_or_contradictory_snapshot_is_not_observed(path, value):
    data = snapshot()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(reader.InvalidSnapshot):
        reader.normalize_snapshot(data)


def test_filing_order_scope_and_terminal_stale_lease_are_distinct():
    data = snapshot()
    data["filings"].reverse()
    with pytest.raises(reader.InvalidSnapshot):
        reader.normalize_snapshot(data)
    data = snapshot()
    row = data["filings"][0]
    row.update(status="failed", active_owner=False, lease_state="live", charge_state="refunded",
               reservation_reference="absent")
    observed = reader.normalize_snapshot(data)
    assert observed["filings"][0]["lease_state"] == "live"
    assert observed["filings"][0]["active_owner"] is False
    row["active_owner"] = True
    with pytest.raises(reader.InvalidSnapshot):
        reader.normalize_snapshot(data)


def test_receipt_findings_do_not_claim_monthly_counter_reconciliation():
    data = snapshot()
    row = data["filings"][0]
    row.update(status="complete", active_owner=False, charge_state="settled", result_reference="wrong_filing")
    observed = reader.normalize_snapshot(data)["filings"][0]
    assert observed["observations"] == ["terminal_result_reference_unresolved", "charge_month_unresolved",
                                       "reservation_remains_after_charge_or_refund"]
    data["filings"][1].update(system_funded=True)
    assert "system_job_usage_reference" in reader.normalize_snapshot(data)["filings"][1]["observations"]


def test_missing_fixed_filing_and_coordinator_are_observed_absence_not_health():
    data = snapshot()
    row = data["filings"][0]
    row.update(identity="missing_filing", job_present=False, generation=None, attempts=None,
               system_funded=None, active_owner=False, status="unknown", stage="unknown", charge_state="unknown",
               lease_state="absent", result_reference="absent", reservation_reference="absent", charged_month_shape="absent",
               times={key: {"state": "absent", "seconds_from_snapshot": None} for key in reader.TIMES})
    data["sec_coordinator"] = {"present": False, "times": {}}
    observed = reader.normalize_snapshot(data)
    assert observed["filings"][0]["identity"] == "missing_filing"
    assert observed["sec_coordinator"] == {"present": False, "times": {}}
    assert observed["state"] == "observed_snapshot"


def test_future_hold_is_not_shortened_or_mislabeled_due():
    data = snapshot()
    data["filings"][0]["times"]["next_attempt"] = {"state": "future_bound", "seconds_from_snapshot": None}
    data["sec_coordinator"]["times"]["cooldown"] = {"state": "nonfinite", "seconds_from_snapshot": None}
    observed = reader.normalize_snapshot(data)
    assert observed["filings"][0]["times"]["next_attempt"]["state"] == "future_bound"
    assert observed["sec_coordinator"]["times"]["cooldown"]["state"] == "nonfinite"


def test_readout_accepts_no_runtime_scope_sql_or_output_argument(monkeypatch, tmp_path, capfd):
    monkeypatch.setattr(reader.sys, "argv", ["readout.py", PRIVATE])
    monkeypatch.setattr(reader, "collect_snapshot", lambda: pytest.fail("unexpected arguments must not query"))
    monkeypatch.chdir(tmp_path)
    assert reader.main() == 1
    captured = capfd.readouterr()
    assert PRIVATE not in captured.out + captured.err
    assert json.loads(captured.out)["reason"] == "unexpected_arguments"


def test_artifact_symlink_cannot_overwrite_another_file(monkeypatch, tmp_path, capfd):
    protected = tmp_path / "untouched"
    protected.write_text(PRIVATE)
    (tmp_path / reader.OUTPUT_FILE).symlink_to(protected)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(reader.sys, "argv", ["readout.py"])
    monkeypatch.setattr(reader, "collect_snapshot", lambda: reader.normalize_snapshot(copy.deepcopy(snapshot())))
    assert reader.main() == 1
    assert protected.read_text() == PRIVATE
    assert json.loads(capfd.readouterr().out)["reason"] == "receipt_write_failed"
