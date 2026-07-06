# Exploit prompt-cache and pinned-accession ergonomics when iterating on evals

Date: 2026-06-30   Area: test

**Context**: Two eval-harness ergonomic facts that saved rework during eval iteration: prompt caching makes mid-run prompt edits safe for the in-flight run, and the golden-set builder's re-resolution drift means single-entry re-verification must go by pinned accession.

**Rule**: `prompt_loader` caches prompts at import, so editing a prompt file mid-run is safe for an in-flight eval (it uses the cached copy); the candidate/after run picks up edits via a fresh process. To re-verify ONE golden-set entry after an extraction fix, re-extract by its PINNED accession — don't run the full builder (it re-resolves each entry to the latest filing and drifts).

**Evidence**: `prompt_loader` caches prompts at import; the golden-set builder re-resolves each entry to the *latest* filing (drift).
