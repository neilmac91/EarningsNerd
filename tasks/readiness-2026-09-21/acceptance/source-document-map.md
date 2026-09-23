# E7 source document map

The offline mapper inventories every embedded document in each of the 30 frozen complete
submissions. It addresses the inflated filing-wide text queue, which mixed readable documents,
structured statements, graphics and encoded archives. It does not replace independent source
review or grant generation, judging, quality acceptance or production activation.

From `backend/`, use a fresh private output directory:

```bash
python -m evals.acceptance_document_map \
  --selection ../tasks/review-evidence/acceptance-2026-09-19/candidate-manifest.json \
  --source-root /absolute/path/to/e7-ai-source-snapshot-2026-09-22 \
  --output /absolute/path/to/new-document-map
```

The shared source resolver verifies the fixed selection, all 92 filing packets, 60 SEC JSON
supplements and 30 embedding contracts before output. It re-verifies that inventory before
publishing `index.json`. An existing output is refused. A failed run may leave partial maps,
but has no complete index; preserve it and use a new output directory after correcting the cause.
The JSON maps are deterministic for the same source and selection paths.

Every SGML document records its declared identity, full span, header, payload, footer, content,
format wrapper and prefix/suffix. All spans use zero-based byte offsets and exclusive ends with
SHA-256 hashes. The document and submission-envelope spans form an exact partition of the
complete submission. Outer `<XBRL>`/`<XML>` wrappers and whitespace remain explicitly accounted
for; selected primary/exhibit content must match its frozen embedding hash and length.
Exact duplicate payloads are grouped without deleting any representation.

Each document has a primary routing hint plus non-exclusive review requirements. Inline-XBRL
markers add structured review even when the main route is readable HTML. Namespace/tag detection
is a routing aid, not proof of complete structured extraction. Graphics, archives, generated
statement renderings, other structured data and unknown formats all retain explicit review
requirements. No route means irrelevant or reviewed. The other 62 filing packets and all
supplements are separately hash-bound in the index; their semantic coverage is not established
by the SGML byte partition.

[Real-archive verification](../../review-evidence/e7-source-map-2026-09-23/README.md) mapped 4,330
documents in all 30 submissions, including the previously stalled large filing. Both runs
produced 31 byte-identical JSON files. `semantic_coverage_attested` remains false throughout.
The next step is a source-only review-method capacity tranche that preserves tables, inline
facts, image limits and every issue/disagreement. Do not feed encoded archives or duplicate
renderings into a giant flattened model context and call it complete coverage.
