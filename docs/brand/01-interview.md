# Interviewing the brand (2026-10-11)

Phase 1 of the brand studio brief. The record already answers most of the interview; those
answers are extracted first, with their citations. The founder was asked only what blocked the
work and answered on 2026-10-11 (§2); the answers in force are labelled A1 to A9 (§3), and every
later phase cites them by label.

The questions as asked, the studio's recommendations and the deliberation behind them are in the
founder's private notes, not in this repository
([AGENTS.md §7](../../AGENTS.md#7-pr-body-handover-and-open-items-formats)).

## 1. What the record already answers

| Question | Answer | Where it is written |
|---|---|---|
| What is the product? | AI summaries of 10-Ks, 10-Qs and 20-Fs in which each figure is traced to the filing's own XBRL fact or text where it can be, and the ones that cannot be are counted rather than guessed; generated once per filing and shared. | `backend/app/services/summary_pipeline.py` (one orchestrator, CLAUDE.md rule 1); CLAUDE.md rule 2 (filing-only); `frontend/features/marketing/components/PricingSection.tsx` ("generated once per filing and shared") |
| What job does it do? | "Read this filing for me, tell me what changed since last quarter, and show me exactly where it says so." | `tasks/council-prep.md`, verdict log #1 (run #1, 2026-06-28) |
| Who is it for? | The serious individual investor who already reads 10-Ks and wants the tedium removed, not the reading replaced. Secondary: prosumers and analysts who need defensible, citable facts. Not retail who never open a filing; not traders looking for a sentiment score. | `tasks/council-prep.md`, verdict #1 ("retail unanimously rejected"); the brief §0 |
| What is the one honest positioning? | Accountability: "ChatGPT sells confidence; you sell verifiable, source-traced accuracy." | `tasks/council-prep.md`, verdict #2 (chairman) |
| What is the activation moment? | The catch: a confident wrong number beside the verified one, with a click to the source span, then "now you test it" in the Ask box. | `tasks/council-prep.md`, verdict #4 |
| What are the prices and limits? | At the audit, Pro $39 a month or $390 a year (control arm; a $29 arm behind a flag), since changed by main's #1009 to $25 a month or $240 a year; Free 5 summaries a month, 3 Ask questions, 3 earnings-day alerts, 90-day history; Pro free for beta members while the promo runs. | `frontend/app/pricing/prices.ts`; `frontend/lib/planLimits.ts`; `backend/app/services/entitlements.py` (the only source of plan truth, CLAUDE.md rule 4); `frontend/features/marketing/lib/access.ts` |
| What is access today? | Invite-only beta; the landing page never advertises a signup the API would reject. | `frontend/features/marketing/lib/access.ts` (`DEFAULT_ACCESS_MODE = 'invite'`) |
| What must the brand never be? | A casino or a hype meter: no flashing red and green, no scores, no urgency. Sage never colours a number. | DESIGN.md "The Separate Signals Rule"; `frontend/DESIGN_SYSTEM.md` §1; `docs/competitive-strategy-roadmap-2026.md` §0 ("no flashing red/green casino meters") |
| What is the voice today? | Short, specific, confident, plain; no exclamation marks, no emoji in headings, no em-dashes, no buzzwords; sentence case; middots for compact labels. | `docs/voice-and-style.md`; gate `frontend/tests/unit/no-em-dash-copy.spec.ts` |
| Which theme is the default? | Light (cream) when nothing is stored; dark is a full peer with one sage accent. | `frontend/app/layout.tsx` (`THEME_BOOTSTRAP`), `frontend/DESIGN_SYSTEM.md` §8 |
| What is the type system? | Inter (headings, 600), system-first body, Geist Mono for data and Ask answers, Newsreader only for the filing's own words. | DESIGN.md "Typography", "The Source Voice Rule" |
| How old is the mark? | Three months: the July 2026 rebrand replaced a teal and amber mark with the sage EN. | `frontend/public/assets/LOGO_README.md` |
| What has the founder already decided about the hero? | Headline A ships in the HTML; B and C are a PostHog copy test, not a brand decision. "See a live example" stays the primary action while access is invite-only (decision B). | `frontend/features/marketing/lib/headline.ts`; `tasks/decisions-2026-10-09-design-followups.md` |
| What must stay honest? | Every price, limit, coverage, response-time and security claim stays as it is; no invented metrics, testimonials, logos or press; the reader-quote slot stays unrendered. | `docs/voice-and-style.md` "Claims"; `frontend/app/page.tsx` (`SHOW_QUOTE_SLOT`) |

## 2. What the founder decided

Eight questions went to the founder in one message on 2026-10-11: the voice's humour, the primary
face, whether the mark could change, naming a competitor in a side-by-side, the founder's presence
on the page, whether the page sells or qualifies while access is invite-only, the price, and
Notable filings. The founder answered "proceed", with one instruction: the logo and monogram do
not change. The answers are A1 to A9 below.

## 3. The answers in force

Each is labelled where it is used in later phases. They began as working assumptions while the
questions were open (D-006). The founder's "proceed" of 2026-10-11 put them in force as written,
with A3 tightened by the instruction about the mark; any of them changes on the founder's word.

- **A1 (humour).** Dry, one line per surface, never where it costs the reader, never in evidence.
- **A2 (face).** Cream light is primary; dark is a peer; every colour is a pair.
- **A3 (mark).** Answered on 2026-10-11: the logo and monogram do not change at all (letters,
  arrow, wordmark). Brand work adds arrangements and rules only (`lessons/brand-the-mark-is-protected.md`).
- **A4 (naming).** No competitor is named on a brand surface; the catch is shown with two real
  figures from two real fiscal years.
- **A5 (founder presence).** Keep the founder absent from the website. The previously built empty
  sentence slot, configuration and hero mount are retired; see [08-applications.md §6](08-applications.md#6-the-founder-slot).
- **A6 (job of the page).** Qualify, with "See a live example" primary.
- **A7 (price).** The price is whatever the code states ($39 / $390 at the audit; $25 / $240 since main's #1009); no price copy is authored by the brand work.
- **A8 (notable filings).** Self-omit until curated.
- **A9 (scope).** Nothing under `backend/prompts`, `backend/evals`, entitlements, auth, billing, the
  summary pipeline or the legal pages is touched; the EN letters, the sage accent, the type roles and
  the theme default change only with the founder's word.
