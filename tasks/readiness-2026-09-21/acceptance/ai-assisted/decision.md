# AI-assisted decision dossier

The offline decision command verifies the immutable review seal, reconstructs the complete
durable collector index, checks both independently shuffled packet sets against the retained
outputs, and rehashes the copied source/reference/visible files. Editing a copied packet or
pointing its index at another draw does not change the measured output. Source and generation
readiness holds still apply; no successful AI decision grants production activation or original
human acceptance.

```sh
python -m evals.acceptance_ai_decision \
  --manifest /PRIVATE/candidate-manifest.json --archive /PRIVATE/archive \
  --prerequisites /PRIVATE/evidence/prerequisites.json \
  --outputs /PRIVATE/outputs.json --mapping /PRIVATE/custodian/mapping.json \
  --packets /PRIVATE/reviewer-packets --evidence /PRIVATE/reviews/inventory.json
```

The JSON report goes to stdout, with exit 0 for a complete AI-protocol pass and exit 2 for
fail/incomplete. Capture it in a new dossier file outside the programme/evidence directory.
The command is offline; it does not generate outputs, run a judge, change the ledger or grant
spending permission. Review records are retained assertions with inspectable inputs and
outputs; local receipts do not authenticate a model provider or prove context isolation.

The review inventory has `schema_version: 1`, `review_protocol: "ai_assisted"`, exact
`mapping_sha256`, the frozen `protocol_sha256`, a `judge_ledger` file reference and 120
`assessments` file references. References contain `path` relative to this inventory directory
and `sha256`. Each assessment names its `packet_id` from `ai-packet-1`, quality and challenge
context IDs, exact `reviewer_artifacts`, sorted `surfaces_checked`, `grounding_sha256` and
`reference_sha256`. It contains integer `completeness` and `usefulness` scores 1–5 with
nonempty reasons, `semantic`, `checks`, `findings`, and hash-bound `quality_response`,
`semantic_response`, `challenge_response` and `machine_inventory` files.

Quality and challenge responses carry version 1, `review_protocol: "ai_assisted"`, the exact
frozen `role_identity`, their independently blinded packet ID/artifact inventory, reference
and grounding hashes. Quality supplies both scores/reasons and its complete `allegations`
list. Challenge supplies the complete `checks` and `findings`; normalized values must equal
these retained response contents. Both must bind `machine_inventory_sha256` and record
`claim_inventory_coverage: "all_detected_claims_inventoried"`. This is a model claim, not a
deterministic completeness proof.

The semantic response records version 1, the first packet ID/artifacts and grounding hash,
model `cli:claude-fable-5-1`, contract `"2"`, `error: null`, `grounding_truncated: false` and
the exact inner CLI `raw` response. The decision rebuilds judge stdin from the measured
production summarizer call, complete canonical projection, XBRL and statement evidence;
the existing judge's caps still apply. It verifies all 120 inputs plus the sealed development
smoke against the [retained CLI ledger](README.md#retained-fable-cli-calls), and reparses
the raw responses. A copied PASS or a different input cannot replace a missing invocation.
This verifier audits returned calls; an execution-side call-reservation guard must still be
used for the actual judging handoff so the ceiling is enforced before invocation.

`checks` must cover `numeric_claims`, `causal_claims`, `financial_basis`, `quotations` and
`citations`, each with `checked`, `defect` or `unresolved`. The decision reruns the
[exact deterministic checks](checks.md) over the actual packet files and frozen sources.
Every machine failure requires exactly one finding with its `machine_check_id`, matching
`surface`, and `original_allegation` equal to `machine:<id>:<code>`. Incomplete machine
checks hold the decision. Model/source review supplies semantic coverage beyond exact spans.

Each finding retains a unique `id`, `surface`, `claim`, source locator/context, severity
`S0`–`S3`, category (`claim`, `omission`, `fabricated_quote`, `misleading_citation`),
disposition (`confirmed`, `rejected`, `unresolved`), reason and two independent source-based
`refutations`. All original quality/Fable allegations survive via `original_allegation`;
rejected allegations are preserved. Unresolved claims hold the decision. Confirmed S0/S1,
fabricated quotes and misleading citations veto the candidate even when other outputs score
well. S2 findings cannot coexist with both quality scores above 3.

Exactly 90 candidate and 30 fixed comparator assessments are required. At least 86 candidate
outputs must meet both 4/5 targets; no filing can have two deficient draws. The report retains
all 30 triples, paired better/tied/worse/mixed counts, defects and incomplete evidence.
Comparator defects are reported separately from the candidate's absolute veto. Known failure
takes precedence over incomplete status, while all incompleteness remains visible.

The dossier includes conservative generator reservations, known usage estimates, unknown and
pending usage counts, judge invocation count and exposure limitations. These are not provider
invoice totals. A pass means the evidence supports a limited-beta product-risk decision; it
is not a claim of independent human review, population-wide accuracy or an unseen sample
when external exposure history is unknown.
