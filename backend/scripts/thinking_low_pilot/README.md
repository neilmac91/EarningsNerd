# Fresh paired thinking-low diagnostic

This task-local capsule compares the frozen candidate-r writer with thinking disabled and
thinking set to `low`. It is diagnostic evidence, not a release gate, a replay of the historical
r requests, or a repair of the failed p/r source-provenance comparison.

The pilot job exists only on `codex/wave3-thinking-low-pilot`. It checks the capsule from that
branch and separately checks out candidate-r at `47d040aa53e89d2e1fa78c26ee688d5a49338133`.
The offline preflight requires that subject checkout, tree, and selected files to match the
manifest before any provider step can run.

Each manual dispatch runs one control followed by one thinking-low output. The first dispatch
must select `RIVN-10-K-run0`, use `FIRST`, and leave all prior-state fields blank. A later dispatch
must follow `manifest.json`'s pair order and provide the exact prior successful run ID, the
downloaded continuation hash, both operator-reviewed output hashes, and `PASS`. The prior ledger and
all output receipts are copied forward and hash checked. A failed or pending call is never redrawn.
Workflow reruns are rejected, and each continuation must name the immediately preceding dispatch
on the same frozen workflow commit; a sibling dispatch cannot restart or fork the ledger.

Before every dispatch, the operator must recheck the official price and pass its UTC observation
time. The durable meter refuses the documented weekday peak windows and reserves cache-miss input
plus the full declared output ceiling before each physical SDK attempt. Across the entire carried
ledger it permits at most 20 calls and USD 0.95 of conservative reservations; errors, retries, and
unknown usage receive no refund. The workflow maps only the Actions `DEEPSEEK_API_KEY` secret to
the application's `OPENAI_API_KEY` name and never writes the credential to evidence.

The intended order is eight reviewed pairs (four retained filings, two draws). The operator stops
after any confirmed targeted material failure. Continuing after a pair always requires reviewing
its payloads and retained meter first. Outputs can diagnose whether low thinking merits a larger
measured comparison; they do not satisfy the programme's 70-output or independent-judge admission
criteria.

Offline preflight from a dependency-ready Python 3.11 environment:

```bash
python backend/scripts/thinking_low_pilot/preflight.py \
  --repo /path/to/clean/candidate-r-at-47d040aa \
  --receipt /tmp/thinking-low-preflight.json
```

No local command in this capsule reads a provider credential or invokes the pilot. Only an
explicit manual workflow dispatch reaches the provider.
