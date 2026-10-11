# Brand studio: the handoff

The identity work for EarningsNerd under the brief of 2026-10-11, complete through Phase 10 on
one branch (`claude/adoring-hamilton-y8iuak`, PR #1226). This folder holds the public-safe
records; the system itself lives where the repository already keeps it, and this page is the
index to both. Founder deliberations stay outside the repository (AGENTS.md §7).

**What it is, in one paragraph.** EarningsNerd is the summary that shows its work. The mark and
the wordmark are unchanged (the founder's call, D-015); around them the system adds one graphic
device, the margin and the mark, that only ever means "located in the filing" and "cited": a pale
sage highlight with a hairline under a phrase of ours, a bracket twin in the margin beside a
figure's marker, the filing's own words in the editorial face inside a marked block. Sage never
colours a number; gain and loss keep their own tokens and always carry a sign. The voice is dry
with a pulse, says what the product does in behaviours rather than hedges, and never claims a
figure nobody measured. Every sample figure on every surface is Apple's FY2025 10-K against
FY2024, verified against SEC XBRL.

## Logo files

| File | Use |
|---|---|
| `frontend/public/assets/earningsnerd-logo-light.svg`, `-dark.svg` | The horizontal lockup, unchanged; the header and the auth pane |
| `frontend/public/assets/earningsnerd-logo-mono.svg` | The lockup in one colour, for print and mono contexts (new) |
| `frontend/public/assets/earningsnerd-logo-stacked-light.svg`, `-dark.svg`, `-mono.svg` | The stacked lockup for square and narrow placements (new) |
| `frontend/public/assets/earningsnerd-mark-sage.svg`, `-navy.svg`, `-white.svg`, `-mono.svg` | The EN monogram in its four sanctioned colours, unchanged |
| `frontend/public/assets/earningsnerd-icon-light.svg`, `-dark.svg`, `earningsnerd-appicon.svg` | The favicon and app icon, unchanged |
| `frontend/public/assets/earningsnerd-mask-icon.svg` | Safari's pinned tab, declared in `app/layout.tsx` (new) |
| `frontend/public/og-image.png`, `frontend/scripts/brand/og-template.html` | The social image and its source; regenerate with `npm run brand:assets` |
| `frontend/public/assets/LOGO_README.md` | Clear space, minimum sizes, colours, and what is never done to the mark |

## Guidelines

- `DESIGN.md`: the system, with the new "Graphic device" section and the Marked Copy Rule; the
  frontmatter is the token snapshot that `designSnapshotParity.spec.ts` checks against the code.
- `frontend/DESIGN_SYSTEM.md`: the implementation rules; §3 and §7 carry the device and the accent
  phrase; §12 is the done-gate grep.
- `docs/voice-and-style.md`: the voice: the four rules, the tone, the do and don't table from the
  live site, the five headlines and the tagline, dashes and house conventions.
- `.impeccable/design.json`: the generated sidecar, in parity with `DESIGN.md`.
- [06-system.md](06-system.md): the measured contrast tables for every light and dark pair, the
  type scale, icons, imagery and the device's specification (§6).
- [05-mark.md](05-mark.md): the mark's audit and arrangements; the mark itself does not change.

## Tokens and the device

- `frontend/tailwind.config.js`: every colour, including `brand.*`, `gain.*`, `loss.*`.
- `frontend/app/globals.css`: the "Brand device" block: `.en-mark` (the highlight), `.en-marked`
  (the marked block), `.en-margin` (the gutter) and `.en-margin-mark` (the bracket twin), each
  with its dark pair.
- `frontend/features/marketing/components/MarkedCopy.tsx`: the component that measures the
  markers and places their twins (`EnRef` renders a marker).

## Templates

[templates/](templates/) with its own README: the social post (1080 × 1350, HTML and PNG), the
business card front and back (SVG with trim guide and fill-in layer), the PDF cover (A4), the
email header (600 px tables) and the A5 notebook cover (SVG and preview). Every figure is from
the verified set; every colour is a token; the mark's paths are byte-identical to the mono mark.

## Records by phase

| Phase | File | Outcome |
|---|---|---|
| 0 | [00-audit.md](00-audit.md), [audit/](audit/) | Twenty touchpoints; sameness score 36 of 42 |
| 1 | [01-interview.md](01-interview.md) | Cited answers; eight founder questions with recommendations; assumptions A1 to A9 |
| 2 | [02-battlefield.md](02-battlefield.md), [battlefield/](battlefield/) | Eight competitors, seven captured; the empty space is the act of checking |
| 3 | [03-strategy.md](03-strategy.md) | Positioning, three behaviours, the spectrum, the promise, the never list (S1 to S5) |
| 4 | [04-directions.md](04-directions.md), [directions/](directions/) | Three rendered directions; B, the Marked Copy, chosen by the founder with the mark untouched |
| 5 | [05-mark.md](05-mark.md), [mark/](mark/) | The mark's audit, arrangements, rules and renditions; the drawing unchanged |
| 6 | [06-system.md](06-system.md) | Palette measured, type, spacing, icons, imagery, the device; docs and sidecar in parity |
| 7 | [07-voice.md](07-voice.md) | The voice guide rewritten; every microcopy site changed, with its before and after |
| 8 | [08-applications.md](08-applications.md) | The landing page and every other surface in code; templates; the founder slot; Notable filings dormant |
| 9 | [09-stress-test.md](09-stress-test.md), [stress/](stress/) | Phone, colour-blind, grayscale, misuse, lineup; three fixes; second score 12 of 42 |
| 10 | this page | The handoff |
| all | [decisions-log.md](decisions-log.md) | D-001 to D-020 |

## The pull request

[PR #1226](https://github.com/neilmac91/EarningsNerd/pull/1226), one branch for all ten phases.
Review tier: routine (AGENTS.md §5), because the later phases touch marketing components, the
pricing page's call to action, the consent bar, one product table's number formatting, backend
copy in mail and exports, and their specs. Not touched: prompts, evals, entitlements, auth logic
(`features/auth/api/auth-api.ts` is identical to main; the login and register pages' brand pane,
`AuthShell.tsx`, changed its copy and sample only), billing, the summary pipeline, legal pages,
`vercel.json`, `next.config.js`, workflows.

The review (one Opus lens, a Sonnet refuter per blocker) found three blockers, all upheld and
all fixed: matching claims that had lost the server's scope, a widened search-coverage claim,
and a consent clause broader than the code. The fixes and the should-fix items are recorded in
[09-stress-test.md](09-stress-test.md) §4 and decisions D-021 to D-025.

## Gates this work added

Each fails on a deliberate break of its rule (the PR lists the mutation proofs):

- `frontend/tests/unit/brandCopyRules.spec.ts`: matching claims keep the server's scope; no sage
  number on a public surface; the highlight never on a figure or price; the margin only inside
  `MarkedCopy`, and never without a marker.
- `frontend/tests/unit/markSingleSource.spec.ts`: every rendition of the EN monogram copies the
  canonical outlines and placements byte for byte and never stretches them.
- `frontend/tests/unit/founderNote.spec.tsx` and `waitlistCounter.spec.tsx`: no placeholder in the
  founder slot, no counter below its floor or passing through "0+", the count in neutral ink.

## Gate tails

Run on 2026-10-11 in this container against the branch after it merged main (`0313a49`).

```
frontend: npm run lint                      eslint . --max-warnings 0           exit 0
frontend: npx tsc -p tsconfig.ci.json                                           exit 0
frontend: npm run build                     Next 16 production build, CI's env   exit 0
frontend: npm run test -- --run             Test Files 189 passed (189); Tests 1897 passed (1897)
frontend: npx playwright test (the whole suite; next start, no backend, CI's env:
          NEXT_PUBLIC_API_BASE_URL=http://localhost:8000, WAITLIST_MODE=false,
          NEXT_PUBLIC_ENABLE_ANALYSIS=true; 2 workers)        205 passed, 3 skipped (6.8m)
backend:  ruff check .                      All checks passed!                   exit 0
backend:  bandit -r app -ll                 no findings                          exit 0
backend:  python -m pytest                  11 failed, 6935 passed, 39 skipped in 180.60s
```

The eleven backend failures are not this branch's: the same eleven fail on `origin/main` in this
container (Python 3.13.16): ten `test_copilot_prose_quotations` cases for two code points this
Python's Unicode tables assign, and `test_capacity_readout_error_detail_never_aborts_the_receipt`.
None is in a file this branch touches; CI runs the pinned toolchain.

## Lessons

- `lessons/brand-the-mark-is-protected.md`: never change the EN monogram or the wordmark; brand
  work composes around them. Now held by `markSingleSource.spec.ts`, so `lessons/README.md` lists
  it under the machine-gated lessons.

## Left for the founder

1. The first-person sentence for the founder slot (`frontend/features/marketing/lib/founderNote.ts`;
   it renders nothing until written).
2. The Multi-Period demo regenerated through the pipeline to end at FY2025
   (`frontend/features/analysis/demo/demo-analysis.json`).
3. A curation rule before Notable filings returns to the homepage (`NotableFilings.tsx`).
4. The landing page's section composition (tell T4), as its own PR.
5. Vercel Web Analytics on the privacy page, or gated on consent: `/privacy` does not name it today.
6. Whether sage may mark a count inside the product (three calendar sites, D-023).

In `tasks/todo.md` the first three share the brand studio's founder line; the other three have a
line each.

## Closing

The brief asked for a brand that could be recognised with the logo covered. On the rebuilt pages
the thing you would recognise is small and specific: a phrase with a pale mark under it, a
bracket in the margin, a figure beside the sentence it came from. That is the product's own habit
made visible, which is why it will hold: nothing in it needs a campaign to stay true, only the
rules the gates above now hold. What remains is the founder's voice in the one slot kept for it, and
a page layout that has yet to be as particular as the copy it carries.
