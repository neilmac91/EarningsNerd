# E3 completion audit and engineering decision — 22 September 2026

**Accept the returned E3 verdict evidence as complete; do not enable attribution deletion or claim improved quality.** Both candidate corpora contain 70 validated judgments. Candidate 1 has 44 negative verdicts and candidate 2 has 39, compared with 38 and 42 in the retained E2 controls. Corrected KO remains 70/70 with 41 negatives. The two Coca-Cola-specific draws in the corrected KO corpus are distinct from that whole-corpus rate.

The four transport attachments reconstruct a 27,927,235-byte ZIP with SHA-256 `281095aa83f560ded61961c09479f9b9d917947c21ffac887be338d729019ed6`. All four outer archives and payload hashes, the combined hash, ZIP CRC and 712 inventory entries verified. The returned 11 supplemental files are identical to the delivered package; all 155 prior stage files remain byte-identical. A fresh local copy of the pinned original bundle verifies 818 immutable files. The original STOP, rejected AAPL FAIL, ledger and reconciliation record are preserved; no completed slot replaces the failed AAPL directory.

Using the trusted local supplement and five pinned frozen judge files, the audit rebuilt packet/request bindings and validated all 210 KO/E3 judgments against the original rows. All supplemental readout rows and judge objects agree with those originals and validated slot outputs. There are exactly 53 and 70 successful new harness ledger entries, no new failed entry, no new STOP and no pending invocation. These are local evidence checks; remote account identity, remote sealed-file readbacks and untouched E8 guard state are reported evidence, not direct observation here.

| Corpus | Complete | Negative | G2 | G3 | G4 | G5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| E2 control 1 | 70 | 38 | 2 | 14 | 23 | 22 |
| E2 control 2 | 70 | 42 | 2 | 12 | 25 | 24 |
| E3 candidate 1 | 70 | 44 | 1 | 15 | 24 | 23 |
| E3 candidate 2 | 70 | 39 | 0 | 11 | 23 | 27 |

Codes count affected outputs, once per code; columns overlap. Candidate 1 also retains one uncoded AAPL failure reason. E3 pooled negatives are 83/140 versus E2's 80/140; G4 is 47 versus 48 and G5 is 50 versus 46. These separately generated outputs repeat the same 35 filings, so this is descriptive evidence, not 140 independent trials or a causal comparison. The earlier manual E3 prospective-drop review (5 correct, 4 unsafe, 17 unresolved) independently prevents activation. The historical corpora do not test the later strict verifier/passage safeguards in PR #937.

## Canonical files and corrected metadata

Use `extracted/readouts-supplement/e3-candidate1.json` and `e3-candidate2.json` for current complete E3 results, backed by their slot files. The files under `readouts-final/` are preserved **September 21** reports (16/70 and 0/70), despite the directory name; their nulls do not mean current missing judgments. Originals remain untouched.

The candidate-1 accounting file labels all 70 as `new_this_session`; the correct continuation split is 16 preserved + 1 reconciled unchanged FAIL + 53 new. Its `observed_cli_processes: 71` and derived one-retry count combine historical and incomplete monitor coverage, not a complete current-call census. The prose receipt reports 55 candidate-1 and 70 candidate-2 continuation CLI calls. We independently matched **54 + 70 = 124 observed processes** to their ledger windows; candidate-1 slot 018 completed before its counter began. Two observed second attempts belong to slots 037 and 045. Thus **125 continuation calls are reconstructed/attested, with one initial-slot coverage gap**; exact CLI accounting is not fully independently closed by process sampling. The 123 harness invocations are fully ledger-bound. E3 calls are separate from E8's shared ceiling.

Candidate 1's all-output maximum summary input is **35,645 characters**, not the prose receipt's 28,242; the machine accounting file has the correct maximum. Candidate 2's maximum is 34,006; both have excerpt maximum 260,154 and XBRL maximum 22,500. All are below frozen caps 100,000 / 400,000 / 40,000. Each corpus has 70 retained excerpts, 64 XBRL channels and 4 statement-evidence channels; all 70 judgments report complete input.

## Next actions

1. E3 semantic judging is complete and retain the no-activation/no-improvement decision. Preserve source-confirmed JPM/ASML/AMZN owner-transfer cases as development evidence; do not substitute keyword deletion for source-owner judgment.
2. Prepare one bounded formula-first label correction for code-computed period-end return ratios, preserving arithmetic and applicability. This addresses a naming collision, not the causal-prose residuals. Separately keep E7 held until every structured/section channel is bound to the frozen archive; a retained primary document alone is insufficient.
3. Prepare a separate E8-only continuation that understands the reviewed AAPL reconciliation while retaining the original shared guard. Founder confirmed on September 22: **“No additional E8 judging or probes.”** Retained conservative charge remains 287 of 601, leaving 314 calls for 160 missing judgments. Fable must still confirm the sole persistent remote guard and complete original accounting; initialization is not performed here. Retry needs can exceed the remaining ceiling, so partial completion is possible. E1 remains optional and outside this next handoff.

Machine evidence: `transport-audit.json`, `integrity-audit.json`, `recomputed-summary.json`, `invocation-audit.json`, and the per-stage validated-slot records retained with the original local archive (raw corpus/slot files are not duplicated in Git). Descriptive comparison and source hashes: `summary.json` and `residual-triage.md`. No new judge/provider call or generation was performed for this review.
