# Selected-source review capacity

A separate streaming profile read the 32 selected primary/exhibit spans for the 30 filings.
Every span hash and source-file size matched, with no parser error or UTF-8 replacement.
It counted **18,780,389 text characters** across 186,916,805 selected bytes: about 19.2% of all
complete-submission bytes. This is a workload measurement, not full-source coverage.

The selected spans contain 6,859 tables, 66,069 rows, 628,675 cells, 480 images and 92,388
inline-XBRL facts. Explicitly hidden regions contain 3,125,870 text characters (16.6%). These
categories overlap. Image alt attributes and text counts do not prove image/table meaning was
preserved. No script/style data occurred inside these selected spans; comments/declarations and
processing instructions were counted separately. External CSS and rendered reading order were
not evaluated.

Two filings (H29/H30) have at most 100,000 non-whitespace characters; 16 have 100,000–500,000;
eight have 500,000–1 million; four (H02/H05/H25/H26) exceed 1 million. H25 alone has **3,086,393
text characters, 1,621 tables and 16,411 inline-XBRL facts**, including 1,092,693 explicitly hidden
characters. Its other 549 SGML documents remain outside this selected-span profile.

The profiler used 256 KiB reads without a whole-document DOM: 72.31 seconds total and 36.2 MB
peak resident memory. It created no flattened review text and altered no source bytes. The
machine profile, utility and full report are retained under the private workspace output
`outputs/overnight-2026-09-23/fable-audit/`.

Proceed with a measured section/table/inline-XBRL source-review tranche on H29, H01, H02 and H25.
The largest filings cannot be represented honestly as one small unstructured context. Any
hierarchical review method must preserve each child context's source ranges and actual receipts,
reconcile cross-section issues and account for image/structured/other-document limitations.
Sampling or summaries alone cannot support a complete-coverage assertion. Stop as incomplete
when the recorded method cannot establish coverage; do not weaken the approved quality bar.
