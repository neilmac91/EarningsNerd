# Match the real evidence selector and admit authored evidence before fuzzy repair

Date: 2026-09-29 · Area: arch / generation consumer boundary

The tax-cause withholder initially handled absent camel/snake aliases but missed the read-time
consumer's truthy fallback: empty or null canonical evidence still selects valid camel-case
evidence. Independently, calling it after evidence snapping could grant exact-source eligibility
solely because a different gate had repaired the original near-match.

Use the consumer's actual `canonical or camel` selection, while abstaining for two populated
conflicting values. Whitespace is truthy and must not silently fall through. Decide this owner's
source eligibility before fuzzy evidence repair in final, as preview already does. Do not change
the independent snapping behavior or call a repaired quotation originally authored evidence.

The existing `test_statement_relationship_integration.py` consumer gate covers empty/null
fallback, populated and whitespace conflicts, and a real armed snap that occurs while the
original unsupported impact stays authored on final, preview and exports. Its bounded
fault/restoration proofs are recorded in the local candidate review artifact.
