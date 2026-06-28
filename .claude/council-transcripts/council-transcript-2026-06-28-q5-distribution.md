# Council Transcript — Q5: Distribution (first 100 engaged users / first 10 payers)

_Run: 2026-06-28 · Source: `tasks/council-prep.md` Question #5 · Skill: `llm-council`_

Protocol: 5 advisors (parallel, independent) → anonymized peer review (parallel) → chairman synthesis.
Grounding verified against the codebase (June 2026): `frontend/lib/featureFlags.ts`,
`backend/app/config.py`, `tasks/research/competitors.md`, `tasks/launch-runbook.md`.

---

## Framed Question

EarningsNerd — Distribution decision: the first 100 engaged beta users and the first 10 payers.

**THE PRODUCT (verified):** structured, citation-backed AI "analyst-style" summaries of SEC
10-K/10-Q/20-F filings, plus an "Ask this Filing" copilot, peer comparison, insider (Form 4)
activity, watchlists with change-alerts, and a personalized dashboard feed. Differentiated edge:
foreign-issuer/ADR coverage in correct native currency (verified live on Alibaba's 20-F in RMB;
eval golden set covers JD/SE/NVO/PDD/MELI/BABA/TSM). Caveat: the company-page *listing* of foreign
filings (20-F/6-K) is behind a multi-week flag and DARK in beta — but a curated deep-link to a
pre-generated foreign-filing summary works TODAY. Honest weakness: summary quality has real variance
(some filings return "partial"; output depth is the known #1 gap).

**THE MARKET (verified):** crowded. Fiscal.ai (ex-FinChat, $39 Pro, ~350k users, citation-backed
chat-with-filing) is the bar; also Stock Titan, TipRanks, Koyfin, BamSEC, Stockanalysis.com, plus
free ChatGPT and finance newsletters/YouTube. White space: an auto-generated *structured analyst
report of a single filing* is under-served; period-over-period disclosure diffing is the
rarest/most-wanted feature market-wide. Prosumer paid band $39–$89/mo; EarningsNerd Pro is $14/mo
($140/yr) — the budget option. Free = 5 summaries/mo.

**FOUNDER & STAGE:** solo, pre-revenue, pre-traffic, no audience; closed beta in weeks; cannot run
paid acquisition; very limited time. Has invite-gated magic-link onboarding and a live 100%-off beta
promo. Distribution is the roadmap's biggest blind spot.

**DECISION:** highest-leverage path to the first 100 engaged beta users and first 10 payers.
Pressure-test channel bets (a) finance Twitter/Reddit, (b) public "filing of the week" teardown,
(c) ADR/Alibaba communities (foreign-issuer edge), (d) newsletter design-partner outreach — pick
one or two, give the concrete first move.

---

## Advisor Responses (de-anonymized)

### The Contrarian

Channel (c) is a trap dressed as your moat, and it's the one you're emotionally attached to — so kill it first. Alibaba/ADR investor communities (r/baba, Stocktwits BABA) are dominated by traders arguing price targets and delisting fear, not people who read 20-Fs. Worse, your foreign-filing *listing* is DARK behind a multi-week flag; you'd be selling your headline differentiator via a single curated deep-link held together with tape. Pitch your edge, get a curious user, they hit the wall where the feature isn't actually there. That's how you burn a community you can only enter once.

(a) finance Twitter with no audience and no budget = screaming into a void; the algorithm buries link-posts from zero-follower accounts. (d) newsletter writers won't promote a $14 unproven tool with quality variance to their reputation-sensitive lists — you have nothing to offer them yet.

The brutal question you're avoiding: **does the summary survive a side-by-side vs. a free ChatGPT prompt?** You admitted it sometimes doesn't. No channel fixes that. So lead with the ONE thing ChatGPT can't fake: verifiable, deep-linked, period-over-period *diffing* — the rarest feature in the market.

Pick (b), narrowed: a public "what changed since last quarter" teardown, posted as a native text/image breakdown (not a link) into r/SecurityAnalysis where readers actually open filings.

**Monday move:** pick one widely-held name reporting this week, manually produce one gorgeous change-report teardown, post it natively, soft-CTA to beta in a comment. If it can't earn 20 upvotes there, no channel will save the product — and you'll have learned that for free.

### The First Principles Thinker

Your closest competitor, Fiscal.ai, has 350k users and a citation-backed chat-with-filing product. You're a $14/mo budget clone of that with worse summary depth and a foreign-issuer feature that's DARK in beta. If you frame this as "100 generic engaged users," you will lose, because there's no reason for a generic investor to pick you over a free ChatGPT prompt or a more mature paid tool.

So strip the question down. You don't need 100 users. You need 10 people who hold a specific ADR, cannot get a clean read on its 20-F in native currency anywhere else, and feel relief the first time they use you. The product has exactly one thing nobody else does well: foreign-issuer filings in correct native currency. That is your entire wedge. Everything else is parity-or-worse and should be invisible in your pitch.

Kill (a) finance Twitter/Reddit broadly — you have no audience and no edge there; you'd be shouting a budget pitch into a saturated room. Kill (d) newsletter outreach for now — it's a credibility play you can't yet back with traction.

Concentrate on (c), sharpened: ADR/foreign-issuer investors, delivered via (b) as the vehicle. Not "filing of the week" generically — a recurring "what BABA/PDD/SE actually said in native RMB" teardown, the thing a free prompt gets wrong.

Monday move: pick BABA. Manually write ONE killer teardown using your pre-generated deep-link. Post it as a comment answering a real, recent question in r/SecurityAnalysis or an Alibaba investor forum — value first, invite-link second. Ten relieved ADR holders beat 100 indifferent ones.

### The Expansionist

Concentrate on (b) public "filing of the week" teardown, sequenced into (c) ADR communities. Kill (a) and (d) as primary bets — finance Twitter with no audience is shouting into a void, and newsletter writers won't partner with a pre-traffic stranger until you have a body of work to point at. The teardown IS the body of work.

Here's the upside everyone's underweighting: the foreign-issuer/native-currency edge isn't a feature, it's a content moat. Nobody — not Fiscal.ai, not finance YouTube — is publishing clean, structured, citation-backed teardowns of 20-Fs in native RMB. That's a Google-and-Reddit-searchable void. Every BABA/PDD/SE/MELI investor who searches "Alibaba 20-F revenue breakdown" is a pre-qualified lead, and you'll own that SERP because the supply is zero. The deep-link to a pre-generated foreign summary works TODAY — you don't need the dark listing flag.

Monday-morning first move: publish ONE teardown of Alibaba's latest 20-F as a public, no-login deep-link page — the native-RMB structured report plus a period-over-period diff (the rarest, most-wanted feature in the market — lead with it). Then post it ONCE in r/SecurityAnalysis framed as "I parsed BABA's 20-F in native currency, here's what changed YoY," with the deep-link. Not a launch — a gift.

Why this compounds: each teardown is a permanent, indexed asset that recruits while you sleep, doubles as the artifact that finally makes newsletter writers say yes, and turns the $14 price from "budget" into "absurdly cheap for this." Cadence beats blast. One filing a week, foreign-first, and the channel widens on its own.

### The Outsider

Nobody outside finance knows what a "20-F" is, and most people who own Alibaba stock have never read one. So lead with that gap, not past it.

KILL (d): newsletter writers are busy, get pitched constantly, and a no-audience solo founder offering a budget tool is the easiest "no" in their inbox. Low odds, high time-cost.

KILL (a) as a primary: shouting into finance Twitter/Reddit with no following = zero reach. It's a graveyard for unknown founders.

PICK (c) + (b), sequenced. Here's the outsider logic: your one thing a stranger instantly *gets* is "I own BABA/PDD/JD and I can't understand their filings — this reads it for me, in actual yuan." That's a sentence a normal person nods at. "Structured analyst report" is not — that's curse-of-knowledge jargon that sounds like every other terminal.

MONDAY MORNING: Pick the single most-watched ADR right now (Alibaba or Nvidia-adjacent China name). Generate one gorgeous, screenshot-able teardown using your working deep-link. Post it where ADR holders already congregate and feel underserved — r/Baba, Seeking Alpha comment threads, Stocktwits BABA stream, the Alibaba/PDD investor Discords. Not "check out my startup." Instead: "I pulled the latest 20-F and here's what changed, in RMB" — and drop the link.

Then make (b) the *engine*: one ADR teardown per week, same format, building a tiny following of people who can't get this anywhere cheap.

The 100 engaged users come from being the only person feeding a specific, ignored crowd. The 10 payers come from those same people hitting the 5-summary wall mid-research. $14 is an impulse for someone already hooked.

### The Executor

Kill (a) and (d) as primary bets. Finance Twitter/Reddit with no audience and a product whose #1 known gap is summary depth = you'll get downvoted in r/SecurityAnalysis (sophisticated, ChatGPT-savvy, will eat your weak filings for breakfast) and ghosted by newsletter writers who get pitched daily and have nothing to gain from a pre-traffic tool. Both are slow, rejection-heavy, and don't play to your one verified edge.

Concentrate on (c), sequenced into (b). Your only defensible, demoable advantage is native-currency ADR coverage that works TODAY via curated deep-links. ADR-investor communities are starved for exactly this — BABA/PDD/SE/MELI bulls argue about RMB-denominated numbers constantly and there is no good tool for it.

Monday morning, literally:
1. Pre-generate 5 clean foreign-filing summaries you've eyeballed (BABA 20-F, PDD, SE, MELI, NVO) — only the ones that DON'T return "partial." Grab the shareable deep-links.
2. Find the 3 highest-engagement recent threads on r/China_Stocks, the Stocktwits BABA stream, and any Substack/Discord with active ADR discussion. Don't pitch. Answer one real question (e.g., "here's what BABA's 20-F actually says about buybacks, in RMB") and drop the deep-link as the receipt.
3. Each link lands on the 100%-off beta gate. That's your funnel.

Do this daily for 2 weeks: one genuinely useful comment + one curated link. That's ~10 touches/day, no budget, plays your edge.

Then (b) is the compounding layer: turn the best teardown each week into a public "Foreign Filing of the Week" post. Don't start (b) until you've proven a community bites. ADR communities first — they're a knife-fight you can win.

---

## Peer Review (anonymized inputs)

Anonymization map for this round: **A** = Expansionist · **B** = Outsider · **C** = Contrarian ·
**D** = First Principles · **E** = Executor.

### Reviewer 1
1. **Strongest: A.** It alone names the compounding mechanism others miss: each teardown is a permanent, SEO-indexed asset that recruits while you sleep, owns a zero-supply SERP ("Alibaba 20-F revenue breakdown"), and doubles as the artifact that later unlocks newsletter writers. It also correctly notes the deep-link works today, defusing the dark-flag risk. B/D/E reach a similar (c)+(b) conclusion but treat content as a one-shot post, not an asset.
2. **Biggest blind spot: C.** It kills (c) — the verified moat — on a vibe ("emotionally attached"), then lands on basically the same change-report teardown the others reach via (c). It conflates "ADR price-target traders" with "20-F readers" while ignoring that SEO/search captures the latter regardless of community noise. Its one gift (the ChatGPT side-by-side gut-check) is real but underweighted by everyone else.
3. **What all five missed:** no retention/activation loop. They obsess over acquisition touches but never address what makes 100 visitors into *engaged* users or trips the 5-summary wall — onboarding, the watchlist change-alert hook, or a follow-up. And none proposes measuring whether posts actually convert (UTM/funnel), so the founder can't tell a winning channel from noise.

### Reviewer 2
1. **Strongest: Response A.** It's the only one that reframes the foreign-issuer edge as a *durable, SEO-indexed content moat* rather than a one-off post — "own the SERP because supply is zero" is the most compounding insight. It also correctly notes the deep-link works today (bypassing the dark flag), leads with the rare diffing feature, and gives a concrete cadence. C is a close second for its brutal ChatGPT side-by-side honesty.
2. **Biggest blind spot: Response B.** It picks the right wedge but ignores the quality-variance landmine that C names directly: posting into ADR communities can backfire if the summary loses to a free ChatGPT prompt. B also picks high-noise trader venues (r/Baba, Stocktwits) where C correctly warns the audience argues price targets, not filings — wrong crowd for filing depth.
3. **What ALL missed:** No one mentions *measuring* anything — no instrumentation of which deep-links convert, no activation metric, no definition of "engaged." With ~10 touches/day and a solo founder, knowing which posts drive signups vs. silence is the whole game. Also missed: direct 1:1 outreach (DMing people who *just asked* a BABA filing question) likely beats broadcast posting at this tiny scale.

### Reviewer 3
1. **Strongest: Response A.** It's the only one that reframes the foreign-issuer edge as a *content moat with SERP capture* — indexed, compounding assets that recruit while the founder sleeps and double as the artifact that later unlocks newsletter writers. It also correctly leads with period-over-period diffing (the rarest feature) and rebuts the "DARK flag" objection (deep-link works today). Strategic and compounding, not just tactical.
2. **Biggest blind spot: Response C.** It kills (c) — the one verified edge — partly because the founder is "emotionally attached," then funnels everyone into r/SecurityAnalysis, a sophisticated, ChatGPT-savvy crowd most likely to expose the admitted summary-quality variance. It talks itself out of the moat and into the most hostile room.
3. **What ALL five missed:** No conversion mechanics. The question demands the first *10 payers*, but every response stops at the free 100%-off beta gate — and beta users get Pro FREE, so there is no payment trigger at all during beta. Nobody addresses how/when the 100%-off promo ends, what converts a freeloader to a $14 card, or measurement (which post drove signups). They optimized acquisition and ignored monetization and instrumentation.

### Reviewer 4
1. **Strongest: Response A.** It's the only one that reframes the foreign-issuer edge as a *searchable content moat* (owning the "Alibaba 20-F revenue breakdown" SERP where supply is zero) — a compounding, indexed asset that recruits passively, rather than just a community to spam. It also correctly notes the deep-link works today, and leads with the period-over-period diff (the rarest feature). Strategic depth beyond "post in r/baba."
2. **Biggest blind spot: Response C.** It kills (c) as an "emotional trap," then lands on essentially the same teardown play everyone else recommends — but strips out the foreign-issuer wedge, which is the *only* verified differentiator vs. free ChatGPT. Its own "does it beat ChatGPT?" question gets answered by native-currency 20-Fs (ChatGPT hallucinates these), yet C discards exactly that edge.
3. **What ALL five missed:** No measurable kill-criteria or instrumentation. They prescribe daily posting for 2 weeks but never define what "engaged" means, what conversion signal validates the wedge, or when to pivot. Also unaddressed: the 5-summary free wall and copilot-gating as the actual *conversion mechanic* — how a relieved ADR reader becomes one of the 10 payers. Distribution without an activation/retention loop just leaks.

### Reviewer 5
1. **Response D is strongest.** It reframes the goal correctly: not 100 generic users but 10 relieved ADR holders who can't get a native-currency read anywhere else. Sharpest wedge logic, ruthless prioritization, value-first Monday move tied to a real thread. E is a close second (most operational), but D's strategic clarity wins.
2. **Response A has the biggest blind spot.** It bets everything on SEO/SERP compounding ("recruits while you sleep," "own that SERP") — but indexing takes months and the founder needs traction in weeks. It ignores the codebase caveat C nails: the foreign-listing feature is DARK, held together by a single taped-together deep-link. A oversells a moat that's barely shipped.
3. **All five ignored the admitted quality variance as a conversion killer at the moment of truth.** They route ADR users to a 100%-off gate, but once inside, those users generate their OWN filings — which sometimes return "partial" and lose to ChatGPT. The curated teardown is cherry-picked; the live product isn't. None proposed a guardrail: pre-screen which tickers a user is likely to try, or onboard them onto known-good filings first. Also unaddressed: how a free-via-promo beta ever converts to $14 when the wall is removed.

---

## Chairman's Verdict

### Where the Council Agrees

Four of five advisors converged on the same architecture, independently:

- **Kill (a) and (d) as primary bets.** Finance Twitter/Reddit with zero followers is algorithmically buried — shouting into a void. Newsletter writers are the easiest "no" in the inbox: they get pitched daily and won't stake their reputation on a $14, pre-traffic tool with known quality variance. Unanimous, including the Contrarian.
- **The wedge is the foreign-issuer / native-currency edge, not "100 generic engaged users."** First Principles, Outsider, Expansionist, and Executor all reframe the goal as *10 relieved ADR holders* who can't get a clean native-currency read on a 20-F anywhere else. Generic investors have no reason to pick a $14 budget clone over free ChatGPT or a mature paid tool. Narrow or lose.
- **Content/teardown (b) is the vehicle, ADR communities (c) are the destination.** The dominant shape is (c)+(b) sequenced: a recurring, screenshot-able "what BABA/PDD/SE said in native RMB, and what changed YoY" teardown, delivered value-first into communities where ADR holders already congregate.
- **The dark-flag risk is overstated — the deep-link works TODAY.** Multiple advisors note you don't need the multi-week listing flag; the curated pre-generated foreign-filing summary is shippable now.
- **Lead with the period-over-period diff.** It's the rarest, most-wanted feature market-wide and the thing ChatGPT structurally cannot fake.

### Where the Council Clashes

**Clash 1 — Is (c) the moat or a trap?** The Contrarian alone kills (c), arguing ADR communities (r/Baba, Stocktwits BABA) are price-target traders and delisting-fear arguers, not 20-F readers, and that you'll burn a one-shot community by pitching a feature that's half-shipped. The other four say (c) is the *only* verified differentiator and discarding it leaves you with parity-or-worse. The peer reviews sided decisively against the Contrarian (3 of 5 named C the biggest blind spot: it kills the moat "on a vibe," then lands on the same teardown play anyway). Reasonable people disagree here because the Contrarian is right about the *crowd quality* (traders ≠ readers) but wrong about the *conclusion* — the fix is venue selection (filing-literate corners, 1:1 outreach), not abandoning the wedge.

**Clash 2 — SEO content moat vs. weeks-horizon traction.** The Expansionist's "own the SERP, recruits while you sleep" framing was named strongest by four of five peer reviewers — it's the only genuinely compounding insight. But Peer Review 5 lands the sharpest counterpunch: *SEO indexing takes months; this founder needs traction in weeks.* Both are right. SEO is the correct long-game by-product, but it cannot be the acquisition engine for a beta opening in weeks. The teardown's near-term job is the Reddit/community post and the 1:1 DM, not the Google ranking.

**Clash 3 — Broadcast post vs. 1:1 outreach.** Most advisors prescribe broadcast posting (one great teardown, posted natively). Peer Reviews 2 and 3 argue that at this tiny scale, DMing people who *just asked* a BABA filing question beats broadcasting. This is the more correct instinct for 10 users.

### Blind Spots the Council Caught

Peer review surfaced what every individual advisor missed — and these are the gaps that actually sink the plan:

- **There is no payment trigger during beta.** Beta users get Pro FREE via the 100%-off promo. Every advisor stops at the beta gate and declares victory, but the question explicitly demands the *first 10 payers*. Nobody addressed how/when the promo ends or what converts a freeloader to a $14 card. (Peer Reviews 1, 3, 4.)
- **The curated teardown is cherry-picked; the live product isn't.** You route a relieved ADR reader to the gate, they generate their *own* filing, it returns "partial," and it loses to ChatGPT at the moment of truth. Peer Review 5 nails the only proposed guardrail: onboard new users onto *known-good* filings first — pre-screen the tickers they're likely to try. This is the single highest-leverage missed point.
- **Zero instrumentation.** All five prescribe ~10 touches/day for two weeks but define no "engaged," no UTM/funnel on which deep-link converts, and no kill-criteria. With one founder and limited time, not knowing which post drove signups means you can't tell a winning channel from noise. (Peer Reviews 1, 2, 4.)
- **No activation/retention loop.** Acquisition gets all the attention; nobody addresses what trips the 5-summary wall or activates the watchlist change-alert hook to make a visitor *engaged*. (Peer Review 1.)

### The Recommendation

**Concentrate on (c) ADR/foreign-issuer communities, with (b) the curated teardown as the vehicle. Deliberately do NOT touch (a) broad finance Twitter or (d) newsletter outreach until you have a body of work and traction to point at.**

I side with the majority over the Contrarian — but I adopt the Contrarian's best instinct as a constraint. The Contrarian is correct that generic ADR communities are traders, and correct that the side-by-side-vs-ChatGPT question is the real one. The answer to that question *is* native-currency 20-Fs (ChatGPT hallucinates RMB-denominated figures), which is exactly why you must NOT discard the wedge — you must aim it at the right room and protect it from your own quality variance.

Three non-negotiable modifications the raw advice missed:

1. **Onboard onto known-good filings only.** Your curated teardown is cherry-picked; the live product is not. Pre-generate and eyeball 5 foreign filings that do NOT return "partial" (BABA, PDD, SE, MELI, NVO per the eval golden set). When a beta user lands, steer them onto these first. A relieved first session beats an honest-but-broken one.
2. **At this scale, 1:1 beats broadcast.** Spend the daily budget answering a *specific real question* someone just asked about a Chinese ADR filing, with the deep-link as the receipt — not blasting a launch post. Ten relieved people you spoke to directly beat 100 indifferent scrollers.
3. **Instrument and define the payment trigger now.** Put a UTM on every deep-link so you know which post/community converts. And confront the freeloader problem: the 100%-off promo must be a *time-boxed* trial (e.g., 60–90 days), with the conversion ask landing when an engaged user hits the 5-summary wall mid-research on an ADR they care about. $14 is an impulse for someone already hooked — but only if the wall exists and the promo ends.

The SEO content moat (the Expansionist's insight) is real and valuable — treat it as a *free by-product* of posting publicly, not your weeks-horizon engine. It pays off in months; your community 1:1 work pays off in weeks.

### The One Thing to Do First

Monday morning: pick **Alibaba**, generate one gorgeous, screenshot-able teardown from your working deep-link leading with the **period-over-period diff in native RMB** ("here's what BABA's latest 20-F changed YoY, in actual yuan"), verify it does NOT return "partial," put a UTM on the link — then find the single highest-engagement *recent* thread where someone is genuinely asking about BABA's filings, and post it as a direct, value-first answer to that one person. Not a launch. A receipt.
