# prompt_loader caches at import; re-verify one golden entry by its pinned accession, not the full builder

**Area:** ai-evals · **Date:** 2026-06-30

- `prompt_loader` caches prompts at import, so editing a prompt file mid-run is safe for an in-flight
  eval (it uses the cached copy); the candidate/after run picks up edits via a fresh process.
- The golden-set builder re-resolves each entry to the *latest* filing (drift). To re-verify ONE
  entry after an extraction fix, re-extract by its PINNED accession — don't run the full builder.
