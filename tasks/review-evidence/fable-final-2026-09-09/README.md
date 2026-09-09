# Durable final Fable review evidence

This directory makes the substantive comparison and source-backed decisions available in a fresh checkout. It contains public filing/candidate quotations, source references, declared coverage, original reviewer labels and dated adjudications. It does not include full SEC filing text, private account data, credentials, provider responses or live account records. It is a review evidence bundle, not a generated-output acceptance certificate.

## Start here

- [Final comparison and coverage](review-comparison.md): original counts and case map, incomplete scope, contextual decisions and fix mapping.
- [Financial/source adjudication](source-adjudication.md): JD, SE, NVO, PDD, MELI and JPM/KO, with candidate paths and two refutations.
- [Narrative and evidence adjudication](narrative-and-evidence-adjudication.md): BA, INTC, PFE, AAPL and the raw-versus-rendered evidence distinction.
- [Machine-readable final inventory](verified-inventory.json): all 52 original attempt verdicts/scores, final Fable findings, candidate quotes/paths, source quotes/references and coverage limitations. It is copied unchanged.
- [Prior decisions](prior-reconciliation/ROOT-DECISIONS.md) and detailed historical [reviewer A](prior-reconciliation/agent-a.md), [reviewer B](prior-reconciliation/agent-b.md), [reviewer C](prior-reconciliation/agent-c.md) and [root](prior-reconciliation/root.md) adjudications preserve earlier source-backed narrowing and additions, including Sonate. Their adjacent JSON files contain structured details.

The prior-reconciliation files are intentionally byte-identical historical records. References there to unfinished Fable reports, older release states or local `work/` paths describe that earlier checkpoint. The final comparison supersedes earlier missing-report status; it does not rewrite the original judgments. Local path strings in historical JSON or coverage declarations identify original artifacts, not repository links. The substantive comparison evidence itself is included here; recreating source extraction or rerunning generation is outside this bundle.

## Resolve source and candidate identity

The [original source manifest](source-manifest.json) records case ID, public SEC document URL, accession, report period and candidate/generator/full-text hashes, plus recovery and incorporated-exhibit metadata. It is copied unchanged from the retained package. In a finding, first identify its case, then select that manifest entry:

- F labels identify lines in the retained full-filing text representation.
- G and X labels identify the retained generator excerpt and XBRL evidence, respectively.
- S labels identify the table-text recovery supplement.
- E labels identify NVO's incorporated annual-report exhibit, whose separate public URL and hash are in the manifest.
- Candidate paths identify A or B and the payload/structured representation in that case's retained candidate packet. The inventory and prior JSON preserve the relevant quoted text and exact paths.

These are packet line labels, not HTML line numbers or web anchors. Full packet files are not bundled, and no local-path link pretends otherwise. A fresh checkout can inspect the quoted allegations, opposing checks, final decisions and public source identity; independently checking every cited line against the exact rendered packet requires that retained packet. Fetching current SEC HTML alone does not certify byte-equivalence to the retained rendering.

## Integrity and limits

[Final Fable review hashes](fable-review-file-hashes.json) identify 56 final review files. [The original Codex freeze](codex-freeze.json) identifies the original independent review files; it is an integrity record, not a claim every frozen file is bundled. [Copy hashes](COPY-HASHES.json) records source-artifact identifiers and SHA-256 values for 13 unchanged copies. The three current detailed Markdown reports are adapted for durable navigation and are not represented as byte-identical originals.

All JSON parses, and copied-file hashes were verified against the retained originals. Hash integrity does not prove a reviewer's reading, source completeness, quote relevance or analysis correctness. Seven Fable cases remain partial, Amazon retains its S14 range ambiguity, and AAPL A is excluded from blind comparisons. Neither original reviewer count is an adjudicated global defect rate. No unseen acceptance, retrospective refresh or release authorization is implied.

The [top-level reconciliation](../../fable-quality-reconciliation-2026-09-09.md) and [execution ledger](../../beta-to-scale-execution.md) retain implementation ordering and subsequent release evidence.

## Subsequent coverage map

The [material coverage map](material-coverage-map.md) links original material IDs to remaining intervention and the [acceptance checklist](../../quality-residual-acceptance-2026-09-09.md). Final AAPL tax severity is material but mitigated; the earlier minor narrowing remains historical. This adapted later map is not one of the unchanged COPY-HASHES.json artifacts.
