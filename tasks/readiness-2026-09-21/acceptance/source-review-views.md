# E7 source review views

Source review needs the complete filing's narrative, table relationships, hidden text and
visual disclosures. The submission document map establishes byte boundaries; it does not
make a flattened text dump a sufficient review input.

`evals.acceptance_source_view` prepares an offline HTML view from an expected source hash
and byte count. Exact raw bytes remain authoritative. The projection retains source byte
locators, source order, table/row/cell structure and attributes, image references, and an
explicit inventory of comments, scripts and styles. Hidden text remains content. Scripts
are never executed and remote resources are never fetched. Whitespace normalization is
an explicit transformation, not a claim of browser-rendering equivalence.

From `backend/`, with the expected identity from the frozen source inventory:

```bash
python -m evals.acceptance_source_view \
  --source /absolute/path/to/source.html \
  --expected-sha256 <frozen-sha256> --expected-bytes <frozen-byte-count> \
  --output /absolute/path/to/new-view-directory
```

Read `reader.txt` for the compact ordered narrative and table rows; use `review.txt`
and `source-view.json` for detailed locators, attributes and nesting. `compact.txt` is
only the normalized text invariant, not sufficient financial-table review input. Both
structural renderings reproduce that exact text stream. `manifest.json` binds all files.
Unknown declarations (including CDATA), ambiguous spans, invalid UTF-8 and truncated
structural markup are rejected. An existing output is never overwritten.

The module is a review aid only. It has no path to enable paid execution or mark a source
brief complete. Unsupported syntax, uncertain display behavior and material visual content
remain obligations for the source reviewer. A projection or a clean hash check cannot
establish that a model inspected all material disclosures.

## Pilot before scale

H29 is the first capacity pilot: four approved source packets, three HTML submission
members and two encoded graphics. Its unselected EX-99.2 stays inside review scope because
it is part of the complete submission. The standalone primary/exhibit have an SGML envelope
and an injected external SEC script absent from the embedded HTML. Preserve the separate
hashes and review the exact differences; do not call those files byte-identical duplicates.

For each independent role, retain the exact prompt, source/view identities, observed
context identity, complete input ranges, image observations and output bytes. The roles
must not see one another's briefs or generated candidate/comparator outputs. Use a separate
context for reconciliation, carrying every original issue and its source-backed disposition.
Any incomplete delivery, unresolved material source or observed truncation keeps the result
partial. These are AI source references, never human acceptance.

Single-context H29 work uses the existing source evidence contract. Larger filings still
need a separately reviewed hierarchy that binds leaf reviews, all member dispositions and
the full union of issues. This view module does not implement or freeze that hierarchy.
