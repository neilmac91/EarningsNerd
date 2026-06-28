# LLM Council Transcript — Q2: The Moat ("why won't ChatGPT eat this?")

> Run #2 from `tasks/council-prep.md`. Date: 2026-06-28.
> Special case: 3/5 advisors had been captured as partials in a prior run (Contrarian,
> First Principles, Expansionist). This run added the Executor + Outsider, then ran a full
> anonymized peer-review round across all 5, then chairman synthesis.

---

## Framed question

EarningsNerd (earningsnerd.io) is an AI SEC-filing analysis platform built by a SOLO,
pre-revenue founder launching a CLOSED BETA within weeks. Pressure-test its defensibility —
for investors and for deciding where to spend scarce build time. A skeptic argues: "Anyone can
paste a 10-K into ChatGPT; Bloomberg/Koyfin/AlphaSense already serve professionals; SEC EDGAR
data is free and public. This is an AI wrapper with a 12-month head start, not a moat."
Candidate moats: (a) citation/provenance verification + an eval harness gating numeric accuracy;
(b) foreign-issuer/ADR coverage in correct native currency; (c) workflow lock-in via watchlists,
change-alerts, saved history; (d) a proprietary verification dataset (claim → source span →
pass/fail) accumulating with every summary. Are these real, durable moats or features with a
head start? What would actually make EarningsNerd defensible, and what is the strongest *honest*
answer to "why won't ChatGPT eat this?"

---

## Advisor responses

### The Contrarian (captured partial)
Candidate moats are mostly features, not moats — none compound meaningfully with scale; citation
verification, ADR currency, watchlists, and even the verification dataset are replicable or don't
get structurally stronger as you grow. The uncomfortable flip side that *helps*: ChatGPT won't
bother eating this, because retail SEC analysis is a thin niche not worth OpenAI's attention. The
threat isn't the giants — it's that the niche is small. The only defensible bet is distribution
(owning a wedge of users), not a technical moat. Stop polishing features hoping one becomes a moat.

### The First Principles Thinker (captured partial)
"Moat" is the wrong lens at pre-seed. The real question is not "do you have a moat" but "can this
founder reach a wedge of users who genuinely care, faster than the category commoditizes?"
Defensibility at this stage is speed to a specific audience, not structural barriers that don't
exist yet. The candidate moats are mostly post-hoc rationalizations. The Alibaba-in-RMB catch is
the most telling signal — proof of founder taste and attention to detail, not a moat in itself.
Stop constructing a moat narrative; start proving you can win a niche.

### The Expansionist (captured partial)
There's bigger upside hiding in (d). Every verified citation mints a labeled (claim → source span
→ pass/fail) pair; over thousands of summaries that becomes a proprietary "financial verification"
data asset general LLMs don't have — which can become a product in its own right: a verification
API or "trust-stamp" other tools, newsletters, or fund workflows embed. The reframe: ChatGPT sells
confidence; you sell accountability. Where being confidently wrong about a number has real
consequences, accountability is what people pay for and what compounds as the dataset grows.

### The Executor (this run)
The skeptic's "anyone can paste a 10-K into ChatGPT" is true, and that's exactly why the real moat
isn't any of the four — it's the verification dataset (d), but ONLY if instrumented now. The others
are features with a head start. Cheap & high-leverage this week: you already log claim → source →
pass/fail; make it queryable rows and start counting. A moat you can't measure is a story, not an
asset. By beta end you want a number: "X claims verified, Y% catch rate on hallucinations general
LLMs would emit." That stat is the investor answer AND a rising accuracy ceiling. Expensive &
skippable: don't build more peer/insider/ADR features. ADR-native-currency (b) is a genuine wedge
but a correctness bug-fix copyable in a weekend once someone cares. Lock-in (c) is worthless
pre-traffic — you can't lock in zero users. Honest answer to "why won't ChatGPT eat this": at the
high end, OpenAI will never assume liability for a wrong number in a financial filing. The eval
harness + provenance lets you SAY "every figure is traced to source and gated." That's a
positioning + trust product, not a tech product. Monday: instrument the log into queryable rows,
ship a per-summary "verified against source" badge users click to the exact span, write the stat down.

### The Outsider (this run)
The eval harness gating numeric accuracy is the only thing that made me lean in. (a) Trust layer is
your real story but you're burying it — "citations + provenance verification" is jargon. What lands:
"ChatGPT will confidently tell you the wrong revenue number. We catch that before you see it." Show
a side-by-side and I believe you instantly. (b) Native currency — I don't know why it matters until
you say what breaks: "ChatGPT reads Alibaba's filing and quietly converts numbers wrong, so your
comparison is garbage." Alone it's a niche feature. (c) Lock-in — you have zero users; lock-in for
whom? A someday-moat. (d) Verification dataset — sounds impressive, means nothing yet; a dataset
that improves nothing I can observe is a spreadsheet, not a moat. Honest answer to "why won't
ChatGPT eat this?": ChatGPT optimizes for sounding right; you're the only one who proves it. One
demo of ChatGPT getting a number wrong and you catching it is worth more than any feature.

---

## Peer review (anonymized A–E; A=First Principles, B=Executor, C=Expansionist, D=Outsider, E=Contrarian)

- **Strongest:** B (Executor) — 3 votes; D (Outsider) — 2 votes. B praised as the only response that
  converts the abstract into a measurable, shippable Monday plan + the liability framing; D praised
  for turning each "moat" into a falsifiable, demoable claim. Seen as complementary.
- **Biggest blind spot:** C (Expansionist) — **unanimous 5/5**. Romanticizes (d) as a sellable
  verification-API/trust-stamp without confronting that the labels are tiny, self-generated, and
  self-referential (circular ground truth); span-verification may be a deterministic XBRL/regex
  problem, not a learned one with a data network effect; and no obvious buyer for a verification API
  from a pre-revenue solo founder. Mistakes accumulation for a flywheel.
- **What ALL missed (peer-review catches):**
  1. **Distribution mechanics** — everyone hand-waved *how* the wedge gets acquired. Named channel
     the advisors missed: shareable public per-filing summary pages (SEO/sitemap already in the
     codebase) as a top-of-funnel acquisition loop; long-tail ticker/ADR SEO; newsletter embeds.
  2. **Ground-truth circularity** — (d)'s value depends on *who* judges pass/fail; self-graded LLM
     labels can encode the same blind spots they claim to catch, so it may not compound without
     human-audited ground truth.
  3. **Liability cuts both ways** — claiming "every figure traced and gated" invites the very lawsuit
     OpenAI avoids; EarningsNerd also can't *guarantee* a number, so the trust claim needs hedging.
  4. **Willingness-to-pay / unit economics** — will price-sensitive retail pay for accuracy they
     can't easily detect they're missing? Inference cost vs WTP untouched.
  5. **Switching cost ≈ zero** for a free public tool → retention, not "moat," is the real
     pre-revenue metric.

---

## CHAIRMAN VERDICT

### Where the Council Agrees
- The four candidate "moats" are **features with a head start, not durable structural moats.** Every
  advisor lands here independently.
- The realest thing is the **trust / verification layer (a)+(d) — but as positioning, not as a
  self-compounding asset.** The honest answer to "why won't ChatGPT eat this" converges almost
  word-for-word: *ChatGPT sells confidence; you sell accountability.* OpenAI will never assume
  liability for a wrong financial number; EarningsNerd's wedge is provable, source-traced accuracy.
- Defensibility at pre-seed = **reaching a wedge of users faster than the category commoditizes**,
  not structural barriers (First Principles + Contrarian).
- **Lock-in (c) is inert pre-traffic** — "you can't lock in zero users."

### Where the Council Clashes
- **Is the verification dataset (d) a compounding asset or a vanity spreadsheet?** Expansionist: a
  genuine proprietary data asset → verification API. Executor: the only real moat candidate, *but
  only if instrumented and measured now* ("a moat you can't measure is a story"). Outsider + the
  unanimous peer review push back hard: self-graded labels are circular, the asset is tiny/noisy,
  span-verification may be deterministic not learned, and no one buys a verification API from a
  pre-revenue founder. **Resolution: (d) is a proof/evidence asset, not a network-effect flywheel.**
- **Build vs. show.** Executor → instrument + ship the badge + write the stat. Outsider → make the
  gap undeniable with one killer demo. **These aren't contradictory — the demo is the badge made
  undeniable.**

### Blind Spots the Council Caught
The five peer-review catches above — chiefly: **distribution was the gaping hole** (advisors named
it but none said *how*; reviewers did — public summary pages + ticker/ADR SEO); **ground-truth
circularity** undermines (d); **liability cuts both ways**; **WTP/unit-economics unexamined**;
**retention, not moat, is the real pre-revenue metric.**

### The Recommendation
Stop calling these moats. At pre-seed you don't have one and don't need one — you need a **wedge +
proof.** The single honest, durable answer to "why won't ChatGPT eat this" is **accountability:**
ChatGPT sells confidence; you sell verifiable, source-traced accuracy backed by an eval harness, in
a domain where a confidently-wrong number has consequences. Operationalize it three ways before
beta: (1) instrument the claim→source→pass/fail log into queryable rows and count a catch-rate stat;
(2) make the gap undeniable with one side-by-side demo of ChatGPT hallucinating a figure you flag;
(3) hedge the liability honestly ("traced to source," not "guaranteed"). Treat the verification
dataset as **evidence, not a future API** — don't over-invest. The real defensibility work is
**distribution + retention** (→ Q5). Don't build more features; ADR-currency is a genuine taste
signal but copyable — keep it as a wedge-marketing proof point, not a build priority.

### The One Thing to Do First
**Build the one side-by-side demo:** a real filing where ChatGPT states a wrong/unsourced number
and EarningsNerd flags it (or sources it correctly), with click-through to the exact source span.
It simultaneously (a) makes the trust positioning undeniable to a first-time user, (b) is the
investor answer to "why won't ChatGPT eat this," and (c) doubles as the highest-leverage
distribution content. Capture the catch-rate stat while building it.
