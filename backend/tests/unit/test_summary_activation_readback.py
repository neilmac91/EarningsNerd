"""Activation evidence stays bounded, private and configuration-only at the real readers."""
import json

import pytest

from tests.unit.test_prod_flag_visibility import _execute, _readbacks, resources as renderer_resources

resources = renderer_resources

SCHEDULE = ("jobs", "describe", "summary-recovery-minute")
QUEUE = ("queues", "describe", "earningsnerd-background")
SENTINEL = "PRIVATE_ACTIVATION_SENTINEL=https://private.invalid/token?secret=opaque"


def _metadata(reads):
    reads[SCHEDULE] = {
        "state": "ENABLED", "schedule": "* * * * *", "timeZone": "Etc/UTC", "attemptDeadline": "30s",
        "httpTarget": {"httpMethod": "POST", "uri": "https://api.earningsnerd.io/internal/jobs/summary-recovery",
                       "headers": {"X-Internal-Token": SENTINEL}, "body": SENTINEL,
                       "oidcToken": {"serviceAccountEmail": SENTINEL, "audience": SENTINEL}},
        "retryConfig": {"retryCount": 0, "maxRetryDuration": "0s", "minBackoffDuration": "5s",
                        "maxBackoffDuration": "30s", "maxDoublings": 2},
    }
    reads[QUEUE] = {
        "state": "RUNNING", "name": SENTINEL,
        "rateLimits": {"maxConcurrentDispatches": 1, "maxDispatchesPerSecond": 0.2, "maxBurstSize": 1},
        "retryConfig": {"maxAttempts": 5, "maxRetryDuration": "0s", "minBackoff": "30s",
                        "maxBackoff": "900s", "maxDoublings": 5},
    }


def _line(output, prefix):
    return json.loads(next(line[len(prefix):] for line in output.splitlines() if line.startswith(prefix)))


def test_real_service_reader_reports_exact_config_without_echoing_credentials(resources):
    service, revision, job, worker, worker_revision, policy = resources
    revision["spec"]["containers"][0]["env"] += [
        {"name": "SUMMARY_DURABLE_GENERATION_ENABLED", "value": "false"},
        {"name": "SUMMARY_JOB_MAX_PENDING_PER_ACCOUNT", "value": "3"},
        {"name": "SUMMARY_PREWARM_MAX_PER_DAY", "value": "0"},
        {"name": "SEC_DISTRIBUTED_WAIT_SECONDS", "value": "10.0"},
        {"name": "INTERNAL_JOB_TOKEN", "value": SENTINEL},
    ]
    reads = _readbacks(revision, job, worker, worker_revision, policy)
    _metadata(reads)
    output, exit_, calls = _execute(service, reads)
    assert exit_ is None and len(calls) == 8
    assert SENTINEL not in output and "private.invalid" not in output
    runtime = _line(output, "Summary/SEC runtime configuration: ")
    assert runtime["fields"]["SUMMARY_DURABLE_GENERATION_ENABLED"] == {"state": "literal", "value": False}
    assert runtime["fields"]["SUMMARY_JOB_MAX_PENDING_PER_ACCOUNT"]["value"] == 3
    assert runtime["fields"]["SUMMARY_PREWARM_MAX_PER_DAY"]["value"] == 0
    assert runtime["fields"]["SEC_DISTRIBUTED_WAIT_SECONDS"]["value"] == 10
    assert runtime["fields"]["SUMMARY_NEW_JOBS_PAUSED"] == {"state": "not_set_image_default_unverified"}
    assert runtime["internal_job_token"] == {"state": "literal", "nonempty_literal": True}
    schedule = _line(output, "Activation configuration summary-recovery-minute: ")
    assert schedule["schedule"] == "* * * * *" and schedule["time_zone"] == "Etc/UTC"
    assert schedule["post_target_matches"] and schedule["internal_token_header_present"] and schedule["oidc_present"]
    assert schedule["attempt_deadline_seconds"] == 30 and schedule["retry_count"] == 0
    queue = _line(output, "Activation configuration earningsnerd-background: ")
    assert (queue["max_concurrent_dispatches"], queue["max_dispatches_per_second"], queue["max_burst_size"]) == (1, 0.2, 1)
    assert (queue["max_attempts"], queue["max_retry_duration_seconds"], queue["min_backoff_seconds"],
            queue["max_backoff_seconds"], queue["max_doublings"]) == (5, 0, 30, 900, 5)
    assert "Other caller names are not inspected" in output and "recovery success" in output
    assert "observed queue/worker/SQL aggregates" in output


@pytest.mark.parametrize("name", [
    "SUMMARY_DURABLE_GENERATION_ENABLED", "SUMMARY_NEW_JOBS_PAUSED", "SUMMARY_JOB_MAX_ATTEMPTS",
    "SUMMARY_PREWARM_MAX_PER_SCAN", "SEC_DISTRIBUTED_LIMIT_ENABLED", "SEC_DISTRIBUTED_WAIT_SECONDS",
    "DURABLE_TASKS_ENABLED", "TASKS_WORKER_PROCESS",
])
def test_malformed_activation_values_never_escape_the_complete_renderer(resources, name):
    service, revision, job, worker, worker_revision, policy = resources
    revision["spec"]["containers"][0]["env"].append({"name": name, "value": SENTINEL})
    output, exit_, _ = _execute(service, _readbacks(revision, job, worker, worker_revision, policy))
    assert exit_ is None and SENTINEL not in output
    assert _line(output, "Summary/SEC runtime configuration: ")["fields"][name] == {"state": "invalid_withheld"}


@pytest.mark.parametrize("defect", ["PERMISSION_DENIED", "NOT_FOUND", "UNAVAILABLE", "timeout", "missing"])
def test_optional_metadata_read_failure_is_qualified_and_does_not_hide_other_evidence(resources, defect):
    service, revision, job, worker, worker_revision, policy = resources
    reads = _readbacks(revision, job, worker, worker_revision, policy)
    output, exit_, calls = _execute(service, reads, denied={SCHEDULE: defect if defect in {"timeout", "missing"} else defect + SENTINEL})
    assert exit_ is None and len(calls) == 8 and calls[-1] == QUEUE
    assert SENTINEL not in output
    assert _line(output, "Activation configuration summary-recovery-minute: ")["state"] == "UNVERIFIED"
    assert output.rstrip().endswith("describe-service: PASS; UNVERIFIED: activation configuration")
    assert "other callers are not inspected" in output


@pytest.mark.parametrize("body", [None, [], {"state": {}}, {"state": SENTINEL}])
def test_malformed_metadata_cannot_be_readiness_evidence_or_printed(resources, body):
    service, revision, job, worker, worker_revision, policy = resources
    reads = _readbacks(revision, job, worker, worker_revision, policy)
    reads[SCHEDULE] = body
    output, exit_, _ = _execute(service, reads)
    assert exit_ is None and SENTINEL not in output
    assert _line(output, "Activation configuration summary-recovery-minute: ") == {"state": "unreadable_response"}
    assert "UNVERIFIED: activation configuration" in output


def test_unverified_scheduler_never_masks_a_known_unsafe_runtime(resources):
    service, revision, job, worker, worker_revision, policy = resources
    worker["metadata"]["annotations"]["run.googleapis.com/invoker-iam-disabled"] = "true"
    output, exit_, _ = _execute(service, _readbacks(revision, job, worker, worker_revision, policy), denied={SCHEDULE: "NOT_FOUND"})
    assert exit_ is not None and "describe-service: FAIL" in output and "describe-service: PASS" not in output


def test_same_projection_covers_known_jobs_and_secret_duplicate_or_out_of_range_fields(tmp_path, monkeypatch, capfd):
    from tests.unit.test_ops_describe_jobs import _container, _job, _literals, _run, _split, _step

    fixtures = {name: _job(name, pool) for name, pool in _literals(_split(_step())[1])["expected_pools"].items()}
    for job in fixtures.values():
        _container(job)["env"] += [
            {"name": "SUMMARY_DURABLE_GENERATION_ENABLED", "value": "true"},
            {"name": "SUMMARY_JOB_MAX_ATTEMPTS", "value": "9"},
            {"name": "SUMMARY_JOB_LEASE_SECONDS", "valueFrom": {"secretKeyRef": {"name": SENTINEL}}},
            {"name": "SUMMARY_PREWARM_MAX_PER_DAY", "value": "0"},
        ]
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures)
    assert exit_ is None and output.count('"SUMMARY_DURABLE_GENERATION_ENABLED": {"state": "literal", "value": true}') == 9
    assert output.count('"SUMMARY_JOB_MAX_ATTEMPTS": {"state": "invalid_withheld"}') == 9
    assert output.count('"SUMMARY_JOB_LEASE_SECONDS": {"state": "secret_ref_unresolved"}') == 9
    # Duplication is already a hard failure in both owners; the pure projection also refuses ambiguity.
    from ops.describe.summary_configuration import runtime_configuration
    assert runtime_configuration([
        {"name": "SUMMARY_NEW_JOBS_PAUSED", "value": "true"},
        {"name": "SUMMARY_NEW_JOBS_PAUSED", "value": SENTINEL},
    ])["fields"]["SUMMARY_NEW_JOBS_PAUSED"] == {"state": "duplicate_unresolved"}


def test_unknown_and_malformed_metadata_fields_remain_unknown_without_target_or_payload_leak(resources):
    service, revision, job, worker, worker_revision, policy = resources
    reads = _readbacks(revision, job, worker, worker_revision, policy)
    _metadata(reads)
    reads[SCHEDULE]["schedule"] = "99 * * * *"
    reads[SCHEDULE]["timeZone"] = SENTINEL
    reads[SCHEDULE]["httpTarget"]["uri"] = {"hidden": SENTINEL}
    reads[SCHEDULE]["httpTarget"]["headers"] = {}
    reads[QUEUE]["rateLimits"]["maxConcurrentDispatches"] = True
    reads[QUEUE]["rateLimits"]["maxDispatchesPerSecond"] = 10 ** 400
    output, exit_, _ = _execute(service, reads)
    assert exit_ is None and SENTINEL not in output
    schedule = _line(output, "Activation configuration summary-recovery-minute: ")
    assert schedule["schedule"] is None and schedule["time_zone"] is None
    assert not schedule["post_target_matches"] and not schedule["internal_token_header_present"]
    queue = _line(output, "Activation configuration earningsnerd-background: ")
    assert queue["max_concurrent_dispatches"] is None and queue["max_dispatches_per_second"] is None
