# financial-claim-scope-2026-09-27 — evidence index

Engineering evidence for `tasks/financial-claim-scope-2026-09-27.md` (branch
`codex/wave3-financial-claim-scope`, implementation commits `ce72481`, `ffdf371`, `554d3c7`, `595344c` and the fifth-round proposition-bound commit). Not an E7 brief or a Fable verdict.

- `reconciliation.md` — each historical candidate-r defect: locator, exact quotes, this engineer's two refutation attempts, disposition.
- `offline-replay-70.json` — the owner replayed over all 70 retained outputs (report SHA verified), regenerated after each review round; from the fourth round with the filings' source documents (hashes inside), from the fifth under proposition-bound ownership: 1 slot changed, 7 figures restored, 8 abstained with reasons, per-row audit.
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
