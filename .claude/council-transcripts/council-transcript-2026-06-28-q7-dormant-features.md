# Council Transcript — Q7: Dormant Features (finish / flip / defer / kill + activation sequence)

_Run: 2026-06-28 · Source: `tasks/council-prep.md` Question #7 · Skill: `llm-council`_

Protocol: 5 advisors (parallel, independent) → anonymized peer review (parallel) → chairman synthesis.
Framed against the project's actual dormant inventory **and** the already-decided strategic spine from
the prior runs (#1 Wedge, #2 Moat, #5 Distribution) — sequencing was asked to *serve* that spine, not
relitigate it.

---

## Framed Question

EarningsNerd — founder time-allocation: which DORMANT (built-but-not-enabled) features to **finish /
flip / defer / kill** before a closed beta, and in what **sequence**. Solo founder, beta in weeks,
no paid acquisition, pre-traffic.

**Strategic spine (fixed):** #1 wedge = single "what changed, with the receipts" report for the
serious 10-K reader (click-to-source + diffing already shipped/live; real gap = summary content
quality); #2 = accountability positioning + the "ChatGPT-wrong / we-catch-it" demo (ADR = proof
point, not a build); #5 = ADR-beachhead teardowns + onboard onto known-good filings + instrument
links + time-box the promo.

**Dormant inventory:** (A, flip-ready/hours) quality badge, stream section reveal, example-filing
landing, calendar+FMP key, alerts/digest cron (`INTERNAL_JOB_TOKEN`), Turnstile, section-tabs/charts,
guest daily quota; (B, days–weeks) Compare, insider activity (~75s), Apple sign-in, reverse trial,
FPI/ADR listing; (C, eval-gated) `USE_STRUCTURED_OUTPUT` (documented top quality fix), fast/recovery
models. Cross-cutting: confirm the backend PostHog key.

**Ask:** per-item verdict + a sequenced activation order; what to cut with courage; the single first
thing.

---

## Advisor Responses (de-anonymized)

### The Contrarian

FIRST, before anything else: run the evals/ golden set. Everything else is rearranging deck chairs if summary content degrades to boilerplate, because #1/#2/#5 ALL assume the report is good. You cannot sequence flips on top of an unmeasured quality base.

Now the traps, because half this "flip-ready" list is loaded:

ENABLE_QUALITY_BADGE — this is the dangerous one. You're about to FLIP a badge that publicly stamps "Partial" on filings while your known boilerplate-degradation bug is unmeasured. You'd be advertising your own failure rate at the exact moment of first impression. FLIP — but ONLY after evals quantify the partial rate AND #5's "onboard onto known-good filings" is enforced. Sequencing this before evals is self-sabotage.

ENABLE_GUEST_DAILY_QUOTA — KILL for beta. Redis is OFF in prod; it fails open, so it's security theater that lulls you into thinking anon abuse is capped when it isn't. Don't ship a control you can't trust. It's a closed beta — gate by invite, not quota.

ENABLE_CALENDAR — DEFER. Paid FMP key, and it's a feature the spine says to HIDE. Spending money to surface a thing you decided to bury is backwards.

INTERNAL_JOB_TOKEN/cron alerts — DEFER, do NOT flip. Retention on a beta with no filing history and a thin watched-company set means the cron fires on near-nothing or fires noise. You'd be debugging an empty alert pipeline instead of fixing reports.

USE_STRUCTURED_OUTPUT — this is your real #1, not "experimental." It's the documented top fix for the quality gap the whole spine rests on. Eval-gate it, but it's the prize.

CUT cold: Compare, insiders, FPI, reverse-trial, Apple, charts/tabs, Turnstile, calendar.

SEQUENCE: (1) run evals → (2) eval-gate USE_STRUCTURED_OUTPUT → (3) NEXT_PUBLIC_EXAMPLE_FILING_ID → (4) STREAM_SECTION_REVEAL → (5) QUALITY_BADGE → (6) confirm backend PostHog key. Stop there.

### The First Principles Thinker

Strip the framing. The question isn't "which dormant features ship" — it's "what must be true for this beta to produce signal worth having?" One thing: a serious 10-K reader opens a report and thinks *this is better than what I'd do myself, and I can trust the numbers.* Nothing else matters at beta scale. You have no traffic; retention loops, alerts, calendars, and bot defense are answers to problems you do not yet have.

So the entire prioritization collapses to: **fix content quality, then remove every second of friction between a stranger and one trustworthy report.**

FIRST, and possibly only thing that matters: run the eval harness, then ship **USE_STRUCTURED_OUTPUT** if it beats baseline. It's filed under "experimental," but it's the documented top fix for the exact failure (boilerplate degradation) that nullifies #1, #2, AND #5 simultaneously. A beta on a hit-and-miss summary is a beta that measures nothing. FINISH NOW.

Then the friction flips, in order:
- **NEXT_PUBLIC_EXAMPLE_FILING_ID** — FLIP. Zero-wait proof beats a 60s wait. Pick a known-good filing. Do this the same afternoon as the pregenerate job.
- **STREAM_SECTION_REVEAL** — FLIP. Free perceived-quality win.
- **ENABLE_QUALITY_BADGE** — FLIP. Honesty *is* the product (#2). But it's only credible *after* structured output lifts the floor.
- **PostHog backend key** — set it. Beta blind on conversion is not a beta.

CUT with courage, leave dark: Compare, insiders, FPI, reverse-trial, calendar (paid key!), Apple sign-in, Turnstile, guest quota (Redis off anyway), section tabs, charts. Alerts/cron — DEFER; retention is a post-signal problem.

If quality fails the eval, **stop and fix the prompt before launching anything.** A fast, pretty, badged wrong answer is the one outcome that kills you.

### The Expansionist

FIRST: flip NEXT_PUBLIC_EXAMPLE_FILING_ID. Run the pregenerate job on a known-good ADR teardown, paste the id. This is your entire wedge made tangible in two hours — the landing IS the distribution asset (#5 teardowns funnel straight to it), the activation lever (zero-wait first touch with no audience to retry-burn), and the #2 hero artifact's stage. Everything else orbits this.

Per-item, through the leverage lens:

- USE_STRUCTURED_OUTPUT — FINISH NOW (run the eval first). This is the dormant flip with the largest blast radius: it lifts EVERY downstream surface — the example landing, every teardown, the #2 catch-ChatGPT artifact, onboarding-onto-known-good. Filed "experimental," but it's the master quality knob #1/#2/#5 all silently depend on. The eval run is the unlock gate; do it this week.
- ENABLE_QUALITY_BADGE — FLIP ON. Cheap, but load-bearing for the wedge: it IS the accountability claim made visible, and it converts your worst filings from silent embarrassments into honest "retry" prompts. Cosmetic in effort, structural in meaning.
- STREAM_SECTION_REVEAL — FLIP ON. ~10s vs ~60s on the one screen every beta user judges you by. Free perceived-quality multiplier.
- INTERNAL_JOB_TOKEN + cron — FLIP ON. The dormant item with compounding payoff: it's the only thing here that creates a reason to RETURN. Inert watchlist → live retention loop for one env action. Don't ship beta without it.
- PostHog backend key — FLIP ON first-day. Cheap; without it you're blind on the funnel the whole beta.

CUT/leave dark: Compare, insiders, FPI, reverse-trial, Apple, calendar, charts, tabs, Turnstile, guest-quota. None compounds the wedge pre-beta.

Sequence: example-filing → eval+structured-output → quality-badge → stream-reveal → cron+PostHog. Five flips, one unlock. Polish nothing else.

### The Outsider

Here's what a first-time beta user actually feels in their first 60 seconds. Nothing else matters yet.

**FIRST, and it's not close: NEXT_PUBLIC_EXAMPLE_FILING_ID. FLIP ON.** A new user with no account lands and either sees a finished, gorgeous report in zero seconds, or stares at a 30-80s spinner generating AAPL. That spinner is where your beta dies. No human waits 60 seconds to find out if your product is good. This is a paste-an-id task that decides whether anyone ever sees the thing your whole strategy rests on. Do it today.

**STREAM_SECTION_REVEAL. FLIP ON.** 10s vs 35-60s to first content, same output, safe fallback. Perceived speed *is* perceived quality to a stranger. Free.

**USE_STRUCTURED_OUTPUT. FINISH NOW (eval-gate it).** This is the only "invisible plumbing" a user will actually feel — because it's not plumbing, it's whether the report reads like a sharp analyst or like boilerplate. A fast example that's mush converts no one. Quality and the example landing are the same bet.

**ENABLE_QUALITY_BADGE. FLIP ON.** Cheap honesty; a "Partial — retry" beats a silently bad report. But onboard users onto known-good filings so they rarely see it.

**Everything else: DEFER or leave dark.** Calendar, Compare, insiders (75s!), FPI, Apple sign-in, charts, section tabs, reverse-trial, Turnstile, guest quota, alerts cron — a first-time user notices NONE of these in 60 seconds. They are founder catnip. Insiders at 75s would actively poison the experience. Alerts/retention don't exist if nobody survives minute one.

**Sequence:** (1) pregenerate + paste EXAMPLE_FILING_ID, (2) eval + flip USE_STRUCTURED_OUTPUT, (3) STREAM_SECTION_REVEAL, (4) QUALITY_BADGE. Confirm the PostHog key so you can *see* step 1 working. Cut the rest with zero guilt.

### The Executor

FIRST, before anything else: run the eval golden set against `USE_STRUCTURED_OUTPUT`. Not as a flip — as a measurement. Every dormant feature is downstream of summary quality being good enough; flipping the example-filing landing to showcase a boilerplate-degraded report actively hurts you. This is your single most-leveraged action and it's the prerequisite gate for everything else.

PER-ITEM VERDICTS:

FLIP ON (the cheap activation core, in order):
1. ENABLE_QUALITY_BADGE — flip with the eval run; it's the honesty claim made real, ~1hr.
2. NEXT_PUBLIC_EXAMPLE_FILING_ID — but ONLY after eval picks a KNOWN-GOOD filing. Sequence: run pregenerate job → hand-pick a clean ADR report (serves #5) → paste id. ~3hrs, single best activation lever.
3. STREAM_SECTION_REVEAL — pure perceived-latency win, safe fallback. ~1hr.
4. USE_STRUCTURED_OUTPUT — flip ONLY if eval beats baseline. If it does, this is #1 leverage, full stop.
5. INTERNAL_JOB_TOKEN + Cloud Scheduler — the one retention lever worth the half-day; alerts are inert without it and #2 says retention is the real work.

Confirm the backend PostHog key in the same sitting as #1 — it's a secret-check, not a build, and you're blind without it.

DEFER (leave dark): Calendar (paid key, off-spine), Section Tabs, Financial Charts (cosmetic, #1 says hide), Turnstile (no traffic to defend yet), Guest Quota (Redis-off neuters it), Apple Sign-In.

KILL/leave-dark through beta: Compare, Insiders (75s fan-out), FPI (weeks, distortion risk), Reverse Trial (churn-exploitable until ledger exists).

CUT WITH COURAGE: every B-tier "needs finishing" item. You have a handful of ship slots; spend zero on multi-day features when 4-hour flips move activation more.

FIRST MONDAY: eval run + PostHog key check. Nothing else until you know the quality number.

---

## Peer Review (anonymized inputs)

Anonymization map for this round: **A** = Outsider · **B** = Contrarian · **C** = Executor ·
**D** = Expansionist · **E** = First Principles.

### Reviewer 1
1. **Response C is strongest.** It alone correctly orders the eval as a *measurement gate*, then ties EXAMPLE_FILING_ID to picking a known-good ADR filing (serving #5), flips INTERNAL_JOB_TOKEN as the one retention lever, and bundles the PostHog key-check into the same sitting. Most actionable, best-sequenced, no naivety on the badge trap.
2. **Response D has the biggest blind spot.** It flips QUALITY_BADGE and EXAMPLE_FILING_ID without making them strictly conditional on the eval result — and B/C correctly flag that badging "Partial" on an unmeasured failure rate advertises your own weakness at first impression. D also flips cron retention, weak when beta has no filing history (B's point).
3. **All five missed that this is a CLOSED, INVITED beta.** Invite-gating changes everything: it moots guest-quota and Turnstile entirely (no anon traffic), weakens the EXAMPLE_FILING_ID urgency (invited users expect to engage), and means the eval sample should be drawn from the *actual filings invitees care about*, not a generic golden set. None proposed hand-curating onboarding filings per invitee. Also: no one set a quantitative pass/fail threshold for the eval or named who/what the beta cohort actually is.

### Reviewer 2
1. **Response E is strongest.** It reframes the whole question correctly — beta = produce trustworthy signal — and refuses to let pretty/fast/badged compensate for a wrong number. Its kill-list is ruthless, its sequence correct, and its closing line ("stop and fix the prompt before launching anything") is the right hard gate that A/D soft-pedal.
2. **Response D has the biggest blind spot.** It puts EXAMPLE_FILING_ID *first*, before the eval — exactly the trap B and C name: showcasing a possibly-boilerplate report as the headline asset. It also calls cron alerts "don't ship beta without it," contradicting the spine (no filing history, thin watchlist → fires on noise/nothing). D optimizes the wedge's stage before confirming the wedge works.
3. **All five missed: the known-good filing set is itself an unbuilt dependency.** #5 says onboard onto non-partial filings and the example must be clean — but nobody specifies *who curates that whitelist or how*, and the eval golden set may not cover the ADR beachhead filings beta users actually open. Also unaddressed: what's the pass/fail threshold and fallback if USE_STRUCTURED_OUTPUT *fails* the eval — there's no plan B for the quality gap everything depends on.

### Reviewer 3
1. **Response E is strongest.** It reframes the question correctly — beta must produce *signal*, not features — and lands the sharpest single line: "a fast, pretty, badged wrong answer is the one outcome that kills you." It correctly sequences quality (USE_STRUCTURED_OUTPUT) ahead of the example landing, and explicitly says STOP and fix the prompt if evals fail. B and C are nearly as good on the gating logic; D and A under-weight the eval-before-flip dependency (A even sequences example landing first).
2. **Response D has the biggest blind spot.** It puts EXAMPLE_FILING_ID "FIRST" and treats structured-output as parallel, risking a beautiful zero-wait landing showcasing boilerplate. It also keeps INTERNAL_JOB_TOKEN/cron as "don't ship without it" — but B/C correctly note alerts fire on near-nothing in a thin closed beta. D polishes a retention loop with no inventory to populate it.
3. **All five missed: who gets invited and how, and what "signal worth having" is measured against.** No response defines the beta cohort, the invite mechanism, or a kill/iterate threshold on the eval number itself (what partial-rate is launch-blocking?). They also ignore that a closed beta makes EXAMPLE_FILING_ID less load-bearing — invited users arrive warm, not cold strangers needing zero-wait proof.

### Reviewer 4
1. **Strongest: C.** It nails the one ordering subtlety the others fumble: the example-filing landing must come *after* the eval picks a known-good filing, and it explicitly ties that to #5 (ADR teardown). It also catches the QUALITY_BADGE trap (don't stamp "Partial" before measuring the rate), keeps the cron retention lever, and time-boxes PostHog into the same sitting. B raises the same badge trap sharply but kills the cron too hastily.
2. **Biggest blind spot: D.** It opens with "FIRST: flip EXAMPLE_FILING_ID" before the eval gate — exactly the self-sabotage B/C warn against (you'd showcase a possibly-boilerplate report). It also keeps the cron as a must-have without noting the empty-pipeline problem on a beta with no filing history.
3. **All five missed:** the closed beta is *invite-gated*, so anon-facing flips they spent words on (guest quota, Turnstile, even the zero-wait landing's urgency) are partly moot — invited users will tolerate a short wait. None asked who's actually in the beta or how they're recruited (no audience). And none flagged that the eval harness itself may be the real time sink — running/interpreting it could eat the "weeks," dwarfing every flip.

### Reviewer 5
1. **Strongest: Response C.** It nails the dependency graph: eval-as-measurement first, then orders the cheap flips while attaching the load-bearing conditions others state loosely — example-filing must wait for a known-good pick (serves #5's ADR beachhead), badge sequenced with the eval, PostHog "in the same sitting." It alone keeps INTERNAL_JOB_TOKEN as the one defensible retention flip per #2, without overclaiming. B is close and sharpest on traps (quality-badge self-sabotage, guest-quota theater) but cuts the cron too reflexively.
2. **Biggest blind spot: Response D.** It opens "FLIP example-filing FIRST" before the eval, contradicting its own later "run the eval first." If quality degrades, you'd hardcode a boilerplate report as your hero asset. Sequencing the showcase ahead of the measurement is exactly the self-sabotage B/C/E warn against.
3. **All five missed:** none names WHICH filing becomes the example, nor a fallback if USE_STRUCTURED_OUTPUT *fails* the eval (E gestures, none plans). And the spine's literal "first move" — running the golden set — may be blocked if the golden set lacks ADR/degrading cases; nobody checks whether the eval can even measure the bug it's gating on.

---

## Chairman's Verdict

### Where the Council Agrees

Five advisors converged hard on a small set of moves — this is the high-confidence spine:

- **The eval golden set runs FIRST, as a measurement gate, not a flip.** All five open here. Every dormant feature is downstream of summary quality; you cannot sequence flips on top of an unmeasured quality base.
- **USE_STRUCTURED_OUTPUT is the real #1, not "experimental."** It is the documented top fix for the boilerplate-degradation bug that nullifies #1, #2, AND #5 simultaneously. Eval-gate it; if it beats baseline, it is the single highest-leverage flip on the board.
- **The cheap activation core ships: EXAMPLE_FILING_ID, STREAM_SECTION_REVEAL, QUALITY_BADGE.** Hours each, all touch the one screen every beta user judges you on.
- **Confirm the backend PostHog key in the same sitting.** A secret-check, not a build. Beta blind on the funnel is not a beta.
- **Cut with courage, leave dark:** Compare, Insiders (75s fan-out actively poisons the experience), FPI (weeks + 7x distortion risk), Reverse Trial (churn-exploitable without the ledger), Apple sign-in, Calendar (paid key, off-spine), section-tabs, charts. Unanimous. None compounds the wedge pre-beta.
- **QUALITY_BADGE must follow the eval, not precede it.** Four of five flag that stamping "Partial" on an unmeasured failure rate advertises your own weakness at first impression.

### Where the Council Clashes

**1. INTERNAL_JOB_TOKEN + alerts cron — flip or defer?**
- *Expansionist + Executor:* FLIP. It is the only dormant item that creates a reason to RETURN, and #2 names retention as the real defensibility work. One env action turns an inert watchlist into a live loop.
- *Contrarian + First Principles + Outsider:* DEFER. A closed beta has no filing history and a thin watched-company set — the cron fires on near-nothing or fires noise. Retention is a post-signal problem; you'd be debugging an empty pipeline instead of fixing reports.
- *Why reasonable people split:* It hinges on whether retention is a "build now" or "build once signal exists" problem. The defer camp is correct **for the closed-beta window specifically** — you have no inventory to populate the loop yet. The flip camp is right that it's cheap and load-bearing eventually. **Chairman's call: DEFER to the back of the sequence — flip it only if the quality work lands with slack time, never before the eval and the activation core.** The half-day is real, and a loop firing on an empty set teaches you nothing.

**2. How load-bearing is EXAMPLE_FILING_ID?**
- *Expansionist/Outsider:* THE first thing — the spinner is where the beta dies, the landing IS the distribution asset.
- *Peer reviewers (all five):* This is a CLOSED, INVITED beta. Invited users arrive warm and tolerate a short wait, which weakens the zero-wait urgency. Still worth doing (cheap, serves the #5 ADR teardown stage), but it is not the do-or-die that the cold-traffic framing implies.
- *Chairman's call:* Keep it high in the sequence because it is cheap and doubles as the teardown asset — but it ranks **after** the quality gate, never before. A zero-wait landing showcasing boilerplate is worse than a spinner.

### Blind Spots the Council Caught

These only surfaced in peer review — every individual advisor missed them:

- **This is an invite-gated beta, which moots the anon-defense flips entirely.** Guest quota and Turnstile defend against anonymous traffic you won't have. All five advisors spent words gating/killing them on technical grounds (Redis-off) when the simpler truth is: no anon surface exists. Gate by invite.
- **The known-good filing whitelist is itself an unbuilt dependency.** #5 says onboard onto non-partial filings and the example must be clean — but no advisor specified *who curates that list or how*. This is a real task hiding inside "paste the id."
- **There is no plan B if USE_STRUCTURED_OUTPUT FAILS the eval.** E gestures at "stop and fix the prompt," none plans it. You need a pass/fail threshold defined *before* you run, and a prompt-iteration fallback if structured output doesn't beat baseline.
- **The golden set may not cover the bug it's gating.** If the eval lacks ADR/degrading cases, running it measures nothing about the actual failure mode (boilerplate on ADR teardowns). Verify the harness can see the bug before trusting its number.

### The Verdict Table — finish / flip / defer / kill

| Item | Verdict | Why |
|---|---|---|
| Run eval golden set | **DO FIRST (gate)** | Everything is downstream; it's a measurement, not a flip. |
| USE_STRUCTURED_OUTPUT | **FINISH NOW (eval-gated)** | Documented top fix for the quality bug the whole spine rests on. |
| NEXT_PUBLIC_EXAMPLE_FILING_ID | **FLIP ON (after known-good pick)** | Best activation lever + #5 teardown stage; must showcase a clean filing. |
| STREAM_SECTION_REVEAL | **FLIP ON** | Free perceived-quality win on the one screen that matters; safe fallback. |
| ENABLE_QUALITY_BADGE | **FLIP ON (after eval)** | Honesty is the product (#2); but don't stamp "Partial" before measuring the rate. |
| PostHog backend key | **CONFIRM DAY ONE** | Secret-check; you're blind on the funnel without it. |
| INTERNAL_JOB_TOKEN + cron | **DEFER (slack-time only)** | Retention is a post-signal problem; fires on noise/nothing in a thin closed beta. |
| ENABLE_CALENDAR + FMP_API_KEY | **DEFER** | Paid key to surface a feature the spine says to HIDE. |
| Turnstile | **DEFER** | No anon surface — it's an invite-gated beta. |
| ENABLE_SECTION_TABS / FINANCIAL_CHARTS | **DEFER** | Cosmetic; #1 says hide the feature grid. |
| ENABLE_GUEST_DAILY_QUOTA | **KILL (for beta)** | Redis-off → fails open; security theater, and no anon traffic anyway. |
| ENABLE_COMPARE | **KILL (leave dark)** | Days of rework; dead-ends on 404; off-spine (hidden). |
| ENABLE_INSIDER_ACTIVITY | **KILL (leave dark)** | 75s live fan-out actively poisons the experience; off-spine. |
| ENABLE_APPLE_SIGNIN | **DEFER** | Console setup for zero beta value; button 404s if half-done. |
| REVERSE_TRIAL_ENABLED | **KILL (until ledger)** | Re-grantable via re-registration churn; the $0 promo already covers the payment trigger. |
| ENABLE_FPI_FILINGS | **KILL (leave dark)** | Weeks of work + ~7x currency distortion; ADR is a proof point, not a build. |
| AI_FAST_MODEL / SECTION_RECOVERY_MODEL | **DEFER** | Cost levers, not quality/activation levers; eval sign-off later. |

### The Activation Sequence

Only these ship before beta. In order:

1. **Run the eval golden set** — but first verify it contains ADR/degrading cases, and write down the pass/fail partial-rate threshold *before* you look at the number.
2. **Eval-gate USE_STRUCTURED_OUTPUT.** If it beats baseline → flip. If it fails → STOP and iterate the prompt; do not launch anything on a hit-and-miss base. This is the gate, not a step to rush past.
3. **Hand-curate the known-good filing whitelist** (a small set of clean, non-partial ADR filings — serves #5 onboarding + the example landing).
4. **Run pregenerate + paste NEXT_PUBLIC_EXAMPLE_FILING_ID** using a known-good ADR report from step 3.
5. **Flip STREAM_SECTION_REVEAL.**
6. **Flip ENABLE_QUALITY_BADGE.**
7. **Confirm the backend PostHog key** (do this alongside step 2 so you can see the funnel from day one).
8. **(Slack time only) Flip INTERNAL_JOB_TOKEN + cron** — only if steps 1–7 land with time to spare. Never before.

**Deliberately left dark / cut:** Compare, Insiders, FPI, Reverse Trial, Apple sign-in, Calendar, section-tabs, charts, Turnstile, guest quota, fast/recovery models. These are founder catnip. A first beta user notices none of them in their first session; several (insiders' 75s, a half-built Compare 404) would actively harm the impression. Cut with zero guilt.

### The One Thing to Do First

Before running anything, open the eval golden set and confirm it actually contains ADR and boilerplate-degrading filings — the exact failure mode USE_STRUCTURED_OUTPUT is meant to fix. If the harness can't see the bug, its pass/fail number is meaningless and every flip downstream is built on sand. Verify the eval can measure the thing it's gating — then run it.
