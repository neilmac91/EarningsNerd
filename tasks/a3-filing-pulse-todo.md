# A3 — Filing Pulse (calm, sourced sentiment) — Implementation Todo

Implements the **NEXT / A3** item from `docs/competitive-strategy-roadmap-2026.md`: present the
multi-signal buzz the pipeline already computes as a calm, transparent, source-attributed gauge —
the deliberate opposite of the Stocktwits 1–100 hype meter / red-green "casino" aesthetic.

## Design decisions
- **Reuse existing signals, no new data.** `hot_filings.py` already computes an 8-component
  `buzz_components` dict + composite score (recency, reader interest, filing cadence, earnings
  proximity, news volume/headlines/sentiment). A3 *composes* these into a calm view — pure logic,
  no new external API calls, fully unit-testable.
- **Calm over casino (brand D3).** Replaced the flame icon / `animate-pulse` / orange→red gradient /
  "On Fire" UI with a muted mint/slate gauge, a qualitative tier ("Quiet / On the radar / Active /
  Elevated"), and a labelled, source-attributed breakdown ("Recently filed · 50%", with the data
  source in the tooltip). No precise hype number on display.
- **Transparent provenance.** Each driving signal shows its human label, share-of-total, and source
  (EDGAR / EarningsNerd / FMP / Finnhub) — consistent with the Trace-to-Source brand.
- Additive + tolerant: composition handles missing/zero/malformed input and degrades to "Quiet".

## Backend
- [x] `app/services/pulse_service.py`: `pulse_tier()` + `compose_pulse(buzz_components, buzz_score)`
      → `{score, tier, has_signal, components[]}` (active signals only, sorted, with share %).
- [x] `routers/hot_filings.py`: enrich every filing in the response with `pulse` (ranked + fallback).
- [x] `tests/unit/test_pulse_service.py` (7 tests).

## Frontend
- [x] `components/FilingPulse.tsx`: reusable calm gauge (muted palette, accessible `role="img"` label,
      top-3 driving signals with share %).
- [x] `components/HotFilings.tsx`: swap the casino buzz block for `<FilingPulse>`; flame→Activity icon,
      mint accents; all data/links/refresh/analytics behavior preserved.
- [x] `tests/unit/filing-pulse.spec.tsx` (5 tests).

## Verify
- [x] backend: `pytest tests/unit/test_pulse_service.py` → 7 passed; ruff clean; router `py_compile` ok.
- [x] frontend: `vitest filing-pulse` → 5 passed; `eslint --max-warnings 0` + `tsc` clean.

## Follow-ups (not in this slice)
- Per-filing / per-company on-demand Pulse (needs live signal fetch for an arbitrary ticker → external
  API keys). 
- `SentimentSnapshot` persistence (roadmap B4) to chart the Pulse trend over time.
