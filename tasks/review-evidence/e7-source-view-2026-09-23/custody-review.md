# H29 pilot custody sanity review

**Disposition: no custody/reporting blocker found.** This review checks the retained metadata, hashes, normalization, and admission language only. It does not independently assess any financial conclusion in either reference draft.

## Reference A

- The original `reference-a.json` hash is `3eae418977d78f091f38468d7ee14c97c95e9f81aa9246283838175863ea53ba`; its read-log hash is `b67ed6e48dee33fa3b8eaa639ae721e2dfcf793a4efc4c3d9947ddc9dba41db6`. Both match the custody audit, the pilot decision, and the compact repository receipt.
- All 12 `material_issues` in the frozen schema-2 brief are exactly equal to the original draft objects, in the same order. The four packet role/hash objects are unchanged. Normalization is limited to joining the four original `coverage_limits` entries into a string and appending explicit custody limits and identifiers.
- The prompt, dossier manifest, brief, and context-receipt hashes all match their referenced files. Each of the six logged reader hashes matches its file, and every line from 1 through the recorded final line is covered without a gap. The retained log separately accounts for four packet roles, five submission members, and two decoded graphics.
- The brief has the exact `_BRIEF_KEYS` shape expected by `acceptance_ai_protocol.py`; `_source_packets`, `_material_issues`, and `_context_receipt` accept the retained values. The receipt records `source_only: true`, no candidate artifacts, and `context_window_truncated: false` for the actual `/root/h29_reference_a` context.
- This is correctly described as an **individual schema-2 evidence freeze**. The current validator would still require a frozen schema-3 role protocol, both independent briefs for every accession, reconciliation, and the remaining global evidence before readiness can pass. Nothing reviewed claims otherwise.

## Reference B and programme status

- The original B draft, Markdown, and read log retain the hashes listed in the separate addendum. The six reader hashes, byte counts, and recorded ranges verify against the files, including the post-compaction direct read of the standalone earnings exhibit.
- B consistently records `context_window_truncated: true` / `context_compaction_observed: true`. The addendum correctly distinguishes completed range accounting from the required single-context condition and assigns `coverage_status: partial`, `eligibility: ineligible`, and `eligible_for_freeze: false`. No B brief was frozen and no reconciliation was dispatched.
- The compact repository receipt binds the full local decision (`731c9162425d9c0103d4e1fe650325ef1858c4e2ef525a27ce73f8eebb38e4bd`) and B addendum (`7b9a5a89bd74defa5fe0cb9a9bf13d3e0549b090d9810f6369741fc6ea399996`). Its shared fields reproduce the local decision; it intentionally replaces the six detailed B reader checks with their count while retaining the full-decision hash.

## Reporting boundary

The repository pilot report and continuation plan accurately state one frozen A brief, no eligible A/B pair, no reconciliation, no E7 holdout generation, no Fable call, and no human acceptance. They keep source-method progress separate from quality acceptance, production deployment, and universe-wide generation. Model metadata is limited to the requested `gpt-5.6-sol` selection; the records explicitly say that an immutable served-model build is not exposed and do not invent one. Coverage statements are framed as observed hash/range and context metadata rather than proof of private model attention or browser-rendering equivalence.

The next-step hierarchy remains proposed and unadmitted. The report does not retroactively relabel B, reuse it for reconciliation, or present the pilot as production-ready evidence.
