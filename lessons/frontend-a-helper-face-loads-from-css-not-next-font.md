# Load a one-glyph helper face with a plain @font-face in globals.css, not next/font/local

Date: 2026-10-25   Area: frontend

**Context**: The analysis figures draw a true minus through "EN Figure Minus", a one-glyph face that maps
Geist Mono's U+2212 outline to U+002D (`unicode-range: U+002D`), so the DOM text, copy and the Excel export
keep the hyphen-minus. Loaded first with `next/font/local` in `app/fonts.ts`, it broke nine unit specs that
render the layout: next/font's loader is a build-time transform, and under vitest the import resolved to a
module whose default export is not a function.

**Rule**: A face that only patches glyphs of a font next/font already loads goes in `app/globals.css` as a
plain `@font-face` with a `unicode-range`, its file under `public/fonts/` with its licence beside it
(`OFL.txt`), and leads the family stack in `tailwind.config.js` ahead of the next/font variable. Keep
next/font for whole families, where its preload and size-adjust matter.

**Evidence**: `frontend/app/globals.css` (the `EN Figure Minus` rule), `frontend/public/fonts/` (the woff2
and its `OFL.txt`), `fontFamily.figure` in `frontend/tailwind.config.js`, pinned by
`frontend/tests/unit/designSystemDoneGate.spec.ts` (the figure stack is the minus face, then exactly the data
stack, and globals.css declares the face) and, in a browser, by `document.fonts.check` in
`frontend/tests/e2e/analysis-layout.spec.ts` "analysis phone marks".
