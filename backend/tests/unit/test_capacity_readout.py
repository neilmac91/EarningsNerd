"""Readout evidence cannot turn missing pages into completeness or publish raw payloads."""
import importlib.util
import json
from pathlib import Path

import pytest


def test_capacity_readout_keeps_coverage_and_sanitizes_evidence(monkeypatch):
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("capacity_readout", root / "ops/capacity/readout.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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
    run = {"name": "projects/test-project/locations/us-west1/jobs/pregenerate/executions/a",
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

    def request(url, params, post=False):
        requests.append((url, dict(params), post))
        if "run.googleapis.com" in url:
            if params.get("pageToken"):
                return {"executions": [{"createTime": "2026-09-28T04:00:00Z",
                         "completionTime": "2026-09-28T05:00:00Z"}]}, None
            return {"executions": [run, {"name": "unplaced"}], "nextPageToken": "second"}, None
        if "monitoring.googleapis.com" in url:
            if "request_count" in params["filter"]:
                return None, "http_403"
            if "request_latencies" in params["filter"]:
                return {"timeSeries": []}, None
            return {"timeSeries": [series], "nextPageToken": "repeated"}, None
        assert url == "https://logging.googleapis.com/v2/entries:list" and post
        return {"entries": [{"timestamp": start, "severity": "ERROR",
                             "textPayload": "QueuePool limit " + secret,
                             "httpRequest": {"requestUrl": secret},
                             "resource": {"labels": {"revision_name": "r1", "private": secret}}}]}, None

    api = module.Api("unused-private-token")
    monkeypatch.setattr(api, "request", request)
    result = module.collect(api, "test-project", "us-west1", start, end)
    assert result["executions"]["state"] == "complete"
    assert result["executions"]["pages"] == 2
    assert len(result["executions"]["items"]) == 1
    assert result["executions"]["unplaced_count"] == 1
    assert result["executions"]["items"][0]["task_configuration"] == {"maxRetries": 0}
    assert result["database_connections"]["state"] == "partial"
    assert result["database_connections"]["error"] == "invalid_pagination"
    assert result["request_count"]["state"] == "unavailable"
    assert result["request_count"]["error"] == "http_403"
    assert result["request_latencies"]["state"] == "complete"
    assert result["request_latencies"]["items"] == []  # no fabricated zero sample
    assert result["error_logs"]["items"][0]["pool_timeout_signature"] is True
    assert secret not in json.dumps(result)
    assert all(not post or url.endswith("/entries:list") for url, _, post in requests)
    # A finite page cap is a partial result even if every received page parsed successfully.
    monkeypatch.setattr(module, "MAX_PAGES", 1)
    limited = api.pages("https://run.googleapis.com/executions", {}, "executions")
    assert limited["state"] == "partial" and limited["error"] == "page_limit"
    histogram = module.metric({"points": [{"value": {"distributionValue": {
        "count": "2", "mean": 30, "bucketCounts": ["1", "1"],
        "exemplars": [{"attachments": [secret]}]}}}]})
    assert secret not in json.dumps(histogram)
    assert histogram["points"][0]["value"]["distributionValue"]["count"] == "2"
