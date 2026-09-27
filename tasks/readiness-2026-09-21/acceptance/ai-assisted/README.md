# E7 AI-assisted evidence: role protocol 3, evidence schema 2

Use a private evidence directory outside the repository. The enclosing
`prerequisites.json` uses `schema_version: 2`, `review_protocol: "ai_assisted"`,
the original execution fields (`candidate_config`, `comparator_config`, pricing,
balance, Fable, development smoke and budget control), and an `ai_assisted`
object with `protocol`, `source_briefs`, `reconciled_references` and
`exposure_review`. Each file reference has a relative `path` and exact SHA256.

The protocol lists five separate roles: `source_reference_a`,
`source_reference_b`, `source_reconciliation`, `blind_quality` and
`source_challenge`. The role protocol uses `schema_version: 3`. Each role records the actual provider,
model and version, plus hash-bound prompt and contract files. Context IDs belong
to actual evidence records, not to the frozen role descriptors. The enclosing
prerequisites, source briefs, references and context receipts keep schema version 2. A role declaration does
not imply that a model has run; retain the actual source briefs, reconciliation
and later rating/challenge records. The first two roles must produce one
independent source-only brief per approved accession, for 60 briefs. The
reconciliation role produces one source-only reference per accession, for 30
references. Each source-brief index row includes `accession_number`, `role`,
`context_id`, `path` and `sha256`. Use a fresh actual context for each filing and
source role: all 60 brief contexts and 30 reconciliation contexts must be unique.
This permits bounded filing reads without placing all 30 filings in one context.
No candidate output may enter these contexts before their evidence
is sealed in the programme ledger. The protocol freeze follows all briefs,
reconciliations and the exposure observation, and precedes generation.

The `source_packets` array in each brief/reference lists every approved packet
role and SHA256 for that accession. Each also hashes a separate context receipt
with the exact source inputs, role, context, timestamp, and an empty candidate
output input list. The reconciliation receipt also binds both source brief
hashes as inputs. A `complete` coverage claim and
`context_window_truncated: false` are required for paid readiness. These fields
are retained assertions: the preflight cannot prove that a model actually read
the whole filing. Use `coverage_limits` to state source or extraction limits
honestly. A partial or truncated context must be recorded as such and holds the
run; do not label a subset as complete. Each material issue carries its source
role/hash, locator, amounts and bases, qualifiers, importance and disclosure
limits. Reconciliation binds both exact brief hashes and gives every brief
issue a stable, unique ID and a source-backed disposition. Supported issues
link a reconciled issue ID; rejected issues retain a source reason. An original
issue cannot be omitted. Reconciliation lists every material disagreement as
supported, rejected or unresolved with a source locator. An
unresolved source-reference disagreement holds generation. If the source itself
is uncertain, retain that as a supported uncertainty with explicit limits.

The exposure review names the checked accessions, observed scope, external
artifact inventory, known candidate-output/tuning exposures and whether
external exposure history remains unknown. Unknown external history is allowed
for descriptive AI quality measurement and is labeled in readiness and packet
metadata. Known candidate-output or tuning exposure holds the programme.
Neither field is a human unseen attestation. The AI evidence provides different,
weaker assurance than the original human acceptance protocol. It cannot be
reported as human-reviewed acceptance or used alone to turn on a production
flag.

After generation, each quality/challenge response records its actual `context_id`
and the frozen role identity separately. Contexts may be reused within one review
role only when that is what actually ran. A quality context cannot also be a
challenge context, and neither may reuse any source-stage context. Actual IDs need
not be invented before those reviews run. Retain coverage limitations for each
reviewed output.

All AI protocol files, prompts/contracts, briefs, references and exposure bytes
are included in the ledger's immutable `review_evidence` inventory before
dispatch. Only the existing balance, quota and pricing observations may be
refreshed after that seal. The archive-binding hold and every other execution
gate still apply. These templates contain no observations or verdicts.

## Optional cross-role reconciliation history

`ai_assisted.reconciliation_history` may retain declared cross-role history that does not fit the
bounded retired-source-B format. It is an optional list with at most one schema-1
`source_reconciliation_history` record per accession. Omitting the key leaves the review-evidence
inventory byte-for-byte unchanged. Each record binds the current reconciliation context and exact
file reference, the retained raw reconciliation draft, a partial-history manifest and all artifacts
it names, a separate disposition ledger, and the complete historical-origin map. Every origin has a
stable `history_prefix`, its context/role, the status of that historical artifact, and an exact file
reference whose SHA must match `artifact_sha256`. The artifact status does not classify every use of
the context: a context may also own a later eligible source brief. All such contexts still enter the
shared exclusion closure so no downstream blind role can reuse them.

`technical_attempts` separately binds incomplete source attempts that produced no financial history
rows. Each declaration fixes its context, role, `partial_ineligible` status, reservation, dispatch,
and settlement. The validator checks their accession/context chain and reads every draft, brief, and
read-log named by the settlement. This no-history route requires `issue_count: 0` and an exact empty
`material_issues` array in the bound settlement draft; an attempt with findings must enter the
origin/ledger route instead. Technical contexts join the exclusion closure despite their zero issue
count. `source_context_closure_sha256` is SHA256 over the compact, ASCII, sorted JSON
array containing current A/B/reconciliation contexts, historical-origin contexts, and technical
attempt contexts.

The ledger declaration adds `row_count`, `identity_set_sha256`, and `runtime_holds` to its ordinary
`{path, sha256}` file reference. `identity_set_sha256` is SHA256 over the compact, ASCII, sorted JSON
array of exact history IDs. Each `runtime_holds` row contains only `history_id` and
`hold: "custodian_classification"`. Rows outside that list must be source-supported, retain a valid
role/hash and filing locator, and target an unchanged current reconciled issue. A declared runtime
row must remain unresolved with a null current target. The hold ID set must equal the exact set of
disagreements that were unresolved in the bound origin bytes; the wrapper cannot promote or
reclassify them. This bounded rule preserves H30's known runtime-custody dispute without claiming
that unresolved status alone proves whether another legacy dispute is financial or operational.
Use this route only where separate retained review already classified each unresolved legacy
disagreement as runtime custody. Structural validation preserves its identity and status but does
not prove that semantic classification; a history known to contain an unresolved financial dispute
requires a separate supported reconciliation path. Validation preserves the frozen legacy
locator text while the typed inventory exposes `filing_source_locator: null`,
`evidence_class: "operator_runtime"`, and the custody hold.

The complete ledger identity set is derived from the bound origin bytes rather than trusted from the
ledger declaration. Each origin contributes `<history_prefix>:issue:<issue_id>` for every
`material_issues` row and `<history_prefix>:disagreement:<array-index>` for every disagreement.
Manifest counts for source issues, reconciled issues, and disagreements must equal the corresponding
manifest-exposed artifacts. The raw reconciliation draft is retained as custody evidence only; its
hash does not assert that a generic transformer can reproduce the current reference.

The readiness boundary reports an unresolved operator-runtime row through `evidence_limitations`.
It does not turn a retired execution-history uncertainty into a financial-source disagreement or a
permanent quality hold. The risk control is the immutable unresolved classification plus inclusion
of every origin and technical-attempt context in the shared source-context closure; the decision path
then rejects those contexts as blind quality or source-challenge identities. This custody binding
does not prove the old runtime, re-judge financial findings, dispatch a provider, establish programme
admission, or authorize a production flag.

## Retained Fable CLI calls

The [E7 judge runner](judge-runner.md) reserves each explicit call before
dispatch and captures immutable CLI evidence for this ledger.

After generation, keep a separate JSON invocation ledger with
`schema_version: 1`, `programme_id: "E7"`, `kind: "e7_fable_cli_ledger"`,
`model: "cli:claude-fable-5-1"`, `contract_version: "2"`,
`cli_version: "2.1.278"`, and an ordered `entries` array. Each entry has
`slot_id`, `attempt`, `kind` (`substantive` or `quota_probe`), and SHA256 file
references for exact CLI stdin, raw stdout, raw stderr and a JSON receipt.
The receipt identifies the same slot/attempt/kind/programme, a unique invocation
ID, model/contract/CLI version, `auth_mode: "subscription_oauth_no_api_key"`,
the actual argv, integer exit code, UTC start/finish times, and the three
input/output byte hashes. Substantive calls use the exact CLI argv in
`evals.acceptance_ai_judge_evidence`; quota probes may use a different argv
with the same `claude -p --model claude-fable-5-1 --output-format json` prefix
and require an `OK` result. A probe is optional and at most one is allowed.

`validate_judge_ledger` takes an independent map of all 120 output slots plus
`development-smoke` to SHA256 of the exact reconstructed CLI stdin. It checks
all 121 outcomes, the 243-call ceiling, at most two attempts per substantive
slot, and retries only after a CLI error on identical input. It reparses the
raw CLI wrapper and verdict; a negative verdict cannot be redrawn. The
receipt is locally retained execution evidence, not provider authentication.
