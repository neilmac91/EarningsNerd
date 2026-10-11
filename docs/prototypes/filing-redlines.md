# Filing redlines prototype

This local research prototype compares exact paragraphs in two original 10-K filings. It is hidden by default, including direct navigation. It does not appear in product navigation.

## Run locally

Use the repository's pinned Node version (`frontend/.nvmrc`) and existing dependency setup. No new dependencies are introduced.

From `frontend/`, enable the flag for the local process only:

```sh
WAITLIST_MODE=false NEXT_PUBLIC_ENABLE_FILING_REDLINES=true NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

Open `http://localhost:3000/labs/filing-redlines`. The existing global waitlist gate must be disabled for this local process; otherwise it redirects `/labs` to the waitlist before the feature layout runs. The initial fictional example needs no backend. The standard app shell may perform its existing local API reads. Do not enable this flag or change the waitlist setting in production for the prototype.

For **Cached filings**, run the backend with the repository's existing local development setup. Enter the numeric IDs from two local `/filing/<id>` URLs. They must identify distinct original 10-Ks from the same company, with increasing report and filing dates. Both need existing `markdown_content` in the local database. This prototype does not generate missing content or fetch from SEC. Newer cached filings may have no legacy markdown and will report unavailable.

To check the feature is dark, keep `WAITLIST_MODE=false` locally and restart without `NEXT_PUBLIC_ENABLE_FILING_REDLINES`; direct navigation should return the application's not-found page. The global waitlist gate may otherwise redirect first. For a production-mode local build, supply both settings when building and starting, because Next.js inlines `NEXT_PUBLIC_*` flags.

Focused checks from `frontend/`:

```sh
npx vitest run tests/unit/filing-redlines.spec.tsx tests/unit/filing-redlines-route.spec.tsx tests/unit/compareParagraphs.spec.ts
```

## Real and illustrative behavior

- **Real:** existing filing metadata and cached-content GET endpoints; pair validation; bounded deterministic paragraph matching; original-document links from the returned filing metadata; missing-content, incompatible-pair and failed-read states; stale-response suppression.
- **Illustrative:** the initial Harbor Vale Industries text and metadata are invented. They make no claim about a real issuer and have no SEC links.
- **Not implemented:** whole-filing or Item 1A extraction, section alignment, semantic or word-level changes, materiality assessment, AI summaries, monitoring, alerts, persistence, exports, billing or paywalls.

The comparator ignores whitespace within paragraphs and paragraph order for matching while honoring duplicate counts. It preserves displayed paragraphs as supplied, trimming only their outer whitespace. A modified paragraph appears once as removed and once as added; the columns are independent lists, not paired edits. It refuses empty text or an input over 120,000 characters or 400 paragraphs. Missing text is unavailable, never evidence of no changes. Available cached text does not establish complete filing coverage.

## Browser checks

The browser spec uses local API fixtures, including the actual ISO timestamp response shape; it does not prove production cache coverage. With the local server running as above, run from `frontend/`:

```sh
NEXT_PUBLIC_ENABLE_FILING_REDLINES=true npx playwright test tests/e2e/filing-redlines.spec.ts
```

It exercises the example, cached comparison, source links, literal HTML display, focus during a pending request, duplicate submission, and missing-text state at desktop/mobile widths in both themes. To verify default-off HTTP 404 separately, stop the enabled server, restart/build with the flag unset, and run the same spec with the test process flag unset. The positive-flow cases skip in that mode, and the 404 case skips in enabled mode.

No dependencies were added or updated. Existing React, Next.js, shared UI and Axios dependencies are reused under their MIT licences; the comparator is application code. Preserve the existing third-party notices. No commercial data or model weights are introduced.

Before production, validate extraction coverage and provenance, choose complete supported sections, test representative filing pairs and amendments, confirm demand with beta users, and review performance and accessibility across the full workflow. There are no production migrations, environment updates, paid services or new secrets in this prototype. The only new setting is the default-off public flag `NEXT_PUBLIC_ENABLE_FILING_REDLINES`.
