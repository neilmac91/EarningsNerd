# When an integration is declared dead, sweep every consumer in the same pass

**Date:** 2026-07-06 · **Area:** architecture / integrations

**Context:** The earnings-calendar strategy work (2026-07-03) established with live verification
that FMP's legacy `/api/v3` API — every endpoint `fmp.py` calls — was dead for our account class,
and rewired the calendar surfaces off it. But FMP had two other consumers (`trending_service.py`,
`hot_filings.py`) that nobody enumerated, so for three more days the public homepage — by then a
Pro sales surface — served a hardcoded fallback with the internal error string
"Last error: No symbols passed FMP validation" rendered to end users, and the "Trending Filings"
scoring silently lost its earnings/news signals (Finnhub, also personal-use-only, was equally
tombstoned-in-fact). The keep/fix/kill review (PR #571, `tasks/homepage-sections-review-findings.md`)
found it by curling prod.

**Rule:** The moment an integration is declared dead, deprecated, or unlicensed, grep for ALL of
its importers (`grep -rn "integrations.<name>" backend/app/`) and either fix, hide, or tombstone
every consumer in the same PR — and land a machine gate (importer allowlist test) so no new consumer
can appear and the teardown can't be forgotten. A dead integration with a live consumer is a
user-visible incident waiting on a cache miss.

**Evidence:** `tasks/earnings-calendar-strategy.md` TL;DR item 1 (FMP death, 2026-07-03);
`tasks/homepage-sections-review-findings.md` §2 (prod symptoms, 2026-07-06);
`backend/tests/unit/test_dead_integrations_allowlist.py` (the gate);
`lessons/arch-structural-gates-over-prose-rules.md` (why the gate ships in the same PR).
