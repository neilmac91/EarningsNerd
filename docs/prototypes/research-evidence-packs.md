# Research evidence packs prototype

This default-off prototype explores a narrower job than generic notes or citation export: reuse prior research without silently replacing its filing evidence or carrying an old interpretation forward as reviewed.

## Run locally

Use the repository's pinned Node 22 toolchain and the existing frontend dependencies. From `frontend/`:

```sh
WAITLIST_MODE=false NEXT_PUBLIC_ENABLE_RESEARCH_EVIDENCE_PACKS=true NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

Open `/labs/research-evidence-packs`. `WAITLIST_MODE=false` is an existing local setting: otherwise the global waitlist middleware redirects before the route's feature gate. With the prototype flag unset or any value other than `true`, the route returns 404. No navigation link is added, and indexing is disabled. Next embeds this public flag at build time; a production-mode local check must build with the same flag value before starting.

The fictional example works without a backend. Choose **Compare selected source** on the saved evidence, write a review note, then **Accept new revision** or **Keep prior source**. Editing the interpretation reopens review. The original source and previous review remain in the history.

To try actual cached data, run the existing backend locally, choose **Cached filings**, and enter the numeric ID from a local `/filing/{id}` URL. Load a filing, select a paragraph and save it as evidence. Load a later filing from the same company and form, then compare its selected paragraph against a saved item. The legacy markdown cache must already exist; this page never populates it or calls SEC directly.

Switching modes or refreshing resets this tab's workspace. Export Markdown or JSON first. These downloads preserve every source revision, current interpretation, review decision and pending proposal. There is no import or automatic trust in exported JSON.

## What is real

- Existing cached metadata/content APIs, requested filing-ID validation, original 10-K/10-Q metadata, accession-bound HTTPS SEC links and calendar-date validation.
- Exact paragraph selection from cached text; immutable source snapshots with the accession, form, dates, original link, paragraph ordinal and capture timestamp.
- Separate editable interpretations; explicit human review notes; append-only source revisions; retained candidates when a reader keeps prior evidence.
- User review never verifies the truth of a claim. Even an identical later excerpt reopens review. Changing an interpretation invalidates its prior reviewed state.
- Portable Markdown and JSON downloads via the existing shared download helper. Untrusted quotes and notes render as text and are escaped in Markdown.
- A strict opt-in identity mode on `fetchFilingContent`. Other callers retain its legacy behavior. This prototype rejects content responses that omit or mismatch the requested filing ID.
- Synchronous duplicate-request guard and stale-response invalidation when the input/mode changes or the component unmounts.

## What is illustrative or missing

Harbor Vale Instruments and both example filings are invented and explicitly labelled. Example source links do not exist. The prototype has no server persistence, accounts/permissions for saved packs, sharing, import, background monitoring, automatic passage alignment, LLMs, market data or billing.

Cached text is not an independently verified SEC copy; its extraction can omit tables or footnotes. The paragraph number identifies a block in that cache, not an SEC page, section or stable paragraph ID. Each document is bounded at 120,000 characters and 400 paragraphs; exceeding a bound refuses the whole load without truncation. Amendments and different forms cannot be compared in this prototype. A user manually chooses a later source; the app does not claim to detect every new filing or changed claim.

Before production: add owned persistence and access controls, robust source-content coverage and stable spans, amendment handling, background filing discovery through the existing SEC service, an explicit save/review lifecycle with better source browsing, export/import versioning, retention/deletion controls, accessibility and real cached-filing integration validation, beta-user demand testing and a deliberate flag rollout. No investment recommendation is generated.

## Verification

From `frontend/`:

```sh
npx vitest run tests/unit/evidenceLedger.spec.ts tests/unit/evidence-packs-route.spec.tsx tests/unit/filing-content-strict-identity.spec.ts tests/unit/research-evidence-packs.spec.tsx
npm run lint
npx tsc -p tsconfig.ci.json
npm run test -- --run
npm run build
```

`tests/e2e/research-evidence-packs.spec.ts` exercises the browser with fixture-only cached responses. Run it against an explicitly enabled local build/dev server, or against a default-off local build to assert the 404. It blocks external requests and does not establish production backend integration.

No new package dependencies, secrets, environment files, database changes, services or paid calls are introduced. The new variable is `NEXT_PUBLIC_ENABLE_RESEARCH_EVIDENCE_PACKS` (default off); the command above uses two existing variables only for the local process. Existing dependency licenses remain unchanged.
