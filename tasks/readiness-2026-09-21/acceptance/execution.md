# E7 measurement executor — review draft, not execution clearance

The controller, durable budget ledger, readiness check, packet builder and isolated worker are implemented for review. **Do not start paid E7 generation yet.** The original acceptance specification and USD 10 ceiling remain unchanged. This package does not infer human review, source availability or quality acceptance.

## What the draft does

`evals.acceptance_executor inspect` reads the approved manifest, source archive and human/execution receipts without calling a provider or creating a database. It requires all 30 independent briefs, named reviewers/adjudicator, exposure attestation, frozen configurations, current official pricing/balance, exact Fable contract and budget evidence. Blank templates remain deliberately incomplete.

The explicit `run-smoke` and `run-slot` paths create one fresh SQLite invocation in a sanitized child process and call `app.services.summary_pipeline.stream_filing_summary`, the existing production owner. The child has no production database, Stripe, Resend or PostHog credentials. Only the explicitly supplied `E7_GENERATOR_API_KEY` reaches the provider. A config cannot set Python import paths or arbitrary process controls. Both frozen checkouts must contain the same reviewed measurement instrumentation; an older uninstrumented comparator is refused, not silently patched or run without accounting.

The development smoke must match a current development-golden identity, have retained source packets and be charged to the same programme ledger before a holdout slot runs. Only its own completion receipt can be missing during that smoke; the human and other readiness requirements still apply. The manifest is bound to 90 candidate and 30 preselected comparator identities. Each slot requires an explicit command; the controller never advances to another filing automatically. Any error stops the programme. This draft performs **zero outer timeout retries**; it preserves the production owner's internal retries and is stricter than the approved maximum of one outer retry. Do not erase a failed slot or retry to improve a result.

Each provider attempt reserves a conservative charge atomically before SDK I/O, including streaming, internal retry, section recovery and verifier calls. SDK retries must be zero. Reservations are never refunded, including cancellation or unknown usage. The SQLite ledger is bound to the programme and exact tariff artifact; expiry or identity drift stops admission. It prices text request bytes plus framing at uncached input and maximum output tariffs, with rounding allowance; actual tokenizer/rate conservatism still needs the specified preflight review. The report separates retained conservative reservations from known usage estimates; neither is a provider invoice. The controller recomputes the full 5,082-request worst case; if over USD 10, the required explicit incomplete-stop-risk decision must be recorded before dispatch.

Keep **one permanent programme directory and budget ledger** for E7. Do not start a second directory, copy a zero ledger, delete STOP/pending records, or reset charges after a crash. The parent takes a programme lock; a child atomically consumes one hash-bound durable slot claim, so the same request cannot launch twice even if the parent dies. Accounting errors retain observed anomaly metadata and latch STOP. Pending, interrupted or failed accounting needs triage, not automatic redispatch.

The worker preserves actual source/structured grounding, raw canonical output, all emitted events and raw preview callbacks before UI coalescing, shared rendered Markdown, export HTML, and provider records. Preview callbacks carry the exact measured provider attempt. The collector derives counts and hashes from these retained files; it does not accept manually entered preview counts as proof. It preserves incomplete slots and requires the full 120 identities for completion. The packet builder removes only known administrative fields from a reviewer projection of canonical data, preserves financial content, keeps originals custodian-side, and rejects known execution markers. A custodian must still inspect real packets for unforeseen identity leaks, beyond the known export generation-date metadata omitted from the reviewer projection, before distribution.

## Remaining blockers

- The 1.16 GB source archive recorded in September 19 evidence was not present in the restored workspace on September 21. Recover the original archive and verify all 92 hashes; do not quietly substitute a recapture.
- Independent human briefs, reviewer/adjudicator commitments, exposure attestation and exact final configuration receipts remain unprovided. Fable availability does not satisfy them.
- The 6-K adapter binds the existing extractor to hash-verified archived SGML and verifies filing identity and embedded primary/exhibit bytes. Synthetic EX-99 and primary-fallback fixtures pass; the original archive is absent, so real archived-byte compatibility is unverified and any mismatch must stop before generation. SDK source fallbacks are refused before provider admission and retained as violations. No case may be excluded to shrink the denominator. Other edgartools/XBRL channels retain accession/CIK-linked results, with that provenance limitation visible.
- Automatic approval review rejected temporary source mutations of the USD 10 admission and required-brief gates. Those proofs have not run, and the checks remain intact. New E7 gates are not declared compliant with the repository's mutation-proof rule. The PR remains draft pending the required proofs and independent review.
- Current official tariffs, balance/quota evidence, tokenizer upper-bound review, current full-run risk decision and a frozen instrumented comparator remain pre-execution work. No E7 provider call has run in this tranche.

## Offline inspection

From `backend/`, using the repository's pinned dependencies:

```sh
python -m evals.acceptance_executor inspect \
  --manifest ../tasks/review-evidence/acceptance-2026-09-19/candidate-manifest.json \
  --archive /PATH/TO/ORIGINAL/work \
  --prerequisites ../tasks/readiness-2026-09-21/acceptance/prerequisites.template.json
```

The archive root is the parent of `e7-sources/`. Expected current result: `ready_for_paid_execution=false`. This is an honest hold, not a failed product score. Command help documents `run-smoke`, `run-slot` and `collect` for later authorized use; do not run them as a quota or connectivity probe. `worker` is an internal child entry point with one-time claim enforcement, not a second execution path.
