"""Fixed, read-only summary recovery snapshot; no application imports or arbitrary inputs.

Connection identity comes from the Ops proxy's existing libpq PG* environment. The only SQL
is snapshot.sql beside this file. Database output and errors stay private until a closed-shape
validator accepts the snapshot; the JSON artifact and stdout contain only that normalized result.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

SQL_FILE = Path(__file__).with_name("snapshot.sql")
OUTPUT_FILE = "summary-recovery-receipt.json"
MAX_OUTPUT_BYTES = 32 * 1024
MAX_ERROR_BYTES = 8192
PROCESS_TIMEOUT_SECONDS = 25
MAX_INTERVAL_SECONDS = 30 * 24 * 60 * 60
FILINGS = (45003, 45004)
STATES = {"queued", "running", "retry_wait", "complete", "partial", "failed", "unknown"}
STAGES = {"queued", "initializing", "fetching", "parsing", "analyzing", "summarizing",
          "saving", "completed", "partial", "error", "unknown"}
CHARGES = {"unreserved", "reserved", "charged", "settled", "refunded", "unknown"}
TIMES = {"created", "updated", "lease_until", "next_attempt", "last_dispatch"}
COUNTERS = {"retained", "queued", "running", "retry_wait", "unacknowledged",
            "acknowledged_due_over_300s", "expired_leases", "running_without_lease_deadline",
            "older_than_3600s"}
LIMITS = {
    "filing_ids": list(FILINGS),
    "active_sample_limit": 1000,
    "active_scope": "Current queued/running/retry_wait jobs only; oldest 1000, with a 1001st-row truncation probe.",
    "time_bounds_seconds": MAX_INTERVAL_SECONDS,
    "reference_thresholds_seconds": {"stale_dispatch": 300, "job_horizon": 3600},
    "threshold_scope": "Reference thresholds only, not a read of deployed Settings or scheduler execution.",
    "receipt_scope": "Referenced reservation and result integrity only; no user_usage counters or provider billing reconciliation.",
    "outcome_scope": "One database snapshot; no successful generation, queue delivery, recovery caller or physical SEC rate is established.",
}


class InvalidSnapshot(ValueError):
    """Only its closed class may cross the output boundary."""


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise InvalidSnapshot()


def _enum(value, allowed):
    if type(value) is not str or value not in allowed:
        raise InvalidSnapshot()
    return value


def _integer(value, minimum=0, maximum=1000, *, nullable=False):
    if value is None and nullable:
        return None
    if type(value) is not int or not minimum <= value <= maximum:
        raise InvalidSnapshot()
    return value


def _boolean(value):
    if type(value) is not bool:
        raise InvalidSnapshot()
    return value


def _times(value, names):
    _keys(value, names)
    result = {}
    for name in sorted(names):
        item = value[name]
        _keys(item, {"state", "seconds_from_snapshot"})
        state = _enum(item["state"], {"absent", "nonfinite", "past_bound", "future_bound", "bounded"})
        seconds = item["seconds_from_snapshot"]
        if state == "bounded":
            seconds = _integer(seconds, -MAX_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS)
        elif seconds is not None:
            raise InvalidSnapshot()
        result[name] = {"state": state, "seconds_from_snapshot": seconds}
    return result


def _filing(row, expected_id):
    _keys(row, {"filing_id", "identity", "job_present", "generation", "attempts", "system_funded",
                "status", "stage", "charge_state", "error_recorded", "active_owner", "lease_state", "result_reference",
                "reservation_reference", "charged_month_shape", "times"})
    if type(row["filing_id"]) is not int or row["filing_id"] != expected_id:
        raise InvalidSnapshot()
    result = {
        "filing_id": expected_id,
        "identity": _enum(row["identity"], {"matched", "missing_filing", "identity_mismatch"}),
        "job_present": _boolean(row["job_present"]),
        "generation": _integer(row["generation"], 1, 2**31 - 1, nullable=True),
        "attempts": _integer(row["attempts"], 0, 2**31 - 1, nullable=True),
        "system_funded": None if row["system_funded"] is None else _boolean(row["system_funded"]),
        "status": _enum(row["status"], STATES),
        "stage": _enum(row["stage"], STAGES),
        "charge_state": _enum(row["charge_state"], CHARGES),
        "error_recorded": _boolean(row["error_recorded"]),
        "active_owner": _boolean(row["active_owner"]),
        "lease_state": _enum(row["lease_state"], {"absent", "inconsistent", "nonfinite", "expired", "live"}),
        "result_reference": _enum(row["result_reference"], {"absent", "missing", "wrong_filing", "matching_filing"}),
        "reservation_reference": _enum(row["reservation_reference"], {
            "absent", "missing", "wrong_owner_or_kind", "invalid_month", "nonfinite", "expired", "live"}),
        "charged_month_shape": _enum(row["charged_month_shape"], {"absent", "valid_shape", "invalid_shape"}),
        "times": _times(row["times"], TIMES),
    }
    if result["job_present"]:
        if result["identity"] != "matched" or any(result[key] is None for key in ("generation", "attempts", "system_funded")):
            raise InvalidSnapshot()
    elif (any(result[key] is not None for key in ("generation", "attempts", "system_funded"))
          or any(result[key] != "unknown" for key in ("status", "stage", "charge_state"))
          or any(result[key] != "absent" for key in ("lease_state", "result_reference", "reservation_reference", "charged_month_shape"))
          or result["error_recorded"] or result["active_owner"]
          or any(item["state"] != "absent" for item in result["times"].values())):
        raise InvalidSnapshot()
    if result["active_owner"] != (result["status"] == "running" and result["lease_state"] == "live"):
        raise InvalidSnapshot()
    # These are observations for operator review, not automatic reconciliation instructions.
    findings = []
    if result["job_present"]:
        if result["status"] in {"complete", "partial"} and result["result_reference"] != "matching_filing":
            findings.append("terminal_result_reference_unresolved")
        if result["charge_state"] == "reserved" and result["reservation_reference"] != "live":
            findings.append("reservation_not_live")
        if result["charge_state"] in {"charged", "settled"} and result["charged_month_shape"] != "valid_shape":
            findings.append("charge_month_unresolved")
        if result["charge_state"] in {"charged", "settled", "refunded"} and result["reservation_reference"] != "absent":
            findings.append("reservation_remains_after_charge_or_refund")
        if result["system_funded"] and (result["charge_state"] != "unreserved" or result["reservation_reference"] != "absent"):
            findings.append("system_job_usage_reference")
    result["observations"] = findings
    return result


def normalize_snapshot(raw):
    """Accept only the fixed SQL projection. Unknown fields cannot become an artifact leak."""
    _keys(raw, {"schema_version", "read_only", "isolation", "observed_at", "filings", "active_jobs", "sec_coordinator"})
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1 or raw["read_only"] != "on" or raw["isolation"] != "repeatable read":
        raise InvalidSnapshot()
    stamp = raw["observed_at"]
    if type(stamp) is not str or len(stamp) > 40:
        raise InvalidSnapshot()
    try:
        parsed = datetime.fromisoformat(stamp)
        if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
            raise InvalidSnapshot()
    except (ValueError, AttributeError):
        raise InvalidSnapshot() from None
    if type(raw["filings"]) is not list or len(raw["filings"]) != 2:
        raise InvalidSnapshot()
    filings = [_filing(row, expected) for row, expected in zip(raw["filings"], FILINGS)]
    active = raw["active_jobs"]
    _keys(active, COUNTERS | {"truncated", "oldest_age_seconds_capped"})
    counts = {key: _integer(active[key]) for key in sorted(COUNTERS)}
    counts["truncated"] = _boolean(active["truncated"])
    counts["oldest_age_seconds_capped"] = _integer(active["oldest_age_seconds_capped"], maximum=MAX_INTERVAL_SECONDS, nullable=True)
    if counts["queued"] + counts["running"] + counts["retry_wait"] != counts["retained"]:
        raise InvalidSnapshot()
    if any(counts[key] > counts["retained"] for key in COUNTERS - {"retained"}):
        raise InvalidSnapshot()
    if (counts["retained"] == 0) != (counts["oldest_age_seconds_capped"] is None):
        raise InvalidSnapshot()
    if counts["truncated"] and counts["retained"] != 1000:
        raise InvalidSnapshot()
    coordinator = raw["sec_coordinator"]
    _keys(coordinator, {"present", "times"})
    present = _boolean(coordinator["present"])
    coordinator = {"present": present, "times": _times(coordinator["times"], {"next_admission", "cooldown"} if present else set())}
    return {"state": "observed_snapshot", "schema_version": 1,
            "observed_at": parsed.astimezone(UTC).isoformat(), "read_only": True,
            "isolation": "repeatable read", "filings": filings, "active_jobs": counts,
            "sec_coordinator": coordinator, "limits": LIMITS}


def _unverified(reason):
    return {"state": "UNVERIFIED", "reason": reason, "limits": LIMITS}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidSnapshot()
        result[key] = value
    return result


def _reject_constant(_value):
    raise InvalidSnapshot()


def _error_class(stderr, returncode):
    # VERBOSITY=sqlstate emits codes, but never echo the surrounding stderr (including connect failures).
    classes = {"42501": "permission_denied", "42P01": "missing_schema", "42703": "schema_mismatch",
               "57014": "statement_timeout", "55P03": "lock_timeout", "25006": "read_only_violation"}
    codes = set(re.findall(rb"(?<![0-9A-Z])[0-9A-Z]{5}(?![0-9A-Z])", stderr))
    for code, label in classes.items():
        if code.encode("ascii") in codes:
            return label
    return "connection_error" if returncode == 2 else "database_read_failed"


def collect_snapshot():
    env = dict(os.environ)
    env["PGOPTIONS"] = (env.get("PGOPTIONS", "") +
                        " -c default_transaction_read_only=on -c statement_timeout=15s -c lock_timeout=2s")
    env["PGCONNECT_TIMEOUT"] = "5"
    env["LC_ALL"] = "C"
    command = ["psql", "--no-psqlrc", "--no-password", "--quiet", "--tuples-only", "--no-align",
               "--set=ON_ERROR_STOP=1", "--set=VERBOSITY=sqlstate", "--file", str(SQL_FILE)]
    try:
        # Bounded reads from private, auto-removed files; subprocess output never inherits console descriptors.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            completed = subprocess.run(command, env=env, stdout=output, stderr=errors,
                                       timeout=PROCESS_TIMEOUT_SECONDS, check=False)
            output.seek(0)
            raw = output.read(MAX_OUTPUT_BYTES + 1)
            errors.seek(0)
            error = errors.read(MAX_ERROR_BYTES)
        if completed.returncode:
            return _unverified(_error_class(error, completed.returncode))
        if len(raw) > MAX_OUTPUT_BYTES:
            return _unverified("output_limit")
        return normalize_snapshot(json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant))
    except subprocess.TimeoutExpired:
        return _unverified("process_timeout")
    except FileNotFoundError:
        return _unverified("client_unavailable")
    except (InvalidSnapshot, UnicodeError, ValueError, TypeError, OverflowError, RecursionError):
        return _unverified("unreadable_response")
    except OSError:
        return _unverified("local_read_failed")


def main():
    receipt = collect_snapshot() if len(sys.argv) == 1 else _unverified("unexpected_arguments")
    encoded = json.dumps(receipt, sort_keys=True, allow_nan=False) + "\n"
    if len(encoded.encode("utf-8")) > MAX_OUTPUT_BYTES:
        receipt = _unverified("output_limit")
        encoded = json.dumps(receipt, sort_keys=True) + "\n"
    try:
        descriptor = os.open(OUTPUT_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(encoded)
    except OSError:
        receipt = _unverified("receipt_write_failed")
        encoded = json.dumps(receipt, sort_keys=True) + "\n"
    print(encoded, end="")
    return 0 if receipt["state"] == "observed_snapshot" else 1


if __name__ == "__main__":
    raise SystemExit(main())
