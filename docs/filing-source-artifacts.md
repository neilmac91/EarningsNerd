# Verified filing source artifacts

`FILING_SOURCE_ARTIFACTS_ENABLED=false` and an empty `FILING_SOURCE_ARTIFACTS_BUCKET` preserve the existing generation path. This feature prepares code for private primary/exhibit reuse; it provisions no bucket, IAM, lifecycle policy, schedule or backfill. It does not activate durable summary jobs or preparation caps.

For a new enabled-mode 10-K, 10-Q or 8-K generation (including amendments), the existing `stream_filing_summary` orchestrator loads or captures the exact filing's source before starting any model task. Completed summary reads still return immediately and do not backfill artifacts. 6-K and 20-F generation retain their existing paths.

## Source and commit contract

The internal identity binds filing ID, canonical CIK/accession, form, primary filename, schema and selection version. Only an exact canonical same-filing SEC archive URL is accepted. Primary bytes use the existing attachment transport and its shared SEC admission, pacing and cooldown controls. The existing 8-K selector chooses at most three same-accession exhibits; advertised-but-missing earnings attachments remain a failure.

A raw bundle records ordered primary/exhibit members, roles, identity-encoded entity-byte representation, byte lengths, SHA-256 values, MIME types and pinned private storage generations. These are entity bytes, not original network framing or UTF-8 re-encodings. An independent extraction record binds a raw bundle to decoder/grounding-extractor versions and the derived text hash/length. A decoder/extractor version change can reuse captured bytes; a selector change may require different membership and another source retrieval.

Each validated object uses a generated identity/content-hash key and a create-only upload. The adapter fully reads and hashes the pinned generation after a successful upload, a collision or an ambiguous acknowledgment. It never overwrites, lists, deletes or produces a public URL. Corrupt/missing stored data fails closed. The complete manifest and all members commit together only after object verification; extraction commit/readback follows deterministic grounding. Only then can the coordinator return a receipt. A pure check in `generation.generate`, before provider task creation, verifies the receipt against the run's exact identity and text. Finalization checks it again.

Concurrent captures converge on one unique capture identity. A loser re-reads and verifies the winner's bodies, rather than returning its candidate text. A lost SQL commit acknowledgment requires a fresh exact readback. Failed partial captures may leave purpose-tagged unreferenced objects; this patch implements no destructive reconciliation. The manifest, member and extraction store APIs are append-only, and every reuse recomputes/validates their hashes. Restrictive foreign keys prevent dropping referenced manifest rows. Operational retention must account for summary references before any deletion policy is approved.

## Ownership and bounds

| Boundary | Implemented bound |
| --- | --- |
| Source size | 32 MiB aggregate entity bytes, including primary plus at most three exhibits; sequential member retrieval and storage |
| Source preparation | One monotonic deadline capped at 30 seconds; no restart of the budget between capture, storage, grounding and commit/readback |
| Storage operation | At most 10 seconds including admission, spawn, SDK calls and IPC; further bounded by the source deadline |
| Storage concurrency | One active child per process; callers waiting for it consume their own deadlines |
| Object reconciliation | One upload attempt, at most one exact-object generation lookup after ambiguity, then full pinned verification; no mutation replay |
| SQL units | Short session-owning workers; PostgreSQL lock timeout 2 seconds and statement timeout 5 seconds; no connection/transaction held across SEC or storage I/O |

A storage child inherits the existing worker process group. The parent kills and reaps it on expiry/cancellation before releasing the permit. Linux parent-death signaling plus an expected-parent-PID check prevents it continuing after parent death, including death before signaling was armed. Unsupported signaling fails closed before ADC. No application environment is inherited; the child obtains its own ADC in the deployed environment, with its private request on stdin and bounded output on stdout. SDK output and exceptions are withheld. The SDK's checksum cleanup cannot delete objects: automatic checksum handling is disabled in favor of application SHA-256 verification, and the Blob delete method refuses locally.

The deadlines stop storage work by terminating its owned process. Kernel scheduling/reaping has no finite wall-clock guarantee. Existing CPU/SQL threads remain request-owned and are drained after cancellation; their cancellation is not physical thread termination. These caps are not production latency or throughput promises. Source bodies, IPC copies, SDK buffers and local parsers require a measured memory/concurrency envelope before activation.

## Excerpt and result publication

Artifact mode is snapshotted per generation. It bypasses legacy excerpt reuse and extracts a fresh private excerpt with `persist=False` and `reuse_stored=False`, including non-force runs. It never impersonates a forced regeneration. The existing finalizer atomically promotes the summary, safe source receipt, sections and matching excerpt/risk source. Failed, keep-better and losing INSERT paths preserve the served cache.

**E77 remains open.** The existing bounded enrichment join may drop the excerpt. In that case generation uses verified full text; a winning promotion clears the incompatible old excerpt and risk source in the same transaction. This can leave Copilot without a cached excerpt until a later successful replacement. This change does not resolve excerpt CPU capacity or authorize historical excerpt repair (E28).

`Summary.raw_summary.filing_source_provenance` exposes only opaque bundle/extraction IDs, hashes, representation/version fields and existing public filing provenance. Bucket names, object keys, storage generations, SDK metadata and credentials stay private. Storage failures have a closed internal reason set and map to the existing source-unavailable frame; a storage HTTP 429 must never be reported as a SEC rate-limit response.

## Compatibility and acceptance

Enabled mode deliberately rejects redirected/compressed primary responses, unsupported MIME/body formats, noncanonical URLs and over-budget bundles. The primary uses one physical attempt inside the source deadline, rather than the legacy decoded path's retry ladder. Existing durable source retry/cooldown semantics remain responsible for later attempts. Raw identity bytes and derived text have different hashes when decoding changes their representation.

Offline gates compare the actual legacy grounding with capture/reuse grounding for fixed synthetic 10-K/10-Q and 8-K primary/exhibit fixtures, including charset decoding. This establishes input parity for those fixtures, not semantic quality or SEC availability. Storage gates execute real local child IPC, cancellation and parent-death behavior while replacing cloud calls. The PostgreSQL home proves complete-manifest races, rollback invisibility, commit ambiguity, immutable extraction-version identity, migration replay, finalizer/cache atomicity and separate-process crash/restart behavior:

```sh
FILING_SOURCE_TEST_DATABASE_URL=<disposable-postgresql-15-dsn> \
python -m pytest -n 0 tests/integration/test_filing_source_transactions.py -q
```

Production activation requires a dedicated private bucket and narrowly scoped runtime access, connector/ADC and Linux ownership acceptance, actual conditional upload/pinned readback, measured source/parse memory and latency, daily admission/storage/request budgets, and explicit reference-aware retention/orphan policy. No live GCS durability, capacity or paid-provider quality claim follows from the offline tests. Retrieval of primary/exhibit artifacts does not remove XBRL or other independent SEC calls, and this feature alone does not close discovery-to-preparation or ready-notification delivery gaps.
