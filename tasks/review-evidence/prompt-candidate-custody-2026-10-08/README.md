# Custody of the prompt-candidate archives (2026-10-08)

Codex's handover on #1029 (comment 5966195498) left one evidence task for the next continuation: "private preservation and independent custody/telemetry verification of all four archives" of the Copilot prompt-candidate measurement (#1074, handback 5965113700).

This folder covers both halves, following the item-A pattern in [`../evidence-retention-2026-10-01/`](../evidence-retention-2026-10-01/README.md):
- **Verification:** done here, independently.
- **Preservation:** a kit for the founder. A Claude session cannot reach founder-controlled storage, and the repository is public, so the archives themselves do not belong in it.

The measurement's evidence, pre-registration and review history are in [`../prompt-candidate-2026-10-02/`](../prompt-candidate-2026-10-02/README.md).

## Status

- **Verified: 4 of 4.** Fresh downloads equal the Actions digests and the session's scratch copies byte for byte. Every posted hash, run telemetry figure, cost and check outcome reproduces from the raw files (the DeepSeek balance readings excepted: no archive records them). The critic confirmed 33 of 35 handback claims. One per-run balance statement was wrong and is corrected; the balance readings themselves cannot be verified from any archive. See [verification.md](verification.md).
- **Not yet preserved.** The copy into founder-controlled storage needs a founder machine with an authenticated `gh` CLI.

## Deadline

The manifest lists twelve archives in two sets. Three eval reports from the close-out expire **before** the candidate's own eval report.

| Archive | Set | Expires (UTC) |
| --- | --- | --- |
| `eval-report-37048017303` (D29, #1056) | close-out | **2026-10-16 18:41** |
| `eval-report-37051282050` (D31, #1060) | close-out | **2026-10-16 19:10** |
| `eval-report-37061778841` (D33, #1065) | close-out | **2026-10-16 20:48** |
| `eval-report-37092291865` (row R(i)) | prompt candidate | **2026-10-17 03:20** |
| five `copilot-fidelity-*` (D28, D30, D32, D34, post-#1066 control) | close-out | 2026-12-31 |
| three `copilot-fidelity-*` (Q1, Q2, Q3) | prompt candidate | 2027-01-01 |

- **`prompt_candidate_2026_10_03`:** the four archives Codex named.
- **`close_out_2026_10_02_cited`:** the eight archives the 2026-10-02 close-out cites (ledger rows D28–D32 in `tasks/pr-disposition-2026-09-30.md`, D33–D34 in #1029 comment 5961781714, and the post-#1066 control in `run_validity_post1066.txt`). No manifest on main preserved them. They fall outside Codex's four-archive request and are listed so that one run before 2026-10-16 keeps every archive the close-out and the candidate cite. Each was checked against its Actions digest.

## Founder action

```bash
# Extract this folder without touching your working tree or index:
git fetch origin claude/admiring-hopper-n0d93b
mkdir -p /tmp/pc && git archive origin/claude/admiring-hopper-n0d93b tasks/review-evidence/prompt-candidate-custody-2026-10-08 | tar -x -C /tmp/pc
K=/tmp/pc/tasks/review-evidence/prompt-candidate-custody-2026-10-08
python3 "$K/preserve_artifacts.py" /path/outside/icloud/earningsnerd-evidence/prompt-candidate   # downloads + checks 12 zips
python3 -I "$K/recompute_archives.py" /path/outside/icloud/earningsnerd-evidence/prompt-candidate  # re-derives the figures
```

Once this folder is on main, `git archive origin/main` works the same way. The run needs about 650 MB free.

Then:
1. Keep a second copy in the private storage you already use.
2. Post the `N/12 verified` line from `verification.json` and the `recompute_archives.py` summary line on #1029.

Do not publish the zips or attach them to a public Release.

## Contents

| File | What it is |
| --- | --- |
| [manifest.json](manifest.json) | 12 artifacts, 644,613,214 bytes. Identifiers, run and head, sizes, Actions digests, expiry and set; no artifact content. |
| [preserve_artifacts.py](preserve_artifacts.py) | Byte-identical copy of item A's script (sha256 `2c5923e0…4f69`). It downloads each original zip, earliest expiry first, checks it against the manifest, skips verified zips on a re-run, refuses iCloud destinations and deletes nothing. |
| [stub-test.txt](stub-test.txt) | The script run against this manifest with a stub `gh` that serves the session's scratch copies: 12/12 verified, a re-run skips them, a corrupted zip exits 1, and an iCloud destination exits 2. |
| [recompute_archives.py](recompute_archives.py) | Offline re-derivation from the preserved zips. It checks every zip's hash and the member hashes, and for the four candidate archives recomputes the figures posted on #1029 and compares them. Standard library only; it reads the zips without extracting anything. |
| [recompute.txt](recompute.txt) | Its run on the twelve scratch copies (12/12 match) and five negative checks: a corrupted zip, a changed expected figure, a changed member hash and a file that is not a zip each exit 1, with every other archive still checked; a missing zip is listed. |
| [members.tsv](members.tsv) | Every member of the four candidate archives (231 rows), with bytes and sha256. |
| [verification.md](verification.md) | The independent verification: method, results, the critic's findings, corrections to the handback, merge-ref reproducibility and limits. |
| [final-review-437e245c.md](final-review-437e245c.md) | Verbatim text of the final three-lens review of the frozen head, previously only in session scratch. |

## Correction and clarifications to the handback (5965113700)

The critic contradicted one claim (the first bullet). The other three bullets clarify claims it confirmed.

- **Correction: balance gaps.** "Every gap is within cent resolution" holds for the lane total (0.22 against 0.221175) but not per run: the gaps are −0.0154, −0.0124, +0.0134 and +0.0032. These are consistent with charges debited after the reading that followed each run. Known costs stood throughout, so no spend decision depended on it. Posted on #1029 (comment 6054003539).
- **Clarification: cost rounding.** Each posted per-run cost is that run's tokens priced once and rounded to 6 decimals, and the posted lane total 0.221175 is the sum of those four figures. The exact total is 0.221175672 (0.221176 at 6 decimals). Rounding each call first gives 0.221181.
- **Clarification: eval-baseline telemetry.** The eval-baseline archive records `cost_usd` 0.0, so its 0.175401 is priced from tokens. Its 70 calls carry no peak flags or fingerprints; "off-peak" rests on the Saturday job timestamps, and the fingerprint count covers the 97 Copilot calls only.
- **Clarification: quoted figures.** "0 table figures in quotation marks" is `quote_inventory.py`'s heuristic. Q3 ASML d2 quoted figure-bearing MD&A sentences, which decision F's normalised check found in the source and published.
