"""Fixed incident readout: source attribution, bounded census and no raw log disclosure."""
import copy
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from tests.support.ops_workflow import BY_NAME, OPS, OPTIONS, PROXY, selected

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("regn_incident", ROOT / "ops/diagnostics/regn_summary_incident.py")
incident = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(incident)
OPERATION = "regn-summary-incident-readout"
PRIVATE = "PRIVATE_VALUE_SENTINEL reader@example.invalid https://private.example.invalid/?token=private"


def entry(message, *, exception="", filing=45003):
    return {"timestamp": "2026-10-30T11:05:22.086123456Z", "insertId": PRIVATE,
            "httpRequest": {"requestUrl": PRIVATE},
            "resource": {"type": "cloud_run_revision", "labels": {
                "service_name": incident.SERVICE, "revision_name": incident.REVISION, "private": PRIVATE}},
            "jsonPayload": {"message": f"[stream:{filing}] {message}", "exception": exception,
                            "correlation_id": PRIVATE, "user_id": PRIVATE, "headers": PRIVATE}}


@pytest.mark.parametrize("status,reason", [(403, "http_forbidden"), (429, "http_rate_limited"),
    (404, "http_not_found"), (500, "http_server_error"), (503, "http_server_error"), (401, "http_other_client_error")])
def test_fetch_error_identifies_only_the_transport_status_prefix(status, reason):
    record = entry(f"Error fetching SEC document: Failed to fetch document: Client error '{status} Reason' for url '{PRIVATE}'",
                   exception=PRIVATE)
    result = incident.receipt([record])
    assert result["entries"][0]["reason"] == reason
    assert result["entries"][0]["upstream_http_status"] == status
    assert result["entries"][0]["stage"] == "document_fetch_error"
    assert "PRIVATE" not in json.dumps(result) and "example.invalid" not in json.dumps(result)


@pytest.mark.parametrize("message,exception,reason", [
    ("Failed to fetch document: " + PRIVATE, "httpx.ReadTimeout: " + PRIVATE, "timeout"),
    ("Failed to fetch document: " + PRIVATE, "httpx.ConnectError: " + PRIVATE, "connection_error"),
    ("Failed to fetch document: " + PRIVATE, "httpx.InvalidURL: " + PRIVATE, "invalid_url"),
    ("SEC EDGAR circuit breaker is open: " + PRIVATE, PRIVATE, "circuit_open"),
    ("Filing document is empty or inaccessible", PRIVATE, "empty_document"),
    ("Failed to fetch document: " + PRIVATE + " 403", PRIVATE, "unclassified"),
    ("Failed to fetch document: " + PRIVATE, "url httpx.ReadTimeout: "+PRIVATE, "unclassified"),
])
def test_non_http_causes_keep_only_closed_codes(message, exception, reason):
    result = incident.receipt([entry("Error fetching SEC document: " + message, exception=exception)])
    assert result["entries"][0]["reason"] == reason
    assert result["entries"][0]["upstream_http_status"] is None
    assert PRIVATE not in json.dumps(result)


@pytest.mark.parametrize("message,stage", [
    ("Starting SEC fetch for URL: " + PRIVATE, "document_fetch_started"),
    ("SEC fetch completed. Text length: 123", "document_fetched"),
    ("Skipping main thread SEC fetch, using cache.", "document_cache_hit"),
    ("Yielding fetching stage", "fetching"),
    ("SEC fetch heartbeat 1: " + PRIVATE, "document_fetch_waiting"),
    ("Pipeline timeout after 420s", "pipeline_error"),
    ("Error in streaming summary: " + PRIVATE, "pipeline_error"),
    (PRIVATE, "other_stream_event"),
])
def test_stages_do_not_disclose_messages_or_exception_text(message, stage):
    result = incident.receipt([entry(message, exception=PRIVATE, filing=45004)])
    assert result["entries"][0]["filing_id"] == 45004
    assert result["entries"][0]["stage"] == stage
    assert PRIVATE not in json.dumps(result)
    assert set(result["entries"][0]) == {"filing_id", "timestamp", "stage", "reason", "upstream_http_status"}


def test_privacy_projection_rejects_other_filings_resources_and_malformed_fields():
    original = entry("Yielding fetching stage")
    variants = [None, PRIVATE, [], {"timestamp": PRIVATE}]
    for key, value in [("timestamp", PRIVATE), ("timestamp", "2026-10-30T11:15:00Z"),
                       ("timestamp", "2026-10-30T10:59:59Z"), ("timestamp", "2026-02-30T11:05:00Z"),
                       ("jsonPayload", [PRIVATE]), ("resource", {"type": PRIVATE})]:
        variants.append(dict(original, **{key: value}))
    for key in ("service_name", "revision_name"):
        item = copy.deepcopy(original)
        item["resource"]["labels"][key] = PRIVATE
        variants.append(item)
    variants.append(entry("Yielding fetching stage", filing=45005))
    result = incident.receipt(variants)
    assert result["state"] == "partial" and result["entries"] == []
    assert result["scope_or_shape_rejected"] == len(variants)
    assert "PRIVATE" not in json.dumps(result) and "example.invalid" not in json.dumps(result)


def test_text_payload_fallback_has_the_same_projection():
    record = entry("Yielding fetching stage")
    record["textPayload"] = record.pop("jsonPayload")["message"]
    assert incident.receipt([record])["entries"][0]["stage"] == "fetching"


def test_record_limit_and_invalid_envelope_cannot_claim_a_complete_census():
    record = entry("Yielding fetching stage")
    assert incident.receipt([record] * 500)["state"] == "complete"
    result = incident.receipt([record] * 501)
    assert result["state"] == "truncated" and len(result["entries"]) == 500
    assert incident.receipt({PRIVATE: PRIVATE}) == incident.unavailable("invalid_response")


def test_read_command_is_fixed_bounded_and_never_calls_sec_or_a_write(monkeypatch):
    calls = []

    def fake(argv, *, stderr, timeout):
        calls.append(argv)
        assert stderr is subprocess.DEVNULL and timeout == 60
        return json.dumps([entry("Yielding fetching stage")]).encode()

    monkeypatch.setattr(subprocess, "check_output", fake)
    assert incident.collect()["state"] == "complete"
    assert len(calls) == 1
    argv = calls[0]
    assert argv[:3] == ["gcloud", "logging", "read"]
    assert "--project=earnings-nerd" in argv and "--limit=501" in argv and "--order=asc" in argv
    assert 'timestamp>="2026-10-30T11:00:00Z"' in argv[3]
    assert 'timestamp<"2026-10-30T11:15:00Z"' in argv[3]
    assert 'resource.labels.revision_name="earningsnerd-backend-00661-zr9"' in argv[3]
    assert "45003" in argv[3] and "45004" in argv[3]


@pytest.mark.parametrize("fault,reason", [
    (subprocess.TimeoutExpired("private-command", 60, output=PRIVATE), "command_timeout"),
    (subprocess.CalledProcessError(1, "private-command", output=PRIVATE, stderr=PRIVATE), "gcloud_failed"),
    (OSError(PRIVATE), "command_unavailable"),
    (b"[" + b"x" * (8 * 1024 * 1024), "response_size_limit"),
    (PRIVATE.encode(), "invalid_response"),
    (b"null", "invalid_response"),
])
def test_reader_failures_never_print_raw_stdout_stderr_or_exception(monkeypatch, capsys, fault, reason):
    def fake(*args, **kwargs):
        if isinstance(fault, Exception):
            raise fault
        return fault

    monkeypatch.setattr(subprocess, "check_output", fake)
    monkeypatch.setattr(incident.sys, "argv", ["readout.py"])
    assert incident.main() == 1
    out = capsys.readouterr()
    assert json.loads(out.out) == incident.unavailable(reason)
    assert out.err == "" and "PRIVATE" not in out.out and "private-command" not in out.out


def test_cli_refuses_arguments_without_a_read(monkeypatch, capsys):
    monkeypatch.setattr(incident.sys, "argv", ["readout.py", PRIVATE])
    monkeypatch.setattr(incident, "collect", lambda: pytest.fail("must not read"))
    assert incident.main() == 1
    assert json.loads(capsys.readouterr().out) == incident.unavailable("arguments_not_supported")


def test_workflow_runs_only_the_fixed_diagnostic_without_database_or_apply_steps():
    assert OPERATION in OPTIONS
    step = BY_NAME["Read REGN summary incident classifications"][1]
    assert selected(step) == {OPERATION}
    assert step["run"] == "python3 ops/diagnostics/regn_summary_incident.py"
    assert step["timeout-minutes"] == "2" and "continue-on-error" not in step and "env" not in step
    assert OPERATION not in selected(BY_NAME[PROXY][1])
    assert OPERATION not in selected(OPS["jobs"]["approve-apply"])
    assert OPERATION not in selected(BY_NAME["Refuse to run while a main push (deploy) is in flight"][1])
    assert "github.ref == 'refs/heads/main'" in OPS["jobs"]["ops"]["if"]
    assert set(step) == {"name", "if", "timeout-minutes", "run"}
