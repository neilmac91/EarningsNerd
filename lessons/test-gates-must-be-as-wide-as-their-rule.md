# A gate narrower than its rule is worse than no gate — evaluate the source, don't text-match it

Date: 2026-09-13   Area: test

**Context**: PR #850 landed the two gates CLAUDE.md rule 12 was missing. Five separate
review passes — one of mine, four from Codex — found seven defects in those gates and
nothing else. Every one was the same defect: the gate checked a strict subset of what its
rule covers, so it was green while the rule was violated:

1. The §12 legacy-token scanner filtered to `.ts/.tsx/.js/.jsx/.css/.md`, but §12's grep is
   `grep -rnE '…' app components features`, which reads every non-binary file under those
   directories. It exempted `features/analysis/demo/demo-analysis.json` — exactly the kind
   of demo payload that carries color and font strings.
2. `JS_TEST` listed `mts` and `cts` but not `mjs`/`cjs`, so a repo-root `orphan.spec.mjs`
   left all five test-home assertions green.
3. The font half checked a fixed table of four stacks and three vars, so a stack added by a
   later theme change was never looked at.
4. After (3) was fixed by enumerating keys with a regex, that regex matched only bare
   identifiers — a valid quoted key, `'display-alt': ['Arial', 'sans-serif']`, left all 17
   assertions green with a literal-first stack in plain violation of §12.
5. Both walks skipped directories by name. `build` was on that list and is NOT gitignored
   here, so a committed `frontend/build/orphan.spec.mjs` was invisible — `node_modules` and
   `.next` were only skipped correctly by coincidence of also being gitignored.
6. The next/font check was `expect(layout).toContain("variable: '--font-inter'")`. Rename the
   live option to `--font-inter-v2`, leave the old name in a comment above it, and the gate
   stays green while every stack in Tailwind and `globals.css` points at nothing.
7. The `:root` matcher read commented-out declarations as active: wrapping `--font-heading`
   in `/* … */` left all 17 assertions green while the browser defined no such variable.

This is more dangerous than having no gate. A missing gate is a known hole; a narrow gate
reports "enforced" and stops anyone looking.

**Rule**: Three sub-rules, each learned the hard way above.

*Ask the source of truth rather than approximating it.* `git ls-files` is the exact set of
files in the repo; a hand-written skip list is a guess at what git already knows, and it is
wrong the moment someone commits a directory whose name you happened to list. Likewise
`createRequire(import.meta.url)('../../tailwind.config.js')` gives the same
`theme.extend.fontFamily` object Tailwind consumes, so quoted keys, computed keys, spreads
and helpers are covered for free and no regex needs widening again. Text-matching is sound
only where the format forbids the ambiguity — CSS custom properties cannot be quoted or
computed, so `globals.css` stays a regex.

*Match only code that is running.* A matcher that reads comments will accept a declaration
someone switched off, or a stale name someone left behind. Strip comments first, and be
quote-aware about it, since `//` inside a string is not a comment.

*Then the general form.* When you write a gate, state the rule's exact extent first and make the gate cover
at least that, then prove the boundary with a mutation planted in the part you most suspect
is exempt — a data file, an unusual extension, a quoted key — not in the obvious middle.
Prefer a denylist of what genuinely cannot apply (binaries) over an allowlist of what you
happen to have thought of; an allowlist silently narrows every time the codebase grows a
new file type. And when the thing being checked is a **programming language**, evaluate it
instead of matching its text: `createRequire(import.meta.url)('../../tailwind.config.js')`
gives the same `theme.extend.fontFamily` object Tailwind consumes, so quoted keys, computed
keys, spreads and helpers are all covered for free, and no regex needs widening again.
Text-matching is sound only where the format forbids the ambiguity — CSS custom properties
cannot be quoted or computed, so `globals.css` stays a regex.

Corollary for the anti-vacuity floor: assert the scanner actually found things (>100 files,
>100 tests). A narrow gate and a broken walk look identical from the outside — both green.

**Evidence**: [#850](https://github.com/neilmac91/EarningsNerd/pull/850) —
`frontend/tests/unit/designSystemDoneGate.spec.ts` and `testHomesAllowlist.spec.ts`;
commits `b7eac32c` (binary denylist), `07817b2b` (mjs/cjs + key enumeration), `35262bef`
(evaluate the config), and the follow-up that replaced both filesystem walks with
`git ls-files` and made every matcher read a comment-free view of its source. Each fix carries a
before/after proof: the pre-fix form passed with the mutation present — `Tests 17 passed
(17)` for the quoted key, `5 passed (5)` for the `.mjs` orphan, `22 passed (22)` for the
tracked `build/` orphan, the renamed font variable and the commented-out `--font-heading`
all at once — which is what makes "the gate was narrower than the rule" a measurement
rather than a claim. Companion to `arch-structural-gates-over-prose-rules.md`, which says to
build the gate; this one says how wide to build it.
