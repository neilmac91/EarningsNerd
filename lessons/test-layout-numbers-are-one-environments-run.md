# Accept a layout measurement on its invariants, never on equal pixels; one pinned browser still measures differently on another machine

Date: 2026-10-11   Area: test

**Context**: #1197's briefing prompt asked the next agent to reproduce both harness runs "record for record in
the pinned browser", after a records lens called "within a few pixels" too loose. The founder's review of `c7fc65e`
reran the unchanged harnesses in that same browser (Chromium 141.0.7390.37 on linux x64), with matching source,
fixture, font and install hashes. It measured the `97293e7` table at 2,044 px against the recording's 2,076, and
all 20 geometry records differed. Six prototype card heights came out at 206 px against 238. The Track A
verification had measured 2,044 px too. Text widths depend on the machine as well as the browser (its font
setup most likely; the cause was not isolated), so the criterion could not be met, while every layout invariant
still held.

**Rule**: Write a measurement harness's acceptance as invariants: zeros (overflow, clipping, occlusion), counts,
booleans and a defect's sign. Give any numeric tolerance a measured spread as its justification. Record the
run's environment and note the differences beside it. Never require equal pixels between machines, even with
the browser pinned. Never rewrite a committed recording to match another machine; check from an `--out` run
instead. A browser pin guards against one known drift (another Chromium version), not against the machine.

**Evidence**: `tasks/analysis-redesign-2026-10/astra-prompt.md` (Track A's done line);
`docs/design/analysis-data-notes-redesign-2026-10.md` §11 ("Font-dependent widths");
`tasks/analysis-redesign-2026-10/harness/browser-pin.mjs`; the founder's review on #1197 (2026-10-11).
