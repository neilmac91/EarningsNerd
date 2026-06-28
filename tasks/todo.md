# Task: Unify company-search dropdown styles

## Problem
The main-page search dropdown (`CompanySearch.tsx`) rendered results in two
divergent visual styles during a single search:
- "Instant local matches" block (sage ticker + muted name + "instant" badge),
  seeded from a static `TOP_TICKERS` list — no price/change data possible.
- "Search Results" block (network) — name + ticker + price + daily gain/loss.
They appeared in sequence, reading as two design languages = "amateur/buggy".

## Decision (from user)
- DROP the instant-matches block entirely (one consistent style).
- Scope: CompanySearch only (leave WatchlistAddSearch alone).
- Function over design — keep the already-correct, theme-aware network row.

## Plan
- [x] Remove instant-matches JSX block from `CompanySearch.tsx`
- [x] Remove supporting machinery (`localMatches`, `showLocalResults`, simplify
      `navigableTickers` to network results) + the `matchTopTickers` import
- [x] Delete now-orphaned `lib/topTickers.ts` and update its CLAUDE.md reference
- [x] Add focused Vitest regression test for the single unified row
- [x] Verify: lint (max-warnings 0), typecheck, vitest, next build
- [ ] Commit + push + open draft PR

## Review
- The dropdown now has a SINGLE rendering path: the theme-aware network
  "Search Results" block (name + ticker + price + daily gain/loss). The
  divergent instant-local-matches block (sage ticker + muted name + "instant"
  badge) is gone, so no second style can appear during a search.
- `lib/topTickers.ts` was used only by that block, so it was deleted (dead code);
  its one CLAUDE.md reference was updated.
- Verification:
  - `eslint . --max-warnings 0` → clean
  - `tsc --noEmit` (tsconfig.ci.json) → clean
  - `vitest run` → 47 files / 215 tests pass (incl. new `CompanySearch.test.tsx`)
  - `next build` → succeeds
  - Rendered the real homepage via Playwright with the search API mocked and
    screenshotted the dropdown in BOTH themes — one consistent, theme-aware
    style; gain green / loss red; "Loading price…" placeholder for quote-less
    rows; no "instant" badge.
- Deploy note: the deployed `origin/main` ran an older single dark-only block;
  this branch already carried the two-block version. Collapsing to one block
  fixes the inconsistency regardless of which generation prod runs; takes effect
  on merge + deploy.
