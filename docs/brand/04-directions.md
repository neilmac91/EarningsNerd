# Three directions (2026-10-11)

Phase 4 of the brand studio brief. Three distinct concepts, each four lines (idea, mood, signature
element, risk), each shown as a rendered landing hero in both themes at 1440 and at 390, built from
the real tokens (`frontend/tailwind.config.js`), the real faces (Inter, Geist Mono, Newsreader) and
only the figures the audit re-verified against SEC companyfacts ([00-audit.md](00-audit.md) §4).
The sources are committed beside the renders (`directions/direction-{a,b,c}.html`, `mockup.css`) so
any direction can be re-rendered or edited; they are documentation, not application code. Every
direction keeps the EN monogram (A3), one sage accent in both themes (A2) and the existing type
roles; direction C would add one role. Each cites the strategy page by label (S1 to S5).

[The lineup, light above dark](directions/lineup.jpg)

## A. The Receipt (the ledger territory)

[light 1440](directions/direction-a-light-1440.jpg) · [dark 1440](directions/direction-a-dark-1440.jpg) · [390](directions/direction-a-light-390.jpg)

- **Idea.** Every claim is a line item, and the summary is the itemised receipt for the filing: the
  figure, its XBRL fact, its check, and a total of what matched and what was withheld (S1, S2.2).
- **Mood.** Ledger paper: hairlines, tabular figures, a dashed rule, a stamp, a tear. The calm of a
  till receipt you have already checked against the bag.
- **Signature element.** The tally rule: a dashed hairline carrying a count ("5 of 5 matched · 0
  withheld"), repeated as the section divider across the site, and the stamp that states the count.
- **Risk.** It reads transactional, and the receipt tear is a fintech cliché of the last decade;
  with five mono figures on the hero it drifts toward the terminal look the battlefield says to
  avoid. It also puts the count in front of the reading, and the product is reading first.

Why it still works in five years: a count of what was checked is a claim no copilot makes without
building the checker, and the device is typographic, so it survives any UI fashion.

## B. The Marked Copy (the annotated document territory)

[light 1440](directions/direction-b-light-1440.jpg) · [dark 1440](directions/direction-b-dark-1440.jpg) · [390](directions/direction-b-light-390.jpg)

- **Idea.** EarningsNerd is the reader's own marked-up copy of the filing: the AI reads and writes
  it up, every figure carries a bracketed mark in the margin, and the filing's words sit beside
  the summary in their own voice with the passage highlighted (S1, S2.2, S2.3). The catch is shown
  as the reader's own experience, two real figures from two real years (D-012, A4).
- **Mood.** A desk, a pencil, a good footnote. Paper and ink, one green highlighter, nothing
  decorative.
- **Signature element.** The margin: a hairline gutter with bracketed citation marks (`[F1]`, `[1]`)
  positioned to the lines they belong to (the mockup measures each inline marker and places its
  margin twin on that line), and the sage mark, a highlight bar under a phrase or beside a
  passage, which is the monogram's rising stroke laid flat. On the hero it underlines "shows its
  work"; on a surface it marks the located span.
- **Risk.** Executed literally it turns skeuomorphic (yellow highlighter, paper grain); the margin
  costs width on phones and must collapse into the chip; a highlight that is not tied to the
  provenance vocabulary reads as decoration. The phone render shows the margin surviving at 36px.

Why it still works in five years: every competitor will have a copilot; none will own the checked
copy. The device is the product's own behaviour (the span highlight, the citation marker, the chip)
made visible, so it cannot be copied without copying the work, and it is legible at 16px (a bracket)
and on paper (a margin).

## C. The Nerd's Notebook (the field notebook territory)

[light 1440](directions/direction-c-light-1440.jpg) · [dark 1440](directions/direction-c-dark-1440.jpg) · [390](directions/direction-c-light-390.jpg)

- **Idea.** The brand is the person the name promises: the Nerd, who reads the footnotes for
  pleasure and writes numbered notes you can check, signed. The italic *Nerd* becomes a voice,
  not just a wordmark (S3 colleague, A1).
- **Mood.** A ruled page, numbered entries, a dry aside in the margin ("worth a look"), a
  signature line.
- **Signature element.** The numbered note (01, 02 … in the data face on a ruled page, as the
  summary's section rail already numbers itself) and the
  italic aside, which would be the one added type role: the Nerd's own voice in Inter italic,
  distinct from the filing's serif and the summary's upright sans.
- **Risk.** A character on a trust product is a risk to S3's colleague-not-oracle line the moment
  it becomes cute; a second voice must be rationed or it leaks into evidence surfaces where the
  Source Voice Rule forbids it; a notebook is a metaphor, and metaphors age faster than devices.

Why it still works in five years: a voice is the hardest thing to copy and the easiest to keep,
and the numbered note is already how the summary is built (the numbered section rail); but the identity
lives in the writing, so it depends on the founder keeping the voice, not on the system.

## Comparison

| | A. The Receipt | B. The Marked Copy | C. The Nerd's Notebook |
|---|---|---|---|
| Ownable without the logo | the tally rule and stamp | the margin and the mark | the numbered note and the aside |
| What the product already proves | the tally sentences | the span highlight, chips, `[F1]` markers, the Source pane | the numbered section rail, the quips |
| Recognisable at 16px | a dashed rule: weak | a bracket: yes | a numeral: weak |
| In grayscale and on paper | yes | yes | yes |
| On a phone at 390 | five mono rows crowd the fold | the margin collapses to 36px and holds | the ruled page holds |
| Fits the voice (S3) | quiet, plain; colder than colleague | quiet, plain, colleague | warm end of dry; risk of cute |
| Type roles | existing three | existing three | adds one (the aside) |
| Mark (A3) | keeps EN; the stamp competes with it | keeps EN; the stroke becomes the mark | keeps EN; the italic carries the name |
| Five-year test | survives fashion, but counts are copyable | survives: it is the work made visible | survives only if the voice is kept |
| Main risk | terminal drift, transactional tone | skeuomorphism if literal | character creep into evidence |

## Recommendation

**B, the Marked Copy.** It is the one idea the product already proves on every surface: the located
span, the bracketed marker, the chip, the "Source" pane. It gives the brand a graphic device (the
margin and the mark) that reads at favicon size and on a business card, a copy register (the person
who checked), and a use for the monogram's stroke that is not a chart arrow (A3). It is the only
one of the three that makes "I can check it" (S4) visible before the reader has read a word. Phase 5
refines the mark along the stroke; Phase 6 specifies the margin and the mark in CSS and SVG with
scale, placement, colour in both themes and misuse; Phase 7 writes the voice of the person who
marked the copy; Phase 8 applies it.

What B takes from the others: A's tally rule as the section divider (the count belongs after the
reading, not before it), and C's dry aside as the one sanctioned place for the Nerd's voice (the
loading quips, the empty states), rationed by A1.

**This is the founder's choice.** Phases 5 to 10 wait on it ([01-interview.md](01-interview.md)
asks the other questions in the same message). "B" is enough of an answer; "B with A's rule" or
"C" are equally fine, and the studio proceeds the same way from any of them.

## Provenance of the renders

- Figures: Apple FY2025 10-K (accession 0000320193-25-000079) and FY2024 comparatives, verified
  2026-10-11 against SEC companyfacts; the tallies shown ("5 of 5", "3 of 3") count the figures on
  each mockup, checked by the audit, and are not the product's own count for filing 3 ("3 of 5
  checkable figures"), which the product computes over a different set.
- The excerpt in B is the risk passage the live hero example located in the filing text, cut where
  the product cuts it. "Nine parts" repeats the live hero's own claim (`LandingHero.tsx`); the
  rendered section rail varies by filing ("Segments" and "What changed" are conditional), which
  Phase 7 must keep in mind when it writes a count.
- The mockups say "passage", never "page": the product cites a section and highlights a passage;
  it does not compute page numbers.
- Rendered with Playwright 1.56.1 and the preinstalled Chromium at device scale 2; Inter and Geist
  Mono from the repository's committed font files, Newsreader from Google Fonts at render time.
