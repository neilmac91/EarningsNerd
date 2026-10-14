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

*Score the gate on the rule's forms, not only on its sites.* A mutation proof on the site you
just fixed shows the gate catches that site; it says nothing about the other forms the rule can
take. Before a record says what a gate holds, plant one case for each way the rule can be broken
and one for each look-alike that must pass, mark each flag or clean, run the gate over them and
record the score. Name in the gate's header what stays out of reach, so the record claims only
what the score shows, and keep the header and the cases in step: a form the rule forbids that the
gate passes is planted as a gap, never as a look-alike, and each gap the header says the cases mark
has one. For a gate that reads code (a source scan, an AST walk), keep the planted cases as the
gate's fixture and score them in its own spec, so CI reruns the score on every change and the next
review extends the cases instead of starting over. When a review finds one form of a claim the gate
already makes that it misses, probe the claim's whole family before fixing that form, and take the
family from the language, not from the forms the reviews have named: for a value, every way a name
gets one (a declaration and each assignment, destructuring and its default, a loop's variable, a
parameter at each call of its function, a callback however it is handed over, and what the code
puts in it after making it), and the framework's calls that move one (React's `Children`,
`cloneElement` and `createElement`). A reader that gains one syntax per review is matching forms,
not following the value, and the fix is a reader that follows it. And when a gate has more than one
check over the same code, give them one walk: a check that follows a value through the bindings
while its sibling reads only the syntax around it leaves the sibling as narrow as the first reader
was, and a value the gate must recognise rather than read (a component's children) rides that walk
as a mark, not a second walk of its own.

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
rather than a claim. [#1251](https://github.com/neilmac91/EarningsNerd/pull/1251)'s rule 2 in
`frontend/tests/unit/brandCopyRules.spec.ts` (sage never colours a number) passed its mutation proofs
on every site it fixed, and its records said no sage element anywhere rendered a digit; scored on
50 planted forms at `cc2df56`, it missed 15 (a Badge variant, an opacity modifier, a selected state,
a wrapper component, a block-bodied callback, SVG text, among others) and failed 3 that must pass
(a literal "10-K", a primary Button or a neutral Badge inside sage text). After it asked the
components for their colours and followed sage through variants, states and components, it scored
50 of 50. The review of `88f801c`, with the forms its fixes turned up, widened the probe to 74; at
`88f801c` rule 2 misread 17 of them (sage given to a component where it is used, a comparison read
as a number, a size or `text-inherit` read as a colour, a visited or focused sage count, a control
holding its count in a span of its own ink, a const another function declares, among others), and
fixed it named every form that breaks the rule and passed every look-alike and the known gap. The
next two reviews asked for the score to run in CI and added 39 forms, among them a chained `&&` the
fix had stopped reading, and their fixes turned up 3 more; the forms became the spec's fixture,
`frontend/tests/unit/fixtures/brandRule2Forms.tsx`, scored on every run. Read against its own
header, that fixture still marked a fiscal year held in a string (`FY{y}`) clean though the gate
leaves it to review, planted no index name held in a string though the header named one, and the
header missed a date or an index name written in words; all three are now gap forms. Codex's
reviews of `8a946b2` and `ee581e3` then each found one more form of a claim the header already made
(a class const inside a conditional; a mapped array's element), and a probe of the second's family
at `19ed8fb` found six more ways a literal's value reached the JSX unread (a destructured element, a
renamed one, a tuple's member, a nested field, a `.slice()` chain, a template's substitution).
Codex's review of `19ed8fb` found the same of a class, one destructured from a map, and the round's
lens found a const holding a keyed read (`const config = MAP[s] ?? MAP.x`) that both readers lost.
One resolver, a single walk through any chain of consts, fields, indices, destructuring and map
callbacks, replaced the readers written per form; the gate at `19ed8fb` misread the 21 forms planted
for it. That probe took its family from the chains the reviews had named, and Codex's review of
`c9bd846` found the next form among the ways a name is bound: a map's callback held in a name
(`labels.map(render)`). Probed from the binding forms instead (a named callback however it is held,
the other array methods, a call's arguments, a rest parameter, a default, a reassigned `let`, a
loop's variable), and then by the round's lens (a helper's return in a component's inherited ink, a
number handed to a parameter typed wider, a value held in what a call returns, and a recursion that
ran for minutes), the fixture gained 100 forms, and the gate at `c9bd846` misreads all 74 of them
that break the rule. An index of each file's calls, binding a parameter at every call of its
function and every array method it is handed to, replaced the map-only rule, and a binding met again
on the walk now ends it. Codex's review of `f00c4be` then found the count-control check still taking
a control's sage from the syntax around where it is written: a control held as JSX and rendered
under a sage parent passed, while the text check followed the same JSX to where it renders. Probed
through the same binding forms and a component boundary, 25 such forms broke the rule unread at
`f00c4be`; one walk now yields what an element renders in its ink, its texts and its elements, for
both checks, and a component's summary says whether it renders such a control in the ink it
inherits. The re-review of `c9bd846` had also named a rest element in a binding pattern, which the
walk abandoned; it is read as the whole it is taken from. Codex's review of `f5526d3` then found JSX
that `Children.toArray` normalizes read by neither check: the walks followed the language's array
methods but not the framework's, and the value walk read an array of JSX only by its type. Probed
across React's child utilities, the lists a call keeps or a push fills, and the ways a component
reaches its children, the family broke the rule in forms no walk read; the three walks now read a
list, and those utilities, through the one resolver. The review of that fix found the component
summary still finding a component's children by a walk of its own, narrower than the resolver (a
`Children.map` held in a const, a helper handed them, `forEach` filling an array) and wider where it
should not be (a row's field named children); the resolver now carries the children from the props
as a mark, and the summary's walk is gone. Its second review found two more forms of claims the
header made: children handed by a shorthand (`{ children }`), which the walk resolved inside an
object it read but not where a clone's props hand the name over, and a spread of sources to
`Object.assign`. A second session fixing the same finding at the same time (`d3f1522c`) read `flat`,
which this probe had missed; listing the family from the language instead, every array method that
returns its receiver's members, found five more (`toSpliced`, `with`, `splice`, `fill` and
`copyWithin`), and `pop` and `shift`, which return one. In all, 99 forms broke the rule unread at
`f5526d3`, and it failed 4 look-alikes. Codex's reviews of that session's fixes (`d3f1522`,
`1dd291d`, `c00788f`, `4e44658`) named in turn `Children.only`, an alias of `Children` or a helper
destructured from it, `Children` destructured from React itself, and `React['Children']`; the gate
reads all four without a rule for each, since it names a utility by the declaration the checker
resolves its callee to, not by its spelling. A guard kept the checker to callees under a utility's
name, for speed, and so left one called through a key, or held under a name of its own, unread;
measured idle, it saved about a tenth of a second, so every callee is now asked. Codex's review of
`99f0380` then found the count control's one-source check blind to a label delegated to a same-file
component (`<a><CountLabel>See all {n}</CountLabel></a>`, the span's pointer sage inside the
component): the control's own classes and its label span were covered, the component's were not, so
the check now reads a component that renders its children in a pointer-sage element as the label's
classes; its review of `63b7144` named the same label held in a name before it renders, which the check
now reads through the held-JSX walk, as the ink checks already did; and its review of `2e946f7` the
same label behind `&&` or in an array, so the walk reads the containers on the way, as the ink checks
do. Round twenty-seven read the rest of the family in that walk: a label component's own count,
self-closing too, which Codex's review of `820b5a0` named, a nested label component and a className
it forwards. Its review lens found the walk's cost in a cycle of components: a summary read more than
once per element multiplied the walk, so the walk now reads each element's summary once. A control's
own-ink check still reads the components inside it again, so a cycle of six controls, each rendering
the next twice, still takes about 9 s, against 16 s before. Codex's review of `b36e741` then named the
forwarded className under another name (`({ className: cls })`), which a spelling check missed, so the
check resolves each identifier a className reads to its declaration; its review of `ffa0227` the same
destructuring of the props kept whole (`const { className: cls } = props`), so the binding is followed
to the parameter through the variables holding it, a rest of it and an object spreading it, the next
two forms of that family planted before a review named them; and its review of `2a18988` the name
filled by an assignment (`let cls; ({ className: cls } = props)`), so the name is read through every
value the file gives it, as the ink check reads a variable, and a same-file helper returning it was
planted next, ahead of a review; its review of `2a5ec9c` the name filled through an array
(`[cls] = [props.className]`), so the steps an assignment leaves are walked into the value by the
ink check's own walk, whatever the path; and its review of `3a15929` a helper that destructures the
argument it is handed and a rest target in an assignment, so a helper's parameter holds what the file's
calls hand it and a rest target holds the whole, as the walk already read a declaration's; the key
read by a string or a constant was planted beside them. Companion to
`arch-structural-gates-over-prose-rules.md`, which says to build the gate; this one says how wide to
build it.

**Recurrence (2026-10-14, the Copilot's links)**: rule 2 read every component the app renders.
Fixing the Copilot's links, which had waited on the founder's call, found the prose links' rule in
`app/globals.css` setting sage at rest by `@apply` on every link in the filing reader, the summary
and the analysis narrative, where a scan of components never looked. A rule about ink holds wherever
ink is set: rule 2 now reads the stylesheet, and reads the fields the server and the model write
figures into by their declared type.
