# Render eligibility must be owned by the persisted application envelope

Date: 2026-09-12 · Area: arch / output trust

A new source-unit renderer originally risked accepting arbitrary nested keys that old model
responses could retain. A newly added schema field did not establish trust: that Pydantic schema
had no production caller. A content-version increment also could not prove who authored a marker.
No contaminated historical production payload was established by the retained sample.

The application constructs `source_unit_context_version=1` in the explicit final outer envelope
only after stripping model annotations and associating verified source context. The shared
renderer requires that exact integer marker; nested model/quote copies and boolean values do
not authorize display. Keep this trust boundary separate from future-generation cache stamps.

Existing enforcement is
`backend/tests/unit/test_source_unit_quote_context.py::test_only_code_owned_outer_envelope_authorizes_read_and_export`,
which covers old forged quote/nested data, a boolean marker and a real newly generated envelope
through read enrichment, Markdown, PDF and CSV. The committed eligibility-bypass proof
`3023c479` failed three controls; restoration `690de5c7` passed all four. The task ledger retains
the exact tails. This lesson records that existing guard; it adds no second test or proof.
