# Authored-guidance unit correction — September 12, 2026

**#825 is held as a draft after both summary rounds failed scoped functional acceptance. The second local correction is fully gated and reviewable, but unpublished. Both authorized paid rounds are used; another assessment requires explicit approval. No merge or production release is claimed.** First-round artifacts remain separate evidence. Copilot acceptance does not establish authored-guidance behavior.

The preceding documentation release #824 merged as `8dd880d977dd8484acb50466dacbe1fcc9e62052` at 15:11:21Z. Main CI `34701471681` passed; deploy job `103574296028` reported “No backend changes - skipping deploy.” at 15:14:34.4069220Z. The latest verified production revision remains #823's `earningsnerd-backend-00333-56s`.

## First implementation and actual failure

[Local verification](authored-guidance-local-verification.md) and [independent review](authored-guidance-units-independent-review.md) preserve the first implementation's gate and proof. Head `21c72a120395fb3640d3343b3593b1ca53159302` passed 2,927 tests with 29 warnings in 98.75s, exit 0, including Ruff/Bandit, performance and all four PostgreSQL lanes. The [offline #823 comparison](authored-guidance-retained-evidence.json) corrected two supported COST strings across 52 retained outcomes; it was not fresh model acceptance.

The actual first #825 summary exposed a missing punctuation variant. [Functional review](pr825-first-guidance-review.md) and [exact finding](pr825-first-guidance-finding.json) show COST run 0 retained unscaled `$6,500` because “fiscal 2026 and plans to open” lacked the comma required by the target matcher. Actual final output and retained previews remained wrong. Run 1's comma form was corrected. This confirmed same-scope defect withheld acceptance even though [metadata checks](pr825-first-summary-metadata-acceptance.md), [comparison evidence](pr825-first-summary-metadata.json), [execution identity](pr825-first-summary-execution-integrity.json) and [usage conservation](pr825-first-summary-usage.json) passed their bounded checks in CI `34701847075`.

[First Copilot acceptance](pr825-first-copilot-acceptance.md) and [integrity](pr825-first-copilot-integrity.json) separately retain run `34701858130`, job `103574916014`: 18/18 under the existing six-question gate, with citation-scope/redundancy advisories. Execution synthetic `216003c75ebd13f2c704b56c56f90ffd5c56ec1b` and the first gated head share tree `8e58f1429c02ba44c9028b475556a285374b6483`.

## Corrected head and verification

The [correction review](authored-guidance-correction-review.md) and [offline first-#825 comparison](pr825-correction-retained-evidence.json) retain the narrow coordinated-continuation correction. The offline check changes exactly COST run 0 across 52 first-round outcomes, preserving other section bytes. It is not acceptance of the new generated cohort.

Corrected head `604a457c4e755e27cdf8d7f1b1ca6f403f315b38` passed Ruff/Bandit and the complete committed performance/four-PostgreSQL-lane gate, exit 0:

```text
2928 passed, 29 warnings in 95.49s
```

Log `work/authored-units-correction-gate.log` SHA-256: `8e3887a5830ee2d70fbbcf65842871fe9bd08253523049af9fe7879f0e5a718f`. The initial sandbox PostgreSQL connection denial occurred before tests and is retained separately; the complete permitted rerun supplies the pass. Second CI `34702770441` completed, but functional summary acceptance was withheld as described below. [Second Copilot acceptance](pr825-second-copilot-acceptance.md) and [integrity](pr825-second-copilot-integrity.json) separately accept run `34702770437` for 18 correct requested answers within the existing gate. One BABA 2025 answer is genuinely uncited, and AAPL/ASML have local citation-scope weaknesses; no universal citation-compliance claim follows.

Exactly one new source-proposition-to-visible-correction proof is retained. The punctuation case extends the same invariant, so the proof was not repeated:

```text
Mutation c510be6605f9c5617279db22c4d7049f9b53d319:
3 failed, 18 passed, 14 deselected, 2 warnings in 4.83s
Restoration 7125e8aef331628088b448033ac08ddbb3170b58:
21 passed, 14 deselected, 2 warnings in 4.69s
```

## Archive and remaining scope

[Archive integrity](archive-integrity.json) identifies twenty-four immutable reports/evidence files and original private paths. Matching original `work/<basename>` references resolve to these copies; large provider/source artifacts, logs and utilities remain private. The mutable PR-body draft is deliberately excluded. Earlier checkpoint wording inside copied reports is historical; this README states the current archive status.

Unsupported paraphrases, recovered/missing-source guidance, debt scope and broader comparison/causal findings remain open. The next typed numerical-relationship proposal is design-only: unrestricted analysis/program text could still restate false relations. That is an unresolved engineering boundary, not a founder decision or shipped fix. No new lock exception, production flag or universe-wide generation/replay follows from this archive.

## Second summary: functional hold and local correction

[Second functional review](pr825-second-guidance-review.md) and [finding](pr825-second-guidance-finding.json) show COST run 1 uses “The company states its current intention,” which the anchored reporting introduction rejects. Its authored guidance and actual final rendering retain `$6,500` without million. Three of seven retained previews contain the unscaled amount and none contains the correction. COST run 0 is corrected; the correct quote in another surface is not closure.

[Second metadata acceptance](pr825-second-summary-metadata-acceptance.md), [execution identity](pr825-second-summary-execution-integrity.json), [comparison evidence](pr825-second-summary-metadata.json) and [usage](pr825-second-summary-usage.json) remain valid within their distinct scope. Their passing checks do not override the functional hold.

Root prepared local correction `d19c782bf488463d93e26c33d76ded6a07cc003e`, adding two observed reporting introductions while preserving financial/source guards and the first boundary correction. Its full committed gate and independent review passed; it remains unpublished. The original invariant proof is not repeated. Both assessment rounds remain immutable; no third paid round or code push is authorized by this record. The latest verified production remains #823 revision `earningsnerd-backend-00333-56s`. A concrete additional-assessment approval can be requested only after local verification and independent review make the correction reviewable.

## Latest local correction: gated and awaiting assessment authorization

[Immutable verification](authored-guidance-reporting-verification.md), [104-outcome offline comparison](pr825-reporting-retained-evidence.json) and the [reviewable correction patch](pr825-reporting-correction.patch) preserve exact local head `d19c782bf488463d93e26c33d76ded6a07cc003e`. The patch is evidence only, not applied code in this documentation PR. The offline comparison corrects exactly the two missed strings from the two actual assessments, preserves every other section byte and is idempotent. It is not a third model assessment.

```text
2929 passed, 29 warnings in 119.95s (0:01:59)
```

Ruff, Bandit, performance and all four PostgreSQL lanes passed, exit 0. Gate log `work/authored-units-reporting-gate.log` SHA-256: `f6e4b3d7155e081365327beca60870c67dba11b594b76a938ed9d1d3f826e438`. All eleven locked anchors remain unchanged. The original proof was not repeated. #825 remains a draft at published `604a457c4e755e27cdf8d7f1b1ca6f403f315b38`; no additional code push or third paid round is approved. Only this documentation hold record is prepared for publication.
