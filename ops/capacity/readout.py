"""Bounded, read-only Cloud Run/Monitoring/Logging evidence; no raw logs or env values.

Run with an existing gcloud identity. Missing permissions/data are recorded, never zeroed; a failed
API call keeps only its structured error status, reason and a bounded message, never the raw body.
The receipt is evidence to inspect, not a capacity verdict or an invitation limit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SERVICE = "earningsnerd-backend"
INSTANCE = "earningsnerd-db"
REGION = "us-west1"
JOBS = ("pregenerate", "filing-scan", "filing-digest", "backfill-facts",
        "earnings-calendar-refresh", "earnings-day-alerts", "notable-filings", "retention-purge")
MAX_PAGES = 5
MAX_RESPONSE = 8 * 1024 * 1024
MAX_ERROR_BODY = 8 * 1024
MAX_ERROR_MESSAGE = 240


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def window(start, end):
    pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
    if not all(re.fullmatch(pattern, value) for value in (start, end)):
        raise ValueError("Use UTC YYYY-MM-DDTHH:MM:SSZ timestamps")
    first, last = timestamp(start), timestamp(end)
    if not 0 < (last - first).total_seconds() <= 7200:
        raise ValueError("Window must be positive and at most two hours")
    if last > datetime.now(timezone.utc):
        raise ValueError("Window must end in the past")
    return first, last


def error_detail(exc):
    """Bounded, structured reason from a Google API error envelope; never the raw body or headers.

    Keeps only error.status, error.code, the first ErrorInfo detail's reason/domain and at most
    MAX_ERROR_MESSAGE characters of error.message, reading at most MAX_ERROR_BODY bytes.
    """
    try:
        envelope = json.loads(exc.read(MAX_ERROR_BODY))
    except (OSError, ValueError, HTTPException):
        return {"body": "non_json_or_unreadable"}
    error = envelope.get("error") if isinstance(envelope, dict) else None
    if not isinstance(error, dict):
        return {}  # JSON, but not a Google API error envelope: nothing recognised to record.
    detail = {}
    if isinstance(error.get("status"), str):
        detail["status"] = error["status"]
    if isinstance(error.get("code"), int):
        detail["code"] = error["code"]
    details = error.get("details") if isinstance(error.get("details"), list) else []
    for info in details:
        if isinstance(info, dict) and isinstance(info.get("@type"), str) and info["@type"].endswith("ErrorInfo"):
            detail.update({key: info[key] for key in ("reason", "domain") if isinstance(info.get(key), str)})
            break
    if isinstance(error.get("message"), str):
        detail["message"] = error["message"][:MAX_ERROR_MESSAGE]
    return detail


class Api:
    def __init__(self, token):
        self.token = token
        # Structured reason for the latest failed request(), or None. It lives on the instance so
        # request() keeps its (data, error) return shape and existing callers and fakes stay unchanged.
        self.last_error_detail = None

    def request(self, url, params, post=False):
        self.last_error_detail = None
        # Hosts and paths are code-owned; no endpoint/SQL/command comes from workflow input.
        body = json.dumps(params).encode() if post else None
        request = Request(url if post else url + "?" + urlencode(params), data=body,
                          headers={"Authorization": "Bearer " + self.token,
                                   "Content-Type": "application/json"})
        try:
            # HTTPS endpoints are code-owned; project/region cannot supply a URL scheme.
            with urlopen(request, timeout=10) as response:  # nosec B310
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                return None, "response_size_limit"
            return json.loads(raw), None
        except HTTPError as exc:
            # Never echo response bodies or auth headers; keep only the bounded, structured reason.
            self.last_error_detail = error_detail(exc)
            return None, "http_" + str(exc.code)
        except (URLError, TimeoutError, OSError, ValueError):
            return None, "transport_or_decode_error"

    def pages(self, url, params, key, *, post=False):
        items, tokens = [], set()
        params = dict(params)
        for page in range(1, MAX_PAGES + 1):
            data, error = self.request(url, params, post)
            if error or not isinstance(data, dict) or not isinstance(data.get(key, []), list):
                failure = {"state": "partial" if items else "unavailable", "pages": page - 1,
                           "error": error or "invalid_response", "items": items}
                if self.last_error_detail:
                    failure["error_detail"] = self.last_error_detail
                return failure
            items.extend(data.get(key, []))
            token = data.get("nextPageToken")
            if not token:
                return {"state": "complete", "pages": page, "items": items}
            if not isinstance(token, str) or token in tokens:
                return {"state": "partial", "pages": page, "error": "invalid_pagination", "items": items}
            tokens.add(token)
            params["pageToken"] = token
        return {"state": "partial", "pages": MAX_PAGES, "error": "page_limit", "items": items}


def pick(value, keys):
    return {key: value[key] for key in keys if key in value}


def execution(record):
    result = pick(record, ("name", "job", "createTime", "startTime", "completionTime",
                           "parallelism", "taskCount", "runningCount", "succeededCount",
                           "failedCount", "cancelledCount", "retriedCount"))
    template = record.get("template", {})
    result["task_configuration"] = pick(template, ("maxRetries", "timeout"))
    # Arguments, environment, labels and error messages may contain secrets/customer data.
    result["images"] = [c.get("image") for c in template.get("containers", [])]
    result["conditions"] = [pick(c, ("type", "state", "lastTransitionTime", "reason"))
                            for c in record.get("conditions", [])]
    return result


def metric(record):
    result = pick(record, ("metricKind", "valueType", "unit"))
    result["metric"] = {"type": record.get("metric", {}).get("type"), "labels": pick(
        record.get("metric", {}).get("labels", {}), ("database", "response_code", "response_code_class"))}
    result["resource"] = {"type": record.get("resource", {}).get("type"), "labels": pick(
        record.get("resource", {}).get("labels", {}),
        ("database_id", "region", "location", "service_name", "revision_name", "configuration_name"))}
    result["points"] = []
    for point in record.get("points", []):
        value = pick(point.get("value", {}), ("int64Value", "doubleValue"))
        distribution = point.get("value", {}).get("distributionValue")
        if distribution is not None:
            # Exemplars contain tracing identifiers; only numerical histogram statistics survive.
            value["distributionValue"] = pick(distribution, (
                "count", "mean", "sumOfSquaredDeviation", "range", "bucketOptions", "bucketCounts"))
        result["points"].append({"interval": pick(point.get("interval", {}), ("startTime", "endTime")),
                                 "value": value})
    return result


def log_entry(record):
    result = pick(record, ("timestamp", "severity"))
    result["resource"] = pick(record.get("resource", {}).get("labels", {}),
                              ("revision_name", "job_name", "location"))
    # Classify locally without retaining the message, payload, URL or request/user identity.
    raw = json.dumps({key: record.get(key) for key in ("textPayload", "jsonPayload")}).lower()
    result["pool_timeout_signature"] = "queuepool limit" in raw or "connection pool exhausted" in raw
    return result


def collect(api, project, region, start, end):
    first, last = window(start, end)
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]|[0-9]+", project):
        raise ValueError("Invalid project identifier")
    if region != REGION:
        raise ValueError("Only the production region is supported")
    result = {"schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
              "project": project, "region": region, "window": {"start": start, "end": end},
              "limits": {"max_pages_per_query": MAX_PAGES, "max_response_bytes": MAX_RESPONSE},
              "interpretation": "Samples are not instantaneous peaks. Empty/partial/unavailable data cannot prove headroom. Execution success is not a business outcome. Current SQL snapshots are not historical samples."}
    result["executions"] = {}
    for name in JOBS:
        job = "earningsnerd-" + name
        runs = api.pages(f"https://run.googleapis.com/v2/projects/{project}/locations/{region}/jobs/{job}/executions",
                         {"pageSize": 100, "showDeleted": "true"}, "executions")
        raw_runs = runs.pop("items")
        runs["retained_resources_inspected"] = len(raw_runs)
        runs["items"] = []
        runs["unplaced_count"] = 0
        runs["outside_scope_count"] = 0
        for record in raw_runs:
            if not re.fullmatch(r"projects/[^/]+/locations/" + region + r"/jobs/" + job + r"/executions/[^/]+",
                                record.get("name", "")):
                runs["outside_scope_count"] += 1
                continue
            try:
                begins = timestamp(record.get("startTime") or record["createTime"])
                ends = timestamp(record["completionTime"]) if record.get("completionTime") else None
                if begins < last and (ends is None or ends >= first):
                    item = execution(record)
                    item["interval_start_basis"] = "startTime" if record.get("startTime") else "createTime; actual start unknown"
                    runs["items"].append(item)
            except (KeyError, ValueError, TypeError):
                runs["unplaced_count"] += 1
        # Complete pagination is not proof of lifetime completeness or known execution intervals.
        runs["coverage"] = "retained API resources only; expired/deleted history may be absent"
        result["executions"][job] = runs
    queries = {
        "database_connections": ('cloudsql.googleapis.com/database/postgresql/num_backends',
                                 f'resource.type="cloudsql_database" AND resource.labels.database_id="{project}:{INSTANCE}"'),
        "request_count": ('run.googleapis.com/request_count',
                          f'resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICE}" AND resource.labels.location="{region}"'),
        "request_latencies": ('run.googleapis.com/request_latencies',
                              f'resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICE}" AND resource.labels.location="{region}"'),
    }
    for name, (kind, scope) in queries.items():
        data = api.pages(f"https://monitoring.googleapis.com/v3/projects/{project}/timeSeries", {
            "filter": f'metric.type="{kind}" AND {scope}', "interval.startTime": start,
            "interval.endTime": end, "view": "FULL", "pageSize": 1000}, "timeSeries")
        data["items"] = [metric(item) for item in data["items"]]
        data["aggregation"] = "none; original series and sample intervals retained"
        result[name] = data
    job_filter = " OR ".join(f'resource.labels.job_name="earningsnerd-{name}"' for name in JOBS)
    logs = api.pages("https://logging.googleapis.com/v2/entries:list", {
        "resourceNames": [f"projects/{project}"], "pageSize": 100,
        "orderBy": "timestamp asc", "filter": (
            f'timestamp>="{start}" AND timestamp<"{end}" AND '
            f'resource.labels.location="{region}" AND '
            f'((resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICE}") OR '
            f'(resource.type="cloud_run_job" AND ({job_filter}))) AND '
            '(severity>=ERROR OR "QueuePool limit" OR "connection pool exhausted")')}, "entries", post=True)
    scoped_logs = []
    logs["outside_scope_count"] = 0
    for item in logs["items"]:
        resource = item.get("resource", {})
        labels = resource.get("labels", {})
        if labels.get("location") == region and (
            resource.get("type") == "cloud_run_revision" and labels.get("service_name") == SERVICE
            or resource.get("type") == "cloud_run_job" and labels.get("job_name") in {"earningsnerd-" + name for name in JOBS}
        ):
            scoped_logs.append(log_entry(item))
        else:
            logs["outside_scope_count"] += 1
    logs["items"] = scoped_logs
    result["error_logs"] = logs
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--region", default="us-west1")
    parser.add_argument("--output", default="capacity-cloud.json")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    window(args.start, args.end)
    if args.validate_only:
        return
    def gcloud(*command):
        return subprocess.check_output(["gcloud", *command], text=True, stderr=subprocess.DEVNULL).strip()
    project = gcloud("config", "get-value", "project")
    api = Api(gcloud("auth", "print-access-token"))
    result = collect(api, project, args.region, args.start, args.end)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        os.chmod(output, 0o600)
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print("Capacity receipt saved; inspect each source's state and coverage before interpreting.")


if __name__ == "__main__":
    main()
