# Evidence retention (item A, 2026-10-01)

This folder covers the retention of GitHub Actions artifacts, as decided in PR #1029 comment 5925688598:
- #942's complete cited evidence, including the r eval report `10933338099`, the original ZIPs, and failed or superseded runs;
- the raw Copilot artifacts that items F (#1021 qualification set) and G (#1036 run table) depend on.

Nothing has been regenerated. This folder holds only the manifest, which is privacy-reviewed: identifiers, sizes, expiry times and hashes, with no artifact content.

## Status

**Inventoried. Not yet preserved.**

The preservation needs a founder-controlled machine with an authenticated `gh` CLI. The Claude session cannot reach any founder-controlled durable storage.

## Deadline

The first artifact expires on **2026-10-06 at 11:18:15 UTC**. The 14-day CI eval reports expire in this order:

| Artifact | Expires (UTC) |
| --- | --- |
| `eval-report-35719785433` | 2026-10-06 11:18 |
| `…35831800595` | 2026-10-07 07:42 |
| `…35834524871` | 2026-10-07 08:09 |
| `…36272463033` (p control) | 2026-10-10 21:28 |
| `…36276521637` | 2026-10-10 22:41 |
| `…36276551360` | 2026-10-10 22:45 |
| `…36278111326` | 2026-10-10 23:11 |
| `…36324847604` (r, `10933338099`) | 2026-10-11 14:19 |

The 90-day `copilot-fidelity-*` artifacts expire between 2026-12-07 and 2026-12-30.

## Contents

- `manifest.json`: 27 distinct artifacts totalling 1,525,958,920 bytes, sorted by expiry. Each entry records the artifact id and name, run id, workflow, event, head SHA and branch, run conclusion, size, the Actions sha256 digest, created and expires times, and which set(s) cited it (`pr942`, `pr1021_qualification`, `pr1036_cited`).
- **Runs without artifacts:** #942 CI runs 34292517143 and 34287780530, both from 2026-09-08. The API lists nothing for them, which is consistent with their 14-day reports having aged out before this inventory. They are recorded rather than silently dropped.
- `preserve_artifacts.py`: downloads each original zip in expiry order to a destination you choose. For each zip it:
  - checks the SHA-256 against the manifest;
  - skips a zip that is already present and verified;
  - writes `verification.json`.

  It refuses iCloud-synced destinations and deletes nothing. It was tested with a stub `gh`: a hash mismatch is flagged with exit 1, an iCloud path is refused with exit 2, and a re-run skips already-verified zips.

## Founder action

```bash
# Extract the folder to a temp dir without touching your working tree or index:
git fetch origin claude/admiring-hopper-n0d93b
mkdir -p /tmp/er && git archive origin/claude/admiring-hopper-n0d93b tasks/review-evidence/evidence-retention-2026-10-01 | tar -x -C /tmp/er
python3 /tmp/er/tasks/review-evidence/evidence-retention-2026-10-01/preserve_artifacts.py /path/outside/icloud/earningsnerd-evidence
```

This needs about 1.6 GB free. Then:
1. Keep a second copy in the private storage you already use.
2. Post the final `N/27 verified` line from `verification.json` on PR #1029.

Do not publish the ZIPs or attach them to a public Release.
