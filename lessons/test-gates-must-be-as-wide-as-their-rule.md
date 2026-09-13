# A gate narrower than its rule is worse than no gate — evaluate the source, don't text-match it

Date: 2026-09-13   Area: test

**Context**: PR #850 landed the two gates CLAUDE.md rule 12 was missing. Four separate
review passes — one of mine, three from Codex — each found the same defect in those gates,
and nothing else. Every time, the gate checked a strict subset of what its rule covers, so
it was green while the rule was violated:

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

This is more dangerous than having no gate. A missing gate is a known hole; a narrow gate
reports "enforced" and stops anyone looking.

**Rule**: When you write a gate, state the rule's exact extent first and make the gate cover
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
commits `b7eac32c` (binary denylist), `07817b2b` (mjs/cjs + key enumeration) and `35262bef`
(evaluate the config). Each fix carries a before/after proof: the pre-fix form passed with
the mutation present (`Tests 17 passed (17)` for the quoted key, `5 passed (5)` for the
`.mjs` orphan), which is what makes "the gate was narrower than the rule" a measurement
rather than a claim. Companion to `arch-structural-gates-over-prose-rules.md`, which says to
build the gate; this one says how wide to build it.
