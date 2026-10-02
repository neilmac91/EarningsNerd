# Put every module that composes Tailwind classes under a content glob

Date: 2026-10-02   Area: frontend

**Context**: `lib/financialTone.ts` `directionChip` composes the gain/loss/flat chip borders
(`border-gain-light/20`, `dark:border-loss-dark/20`, …) and the flat tint (`bg-flat-light/10`).
`tailwind.config.js` `content` scanned `pages/ components/ app/ features/ hooks/` but not `lib/`,
so those classes were never generated. The What Changed chips and the AuthShell chip rendered with
the default gray-200 border and the flat chip had no tint. Nothing failed: lint, typecheck, unit
tests and the build all stayed green. `text-gain-text` and `bg-gain-soft` still worked only because
other components happened to use them too, which hid the gap. It was found by the design-v3
pre-merge review, and the gap was older than that series.

**Rule**: Any module that composes Tailwind class strings outside JSX (tone maps, variant
factories, recipe constants) must live under a `content` glob that covers its extension. A new
directory of shared code goes into `content` in the same PR. Don't treat "the class renders
somewhere else" as evidence: a class shared with a scanned file only works until that other use
goes away.

**Evidence**: `frontend/tailwind.config.js` (`./lib/**/*.{js,ts,jsx,tsx}`);
`frontend/tests/unit/designSystemDoneGate.spec.ts` ("tailwind content scans every module that
composes classes") runs Tailwind's own extractor over every unscanned app module and fails on any
hyphenated or variant class it finds. It also builds production CSS and checks that every
financialTone class is emitted. With the `lib/` glob removed, both tests fail. With the glob
restored, the build emitted exactly 11 more rules: the 8 chip border/tint classes plus the 3
`text-*-dark` classes in `directionTextOnDark`, an export with no consumer that was then removed.
