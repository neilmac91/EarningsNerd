# Current-main sameness captures

Captured on 2026-10-23 from main `5897d602`, after #1457 (`ab6962ec`) and E120 (#1495).
This set supports [the rescore](../../09-stress-test.md#2-the-sameness-test-rerun), not a claim
that every sweep surface has been tested again. No application code changed for the captures.

The local production build uses Node 22.22.2, Next 16.4.2 and webpack, a fresh `npm ci` from the
lockfile, and CI's e2e flags: the API base is `http://localhost:8000`, waitlist mode is false,
and analysis, calendar, calendar fixtures and full-text search are enabled. `next start` serves
port 3000 with no backend. Chromium 151.0.7922.173 is preinstalled. Each context has reduced
motion, blocked service workers and a theme saved before navigation. Company marks fall back
to their text avatars because external browser requests are blocked.

Eight routes each have eight profiles: 390x900 and 1440x900, light and dark, 100% and 200% text.
The enlarged setting is Chromium's `Page.setFontSizes` (standard 32, fixed 26), with the computed
root confirmed as 32px; the default root is 16px. Enlarged captures are viewport screenshots,
not full-page screenshots, which can reset that setting. Filenames use
`<surface>-<theme>-<width>-<text-percent>-<view>.jpg`; every JPEG is the browser's screenshot.

| Surface | Route | Light, 390px | Dark, 390px | Light, 1440px | Dark, 1440px |
|---|---|---|---|---|---|
| Home | `/` | [100%](home-light-390-100-fold.jpg), [200%](home-light-390-200-fold.jpg) | [100%](home-dark-390-100-fold.jpg), [200%](home-dark-390-200-fold.jpg) | [100%](home-light-1440-100-fold.jpg), [200%](home-light-1440-200-fold.jpg) | [100%](home-dark-1440-100-fold.jpg), [200%](home-dark-1440-200-fold.jpg) |
| Waitlist | `/waitlist` | [100%](waitlist-light-390-100-fold.jpg), [200%](waitlist-light-390-200-fold.jpg) | [100%](waitlist-dark-390-100-fold.jpg), [200%](waitlist-dark-390-200-fold.jpg) | [100%](waitlist-light-1440-100-fold.jpg), [200%](waitlist-light-1440-200-fold.jpg) | [100%](waitlist-dark-1440-100-fold.jpg), [200%](waitlist-dark-1440-200-fold.jpg) |
| Auth shell | `/login` | [100%](login-light-390-100-fold.jpg), [200%](login-light-390-200-fold.jpg) | [100%](login-dark-390-100-fold.jpg), [200%](login-dark-390-200-fold.jpg) | [100%](login-light-1440-100-fold.jpg), [200%](login-light-1440-200-fold.jpg) | [100%](login-dark-1440-100-fold.jpg), [200%](login-dark-1440-200-fold.jpg) |
| Pricing | `/pricing` | [100%](pricing-light-390-100-fold.jpg), [200%](pricing-light-390-200-fold.jpg) | [100%](pricing-dark-390-100-fold.jpg), [200%](pricing-dark-390-200-fold.jpg) | [100%](pricing-light-1440-100-fold.jpg), [200%](pricing-light-1440-200-fold.jpg) | [100%](pricing-dark-1440-100-fold.jpg), [200%](pricing-dark-1440-200-fold.jpg) |
| Analysis teaser | `/analysis` | [100%](analysis-light-390-100-fold.jpg), [200%](analysis-light-390-200-fold.jpg) | [100%](analysis-dark-390-100-fold.jpg), [200%](analysis-dark-390-200-fold.jpg) | [100%](analysis-light-1440-100-fold.jpg), [200%](analysis-light-1440-200-fold.jpg) | [100%](analysis-dark-1440-100-fold.jpg), [200%](analysis-dark-1440-200-fold.jpg) |
| 404 | `/no-such-page` | [100%](not-found-light-390-100-fold.jpg), [200%](not-found-light-390-200-fold.jpg) | [100%](not-found-dark-390-100-fold.jpg), [200%](not-found-dark-390-200-fold.jpg) | [100%](not-found-light-1440-100-fold.jpg), [200%](not-found-light-1440-200-fold.jpg) | [100%](not-found-dark-1440-100-fold.jpg), [200%](not-found-dark-1440-200-fold.jpg) |
| Company | `/company/AAPL` | [100%](company-light-390-100-fold.jpg), [200%](company-light-390-200-fold.jpg) | [100%](company-dark-390-100-fold.jpg), [200%](company-dark-390-200-fold.jpg) | [100%](company-light-1440-100-fold.jpg), [200%](company-light-1440-200-fold.jpg) | [100%](company-dark-1440-100-fold.jpg), [200%](company-dark-1440-200-fold.jpg) |
| Filing | `/filing/3` | [100%](filing-light-390-100-fold.jpg), [200%](filing-light-390-200-fold.jpg) | [100%](filing-dark-390-100-fold.jpg), [200%](filing-dark-390-200-fold.jpg) | [100%](filing-light-1440-100-fold.jpg), [200%](filing-light-1440-200-fold.jpg) | [100%](filing-dark-1440-100-fold.jpg), [200%](filing-dark-1440-200-fold.jpg) |

The other 36 captures show the first landing row (`home-...-rows`, eight), Risks
(`filing-...-risks`, eight), the bounded teaser (`analysis-...-teaser`, eight), the first-visit
consent bar (`consent-...-fold`, eight), and default-size full homepages (`home-...-page`, four).
The consent contexts have no saved choice; no button or form is submitted.

The filing uses `tests/e2e/fixtures/filing-3-summary.json` and `filing-3-risks.json`; the company
uses the company/filings shapes in `tests/e2e/text-floors.spec.ts`. Browser `page.route` handlers
fulfil API requests from those fixtures, including a company comparison with no prior report;
the session check is 401. Every other API path receives a fixture 404 and every external browser
request is aborted. No production account, API or mail transport is used. The homepage's
server-rendered example is its checked fallback; Reporting this week and Notable filings omit
themselves with no backend. The waitlist example shows its unavailable state, so this run does
not establish its successful data state or a populated feed.

All 64 route measurements in [measurements.json](measurements.json) fit the document width and
log no uncaught page error. This is not a full accessibility or interaction audit. The phone is
emulated, the first-visit consent bar intentionally covers part of the page, and the analysis
preview is deliberately blurred and clipped. Exports, mail clients, small icons and production
feed contents retain their earlier evidence. [files.json](files.json) lists each screenshot's
size and SHA-256 so the set can be checked without treating a thumbnail as the original.
