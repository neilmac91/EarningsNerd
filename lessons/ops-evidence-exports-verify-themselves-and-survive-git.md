# An evidence export copies everything, verifies its copy, states its own eligibility, and survives `git add`

**Date:** 2026-09-23 · **Area:** ops / evals / judging sessions

## Context

The E8 judging container is ephemeral: the committed export of the guard and stage state is the
only durable record of a paid, ceiling-limited run. The 23 September readiness review found four
ways the export could lose that record without anyone noticing:

- `export_e8_state.py` refused a reachable stop state (template configured, initialization
  refused) and an unmatched readback. The kit forbids retrying a refused step, so the refusal
  would have discarded the evidence it was built to keep.
- It hashed the source after copying and never read the copy back, although the sealed recovery
  policy requires the copy to be verified against the inventory and the unchanged source.
- Git cannot track an empty directory, so a `.pending-*` owner marker, which is terminal for the
  resume tool, vanished from the commit.
- The repository's `*.log` ignore rule made `git add` drop every per-slot `run.log` silently, while
  the export's inventory still listed them. A later restore would have failed against its own
  inventory, with the container gone.

## Rule

A tool that exports evidence for commit refuses only on structural errors: no source, or a
destination that already exists. For everything else it copies what exists and records a
verdict (`recovery_eligible`, with every blocker named). It verifies each copy against the source
before and after copying, re-lists the source afterwards, records an inventory hash, and lists
directories and terminal markers explicitly. A gate proves that git keeps every file the
inventory lists (`git check-ignore --no-index` on representative paths). Ignore rules and
exporters change separately, so the gate belongs with the exporter's tests.

Gate (rule 12): `backend/tests/unit/test_e8_export_state.py`. It covers each stop stage, the
readback encodings, copy and source verification, pending markers and the ignore rule.

## Evidence

- `tasks/review-evidence/e8-launch-readiness-2026-09-23/README.md` (findings F05, F08, F09, F10, F30)
- `.gitignore` (`!tasks/review-evidence/**/*.log`)
- `tasks/fable-e8-repin-2026-09-22/README.md`, sole-guard recovery conditions 1, 3 and 6
