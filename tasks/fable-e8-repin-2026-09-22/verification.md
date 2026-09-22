# E8 re-pin offline verification — 22 September 2026

**Status: NOT YET BUILT OR VERIFIED.** The Claude Code web session that authored this package
(session `01KqPfr1vxZn3pw79Pi4rQj7`) was stopped by its auto-mode permission classifier when it
tried to run `build_repin.py` (reason given: "Security Weaken", because the output relaxes a
version pin). The session did not route around that decision. The package directory therefore
contains the build script, the restore and export tools, this README and this file, but none of
the derived outputs (`tools/*.py`, `supplement-sha256.json`, `code-sha256.json`, `repin.diff`,
`build-summary.json`).

To finish, in a session with the allow rules named in `tasks/handover-astra-2026-09-22-e8-repin.md`
or on a machine with the judging kit extracted:

1. Run `build_repin.py` against the sealed supplement and add-on. It asserts every sealed source
   hash before copying and refuses if any substitution does not match exactly once.
2. Confirm `repin.diff` shows only the five expected lines (two in `guard_setup.py`, two in
   `resume.py`, one in `e8_resume.py`) and that `build-summary.json` lists `tools/binding.py`,
   `tools/readout.py`, `founder-history-attestation.md` and `tests/test_e8_addon.py` as
   byte-identical.
3. Run the add-on's offline suite against a disposable copy of the restored bundle with the
   fixture layout `tests/test_e8_addon.py` expects (three levels above the tests directory:
   `work/fable-reconcile-2026-09-22/{supplement -> this package, fixture/<bundle copy>,
   fixture-repo -> frozen checkout}` and `outputs/fable-e3-complete-review-2026-09-22/extracted/
   bundle-stage-records -> the E3 deliverable's stage records`). Expected: 10 tests OK, as the
   sealed add-on reported. The E3 supplement's `tests/test_reconciliation.py` needs the
   21 September partial-state fixture, which is not in the kit; record it as not run.
4. Rebuild once more after editing this file so `code-sha256.json` covers the final text, and
   record the resulting `repin_supplement_manifest_sha256` here; that value goes into the
   attestation's `e3_supplement_manifest_sha256` field.

No CLI, model, guard setup or attestation is involved in any of these steps.
