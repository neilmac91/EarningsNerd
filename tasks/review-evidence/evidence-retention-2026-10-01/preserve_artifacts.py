"""Preserve the GitHub Actions artifacts listed in manifest.json and verify each original ZIP.

Item A of the founder-delegated decision (PR #1029 comment 5925688598). Run this on a
founder-controlled machine with an authenticated `gh` CLI that can read neilmac91/EarningsNerd:

    python3 preserve_artifacts.py /path/to/non-icloud/evidence-dir

What it does:
- downloads every artifact as its ORIGINAL zip (`gh api repos/.../actions/artifacts/<id>/zip`),
  earliest expiry first;
- checks each zip's SHA-256 against the Actions digest recorded in manifest.json;
- skips a zip already present with the matching hash, so re-running only fills gaps;
- copies manifest.json next to the zips and writes verification.json with one row per artifact.

It refuses destinations under iCloud-synced folders (~/Library/Mobile Documents, ~/Desktop,
~/Documents), because the decision requires a materialized non-iCloud copy. It deletes nothing,
needs no model calls, and exits non-zero if any artifact is missing, expired or mismatched.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYNCED = [Path.home() / "Library" / "Mobile Documents", Path.home() / "Desktop", Path.home() / "Documents"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    dest = Path(sys.argv[1]).expanduser().resolve()
    if any(dest == root or root in dest.parents for root in SYNCED) or "icloud" in str(dest).lower():
        print(f"Refusing {dest}: choose a folder outside iCloud-synced locations.")
        return 2
    manifest = json.loads((HERE / "manifest.json").read_text())
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "manifest.json", dest / "manifest.json")
    rows, failures = [], 0
    for item in manifest["artifacts"]:
        target = dest / f"{item['artifact_name']}-{item['artifact_id']}.zip"
        status = "present"
        if not (target.exists() and sha256(target) == item["sha256"]):
            partial = target.with_suffix(".zip.part")
            with partial.open("wb") as handle:
                result = subprocess.run(
                    ["gh", "api", f"repos/{manifest['repo']}/actions/artifacts/{item['artifact_id']}/zip"],
                    stdout=handle, stderr=subprocess.PIPE, check=False,
                )
            if result.returncode != 0:
                # Keep the partial download (never delete): it stays as *.zip.part for inspection.
                status = "download_failed: " + result.stderr.decode(errors="replace").strip()[:200]
            else:
                partial.replace(target)
                status = "downloaded"
        actual = sha256(target) if target.exists() else None
        ok = actual == item["sha256"]
        failures += not ok
        rows.append({"artifact_id": item["artifact_id"], "name": item["artifact_name"],
                     "run_id": item["run_id"], "expires_at": item["expires_at"],
                     "expected_sha256": item["sha256"], "actual_sha256": actual,
                     "bytes": target.stat().st_size if target.exists() else None,
                     "status": status, "verified": ok})
        print(f"{'OK ' if ok else 'BAD'} {item['expires_at']} {target.name} {status}")
    (dest / "verification.json").write_text(json.dumps(
        {"manifest_generated_at": manifest["generated_at"], "destination": str(dest),
         "verified": len(rows) - failures, "failed": failures, "rows": rows}, indent=1))
    print(f"{len(rows) - failures}/{len(rows)} verified; details in {dest / 'verification.json'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
