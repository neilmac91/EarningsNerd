# Retain a probe's journal and ledger outside the temporary directory, and validate the copy you keep

Date: 2026-11-01 · Area: evals, the founder's machine

**Context.** F21 asked for the offline re-validation of the 2026-10-01 native-delivery probe's ledger at
#1035's merged head. When the founder ran probe 3 on 2026-11-01, nothing was left under `/private/tmp`:
macOS clears it on restart, and the ledger had lived there. The adapter refuses a delivery root under any
`.claude` ancestor, so on a machine with `~/.claude` the dispatch roots sit in a temporary directory, and
`backend/scripts/native_delivery_probe.py` called its journal "discarded afterwards". Probe 3's folder
survived only because the founder copied it to `~/en-probe-3-ledger` by hand. Its re-validation still had
to be asked for separately.

**Rule.**
- A probe's journal and ledger are evidence, not scratch: both are needed to validate it later.
- `native_delivery_probe.py run` copies both into `<retain_root>/<probe_id>/`, checks the copy byte for
  byte against the originals, and validates it with `validate_delivery_binding`. Exit code 6 means the copy
  did not validate: copy the original roots by hand before a restart.
- `plan` refuses a `retain_root` that is relative, missing, under a temporary directory (`/tmp`,
  `/private/tmp`, `/var/folders`, the machine's own temporary directory), under an iCloud-synced home
  directory, inside the repository, or already holding that probe's copy. Gated by
  `test_probe_retain_root_is_durable_outside_the_repository_and_written_once` and
  `test_probe_retains_a_copy_that_validates_and_reports_one_that_does_not` in
  `backend/tests/unit/test_acceptance_source_review_delivery.py`.
- Before relying on a retained ledger (a re-validation, a comparison, a record), validate the copy you hold.
  The validation is cheap and offline, and the original may already be gone. This clause is review-checked:
  no gate can see which copy a later reader uses.

Related: `ops-evidence-exports-verify-themselves-and-survive-git.md` (an evidence export verifies its copy).

**Evidence.** The founder's probe 3 run output (2026-11-01: "earlier probes: no record left under
/private/tmp"); `tasks/todo.md` F21; `tasks/readiness-2026-09-21/acceptance/source-review-native-delivery.md`.
