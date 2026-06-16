# Lessons

## 2026-06-11 — Adjacent-line edits conflict on merge
While draining the dependabot queue: assumed PRs touching *different lines* of
`backend/requirements.txt` could merge back-to-back without conflicts. Wrong —
git's 3-way merge conflicts when hunks fall within ~3 lines of each other
(context window), not only on identical lines. PR #224 (pydantic, line 4)
conflicted after #222 (python-multipart, line 3) and #223 (email-validator,
line 6) merged.

**Rule:** treat any two PRs editing the same file within a few lines of each
other as conflicting; plan serial merge + rebase between them. Only file-level
disjoint PRs are safely parallel.

## 2026-06-16 — Backend CI runs bandit, not just ruff
The `backend-tests` CI job runs `bandit -r app -ll` as a gate. I verified locally with
ruff + pytest only, so a `hashlib.sha1()` call (legitimately required by the HIBP
k-anonymity protocol) tripped bandit B324 (weak hash, High) and failed CI on the first
push. Fix was `usedforsecurity=False` (bandit's own suggested remedy + semantically correct).

**Rule:** before pushing backend changes, run the full local gate — `ruff check .` AND
`bandit -r app -ll` AND `pytest` — not just ruff + pytest. For intentional weak-hash use
(SHA-1/MD5 required by an external protocol), pass `usedforsecurity=False`.

## 2026-06-16 — Verify against the actual code before "implementing" a plan item
While executing the auth/privacy plan I almost rebuilt analytics consent-gating, the
Privacy Policy, and the GDPR export/delete UI — all three already existed and were
well-built (`posthog-provider.tsx` gates on consent; `/privacy`; `/dashboard/settings`).
The audit/plan flagged them as gaps from a distance; the code said otherwise.

**Rule:** re-read the relevant files immediately before implementing any plan item, even
one the plan marked "missing". Confirm the gap is real before writing code — re-implementing
working code is wasted effort at best and a regression risk at worst.
