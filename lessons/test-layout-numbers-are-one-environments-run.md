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

**Recurrence (2026-10-29, #1799)**: the alias now fails one of main's gates, not only a measurement. On `325e1fcc`,
`frontend/tests/e2e/reflow-200.spec.ts` fails 11 of its 205 cases in the sandbox. In CI's fonts (the fontconfig
above, where the account link's label paints in the web font, `isCustomFont` true) all 205 pass, and CI's own e2e job
passes on `4a026332`, the same frontend. Ten of the failures are the case "does not scroll sideways at 390px", once
for each route that shows the site header. E223's hold (#1694) sizes the compact bar's account link to both its
labels, "Live example" and the mode's own. In the sandbox, at 390px under 200% text, the bar's action group (that
link and the menu button) takes a second row below the logo, with the link's label on one line, and keeps it once
readiness lands and "Request invite" shows. The header is then 225px. The spec's one-row limit is the bar's tallest
item plus its padding and border, so it follows the group: 137px for that 88px group, which the 225px header fails.
In CI's fonts the group stays beside the logo, the link's label on two lines and the group 102px tall, so the limit
is 151px and the header is one row at 151px. Before the hold, the sandbox's bar took the second row only while
readiness checked, the 74px drop above; now the row stays. The eleventh failure does not involve the header: at 320px
under 200% text the cookie settings dialog breaks "authentication," inside the word, as /privacy broke
"communications," above. Before reading a sandbox failure of a layout gate as a regression, rerun the case in CI's
fonts. A case that passes there failed because of the alias. A case that still fails there is not explained by the
alias: treat it as a regression unless CI's own e2e run on the same frontend passes it, and if CI passes it, the
machines differ by more than the alias, so note that beside the run.

**Evidence**: `tasks/analysis-redesign-2026-10/astra-prompt.md` (Track A's done line);
`docs/design/analysis-data-notes-redesign-2026-10.md` §11 ("Font-dependent widths");
`tasks/analysis-redesign-2026-10/harness/browser-pin.mjs`; the founder's review on #1197 (2026-10-11).
