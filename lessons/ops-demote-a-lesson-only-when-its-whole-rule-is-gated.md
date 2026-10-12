# Demote a lesson from session reading only when its whole rule is machine-gated

**Date:** 2026-10-07 · **Area:** ops / agent workflow

## Context

#1118 cut session-start reading by moving lessons whose rule "is enforced by a gate" out of the
sections agents read. Two of the ten were only partly gated: `frontend-busy-controls-stay-focusable`
says in its own rule (h) that the AST scan cannot see post-success flips, unmounts or a busy flag
under another name, and `frontend-native-modal-dialog-makes-body-portals-inert` has only rules (c)
and (e) covered by `dialogAllowlist.spec.ts`. The independent review caught both; an agent told to
skip them could have shipped a keyboard or focus failure that users would hit while every gate
stayed green. The test that cites a lesson proves the clause it tests, not the lesson.

## Rule

- Before marking a lesson "enforced by a machine gate", read the lesson's own **Rule** and
  **Evidence** sections and list each clause against the gate that checks it. One ungated clause
  keeps the lesson in session reading; note the partial gate in the index entry instead.
- Prove the gate on the bad case for the clause you rely on (plant it, run the gate, restore). A
  gate that reads `git ls-files` needs the mutation staged, or it passes vacuously.
- Record the clause-to-gate mapping in the PR body, not only "gated by X".
- Name the gate file in the index entry (`— gate: \`path\``); `test_every_demoted_lesson_names_an_existing_gate`
  fails when that file does not exist, which is the mechanical half of this rule.

## Evidence

- #1118 review finding S6 (2026-10-07) and the fix in `ea054a55`; `lessons/README.md`
  "Enforced by a machine gate" section and the two Frontend entries marked "partly gated".
- `frontend/tests/unit/busyControlsStayFocusable.spec.ts`, `dialogAllowlist.spec.ts`,
  `testHomesAllowlist.spec.ts` (the `git ls-files` case).
