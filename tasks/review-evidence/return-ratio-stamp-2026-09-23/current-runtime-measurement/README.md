# PR942 current-runtime measurements

The report receipts preserve actual identities, provenance, flags and all measured warnings.
The fresh p control and q2 candidate share 70 identities and exact grounding/source projections;
q3 has the full 105 identities required by the existing pin tool. No generation was repeated in
this audit and no judge was called. The prompt-change trigger makes the q3 deterministic
pin eligible, but the backend floor is unchanged until the matched Fable contract-2 comparison
clears q. The [prospective snapshot](q-baseline-proposal.json) is a proposal only: its citation-fidelity
reference would move from 0.9648 to 0.9532, so it must not be applied ahead of that semantic
disposition. PR942 stays draft.

- p control: run 36272463033, 70 scored, zero errors/retries.
- q2: run 36276521637, 70 scored, zero errors/retries.
- q3 pin: run 36276551360, 105 scored, zero errors/retries. Report SHA-256
  `3e0f758432ff85b899bafdbb795bd80cb8d6784cc12debd598fd6d2a2cd5499e`.
- [Matched comparison](p-v-q2-comparison.md). Its deterministic perfect hard metrics do not
  establish semantic quality; standing untraceable-dollar warnings remain.

Full reports and raw logs remain in workspace `outputs/ratio-release-2026-09-27/` and their GitHub
Actions artifacts. The matched judging packet is under 30 MB. No E7/E8 ledger or acceptance
criteria changed. Production remains p until an explicit release decision and verified deployment.
