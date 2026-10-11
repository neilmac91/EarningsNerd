# Never change the EN monogram or the wordmark; brand work composes around them

Date: 2026-10-11   Area: frontend, brand

**Context**: The brand studio's Phase 4 recommendation proposed refining the monogram's drawing
(the E and N fuse at 16px) and testing whether the N's arrowhead could read as a pen stroke. The
founder answered: "I don't want you to change the logo or monogram, I like them." The mark is three
months old, carried in the PDF and Excel exports, the emails and the app tile, and the founder's
attachment to it is itself a brand asset.

**Rule**: The EN monogram's geometry (`frontend/public/assets/earningsnerd-mark-mono.svg` and its
fixed-colour renditions) and the wordmark's composition ("Earnings" in the surface's primary ink,
italic "Nerd" in the brand accent, `components/EarningsNerdLogo.tsx`) never change. Brand work may add
arrangements (a stacked lockup, a one-colour lockup, a mask icon) that reuse the same paths and the
same wordmark rule, document clear space and minimum sizes, and choose where the mark goes; it may
not redraw a stroke, move the arrowhead, change the letter spacing of the wordmark, or recolour the
mark outside the renditions `LOGO_README.md` lists. A size at which the mark fuses is handled by
rules (use the tile, not the bare mark, below 32px), not by redrawing.

**Evidence**: founder instruction of 2026-10-11 in the brand studio session (PR #1226);
`frontend/public/assets/LOGO_README.md` ("In-app usage", "Rules");
`frontend/tests/unit/wordmarkSingleSource.spec.ts` keeps the wordmark to one source.

**Gate (partial)**: `frontend/tests/unit/markSingleSource.spec.ts` fails when any rendition (the
assets, the templates, the social card, `EarningsNerdLogoIcon.tsx`, the chart export) redraws one of
the three outlines, moves one outline (a transform of its own, an extra group, a style or class
that moves it), moves the N against the E, or stretches the mark. It reads the transform hierarchy,
not substrings: the founder's review of PR #1226 moved only the stacked logo's arrowhead and the
first version, which checked that the strings were present, stayed green. The colours, the
wordmark's composition and the small-size rule are not gated, so this lesson stays in session
reading (`lessons/ops-demote-a-lesson-only-when-its-whole-rule-is-gated.md`).
