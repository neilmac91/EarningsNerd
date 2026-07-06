# A test outside the CI collection path gives zero coverage and has rotted — run it isolated before 'adopting'

**Area:** testing · **Date:** 2026-07-05

A plan item said to "adopt" 6 repo-root `/tests/` files into the CI-collected suite. All 6 were in
fact bit-rotted — they had never been collected (CI runs `cd backend && pytest`, so a repo-root
`/tests/` is invisible), so nothing kept them honest: one tested a class deleted in a refactor
(`XBRLService._parse_xbrl_xml`), the rest failed current validation (a 15-char `SECRET_KEY` vs the
≥32 rule) and polluted global state (module-level `dependency_overrides`, `importlib.reload` of
config). "Adopting" them would have meant rewriting them.

**Rule:** a test outside the CI collection path provides ZERO coverage and has almost certainly
rotted. Before "adopting" one, run it in isolation AND in-suite; if it fails or pollutes, treat it
as dead (delete — git preserves it) or a fresh rewrite. Don't assume a plan's "adopt" framing
survives contact with the code; deleting an uncollected test loses no coverage.
