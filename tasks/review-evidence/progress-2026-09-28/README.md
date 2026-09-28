# September 28 execution evidence

The retained monthly SQL export from run `36349655416` passed an [isolated local import](logical-import-outcome.json). Its full 4,848,767 bytes matched the retained provider MD5 and CRC32C; the gzip stream validated and its SHA-256 is retained. The remote generation and checksums remained unchanged.

A first stock PostgreSQL 15 import stopped on a missing owner role. A separate pristine database with one local `NOLOGIN` placeholder then imported the **unchanged** SQL successfully with `psql -X -v ON_ERROR_STOP=1`. The dump identifies PostgreSQL 15.19; the local client/server were 15.15. All 33 ORM tables were present and readable, all 40 migration filename/hash pairs matched the export-head schema, core tables were nonempty, and the bounded orphan, filing-identity, invalid-index and unvalidated-constraint checks returned zero. This did not run application startup or migrations against the restored data.

The local cluster, downloaded SQL gzip and private logs were removed after aggregate evidence and log hashes were retained. No production database connection, new export, cloud instance or model call was needed. The two downloads remained under a USD 0.10 planning ceiling; invoice cost is unknown. An initial sandbox shared-memory failure occurred before any SQL import and is retained separately.

This establishes local importability with an owner-role prerequisite. It does not prove managed Cloud SQL import permissions/connectivity, source trigger/function completeness, collation parity, current-live row parity, a recovery-time guarantee, the natural monthly trigger, or the product-quality gates. The existing [PITR drill](../progress-2026-09-27/recovery-outcome.json) remains separate evidence.
