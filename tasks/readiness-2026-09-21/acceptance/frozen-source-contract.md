# E7 frozen source contract

The evaluation keeps the approved 30-filing selection and its original manifest unchanged. An explicit revised-source overlay supplies the bytes used by both experiment arms. The source adapter is measurement instrumentation around the existing production pipeline; it does not generate summaries or grant acceptance.

## Retained identities and bytes

| Record | SHA-256 |
| --- | --- |
| Original selection manifest | `68242a2c1c57da8d445bc4e1aca104017cffaffe8bbebf131228cde8ea94ba66` |
| Revised source manifest | `f65b783c0d73f98eb49f4d91acc79fbada546be7133decb3f2094679b2aaa708` |
| SEC JSON supplement manifest | `f6365709fa83983538a55f7ad4745cf79ccdd955ac9c91bdde2d2118ac21f12a` |
| Embedding manifest | `043a595866d51c74e807d533c2f980e1dcbcf0033af19d20ed4cd6c9485b5639` |

The revised archive contains 92 filing packets. Sixty retain their historical hashes: all 30 indexes and complete submissions. Thirty primary documents and two exhibits have changed hashes; their new bytes are not represented as recovered historical bytes. Sixty raw SEC JSON supplements preserve submissions metadata and companyfacts for each selected filing. Thirty embedding records declare the relationship between separately retained HTTP documents and the documents inside each SGML submission.

The resolver checks fixed manifest hashes, exact identity and role coverage, safe paths, and every referenced file's size and hash before admission. Readiness, slot selection, worker requests, collection, source-reference validation, blinded packets and decision reporting share these effective sources. The permanent programme's review-evidence inventory binds the source contract alongside source-reference evidence. The original selection hash remains a separate part of that binding.

## Production parsing

The adapter supplies retained sources to the existing Edgar parsers and SEC document service. It preserves primary text, section extraction, filing-instance XBRL, companyfacts fallback, statement context and excerpt acquisition. Persisted, Redis and process XBRL caches are bypassed in the isolated invocation. Companyfacts still passes through the existing accession-filtered production parser; missing facts remain missing.

The production pipeline invokes XBRL and sections for 10-K, 10-Q and 20-F. Its 6-K branch uses the production exhibit extractor and may fall back to the archived primary. Standalone adapter canaries also exercise 6-K XBRL capability; that does not mean the production pipeline calls it.

Source faults remain recorded even if the production pipeline catches the exception. Every actual provider reservation rechecks the active archive context and source violations, including retries, recovery and attribution verification. The worker retains the source trace, exact summarizer inputs and outputs, previews, canonical output, rendered output and export, and seals each declared artifact. Collection verifies those retained bytes against the contract.

For H02 and H19, the retained index names a co-registrant primary URL. Its unique selected SGML attachment supplies the parser bytes through an explicit alias. Live HTTP byte parity for those two alias URLs remains unverified and must remain a limitation in the measurement report. Known SEC-injected script/wrapper differences between HTTP and SGML are audited exactly; unknown differences fail.

## Execution prerequisites

The revised contract replaces the blanket implementation hold with explicit source validation. It does not satisfy the remaining review or execution requirements. Real independent AI source briefs and reconciliation, candidate/comparator configuration and runtime parity, fresh price/balance/quota evidence, and a metered non-holdout smoke remain required. The PLD development smoke sources are retained and adapter-validated; the paid smoke has not run. The smoke source contract (`162898a52278f7707f33a72816036e17f08ef7f58060f24c67fbe7ac5e7b8aa7`) is immutable evidence too; its filing must match an existing development golden and cannot be one of the 30 holdouts.

No source-only test or parser canary establishes product quality, full human review, or production activation. No paid E7 generation is authorized by a successful source check alone.

## Source review preparation

The [offline document mapper](source-document-map.md) binds this same archive and inventories all
SGML documents with exact byte spans, hashes and review requirements. Its [30-filing receipt](../../review-evidence/e7-source-map-2026-09-23/README.md) removes the giant-packet parsing bottleneck; it does not establish semantic source coverage.
