# E8 re-pin offline verification — 22 September 2026

**PASS: founder-approved six-line sibling derivation; 10 offline tests OK.** No E8 judging
was performed. The final README and this verification record are covered by the rebuilt
`code-sha256.json`. The exact source diff is `repin.diff`; output hashes are in `build-summary.json`.

## Review and approved scope

The initial five-line build failed: 4 tests passed, 3 failed and 3 errored, all six unsuccessful
tests reaching `Reconciliation record changed`. Work stopped as instructed. The founder then
approved the proposed sixth source-line change before implementation.

`resume.py::expected_reconciliation()` originally read the current runtime manifest hash when
validating historical E3 evidence. The sixth substitution pins that historical identity to the
original supplement hash `8e43ac912126d5253f5a46b4e5cc88ffbaa5b4ab4e5d49bb37f3189d1b0c568c`.
It preserves the historical record exactly and keeps its STOP/ledger/failed-output bindings.
Current runtime integrity remains independently checked by `trusted_common()` and
`verify_supplement()` against the regenerated manifest. No acceptance check is bypassed.

Final diff: two version-check/message lines in `guard_setup.py`, two version-check/message
lines and one historical-manifest line in `resume.py`, one runtime-manifest constant in
`e8_resume.py`. Exactly six removed/six added source lines in three files. `binding.py`,
`readout.py`, `founder-history-attestation.md` and `tests/test_e8_addon.py` are byte-identical to
the sealed sources. The builder asserts every substitution occurs exactly once.

The new supplement manifest SHA-256 is:

```text
1ef772b3157106bcf9bee52675f89bdf0cf643f0457eb405b6ce28e5fe950f6f
```

This is the value for a future operator attestation's `e3_supplement_manifest_sha256`, after
that operator performs the required live readback. No operational attestation was created here.

## Inputs and fixture

Four archives matched their pinned SHA-256 values before extraction:

| Archive | SHA-256 |
| --- | --- |
| corrected bundle | `38db06d2c3815893f5d48c96b1f2f8bfd0984f45c538026e19d2e034cc9b5256` |
| E3 supplement | `0ac918a0f38456250b5db634728a3461f6b2f921c1efbd11f599320aa4e5c1bd` |
| E8 add-on | `5298a21e818c105a2a33f12859813446b1cde635d7bb48f3ce46e4a58f140909` |
| E3 complete return | `281095aa83f560ded61961c09479f9b9d917947c21ffac887be338d729019ed6` |

Sealed checks passed before building and again after deriving the package: bundle 818/818,
supplement 4/4 and payload inventory 10/10, original add-on 5/5, E3 return 712/712. The original
immutable manifest hash remains `0fe5cb9e45c1fca76d2d9d71b0a13f58958ea7242efe34ae2a9f64544402d2c3`.
The detached frozen checkout is `73cc31162c3dfe7ec497c8c88c43cf397afce4a7`; all five pinned eval
files match. Original extracted sources were not edited.

Tests ran with Python 3.14.7 on macOS 26.7 arm64. They require only the standard library and
extract pure validation logic from frozen files, rather than importing the application or
starting its harness. This does not verify the Linux judging environment, its venv or real CLI.

Fixture layout, relative to the repository root (the test's `PROJECT`):

```text
work/fable-reconcile-2026-09-22/
  supplement -> ../../tasks/fable-e8-repin-2026-09-22
  fixture/fable-resume-corrected-2026-09-20/   # disposable bundle copy with E3 overlay
  fixture-repo -> detached frozen checkout at 73cc311...
outputs/fable-e3-complete-review-2026-09-22/extracted/
  bundle-stage-records -> extracted E3 return's bundle-stage-records
```

The reviewed restore module's offline overlay function copied 656 inventory-verified E3 files
to the disposable fixture, producing 70/69/70 slot directories. The AAPL017 result remains
virtually reused. All 818 sealed files and the historical reconciliation record stayed identical.
The fixture shim's mode was restored to 0755 with no content change. The test suite then made
its own temporary copies. No fixture data is committed as operational evidence.

Reproduction after restoring this layout:

```sh
python3 -B tasks/fable-e8-repin-2026-09-22/build_repin.py \
  --supplement /path/to/sealed/fable-reconciliation-2026-09-22 \
  --addon /path/to/sealed/fable-e8-continuation-2026-09-22 \
  --out tasks/fable-e8-repin-2026-09-22
python3 -B -m unittest discover \
  -s tasks/fable-e8-repin-2026-09-22/tests -p test_e8_addon.py -v
```

## Results and limits

```text
Ran 10 tests in 73.329s

OK
```

The unchanged suite covers frozen panel/prerequisite admission, original AAPL STOP integrity,
missing E3 evidence, unlogged E8 outputs, STOP/order changes, per-slot prerequisite rechecks,
initialization hold, counter continuity, synthetic two-slot progression and attestation freshness.
Its synthetic attestations and counters exist only in temporary test directories; they are not
operator attestations, initialized live guards or model results.

The final read-only adapter inspection (without `--execute`) also passed its own manifest
verification and full admission, reporting 140 reused controls, 160 planned, 0 complete and
160 missing; [inspection JSON](../review-evidence/e8-repin-2026-09-22/offline-inspection.json).
No guard/execution lock, initialization record or E8 stage output was created in the fixture.

The initial failing build and final passing build are the regression proof for the added
historical pin. No sealed test was edited. The old E3 `tests/test_reconciliation.py` was not run:
it requires the September 21 partial-state fixture, which is absent from this kit. The live
Linux CLI, real guard initialization, export/recovery execution and model calls were not tested.
The optional CLI binary-hash pin is deferred because the Linux executable is unavailable here.

Independent read-only review found no blocker in the six-line derivation. It checked historical
versus runtime identity, full evidence preservation, CLI-confound interpretation and the guard
recovery policy. README clarifications distinguish recovery into a verified pristine base from
overwriting initialized state. `attest()` proves internal ledger continuity, not freshness or
sole ownership; the documented recovery conditions require both externally. No automated E8
checkpoint restore is supplied. The seven allow rules match handover section 4 exactly.

Evidence: [initial failing suite](../review-evidence/e8-repin-2026-09-22/five-line-tests.log),
[passing suite](../review-evidence/e8-repin-2026-09-22/six-line-tests.log),
[integrity checks](../review-evidence/e8-repin-2026-09-22/integrity-checks.json),
[archive/manifests](../review-evidence/e8-repin-2026-09-22/kit-verification.json),
[fixture overlay](../review-evidence/e8-repin-2026-09-22/fixture-verification.json).

## E8 status and interpretation

E8 remains 140 reused E2 controls / 0 new / 160 missing. No real CLI, live guard setup, operator
attestation, judge invocation or model call occurred in this preparation. Universe-wide
generation remains off; production was not changed. A judging session is separately authorized.

The 140 reused controls were judged under CLI 2.1.278; 160 new slots (140 mains, 20 duplicates)
are planned under 2.1.280. Every readout must state that CLI-version confound alongside timing
and historical control reuse. This is not randomized/interleaved 300-call execution, and the
panel cannot isolate causal prompt improvement or establish product acceptance. No quality
result is claimed by these offline proofs.
