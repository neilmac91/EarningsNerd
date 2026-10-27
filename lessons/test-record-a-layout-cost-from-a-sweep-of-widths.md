# Record a layout cost from a sweep of widths at both text sizes, in CI's fonts, not from the widths a test runs

Date: 2026-10-27 · Area: testing / frontend layout

**Context.** #1686 (E220) holds the landing hero's access line at the checking line's height, so the settled invite
line sits over the rows the checking line leaves. Its records gave that cost as "20px, 40px under 200% text", taken
at the readiness e2e case's widths (320, 390, 1152 and 1440px, and 640, 1440 and 2304px under 200% text) and at chief
design's (320, 390 and 1440px, and 640 and 1440px under 200% text). A verification lens's font model put it at 80 to
120px at phone widths under 200% text. A sweep of a production build, 15 widths at the default size and 18 under 200%
text, found 40 to 120px under 200% text. The widths at each figure depended on the font: in the cloud sandbox, whose
fontconfig paints the body stack in a static Inter, 120px came at 320 and 340px and 80px at 360px, at 480 to 500px and
at 1100px; in CI's fonts (the site's Inter web font), 120px at 320px and 80px at 340 and 1024px. A second sweep, every
10px, found the compact bar changing height as readiness lands under 200% text, where no case ran (E223): 14px at 370
and 450px in CI's fonts, and a 74px drop at 390px in the sandbox's alone.

**Rule.** Before a pull request or a record states how far something moves or what space it costs, sweep a production
build:
- every 10 to 40px from 320px to the widest layout, at the default size and under the 200% text setting (Chromium's
  `Page.setFontSizes` with standard 32 and fixed 26, as `header-covers-nothing.spec.ts`'s `doubleText` does);
- in CI's fonts: in a cloud sandbox, launch the browser with the fontconfig that leaves out the Inter alias
  (`lessons/test-layout-numbers-are-one-environments-run.md`), and check with `CSS.getPlatformFontsForNode` that the
  text paints in the web font;
- served with the e2e environment at `next start` as well as at build (`WAITLIST_MODE=false`, or `/` redirects to
  `/waitlist`), each state settled before it is read (an auth check that lands between two reads moves the header too).

Record the range, the widths at its ends and the fonts it was measured in. A gate's widths prove that a case holds;
they do not bound its cost.

**Gate.** Review-checked: a figure in prose cannot be checked by a machine. The case that proves the hero line's hold
also runs at the sweep's worst phone width under 200% text (`frontend/tests/e2e/header-covers-nothing.spec.ts`,
320px).

**Evidence.** #1686: `2b123383` recorded "40px under 200% text" (`frontend/DESIGN_SYSTEM.md` §7 and
`PublicAccessLine.tsx`); its verification lens found the model's figures; the sweep's head records the measured range
and adds the 320px case. E223 in `tasks/todo.md` records the compact bar.
