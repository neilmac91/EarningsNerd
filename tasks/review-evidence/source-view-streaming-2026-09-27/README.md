# Bounded source-view export — 27 September 2026

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
