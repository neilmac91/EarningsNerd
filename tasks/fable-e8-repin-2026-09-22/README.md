# Fable E8 re-pin package — 22 September 2026

Purpose: continue the E8 variability panel on the Claude CLI that the judging containers now
carry (`2.1.280`), after the sealed packages' exact `2.1.278` build disappeared with a container
image change. The founder chose this on 22 September ("go with the latest version"). This package
is a new reviewed sibling of the sealed E3 supplement and E8 add-on. It edits nothing sealed.

## What changed, and only that

Built by `build_repin.py` from the sealed sources (hashes asserted before copying). The full
unified diff is `repin.diff`; `build-summary.json` records every output hash.

| File | Relation to sealed source |
|---|---|
| `tools/binding.py`, `tools/readout.py` | byte-identical to the E3 supplement |
| `tools/guard_setup.py` | supplement copy; `_real_cli` regex and message `2.1.278` → `2.1.280` (two lines) |
| `tools/resume.py` | supplement copy; `verified_cli` regex and message `2.1.278` → `2.1.280` (two lines) |
| `supplement-sha256.json` | regenerated for the four tools above |
| `tools/e8_resume.py` | add-on copy; `E3_SUPPLEMENT_MANIFEST_SHA256` now names this package's manifest (one line) |
| `founder-history-attestation.md`, `tests/test_e8_addon.py` | byte-identical to the E8 add-on |
| `code-sha256.json` | regenerated for the five add-on files |

Unchanged by construction: the judge (`cli:claude-fable-5-1`), contract 2, the frozen checkout
`73cc31162c3dfe7ec497c8c88c43cf397afce4a7` and its five pinned files, the frozen 300-slot panel
and order, the 140 reused E2 controls, the sealed guard shim and its 601-call ceiling, the
conservative prior charge 287, the attestation schema (only the `e3_supplement_manifest_sha256`
value changes to this package's manifest hash), the single-slot concurrency, the no-outer-retry
rule and every admission check.

## The confound this introduces

The 140 reused E2 control verdicts and all KO, E1 and E3 judgments were produced under CLI
`2.1.278`. The 160 new E8 slots (140 new mains, 20 duplicates) will be produced under `2.1.280`.
The model identifier is the same, but the CLI build differs, so any within-E8 comparison between
reused and new slots carries a CLI-version confound in addition to the order/timing confounds the
sealed README already names. Every E8 readout must state this. `environment.supplement.json`
under `stages/e8/` records the observed version on each run.

## How to use it (judging session)

Roles: this directory is passed as BOTH `--supplement` and the add-on root. `e8_resume.py` verifies
`code-sha256.json` two levels above itself and `supplement-sha256.json` two levels above the
`resume.py` it imports, so one directory serves both.

```sh
REPIN=/home/user/EarningsNerd/tasks/fable-e8-repin-2026-09-22
BUNDLE=/home/user/fable-judging/fable-resume-corrected-2026-09-20
FROZEN_REPO=/home/user/earningsnerd-fable-frozen
PYTHON_BIN=/home/user/fable-judging/venv/bin/python
REAL_CLI=/opt/claude-code/bin/claude

# 0. Offline restore (assemble, extract, verify, overlay E3 records, worktree, venv, readback).
python3 "$REPIN/restore_e8_session.py" --uploads /root/.claude/uploads/<session-dir>

# 1. Read-only inspection: expect 140 reused, 160 planned, 0 complete, 160 missing.
"$PYTHON_BIN" "$REPIN/tools/e8_resume.py" --bundle "$BUNDLE" --supplement "$REPIN" --repo "$FROZEN_REPO"

# 2. Guard readback (before-state snapshot outside the bundle), then a NEW attestation with a
#    current UTC observation, prior_count 287, and e3_supplement_manifest_sha256 = the value in
#    build-summary.json (repin_supplement_manifest_sha256).

# 3. One-time setup through THIS package's guard_setup.py (the sealed one refuses 2.1.280).
"$PYTHON_BIN" "$REPIN/tools/guard_setup.py" --guard-dir "$BUNDLE/e8/guard" --real-cli "$REAL_CLI" --configure-template
"$PYTHON_BIN" "$REPIN/tools/guard_setup.py" --guard-dir "$BUNDLE/e8/guard" --real-cli "$REAL_CLI" --prior-count 287

# 4. Execute, background, log retained.
"$PYTHON_BIN" "$REPIN/tools/e8_resume.py" --bundle "$BUNDLE" --supplement "$REPIN" --repo "$FROZEN_REPO" \
  --python "$PYTHON_BIN" --cli "$REAL_CLI" --guard-dir "$BUNDLE/e8/guard" \
  --attestation "$E8_ATTESTATION" --max-new 160 --execute

# 5. After any stop, export guard + stage state for commit (containers are not persistent).
python3 "$REPIN/export_e8_state.py" --bundle "$BUNDLE" --receipts /home/user/fable-judging/receipts \
  --out tasks/review-evidence/e8-fable-state-$(date -u +%Y%m%dT%H%M%SZ)
```

All the sealed rules still apply: never repeat a setup command, never clear a latch or STOP, never
invoke the judge harness directly, never start E1 or E7, stop on any refusal, quota latch, ceiling
exhaustion or accounting discrepancy, and return partial results with the evidence.

## Session prerequisites that this package cannot supply

- The judging session must run on a branch whose `.claude/settings.json` allows the restore
  script, this package's `guard_setup.py` and `e8_resume.py`, and `export_e8_state.py`. The
  22 September restore attempt was stopped by the auto-mode permission classifier on the
  overlay step because the session's branch carried no allow rules; the exact rule text is in
  `tasks/handover-astra-2026-09-22-e8-repin.md`.
- The container is ephemeral. Run `export_e8_state.py` and commit its output after every stop.
  Restoring an exported guard into a later container is a founder decision; the add-on's
  `attest()` re-derives the counter from the ledger and refuses a guard that disagrees.

## Verification

See `verification.md` for the offline proofs run against a disposable copy of the restored bundle.
