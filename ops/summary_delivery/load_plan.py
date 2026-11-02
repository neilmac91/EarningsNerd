"""Read one plan artifact from a successful first-attempt Ops dispatch on main.

No archive is extracted and no artifact content is executed. Only the one bounded
JSON member is copied to the fixed private output after run/artifact provenance,
manifest hash and nonce checks. Apply requires this SHA; cleanup can use the old
plan after main advances. Provider stderr and malformed data stay withheld.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path

REPOSITORY = "neilmac91/EarningsNerd"
OUTPUT = Path("summary-approved-plan.json")
LIMIT = 32768
ARTIFACT_LIMIT = 1048576
KINDS = {
    "summary-delivery-apply": ("summary-delivery-plan", "summary-delivery-plan.json"),
    "summary-delivery-cleanup-apply": ("summary-delivery-plan", "summary-delivery-plan.json"),
    "summary-recovery-caller-apply": ("summary-recovery-caller-plan", "summary-recovery-plan.json"),
}


class Refused(RuntimeError):
    """Closed refusal; details and raw provider output do not leave this module."""


def gh(path: str, *, binary: bool = False):
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(["gh", "api", path], stdout=output,
                                stderr=subprocess.DEVNULL, timeout=40, check=False)
        output.seek(0)
        data = output.read(ARTIFACT_LIMIT + 1)
    if result.returncode or len(data) > ARTIFACT_LIMIT:
        raise Refused("artifact_read_unverified")
    return data if binary else json.loads(data)


def load(env: dict[str, str]) -> bytes:
    operation = env.get("OP", "")
    run_id = env.get("SUMMARY_PLAN_RUN", "")
    expected = env.get("SUMMARY_PLAN_SHA256", "")
    nonce = env.get("SUMMARY_APPROVAL_NONCE", "")
    source = env.get("GITHUB_SHA", "")
    if (operation not in KINDS or env.get("GITHUB_REPOSITORY") != REPOSITORY
            or env.get("GITHUB_REF") != "refs/heads/main"
            or not re.fullmatch(r"[1-9][0-9]{0,19}", run_id)
            or not re.fullmatch(r"[a-f0-9]{64}", expected)
            or not re.fullmatch(r"[a-f0-9]{32}", nonce)
            or not re.fullmatch(r"[a-f0-9]{40}", source)):
        raise Refused("plan_input_refused")
    prefix, filename = KINDS[operation]
    run = gh(f"repos/{REPOSITORY}/actions/runs/{run_id}")
    if (type(run.get("id")) is not int or str(run["id"]) != run_id
            or run.get("repository", {}).get("full_name") != REPOSITORY
            or run.get("head_repository", {}).get("full_name") != REPOSITORY
            or run.get("path") != ".github/workflows/ops.yml"
            or run.get("event") != "workflow_dispatch" or run.get("head_branch") != "main"
            or not re.fullmatch(r"[a-f0-9]{40}", run.get("head_sha", ""))
            or (operation != "summary-delivery-cleanup-apply" and run["head_sha"] != source)
            or run.get("status") != "completed"
            or run.get("conclusion") != "success" or type(run.get("run_attempt")) is not int
            or run["run_attempt"] != 1):
        raise Refused("plan_run_unverified")
    listing = gh(f"repos/{REPOSITORY}/actions/runs/{run_id}/artifacts?per_page=100")
    artifacts = listing.get("artifacts")
    if (not isinstance(artifacts, list) or type(listing.get("total_count")) is not int
            or listing["total_count"] != len(artifacts) or len(artifacts) > 100):
        raise Refused("artifact_list_unverified")
    matches = [a for a in artifacts if a.get("name") == f"{prefix}-{run_id}"]
    if len(matches) != 1:
        raise Refused("artifact_identity_unverified")
    artifact = matches[0]
    if (artifact.get("expired") is not False or type(artifact.get("id")) is not int
            or artifact["id"] <= 0 or type(artifact.get("size_in_bytes")) is not int
            or not 0 < artifact["size_in_bytes"] <= ARTIFACT_LIMIT):
        raise Refused("artifact_identity_unverified")
    data = gh(f"repos/{REPOSITORY}/actions/artifacts/{artifact['id']}/zip", binary=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) != 1:
            raise Refused("artifact_members_refused")
        entry = entries[0]
        if (entry.filename != filename or not 0 < entry.file_size <= LIMIT
                or entry.flag_bits & 1 or entry.is_dir()
                or stat.S_ISLNK(entry.external_attr >> 16)):
            raise Refused("artifact_member_refused")
        with archive.open(entry) as member:
            content = member.read(LIMIT + 1)
    if len(content) > LIMIT:
        raise Refused("plan_size_refused")
    document = json.loads(content)
    if not isinstance(document, dict) or set(document) != {"manifest", "sha256"}:
        raise Refused("plan_shape_refused")
    manifest = document["manifest"]
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if (not isinstance(manifest, dict) or not isinstance(document["sha256"], str)
            or not isinstance(manifest.get("nonce"), str)
            or not hmac.compare_digest(hashlib.sha256(canonical).hexdigest(), expected)
            or not hmac.compare_digest(document["sha256"], expected)
            or not hmac.compare_digest(manifest["nonce"], nonce)):
        raise Refused("plan_integrity_refused")
    return content


def main() -> int:
    try:
        content = load(dict(os.environ))
        descriptor = os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
        print("Summary plan provenance and integrity verified")
        return 0
    except Exception:  # noqa: BLE001 — final public boundary must never format provider data
        print("Summary plan UNVERIFIED; no apply may proceed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
