"""Readout evidence cannot turn missing pages into completeness or publish raw payloads."""
import importlib.util
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

URL = "https://monitoring.googleapis.com/v3/projects/test-project/timeSeries"


def load_readout():
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("capacity_readout", root / "ops/capacity/readout.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TrackedBody(io.BytesIO):
    """Error body that records each read size and the bytes consumed, so the read cap can be asserted
    even after urllib's HTTPError wrapper has closed the stream."""

    def __init__(self, data):
        super().__init__(data)
        self.requested = []
        self.consumed = 0

    def read(self, size=-1):
        self.requested.append(size)
        chunk = super().read(size)
        self.consumed += len(chunk)
        return chunk


def fail_with_http_error(module, monkeypatch, body, code=403):
    """Make the module's urlopen raise HTTPError(code) with a fresh copy of `body`; returns the bodies served."""
    served = []

    def urlopen(request, timeout):
        served.append(TrackedBody(body))
        raise HTTPError(request.full_url, code, "Forbidden", {}, served[-1])

    monkeypatch.setattr(module, "urlopen", urlopen)
    return served


def test_capacity_readout_keeps_coverage_and_sanitizes_evidence(monkeypatch):
    module = load_readout()
    start, end = "2026-09-28T05:55:00Z", "2026-09-28T07:10:00Z"
    for invalid in ("2026-09-28", "2026-09-28T05:55:00+00:00", "$(touch /tmp/bad)"):
        with pytest.raises(ValueError):
            module.window(invalid, end)
    with pytest.raises(ValueError):
        module.window(end, start)
    with pytest.raises(ValueError):
        module.window(start, "2026-09-28T09:55:00Z")
    with pytest.raises(ValueError):
        module.window("2999-01-01T00:00:00Z", "2999-01-01T00:01:00Z")

    requests = []
    secret = "PRIVATE-MESSAGE-TOKEN-EMAIL"
    api = module.Api("unused-private-token")
    monkeypatch.setattr(api, "request", _fake_request(module, requests, start, secret))
    result = module.collect(api, "test-project", "us-west1", start, end)
    executions = result["executions"]["earningsnerd-pregenerate"]
    assert executions["outside_scope_count"] == 1
    assert result["error_logs"]["outside_scope_count"] == 1
    assert len(result["error_logs"]["items"]) == 1
    assert len(result["executions"]) == 8
    assert executions["state"] == "complete"
    assert executions["pages"] == 2
    assert len(executions["items"]) == 1
    assert executions["unplaced_count"] == 1
    assert executions["items"][0]["task_configuration"] == {"maxRetries": 0}
    assert result["database_connections"]["state"] == "partial"
    assert result["database_connections"]["error"] == "invalid_pagination"
    assert result["request_count"]["state"] == "unavailable"
    assert result["request_count"]["error"] == "http_403"
    assert result["request_latencies"]["state"] == "complete"
    assert result["request_latencies"]["items"] == []  # no fabricated zero sample
    assert result["error_logs"]["items"][0]["pool_timeout_signature"] is True
    assert secret not in json.dumps(result)
    assert all(not post or url.endswith("/entries:list") for url, _, post in requests)
    # Additive receipt keys at schema_version 1; a window ending well past the metric visibility lag is unflagged.
    assert result["schema_version"] == 1
    assert set(result) == {"schema_version", "observed_at", "project", "region", "window", "limits", "interpretation",
                           "executions", "database_connections", "request_count", "request_latencies",
                           "worker_request_count", "worker_request_latencies", "queue_depth", "queue_task_attempts",
                           "error_logs", "worker_error_logs"}
    assert set(result["window"]) == {"start", "end", "end_age_seconds"} and result["window"]["end_age_seconds"] > 300
    logs = result["error_logs"]
    assert logs["counts_by_severity"] == {"ERROR": 1} and logs["pool_timeout_signature_count"] == 1
    assert logs["counts_basis"] == module.COUNTS_BASIS
    assert logs["items"][0]["resource"] == {"service_name": "earningsnerd-backend", "revision_name": "r1", "location": "us-west1"}
    # Worker series keep only the response labels and the revision identity; no scoping keys are added.
    worker_count = result["worker_request_count"]
    assert worker_count["state"] == "complete" and "outside_scope_count" not in worker_count and "note" not in worker_count
    assert worker_count["items"][0]["metric"]["labels"] == {"response_code": "503", "response_code_class": "5xx"}
    assert worker_count["items"][0]["resource"] == {"type": "cloud_run_revision", "labels": {
        "service_name": module.WORKER, "revision_name": "w1", "location": "us-west1"}}
    latency = result["worker_request_latencies"]["items"][0]["points"][0]["value"]["distributionValue"]
    assert latency["bucketCounts"] == ["1", "1", "0", "0"] and "bucketOptions" in latency and "exemplars" not in latency
    # Queue channels are filtered server-side by type and location only and re-scoped locally on either queue_id form.
    assert result["queue_depth"] == {"state": "complete", "pages": 1, "items": [], "outside_scope_count": 0,
                                     "aggregation": "none; original series and sample intervals retained",
                                     "note": module.QUEUE_NOTE}
    attempts = result["queue_task_attempts"]
    assert attempts["state"] == "complete" and len(attempts["items"]) == 2 and attempts["outside_scope_count"] == 1
    assert {item["resource"]["labels"]["queue_id"] for item in attempts["items"]} == {
        "earningsnerd-background", "projects/test-project/locations/us-west1/queues/earningsnerd-background"}
    assert attempts["items"][0]["metric"] == {"type": "cloudtasks.googleapis.com/queue/task_attempt_count",
                                              "labels": {"response_code": "ok"}}
    assert attempts["items"][0]["resource"]["labels"] == {"location": "us-west1", "queue_id": "earningsnerd-background"}
    worker_logs = result["worker_error_logs"]
    assert worker_logs["state"] == "complete" and worker_logs["outside_scope_count"] == 1
    assert worker_logs["counts_by_severity"] == {"ERROR": 1} and worker_logs["pool_timeout_signature_count"] == 0
    assert worker_logs["items"] == [{"timestamp": start, "severity": "ERROR", "pool_timeout_signature": False,
                                     "resource": {"service_name": module.WORKER, "revision_name": "w1", "location": "us-west1"}}]
    assert "example.invalid" not in json.dumps(result) and "requestUrl" not in json.dumps(result)
    filters = [params["filter"] for _, params, _ in requests if "filter" in params]
    assert sum(module.WORKER in query for query in filters) == 3
    assert sum('resource.type="cloud_tasks_queue" AND resource.labels.location="us-west1"' in query for query in filters) == 2
    assert sum(url.endswith("/entries:list") for url, _, _ in requests) == 2
    # A finite page cap is a partial result even if every received page parsed successfully.
    monkeypatch.setattr(module, "MAX_PAGES", 1)
    limited = api.pages("https://run.googleapis.com/executions", {}, "executions")
    assert limited["state"] == "partial" and limited["error"] == "page_limit"
    histogram = module.metric({"points": [{"value": {"distributionValue": {
        "count": "2", "mean": 30, "bucketCounts": ["1", "1"],
        "exemplars": [{"attachments": [secret]}]}}}]})
    assert secret not in json.dumps(histogram)
    assert histogram["points"][0]["value"]["distributionValue"]["count"] == "2"


def _fake_request(module, requests, start, secret, *, break_queue=False, break_worker_logs=False, break_executions=False):
    """An Api.request fake serving every channel collect() reads; `secret` rides in every field a projection
    must drop (labels, payloads, request URLs, exemplars, a foreign queue). The break flags append a non-dict
    item to one Monitoring and one Logging channel, and a non-dict item plus a non-string startTime to the pregenerate
    executions: a shape surprise must never abort the receipt."""
    run = {"name": "projects/test-project/locations/us-west1/jobs/earningsnerd-pregenerate/executions/a",
           "createTime": "2026-09-28T05:50:00Z", "startTime": "2026-09-28T06:00:00Z",
           "completionTime": "2026-09-28T06:20:00Z", "taskCount": 1,
           "template": {"maxRetries": 0, "containers": [{"image": "image@sha256:abc",
                         "args": [secret], "env": [{"value": secret}]}]},
           "conditions": [{"type": "Completed", "state": "CONDITION_SUCCEEDED", "message": secret}]}
    series = {"metricKind": "GAUGE", "valueType": "INT64",
              "metric": {"type": "connections", "labels": {"database": "earningsnerd", "private": secret}},
              "resource": {"labels": {"database_id": "test-project:earningsnerd-db", "private": secret}},
              "points": [{"interval": {"endTime": "2026-09-28T06:01:00Z"},
                          "value": {"int64Value": "12"}}]}
    worker_series = {"metricKind": "DELTA", "valueType": "INT64",
                     "metric": {"type": "run.googleapis.com/request_count",
                                "labels": {"response_code": "503", "response_code_class": "5xx", "route": secret}},
                     "resource": {"type": "cloud_run_revision", "labels": {
                         "service_name": module.WORKER, "revision_name": "w1", "location": "us-west1",
                         "project_id": "test-project", "private": secret}},
                     "points": [{"interval": {"startTime": start, "endTime": "2026-09-28T06:01:00Z"},
                                 "value": {"int64Value": "3"}}]}
    worker_latency = {"metricKind": "DELTA", "valueType": "DISTRIBUTION", "unit": "ms",
                      "metric": {"type": "run.googleapis.com/request_latencies", "labels": {"response_code_class": "2xx"}},
                      "resource": {"type": "cloud_run_revision", "labels": {"service_name": module.WORKER, "location": "us-west1"}},
                      "points": [{"interval": {"endTime": "2026-09-28T06:01:00Z"}, "value": {"distributionValue": {
                          "count": "2", "mean": 30,
                          "bucketOptions": {"exponentialBuckets": {"numFiniteBuckets": 2, "growthFactor": 2, "scale": 1}},
                          "bucketCounts": ["1", "1", "0", "0"], "exemplars": [{"attachments": [secret]}]}}}]}

    def attempts(queue_id):
        return {"metricKind": "DELTA", "valueType": "INT64",
                "metric": {"type": "cloudtasks.googleapis.com/queue/task_attempt_count", "labels": {"response_code": "ok"}},
                "resource": {"type": "cloud_tasks_queue", "labels": {"queue_id": queue_id, "location": "us-west1",
                                                                      "project_id": "test-project", "target_type": "HTTP"}},
                "points": [{"interval": {"startTime": start, "endTime": "2026-09-28T06:01:00Z"},
                            "value": {"int64Value": "4"}}]}

    def request(url, params, post=False):
        requests.append((url, dict(params), post))
        if "run.googleapis.com" in url:
            if "/jobs/" in url and "/jobs/earningsnerd-pregenerate/" not in url:
                return {"executions": []}, None
            if params.get("pageToken"):
                return {"executions": [{"name": run["name"] + "-old", "createTime": "2026-09-28T04:00:00Z",
                         "completionTime": "2026-09-28T05:00:00Z"}]}, None
            broken = ["not-a-dict", {"name": run["name"] + "-badstart", "createTime": "2026-09-28T05:50:00Z", "startTime": 5}]
            return {"executions": [run, {"name": run["name"] + "-unplaced"}, {"name": run["name"].replace("earningsnerd-pregenerate", "unrelated-private-job")}]
                    + (broken if break_executions else []), "nextPageToken": "second"}, None
        if "monitoring.googleapis.com" in url:
            query = params["filter"]
            if module.WORKER in query:
                return {"timeSeries": [worker_series if "request_count" in query else worker_latency]}, None
            if "cloud_tasks_queue" in query:
                assert "queue_id" not in query, "queue identity is re-scoped locally, not filtered server-side"
                if "task_attempt_count" in query:
                    items = [attempts("earningsnerd-background"),
                             attempts("projects/test-project/locations/us-west1/queues/earningsnerd-background"),
                             attempts("other-queue-" + secret)]
                    return {"timeSeries": items + (["not-a-dict"] if break_queue else [])}, None
                return {"timeSeries": []}, None
            if "request_count" in query:
                return None, "http_403"
            if "request_latencies" in query:
                return {"timeSeries": []}, None
            return {"timeSeries": [series], "nextPageToken": "repeated"}, None
        assert url == "https://logging.googleapis.com/v2/entries:list" and post
        service_entry = {"timestamp": start, "severity": "ERROR",
                         "textPayload": "QueuePool limit " + secret,
                         "httpRequest": {"requestUrl": secret},
                         "resource": {"type": "cloud_run_revision", "labels": {"location": "us-west1", "service_name": "earningsnerd-backend", "revision_name": "r1", "private": secret}}}
        if module.WORKER in params["filter"]:
            worker_entry = {"timestamp": start, "severity": "ERROR",
                            "textPayload": "Durable task failed " + secret, "jsonPayload": {"message": secret},
                            "httpRequest": {"requestUrl": "https://" + secret + ".example.invalid/internal/tasks/execute",
                                            "status": 503},
                            "resource": {"type": "cloud_run_revision", "labels": {
                                "location": "us-west1", "service_name": module.WORKER, "revision_name": "w1", "private": secret}}}
            return {"entries": [worker_entry, service_entry] + (["not-a-dict"] if break_worker_logs else [])}, None
        return {"entries": [service_entry,
                            {"resource": {"type": "cloud_run_job", "labels": {"location": "europe-west1", "job_name": "unrelated-private-job"}}}]}, None

    return request


def test_capacity_readout_records_structured_http_error_detail_without_body(monkeypatch):
    module = load_readout()
    secret = "PRIVATE-MESSAGE-TOKEN-EMAIL"
    message = "Permission 'monitoring.timeSeries.list' denied on resource 'projects/test-project' " + "x" * 400
    body = json.dumps({"error": {
        "code": 403, "message": message, "status": "PERMISSION_DENIED",
        "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "IAM_PERMISSION_DENIED",
                     "domain": "monitoring.googleapis.com", "metadata": {"permission": secret}},
                    {"@type": "type.googleapis.com/google.rpc.DebugInfo", "detail": secret}],
        "errors": [{"message": secret}]}, "trace": secret}).encode()
    fail_with_http_error(module, monkeypatch, body)
    api = module.Api("unused-private-token")
    assert api.request(URL, {"pageSize": 1}) == (None, "http_403")  # tuple shape unchanged
    detail = api.last_error_detail
    assert detail["status"] == "PERMISSION_DENIED"
    assert detail["code"] == 403
    assert detail["reason"] == "IAM_PERMISSION_DENIED"
    assert detail["domain"] == "monitoring.googleapis.com"
    assert detail["message"] == message[:240] and len(detail["message"]) == 240
    assert detail["message_truncated"] is True  # the receipt says the 240 characters are not the whole message
    assert set(detail) == {"status", "code", "reason", "domain", "message", "message_truncated"}  # nothing else leaked
    assert secret not in json.dumps(detail)
    page = api.pages(URL, {"pageSize": 1}, "timeSeries")
    assert page["state"] == "unavailable" and page["error"] == "http_403" and page["pages"] == 0
    assert page["error_detail"] == detail
    assert secret not in json.dumps(page) and "unused-private-token" not in json.dumps(page)
    # The receipt surfaces the same detail next to each source's existing error string.
    result = module.collect(api, "test-project", "us-west1", "2026-09-28T05:55:00Z", "2026-09-28T07:10:00Z")
    assert result["request_count"]["error"] == "http_403"
    assert result["request_count"]["error_detail"]["reason"] == "IAM_PERMISSION_DENIED"
    assert result["error_logs"]["error_detail"]["status"] == "PERMISSION_DENIED"
    for name in ("worker_request_count", "worker_request_latencies", "queue_depth", "queue_task_attempts",
                 "worker_error_logs"):
        assert result[name]["state"] == "unavailable" and result[name]["error"] == "http_403", name
        assert result[name]["error_detail"]["status"] == "PERMISSION_DENIED", name
    assert result["worker_error_logs"]["items"] == [] and result["worker_error_logs"]["counts_by_severity"] == {}
    assert result["queue_depth"]["outside_scope_count"] == 0
    assert secret not in json.dumps(result)

    # A transport failure carries no detail: no key is written and the previous detail is cleared.
    def unreachable(request, timeout):
        raise URLError("unreachable")

    monkeypatch.setattr(module, "urlopen", unreachable)
    page = api.pages(URL, {"pageSize": 1}, "timeSeries")
    assert page["error"] == "transport_or_decode_error" and "error_detail" not in page
    assert api.last_error_detail is None


def test_capacity_readout_marks_projection_errors_unavailable_and_flags_fresh_windows(monkeypatch):
    """An item that does not project marks its own channel unavailable (never the receipt); a window ending
    inside the metric visibility lag is flagged, not rejected."""
    module = load_readout()
    start, end = "2026-09-28T05:55:00Z", "2026-09-28T07:10:00Z"
    secret = "PRIVATE-MESSAGE-TOKEN-EMAIL"
    api = module.Api("unused-private-token")
    monkeypatch.setattr(api, "request", _fake_request(module, [], start, secret, break_queue=True, break_worker_logs=True,
                                                      break_executions=True))
    result = module.collect(api, "test-project", "us-west1", start, end)
    executions = result["executions"]["earningsnerd-pregenerate"]
    # A non-dict execution and a non-string startTime count as unplaced beside the record missing its createTime.
    assert executions["unplaced_count"] == 3 and len(executions["items"]) == 1 and executions["outside_scope_count"] == 1
    attempts = result["queue_task_attempts"]
    assert (attempts["state"], attempts["error"], attempts["items"]) == ("unavailable", "projection_error", [])
    worker_logs = result["worker_error_logs"]
    assert (worker_logs["state"], worker_logs["error"], worker_logs["items"]) == ("unavailable", "projection_error", [])
    assert worker_logs["counts_by_severity"] == {} and worker_logs["pool_timeout_signature_count"] == 0
    assert result["queue_depth"]["state"] == "complete" and result["worker_request_count"]["state"] == "complete"
    assert secret not in json.dumps(result)

    now = datetime.now(timezone.utc)
    fresh_end = (now - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_start = (now - timedelta(seconds=1830)).strftime("%Y-%m-%dT%H:%M:%SZ")
    monkeypatch.setattr(api, "request", _fake_request(module, [], fresh_start, secret))
    fresh = module.collect(api, "test-project", "us-west1", fresh_start, fresh_end)
    assert fresh["window"]["freshness"] == "tail_within_visibility_lag" and fresh["window"]["end_age_seconds"] < 300
    assert secret not in json.dumps(fresh)


def test_capacity_readout_records_non_json_error_body_as_sentinel(monkeypatch):
    module = load_readout()
    secret = "PRIVATE-MESSAGE-TOKEN-EMAIL"
    fail_with_http_error(module, monkeypatch, ("<html>Forbidden " + secret + "</html>").encode())
    api = module.Api("unused-private-token")
    page = api.pages(URL, {"pageSize": 1}, "timeSeries")
    assert page["error"] == "http_403"
    assert page["error_detail"] == {"body": "non_json_or_unreadable"}
    assert secret not in json.dumps(page)
    # Valid JSON that is not a Google error envelope records nothing rather than a misleading sentinel.
    fail_with_http_error(module, monkeypatch, json.dumps({"unexpected": secret}).encode())
    page = api.pages(URL, {"pageSize": 1}, "timeSeries")
    assert page["error"] == "http_403" and "error_detail" not in page
    assert secret not in json.dumps(page)


def test_capacity_readout_reads_error_body_once_within_cap_and_names_truncation(monkeypatch):
    module = load_readout()
    secret = "PRIVATE-MESSAGE-TOKEN-EMAIL"
    oversized = json.dumps({"error": {"code": 403, "status": "PERMISSION_DENIED",
                                      "message": "x" * (32 * 1024) + secret}}).encode()
    assert len(oversized) > module.MAX_ERROR_BODY == 8 * 1024
    served = fail_with_http_error(module, monkeypatch, oversized)
    api = module.Api("unused-private-token")
    page = api.pages(URL, {"pageSize": 1}, "timeSeries")
    assert len(served) == 1
    assert served[0].requested == [module.MAX_ERROR_BODY]  # one bounded read; never read()/read(-1)
    assert served[0].consumed == module.MAX_ERROR_BODY < len(oversized)
    # A valid envelope cut at the cap cannot parse; the sentinel says so instead of blaming the API's format.
    assert page["error_detail"] == {"body": "truncated_or_non_json"}
    assert secret not in json.dumps(page)
    # A short non-JSON body keeps the plain sentinel (the format, not the cap, is the reason).
    fail_with_http_error(module, monkeypatch, b"<html>Forbidden</html>")
    assert api.pages(URL, {"pageSize": 1}, "timeSeries")["error_detail"] == {"body": "non_json_or_unreadable"}


def test_capacity_readout_bounds_every_detail_field_and_states_the_bounds(monkeypatch):
    module = load_readout()
    body = json.dumps({"error": {
        "code": 403, "message": "short", "status": "S" * 500,
        "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "R" * 500,
                     "domain": "D" * 500}]}}).encode()
    assert len(body) < module.MAX_ERROR_BODY  # the envelope parses; only the fields are long
    fail_with_http_error(module, monkeypatch, body)
    api = module.Api("unused-private-token")
    assert api.request(URL, {"pageSize": 1}) == (None, "http_403")
    detail = api.last_error_detail
    assert module.MAX_ERROR_FIELD == 64
    assert detail["status"] == "S" * 64 and detail["reason"] == "R" * 64 and detail["domain"] == "D" * 64
    assert detail["message"] == "short" and "message_truncated" not in detail  # nothing was cut
    assert set(detail) == {"status", "code", "reason", "domain", "message"}
    # The receipt names the bounds a reader needs to interpret a cut message or a truncation sentinel.
    result = module.collect(api, "test-project", "us-west1", "2026-09-28T05:55:00Z", "2026-09-28T07:10:00Z")
    assert result["limits"]["max_error_body_bytes"] == module.MAX_ERROR_BODY == 8 * 1024
    assert result["limits"]["max_error_message_chars"] == module.MAX_ERROR_MESSAGE == 240


def test_capacity_readout_error_detail_never_aborts_the_receipt(monkeypatch):
    """A body that breaks the parser (deep nesting raises RecursionError inside json) is recorded as the
    sentinel; request() still returns its http_NNN error and collect() still writes a receipt."""
    module = load_readout()
    nested = b"[" * 4000
    assert len(nested) < module.MAX_ERROR_BODY
    with pytest.raises(RecursionError):
        json.loads(nested)
    fail_with_http_error(module, monkeypatch, nested)
    api = module.Api("unused-private-token")
    assert api.request(URL, {"pageSize": 1}) == (None, "http_403")
    assert api.last_error_detail == {"body": "non_json_or_unreadable"}
    result = module.collect(api, "test-project", "us-west1", "2026-09-28T05:55:00Z", "2026-09-28T07:10:00Z")
    assert result["request_count"]["error"] == "http_403"
    assert result["request_count"]["error_detail"] == {"body": "non_json_or_unreadable"}
    # A body with no readable stream at all (fp=None) is the same recorded reason, not an exception.
    monkeypatch.setattr(module, "urlopen",
                        lambda request, timeout: (_ for _ in ()).throw(HTTPError(URL, 403, "Forbidden", {}, None)))
    assert api.request(URL, {"pageSize": 1}) == (None, "http_403")
    assert api.last_error_detail == {"body": "non_json_or_unreadable"}
