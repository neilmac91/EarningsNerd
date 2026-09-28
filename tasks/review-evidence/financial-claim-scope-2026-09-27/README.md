# financial-claim-scope-2026-09-27 — evidence index

Engineering evidence for `tasks/financial-claim-scope-2026-09-27.md` (branch
`codex/wave3-financial-claim-scope`, implementation commits `ce72481`, `ffdf371`, `554d3c7`, `595344c`, `acee6d9`, `d32e4e8`, `1667523` and the eighth-round repeated-ID commit). Not an E7 brief or a Fable verdict.

- `reconciliation.md` — each historical candidate-r defect: locator, exact quotes, this engineer's two refutation attempts, disposition.
- `offline-replay-70.json` — the owner replayed over all 70 retained outputs (report SHA verified), regenerated after each review round; from the fourth round with the filings' source documents (hashes inside), from the fifth under proposition-bound and from the sixth under finite-proposition ownership: 1 slot changed, 7 figures restored, 8 abstained with reasons, per-row audit.
- `retained-package-hashes.json` — attachment zip, manifest and per-packet SHA-256 values used.
- `balance-before-push.json` — DeepSeek balance read (free GET) before any push.
- `run-ledger.json` — every attempt: network reads, local gates (including the aborted one), both mutation faults; no local model calls.
- `local-gate.log.txt`, `local-gate-first-pass.log.txt` — full backend gate tails.
- `mutation-proof.log.txt` — the counted deliberate-fault/restored proof; `mutation-proof-superseded.log.txt` — the weaker first fault, retained, not counted.
- `local-gate-p1p2.log.txt`, `local-gate-round3.log.txt`, `mutation-proof-round3.log.txt` — second- and third-round gate tails and the third-round counted fault/restored proof.
- `ownership-measure-round3.txt` — read-only comparison of the round-2, strict top-down and final ownership rules over the 35,714 demonstrated cells in the 70 retained excerpts.
- `balance-before-round3-push.json` — DeepSeek balance re-read before the third-round push.

Gate and proof tails carry a `.log.txt` suffix because the repository ignores `*.log`; the earlier rounds'
`.log` copies never reached the branch (the tails were quoted in the handback and shipped in the checkpoint
archives) and are committed here under the new suffix, byte-identical.
- `local-gate-round4.log.txt`, `mutation-proof-round4.log.txt` — fourth-round gate tail and the counted fault/restored proof.
- `balance-before-round4-push.json` — DeepSeek balance re-read before the fourth-round push.
- `local-gate-round5.log.txt`, `mutation-proof-round5.log.txt` — fifth-round gate tail and the counted fault/restored proof (row-label binding removed).
- `hosted-run-36386298431-eval-job.log.txt` — the fourth-round eval job log (peak tariff, USD 0.357), the run that took cumulative hosted telemetry to about USD 1.017.
- `local-gate-round6.log.txt`, `mutation-proof-round6.log.txt` — sixth-round gate tail and the counted fault/restored proof (introduction grammar disabled).
- `hosted-run-36392603589-eval-job.log.txt` — the fifth-round eval job log (the authorized measurement under the USD 1.65 ceiling; peak tariff, USD 0.354).
- `hosted-run-36403130259-eval-job.log.txt` — the eighth-round eval job log for head `5936fc4` (the authorized measurement under the USD 2.10 ceiling; peak tariff, USD 0.349; 70/70 scored, PASS).
- `hosted-run-36404908264-copilot-job.log.txt` — the Copilot filing-fidelity job log for head `5936fc4` (root's ready-for-review check; 18/18 cases, 35 calls, USD 0.015).
- `local-gate-round7.log.txt`, `mutation-proof-round7.log.txt` — seventh-round gate tail and the counted fault/restored proof (context identity reduced to its period end).
- `local-gate-round8.log.txt`, `mutation-proof-round8.log.txt` — eighth-round gate tail and the counted fault/restored proof (repeated context ID resolving to its last definition).

## Checkpoint 9 integration

Codex verified all 36 checksum-listed files in the September 28 checkpoint archive and applied the held `f1766fc` patch to the existing documentation PR [#1005](https://github.com/neilmac91/EarningsNerd/pull/1005), preserving Fable's authorship. The two added hosted job logs remain byte-identical to the supplied artifacts. Their 36 timestamp-only trailing-space lines are retained as an explicit raw-evidence exception to the whitespace check; other changed files pass it.

The [ingestion receipt](checkpoint9-ingestion.json) records provenance and independently recomputed accounting: USD 1.735815 of the USD 2.10 ceiling, with billed cost unknown. Two narrow ledger clarifications distinguish required tagged filing-source ownership from auxiliary cached XBRL metrics, and zero generation cost from unassessed infrastructure cost. The engineer's held-commit description is historical to delivery; no further action from that session is required.

The chief engineer's [release receipt](../progress-2026-09-28/pr992-release.json), [service/job readback](../progress-2026-09-28/pr992-wif-release.json) and [public serving check](../progress-2026-09-28/serving-receipt.json) cover the later production verification. They do not prove that historical cached rows have been refreshed or that broader JPM, FIGS and PLTR quality defects are resolved. No historical drain or model evaluation is requested by this accounting integration.
