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

**Recurrence (2026-10-21, #1462)**: E81 pinned /privacy's "communications," as a word past reflow-200's 320px edge
under 200% text, from a measurement in the agents' sandbox (338px), and CI's runner failed the pin: there the page
fits. This time a cause is isolated. The sandbox image carries `/etc/fonts/conf.d/56-prefer-inter.conf`, which points
`-apple-system`, `BlinkMacSystemFont`, `system-ui`, `sans-serif` and five other system names at the installed static
Inter (the `fonts-inter` package), so the body stack, which leads with `-apple-system`, paints in it
(`CSS.getPlatformFontsForNode`: Inter-Regular, not a custom font), about 8% wider at 32px than the site's own Inter
web font, whose optical size there is the Display cut ("communications," 258.1px against 239px). CI's runner has no
such alias and paints the web font, as a reader off Apple's systems does; headings, whose stack leads with the web
font, measure alike on both. CI's run of the pin's expiry is the gate that caught it. To see what CI sees first, run
the browser with `FONTCONFIG_FILE` naming a copy of `/etc/fonts/fonts.conf` whose `conf.d` include points at a folder
of links to every rule but that one: `-apple-system` then matches DejaVu Sans, which Chrome declines, and the body
text paints in the web font, as on CI.

**Recurrence (2026-10-27, #1686)**: the landing hero's access line paints in the body stack, so in the sandbox it
took the static Inter (`CSS.getPlatformFontsForNode`: `isCustomFont` false). Chief design's five widths for its held
cost measure the same in CI's fonts, but the alias moved the widths where the cost reaches 80 and 120px under 200%
text, and the closed line's bands there (chief design's, 960 to 992, 1136 to 1216 and 1984 to 2048px, are the
sandbox's rows, not CI's). It also put a 74px drop in the compact bar at 390px under 200% text that CI's fonts do not
show (`lessons/test-record-a-layout-cost-from-a-sweep-of-widths.md`).

**Recurrence (2026-10-27, E223)**: the compact bar's account link now holds both its labels in one cell, so the bar
keeps the taller of their layouts. In CI's fonts that is the ready bar at every width. In the sandbox's static Inter,
"Live example"'s longest word no longer fits beside the logo at 390px under 200% text, so the held bar keeps two rows
(225px) where main's settled to one (151px) as readiness landed, and `reflow-200.spec.ts`'s one-row case at 390px
fails on every route in the sandbox while it passes there on main, which reads after readiness lands, and in CI's
fonts. Run the e2e with the CI fontconfig before reading a sandbox failure as a regression.

**Evidence**: `tasks/analysis-redesign-2026-10/astra-prompt.md` (Track A's done line);
`docs/design/analysis-data-notes-redesign-2026-10.md` §11 ("Font-dependent widths");
`tasks/analysis-redesign-2026-10/harness/browser-pin.mjs`; the founder's review on #1197 (2026-10-11).
