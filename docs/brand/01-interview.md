# Interviewing the brand (2026-10-11)

Phase 1 of the brand studio brief. The record already answers most of the interview; those
answers are extracted first, with their citations. The founder is asked only what blocks the work,
and each question carries the studio's recommended answer so that a one-word reply suffices. Until
the answers arrive, the labelled assumptions in §3 are in force; every later phase cites them.

Founder deliberations behind these questions are not in this repository
([AGENTS.md §7](../../AGENTS.md#7-pr-body-handover-and-open-items-formats)); the founder was told
where they are.

## 1. What the record already answers

| Question | Answer | Where it is written |
|---|---|---|
| What is the product? | AI summaries of 10-Ks, 10-Qs and 20-Fs in which every figure is traceable to the filing's own XBRL fact or text, generated once per filing and shared. | `backend/app/services/summary_pipeline.py` (one orchestrator, CLAUDE.md rule 1); CLAUDE.md rule 2 (filing-only); `frontend/features/marketing/components/PricingSection.tsx` ("generated once per filing and shared") |
| What job does it do? | "Read this filing for me, tell me what changed since last quarter, and show me exactly where it says so." | `tasks/council-prep.md`, verdict log #1 (run #1, 2026-06-28) |
| Who is it for? | The serious individual investor who already reads 10-Ks and wants the tedium removed, not the reading replaced. Secondary: prosumers and analysts who need defensible, citable facts. Not retail who never open a filing; not traders looking for a sentiment score. | `tasks/council-prep.md`, verdict #1 ("retail unanimously rejected"); the brief §0 |
| What is the one honest positioning? | Accountability: "ChatGPT sells confidence; you sell verifiable, source-traced accuracy." | `tasks/council-prep.md`, verdict #2 (chairman) |
| What is the activation moment? | The catch: a confident wrong number beside the verified one, with a click to the source span, then "now you test it" in the Ask box. | `tasks/council-prep.md`, verdict #4 |
| What are the prices and limits? | Pro $39 a month or $390 a year (control arm; a $29 arm exists behind a flag); Free 5 summaries a month, 3 Ask questions, 3 earnings-day alerts, 90-day history; Pro free for beta members while the promo runs. | `frontend/app/pricing/prices.ts`; `frontend/lib/planLimits.ts`; `backend/app/services/entitlements.py` (the only source of plan truth, CLAUDE.md rule 4); `frontend/features/marketing/lib/access.ts` |
| What is access today? | Invite-only beta; the landing page never advertises a signup the API would reject. | `frontend/features/marketing/lib/access.ts` (`DEFAULT_ACCESS_MODE = 'invite'`) |
| What must the brand never be? | A casino or a hype meter: no flashing red and green, no scores, no urgency. Sage never colours a number. | DESIGN.md "The Separate Signals Rule"; `frontend/DESIGN_SYSTEM.md` §1; `docs/competitive-strategy-roadmap-2026.md` §0 ("no flashing red/green casino meters") |
| What is the voice today? | Short, specific, confident, plain; no exclamation marks, no emoji in headings, no em-dashes, no buzzwords; sentence case; middots for compact labels. | `docs/voice-and-style.md`; gate `frontend/tests/unit/no-em-dash-copy.spec.ts` |
| Which theme is the default? | Light (cream) when nothing is stored; dark is a full peer with one sage accent. | `frontend/app/layout.tsx` (`THEME_BOOTSTRAP`), `frontend/DESIGN_SYSTEM.md` §8 |
| What is the type system? | Inter (headings, 600), system-first body, Geist Mono for data and Ask answers, Newsreader only for the filing's own words. | DESIGN.md "Typography", "The Source Voice Rule" |
| How old is the mark? | Three months: the July 2026 rebrand replaced a teal and amber mark with the sage EN. | `frontend/public/assets/LOGO_README.md` |
| What has the founder already decided about the hero? | Headline A ships in the HTML; B and C are a PostHog copy test, not a brand decision. "See a live example" stays the primary action while access is invite-only (decision B). | `frontend/features/marketing/lib/headline.ts`; `tasks/decisions-2026-10-09-design-followups.md` |
| What must stay honest? | Every price, limit, coverage, response-time and security claim stays as it is; no invented metrics, testimonials, logos or press; the reader-quote slot stays unrendered. | `docs/voice-and-style.md` "Claims"; `frontend/app/page.tsx` (`SHOW_QUOTE_SLOT`) |

## 2. Questions for the founder, with the recommended answer beside each

One message, eight questions. The first six are the brief's; the last two surfaced in the audit.

1. **Is the voice allowed to be dry and occasionally funny, within "no exclamation marks, no emoji"? Where is the humour floor?**
   Recommended: yes, dry. The humour is the footnote reader's: understatement, precision, the
   pleasure of having checked. One wry line per surface at most. Never a joke about money, a
   company or a loss; never in a state that costs the reader something (the monthly-limit card, a
   failed generation, a billing error); never inside a summary, a chip, a tally or an export. The
   loading quips remain the one sanctioned playful surface, rewritten drier.

2. **Which face is primary: cream light (the code's default) or navy dark (the June strategy document)?**
   Recommended: cream light. The filing is a paper document; the OG card, the emails and the PDF
   are already light; the product's default is light. Dark stays a full peer for the reading
   session, with the same one accent, and the identity must work in both. The June document's
   "dark-first, mint accent" line is superseded and will be corrected in the same PR that lands
   the system.

3. **Is the EN monogram protected, or on the table if a direction proves it must change?**
   Recommended: the letters are protected; the execution is not. Keep E + N and the rising stroke's
   energy, refine the drawing so that 16px, one colour and embroidery survive (the audit's icon
   board shows the E and N fusing at 16px and 24px). One honest tension to decide: the N's arrow is
   the universal "price went up" glyph on a brand whose first rule is that sage never colours a
   number. The recommendation is to keep the stroke but let Phase 5 test whether its head can read
   as a pen stroke or a mark of checking rather than a chart arrow. If the letters themselves are
   also open, say so; the studio will not assume it.

4. **May the brand name ChatGPT in a side-by-side ("ChatGPT says X, the filing says Y")? If not, how do we show the catch without naming anyone?**
   Recommended: not on the brand surfaces. Naming a competitor makes it the subject, dates the page,
   and invites a rebuttal over a screenshot. Show the catch as the reader's own experience: "From
   memory: $391.0B. In the filing: $416.2B. The first is last year's." (both figures are Apple's
   real XBRL totals for FY2024 and FY2025). A dated, reproducible side-by-side that names the tool
   belongs in a content piece (the council's teardown), where the specificity is the point.

5. **Does the founder want to appear (name, a sentence, a signature) on the page?**
   Recommended: yes, one true sentence in the first person and a first name, placed under the hero
   example or beside the primary action, never a photo requirement. The Nerd is a person; the
   sentence is where the person is. The studio can draft three candidates for approval; the
   founder's own words are better. Nothing ships until the founder approves the exact sentence.

6. **While access is invite-only, is the landing page's job to sell or to qualify?**
   Recommended: qualify. The page should make the right reader recognise themselves ("for investors
   who still check the source") and request an invite, and let the wrong reader leave without a
   fight. That means the copy states plainly who it is for and what it will not do, and the
   primary action stays "See a live example" (decision B). When access opens, the same page sells
   without rewriting, because the qualification is the pitch.

7. **Which price is true?** The brief says Pro is $20 a month or $200 a year; the code shows $39 /
   $390 with a $29 arm behind a flag, and `/pricing` shows "$32.50 /month" on the yearly default.
   Recommended: the code is the brand fact until the founder changes it; the brand work will not
   touch a price, and any pricing copy it writes will read the price from `prices.ts` as the
   landing section already does. If $20 / $200 is a planned change, it is its own PR.

8. **"Notable filings": curate, retitle or omit?** The audit found Delta Air Lines beside seven
   microcap 8-Ks under "High-signal SEC filings … across the whole market."
   Recommended: self-omit under the brand until a curation rule exists (a known-good set, a size
   floor, or 10-K / 10-Q only), then return as "Filed this week" with the filing identity
   vocabulary. The council hid breadth on purpose (verdict #1); a firehose section undoes that.

## 3. Working assumptions until the founder answers

Each is labelled where it is used in later phases.

- **A1 (humour).** Dry, one line per surface, never where it costs the reader, never in evidence.
- **A2 (face).** Cream light is primary; dark is a peer; every colour is a pair.
- **A3 (mark).** Letters protected; drawing refined; the arrowhead is on the table only as a
  refinement question, not a replacement.
- **A4 (naming).** No competitor is named on a brand surface; the catch is shown with two real
  figures from two real fiscal years.
- **A5 (founder presence).** A first-person sentence slot is designed and built; it renders only with
  an approved sentence, like the reader-quote slot.
- **A6 (job of the page).** Qualify, with "See a live example" primary.
- **A7 (price).** $39 / $390 as the code states; no price copy is authored by the brand work.
- **A8 (notable filings).** Self-omit until curated.
- **A9 (scope).** Nothing under `backend/prompts`, `backend/evals`, entitlements, auth, billing, the
  summary pipeline or the legal pages is touched; the EN letters, the sage accent, the type roles and
  the theme default change only with the founder's word.
