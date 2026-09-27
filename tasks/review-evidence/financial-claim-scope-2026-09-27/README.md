# financial-claim-scope-2026-09-27 — evidence index

Engineering evidence for `tasks/financial-claim-scope-2026-09-27.md` (branch
`codex/wave3-financial-claim-scope`, implementation commit `ce72481`). Not an E7 brief or a Fable verdict.

- `reconciliation.md` — each historical candidate-r defect: locator, exact quotes, this engineer's two refutation attempts, disposition.
- `offline-replay-70.json` — the owner replayed over all 70 retained outputs (report SHA verified): 1 slot changed, 7 figures restored, 8 abstained with reasons, per-row audit.
- `retained-package-hashes.json` — attachment zip, manifest and per-packet SHA-256 values used.
- `balance-before-push.json` — DeepSeek balance read (free GET) before any push.
- `run-ledger.json` — every attempt: network reads, local gates (including the aborted one), both mutation faults; no local model calls.
- `local-gate.log`, `local-gate-first-pass.log` — full backend gate tails.
- `mutation-proof.log` — the counted deliberate-fault/restored proof; `mutation-proof-superseded.log` — the weaker first fault, retained, not counted.
