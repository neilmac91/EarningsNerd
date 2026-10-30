"""Pure, closed projections for summary/SEC activation configuration; no I/O.

Absent settings remain unknown: the inspected image may predate the capability.
These projections never establish delivery, recovery, throughput or activation readiness.
"""
import re
from urllib.parse import urlsplit

BOOLEAN_FIELDS = (
    "SUMMARY_DURABLE_GENERATION_ENABLED", "SUMMARY_NEW_JOBS_PAUSED",
    "SEC_DISTRIBUTED_LIMIT_ENABLED", "DURABLE_TASKS_ENABLED", "TASKS_WORKER_PROCESS",
)
INTEGER_FIELDS = {
    "SUMMARY_JOB_FAILED_RETRY_SECONDS": (15, 3600),
    "SUMMARY_JOB_MAX_PENDING_PER_ACCOUNT": (1, 20),
    "SUMMARY_JOB_MAX_ATTEMPTS": (1, 8),
    "SUMMARY_JOB_LEASE_SECONDS": (30, 300),
    "SUMMARY_JOB_RECOVERY_SECONDS": (60, 1800),
    "SUMMARY_JOB_MAX_AGE_SECONDS": (300, 86400),
    "SUMMARY_PREWARM_MAX_PER_DAY": (0, 200),
    "SUMMARY_PREWARM_MAX_PER_SCAN": (0, 20),
}
NUMBER_FIELDS = {"SEC_DISTRIBUTED_WAIT_SECONDS": (0, 30), "TASKS_WORK_TIMEOUT_SECONDS": (0, 480)}
CONFIG_FIELDS = (*BOOLEAN_FIELDS, *INTEGER_FIELDS, *NUMBER_FIELDS)


def number(value, minimum, maximum, *, integer=False, positive=False):
    """Accept only a short decimal or actual JSON number; never bool/nonfinite."""
    if type(value) not in (int, float, str):
        return None
    if isinstance(value, str) and not re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,6})?", value):
        return None
    try:
        parsed = float(value)
    except (OverflowError, ValueError):
        return None
    if not minimum <= parsed <= maximum or (positive and parsed == 0) or (integer and not parsed.is_integer()):
        return None
    return int(parsed) if integer else parsed


def _entry(entries, name):
    matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("name") == name]
    if not matches:
        return None, "not_set_image_default_unverified"
    if len(matches) != 1:
        return None, "duplicate_unresolved"
    entry = matches[0]
    if "valueFrom" in entry or "valueSource" in entry:
        return None, "secret_ref_unresolved"
    if not isinstance(entry.get("value"), str):
        return None, "invalid_withheld"
    return entry["value"], "literal"


def runtime_configuration(entries):
    if not isinstance(entries, list):
        return {"state": "unreadable_response"}
    fields = {}
    for name in CONFIG_FIELDS:
        raw, state = _entry(entries, name)
        result = {"state": state}
        if state == "literal":
            if name in BOOLEAN_FIELDS:
                normalized = raw.lower()
                value = {"true": True, "false": False, "1": True, "0": False,
                         "on": True, "off": False, "yes": True, "no": False}.get(normalized)
            else:
                low, high = (INTEGER_FIELDS | NUMBER_FIELDS)[name]
                value = number(raw, low, high, integer=name in INTEGER_FIELDS, positive=name in NUMBER_FIELDS)
            result = {"state": "literal", "value": value} if value is not None else {"state": "invalid_withheld"}
        fields[name] = result
    token, token_state = _entry(entries, "INTERNAL_JOB_TOKEN")
    return {
        "fields": fields,
        "internal_job_token": {"state": token_state, "nonempty_literal": bool(token) if token_state == "literal" else None},
        "limit": "Configured literals only; absent image defaults, authentication and runtime outcomes remain unverified.",
    }


def cron(value):
    """Bounded numeric five-field cron; unsupported syntax is withheld, never guessed."""
    if not isinstance(value, str) or len(value) > 96:
        return None
    fields = value.split()
    if len(fields) != 5:
        return None
    for field, (low, high) in zip(fields, ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))):
        for part in field.split(","):
            match = re.fullmatch(r"(\*|[0-9]{1,2}(?:-[0-9]{1,2})?)(?:/([0-9]{1,2}))?", part)
            if not match:
                return None
            base, step = match.groups()
            if step is not None and not 1 <= int(step) <= high + 1:
                return None
            if base != "*":
                bounds = [int(item) for item in base.split("-")]
                if not all(low <= item <= high for item in bounds) or bounds[-1] < bounds[0]:
                    return None
    return " ".join(fields)


def duration(value):
    if not isinstance(value, str) or not value.endswith("s"):
        return None
    return number(value[:-1], 0, 31536000)


def _https_origin(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ("", "/") or parsed.port not in (None, 443)):
            return None
    except ValueError:
        return None
    return f"https://{parsed.netloc}".rstrip("/")


def scheduler_configuration(data, name, service_url, region):
    if not isinstance(data, dict) or data.get("state") not in ("ENABLED", "PAUSED", "DISABLED", "UPDATE_FAILED"):
        return {"state": "unreadable_response"}
    target = data.get("httpTarget")
    target = target if isinstance(target, dict) else {}
    if name == "filing-scan-hourly":
        expected = {
            f"https://{region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/earnings-nerd/jobs/earningsnerd-filing-scan:run",
            f"https://run.googleapis.com/v2/projects/earnings-nerd/locations/{region}/jobs/earningsnerd-filing-scan:run",
        }
    else:
        expected = {"https://api.earningsnerd.io/internal/jobs/summary-recovery"}
        origin = _https_origin(service_url)
        if origin:
            expected.add(origin + "/internal/jobs/summary-recovery")
    headers = target.get("headers")
    headers = headers if isinstance(headers, dict) else {}
    retry = data.get("retryConfig")
    retry = retry if isinstance(retry, dict) else {}
    return {
        "state": "observed_configuration", "scheduler_state": data["state"],
        "schedule": cron(data.get("schedule")),
        "time_zone": data.get("timeZone") if data.get("timeZone") in ("Etc/UTC", "UTC", "America/New_York", "Europe/London") else None,
        "post_target_matches": target.get("httpMethod") == "POST" and isinstance(target.get("uri"), str) and target["uri"] in expected,
        "oidc_present": isinstance(target.get("oidcToken"), dict),
        "oauth_present": isinstance(target.get("oauthToken"), dict),
        "internal_token_header_present": any(isinstance(key, str) and key.lower() == "x-internal-token" for key in headers),
        "attempt_deadline_seconds": duration(data.get("attemptDeadline")),
        "retry_count": number(retry.get("retryCount"), 0, 100, integer=True),
        "max_retry_duration_seconds": duration(retry.get("maxRetryDuration")),
        "min_backoff_seconds": duration(retry.get("minBackoffDuration")),
        "max_backoff_seconds": duration(retry.get("maxBackoffDuration")),
        "max_doublings": number(retry.get("maxDoublings"), 0, 100, integer=True),
        "limit": "Named resource only; configuration does not prove authentication, execution, non-overlap or recovery success. Other caller names are not inspected.",
    }


def queue_configuration(data):
    if not isinstance(data, dict) or data.get("state") not in ("RUNNING", "PAUSED", "DISABLED"):
        return {"state": "unreadable_response"}
    rate = data.get("rateLimits")
    rate = rate if isinstance(rate, dict) else {}
    retry = data.get("retryConfig")
    retry = retry if isinstance(retry, dict) else {}
    return {
        "state": "observed_configuration", "queue_state": data["state"],
        "max_concurrent_dispatches": number(rate.get("maxConcurrentDispatches"), 1, 100000, integer=True),
        "max_dispatches_per_second": number(rate.get("maxDispatchesPerSecond"), 0, 100000, positive=True),
        "max_burst_size": number(rate.get("maxBurstSize"), 1, 100000, integer=True),
        "max_attempts": number(retry.get("maxAttempts"), -1, 100000, integer=True),
        "max_retry_duration_seconds": duration(retry.get("maxRetryDuration")),
        "min_backoff_seconds": duration(retry.get("minBackoff")),
        "max_backoff_seconds": duration(retry.get("maxBackoff")),
        "max_doublings": number(retry.get("maxDoublings"), 0, 100, integer=True),
        "limit": "Configuration only; queue age, mail latency, SQL headroom and successful delivery require separate capacity evidence.",
    }
