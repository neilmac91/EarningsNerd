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
