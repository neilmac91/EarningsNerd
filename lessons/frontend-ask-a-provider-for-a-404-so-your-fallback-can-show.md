# Ask a third-party image provider for a 404 on a miss, or your own fallback never shows

Date: 2026-10-22 · Area: frontend / company marks

**Context.** `components/CompanyLogo.tsx` draws a sage initials monogram, swaps in Logo.dev's mark
on `load` and keeps the monogram on `error`. Logo.dev's CDN answers a ticker it has no logo for with
a generated placeholder at HTTP 200 unless the URL carries `fallback=404`, so `onError` never fired:
on the live site a company without a logo showed Logo.dev's grey letter (a "C" for Antelope
Enterprise, from a domain it guessed), never the site's "AE". The 2026-10 company-mark review found
it; the CDN had served 0 errors across 496 live slots, which read as reliability and was the
placeholder.

**Rule.** When a component draws its own fallback for a provider-served image, the request tells
the provider to answer a miss with an error status (`fallback=404` on Logo.dev; the equivalent flag
on the next provider), never with an image of its own. The unit spec fires `error` on the element
and finds the fallback, and asserts the request URL carries the flag. A mark that loads or fails before
React hydrates fires its event with nobody listening, so the component also reads `complete` and
`naturalWidth` on mount (next/image reads `complete` there too; it replays an error by resetting
`src`, where a PNG with no width reads as failed here).

The visual half of the check is `node frontend/scripts/capture-company-marks.mjs <url>`: a sheet per
theme and pixel ratio of every mark on a page, where a provider placeholder, a clipped tile or a
dark mark on a dark ground is seen in one glance.

**Evidence.** `frontend/components/CompanyLogo.tsx` (`logoDevUrl`, `onMount`);
`frontend/tests/unit/CompanyLogo.spec.tsx` ("keeps the monogram when the image fails", "asks the
CDN at the exact size … with a 404 for a missing logo", "shows a mark that finished loading before
React attached its listeners"); Logo.dev's CDN introduction, "Fallback images".
