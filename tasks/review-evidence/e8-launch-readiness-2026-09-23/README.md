# E8 launch readiness review and attached add-on receipt — 23 September 2026 (session_016Pp5bKtWb43ugUV1QfPtr6)

**Outcome: no E8 judging, by design. This session received one of the kit's nine attachments and
ran in Auto mode, so it could not be the judging session. It verified the attachment, observed
the container read-only and reviewed the whole launch path offline (56 agents, 37 findings, each
adversarially verified). The launch kit, the unsealed restore and export tools, the gates and
the handovers are fixed here; nothing sealed changed. E8 remains 140 reused E2 controls (CLI
2.1.278) / 0 new / 160 missing. No bundle, guard, attestation, setup, model call, judge probe or
export.**

Branch `claude/attached-file-review-any8xz`, based on `main` `ebdc4c4`. Session origin iOS,
permission mode `auto`, per the session record.

## 1. What was asked, and why no judging started

The founder attached `fable-e8-continuation-2026-09-22.zip` with "Please refer to the attached
file and progress to the best of your abilities." It is attachment 7 of the launch kit's nine.
Two independent conditions rule out a judging run here:

- The kit says "refuse to proceed if any is missing"; eight were missing (the five bundle parts,
  the E3 supplement, the E3-complete deliverable and the transport manifest). The bundle, the
  guard and the E3 prerequisites exist only inside them.
- The founder's 22 September decision (option A) requires a fresh session in a non-Auto mode.
  This session is Auto, the mode whose classifier stopped both 22 September sessions.

So the useful work was to make the next properly launched session more likely to finish, and to
make its evidence complete.

## 2. The attachment (verified)

| Check | Result |
|---|---|
| Upload | `4ec603f3-fable-e8-continuation-2026-09-22.zip`, 17,064 bytes |
| SHA-256 | `5298a21e818c105a2a33f12859813446b1cde635d7bb48f3ce46e4a58f140909` = kit table row and `restore_e8_session.py::ADDON_ZIP_SHA256` |
| Members | 6; `code-sha256.json` 5/5 entries match (manifest SHA-256 `58145839…bd3f`) |
| Relation to the re-pin package | `build_repin.py::ADDON_HASHES` 3/3 equal the attached files; `founder-history-attestation.md` and `tests/test_e8_addon.py` byte-identical; `tools/e8_resume.py` differs only at line 24 (`E3_SUPPLEMENT_MANIFEST_SHA256` `8e43ac91…` → `1ef772b3…`), as `repin.diff` states |

The add-on's own offline suite needs the sealed bundle and was not run.

## 3. Container observations (read-only, 13:21Z unless noted)

- `/opt/claude-code/bin/claude --version` → `2.1.280 (Claude Code)`; SHA-256
  `1e08503dbdf3c2cb0d706d32f3408277388d1c76ef108673e8fe42c1b322925b`, 233,709,640 bytes, the
  same binary the 22 September receipt hashed. No drift: the re-pin still applies. Two
  containers now agree on this hash, which a future binary pin could use.
- `/opt/node22/bin/claude` is a symlink to it, created at container start.
- The session's own CLI process is `/opt/claude-code/bin/claude`, started by the harness with
  `--allowed-tools preset:default,Task,Bash,Glob,Grep,Read,Edit,MultiEdit,Write,…,mcp__github__*,…`
  (read from its process arguments). Auto mode drops blanket allows such as a whole-tool `Bash`
  (permission-modes.md), so in Auto the classifier decides; in Accept edits the list applies.
  This explains both 22 September denials better than the workspace-trust hold alone, and it
  means a silent step 0 in Accept edits does not prove the project rules were applied.
- `~/.claude.json` has no `projects` key: no workspace-trust record, so project allow rules are
  most likely still held (permissions.md: "Not used" in SDK sessions).
- None of the kit's fixed paths exist (`/home/user/fable-judging`, `/home/user/fable-assembly`,
  `/home/user/earningsnerd-fable-frozen`, `/home/user/fable-e3-deliverable`).
- The frozen commit `73cc311` was fetched by SHA into the engineering clone's object store for
  read-only review; a SHA fetch from a shallow web clone works, as the restore needs.

## 4. Permission events this session (verbatim reasons)

| # | UTC | Command (cwd `/tmp`, then `/home/user/EarningsNerd`) | Reason | Follow-up |
|---|---|---|---|---|
| 1 | 15:08:18Z | `claude auth status` with billing variables unset, output piped to a parser that printed only `loggedIn`/`authMethod`/`apiProvider` (to learn whether its stdout is strict JSON without a TTY) | `[Credential Exploration]` | Not retried. Still unverified; the restore now reads auth before writing anything, so a non-JSON reply refuses before any state exists. |
| 2 | 15:13:44Z | a compound `sed -n 1,45p restore_e8_session.py && python3 tasks/fable-e8-repin-2026-09-22/restore_e8_session.py --help \| head -5` | `[Auto-Mode Bypass]` | My error: a compound command with a pipe. Not retried; the docstring was read with the file tool. It is no evidence about a clean step 0. |

No other denial. The restore, export and setup scripts were never run against real paths; the new
tests import the two unsealed scripts as modules, with every fixed path moved to a temporary
directory.

## 5. Readiness review

Workflow run `wf_bc4180a7-356`: six reviewers, one per stage (restore; inspection, readback,
attestation and setup; execute; export; permission route and gate; docs consistency), each
read-only, with synthetic fixtures only. A merge step deduplicated 37 findings. One adversarial
verifier checked each note or doc finding, two checked each degrading or launch-blocking one.
Full per-finding record, votes and coverage lists: [`findings.json`](findings.json).

| Disposition | Findings |
|---|---|
| Fixed here | F01 mode not named (Plan still routes to the classifier) · F02 frozen commit not in the receipt · F03 six kit hashes unchecked · F04 refusal lost the log · F05 null `active` readback refused · F08 `*.log` ignore dropped every `run.log` from the commit · F09 export never verified its copy · F10 partial-setup stop refused, evidence lost · F11 approvals invisible to Claude · F13 run.log misdescribed · F14 restore docstrings · F16/F17 handovers never reached the kit · F19 kit header · F21 manifest schema crash · F22 attachments resolved after writing · F24 step 3 file list and lock location · F25 six-hour budget · F26 gate pinned only three commands · F28 background run from a subagent dies · F30 empty pending marker lost · F31 gate matcher and parameter rules · F32 uploads dir lookup · F33 attestation evidence · F36 seal self-referential · F37 docstring and todo |
| Kit notes (prose) | F12 founder reachable at run end · F23 restore timeout guidance |
| Founder decisions | F06 judge runs outside the venv (json-repair unavailable; recorded, not changed) · F29 no checkpoint during the ~2 h run (batching would change the pinned execute) · F35 three unused allow rules |
| Sealed rebuild candidates | F07 interrupt handler swallowed inside `communicate()` · F18 README blames the first stop on missing rules |
| Correction recorded | F15 (section 8) |
| Not defects | F20, F27, F34 (F34's refutation produced the launch-argument observation in section 3) |

The launch-blocking finding (F01) and every degrading finding were confirmed by at least one
verifier. The verifiers also cross-checked a long list of things that are right; for example,
all nine kit hashes equal the two earlier receipts, the five frozen eval hashes match `73cc311`,
the frozen requirements install on this image's Python 3.11 in 47 s, and every kit command
parses under its script's argparse (`findings.json`, `coverage`).

## 6. What changed

- `tasks/fable-e8-launch-kit.md` → revision 3. The seven gated commands are byte-identical; the
  prose names **Accept edits**, reads step 0 for it, carries the founder confirmation in
  message 3, names the attestation evidence and six-hour budget, and describes the restore,
  export, run.log and background run as the code behaves.
- `tasks/fable-e8-repin-2026-09-22/restore_e8_session.py` (unsealed). Before any write it
  resolves and checks all nine attachments against the pinned table, checks the transport
  manifest schema, and reads the CLI version and auth. It logs `frozen_commit` and each
  attachment, and prints the partial log on refusal.
- `tasks/fable-e8-repin-2026-09-22/export_e8_state.py` (unsealed). It follows the guard's lifecycle
  and never withholds evidence, writing `recovery_eligible` with named blockers. The verdict
  mirrors the sealed `validate_guard` checks, the quota and owner-loss markers and the exhausted
  601 ceiling. It verifies each copy, re-lists the source and records `inventory_sha256`; a file
  that vanishes mid-export is recorded, not a crash. It lists directories, pending markers, STOP
  files and failed entries.
- `.gitignore`: `!tasks/review-evidence/**/*.log`.
- Gates: `test_e8_launch_kit_matches_allow_rules.py` (83 cases), new `test_e8_export_state.py`
  (20), `test_e8_restore_session.py` (14), `test_e8_repin_package_is_sealed.py` (6).
- Handovers (`handover-astra-2026-09-19.md`, `handover-astra-2026-09-22-e8-repin.md`,
  `handover-fable-consolidated-2026-09-20.md`), lessons
  (`ops-prove-the-permission-route-before-a-gated-session.md` updated,
  `ops-evidence-exports-verify-themselves-and-survive-git.md` new) and `tasks/todo.md`.

## 7. Verification

- New and extended E8 gates: 123 passed (83 + 20 + 14 + 6), ruff clean on `backend/` and on
  both edited scripts.
- Mutation proofs, each reverted afterwards. Nine single-defect reversions of the restore and
  export fixes each failed exactly one test: null-`active` normalisation, copy verification,
  partial-setup refusal, pending markers, frozen-commit log, CLI-before-write order, part schema
  check, kit-table check, refusal log. Without the `.gitignore` line the three log tests fail.
  Tampering with the sealed README and regenerating `code-sha256.json` fails 2 seal tests. The
  kit gate's 15 new evasion cases (prior count, setup order, attestation values, table rows,
  mode sentence) and 6 new rule evasions are all rejected.
- Full backend gate (`ruff check .`, `bandit -r app -ll`, `pytest`): before round 2, 3,512 passed,
  39 skipped, 2 deselected; after round 2, 3,521 passed, 39 skipped, 2 deselected.
- Adversarial review of this diff (workflow `wf_0966267a-99b`), with three lenses: restore, export,
  and kit, gates and docs. The restore and export findings were each checked by two refuters,
  and every one was confirmed as minor:
  - the recovery verdict ignored an exhausted 601 ceiling and quota or owner-loss markers on
    completed calls;
  - it was looser than `validate_guard` (an empty latch string, non-dict owners, a disabled but
    initialized config, an unreadable state);
  - a file vanishing mid-export crashed the tool;
  - `shim_mode` formatting was untested;
  - a docstring misnamed the receipt file.

  The kit lens found six minor wording and gate issues: the header's claim of sameness with the
  upload, the subagent-lifetime wording, "two intervening receipts" when there are three, the
  exit-1 wording, whitespace in parameter rules, and a missing F15 row. Its refuters were stopped
  so the fixes could land; I checked each against the files and docs myself. All eleven are fixed
  in round 2, with new tests. Mutation proofs: removing the ceiling, latch (empty-string), owner,
  enabled/reconciled or quota/owner-loss checks, the vanish handling, the `shim_mode` format or
  the whitespace-tolerant parameter regex each fails its test.

## 8. Correction to earlier records

The second-session receipt (`../e8-repin-restore-2026-09-22/receipt.md`, lines 79-82) says the
17:44:39Z pristine-guard snapshot "files were not committed". The first receipt
(`../e8-restore-2026-09-22/receipt.md`, line 155) says "Nothing above is committed". Both are
inaccurate now. The snapshot directory
`../e8-restore-2026-09-22/guard-before-state-20260922T174439Z/` and `assembly-report.json` were
committed in #945 (`3d836ad`) and verify against that directory's `SHA256SUMS`. It is the
durable before-state reference; the kit's step 3 now cites its `readback.json`. The two receipts
are left unchanged as evidence.

## 9. Still unverifiable here

- The real `transport-manifest.json` schema. The restore now refuses cleanly, before writing,
  if it differs.
- Whether `claude auth status` prints strict JSON without a TTY (event 1 above). Session 1
  recorded its values.
- Whether an Accept edits session gets the same harness allow list. The mode is applied after
  launch, so it is expected but not observed.
- Whether a cloud VM can be reclaimed during the ~2 h background run (F29).

## 10. Before the next launch

1. Merge this PR, so `main` carries revision 3, the tool fixes and the gates.
2. Founder decisions, none blocking: F35 (drop the three unused allow rules or keep them), F29
   (accept the mid-run exposure or batch), F06 (keep the venv as is, recommended, or `--copies`),
   and whether to schedule a sealed rebuild for F07 and F18.
3. Launch exactly as the kit says: a new web session on `main`, **Accept edits**, the nine
   attachments across two messages, and message 3 with its confirmation line completed.

This receipt makes no quality, causal-improvement or production-activation claim.
