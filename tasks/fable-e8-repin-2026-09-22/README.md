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
| `tools/resume.py` | supplement copy; `verified_cli` regex and message `2.1.278` → `2.1.280`, plus the historical E3 reconciliation manifest pinned to its original hash (three lines) |
| `supplement-sha256.json` | regenerated for the four tools above |
| `tools/e8_resume.py` | add-on copy; `E3_SUPPLEMENT_MANIFEST_SHA256` now names this package's manifest (one line) |
| `founder-history-attestation.md`, `tests/test_e8_addon.py` | byte-identical to the E8 add-on |
| `code-sha256.json` | regenerated for the five add-on files |

The founder approved six changed source lines after the initial five-line derivation failed
offline admission. `resume.py::expected_reconciliation()` originally used its own manifest
hash to identify the historical E3 reconciliation record. Rebuilding the runtime manifest
changed that expectation and rejected the preserved record. The sixth substitution pins that
historical identity to `8e43ac912126d5253f5a46b4e5cc88ffbaa5b4ab4e5d49bb37f3189d1b0c568c`.
The E3 record remains byte-identical; `trusted_common()` and `verify_supplement()` still verify
the current runtime against the regenerated manifest. `repin.diff` contains exactly six changed
lines across three files, with no other derived-source differences.

Unchanged by construction: the judge (`cli:claude-fable-5-1`), contract 2, the frozen checkout
`73cc31162c3dfe7ec497c8c88c43cf397afce4a7` and its five pinned files, the frozen 300-slot panel
and order, the 140 reused E2 controls, the sealed guard shim and its 601-call ceiling, the
conservative prior charge 287, the attestation schema (only the `e3_supplement_manifest_sha256`
value changes to this package's manifest hash), the single-slot concurrency and the no-outer-retry
rule. All admission requirements are retained: historical E3 reconciliation stays bound to its
original supplement manifest while E8 runtime and attestation bind the derived manifest.

## The confound this introduces

The 140 reused E2 control verdicts were produced under CLI `2.1.278`. The 160 new E8 slots
(140 new mains, 20 duplicates) are planned under `2.1.280`.
The model identifier is the same, but the CLI build differs, so any within-E8 comparison between
reused and new slots carries a CLI-version confound in addition to the order/timing confounds the
sealed README already names. Every E8 readout, including a partial completion receipt, must
state both versions and report reused controls separately from completed new mains, completed
duplicates and missing slots. The actual execution is historical control reuse followed by a
160-slot continuation, not a randomized or interleaved 300-call execution. Results remain
descriptive: this panel cannot separate CLI/time effects from prompt effects or establish causal
prompt improvement or product acceptance. Control-main versus new control-duplicate disagreement
also carries the version/time confound; it is not a pure within-build repeatability estimate.

Engineering judgment: the panel remains worth running as a bounded descriptive variability
check with those limits. No quality result follows from this offline package review.
`stages/e8/environment.supplement.json` records the observed version and is overwritten by a
later execution; retain each session's export and receipt. A binary-hash pin is deferred because
this offline Mac review does not possess the judging container's Linux `2.1.280` executable.
The exact version gate remains; no binary identity or cross-build equivalence is claimed.

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

# 0. Base-kit restore (includes git/pip environment provisioning and CLI readback).
python3 "$REPIN/restore_e8_session.py" --uploads /root/.claude/uploads/<session-dir>

# 1. First-session inspection: expect 140 reused, 160 planned, 0 complete, 160 missing.
"$PYTHON_BIN" "$REPIN/tools/e8_resume.py" --bundle "$BUNDLE" --supplement "$REPIN" --repo "$FROZEN_REPO"

# 2. Guard readback (before-state snapshot outside the bundle), then a NEW attestation with a
#    current UTC observation, prior_count 287, and e3_supplement_manifest_sha256 = the value in
#    build-summary.json (repin_supplement_manifest_sha256).

# 3. FIRST SESSION ONLY, verified never-initialized template. Never after checkpoint recovery.
#    One-time setup through THIS package's guard_setup.py (the sealed one refuses 2.1.280).
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

## Sole-guard recovery after a container recycle

Engineering ruling under the founder's 22 September request: allow a byte-for-byte recovery
of the **sole logical initialized guard**, only under all the conditions below. This narrowly
supersedes the sealed prohibition on copying an initialized guard for disaster recovery; it
does not permit a second live guard, a reset, a rollback or any dispatch in this offline task.

1. Stop dispatch and establish exclusive ownership before exporting. The source must remain
   quiescent throughout the export: no executor, model/probe call, active guard owner or writer.
   `export_e8_state.py` is a copier, not an atomic snapshot or admission check; it takes no lock
   and hashes the source after copying. Verify the copied files against its inventory as well
   as the unchanged source before committing the checkpoint.
2. Use the latest complete committed checkpoint. Retain a named operator's handoff receipt
   identifying the source container, checkpoint commit, inventory SHA-256, last completed slot,
   guard count, and evidence that no later E8/probe call occurred. Establish that the source
   executor/container is retired and cannot resume before activating the destination. Backups
   remain inert. Ledger agreement cannot establish these external facts. If the source died
   before a trustworthy final checkpoint or later activity is uncertain, stop for reconciliation;
   do not roll back to an older matching counter.
3. Verify the package manifests, original 818-file seal, frozen checkout and E3 prerequisites.
   Require all six exported guard files (`config.json`, `state.json`, `TEMPLATE.json`,
   `initialization.json`, `template-configuration.json`, `sha256.txt`), the complete `stages/e8/`
   tree and prior receipts, including all session attestations and before/after readbacks.
   Verify every exported file's bytes and size against the committed inventory before and after
   copying. Preserve extra evidence; an inventory alone does not prove the export is complete.
4. Restore at the same resolved absolute bundle/guard-state and real-CLI paths into a destination
   with no initialized guard or E8 work of its own. Retain the sealed shim byte-identically and
   executable (0755); restore mutable guard/setup records and E8 evidence byte-for-byte. Do not
   edit paths, alter counts/history, rerun either setup command or clear a latch/STOP. Replacement
   is allowed only for mutable guard/template files that still exactly match the freshly verified
   never-initialized base. Any existing initialized state or other differing destination evidence
   is a conflict: stop without overwriting it. The sealed `stages/e8/index.json` must match
   identically and remain unchanged; reverify all 818 sealed files after overlay. A path change
   needs a separately reviewed migration.
5. Before the separately authorized continuation, perform a new human readback and write a new
   named current-UTC attestation, using this package's supplement hash and the original prior
   charge 287. The three affirmative history/exclusivity assertions require current evidence;
   never reuse an earlier attestation or automatically renew its timestamp. Normal `admit()`
   and `attest()` checks must then pass on the restored state before dispatch, and before each
   subsequent slot. `attest()` requires ledger continuity from 287, increments of one or two
   calls per slot, the matching final counter, and completed invocation sequence 288 through
   that counter. Full admission additionally binds slot outputs and prerequisite evidence.
6. Any pending/failed call, active or unknown owner, STOP, quota/owner-loss latch, exhausted
   ceiling, interrupted initialization, missing evidence or accounting discrepancy remains a
   stop. Export it for investigation; restore permission is never permission to clear or retry it.

Passing `attest()` is necessary but insufficient: a consistent stale checkpoint or fork can
pass its ledger checks. Conditions 1–4 establish freshness and sole ownership outside that
function. The original 601 ceiling and all charged calls survive recovery.

`restore_e8_session.py` restores the base kit and E3 overlay only; it does **not** apply an E8
checkpoint. The command sequence above is for the first session. On recovery, restore the
verified checkpoint under this policy before inspection, skip setup entirely, and expect the
checkpoint's actual completed/missing counts. The checkpoint overlay is an operator procedure,
not an implemented or offline-tested restore command in this package.

## Session prerequisites that this package cannot supply

- The judging session must run on a branch whose `.claude/settings.json` allows the restore
  script, this package's `guard_setup.py` and `e8_resume.py`, and `export_e8_state.py`. The
  22 September restore attempt was stopped by the auto-mode permission classifier on the
  overlay step because the session's branch carried no allow rules; the exact rule text is in
  `tasks/handover-astra-2026-09-22-e8-repin.md`.
- The container is ephemeral. Run `export_e8_state.py` and commit its output after every stop.
  Recovery is permitted only under the sole-guard policy above. A failed or uncertain stop
  produces evidence for reconciliation, not a resumable checkpoint.

## Verification

See `verification.md` for the offline proofs run against a disposable copy of the restored bundle.
