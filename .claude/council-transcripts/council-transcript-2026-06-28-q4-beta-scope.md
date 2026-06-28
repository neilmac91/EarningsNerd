# Council Transcript — Q4: Beta Scope & the Aha Moment (what users see)

_Run: 2026-06-28 · Source: `tasks/council-prep.md` Question #4 · Skill: `llm-council`_

Protocol: 5 advisors (parallel, independent) → anonymized peer review (parallel) → chairman synthesis.
Framed against the live/dormant product state **and** the already-decided strategic spine (#1 Wedge,
#2 Moat, #5 Distribution, #7 Dormant-feature sequencing) — this run was asked to *serve* that spine,
not relitigate it, and to concentrate on the three #4 calls. (Apple Sign-In noted as LIVE in prod.)

---

## Framed Question

EarningsNerd — beta scope & the aha moment: what a closed-beta user actually SEES, whether to surface
the "partial summary" quality badge, and the single zero-to-wow activation moment.

**Three distinct calls** (the dormant-flag ranking is settled in #7):
1. Of the LIVE-and-solid features (copilot, peer comparison, watchlist [alerts inert in beta], dashboard
   feed, search), which to SURFACE vs keep secondary — given #1 says "land on ONE report, hide the grid."
2. The **partial-summary badge**: trust-builder or credibility-killer (for first-timers AND investor
   demos) — flip / hide / conditional?
3. The single **zero-to-wow aha moment** to engineer.

Spine recap: #1 = one what-changed report with receipts (ICP: serious 10-K reader); #2 = accountability
("ChatGPT sells confidence; you sell verifiable accuracy") + the ChatGPT-catch demo; #5 = ADR teardown +
onboard onto known-good (non-"partial") filings; #7 = quality gate first (evals + `USE_STRUCTURED_OUTPUT`),
badge only after evals, alerts cron deferred (so watchlist alerts won't fire in beta).

---

## Advisor Responses (de-anonymized)

### The Contrarian

Here's where the proposed plan quietly wounds itself.

**The badge is a self-inflicted credibility wound — and "onboard onto known-good" is hiding the exact thing that proves your moat.** Think about it: your #2 is ACCOUNTABILITY. A "Partial — retry" badge on a brand-new user's first report doesn't read as "honest" — it reads as "the AI choked." First-timers have no calibration; transparency only signals integrity to people who already trust you. Worse: the badge says *the depth gap is real and the product knows it.* You're advertising your #1 weakness in beta, where impressions are irreversible. **Verdict: hide the badge entirely in beta.** Curate onboarding onto known-good filings so partials are rare, and when one slips through, fail to a quiet "regenerating…" not a yellow scarlet letter. Never let it near an investor demo.

**The deeper flaw in "land on ONE report":** the example-filing landing is a *static artifact*. A skeptical 10-K reader's first instinct isn't to admire your report — it's to test it. If the aha is something they passively watch, the wow evaporates by tab two. **Sharper aha: land them on the known-good report with the ChatGPT-catch pre-staged, then immediately invite ONE copilot question on that same filing.** The activation isn't "look what it made" — it's "I asked it a hard number and it answered with a click-through to the source span." That's your moat *experienced*, not *shown*. Copilot is the only live feature worth foregrounding; bury peer/dashboard/search, and absolutely hide the watchlist — a "watch" button whose alerts never fire is a broken promise on day one. Don't ship a button that lies.

### The First Principles Thinker

Strip it to the load-bearing question: in a beta user's first session, what has to be TRUE for the signal to be worth having? Only one thing — **one report has to land a number the user trusts more than their own reading.** Everything else is noise.

So the unit isn't "the aha moment." It's "the moment they trust a number." Engineer backwards from that.

**(1) Surface vs hide.** Surface ONE live feature: the **what-changed report with click-to-source citations** — the only one that produces a trustable number. Demote everything else. The copilot stays available but un-foregrounded (it's how they *test* trust after the report earns attention, not the opener). Watchlist, dashboard feed, peer comparison, search — actively hide. Watchlist especially: its alerts are inert, so surfacing it ships a broken promise into an irreversible first impression. A dashboard feed with no history is an empty room. Kill the grid entirely.

**(2) The badge.** A "partial" badge in session one is a credibility-killer because the report hasn't earned the right to be transparent yet — transparency about gaps only reads as accountability *after* trust exists. The first-principles move: **users should never SEE partial in beta.** Onboard onto known-good filings (#5), eval-gate first (#7), and suppress the badge in demo mode. Don't flip it, *route around it.* The badge is real and honest — just not a first-impression artifact.

**(3) The aha.** Sharpen past the example landing: the wow is **the ChatGPT-catch on a number the user can verify in two clicks** — wrong figure stated confidently, EarningsNerd's correct figure, click-through to the exact source span. That's the moment a number becomes trustable. The what-changed diff is the *reason to return*; the catch is the *reason to believe.* Lead with the catch.

### The Expansionist

**1. SURFACE vs HIDE.** Foreground exactly one thing: the report itself, with the copilot as the second beat *inside the same page*. The copilot is your single highest-ceiling "come back" surface — it's the only feature where the user's own curiosity ("but did margins actually expand?") gets answered with a click-through citation in real time. That's the moment they realize this isn't a static PDF; it's interrogable. Pre-seed 2-3 suggested copilot questions under the diff so they don't face a blank box. Keep peer comparison and search available-but-secondary (one nav link, no fanfare). HIDE the watchlist entirely in beta — inert alerts are a broken promise on first contact, the most irreversible kind. Don't ship a "Watch" button that does nothing.

**2. THE BADGE — flip it into a flex, but gated.** A "Partial" apology kills investor demos. But "Full" is a wasted opportunity. Rebrand the good state: not "Full" but **"Verified — every claim source-linked"** with the citation count ("47 claims traced to source"). *That's* your accountability moat made visible, the anti-ChatGPT in one badge. Show it only post-evals, and onboard onto known-good filings so "Partial" is nearly invisible. Suppress all badges in demo mode.

**3. THE AHA — sharpen it.** The example-filing landing is right but too passive. The wow isn't the diff — it's the **ChatGPT-catch, made interactive on the landing page**: show ChatGPT confidently stating a wrong revenue number, then your inline correction with a live click-through to the exact 10-K span. New user clicks, the source highlights, the number matches. In three seconds they've *felt* the moat instead of reading about it. That's the screenshot they send to a friend — and your single zero-to-wow.

### The Outsider

Surfacing decision: foreground exactly ONE thing — the report. A new person who already reads 10-Ks doesn't want a dashboard; they want proof you read it for them. So the first screen is a single known-good what-changed report with the ChatGPT-catch front and center. Of the live features, surface only the copilot, and only INSIDE the report ("Ask this Filing" sitting right next to a highlighted number). Keep peer comparison, dashboard feed, and search available-but-secondary (a quiet nav, not the landing). HIDE the watchlist entirely in beta — a "Watch" button that promises alerts which never fire is a broken promise a first-timer WILL notice the moment nothing arrives. Inert alerts are worse than no feature.

The badge: to a newcomer, "Partial — retry" reads as BROKEN and CHEAP, full stop. It looks like an error message, not a virtue. "Honest transparency" is founder curse-of-knowledge — nobody admires a label they have no baseline to interpret. So: onboard onto known-good filings only, so the badge is essentially never seen; suppress it entirely in demo mode; and only after evals, show "Full" as a quiet green confidence cue. Never show the word "Partial" to a first-time user or an investor. A "Regenerate" button on first contact = "the product didn't work."

The aha: NOT the diff alone. The single zero-to-wow moment is the ChatGPT-catch — "ChatGPT confidently says $X. Here's the real number, click to see it in the filing." That's the gut-punch a normal person feels instantly: a thing they trust just lied, and you caught it. The what-changed diff is the second beat. Lead with the catch; it needs zero SEC literacy to land.

"Ask this Filing" is clear enough — keep it.

### The Executor

**Surface vs. hide (call 1):** Land every beta user on ONE report URL — the example ADR what-changed teardown. On that page, foreground exactly two things: the "what changed since last quarter" diff and click-to-source citations. Make the copilot present but quiet — a single "Ask this filing" input pinned under the report, pre-filled with one example question ("Did margins improve?"). That's it. Keep search available (top nav, no promotion). Hide peer comparison, dashboard feed, and watchlist behind a collapsed "More" — watchlist alerts are inert, so promoting it teaches users it's broken on day one. Kill from beta UI: anything flagged dark (Compare, Insiders, Calendar, charts/tabs, FPI), plus the feature-grid landing entirely.

**Badge (call 2):** Nuanced, not flipped-on globally. Implement one rule: render the badge only when `quality == "partial"` AND the filing was user-initiated (not on the curated onboarding/example set, which is hardcoded known-good). On the example landing and any demo link, force `demo_mode` that suppresses the badge AND the Regenerate button. So a first-timer literally never sees "Partial" — they only meet it later, on a filing they chose, where honesty reads as integrity. One flag, two conditions.

**The aha (call 3):** The single screen to engineer is the ChatGPT-catch, inline on the example report. Don't make it a separate page. At the top of the known-good teardown, a small static side-by-side: "ChatGPT: revenue $X (wrong)" / "EarningsNerd: $Y →" where $Y is a live click-to-source link that scrolls-and-highlights the exact filing span. Pre-rendered, no live LLM call. First session: magic-link → report loads → eye hits the catch → clicks the number → watches it land on the source. Wow in under 10 seconds, zero typing.

**Cut:** the feature grid, watchlist promotion, the Regenerate button in demo, every dark flag.

---

## Peer Review (anonymized inputs)

Anonymization map for this round: **A** = Executor · **B** = Outsider · **C** = First Principles ·
**D** = Contrarian · **E** = Expansionist.

### Reviewer 1
1. **Strongest: C.** It reframes the entire problem around the load-bearing primitive — "the moment they trust a number" — and derives all three calls from it. Cleanest distinction: the catch is "the reason to believe," the diff is "the reason to return." Tightest logic, no padding.
2. **Biggest blind spot: A.** It's operationally excellent (the two-condition flag, demo_mode suppression) but keeps the aha *passive* — "watches it land." D and E correctly argue a skeptical 10-K reader's first instinct is to *test*, not admire, so the activation should pull them into one copilot question. A misses that the wow evaporates by tab two.
3. **What ALL five missed:** distribution mechanics of the aha. Every response engineers a private first-session moment, but #5 (ADR teardowns, send-to-a-friend) means the catch must work as a *shareable public artifact* — unauthenticated, pre-magic-link, screenshot-able. None addressed whether the ChatGPT-catch lives before or behind the invite gate, nor how to source a *real, reproducible* wrong-number catch (legal/credibility risk if ChatGPT's "wrong" answer isn't reproducible). They also never defined the success metric that proves activation happened.

### Reviewer 2
1. **Response C is strongest.** It reframes everything around the load-bearing variable — "the moment they trust a number" — and derives all three calls from it cleanly: catch = reason to believe, diff = reason to return. Tightest first-principles logic, no wasted motion, fully serves #1/#2/#5/#7.
2. **Response A** has the biggest blind spot. Its two-condition badge rule (partial AND user-initiated) plus a `demo_mode` flag adds engineering for a solo founder weeks from beta — the rest correctly say *route around* partial via curation, needing near-zero code. A also keeps the Regenerate button conditionally, contradicting the "never signal failure" consensus.
3. **All five missed instrumentation of the aha.** #7 says "confirm PostHog," yet none defines the activation EVENT to fire (e.g., source-span click) or a success metric for the catch. Without measuring whether first-timers actually click-to-source, the founder can't tell if the engineered wow lands — irreversible first impressions with no feedback loop. Also unaddressed: how the curated known-good ADR set gets selected/maintained, and what the second-session return hook is once the static catch is spent.

### Reviewer 3
1. **Response C is strongest.** It reframes the entire question around the load-bearing primitive — "the moment they trust a number" — and derives all three calls from it cleanly. Same conclusions as the others but with the sharpest causal logic ("transparency only reads as accountability *after* trust exists"; "diff = reason to return, catch = reason to believe"). No padding.
2. **Response E's biggest blind spot:** its "Verified — 47 claims traced to source" badge is a liability when the depth gap is the known #1 weakness. A literal claim count invites the skeptical 10-K reader to audit it, and one wrong/shallow citation detonates the accountability moat on first contact. It over-engineers a flex where C/D's "route around it, stay quiet" is safer.
3. **All five missed: who curates the known-good onboarding set, and how it stays good.** Every response leans on "onboard onto known-good filings," but none specifies the selection mechanism, how many, or that filings drift (restatements, re-summarization) — a manually-pinned set is the actual dependency the aha rests on. They also ignored the ChatGPT-catch's accuracy/legal risk: hardcoding "ChatGPT says $X (wrong)" can become stale or defamatory and needs a dated, reproducible snapshot.

### Reviewer 4
1. **Strongest: C.** It reframes the whole question around the load-bearing variable — "the moment they trust a number" — and derives all three calls from it cleanly. It correctly separates the catch (reason to believe) from the diff (reason to return), routes around the badge rather than flipping it, and is the most disciplined about hiding inert features. No wasted motion.
2. **Biggest blind spot: A.** It nails execution detail (pre-rendered catch, no LLM call, demo_mode rules) but keeps the aha *passive* — "watches it land." D and E rightly argue a skeptical 10-K reader's instinct is to *test*, not admire; A never lets them interrogate the filing themselves, leaving copilot inert as an opener.
3. **What ALL five missed:** none defined the *failure path* — what a beta user sees when their own first self-chosen filing returns partial (after the curated onboarding). The catch wows on rails; the irreversible impression is the first off-rails filing. Also unaddressed: the catch is one hand-curated example — does the wow survive when the user runs a filing where EarningsNerd has no ChatGPT-error to contrast? And no one specified how the curated known-good set is built or how many filings deep it goes before users hit the wild.

### Reviewer 5
1. **Strongest: C.** It reframes the entire problem around the load-bearing variable — "the moment they trust a number" — and derives all three calls from it cleanly. The diff-vs-catch distinction ("catch = reason to believe; diff = reason to return") is the sharpest framing produced. Disciplined, first-principles, no padding.
2. **Biggest blind spot: E.** Its "Verified — 47 claims source-linked" badge is the only answer that risks the moat: a claim count invites a skeptic to spot-check, and one bad citation on a partial filing detonates the accountability positioning. It also contradicts the demo logic it endorses. D has the best critique posture but offers no concrete badge mechanic.
3. **What ALL five missed:** the second-session retention cliff. Every response engineers the cold-open wow on a *curated* example, but a beta user's second action is to test their OWN filing — which may return a partial. Routing around the badge in session one just relocates the credibility hit to session two, where it's worse (it's their pick, not yours). None addressed what happens when the user leaves the known-good rails. Also unexamined: the ChatGPT-catch is a static, pre-staged artifact — fine as theater, but it's manufactured, not earned per-filing, and a sharp ICP user may smell the cherry-pick.

---

## Chairman's Verdict

### Where the Council Agrees

Five advisors, near-unanimous on the spine-critical calls:

- **Hide the watchlist, full stop.** Every advisor flagged it independently. Its alerts are inert (cron deferred per #7), so a "Watch" button is a promise that silently breaks on day one — the single most irreversible kind of first impression. Nobody dissented.
- **The ChatGPT-catch is the aha, not the diff.** All five converged: the catch is the gut-punch that needs zero SEC literacy ("a thing you trust just lied, and EarningsNerd caught it"). The what-changed diff is the second beat. The Outsider's framing — "lead with the catch; it needs zero SEC literacy" — is the cleanest.
- **Never show "Partial" to a first-timer or an investor.** Unanimous. Route around it via curated known-good onboarding (#5), eval-gate first (#7), suppress in demo mode. The disagreement is only about *mechanism*, not whether.
- **Foreground exactly ONE report; demote everything else.** Copilot stays available but quiet; peer comparison and search are a single nav link with no fanfare; dashboard feed is hidden (empty room with no history). The grid dies. This is #1 executed literally.
- **No Regenerate button on first contact.** A retry button reads as "the product didn't work." Suppress it in demo/onboarding.

### Where the Council Clashes

**The badge — and it's a real clash with a real answer.**

- **Hide-entirely camp (Contrarian, First Principles, Outsider):** transparency only reads as accountability *after* trust exists. A first-timer has no baseline; "Partial — retry" reads as "the AI choked." So route around it — users should essentially never see it in beta.
- **Conditional-rule camp (Executor):** render the badge only when `quality == "partial"` AND user-initiated; force demo_mode on the curated set. One flag, two conditions.
- **Flip-it-into-a-flex camp (Expansionist):** rebrand the good state as "Verified — 47 claims source-linked."

Why reasonable advisors split: the hide camp optimizes for *first impression*; the conditional camp optimizes for *honesty once trust is earned*; the flex camp optimizes for *making the moat visible*. The flex camp loses on peer review — three reviewers independently flagged that a literal claim count **invites a skeptical 10-K reader to audit it, and one shallow citation detonates the accountability moat.** When depth is your known #1 gap, you do not advertise a number that begs to be spot-checked.

**The aha — passive vs. interactive.** The Executor's pre-rendered catch ("watches it land") is operationally beautiful but four reviewers flagged it as *passive*: a skeptical 10-K reader's instinct is to **test**, not admire. The Contrarian/Expansionist/Outsider want the copilot as the immediate second beat — "I asked it a hard number and it answered with a click-through." This is resolvable, not a true clash: lead with the pre-rendered catch (zero-latency wow), then invite the interrogation.

### Blind Spots the Council Caught

Peer review surfaced four gaps that no advisor addressed — and they are the real risks:

1. **The second-session cliff (most important).** Routing around "Partial" in session one just *relocates* the credibility hit to session two — when the user runs their OWN filing and it returns partial. That's worse: it's their pick, not yours. The wow is on rails; the irreversible impression is the first off-rails filing.
2. **No activation metric defined.** #7 says "confirm PostHog" but no one named the event that proves the aha landed. Without it, irreversible first impressions ship with no feedback loop.
3. **Who curates the known-good set, and how it stays good.** The entire onboarding rests on a manually-pinned set, yet nobody specified selection, count, or drift (restatements, re-summarization can turn a known-good filing partial).
4. **The ChatGPT-catch is manufactured, and a sharp ICP user may smell the cherry-pick** — plus stale/defamatory risk if "ChatGPT says $X (wrong)" isn't a dated, reproducible snapshot.

### The Three Calls

**Call 1 — Surface vs. hide.**
Land every beta user on ONE report URL: the curated known-good ADR what-changed teardown (#5). Foreground exactly two things on that page: the **what-changed diff** and **click-to-source citations**. Make the **copilot present but quiet** — one "Ask this filing" input pinned under the report, pre-seeded with 2-3 example questions ("Did margins actually expand?") so it's never a blank box. Keep **search** as a single quiet nav link. **HIDE** peer comparison and dashboard feed (collapse into "More" or omit). **HIDE the watchlist entirely** — an inert alert button is a broken promise. Kill the feature grid and every dark flag from the UI.

**Call 2 — The badge: route around it, do NOT flip it on, do NOT flex it.**
The hide camp's reasoning is strongest, with one Executor mechanic borrowed. Concretely:
- Onboarding/example/demo links run in `demo_mode`: badge **and** Regenerate button suppressed. A first-timer and any investor literally never see "Partial."
- For user-initiated filings *after* onboarding, show a **quiet green "Full" confidence cue only** (post-evals per #7). Do **not** ship "Verified — 47 claims" — a claim count invites audit and is a moat liability while depth is the #1 gap.
- The "Partial" state: surface it **only** on a user's own self-chosen filing, never on the curated set. And — addressing the second-session blind spot — when a user's own filing returns partial, the failure path must be **"deepening this report…" with the partial content already shown and sourced**, not a yellow scarlet letter with a retry. Honesty without the apology.

**Call 3 — The aha: the inline ChatGPT-catch, then the invitation to test.**
Single screen, top of the known-good teardown: a static, **pre-rendered, dated** side-by-side — "ChatGPT: revenue $X (wrong, as of [date])" / "EarningsNerd: $Y →" where $Y is a live click-to-source link that scrolls-and-highlights the exact filing span. No live LLM call. Flow: magic-link → report loads → eye hits the catch → clicks the number → watches it land on the source span (wow in under 10 seconds, zero typing). Then the **immediate second beat**: the pre-seeded copilot prompt right below, turning the passive wow into "now you test it." Belief, then interrogation. To defuse the cherry-pick smell, the catch must be a **real, reproducible, dated snapshot** — not a manufactured straw man.

### The One Thing to Do First

**Hand-pick and pin 3-5 known-good ADR filings as the locked onboarding set, and capture ONE real, dated, reproducible ChatGPT-wrong-number catch against the first of them.** Everything else — the demo_mode suppression, the inline catch screen, the pinned copilot prompt — is wiring that hangs off this artifact. The entire beta first impression rests on this curated set existing and being verifiably good; it is the actual dependency under all three calls, and it is the one thing that cannot be faked, flagged, or deferred.
