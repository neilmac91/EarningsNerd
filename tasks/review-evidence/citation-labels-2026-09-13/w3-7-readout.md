# W3-7 current readout reconciliation — 2026-09-13

At 2026-09-13T03:49:43Z, the latest GitHub `data-quality-weekly.yml` run is still [34150116352](https://github.com/neilmac91/EarningsNerd/actions/runs/34150116352), scheduled on main at 2026-09-07T18:03:51Z and completed with failure at 18:05:39Z. Its exact head is `c09a4d222e2038a07081c389caf384bb84400a49`. No newer scheduled or manually dispatched run appears in the latest eight workflow runs. There is no new usable weekly strong-judge evidence to release W3-7.

The retained, unexpired artifact is `weekly-judged-readout-34150116352`, artifact ID `10029049893`, created 2026-09-07T18:03:59Z, archive size 1,702 bytes, API digest `sha256:010a6ebea46be71d77eeb530a9d3f58359da46f49e4a9d764718eefa99b26162`. Only this small artifact was downloaded. Its `readout.json` reports:

```text
status: unavailable
reason: Generator or strong-judge credential absent; no model calls made
expected: 24
completed: 0
scored: 0
missing: 24
judge_model: claude-opus-4-8
judge_backend: anthropic
source_sha / cohort_sha256 / golden_set_sha256: null
```

The artifact's missing source SHA is not repaired by inventing one: the run head above is GitHub run provenance, distinct from absent measurement provenance. The old judge-model field describes this failed September 7 attempt, not the founder's later Fable preference or a fresh model execution. This artifact also cannot establish which credential is absent today.

Two independent checks refute a hidden successful measurement in this run: the actual JSON is explicitly unavailable with zero scored; job `101830443960` skipped dependency installation after credential preflight, then logged `Weekly readout: unavailable; judged=0/24; Generator or strong-judge credential absent; no model calls made`. The separate report job `101830477157` succeeded, but it only executed the report delivery path; that success does not turn unavailable measurements into judgments. The immediately preceding August 31 run `33430093824`, head `e8ea339f0548cfcc76e5b1475b67977b5373fcb3`, has zero artifacts. Earlier successes in the returned run list precede the strong-judge implementation and are not 24/24 readouts.

## Due-date and slip evidence

The weekly strong-judge implementation entered the workflow in commit `6cd07983bb496cc07b15f6f74b3c1a063e6e2d79`, recorded 2026-09-05T14:07:02+02:00. The workflow schedules Monday 13:00 UTC (`.github/workflows/data-quality-weekly.yml:9`), making September 7 at 13:00 UTC the first concrete scheduled opportunity after implementation; actual GitHub execution started about five hours later. The handover separately asks the founder to add the credential and dispatch, but records no promised date for that manual action (`tasks/handover-wave3-2026-09.md:127`).

Therefore the handover's September 5 age is not sufficient evidence that the readout has slipped more than one week. Relative to the first scheduled opportunity, the failure is less than six days old at this inspection. A strict more-than-one-week interpretation would first be satisfied after September 14 at 13:00 UTC if that scheduled opportunity is used as the due-date anchor; using actual failed execution instead would put it after September 14 at 18:03:51Z. Neither threshold has elapsed now. This is a documented scheduling inference, not a newly invented founder deadline. If another recorded earlier commitment exists, reconcile it explicitly before invoking the exception.

W3-8a unpaid source/ground-truth preparation can proceed now. Its paid re-pin can follow W3-7 or the documented delay exception once supported; do not perpetuate the old September 8 observation indefinitely, and do not assume that merely crossing the handover's anniversary activates it. W3-8b still follows 8a, and two re-pin PRs must not be open together.

## Required next evidence and boundaries

The governing W3-7 contract remains an actual usable 24/24 artifact, followed by the wrong-snap/advisory report and founder arm decision (`tasks/handover-wave3-2026-09.md:329–348`). Fable's 26-case/52-attempt development-corpus review does not fulfill that workflow contract. Current routine summary assessments with the judge disabled likewise do not satisfy it. No new provider call, credential inspection, dispatch, report email or console change was performed here.

The workflow still runs its report job with `if: always()` and executes the RESEND-carrying Cloud Run job (`data-quality-weekly.yml:102–125`). A convenience manual dispatch would therefore have a live side effect and must not be used casually as a test while reconciling evidence. The correct immediate action is to retain the unmet prerequisite and prepare the concrete approved measurement route separately.

Evidence retained: `outputs/w3-7-weekly-runs.json`, `outputs/w3-7-latest-artifacts.json`, `outputs/w3-7-latest-jobs.json`, `outputs/w3-7-latest-measure.log`, `outputs/w3-7-prior-artifacts.json`, and `outputs/w3-7-current-artifact/readout.json`. All GitHub operations were read-only; no repository files changed.
