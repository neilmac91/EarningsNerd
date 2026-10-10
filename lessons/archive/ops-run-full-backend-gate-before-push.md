# Run the full local gate (ruff + bandit + pytest) before any backend push

Date: 2026-06-16   Area: ops

**Context**: The backend-tests CI job runs bandit as a gate. Local verification was ruff + pytest only, so a legitimate `hashlib.sha1()` call (required by the HIBP k-anonymity protocol) tripped bandit and failed CI on the first push.

**Rule**: Before pushing backend changes, run `ruff check .` AND `bandit -r app -ll` AND `pytest` — not just ruff + pytest. For intentional weak-hash use (SHA-1/MD5 required by an external protocol), pass `usedforsecurity=False`.

**Evidence**: `backend-tests` CI job runs `bandit -r app -ll`; `hashlib.sha1()` tripped bandit B324 (weak hash, High); fix was `usedforsecurity=False` (bandit's own suggested remedy).
