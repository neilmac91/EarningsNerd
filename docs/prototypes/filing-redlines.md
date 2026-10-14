# Filing redlines prototype

This local research prototype compares exact paragraphs in two original 10-K filings and turns their changed passages into a source-bounded review task. It is hidden by default, including direct navigation. It does not appear in product navigation.

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
npx vitest run tests/unit/filing-redlines.spec.tsx tests/unit/filing-redlines-route.spec.tsx tests/unit/compareParagraphs.spec.ts tests/unit/filing-content-api.spec.ts
```

## Real and illustrative behavior

- **Real:** existing filing metadata and cached-content GET endpoints; pair validation and strict returned-text filing identity; bounded deterministic paragraph matching; original-document links from the returned filing metadata; missing-content, incompatible-pair and failed-read states; stale-response suppression; literal search, per-occurrence review labels and a complete JSON review receipt.
- **Illustrative:** the initial Harbor Vale Industries text and metadata are invented. They make no claim about a real issuer and have no SEC links.
- **Not implemented:** whole-filing or Item 1A extraction, section alignment, semantic or word-level changes, materiality assessment, AI summaries, monitoring, alerts, server persistence, receipt import, billing or paywalls.

The comparator ignores whitespace within paragraphs and paragraph order for matching while honoring duplicate counts. It preserves displayed paragraphs as supplied, trimming only their outer whitespace. A modified paragraph appears once as removed and once as added; the columns are independent lists, not paired edits. It refuses empty text or an input over 120,000 characters or 400 paragraphs. In practice a cached 10-K's markdown runs well past 120,000 characters, and a table arrives as consecutive lines (one paragraph per table), so **Cached filings** mode abstains on most real filings at these bounds: plan the demand test around the fictional example, not the cached mode. Missing text is unavailable, never evidence of no changes. Available cached text does not establish complete filing coverage.

## Review workflow and portable receipt

Search is a case-insensitive literal substring search, with separate shown/total counts for additions and removals. An empty filtered view never means the filings have no changes. Each occurrence, including duplicate paragraphs, can be Unreviewed, Reviewed or Needs follow-up. Only Reviewed reduces the remaining count; these are user tracking labels, not source verification or materiality judgments.

Search and labels live in browser memory and reset when inputs or source mode change, a comparison reloads (including a failed reload), or the page reloads. Download all changes (JSON) produces a local snapshot containing every changed occurrence, even those hidden by search, its exact displayed text and review label, both sources' filing IDs/accessions/dates/URLs, an export timestamp, fictional marker, comparison method and coverage limits. It omits matched text and makes no whole-filing coverage claim. There is no server audit record or saved work after leaving the page. Fictional sources retain null IDs and URLs.

The scope was revised after public competitor inspection on 2026-10-11: [BamSEC's comparison guide](https://help.bamsec.com/hc/en-us/articles/45647034214163-Compare-Filings), [Diffchecker](https://www.diffchecker.com/) and [Draftable text comparison](https://www.draftable.com/compare-text) establish comparison and review-navigation workflows. The product hypothesis is that source context, review completion and portable evidence matter beyond a bare diff. These are independently implemented interaction ideas; no competitor code, design assets or proprietary algorithms were copied. Public inspection does not establish their complete paid functionality or customer willingness to pay.

## Browser checks

The browser spec uses local API fixtures, including the actual ISO timestamp response shape; it does not prove production cache coverage. With the local server running as above, run from `frontend/`:

```sh
NEXT_PUBLIC_ENABLE_FILING_REDLINES=true npx playwright test tests/e2e/filing-redlines.spec.ts
```

It exercises the example, cached comparison, source links, literal HTML display, focus during a pending request, duplicate submission, search, review labels, a complete downloaded receipt under a filter, and missing-text/reset states at desktop/mobile widths in both themes. To verify default-off HTTP 404 separately, stop the enabled server, restart/build with the flag unset, and run the same spec with the test process flag unset. The positive-flow cases skip in that mode, and the 404 case skips in enabled mode.

No dependencies were added or updated. Existing React, Next.js, shared UI and Axios dependencies are reused under their MIT licences; the comparator is application code. Preserve the existing third-party notices. No commercial data or model weights are introduced.

Before production, validate extraction coverage and provenance, choose complete supported sections, test representative filing pairs and amendments, confirm demand with beta users, and review performance and accessibility across the full workflow. There are no production migrations, environment updates, paid services or new secrets in this prototype. The only new setting is the default-off public flag `NEXT_PUBLIC_ENABLE_FILING_REDLINES`.
