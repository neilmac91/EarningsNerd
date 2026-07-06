# Eyeball the deployed preview in both themes before declaring visual work done

Date: 2026-06-23   Area: frontend

**Context**: Every visual regression that round (brown heading, clashing gradients, invisible cards, blue info box) passed typecheck/lint/build/tests and was caught only by the user looking at the preview.

**Rule**: For any visual/theme work, "tests pass" is necessary but not sufficient. Review the deployed preview in both light and dark (or get a preview review) before declaring done.

**Evidence**: Brown heading, clashing gradients, invisible cards, blue info box — all green on typecheck/lint/build/tests, all caught only on the preview.
