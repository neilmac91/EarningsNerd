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
read by a string or a constant, the props taken through a declaration's array and `Object.assign`
were planted beside them, ahead of a review. Its review of `9643b93` then turned the other way, to two
look-alikes the widened read flagged: a style map's `className` and a helper handed another object
beside a call handing it the props; so the field counts only when its receiver holds the props, and
a helper's parameter is bound at the call being read alone; its review of `d55931f` two more, a helper
handed the className it never returns and `Object.assign` with a style map after the props, so a
same-file helper's call reads what it returns alone and the last source that sets a `className` wins;
and its review of `2f988e9` three more in the same two readers, so a rest parameter's member read by
an index is that argument alone, and an object's `className` is read property by property, last
first, spreads of sources opened; and its review of `69d1137` three more there, a key written as a
constant, a value reached through an alias and a negative `at()` index, so one reader reads a
className wherever it is written, the attribute's value and an object's key's alike, and a rest
member is counted as `at()` counts, from the end too, each argument a spread's length could leave at
the place read; and its review of `056a071` two more, a spread before the rest's own place and an
`at()` index with a fraction, so every argument a call hands is read by the places a spread could
leave it, a fixed parameter's and a rest's alike, and an index is read as the runtime reads it; the
rest of that family was planted ahead of its review, an index held by a constant or read through
`length - 1` and the rest taken apart by a destructuring, so a name a destructuring gives is read
through `bindingOf` wherever it is bound; its review of `6ce9969` one more, a spread of a tuple read
as any length, so a call's arguments are laid out by the lengths the checker knows; and its reviews
of `36313a7` and `c04bb70` five more in that reader, a key nested in a helper's pattern, an alias of
a parameter read at every call, a rest tail read whole, a default read without its steps and a union
of tuples read as a range, so every value is read at its steps with the calls kept, and a spread's
lengths are the set its type allows; and its review of `ec660d9` three more, a hole below an open
tuple length and a rest parameter or a rest tail aliased by a destructuring, beside a `const` tuple
written into before it is spread, so a spread's lengths keep their holes, its members are read at
each place it could cover, and every name, literal, field and same-file call on the way is read with
the calls kept, a value met inside a helper's call carrying that call to its reader; and its review
of `0e223cb` three more in the layout, so a const array is opened while the file never writes into it
nor reorders it, whatever its type, the type no stand-in for what the file does to it; and its review
of `c5ec172` one more, a call that changes nothing read as a write, which the gate keeps as it fails
closed, and taking it found that the opening rule asked only what the file does to the array under
its own name, so an array handed on whole, to another name, a function, a callback that takes it or a
call that returns it, is now one the file may change unseen. A gate widened
finding by finding needs its look-alikes planted with each copy, or the next review names the false
positive. A context a read carries holds only where every path to a value carries it: the readers kept
the calls through a name and dropped them through a destructuring, a literal, a holder's field and a
helper's returned holder, so the misreads came one path at a time until each value carried the calls
it was met inside. A promise that the file never changes a value holds only over every name the value
reaches: the opening rule read the array's own name, and the misses came through each name it was
handed to. Companion to
`arch-structural-gates-over-prose-rules.md`, which says to build the gate; this one says how wide to
build it.

**Recurrence (2026-10-14, #1288)**: the voice gate's record promised sentence case on "headings,
card and dialog titles, button labels and meta titles", while the spec read h1 to h3, four title
props and two button tags. The founder's probe (a ModalHeader child, a CardTitle, a SecondaryHeader
title, two links styled by `buttonVariants()`, an h4, an aria-label) stayed green, and the live
"Cookie Preferences" dialog title was never counted. The fix read the record's words as the gate's
extent: every heading level, the title components, any element whose className reaches the button
factory, and the components found to render their children or title into one of those, found by a
fixed-point pass over the tree instead of a hand list. Write the record's sentence from what the
gate reads, and name the rest as review-checked.

**Recurrence (2026-10-14, the Copilot's links)**: rule 2 read every component the app renders.
Fixing the Copilot's links, which had waited on the founder's call, found the prose links' rule in
`app/globals.css` setting sage at rest by `@apply` on every link in the filing reader, the summary
and the analysis narrative, where a scan of components never looked. A rule about ink holds wherever
ink is set: rule 2 now reads the stylesheet, and reads the fields the server and the model write
figures into by their declared type. Its first list of those fields was five names long, and the
next review named a metric row's formatted figures outside it; so rule 2 classifies every field the
API types declare that can hold a string, an array of them included, a figure field or a word field,
and fails one it has not classified. A gate keyed on a list of names holds only when a test makes
the list exhaustive over its domain.

**Recurrence (2026-10-15, route metadata)**: `frontend/tests/unit/routeMetadata.spec.ts` (#1312) read
a title or a description only as a typed literal and walked `page.tsx` and `layout.tsx` alone. The
literal reader failed #1299's description, a template over the period caps `lib/planLimits.ts`
mirrors from config, and the literal it asked for would have failed #1299's lockstep gate, so
whichever PR landed second went red; the walk let a noindex `layout.ts` take every company page out
of the index with all 132 tests green. The spec now imports each module and checks the metadata it
exports as Next evaluates it, and walks every page and layout under the extensions Next serves
(next.config.js's `pageExtensions`, else Next's default), with a `.ts` layout planted in its
self-check. A gate over a framework's files reads the file names the framework reads, and a gate
over a value reads the value, not the way one file typed it. An evaluated value is the test
environment's value, though: the review of `7b330a22` found a flag-conditional title the literal
reader had refused passing once evaluated, so a gate that evaluates must also refuse a value an
environment read reaches (`41fa85a2`). The post-merge review of 2026-10-16 found that refusal reading
only a title member's own initializer; it now follows every way a page sets a text (a spread, a name
assigned or written into after its declaration, each state a generated page returns) to the binding
in scope, and the evaluated robots and card are held to the literal's reading.

**Recurrence (2026-10-16, the post-merge review of #1291, #1299, #1310 and #1312)**: reviews cut
short before the four merged found eight brand gates reading less than their rules or their headers,
each shown by a probe that left the gate green: a whole file skipped (`lib/planLimits.ts`, for its
two mirror lines) after the plan lines moved into it; an exemption keyed to a heading's words that
took every icon on it, inside it or on a second heading with the same words; an option scan keyed to
`<option>` beside a rule about every choice the form offers; a date lint keyed to one callee
spelling and one direction of D-033; a JSX reader that joined a count to the word ending the block
before it; a stylesheet reader that needed the `;` CSS lets a block's last statement drop; a password
check that took any `autoComplete` as forwarded and followed one component's callers. A skip or an
exemption is as wide as the thing it exists for and no wider: pin it to that line or that site, let
each entry take one find, and have the scan assert it read the file it used to skip.
The review of that PR (#1370) then found a widening passing a form main failed: the reader that keeps
the words apart where JSX drops a line break no longer joined a count whose hyphen ends one element to
the unit opening the next (`<b>10-</b>` then `<b>year window</b>`), which main's joined reading
failed. Probing every widening in the PR for the same found seven more: a module named planLimits.ts
outside lib/ taken as TRIAL_DAYS's own, an `<option value={prefs.x}>` taken as a control's state, a
serverApi call in static metadata taken as a generated page's data, a template read only in its
expanded readings and no longer with each substitution a name, a PasswordField read only through the
forwarders a caller hands in, copy composed so a slot's text ran into the count, and a reasons reader
keyed to HTTPException beside main's scan of every `detail="…"`; and a cap on a template's readings
dropped the rest silently. A widening adds a reading and keeps the old one beside it (both scanned, a
find in either reported once), the old gate's failing form is planted beside the new ones so the spec
fails if the old reading goes, and a reader that caps what it expands fails loudly at the cap.
The next round's reviews found the fixes widening one side of a pair and leaving the other: the date
lint read a helper's key written as a template but not a field's, the trial reader held TRIAL_DAYS's
declaration to lib/planLimits.ts but took its import from any module named planLimits (and the flag's
from any module at all), and the preference scan read a field from `checked` and `value` alone though
its rule is every field the form reads. A fix to one side of a pair (a declaration and its imports, a
helper's key and a field's key, the read side and the save side) widens the other in the same commit.
And a negated selector attribute holds for every node that lacks it: `[value.name!='x']` matched a
destructuring that keeps the name with a default, whose value has no name; pin the node's type first.
Round four's review found the neighbours of round three's forms again (a save helper in `useCallback`
beside the arrow in a const, a spread beside a prop, a default whose left side is a pattern), so the
round closed the family rather than the instances. The root cause was a reader that knew a function
by one syntax; the fix lists the language's forms and reads each: a function declared, held, wrapped
in any call, an object's method, a hook's return, handed on as a prop or an argument; the value moved
by a const, a key, a prop, a spread, an argument, a return or a context. What stays out of reach (another
module, a class component, React state or a ref, a computed key, call/apply/bind, an array of
functions) is named in the spec's header and planted as a gap the self-check asserts unread, so the
limit is pinned rather than silent. And the round-three rule went to every negated selector attribute
at once, five of them, not the one a reviewer named.
Round five's review (Codex on 77b306f6) found a reader that searched a value instead of evaluating it:
`autoComplete={reset ? 'new-password' : 'off'}` passed the password scan because one literal in it named
a valid kind, so the field was judged by its best branch. A value is judged by every alternative it can
render (each branch of a condition, `&&`, `||` and `??` as the language takes them, a template's every
part, a const, an object's entry, a same-file function's returns), every alternative must pass, and a
form the evaluator cannot read fails loudly with the form. The round closed that reader's family, then
probed the spec's other readers with the same forms and found both short: the forwarding follower knew a
component by its declared name alone (an alias, a wrapper, a loader, an import under another name, a
call and `createElement` went unread), and the length reader read a ternary in a slot as a gap. A family
closed in one reader is probed in its neighbours in the same round.
