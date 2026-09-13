# Citation source attribution — local handoff, 2026-09-13

The retained AAPL supplemental citation contains only the sales row while its attached sentence names sales and gross margin. The primary numeric chips are correct. This change clarifies what a text source check proves, preserving every answer, marker, excerpt, link and viewer action. It does not repair semantic support or change backend verification/grounding metrics.

`citationVerification.ts` owns the shared copy: verified numeric sources show “Numeric source verified”; matched text sources show “Excerpt found in filing”; unmatched citations remain “Cited”. Both the inline popover and Sources list explicitly explain that locating the quoted passage does not verify every claim in the answer. The footer now counts matched sources and source checks. DESIGN_SYSTEM.md is reconciled at its exact affected contract paragraph, with no theme/token changes. Existing citation-kind detection remains the API's marker/section-ref convention, not a newly authenticated provenance discriminator.

Feature `45a0a61fcd9b50a074ca4e151d66aa0dea546a29` passed the full committed frontend gate. Lint (`outputs/citation-frontend-lint2.log`) and TypeScript (`outputs/citation-frontend-tsc2.log`) exited zero. Full Vitest log `outputs/citation-frontend-vitest2.log`:

```text
 Test Files  106 passed (106)
      Tests  593 passed (593)
   Duration  31.79s (transform 4.90s, setup 6.53s, import 117.10s, tests 15.99s, environment 57.53s)
```

The unchanged `npm run build` exited zero; log `outputs/citation-frontend-build3.log`:

```text
✓ Compiled successfully in 7.9s
✓ Generating static pages using 7 workers (27/27) in 1339ms
  Finalizing page optimization ...
```

One invariant proof distinguishes text matching from numeric-source attribution while preserving both chips. The existing CopilotMessage test file now renders the retained mixed AAPL shape, checks both source labels, exact excerpt, untouched source links, keyboard-focused popovers and source-scope explanation. Mutation `acbc8f7177afe8da6145ceb40884d87c1ea8dc9a` deliberately treats all verified text citations as numeric sources; log `outputs/citation-attribution-mutation.log`:

```text
 Test Files  1 failed (1)
      Tests  1 failed | 14 passed (15)
   Duration  2.44s (transform 133ms, setup 64ms, import 1.57s, tests 177ms, environment 526ms)
```

Restoration `ceddc5359b1b640ebcee7893becab50206ed8a1d` has the exact full feature tree `83e117a9c41490da3f9e5dea54de8eefe2c0c2f1`. Restored committed log `outputs/citation-attribution-restored.log`:

```text
 Test Files  1 passed (1)
      Tests  15 passed (15)
   Duration  2.47s (transform 146ms, setup 53ms, import 1.59s, tests 195ms, environment 528ms)
```

The first committed full run caught an ordinary AskCopilotRail test pinned to the old footer (592 passed, 1 failed); its existing positive and not-disclosed absence expectations were updated while retaining all stream/navigation assertions. No locked anchor was edited. Dependency setup initially stalled reading old worktree files; only this task's copy was terminated, and unchanged manifests were installed in `/private/tmp/citation-ui-deps` with Node22.14.0 and isolated npm cache. A sandbox-only install attempt could not resolve the registry. Network-enabled locked installation succeeded. Next/Turbopack rejected an external dependency symlink before compiling, so freshly installed dependencies were copied into this worktree and the normal build reran successfully, without changing Next config or the lockfile. The successful build used network for existing next/font downloads; no Sentry release/source-map auth token was supplied. Earlier failed logs are retained, not substituted for final green evidence.

Self-review refutations: unchanged citation payloads and existing navigation tests refute loss of primary/source links; the mixed-source test plus scoped helper refute a generic verified label surviving in either changed UI entry point. Code still makes no semantic entailment decision. Root's independent review and deployed preview in both themes remain pending, including long-label/popover fit on narrow screens. No screenshots or visual acceptance are claimed. No push, PR, model assessment, live account action or production flag change occurred. Root owns publication and release sequencing.


## September 13 independent-review correction

The initial wording gave a numeric assurance based on a section-label convention. Backend `_verify_citations` accepts model-supplied section labels, and `_resolve_citations` renumbers both real numeric facts and text sources. Requiring an F# marker would therefore misclassify actual numeric citations too. The bounded frontend correction now labels every verified citation “Source match found” and states “A source match does not verify every claim in the answer.” Existing visual grouping, answers, chips, excerpts and links remain unchanged. The regression includes an ordinary text citation with an XBRL-prefixed section label, plus a real reindexed numeric fact; neither receives a stronger kind-dependent assurance.

This supersedes the earlier numeric/text wording and mutation interpretation, preserving the original evidence record. The one new invariant is scoped source attribution rather than whole-answer verification. Its final committed proof will replace the earlier proof's interpretation, not claim an additional independent invariant. Root is addressing the separate expanded-popover placement issue; full frontend gating waits for that layout correction.

Neutral feature `01492a7deb9f7741bced40fa0fac51862ede05bc` passes the focused committed attribution test: 15 passed in 2.71s (`outputs/citation-attribution-neutral-feature.log`). Its single updated invariant proof changes the shared scope from limited source matching to whole-answer assurance. Mutation `764f13efc8118457a45fb005c4d3690acb6a59a2` fails the visible mixed-source regression (`outputs/citation-attribution-neutral-mutation.log`):

```text
 Test Files  1 failed (1)
      Tests  1 failed | 14 passed (15)
   Duration  2.62s (transform 153ms, setup 69ms, import 1.64s, tests 195ms, environment 608ms)
```

Restoration `f5e502e345132a47b2164c0048c5632eb49d64b5` is byte-identical to the complete feature tree `d1278a4c718d1f2eb756d5d9326bca053e925c89`. Restored focused gate (`outputs/citation-attribution-neutral-restored.log`):

```text
 Test Files  1 passed (1)
      Tests  15 passed (15)
   Duration  2.68s (transform 168ms, setup 67ms, import 1.70s, tests 213ms, environment 601ms)
```

These are focused controls on committed state with Node22.14.0, not a replacement for the final full frontend gate after root's layout/preview adjudication. No publication, model call or account action occurred. The application tree is handed back to root unchanged after restoration.


## September 13 viewport correction

Root's read-only browser measurement confirmed the neutral card clipped above the viewport: citation 9 card top −67, bottom 245, height 312 with chip top 253 and viewport height 863. Placement now measures the actual card before paint, clamps its bounds to an eight-pixel viewport margin, and bounds the whole card's width/height with internal scrolling. Scroll events from the card or its excerpt no longer dismiss it; surrounding-page scrolling and resize still do. Portal, focused access, viewer highlight and original-source links remain unchanged.

The new viewport-fit invariant has an integrated component control using the observed dimensions plus a narrow/short viewport with oversized content. JSDOM does not render layout: its geometry shim supplies natural content size and max-size behavior, then asserts the component's actual final bounds and reachable scroll/link/highlight behavior. This is an offline control, not a substitute for root's final real-browser acceptance.

## September 13 runtime evidence correction

The follow-up agent's PATH prefix referenced a nonexistent `~/.nvm/versions/node/v22.14.0/bin`, so its neutral-scope/viewport focused checks and later lint/tsc/Vitest commands actually inherited Node18.20.8. Those outputs are genuine but the preceding claim that those follow-ups used Node22.14.0 was incorrect. `/usr/local/bin/node --version` directly confirms v22.14.0. No publication occurred. The required committed checks and the same two invariant proofs will be re-established under the verified `/usr/local/bin` runtime; the earlier logs remain retained and are not final Node22 gate evidence.

Default, escalated and network-permission build attempts failed at Turbopack's local worker port binding; they are not successful build evidence. No application/configuration/dependency changes were made to work around those environmental failures.

## Final Node22 verification and handoff

The directly verified runtime is `/usr/local/bin/node` v22.14.0 with npm10.9.2. The final application head `1f4bdf110fe758aace29e8e1d91b47722ef0ecd6` has tree `ce56956a705c4ad4a8df0dcdfe7aa7ee17dcad14`, identical to corrected feature `1bfd4cba6528d8c3373197326da51d231a6b27b0`. Only this dated evidence record is appended afterward.

Final full lint and TypeScript exited zero (`outputs/citation-node22-final-lint.log`, `outputs/citation-node22-final-tsc.log`). Full Vitest (`outputs/citation-node22-final-vitest.log`):

```text
 Test Files  106 passed (106)
      Tests  595 passed (595)
   Duration  51.06s (transform 5.43s, setup 9.29s, import 203.59s, tests 18.99s, environment 91.54s)
```

The final unchanged `npm run build` passed at that exact head under Node22 after archiving only generated `.next` to `work/citation-next-failed-20260913` and using the previously successful launcher. The preceding worker-port failures remain environmental failures; the exact cause was not established, and successful rebuilding does not prove cache corruption. A independently performed the successful build; root verified its result. Full log: `outputs/citation-final-build-fresh-next.log`.

```text
✓ Compiled successfully in 8.8s
✓ Generating static pages using 7 workers (27/27) in 1614ms
  Finalizing page optimization ...
```

Exactly two final invariants/proofs are retained for the final implementation; the earlier Node18 attempts and superseded wording remain historical evidence above. For source-match scope, mutation `f6bdb1dc756358c7728886813a36ab8ff71dac8b` falsely claims every answer claim is verified. The mixed-source/model-labelled-XBRL control fails; restoration `7128b59635e2606bd284cf3fd708ffad9509f78d` restores the full feature tree byte-identically. Logs: `outputs/citation-node22-scope-red.log`, `outputs/citation-node22-scope-green.log`.

```text
 Test Files  1 failed (1)
      Tests  1 failed | 14 passed (15)
   Duration  2.65s (transform 159ms, setup 70ms, import 1.66s, tests 194ms, environment 610ms)

 Test Files  1 passed (1)
      Tests  15 passed (15)
   Duration  2.64s (transform 156ms, setup 60ms, import 1.68s, tests 210ms, environment 576ms)
```

For viewport fit and reachable source actions, mutation `bf8cc56cae7d231be9e6c2eae4023374ecfe2bfc` restores the fixed-height placement heuristic. Both the observed clipped geometry and oversized narrow viewport fail. Restoration `1f4bdf110fe758aace29e8e1d91b47722ef0ecd6` restores the full feature tree byte-identically. Logs: `outputs/citation-node22-viewport-red.log`, `outputs/citation-node22-viewport-green.log`.

```text
 Test Files  1 failed (1)
      Tests  2 failed | 3 passed (5)
   Duration  2.51s (transform 85ms, setup 74ms, import 1.60s, tests 131ms, environment 598ms)

 Test Files  1 passed (1)
      Tests  5 passed (5)
   Duration  2.35s (transform 84ms, setup 68ms, import 1.46s, tests 135ms, environment 595ms)
```

All eleven locked anchors match main `5c050cc3d7efabe9360927abf5aecb214f9bc34c` byte-for-byte (`outputs/citation-labels-locked-anchors.json`); diff whitespace checks pass. Independent review and two-refutation findings are in `outputs/citation-labels-independent-review.md`. Both scoped findings are corrected. Root's actual-component visual evidence is `outputs/citation-labels-root-visual-review.md`: the previously clipped card is now top 279 / bottom 591 / height 312 inside an 863 px viewport; light/dark and 320 px labels/scope were checked, along with keyboard viewer highlighting and the original link. This is a local Vite harness with fallback fonts, not a signed-in Vercel assessment or exact production-font fit. The unchanged long XBRL tag link can still overflow a narrow source row; this pre-existing limitation and the underlying supplemental-citation entailment defect remain outside this PR. No backend changes, model calls, publication or production settings occurred. Root owns PR publication and subsequent deployment/preview acceptance.


## September 13 short-viewport reachability correction

PR review found that whole-viewport clamping let a tall portal cover its own trigger in the 320 × 260 control (card 8–252, trigger 128–146). Portal z-index makes this a real pointer obstruction; a JSDOM `fireEvent.click` bypasses browser hit-testing and did not refute it. The corrected placement chooses a side that fits, or the larger available side, and bounds the whole scrollable card to that side with an eight-pixel trigger gap. Existing viewport controls now assert non-overlap after hover, including both edge placements. Browser hit-testing remains a separate root acceptance step. This extends the existing viewport-fit/reachable-actions invariant; its single mutation proof will be re-established on the final source rather than counted as a third invariant.
