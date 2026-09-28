# Completed sibling filing reads: successor evidence

The specific-filing, recent-filings, content and fundamentals handlers can exhaust the four-slot synchronous pool before async dependency cleanup releases completed reads. Each now materializes its existing DTO or primitive payload inside `try` and synchronously closes the session in `finally`. Missing filings still return 404; empty content and fundamentals retain their response shapes.

Runtime and gate bytes were verified at `a92dff9edae4228268f69ef1b77883950f4ca118`, based exactly on PR1016 head `d4798aa219dc6578396d6195bfd457dcd827e3d6`. The company-list function remains byte-identical to that predecessor. No global dependency, pool setting, asynchronous SQL architecture, other router, response schema or locked test changed. The successor is local only, awaiting coordinator base reconciliation and hosted review/checks before serial release.

See [machine-readable proof](local-proof.json), [the shared regression](../../../backend/tests/unit/test_cached_filings_pool_lifetime.py), [the updated lesson](../../../lessons/ops-release-cached-filing-reads-before-yield.md), and [predecessor evidence](../filing-cache-session-2026-09-29/README.md).

## Refutations and actual HTTP evidence

Two fresh passes tried to disprove specific/recent starvation. The HTTP/dependency pass verified original `get_db` and `SessionLocal`, actual Uvicorn over a private Unix socket, separate client/server event loops and no request-start barrier. The source/lifetime pass searched for earlier cleanup or response work requiring a live session: both original handlers fully materialize eager-loaded filing DTOs, but leave closure to the synchronous generator dependency finalizer. Both passes upheld the finding.

Separate content/fundamentals passes reached the same result: actual traces identify their route query timeouts, not missing tables, external waits or ASGI-only scheduling. Content is a completed DTO; the fundamentals service creates a primitive dictionary before returning. Neither needs its session after return.

All four original sibling endpoints were measured with eight concurrent requests apiece. Each missed the unchanged 15-second client burst deadline; four completed-read leases remained held about 40 seconds. Independent PostgreSQL sampling observed four application clients idle in transaction. Specific/recent receipts were retained before this successor; additional content/fundamentals measurement used exactly 32 actual HTTP requests total: eight before and eight after each endpoint.

After the fix, content and fundamentals each returned 8/8 HTTP 200 responses. Local elapsed ranges were 28.156–39.378 ms and 35.014–46.565 ms; longest leases were 3.079 ms and 4.864 ms. The seeded existing filings had no cached content or fundamentals, and exact empty payloads were asserted. The shared CI gate additionally checks populated payloads and 404s. These local timings are not production SLOs.

Each actual-HTTP run used a new private PostgreSQL 15.15 cluster, synthetic data, non-superuser application role, pool 4/0/10 and Unix sockets. External sockets were blocked; no attempts or observer errors were observed. All HTTP servers and database clusters stopped. No production requests, paid calls, users or invitations occurred.

## Gate and committed mutation

The existing full-app burst regression now has ten parameterized cases across the five filing read surfaces, including nonempty/empty content and fundamentals and three missing-filing 404 cases. It still uses genuine dependency cleanup and a real four-slot QueuePool with a short test timeout. There is one shared completed-read rule and one mutation proof.

Exactly one mutation restored `filings.py` from the predecessor, removing all four successor closes while retaining the company-list fix. The company-list case remained green and all nine sibling cases failed. Exact committed bytes were restored:

```text
9 failed, 1 passed, 17 warnings in 12.30s
10 passed, 17 warnings in 8.98s
```

Full local gate on unchanged runtime bytes:

```text
ruff check .: All checks passed!
bandit -r app -ll: No issues identified. [zero medium/high severity findings]
python -m pytest -rs:
3817 passed, 39 skipped, 2 deselected, 40 warnings in 160.02s (0:02:40)
```

The 39 skipped tests need their separate opt-in PostgreSQL transaction databases. The two deselected performance tests are excluded by normal pytest configuration. They are not claimed as executed; the separate PostgreSQL endpoint measurements did run. No new invariant or unrelated gate was added.

## Review scope and limits

Correctness review traced successful, empty and missing paths before cleanup; fundamentals payloads contain no ORM objects. Rules-and-brief review preserves the predecessor scope and every locked contract. Tests-and-gates review binds one failing/restored mutation and the full gate to exact source hashes. Coordinating independent review and exact-head hosted clearance are still required.

This resolves demonstrated local read-session starvation, not production capacity admission. Fleet reserve, effective workers, rollout overlap, shared SEC egress/per-wire admission, representative production useful work and consenting-user readouts remain separate. Detailed private receipts are retained in the coordinating workspace under `outputs/overnight-2026-09-28/capacity/sibling-successor/`; sanitized result fields and hashes are committed here.
