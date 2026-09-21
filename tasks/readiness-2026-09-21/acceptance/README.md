# E7 acceptance preflight and blinded review packets

The founder accepted the [E7 specification](../../quality-acceptance-specification-2026-09-19.md) and the exact [30-accession manifest](../../review-evidence/acceptance-2026-09-19/candidate-manifest.json) with SHA256 `68242a2c1c57da8d445bc4e1aca104017cffaffe8bbebf131228cde8ea94ba66`. This package provides offline checks and blank forms. It does not generate a summary, call Fable, invent a human brief, or authorize acceptance. The archive's 92 source packets are not checked into the repository; their expected 1,161,213,075 decoded-text bytes and hashes are recorded in the manifest. The source archive is absent from this checkout, so current preflight must report `missing_source_archive`.

Keep completed forms and provider receipts outside the repository. Fill [prerequisites.template.json](prerequisites.template.json) as `prerequisites.json` and save its evidence files under the same private directory. `path` fields are relative to that directory and every `sha256` is computed over exact file bytes. The included [reference brief](reference-brief.template.json), [exposure attestation](exposure-attestation.template.json), [review form](review.template.json), and [adjudication form](adjudication.template.json) are blank. A completed brief must be independently source-reviewed by both named reviewers, adjudicated and frozen before generation; the machine checks its recorded fields and hash, not whether the human judgment was actually independent. Reviewer identities, competence and committed hours are supplied only by people. Exposure attestation covers all 30 exact accessions and external/untracked artifacts; silence is not unseen certification.

`archive_root` is the *work directory containing* `e7-sources/`, matching the manifest paths. Run the preflight before any paid acceptance request:

```bash
cd backend
python -m evals.acceptance_readiness \
  ../tasks/review-evidence/acceptance-2026-09-19/candidate-manifest.json \
  /ABSOLUTE/PRIVATE/WORK/DIRECTORY \
  /ABSOLUTE/PRIVATE/EVIDENCE/prerequisites.json
```

The JSON report names each missing or invalid prerequisite and reports separate `ready_for_paid_execution` and `ready_for_packets` values. Paid readiness requires receipts for DeepSeek's current official model price (uncached input and output USD per million tokens), positive available balance and Fable model/contract/quota observed within 24 hours, plus a completed development smoke on a non-holdout accession and a reviewed request-budget-control commit. Packet readiness preserves those receipts without making their freshness a new requirement after outputs exist. Neither flag substitutes for the runner's own atomic per-request USD reservation. Unknown prices, missing source bytes, brief/attestation gaps and unavailable Fable all fail closed. The manifest's draft status text is historical; its accepted hash and the recorded founder decision bind the candidate identities.

After the acceptance runner has retained every output, preview and export, write `outputs.json` containing `{"records": [...]}`. Each record has `accession_number`, `arm` (`candidate` or `comparator`), `draw` (1, 2, 3), `status: "completed"`, `error: null`, UTC `created_at`, `config_sha256`, `canonical_path`, `rendered_path`, `export_path`, `preview_paths`, `preview_count`, `previews_truncated: false`, `retry_preview_attempts_omitted: 0`, and `artifact_sha256` mapping `canonical`, `rendered`, `export`, `preview_0`, etc. Artifact paths are relative to the outputs JSON directory and must be unique, regular, hash-matched files without symlink/traversal. Candidate identities are all 30 accessions × three draws. The **comparator** is only H01, H03, H05, H07, H09, H14, H18, H23, H26 and H29 × three draws: 30 comparator outputs. Missing, duplicate or unrequested identities, errors, truncated/omitted previews, missing files or mismatched configuration stop packet creation.

```bash
cd backend
python -m evals.acceptance_readiness \
  ../tasks/review-evidence/acceptance-2026-09-19/candidate-manifest.json \
  /ABSOLUTE/PRIVATE/WORK/DIRECTORY \
  /ABSOLUTE/PRIVATE/EVIDENCE/prerequisites.json \
  --outputs /ABSOLUTE/PRIVATE/OUTPUTS/outputs.json \
  --reviewer-root /ABSOLUTE/PRIVATE/REVIEWER-PACKETS \
  --custodian-root /DIFFERENT/PRIVATE/CUSTODIAN-MAPPING
```

The builder makes two independently shuffled reviewer directories with opaque case/packet IDs. Each reviewer receives exact verified source bytes once per accession, a source identity file, the frozen material-issue list, and all 120 canonical/rendered/export/preview artifact files. Reviewer indexes and filenames omit arm, draw and configuration hash. The seed and arm/draw/config mapping live only in the separate custodian directory (mode 0700, mapping mode 0600). Keep that mapping outside reviewer access. The builder requires new destination paths and cleans up its own incomplete directories on failure; do not publish either directory until a custodian checks permissions and blinding. Source/company identity remains visible because reviewers must verify the selected filing.

The scoring and defect criteria remain in the accepted specification: zero S0/S1, zero fabricated quotes or misleading citations, at least 86/90 jointly ≥4 on completeness and usefulness, filing-level repeatability, complete same-contract Fable verdicts and human adjudication. These blank forms do not record a score or waive any of those gates.
