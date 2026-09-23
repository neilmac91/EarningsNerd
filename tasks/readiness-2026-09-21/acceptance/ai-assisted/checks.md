# Offline E7 surface checks

`evals.acceptance_ai_checks.run_checks(inventory, surfaces, sources)` reads only local files. The caller must supply **every** retained visible surface (canonical projection, rendered summary, export, and each preview) and the verified source packets that the checker may cite. Its two path mappings must have exactly the names in the inventory. The decision layer must bind the inventory/report hashes to the chosen slot and convert every machine failure ID into a retained source-challenge allegation; failures and incomplete issues cannot be replaced by an all-`checked` assertion.

Inventory schema version 1 has:

```json
{
  "schema_version": 1,
  "selected": {"accession_number": "0000018230-26-000008", "cik": "18230"},
  "sources": {
    "primary": {
      "sha256": "<64 hex characters>",
      "accession_number": "0000018230-26-000008",
      "cik": "18230",
      "official_url": "https://www.sec.gov/Archives/.../filing.htm"
    }
  },
  "surfaces": {
    "rendered": {"sha256": "<64 hex characters>", "claims": []},
    "preview_0": {"sha256": "<64 hex characters>", "claims": []}
  }
}
```

Each surface **must** include `claims`, even when empty. Claim IDs are unique across all surfaces and stable in `results`, `failures`, and `issues`. A `quote` claim has `id`, `kind`, `source_role`, `source_sha256`, `source_accession_number`, `source_range`, and `output_range`. A `citation` adds `target_range`: that output span must exactly equal the selected source's `official_url`. The source and output quote spans must be identical. Ranges are zero-based, half-open character offsets in strict UTF-8 decoded text, not byte offsets. Only exact contiguous text is supported; transformed typography, HTML entities, citation redirects, and paraphrases require other review evidence.

A `numeric` claim has `id`, `kind`, `operation`, `inputs`, `output_range`, `output_unit`, and `output_basis`. Each input has `source_role`, `source_sha256`, `source_accession_number`, `source_range`, `unit`, and `basis`. Every span must contain one plain signed decimal number, optionally with correctly grouped commas. Supported operations are `sum` (two or more operands), `difference`, `ratio`, and `percent_change` (each exactly two operands, in that order). `percent_change` computes `(new − old) / old × 100`. Sum, difference and percent change require identical input unit and basis; ratio reports `ratio` when units match or `numerator-unit/denominator-unit` otherwise, and `numerator-basis/denominator-basis`. The output's own decimal places define half-up rounding; no free-form tolerance is accepted. Zero denominators, scaled/unit conversions, ambiguous values, or unsupported operations are incomplete issues.

The result includes `status` (`pass`, `fail`, `incomplete`), `complete` (true only for pass), `failures`, `issues`, per-claim `results`, and actual file hashes. Quote results include hashes of the exact compared substrings; arithmetic results include parsed operands, computed and rounded values, displayed value, decimal places, unit and basis. A numeric or exact-text mismatch is a failure; absent files, changed hashes, unbound identity, malformed spans, and unsupported checks are incomplete. A failure takes precedence when both failures and issues exist, but both lists remain visible.

This checker establishes exact file, span and arithmetic consistency **only for inventoried claims**. Empty claim lists prove nothing about whether a filing or output contains other claims. Source unit/basis labels and the selected-source identity are verified for internal consistency against the inventory; the archive adapter and separate model/source challenge must establish their truth and claim coverage. Never use this report alone to claim natural-language completeness, grounded causation, or an original human acceptance result.
