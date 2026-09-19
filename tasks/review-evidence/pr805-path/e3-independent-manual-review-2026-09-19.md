# Independent review of corrected E3 manual evidence — 2026-09-19

**Conclusion: no blocking finding in the corrected evidence reports.** The arithmetic and bounded conclusions support retaining this study; they do not support enabling deletion or claiming an E3 quality improvement. This was a review of another agent's manual report, not a second complete adjudication of every clause.

## Arithmetic and provenance

Independently recomputed all entry categories, recorded verdicts and distinct flagged-attempt counts. Run1 has 22 flags in 18/70 attempts: 9 prospective drops (3 correct, 1 unsafe, 5 unresolved), 13 rescues (11 full-source confirmed, 2 unresolved). Run2 has 26 flags in 21/70 attempts: 17 prospective drops (2 correct, 3 unsafe, 12 unresolved), 8 confirmed rescues and 1 unknown.

Pooled: 48 flags, 26 prospective drops = 5 correct + 4 unsafe + 17 unresolved; 21 rescues = 19 confirmed + 2 unresolved; 1 unclassified unknown. Correct-drop lower/upper classification bounds are 5/26–22/26 = 19.2–84.6%; decidable-only 5/9 = 55.6% explicitly excludes 17 unresolved. Unsafe fraction is 4/26 = 15.4%; full-source rescue fraction 19/21 = 90.5%. Per-run ranges and Markdown rounding agree. No actual deletions occurred.

Verified both raw report SHA-256 values, all 48 audit records and their slot verdicts against the raw reports, all per-entry excerpt hashes, 70 scored/error-free rows per corpus, verification on/deletion off, and byte-identical corresponding excerpts across both E3 and both E2 corpora. Independently repeated the application/prompt/eval tree comparison between source 8a8065b7 and synthetic merge d59b0b13: no difference. The disclosed Sea checked-count mismatches remain distinct from matching flagged records; the proposed pre/post-binding explanation is explicitly unproven.

## Representative evidence checks

- Unsafe: run1 PDD flag19 contains “without attributing … a single driver”; full source says operating profit follows the foregoing movements. Run2 KO flag10 exactly transcribes the consolidated growth-factor table (8%, 2%, 3%, −1%, total12%); selected windows omit that table. Negation and an explicit issuer bridge independently refute equating every not_stated verdict with a correct deletion.
- Uncertain: run1 ASML flag1 uses broad “Q2 result,” while the source specifically explains above-guidance revenue and gross margin. Run2 Coinbase flag20 is a ratio/accounting interpretation whose selected windows use net revenue while the full statements supply total revenue. Keeping these scope/policy boundaries unresolved is justified.
- Full-source rescue: BABA run1 flag14 and run2 flag22 have the operating-income explanation in the full excerpt, but reconstructed selected windows begin at the driver fragment. Their correct full-source labels do not validate adequacy of the supplied request evidence.
- Unknown: run2 Pfizer flag13 has the correct SIA subject/anchor; full source retains the causal lead-in and marketing bullet, whereas selected windows contain the detached bullet. Its null manual classification correctly excludes it from both prospective-drop and rescue denominators.

## Context correction and limits

The corrected reports properly distinguish the subject field from the complete request. The regex captures explicit objects inside `attributes … to`, and build_prompt sends connective plus clause. Thus BABA run1's operating-income object and ASML's Q2-result object survive. BABA run2's “the decrease” lacks its previous-sentence antecedent; DCAI's entity anchor alone does not establish the revenue metric. Those residual limits remain honest. Prompt instructions request unknown for insufficient context; they are not deterministic enforcement.

The reports keep reconstructed passages separate from saved provider requests, omit nonexistent verifier reasons, identify manual labels as non-Fable, and make no paired causal-effect or sentence-recall claim. Regenerated claims and 17 unresolved prospective drops independently defeat an improvement claim from the lower observed unsafe fraction. No source edits, tests, model calls, cloud reads or production actions were performed for this review.

Minor presentation issue only: run2 Markdown repeats the reconstructed request-cause line for some INTC entries. This duplicates identical text and does not alter the evidence or totals.

## Reviewed file identities

- `e3-run1-clause-read.md`: `580da1333d0cf275a48fa0d308bd9840fe874e183cbce648f871c6e81a5fc7d2`
- `e3-run1-clause-read.json`: `a29e2034976be99f447a3de3b442c669dcf32ffd2bf0fb63311d513d15268538`
- `e3-run2-clause-read.md`: `c592264689fdf65229ed3007eff3e35c101a1e6ee3d7534d4774bb4081215d50`
- `e3-run2-clause-read.json`: `6530dcb4e9c64bea3eb69e623a4ae2a54ebdf759cd05175c096ad5dbf76173e4`
- `e3-pooled-clause-read.md`: `dfd9c862fee26b441075f4c62397e03bf4ca6ed608f78c7e706f9485a08183d8`
- `e3-pooled-clause-read.json`: `9147e90159653e621519795986e6c93a8327c14c940de82b4a2bc09623a16938`
