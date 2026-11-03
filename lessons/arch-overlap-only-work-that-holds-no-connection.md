# Overlap a wait only with work that holds no pooled connection, and measure pool waits under load before shipping it

Date: 2026-11-03   Area: architecture / performance

**Context**: The summary-latency work moved two steps of a cold generation off the critical path
between the end of the XBRL fetch and the provider request. A local harness (the real app on
PostgreSQL 15, pinned to one CPU with production's four-slot pool, stubbed SEC and provider at
measured latencies) ran each ordering single-user and with four generations at once. Every ordering
cut single-user latency, but two of the three raised total pool-wait time under load (five runs
each; the unchanged code measured 9.6 s and 8.8 s in two sets):

- The statement-context parse started beside the excerpt build: 9.6 s → 24.8 s. The excerpt build
  holds a pooled connection through seconds of CPU, and on one vCPU the parse beside it stretched
  that hold.
- The XBRL write (xbrl_data and its facts) moved out of the enrichment join, with the parse after
  the excerpt build: 20.5 s. The write then landed on the provider start's charge write, two
  connections at once per run where the serial order used one after the other.
- The parse started after the run's own excerpt build, holding no connection, with the write left
  in the join: 10.3 s, within the baseline's spread. That is the one that shipped (single-user p50
  22.20 s → 21.66 s).

**Rule**: On this service (one vCPU, a four-slot pool), overlap a wait only with work that holds no
pooled connection, and never beside a unit that holds one through CPU work. Before shipping any
overlap or reorder in a request that uses the pool, measure pool waits under concurrency against
the baseline, because a single-user gain does not show this cost:
1. Run the app on PostgreSQL with `DB_POOL_SIZE=4`, `DB_MAX_OVERFLOW=0` and one CPU (`taskset -c 0`).
2. Time every `QueuePool` checkout by wrapping `engine.pool._do_get`, and count those over 1 ms.
3. Drive four requests at once, with external calls stubbed at their measured latencies.
4. Run five times on each build and compare the count and the total wait.

#1977's body describes the harness it used.

**Evidence**: `backend/app/services/summary_stages/enrichment.py` (`start_statement_context`, the
XBRL write's comment) and `backend/tests/unit/test_summary_enrichment_overlap.py`
(`test_the_statement_parse_waits_for_its_own_excerpt_build`,
`test_the_xbrl_write_finishes_before_the_provider_request`), with the harness and its numbers in
#1977's body. Other pool readers that hold a connection through CPU work remain review-checked
(E300 names the excerpt build's).
