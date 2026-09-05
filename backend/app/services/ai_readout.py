"""Bounded, stdlib-only weekly measurement handoff; never authorizes feature activation."""
from __future__ import annotations

import base64
import binascii
import json
import math
import re

EXPECTED = 24
JUDGE_MODEL = "claude-opus-4-8"
DIMENSIONS = ("faithfulness", "insight", "clarity", "specificity")
MAX_ENCODED_BYTES = 8192
_URL = re.compile(r"https://github\.com/neilmac91/EarningsNerd/actions/runs/[0-9]+(?:/artifacts/[0-9]+|#artifacts)?")
_COUNTS = ("expected", "completed", "scored", "errors", "missing", "negative_judgments", "deterministic_vetoes")


def unavailable_readout(reason: str = "Weekly judged readout unavailable") -> dict:
    return {
        "version": 1, "status": "unavailable", "reason": reason[:300],
        "source_sha": None, "cohort_sha256": None, "golden_set_sha256": None,
        "run_url": None, "artifact_url": None, "generator_model": None,
        "judge_model": JUDGE_MODEL, "judge_backend": "anthropic", "expected": EXPECTED,
        "completed": 0, "scored": 0, "errors": 0, "missing": EXPECTED,
        "negative_judgments": 0, "deterministic_vetoes": 0,
        "dimensions": dict.fromkeys(DIMENSIONS),
    }


def validate_readout(value: object) -> dict:
    """Reject malformed/contradictory external data; valid negative judgments stay measurements."""
    if not isinstance(value, dict) or set(value) != set(unavailable_readout()):
        raise ValueError("Unexpected weekly readout schema")
    if type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("Unknown weekly readout version")
    if value["status"] not in ("complete", "partial", "unavailable"):
        raise ValueError("Invalid weekly readout status")
    if not isinstance(value["reason"], str) or len(value["reason"]) > 300:
        raise ValueError("Invalid weekly readout reason")
    if value["judge_model"] != JUDGE_MODEL or value["judge_backend"] != "anthropic":
        raise ValueError("An authoritative strong judge is required")
    for key in _COUNTS:
        if type(value[key]) is not int or not 0 <= value[key] <= EXPECTED:
            raise ValueError("Invalid weekly readout count")
    if (value["expected"] != EXPECTED or value["scored"] + value["errors"] + value["missing"] != EXPECTED
            or not value["scored"] <= value["completed"] <= EXPECTED - value["missing"]
            or value["negative_judgments"] > value["scored"]
            or value["deterministic_vetoes"] > value["completed"]):
        raise ValueError("Inconsistent weekly readout denominators")
    expected_status = "complete" if value["scored"] == EXPECTED else "partial" if value["completed"] else "unavailable"
    if value["status"] != expected_status:
        raise ValueError("Incomplete measurement cannot claim completion")
    for key, size in (("source_sha", 40), ("cohort_sha256", 64), ("golden_set_sha256", 64)):
        item = value[key]
        if item is None and value["status"] == "unavailable":
            continue
        if not isinstance(item, str) or not re.fullmatch(r"[0-9a-f]{%d}" % size, item):
            raise ValueError("Invalid measurement provenance")
    for key in ("run_url", "artifact_url"):
        item = value[key]
        if item is not None and (not isinstance(item, str) or not _URL.fullmatch(item)):
            raise ValueError("Untrusted measurement link")
    model = value["generator_model"]
    if model is not None and (not isinstance(model, str) or not re.fullmatch(r"[\w.:-]{1,100}", model)):
        raise ValueError("Invalid generator identity")
    if value["status"] != "unavailable" and not model:
        raise ValueError("Missing generator identity")
    dims = value["dimensions"]
    if not isinstance(dims, dict) or set(dims) != set(DIMENSIONS):
        raise ValueError("Missing judge dimensions")
    for mean in dims.values():
        if value["scored"] == 0:
            if mean is not None:
                raise ValueError("Unscored dimensions must be unavailable")
            continue
        if type(mean) not in (int, float) or not math.isfinite(mean) or not 1 <= mean <= 5:
            raise ValueError("Invalid judge dimension mean")
    return value


def encode_readout(value: dict) -> str:
    encoded = base64.b64encode(json.dumps(validate_readout(value), allow_nan=False, separators=(",", ":")).encode()).decode("ascii")
    if len(encoded) > MAX_ENCODED_BYTES:
        raise ValueError("Weekly readout exceeds handoff limit")
    return encoded


def decode_readout(encoded: str | None) -> dict:
    """Fail visibly but keep the ordinary operational report available on bad/missing handoffs."""
    if not encoded:
        return unavailable_readout("Weekly judged readout handoff absent")
    try:
        if not isinstance(encoded, str) or len(encoded) > MAX_ENCODED_BYTES:
            raise ValueError("oversize")
        value = json.loads(base64.b64decode(encoded, validate=True))
        return validate_readout(value)
    except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError):
        return unavailable_readout("Weekly judged readout handoff invalid")
