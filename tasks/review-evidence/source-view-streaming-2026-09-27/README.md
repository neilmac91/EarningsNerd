# Bounded source-view export — 27 September 2026

PR [#974](https://github.com/neilmac91/EarningsNerd/pull/974) is merged and
[production-verified](pr974-release.json): main `a7983ddc04f5991462367b6d97222d3726430d93`,
revision `00396-p2f` at 100%, migrations 0/39, successful main CI `36320062558`
and independent HTTP 200 healthy database readback. The
[actual hosted audit](pr974-hosted-audit.json) records 70/70 summaries, 18/18
Copilot outputs, 105 successful calls, no errors/retries/hard failures and
USD 0.185313 application-estimated cost; billed cost is unknown. Soft advisories
remain recorded. The exact-head review returned no findings. A PR-body update
refreshed the required review gate; the initial merge attempt was refused, and
merge completed only after that refreshed check passed. No rule was bypassed.

The public `build_source_view` path failed on the frozen H25 direct primary in
[Linux run 36311408531](https://github.com/neilmac91/EarningsNerd/actions/runs/36311408531):
`project_html` returned, then `json.dumps` raised `MemoryError` while constructing
its complete encoded projection. The child was constrained to 3 GiB address space
and 180 seconds, failed after 75.05 seconds, and created no output directory.
H02 was held. This supersedes the earlier unmeasured-export status without
invalidating #972's successful projection/verification measurement.

The correction writes the same sorted, indented UTF-8 JSON into a temporary file,
then streams it into the output with a SHA-256 and byte count. The final source
identity check still precedes output creation; an existing destination is still
refused; the manifest is still written last. JSON formatting, projection content,
compact text and reader rendering are unchanged. The new small public-API memory
gate rejects the previous whole-payload exporter; the Unicode invariant proves
exact old-format bytes and independently recomputes every manifest fingerprint.

The candidate must complete the same H25-first/H02-second Linux export contract
before a capacity claim: exact sources, fresh children, 3 GiB address-space cap,
180 seconds, no retries, no provider calls, complete four-file bundles retained.
The old diagnostic remains immutable. Neither a resource pass nor this engineering
change establishes source coverage, provider fit, independent source briefs or E7
quality acceptance.

## Candidate execution and verification

[Linux run 36318572864](https://github.com/neilmac91/EarningsNerd/actions/runs/36318572864)
completed successfully on diagnostic commit `c0a789a63b3b96f0d660d0e4954ac698c265f310`.
The [raw runner receipt](linux-export-receipt.json) binds the measured module to
SHA-256 `9ab8afb151dd1c2c7fe0e3017267777ffcc89236ec92ef90e1869d3b12d2dabd`.
The runner differs from v4 only in the module identity anchor. Source hashes,
H25-first order, 3 GiB/180-second per-child limits, no-network execution and
no-retry behavior are unchanged. Both children exited zero; neither source was held.

| Direct primary | Worker seconds | Peak RSS bytes | Exported projection bytes |
| --- | ---: | ---: | ---: |
| H25 | 117.437874 | 3,170,091,008 | 1,057,261,406 |
| H02 | 43.387908 | 1,244,389,376 | 408,457,004 |

Each retained bundle has exactly `compact.txt`, `reader.txt`, `source-view.json`
and `manifest.json`. Output compact sizes include their terminal newline; they
are one byte larger than the raw compact strings in the earlier projection-only
receipt. Peak RSS is not a measurement of available address-space headroom.
This single pass does not establish comfortable resource margin or coverage of
all filing members. No model, provider or SEC call occurred.

Artifact `10931507720` is 135,355,892 bytes, SHA-256
`ac42fd92445cfd498f9a1692800a90c241a6e2c8e775794116aede7a9d66d355`.
An independent local audit verified the GitHub digest before safe extraction, all
12 archive members, both frozen source identities, and all eight output files
against the raw receipt and manifests using bounded reads. Its operator-retained
`run-36318572864/execution-receipt.json` has SHA-256
`e2f1522d413138d69159a4ef0083babd7b051d4c375e214aa4303194d47cd1b3`.
The complete archive and expanded bundles are retained in the operator workspace
under `outputs/takeover-2026-09-26/h25-streaming-export/run-36318572864/`; only
small receipts belong in the repository. The raw runner paths refer to that
artifact layout, not repository-relative files.

[Local verification](local-verification.json) records 3,734 passing tests, all four
PostgreSQL concurrency lanes and performance, Ruff/Bandit clearance, exact-byte
parity, and the failed/restored memory mutation. Its log paths refer to the same
operator retention root. The gated code commit is `a8c2c78b88361345d7c7a42ca2bff866880ec4a1`;
subsequent receipt updates change no backend bytes.

## Source provenance and the next quality candidate

The [current H25 entity-body comparison](h25-current-source-comparison.json)
used one request through the existing SEC compatibility path and shared limiter.
The present HTTP-decoded entity is byte-for-byte equal to the frozen source:
297,209,475 bytes, SHA-256 `877d8eb00ae65e64981e3e3eafee69c519a74e4cfed162109109b95c23432a32`.
The UTF-8 round trip is also exact. This places H25's observed uuencode defects
before application text conversion at the current entity-body boundary. It does
not prove historical compressed-wire identity, assign SEC-versus-filer cause,
authorize reconstruction or close the encoded-member/semantic holds. The
operator retained the one-shot observer and its zero-request local resource-limit
setup failure separately under `outputs/takeover-2026-09-26/h25-authoritative-byte-comparison/`.

The [next quality-candidate plan](next-quality-candidate.md) records the reviewed,
locally committed date/coexistence correction and the remaining scope, wording
and causal issues to finish before fresh generation. Remote PR942 remains draft;
no new Fable call, candidate promotion, baseline change or E7 holdout occurred.

A separate [authoritative g39 GIF observation](h25-authoritative-g39-comparison.json)
made one additional SEC request through the same owner and matched the retained
diagnostic candidate's length and SHA-256: 148 bytes,
`6e0164cd8773b7af59b6901641afbdd42a87177910f800c6bac763fe37b6bb3b`.
This is one terminal/nonzero-unused-padding case, with zero short-width data
lines; it does not cover the other 263 strict failures or authorize generic
reconstruction. The actual binary is retained locally in
`outputs/takeover-2026-09-26/h25-authoritative-terminal-image-comparison-v2/`.
Earlier import-only failures made no requests: a 64 KiB file-size limit truncated
new Python bytecode. Disabling bytecode writes and using a fresh cache prefix
passed an offline import probe under the same limit before the single request.
No installed dependency was repaired, and the prior failed observations remain
retained. No strict decoder, source file, frozen contract or admission changed.
