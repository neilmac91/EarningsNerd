# Identify the feature a browser smoke is meant to verify

Date: 2026-09-06   Area: test

**Context**: The first scheduled-workflow dispatch loaded the production summary, then failed
because a case-insensitive button-name locator matched both a callout CTA and the Copilot
dialog launcher. The visible feature existed; Playwright rejected the ambiguous locator.

**Rule**: Keep the existing feature assertion, but identify its target with accessible name
and distinguishing semantics. Do not select an arbitrary first match. Verify that a similar
CTA cannot satisfy the smoke when the actual launcher is absent. Feature presence alone does
not identify the deployed commit or prove the cause of a missing feature.

**Evidence**: Production run `34002187563`, issue #712, and
`frontend/tests/e2e/prod-smoke.spec.ts`. The existing smoke requires the exact launcher name
and `aria-haspopup="dialog"`; a private two-button fixture passes and removing the launcher
must fail its unchanged visibility assertion.
