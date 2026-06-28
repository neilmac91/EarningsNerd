# Council Transcript — Q3: Pricing & Packaging (is $14 flat / Free-5 right?)

_Run: 2026-06-28 · Source: `tasks/council-prep.md` Question #3 · Skill: `llm-council`_

Protocol: 5 advisors (parallel, independent) → anonymized peer review (parallel) → chairman synthesis.
Framed against current pricing/entitlements, the verified competitor band, **and** the decided
strategic spine (#1 Wedge, #2 Moat, #4 Beta UX, #5 Distribution, #7 quality gate) — serve it, not
relitigate it.

---

## Framed Question

EarningsNerd — pricing & packaging: is Free-5 / $14-flat-Pro right; the copilot wall; what to TEST
before public launch. Solo, pre-revenue; closed beta in weeks; WTP unproven; **beta is 100%-off
(comped)**, so the real questions are what to anchor/signal, what to test, and what public-launch
price the beta should de-risk.

Current: Free = 5 summaries/mo (no copilot/export/alerts); Pro = $14/mo or $140/yr (unlimited
summaries, copilot capped 1000 q/mo, PDF/CSV export, real-time alerts, 8-K). Competitor band
~$39–89/mo (Fiscal.ai $39/$79, Koyfin $39/$79, BamSEC $69; cheaper: Stockanalysis $17, Quiver $25),
plus free ChatGPT. EarningsNerd's feature set is *narrower* than the leaders; its edge is the
verification/accountability layer (#2), not breadth.

Three tensions: (a) price level ($14 vs $30–50); (b) the copilot wall (100% Pro vs a free taste);
(c) the free limit (5/mo). Plus: beta packaging + the single experiment to run.

---

## Advisor Responses (de-anonymized)

### The Contrarian

$14 flat is the quiet conversion-killer here, and not for the reason you think. It's not "too low for retail" — it's that it does double damage: it under-prices the prosumer ICP (#1) AND it can't even be tested in a 100%-off beta. You will exit beta with zero WTP signal and a number you picked from vibes.

(a) PRICE LEVEL: Stop anchoring at $14. Anchor the FELT price at the band floor: list Pro at $39/mo ($348/yr), then run beta with the 100%-off promo as a "founding member" comp. That way the price they see is $39 — congruent with the accountability/rigor story (#2/#7) — and the comp feels like a gift, not the product's worth. $14 tells a 10-K reader "toy." Never let them see $14.

(b) COPILOT WALL: Hard wall, no taste. The copilot is your most expensive feature (#4) AND your sharpest differentiator. Giving free users N questions is the textbook margin trap: you eat inference cost on exactly the users least likely to convert, and you spoil the "now you test it" moment that should happen AFTER they've committed. Keep it behind the wall. The 5-summary wall converts; the copilot rewards.

(c) FREE LIMIT: 5 is fine — but only if the wall hits mid-research (#5). Frustration timing beats the number.

THE ONE EXPERIMENT: A real price test, not theater. Mid-beta, present an explicit founding-member offer — "lock in $19/mo for life, or $39 standard later" — with a live Stripe checkout, card required, promo ending in 14 days. Measure who enters a card at $19 vs $39. That's the only WTP datum that survives a comped beta. If nobody cards up at either, your problem isn't price.

### The First Principles Thinker

Stop arguing about $14 vs $39. Both prices assume the customer wants a *subscription*, and that's the unexamined error. The job-to-be-done is "I need to understand THIS filing right now, with the receipts." That's an event, not a habit. A serious investor reads filings in bursts around earnings season, then goes dark for weeks. A monthly fee taxes the dark weeks and guarantees churn the moment the calendar quiets.

The unit of value is *the verified report on one filing* — that is what #2's accountability moat actually sells. Price the unit, not the month.

(a) PRICE LEVEL: Anchor Pro at $39/mo to signal rigor (#1's warning is right — $14 reads "toy"). But the real product is a **credit pack: $5 per filing, or 10 for $39.** This sidesteps the WTP question entirely — you learn the per-filing value, which is the only number that matters.

(b) COPILOT WALL: Don't wall it — it's the *interrogation* that proves the accountability claim (#4). Give the **first filing's copilot fully open, then it's part of the unit.** When someone buys the report, they buy the right to interrogate it. That's coherent value, not a feature gate.

(c) FREE LIMIT: Kill "5/month." Give **one full filing free — report + copilot — then pay per filing.** One complete proof beats five crippled teases.

THE EXPERIMENT: During the comped beta, instrument **how many distinct filings each user actually runs in 30 days.** If the median is 3-4, subscription is a leaky bucket and credit packs win. If it's 15+, sell the subscription. You can't price until you know whether this is a habit or an event.

### The Expansionist

$30/mo for public launch. Not $14, not the $39-89 ceiling. Here is the expansion logic the others will miss: the accountability moat is the only thing in this market with usage-priced upside, and $14-flat throws it away. Trust products earn their margin on verification volume — every copilot interrogation is a chance to charge for "accuracy you can trust," not a cost to be capped.

(a) PRICE: Anchor $30 now (signal it on the page during beta even though it's comped — the comp is "Pro normally $30, free for founders"). $14 permanently caps your ceiling; you can't re-anchor up after launch without churn. $30 sits credibly between Stockanalysis ($17) and Fiscal.ai ($39) — "the verification layer the cheap tools lack, without paying for breadth you won't use."

(b) COPILOT WALL: Don't wall it — and don't give it away flat either. Give free users 3 lifetime copilot questions (not monthly) on their first filing. That is the "now you test it" moment (#4) that PROVES the accountability claim — you cannot sell verifiable trust if no one ever verifies. Then meter it. The real expansion play: copilot is your future credits/overage SKU. 1000/mo is a generous floor for beta; post-launch, watch the power users who blow past it — they are your $79 "Analyst" tier and eventual API/team buyers.

(c) FREE LIMIT: Keep 5 summaries — but the wall that converts is the copilot taste running dry mid-interrogation, not summary count.

EXPERIMENT: Hard A/B the post-beta price — show converting beta users a $30 vs $39 checkout (randomized). Measure conversion AND drop-off reason. You are not testing "will they pay $14"; you are finding the top of the band trust can hold.

### The Outsider

$14/mo lands on me as "this is a side project," not "this is rigorous." When I associate a tool with reading 10-Ks — the thing my actual money decisions ride on — a price that's a third of Koyfin makes me trust it LESS, not more. Cheap accuracy is an oxymoron to a buyer who can't independently verify the accuracy. The price tag is doing your credibility no favors.

(a) PRICE LEVEL: Ship beta with a visible "$29/mo, intro" anchor (comped 100% off). $29 sits at the floor of the serious band — high enough to signal rigor, low enough that a 10-K reader doesn't laugh. Post-beta, test $29 vs $39. Do NOT ship $14; it actively undercuts the trust moat (#2).

(b) COPILOT WALL: Give free users 3 copilot questions, lifetime, not monthly. The copilot IS the "now you test it" moment (#4) — wall it entirely and a skeptic never sees the one thing that proves you're not ChatGPT-with-confidence. Three questions is cheap enough to eat, and hitting that wall mid-interrogation is the most visceral payment trigger you have (#5). Monthly resets train people to wait; lifetime forces the decision now.

(c) FREE LIMIT: 5/month is fine — generous enough to get hooked, tight enough that a real researcher blows through it in one earnings week. Don't touch it.

THE EXPERIMENT: Stop comping silently. Mid-beta, show every engaged user a real checkout at $29 with "founding member, locked forever." Measure how many enter card details even though they could keep using it free. Stated WTP is worthless; a card number at $29 is the only signal that tells you whether $14 was leaving money — and trust — on the table.

### The Executor

Ship $14 flat for beta — it's comped anyway, so the number you advertise is pure signal, not revenue. But put a "$39 at public launch — beta price locked for life" banner on the pricing page NOW. That does two jobs: it anchors the real number you intend to land (#1's prosumer-band move), and it manufactures the payment trigger (#5) by making "lock it now" the action.

(a) PRICE LEVEL: Beta packaging = Free-5 / $14 Pro (100%-off). Post-beta number to TEST = $39/mo, $390/yr. Not $14. $14 hard-codes "toy" into your accountability positioning (#2). You test $39 because that's the bottom of the verified band where TRUST can carry a narrower feature set.

(b) COPILOT WALL: Keep it 100% gated, but give a real taste — 3 copilot questions per filing, free, then wall. The copilot IS the "now you test it" interrogation moment (#4); zero exposure means free users never feel the trust differentiator that justifies $39. Three questions is cheap enough to eat and is the cleanest conversion driver you have. Hard-wall summaries at 5; taste-wall the copilot.

(c) FREE LIMIT: 5/month is fine. Don't touch it. It's the wall that converts mid-research (#5).

THE ONE EXPERIMENT — fake-door price test. On the pricing page, two variants behind a flag: Variant A "Lock $14 for life," Variant B "Lock $39 for life — beta rate." Both click through to the comped 100%-off checkout (nobody pays). Measure click-to-checkout-start rate per variant. That isolates price-level resistance with real intent, zero revenue risk, ships Monday with a feature flag you already have. Clean signal: does $39 halve your clicks, or barely dent them?

---

## Peer Review (anonymized inputs)

Anonymization map for this round: **A** = First Principles · **B** = Expansionist · **C** = Outsider ·
**D** = Executor · **E** = Contrarian.

### Reviewer 1
1. **Strongest: A.** It refuses the framed question and exposes the real unknown — whether filing-reading is a habit or an event. Its experiment (instrument distinct filings/user/30 days during comped beta) is the one input that should *precede* any price decision, and credit packs genuinely sidestep the unprovable WTP problem. Most analytically honest.
2. **Biggest blind spot: B.** It builds an elaborate usage-priced expansion thesis ($79 Analyst tier, API/team buyers) on top of a product with zero proven WTP and a single-filing report. It's pricing the v3 roadmap before validating v1 demand — exactly the over-engineering the brief warns against.
3. **All five missed: annual plans and refund/grandfather mechanics.** Everyone debates monthly price; the $140/$390 yearly option is where serious investors actually commit (and where churn from "dark weeks," A's concern, gets absorbed). Also unexamined: a comped beta with a card-up "founding member" test (C/E) creates real charge/refund obligations and trust risk if you later re-anchor — nobody priced the downside of asking beta users to pay then changing the deal. And none separated WTP from *retention*: a card at signup ≠ month-3 renewal.

### Reviewer 2
1. **Strongest: D.** It alone fully resolves all three tensions while solving the comped-beta paradox: advertise $39 as the locked-for-life anchor (kills the "$14 = toy" risk), taste-wall the copilot at 3 questions/filing, keep Free-5. Its fake-door A/B ($14 vs $39 lock, both routing to the comped checkout) is the cleanest, ship-Monday, zero-revenue-risk way to isolate price resistance. Concrete and serves the spine.
2. **Biggest blind spot: E.** Its hard-wall-no-taste stance contradicts the strategic spine itself: #4 says the copilot IS the "now you test it" proof of the accountability moat, and #2 warns you can't sell verifiable trust if nobody verifies. E's "margin trap" point is real but it spoils the single best demonstration of the differentiator before a skeptic ever commits.
3. **All five missed: annual pricing as the WTP instrument.** A founding-member *annual* lock ($140 or $390) is a far stronger card-up signal than monthly and front-loads cash for a pre-revenue solo founder. Also unexamined: copilot inference cost vs. $14-$39 margin at the 1000-question cap — the actual unit economics that decide whether any price holds.

### Reviewer 3
1. **Strongest: D.** It's the only response that fully respects the brief's constraints while shipping something concrete. It nails the core insight all should have led with: $14 in a 100%-off beta is unmeasurable, so advertise the real anchor ($39) now and lock-for-life as the trigger (#5). Its fake-door price test ships Monday, isolates price resistance with real intent and zero revenue risk — the cleanest experiment proposed. E is close but its "card required" test risks killing a fragile beta's engagement.
2. **Biggest blind spot: A.** It relitigates the strategic spine the brief explicitly forbids ("pricing must serve it, not relitigate it"). Subscription-vs-credit-pack is a real insight, but it ignores that recurring alerts/watchlist are core to the "what changed since last quarter" wedge — an event-based product guts #1's habit loop. Wrong altitude for the question asked.
3. **All five missed:** the annual plan as the WTP instrument. $140/yr vs $390/yr changes churn math entirely, and a comped beta converting to *annual* lock-in is the strongest signal. Also unexamined: copilot inference cost as an actual number — everyone asserts it's "expensive" but nobody sizes whether 3 free questions threatens unit economics at all.

### Reviewer 4
1. **Strongest: D.** It is the only response that resolves all three tensions coherently AND nails the meta-constraint everyone else half-grasps: a comped beta can't test price, so the experiment must be a fake-door with real intent and zero revenue risk. It ships Monday on an existing flag, anchors $39, and isolates price resistance cleanly. C and E are close but their "card required at $19/$29" tests fight the live 100%-off promo.
2. **Biggest blind spot: B.** Its expansion thesis (copilot as metered overage / $79 Analyst tier / API) is fantasy for a pre-revenue solo founder weeks from beta with an unproven core product. It optimizes a pricing ladder before proving anyone pays for rung one. Premature.
3. **All five missed: the annual plan and refund/lock mechanics.** $390/yr (or $140) is the real WTP test — annual prepay is the strongest signal a card-at-checkout can give, and nobody tested monthly-vs-annual mix. Also unexamined: copilot's actual per-user inference cost. Every response asserts it's "expensive" or "cheap enough to eat" without a number — yet that cost is what determines whether any of these prices clear margin.

### Reviewer 5
1. **Strongest: A.** It's the only response that questions the load-bearing assumption everyone else takes for granted — that filing analysis is a *subscription* job. For a bursty, earnings-season-driven ICP, that's the highest-leverage insight, and its experiment (instrument distinct filings/user/30d) generates the data that determines whether ANY monthly price is viable. The packaging follows from evidence rather than vibes.
2. **Biggest blind spot: B.** It builds an elaborate usage-priced expansion thesis ($30 → $79 "Analyst" → API/team) on a product with zero paying users and unproven WTP. Over-engineering a price ladder before validating the first dollar. Also, "3 lifetime copilot questions" contradicts its own "meter it as expansion SKU" logic.
3. **What ALL missed:** the inference-cost math. The copilot is named the most expensive feature, yet nobody priced it — at $14-30/mo with a 1000-question cap, a power user could be gross-margin-negative. No one asked what a copilot question *costs* or whether the cap protects margin. Second miss: annual plans during a comped beta are untested and could lock churners in at a price you haven't validated. The experiment should also capture cost-per-engaged-user, not just WTP.

---

## Chairman's Verdict

### Where the Council Agrees

Five advisors, five different price numbers — but the convergence underneath is loud and unanimous:

- **$14 is wrong and must die before public launch.** Not one advisor defended $14 as the post-beta price. Every single one — including the Executor, who ships it for beta only because it's comped — said $14 hard-codes "toy" into an accountability moat (#1, #2). This is the highest-confidence signal in the entire council.
- **The number the user SEES during beta should be the real anchor, not $14.** Contrarian ($39), Expansionist ($30), Outsider ($29), Executor ($39 banner) all independently arrived at: advertise the band-floor price now, deliver it 100% off as a "founding member" comp. The comp is a gift on top of a serious price — never a $14 sticker.
- **A comped beta cannot test price by itself.** Four of five built their experiment around this paradox. You will exit beta with zero WTP data unless you manufacture an intent signal (fake-door click or card-up).
- **The 5-summary free limit is fine — keep it.** Contrarian, Expansionist, Outsider, Executor all said don't touch it. The conversion lever isn't the *number*, it's the *timing*: the wall must hit mid-research (#5). Only First Principles dissented (one free filing instead).
- **The lock-for-life "founding member" mechanic is the payment trigger** (#5). Multiple advisors landed on it independently as the way to create urgency inside a free beta.

### Where the Council Clashes

**Price level — $29 vs $30 vs $39.** This is a narrow, healthy clash, all inside the verified band:
- *$39 (Contrarian, Executor):* anchor at the band floor of the real competitive set (Fiscal.ai/Koyfin). Trust narrative carries it; you can always discount, never re-anchor up.
- *$29-30 (Outsider, Expansionist):* EarningsNerd's feature set is *narrower* than the $39 leaders (single-filing, ~4 XBRL metrics, no multi-filing diff). $29-30 sits credibly above the cheap tools (Stockanalysis $17) without overclaiming breadth you don't have. Don't price at parity with products that do more.

Both are right about different risks. $39 maximizes signal and ceiling; $29-30 hedges against an over-promise the product can't yet cash. The resolution is to *test the gap*, not pick on vibes.

**The copilot wall — hard wall vs free taste.** The sharpest genuine disagreement:
- *Hard wall (Contrarian, original Executor stance partially):* it's the most expensive feature (#4) AND the reward for committing. Free questions = eating inference cost on the users least likely to convert (the margin trap), and you spoil the "now you test it" moment by giving it away before commitment.
- *Free taste (Expansionist, Outsider, Executor-final, First Principles):* the copilot IS the proof of the accountability moat (#4, #2). A skeptic who never interrogates a filing never sees the one thing that separates you from ChatGPT-with-confidence. Walling it 100% means the differentiator is invisible until after the buy — backwards.

Peer review broke this clash decisively: the spine itself says the copilot is "now you test it" (#4) and "you can't sell verifiable trust if nobody verifies" (#2). A 100% wall contradicts the moat. The taste wins — but bounded.

**Subscription vs. credit packs (First Principles, alone).** Genuinely insightful — filing-reading is bursty/event-driven, so a monthly fee taxes dark weeks. But two peer reviewers correctly flagged it relitigates the spine: recurring alerts + watchlist + "what changed since last quarter" (#1) *are* a habit loop, not an event. Wrong altitude for this question. We keep its experiment, reject its packaging.

### Blind Spots the Council Caught

Peer review surfaced two things **all five advisors missed** — and they matter more than the $29-vs-$39 quibble:

1. **The annual plan is the real WTP instrument, and nobody tested it.** Every advisor debated monthly price; four of five peer reviews independently flagged that **annual prepay ($140 or $390/yr) is the strongest possible card-up signal** for a pre-revenue solo founder — it front-loads cash and absorbs exactly the "dark weeks" churn First Principles worried about. A founding member who locks an *annual* rate is a far stronger datum than a monthly checkout click.

2. **Nobody put a NUMBER on copilot inference cost.** The brief calls it "the most expensive feature." Every advisor asserted "expensive" or "cheap enough to eat" — none computed it. **At a 1000-question/mo cap on a $29-39 plan, a single power user can go gross-margin-negative.** This is load-bearing: it determines whether *any* of these prices clear margin, and whether 3 free taste-questions is trivial or reckless. The founder must size cost-per-question before locking the cap.

A third, quieter catch: **WTP ≠ retention.** A card at signup is not a month-3 renewal. A comped-to-paid annual lock partly solves this; a monthly card-up does not prove durability.

### The Three Tensions Resolved

**(a) PRICE LEVEL — Beta anchor: $39. Post-beta number to test: $39 vs $29.**

Advertise **Pro at $39/mo ($390/yr)** on the pricing page during beta, delivered 100% off as "Founding Member — normally $39, free for beta." The serious 10-K reader must never see $14; it actively corrodes the trust moat (#1's explicit warning, #7's quality-gate logic). $39 is the floor of the verified prosumer band and the number rigor signals.

You de-risk the unproven WTP not by picking a safe-low number, but by **testing $39 against $29** (see The One Experiment). Anchor high, let the data pull you down if it must — you can discount from $39 forever; you can never re-anchor up from $14 without churning your earliest, most loyal users.

**(b) THE COPILOT WALL — Free taste, bounded and lifetime, not 100% Pro.**

Specific rule: **3 copilot questions, LIFETIME (not monthly), on the user's first filing only. Then hard wall.**

- *Lifetime, not monthly:* monthly resets train users to wait and ration; a lifetime cap forces the conversion decision NOW, mid-interrogation — the most visceral payment trigger you have (#5). This is the near-unanimous shape (Expansionist, Outsider, Executor).
- *Why a taste at all:* the spine says the copilot proves the accountability moat (#4, #2). Walling it 100% (Contrarian) hides your single differentiator until after the buy — backwards. The Contrarian's margin point is real, which is exactly why it's **3 questions, once, ever** — bounded hard enough that the inference-cost exposure is trivial *per user*. **Caveat (council blind spot): size the cost-per-question first.** If 3 questions × your worst-case context window is non-trivial at scale, drop to 2. Summaries stay hard-walled at 5; only the copilot gets the taste.

**(c) THE FREE LIMIT — Keep 5 summaries/month. Do not change it.**

Four of five advisors agreed, and they're right. The conversion mechanism is not the count — it's that 5 lets a real researcher get hooked yet blows through it in a single earnings week, hitting the wall mid-research (#5). First Principles' "one free filing" is cleaner in theory but starves the habit loop (#1) that justifies a subscription at all. Leave it.

### The One Experiment to Run

**Ship the Executor's fake-door price test — $39 vs $29, both routing to the comped checkout — and instrument it on the ANNUAL plan, not monthly.**

This is the cleanest signal proposed (endorsed by 4 of 5 peer reviews) and it threads every constraint: ships Monday on a feature flag you already have, zero revenue risk, real purchase intent inside a free beta.

Concretely:
- Two randomized variants on the pricing page: **A = "Lock $29/yr-equivalent founding rate for life," B = "Lock $39 founding rate for life."** Both click through to the live 100%-off checkout — nobody is charged.
- **Primary metric: click-to-checkout-start rate per variant.** Does $39 halve your intent, or barely dent it? That isolates price-level resistance with real intent and tells you the top of the band trust can hold.
- **Lead with the annual frame** ($390 vs $290 "locked for life"), because annual prepay is the strongest WTP signal available (the council's #1 blind spot) and front-loads cash for a solo founder.

Two things to instrument *alongside* it, cheaply, because the council caught them and they gate the whole pricing question:
1. **Distinct filings run per user per 30 days** (First Principles' instrumentation). If the median is 3-4, your subscription is a leaky bucket and you revisit packaging post-launch; if 15+, the subscription is safe. You don't need to act on it now — you need the data before public launch.
2. **Cost-per-engaged-user** (copilot inference $). Pair WTP with actual unit cost so you launch knowing the 1000-question cap and the 3-question taste both clear margin.

**The verdict in one line:** Ship Free-5 / Pro-$39-comped with a 3-question lifetime copilot taste; never show $14; and run the $39-vs-$29 annual fake-door as the one experiment that converts a comped beta into the only WTP signal that survives it.
