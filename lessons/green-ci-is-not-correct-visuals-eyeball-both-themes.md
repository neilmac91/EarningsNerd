# Green CI is not correct visuals — review the preview in both light and dark before done

**Area:** design-system · **Date:** 2026-06-23

Every visual regression this round (brown heading, clashing gradients, invisible cards, blue info
box) passed typecheck/lint/build/tests and was caught only by the user looking at the preview.

**Rule:** for any visual/theme work, "tests pass" is necessary but not sufficient. Review the
deployed preview in **both light and dark** (or get a preview review) before declaring done.
