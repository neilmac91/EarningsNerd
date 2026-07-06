# Run the full backend gate (ruff + bandit + pytest) before every push, not just pytest

**Area:** ci · **Date:** 2026-06-16

The `backend-tests` CI job runs `bandit -r app -ll` as a gate. I verified locally with
ruff + pytest only, so a `hashlib.sha1()` call (legitimately required by the HIBP
k-anonymity protocol) tripped bandit B324 (weak hash, High) and failed CI on the first
push. Fix was `usedforsecurity=False` (bandit's own suggested remedy + semantically correct).

**Rule:** before pushing backend changes, run the full local gate — `ruff check .` AND
`bandit -r app -ll` AND `pytest` — not just ruff + pytest. For intentional weak-hash use
(SHA-1/MD5 required by an external protocol), pass `usedforsecurity=False`.
