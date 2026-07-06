# Verify orphaned or uncollected tests before adopting them

Date: 2026-07-05   Area: test

**Context**: A plan item said to "adopt" 6 repo-root `/tests/` files into the CI-collected suite. All 6 were bit-rotted — never collected (CI runs `cd backend && pytest`, so a repo-root `/tests/` is invisible): one tested a class deleted in a refactor, the rest failed current validation and polluted global state. Note: the dual test dirs themselves were eliminated by this consolidation (the repo-root `/tests/` no longer exists), but the rule generalizes to any future uncollected test, so the lesson stands.

**Rule**: A test outside the CI collection path provides ZERO coverage and has almost certainly rotted. Before "adopting" one, run it in isolation AND in-suite; if it fails or pollutes, treat it as dead (delete — git preserves it) or a fresh rewrite. Don't assume a plan's "adopt" framing survives contact with the code; deleting an uncollected test loses no coverage.

**Evidence**: Repo-root `/tests/` invisible to `cd backend && pytest`; one tested deleted `XBRLService._parse_xbrl_xml`; 15-char `SECRET_KEY` vs the ≥32 rule; module-level `dependency_overrides`, `importlib.reload` of config.
