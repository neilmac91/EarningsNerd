# E7 prompt and attempt-history custody verification

Code commit `b79b936f9c9782f40ae91095625f384ba2696442`, based on verified main
`5554bc87495dbb76e70ab10e32236260936080e8`. This is an offline, non-admitting primitive;
no provider transport, production generation or acceptance decision uses it.

- Full gate: **3,729 passed, 40 warnings, 159.60s**, exit 0. Ruff and Bandit passed.
  PostgreSQL 15.15, isolated local port 55436, all four concurrency URLs set; performance included.
  The inherited post-suite asyncio logging teardown diagnostic is retained in the raw log.
- Ten single-fault proofs detected the intended faults (12 parametrized failed cases), with exact
  committed source bytes restored after each; **25 restored focused passes**. See
  [proof identities and tails](proofs/proof.json) and the retained runner/raw logs.
- All eleven locked test files are byte-identical to main; hashes and evidence-file digests are in
  [verification.json](verification.json).
- [Independent combined review](review-execution-independent.md) cleared the final file hashes.
  Its author made the narrow context-ID compatibility edit; the root engineer independently reviewed
  that edit and all combined source. Root also checked rules, done criteria, locked tests and proofs.

Review corrected parent dispatch before child eligibility, invalid eligible receipts preventing
retry, an unbounded source-owner cache, seal recovery and terminal-status reinterpretation after
crash. For parent chronology and receipt validation, the later graph validator cannot prevent an
already dispatched bad prompt or restore a consumed eligible slot; the separate retry rules do not
supply those missing pre-dispatch/settlement checks. For crash integrity, SQLite rollback alone does
not remove durable files, and matching output bytes alone do not bind an adverse status. The final
code and regression cases reject those alternatives. Source ownership now retains one immutable
corpus at a time and final validation independently rechecks frozen files.

Input-capacity ceilings remain an explicit **before-real-dispatch hold**, not a claim closed by this
release. Binary/multimodal delivery, issue propagation, reconciliation, downstream source-inventory
and context-exclusion integration, and real H29/E7 acceptance remain open. Complete history means
only contexts dispatched through this journal and checked against an independently retained hash.

## Retained H29 byte-delivery rehearsal

The [exact receipt](h29-render-rehearsal.json) records six manifest-declared legacy HTML views: 794,260 source bytes rendered into 805,424 prompt bytes; largest input 302,272 bytes. Both exact-hash JPEGs were rejected as unsupported binary images. Two reproductions were byte-identical; all 18 bundle artifacts verified. No model calls or new journal/graph were made. The full source/prompt bundle and reproducer remain in workspace `outputs/takeover-2026-09-26/h29-render-rehearsal/`, with receipt SHA-256 `1eee0fa1e780e026275478f5af258e6a7c265bd81c3069029ba10ac82836d09a`.

The earlier 794,478-byte estimate mixed two original packets with their 218-byte-smaller derived views. The receipt preserves both sets separately. This fixture proves delivery of the exact six views, not full four-source-contract coverage, semantic boundaries or model-context capacity. Existing A stays individually eligible; compacted B stays ineligible; neither is recertified.
