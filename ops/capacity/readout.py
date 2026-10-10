"""Bounded, read-only Cloud Run/Monitoring/Logging evidence; no raw logs or env values.

Run with an existing gcloud identity. Missing permissions/data are recorded, never zeroed; a failed
API call keeps only its structured error status, reason and a bounded, address-redacted message,
never the raw body. The receipt is evidence to inspect, not a capacity verdict or an invitation limit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SERVICE = "earningsnerd-backend"
WORKER = "earningsnerd-task-worker"
QUEUE = "earningsnerd-background"
INSTANCE = "earningsnerd-db"
REGION = "us-west1"
JOBS = ("pregenerate", "filing-scan", "filing-digest", "backfill-facts",
        "earnings-calendar-refresh", "earnings-day-alerts", "notable-filings", "retention-purge")
MAX_PAGES = 5
MAX_RESPONSE = 8 * 1024 * 1024
MAX_ERROR_BODY = 8 * 1024
MAX_ERROR_MESSAGE = 240
MAX_ERROR_FIELD = 64  # error.status and ErrorInfo reason/domain (Google bounds reason to 63 characters)
FRESHNESS_FLOOR_SECONDS = 300  # metric points appear up to 180 s after sampling; flag a window ending nearer than this
QUEUE_NOTE = "Cloud Tasks points become visible up to 180 s after sampling; a window ending within that lag under-reports the tail."
COUNTS_BASIS = "retained items only; a partial or unavailable state makes these counts a floor"
# error.message is the one free-text field the receipt keeps, and it can name a URL, an email address or IAM
# principal, a host or an IP address; each is replaced by a placeholder before the message is cut. A URL (any
# scheme, principal:// included) and an email address or principal (any "@", or its encoding "%40") are withheld
# as the whole whitespace-delimited token. A dotted name is a host when its last label is letters (any script) or
# an IDN "xn--" label, so the rule fails closed on a suffix it does not know; the one exemption is an IAM
# permission name of three ASCII letter labels ending in a PERMISSION_VERBS verb (monitoring.timeSeries.list),
# which names no address. Four numeric labels are an IPv4 address.
_URL = re.compile(r"(?<!\S)\S*://\S*")
_EMAIL = re.compile(r"(?<!\S)\S*(?:@|%40)\S*")
_DOTTED = re.compile(r"(?<![\w-])[\w-]+(?:\.[\w-]+)+")
_HOST_LABEL = re.compile(r"[^\W\d_]{2,63}|xn--[\w-]{1,59}", re.IGNORECASE)
_IPV6 = re.compile(r"(?<![0-9A-Za-z:])(?:(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}|"
                   r"(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4})*)?::(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4})*)?)"
                   r"(?![0-9A-Za-z:])")
PERMISSION_VERBS = ("get", "list", "use")  # the receipt's reads are get/list calls; Service Usage names .use


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

    Keeps only error.status, error.code, the first ErrorInfo detail's reason/domain (each at most
    MAX_ERROR_FIELD characters) and at most MAX_ERROR_MESSAGE characters of error.message after
    redact_addresses(), reading at most MAX_ERROR_BODY bytes. A diagnostic must never abort the receipt:
    whatever the body does, this returns a dict and request() still records its `http_NNN` error.
    """
    try:
        return _parse_error_envelope(exc)
    except Exception:  # any failure while reading or parsing the body is itself the recorded reason
        return {"body": "non_json_or_unreadable"}


def _parse_error_envelope(exc):
    raw = exc.read(MAX_ERROR_BODY)
    try:
        envelope = json.loads(raw)
    except ValueError:
        # A valid envelope longer than the cap is cut mid-document and cannot parse either; say so.
        return {"body": "truncated_or_non_json" if len(raw) >= MAX_ERROR_BODY else "non_json_or_unreadable"}
    error = envelope.get("error") if isinstance(envelope, dict) else None
    if not isinstance(error, dict):
        return {}  # JSON, but not a Google API error envelope: nothing recognised to record.
    detail = {}
    if isinstance(error.get("status"), str):
        detail["status"] = error["status"][:MAX_ERROR_FIELD]
    if isinstance(error.get("code"), int):
        detail["code"] = error["code"]
    details = error.get("details") if isinstance(error.get("details"), list) else []
    for info in details:
        if isinstance(info, dict) and isinstance(info.get("@type"), str) and info["@type"].endswith("ErrorInfo"):
            detail.update({key: info[key][:MAX_ERROR_FIELD] for key in ("reason", "domain")
                           if isinstance(info.get(key), str)})
            break
    if isinstance(error.get("message"), str):
        # Redact, then cut: a cut first could leave part of an address that no longer matches its pattern.
        message = redact_addresses(error["message"])
        detail["message"] = message[:MAX_ERROR_MESSAGE]
        if len(message) > MAX_ERROR_MESSAGE:
            detail["message_truncated"] = True
    return detail


def _dotted(match):
    labels = match.group().split(".")
    if len(labels) == 4 and all(label.isdigit() and len(label) <= 3 for label in labels):
        return "<host>"  # an IPv4 address
    if not _HOST_LABEL.fullmatch(labels[-1]):
        return match.group()  # a version, a decimal or a field path: its last label cannot end a host name
    if len(labels) == 3 and labels[2] in PERMISSION_VERBS and all(label.isascii() and label.isalpha() for label in labels):
        return match.group()  # an IAM permission name
    return "<host>"


def redact_addresses(text):
    """Replace every URL, email address or principal, host name and IP address in `text` with a placeholder."""
    text = _URL.sub("<url>", text)
    text = _EMAIL.sub("<email>", text)
    text = _DOTTED.sub(_dotted, text)
    return _IPV6.sub("<host>", text)


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
        ("database_id", "region", "location", "service_name", "revision_name", "configuration_name", "queue_id"))}
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
                              ("service_name", "revision_name", "job_name", "location"))
    # Classify locally without retaining the message, payload, URL or request/user identity.
    raw = json.dumps({key: record.get(key) for key in ("textPayload", "jsonPayload")}).lower()
    result["pool_timeout_signature"] = "queuepool limit" in raw or "connection pool exhausted" in raw
    return result


def project_items(channel, projector):
    """Project every item, or mark the channel unavailable: an unobserved API shape is recorded, never raised."""
    try:
        channel["items"] = [projector(item) for item in channel["items"]]
    except Exception:  # a shape surprise in one channel must never abort the receipt
        channel.update({"state": "unavailable", "error": "projection_error", "items": []})
    return channel


def rescope(channel, in_scope):
    """Keep only items the committed scope admits; count the rest, never keep them."""
    kept = []
    channel["outside_scope_count"] = 0
    for item in channel["items"]:
        if in_scope(item):
            kept.append(item)
        else:
            channel["outside_scope_count"] += 1
    channel["items"] = kept
    return channel


def error_log_channel(api, project, region, start, end, resource_filter, in_scope):
    """Error-level entries for one resource scope: counts and log_entry() projections, never text."""
    logs = api.pages("https://logging.googleapis.com/v2/entries:list", {
        "resourceNames": [f"projects/{project}"], "pageSize": 100,
        "orderBy": "timestamp asc", "filter": (
            f'timestamp>="{start}" AND timestamp<"{end}" AND '
            f'resource.labels.location="{region}" AND ({resource_filter}) AND '
            '(severity>=ERROR OR "QueuePool limit" OR "connection pool exhausted")')}, "entries", post=True)
    try:
        raw = logs["items"]
        kept = [item for item in raw
                if item.get("resource", {}).get("labels", {}).get("location") == region
                and in_scope(item.get("resource", {}).get("type"), item.get("resource", {}).get("labels", {}))]
        logs["outside_scope_count"] = len(raw) - len(kept)
        logs["items"] = [log_entry(item) for item in kept]
    except Exception:  # a shape surprise in one channel must never abort the receipt
        logs.update({"state": "unavailable", "error": "projection_error", "items": [], "outside_scope_count": 0})
    logs["counts_by_severity"] = {}
    logs["pool_timeout_signature_count"] = 0
    for entry in logs["items"]:
        severity = entry.get("severity")
        key = severity if isinstance(severity, str) and re.fullmatch(r"[A-Z]{1,9}", severity) else "UNRECOGNISED"
        logs["counts_by_severity"][key] = logs["counts_by_severity"].get(key, 0) + 1
        logs["pool_timeout_signature_count"] += int(entry["pool_timeout_signature"])
    logs["counts_basis"] = COUNTS_BASIS
    return logs


def collect(api, project, region, start, end):
    first, last = window(start, end)
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]|[0-9]+", project):
        raise ValueError("Invalid project identifier")
    if region != REGION:
        raise ValueError("Only the production region is supported")
    observed = datetime.now(timezone.utc)
    end_age = int((observed - last).total_seconds())
    result = {"schema_version": 1, "observed_at": observed.isoformat(),
              "project": project, "region": region,
              "window": {"start": start, "end": end, "end_age_seconds": end_age},
              "limits": {"max_pages_per_query": MAX_PAGES, "max_response_bytes": MAX_RESPONSE,
                         "max_error_body_bytes": MAX_ERROR_BODY, "max_error_message_chars": MAX_ERROR_MESSAGE},
              "interpretation": "Samples are not instantaneous peaks. Empty/partial/unavailable data cannot prove headroom. Execution success is not a business outcome. Current SQL snapshots are not historical samples. Metric points can appear up to 180 s after sampling, so a window ending within that lag under-reports its tail."}
    if end_age < FRESHNESS_FLOOR_SECONDS:
        result["window"]["freshness"] = "tail_within_visibility_lag"
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
            try:
                if not re.fullmatch(r"projects/[^/]+/locations/" + region + r"/jobs/" + job + r"/executions/[^/]+",
                                    record.get("name", "")):
                    runs["outside_scope_count"] += 1
                    continue
                begins = timestamp(record.get("startTime") or record["createTime"])
                ends = timestamp(record["completionTime"]) if record.get("completionTime") else None
                if begins < last and (ends is None or ends >= first):
                    item = execution(record)
                    item["interval_start_basis"] = "startTime" if record.get("startTime") else "createTime; actual start unknown"
                    runs["items"].append(item)
            except (KeyError, ValueError, TypeError, AttributeError):
                # A record-level shape surprise (a non-dict item, a non-string name or timestamp) counts here
                # instead of aborting the receipt, like a shape surprise in a Monitoring or Logging channel.
                runs["unplaced_count"] += 1
        # Complete pagination is not proof of lifetime completeness or known execution intervals.
        runs["coverage"] = "retained API resources only; expired/deleted history may be absent"
        result["executions"][job] = runs
    revision_scope = 'resource.type="cloud_run_revision" AND resource.labels.service_name="{}" AND resource.labels.location="{}"'
    # The queue is filtered server-side by type and location only and re-scoped locally, because the
    # documented queue_id label may carry the short id or the full projects/.../queues/<id> path.
    queue_scope = f'resource.type="cloud_tasks_queue" AND resource.labels.location="{region}"'
    queue_ids = {QUEUE, f"projects/{project}/locations/{region}/queues/{QUEUE}"}
    def queue_in_scope(item):
        labels = item["resource"]["labels"]
        return labels.get("queue_id") in queue_ids and labels.get("location") == region
    # name, metric type, server-side scope, local re-scope predicate (None: none), note (None: none).
    # Cloud Tasks publishes attempts by canonical response_code only (no class label); depth is a gauge.
    queries = (
        ("database_connections", 'cloudsql.googleapis.com/database/postgresql/num_backends',
         f'resource.type="cloudsql_database" AND resource.labels.database_id="{project}:{INSTANCE}"', None, None),
        ("request_count", 'run.googleapis.com/request_count', revision_scope.format(SERVICE, region), None, None),
        ("request_latencies", 'run.googleapis.com/request_latencies', revision_scope.format(SERVICE, region), None, None),
        ("worker_request_count", 'run.googleapis.com/request_count', revision_scope.format(WORKER, region), None, None),
        ("worker_request_latencies", 'run.googleapis.com/request_latencies', revision_scope.format(WORKER, region), None, None),
        ("queue_depth", 'cloudtasks.googleapis.com/queue/depth', queue_scope, queue_in_scope, QUEUE_NOTE),
        ("queue_task_attempts", 'cloudtasks.googleapis.com/queue/task_attempt_count', queue_scope, queue_in_scope, QUEUE_NOTE),
    )
    for name, kind, scope, in_scope, note in queries:
        data = api.pages(f"https://monitoring.googleapis.com/v3/projects/{project}/timeSeries", {
            "filter": f'metric.type="{kind}" AND {scope}', "interval.startTime": start,
            "interval.endTime": end, "view": "FULL", "pageSize": 1000}, "timeSeries")
        project_items(data, metric)
        if in_scope is not None:
            rescope(data, in_scope)
        data["aggregation"] = "none; original series and sample intervals retained"
        if note is not None:
            data["note"] = note
        result[name] = data
    job_filter = " OR ".join(f'resource.labels.job_name="earningsnerd-{name}"' for name in JOBS)
    job_names = {"earningsnerd-" + name for name in JOBS}
    result["error_logs"] = error_log_channel(
        api, project, region, start, end,
        f'(resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICE}") OR '
        f'(resource.type="cloud_run_job" AND ({job_filter}))',
        lambda kind, labels: (kind == "cloud_run_revision" and labels.get("service_name") == SERVICE
                              or kind == "cloud_run_job" and labels.get("job_name") in job_names))
    result["worker_error_logs"] = error_log_channel(
        api, project, region, start, end,
        f'resource.type="cloud_run_revision" AND resource.labels.service_name="{WORKER}"',
        lambda kind, labels: kind == "cloud_run_revision" and labels.get("service_name") == WORKER)
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
