# PR #808 first Copilot failure: independent review

The retained first paid run 34688285251 completed and scored all 18 attempts without execution errors; 17 passed and ASML run 0 failed the deterministic citation veto. This is a real failed acceptance check, but its generic “not found verbatim” message misdescribes the two offending excerpts. Both are present verbatim and fail the unchanged minimum-length safeguard. No provider call, rerun, repository edit, or scorer change was made for this review.

The artifact is `work/pr808-flash-copilot/copilot-fidelity-34688285251/copilot-eval.json`, execution source `d4f5532a105b7a21661a421788e6cdc8e1156255`. It requests `deepseek-flash`; its aggregate `actual_model` is null, so this report does not invent an observed provider model identity. The affected identity is ASML / `0001628280-26-011378` / `us-gaap-sales-net-income-2025` / run 0. Its numeric recall, figure coverage and fact adjacency are all 1.0, with no contradictory currencies or invalid provenance. Revenue €32,667.3 million and net income €9,609.4 million are correctly backed by the two tool citations. The extra rounded KPI restatement adds the failed text citations.

## Confirmed finding: prompt and verifier contract mismatch

**Must fix for this PR's failed check:** `backend/app/services/copilot_service.py:99` asks for the SHORTEST contiguous span, one sentence and at most approximately 30 words, but never communicates the verifier's minimum. `backend/app/services/provenance_service.py:30` sets the actual minimum to **24 normalized characters, not 30**. At lines 125–129, `verify_excerpt_in_text` rejects shorter needles before membership checking. The service itself uses that same verifier at `copilot_service.py:394`; the evaluator independently uses it in `backend/evals/copilot_scorers.py:50`.

| Actual excerpt | Normalized length | Exact source offset (zero based) | Result |
| --- | ---: | ---: | --- |
| `€32.7bn\nTotal net sales` | 23 | 16,399 | Present, below 24; rejected |
| `€9.6bn\n29.4%` | 12 | 21,185 | Present, below 24; rejected |

Two independent refutations were attempted. First, exact raw substring searches and the actual normalization routine both find each excerpt in the retained input, refuting fabrication or missing source text as the cause. Second, an offline replay of the exact verifier function extracted from main `65b9243f` and candidate `131523498c6858b7c516ba4690cb0f718a0b7f64` rejects both spans identically. The verifier source SHA-256 is identical on both refs (`5045b4619d58778f892cc320f10a0410cc148bb5a7ccbc43d35c2bf45cb8a2e1`). Thus the failure survives as a pre-existing prompt/verifier incompatibility encountered in this run, rather than proof that cash/debt metadata broke ASML revenue or net income. Reproduction evidence is `work/pr808-copilot-failure-reproduction.json`.

The alternative that this is only an advisory scorer quirk was also refuted: the product's retained final citations are already `verified: false`, with the unverified base filing URL. The evaluator faithfully retains that trust boundary. A stochastic first occurrence is not evidence of a flake or permission to rerun without a fix.

## Bounded remedy and verification

Reuse the existing canonical 24-character threshold in the actual Copilot system instruction. Require a contiguous excerpt with at least that many characters after normalization/whitespace folding, while preserving the shortest sufficient supporting span, no stitched cells or ellipses, and reuse of an existing `[F#]` marker for tool-provided figures. The instruction must not encourage padding a quote with unrelated adjacent KPI cells: the second failed excerpt lacks its own metric label, and merely adding nearby numbers would not establish support for the claim. A complete relevant sentence or existing authoritative fact marker is preferable.

This is a reasonable narrow confirmed-finding fix, not a guarantee that the model will obey. Keep the verifier threshold, actual matching rules, citation visibility and evaluator veto unchanged. Do not delete the failed citations from the retained artifact, enable W3-7 snapping, alter flags, or relabel this first run as passing. A second paid assessment after committed full gates and review is justified as the authorized confirmed-finding fix round; its actual result remains the acceptance evidence.

The existing `test_contiguous_citation_instruction_reaches_actual_service_messages` in `backend/tests/unit/test_copilot_live_regressions.py:58` checks the real `_build_messages` system instruction, including contiguity and reuse of `[F#]` markers, but does not check the minimum. Extending this request-wiring test is more meaningful than another isolated constant-equality test. One mutation removing the delivered minimum requirement should make that gate fail. Existing shared provenance tests already reject tiny excerpts (`test_provenance_service.py:93` and the short parenthetical near line 536) while accepting a real ASML sentence and rejecting a changed number near lines 543–546. Retain the exact current ASML short-span replay as rejection evidence; do not change those expected safeguards to accept it.

## Diagnostic issue and scope limits

**Should fix:** `backend/evals/copilot_scorers.py:259` says unverified excerpts were “not found verbatim” even when the reason is insufficient length. Refutation by direct substring inspection establishes presence; refutation through the shared verifier establishes the length rejection. A neutral “could not be verified” message would be accurate without relaxing the gate, although changing it also requires updating the existing exact diagnostic assertion in `test_copilot_live_regressions.py`. This diagnostic wording is separable from acceptance and need not broaden the prompt slice.

This review covered the failed answer, its two tool results, four citations, retained source neighborhoods, actual main/candidate verifier replay, product consumer, evaluator and directly relevant existing tests. It does not certify the full ASML filing, all 18 answers' semantic correctness, provider model identity, or the separate 52-attempt summary assessment.

## Read-only review of the committed correction

Reviewed commit `d32c150ecf5e694841813f12d9cefcd8ce1eae71` using `git show`; no tests or processes were run in the candidate worktree. No surviving must-fix or should-fix finding in this correction. It imports the canonical floor, delivers it through the existing system-message f-string, asks for a longer contiguous source span without padding/paraphrase, and preserves the prior support, no-stitching and existing fact-marker instructions. The existing request-wiring assertion now checks that delivery. The evaluator change only corrects diagnostic wording and preserves the actual pass/fail decision.

Two independent refutations of a weakened trust boundary were attempted: the diff does not modify the shared verifier or any numeric/citation scoring decision, and the existing retained stitched-quote regression still requires a hard veto with only its diagnostic string updated. Two independent refutations of ineffective delivery were attempted: the instruction remains in the actual service f-string with the imported canonical value, and the extended test reads `_build_messages` output rather than a detached prompt constant. These are code review conclusions; the parent owns mutation proof and full-gate execution.

The natural-language instruction describes whitespace collapse while the verifier also folds typography and punctuation spacing. That remains a small model-compliance limitation, not evidence that this correction weakens verification; a comfortably long complete supporting span avoids borderline counts. The second paid run must independently demonstrate acceptance, and any new failure must remain visible and be investigated.
