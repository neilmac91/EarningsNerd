# Write down the second anomaly before chasing the first — a parked finding is a lost finding

Date: 2026-09-13   Area: ops

**Context**: While preparing PR #852 I read the `overrides` block and noticed that the
`jsdom` → `undici` pin looked wrong against the jsdom 30 I was installing. I did not act on
it, because in the same minute `npm install` failed outright with
`Unable to resolve reference $postcss` and the install error was blocking everything else.

Diagnosing that took several isolation runs — a control on unmodified main, then each bump
applied alone — to establish that vitest 5 was the trigger and the self-referencing
`"$postcss"` override was the cause. By the time it was resolved and the tree installed, the
undici observation was gone from working memory. It never made it into the PR body, a
comment, or a note. Codex found it in review, and it was a real bug (see
`frontend-overrides-rot-when-the-constrained-package-moves.md`).

The failure was not the missed detail — I had already seen it. The failure was holding it in
working memory across a demanding diagnosis. A blocking error consumes exactly the attention
that would otherwise carry a parked observation forward, so "I'll come back to it" is the
one plan guaranteed not to survive.

**Rule**: The moment you notice a second anomaly while diagnosing a first, write it down
before continuing — into the PR body's "Not in this PR" / open-questions section, `tasks/todo.md`,
or a scratch file, whichever the work already has. Not into working memory, and not into an
intention to revisit. The cost is one line; the cost of losing it is a reviewer finding your
bug, or nobody finding it.

Then, before opening a PR for review, re-read that list and resolve each entry explicitly:
fixed, deliberately deferred with a reason, or checked and found harmless. An unresolved
entry blocks the PR going out, exactly like a failing gate.

This one is prose and stays prose. The gate-able half of the #852 miss is covered by
`overrideDirectionGate.spec.ts`; no gate can check whether something you noticed reached a
written list, so the discipline has to carry it — which is why the rule is "write it now",
not "remember to check later".

**Evidence**: PR #852 review thread; the `$postcss` isolation table in that PR's body
(which recorded the diagnosis in full while omitting the observation made alongside it);
`lessons/frontend-overrides-rot-when-the-constrained-package-moves.md`.
