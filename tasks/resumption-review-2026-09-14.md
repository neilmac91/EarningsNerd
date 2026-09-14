# September 14 resumption review

Takeover main was `324589269edde0c524b103e0f071375378934417` (#856), read from GitHub. The clean primary checkout was fast-forwarded to that commit. This review continues the [September 14 handover](handover-astra-2026-09-14.md) and [September 13 quality checkpoint](handover-astra-2026-09-13.md). It does not repeat any merge, paid assessment or backend deployment verification.

## Completed checks

- [x] Verify takeover SHA and merged history. #850, #851, #840, #852 and #853 are present; #856 is the following documentation checkpoint. #848 and #849 precede this wave and remain completed.
- [x] Exercise the Vitest lesson on the actual Vitest 5.0.0 lockfile with Node 22.23.2, isolated from the primary checkout's stale installed Vitest 4.1.11. The six handled `vi.fn` cases fail; corresponding six plain-function controls pass. Removing call-argument matchers independently leaves the same six failures. Deliberately uncaught errors fail both implementations. The dated [lesson verification](../lessons/test-vitest4-mock-error-tracking.md) retains the workaround without asserting an unverified runner-internals explanation.
- [x] Exercise signed-in production PDF export of the existing Apple filing 3 summary. Native Chrome accessibility control worked after the extension control timed out. Two export activations downloaded PDFs; no generation, job, payment, email or account-setting action was invoked. The route `backend/app/routers/summaries.py:536` reads the stored summary and passes it to WeasyPrint; it does not call the AI provider.
- [x] Inspect all five rendered A4 pages of the downloaded PDF: title/source, all nine summary sections, repeated table headers, page numbering and final disclaimer are present. No clipped text, missing glyphs, blank page or overlapping table was found. PDF metadata identifies **WeasyPrint 70.0**, PDF 1.7, 56,413 bytes. SHA-256: `40b2b0e2e9625ddd6f21dde76b2b2c053794bb3fae54642714ee101986e23418`. Local evidence is `outputs/resumption-2026-09-14/pdf/apple-production.pdf`, extracted text and five rendered page images in the enclosing workspace. This verifies one real portrait summary export, not every document or landscape Analysis export.
- [x] Production frontend smoke: landing page, existing Apple summary, filed calendar date, nine sections and export interaction work in the signed-in Chrome session. This is bounded acceptance, not a complete browser/device matrix or fresh Copilot evaluation.
- [x] Review the override gate against nested resolution, qualified keys, root development and optional dependency edges, plus its anti-vacuity assertion. No current backward override defect was demonstrated. Unsupported ranges/links and optional peers remain explicit limits, not proof of universal coverage.
- [x] Correct Node's declared support floor in [#859](https://github.com/neilmac91/EarningsNerd/pull/859): `>=22.22.2 <23`, existing gate strengthened, full frontend gate (640 tests/build) and negative/restored proof passed.

## Findings and refutations

**Should-fix — Node support declaration.** `frontend/package.json` declares `22.x`, admitting Node 22.10/22.14 although the locked jsdom 30 requires at least 22.22.2 in that major. A contributor following that declaration can install an unsupported test runtime. Refutation 1: inspect `.nvmrc` and CI, both already 22.23.2; that protects CI but not the advertised range. Refutation 2: inspect the locked jsdom/Vitest engines and named contract inventory; the dependency floor is real and `nodeVersionLockstep.spec.ts` is an ordinary gate, not a founder-locked anchor. Fix within Node 22; no new major approval is needed.

**Nit — stale prerequisite list.** September 14 handover section 5 repeats the effective Vercel Analysis flag and repository create/approve-PR setting as outstanding. Refutation 1: section 4 already says the flag was observed true. Refutation 2: September 8's dated CEO execution record in `tasks/todo.md` records both observations. Actual companyfacts warm-up/Pro acceptance and changed-membership publication evidence remain open. A dated correction below the historical handover preserves those distinctions. W3-8a also retains the governing more-than-one-week readout-slip exception; the key/readout is not an unconditional blocker for all breadth preparation.

**Existing quality concern, not a renderer regression.** The exported cached Apple summary says operating cash flow “declined from $110.5B ... to $111.5B ... a marginal increase.” Refutation 1: the exact contradictory sentence is also visible in the web summary. Refutation 2: the export route only renders stored structured text, with no numerical recomputation or generation. The PDF correctly preserves the existing content; successful rendering does not establish world-class analysis. Historical cache repair/replay remains separately held, and this review does not regenerate the example.

The Vitest-staleness hypothesis was refuted by the actual versioned experiments, rather than by the full existing suite. The PDF-breakage hypothesis was refuted for this real export by successful download, producer metadata, text extraction and all-page visual inspection. The six dev-only Lighthouse findings remain a prior measured audit result: locked Lighthouse versions were unchanged by #852, but this review did not rerun a live advisory audit or claim a new count. jsdom isolation overhead has no demonstrated correctness failure; no thread/isolation optimization is warranted in this correction.

## Experiment evidence

Workspace logs: `outputs/vitest5-handled-probe.log`, `vitest5-plain-probe.log`, `vitest5-no-call-matcher-probe.log`, `vitest5-uncaught-probe.log`. Isolated committed probes were `f8f38223`, `3d628a72`, `340cb599`; these are local experiment commits, not released code. The published change contains only dated documentation. Exact tails, respectively:

```text
Test Files  1 failed | 1 passed (2)
     Tests  6 failed | 3 passed | 1 skipped (10)

Test Files  1 passed (1)
     Tests  6 passed | 1 skipped (7)

Test Files  1 failed (1)
     Tests  6 failed | 1 skipped (7)

Test Files  2 failed (2)
     Tests  2 failed | 12 skipped (14)
```

## Scheduled prerequisite checked without dispatch

The September 14 scheduled [weekly run 34880067441](https://github.com/neilmac91/EarningsNerd/actions/runs/34880067441) completed with measurement failure and a retained `weekly-judged-readout-34880067441` artifact. `readout.json` says `status=unavailable`, `expected=24`, `completed=0`, `scored=0`, `missing=24`, reason: “Generator or strong-judge credential absent; no model calls made.” This supersedes the handover's September 7 latest-observation date, not the outstanding readout requirement. The artifact does not distinguish which credential is absent. Its report job completed separately; successful report delivery is not successful judging. Codex only downloaded existing evidence and did not dispatch either job.

## Next order and unchanged boundaries

With the Node floor correction completed in #859, continue unblocked quality and read-only operational evidence work from the existing master plan. The Notable review week runs through September 15; do not request an early retain/kill decision. W3-7 still needs a usable prescribed strong-judge readout and later arm decision. Analysis needs actual warm-up and Pro acceptance evidence. E09 remains an inventory/proposal; E06 needs natural delivery attribution. D8, #270, future dependency majors, #805, historical replay and universe-wide pregeneration retain their respective holds. Earlier specific dependency approvals have been consumed. No fresh clarification is required for the two completed checks or the Node 22 correction.

## Later September 14 closure evidence

Review-record PR #858 merged as `e245afc9762a0d3603073d7f4ec276f2622d95a8`; main CI 34883074560 passed. The primary checkout's dependencies were then restored with `npm ci` on Node 22.23.2. A fresh npm audit now independently reports six high-severity package entries, all marked development-only in the lockfile; `npm audit --omit=dev` reports zero. The chain is Lighthouse/puppeteer/browser download/extract-zip, with two extract-zip advisories. This current audit reports no complete available fix; the earlier blanket suggestion that a breaking Lighthouse upgrade resolves it is not established. No forced update or major approval was requested. Local JSON evidence is in `outputs/resumption-2026-09-14/npm-audit*.json`.

The Node PR's requested review identified the still-open task-list entry. Two refutations failed: historical wording should be retained, but it still needs a dated completion correction; the current resumption checklist also remained unchecked. #859 adds the correction beneath the prior record and completes the current checklist. The full gate ran on committed code `aae93fc2bdde5dd5e5d2df1d5b096f5e06091f5f`; the subsequent current-main merge and task corrections leave the entire frontend and CI workflow trees identical. The documentation delta receives link checks, not another unchanged application suite.
