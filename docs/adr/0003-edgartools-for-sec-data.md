# ADR 0003 — Consolidate SEC data access on `edgartools`

- **Status:** Accepted
- **Deciders:** EarningsNerd maintainers
- **Related:** issue #244

## Context

Pulling filings from SEC EDGAR and extracting XBRL financials originally leaned on two
separate libraries:

- **`sec-edgar-downloader`** — for fetching filing documents, and
- **`arelle-release`** — for XBRL parsing.

This split had real costs:

- Two dependencies, two failure modes, and two mental models for one logical concern
  ("get filing text + structured financials").
- `arelle` is a heavyweight XBRL toolkit; we used a small slice of it.
- Glue code was needed to stitch downloaded documents to parsed XBRL facts.

## Decision

Standardize on **[`edgartools`](https://pypi.org/project/edgartools/)** as the single SEC
integration library, covering both filing retrieval and XBRL extraction. (The floor at decision
time was `>=5.12.0`; it has since advanced to `>=5.40.1` in `requirements.in`, with the lockfile
`requirements.txt` pinning `edgartools==5.40.1`.)

- All SEC access goes through `backend/app/services/edgar/` (client, XBRL service, circuit
  breaker, async executor, compat layer).
- `edgartools` calls are wrapped by a dedicated thread-pool async executor
  (`edgar/async_executor.py`), a token-bucket rate limiter for SEC's ~10 req/s limit, and a
  circuit breaker so SEC outages fail fast without cascading.
- `arelle-release` and `sec-edgar-downloader` were **removed** from `requirements.in` after
  verifying zero remaining imports (issue #244).

## Consequences

**Positive**
- One library, one mental model, one set of failure modes for SEC data.
- Filing text and XBRL facts come from a consistent source, simplifying the extraction →
  validation → quality → write pipeline.
- Smaller, better-aligned dependency surface.

**Negative / costs**
- A hard dependency on `edgartools` tracking SEC EDGAR's format and endpoint changes; we
  pin a tested floor (currently `>=5.40.1`, resolved to `==5.40.1` in the lockfile) rather than
  chasing latest.
- `edgartools` is synchronous, so it must run inside the dedicated thread pool
  (`edgar/config.py: EDGAR_THREAD_POOL_SIZE`) to avoid blocking the event loop — a pattern
  contributors must follow for any new SEC call.
