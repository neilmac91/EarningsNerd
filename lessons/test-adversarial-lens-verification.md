# Verify large mechanical changes with independent adversarial lenses, not one review pass

Date: 2026-07-06   Area: test

**Context**: The F3 mass move (components/ → features/, ~50 components) was verified by
three independent passes, each hunting a different failure mode: (1) classification — is
each file in the RIGHT domain, (2) completeness — did anything get left behind or
double-homed, (3) stale references — do any old paths survive anywhere (docs, mocks,
dynamic imports). The classification lens caught two real misclassifications a single
review had waved through — most memorably `PerAdsNote`, filed under "marketing" because
the name reads as advertising when it actually means Per-ADS (American Depositary Share),
a financial note whose importers are the summary financials tree. Redundant identical
reviews would not have caught it; a differently-aimed lens did.

**Rule**: For any change too large to hold in one head (mass moves, renames, deletions),
run separate verification passes with DIFFERENT failure-mode briefs (classification /
completeness / stale-refs at minimum). Each lens must be free to contradict the work,
and its findings get fixed before merge — not explained away.

**Evidence**: PR #559 (F3) — lens 1 caught `PerAdsNote` marketing→filings and
`TrendingTickers` filings→companies; lenses 2–3 came back clean and said so explicitly.
