# E7 AI-assisted evidence, schema version 2

Use a private evidence directory outside the repository. The enclosing
`prerequisites.json` uses `schema_version: 2`, `review_protocol: "ai_assisted"`,
the original execution fields (`candidate_config`, `comparator_config`, pricing,
balance, Fable, development smoke and budget control), and an `ai_assisted`
object with `protocol`, `source_briefs`, `reconciled_references` and
`exposure_review`. Each file reference has a relative `path` and exact SHA256.

The protocol lists five separate roles: `source_reference_a`,
`source_reference_b`, `source_reconciliation`, `blind_quality` and
`source_challenge`. Each records the actual provider, model, version and unique
context ID, plus hash-bound prompt and contract files. A role declaration does
not imply that a model has run; retain the actual source briefs, reconciliation
and later rating/challenge records. The first two roles must produce one
independent source-only brief per approved accession, for 60 briefs. The
reconciliation role produces one source-only reference per accession, for 30
references. No candidate output may enter these contexts before their evidence
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

All AI protocol files, prompts/contracts, briefs, references and exposure bytes
are included in the ledger's immutable `review_evidence` inventory before
dispatch. Only the existing balance, quota and pricing observations may be
refreshed after that seal. The archive-binding hold and every other execution
gate still apply. These templates contain no observations or verdicts.

## Retained Fable CLI calls

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
