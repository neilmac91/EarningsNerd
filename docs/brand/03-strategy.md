# Brand strategy (2026-10-11)

Phase 3 of the brand studio brief. One page. Every visual and verbal decision in the later phases
cites a line on it by its label (S1 to S5). It rests on the council's verdicts
(`tasks/council-prep.md`, #1, #2, #4), the audit ([00-audit.md](00-audit.md)), the interview record
and assumptions ([01-interview.md](01-interview.md)) and the battlefield
([02-battlefield.md](02-battlefield.md)).

## S1. Positioning

**For the individual investor who still reads the filing, EarningsNerd is the summary that shows its
receipts: each figure traced to the filing's own XBRL or text where it can be, and a plain count of
where it could not, unlike the copilots and terminals that sell confidence, because a number you can
check is worth more than a number you have to trust.**

## S2. Three values, as behaviours the product already performs

1. **We say "withheld" rather than guess.** When a risk excerpt cannot be matched to the filing
   text, the server withholds it and the page counts it: "N withheld because the evidence could not
   be matched" (`frontend/features/summaries/components/SummaryRisks.tsx`; the projection the server
   writes). A summary with gaps it admits is the product; a summary without gaps it hides is not.

2. **We count only what we checked.** The filing page states its own score in scoped words: "3 of 5
   checkable figures matched the company's XBRL · 4 of 4 risk excerpts located in the filing text"
   (`frontend/features/filings/components/FilingIdentity.tsx` and the filing page's tally line). A
   chip says "Verified in filing" or "Cited. Open the section to confirm.", never more
   (`frontend/features/filings/components/SourceTrace.tsx`).

3. **We keep the filing's words in the filing's voice.** Risk excerpts are the filing's own words,
   located before they show, and are set in the filing's own face; summaries and answers never
   borrow it (the Source Voice Rule, DESIGN.md "Typography"; `.filing-reader` in
   `frontend/app/globals.css`; the excerpt rows in `SummaryRisks.tsx`). A quote the server could
   not find in the filing reads Cited, never Verified in filing. The reader can always tell who is
   speaking.

One summary per filing, generated once and shared (CLAUDE.md rule 1), is the economics behind all
three: the product can afford to check because it checks once.

## S3. Personality spectrum

Each axis is marked where the brand sits, on a line from the left word to the right word.

| Axis | Position | In a sentence |
|---|---|---|
| dry ◆──────── warm | dry, with a pulse | The warmth is in the care, not the words. A wry line at most, never a joke about money. (A1) |
| plain ◆──────── ornate | plain | Hairlines, tabular figures, one accent. Decoration is a misuse. |
| quiet ◆─────── loud | quiet | No scores, no flashing, no counters, no exclamation marks. The loudest thing on the page is a figure. |
| patient ◆────── urgent | patient | Filings arrive on a schedule; the reader is not late. "Markets move fast" is the competitor's sentence. |
| colleague ◆───── oracle | colleague | We read it with you and show our work; we do not pronounce. "Here is where it says so", never "trust us". |

## S4. The promise, in the customer's words

**"I can check it."**

Said in full: "It read the filing the way I would have, and when I wanted to check a number, it was
already pointing at the page."

## S5. The never list

- Never a score, a rating, a gauge, a sentiment meter or a flashing red-green anything. Gain and loss
  colour a direction, with a glyph, and nothing else (the Separate Signals Rule).
- Never urgency: no "markets move fast", no countdowns, no "before the next call".
- Never sage on a number.
- Never a claim beyond what the server checked: no "verified" without a match, no "all claims",
  no "100%".
- Never a disclaimer where a sentence from the product belongs. Scope is stated once, as a behaviour
  ("where we could not match it, we say so"), not repeated as a hedge.
- Never a placeholder: no fake quote, no grey bars standing in for words, no counter at zero.
- Never the filing's voice for our words, or our voice for the filing's.
- Never an exclamation mark, an emoji in a heading, an em-dash in copy, or a buzzword from the
  voice guide's list.
- Never a named competitor on a brand surface (A4).
- Never cross-filing insight outside the labelled Change Report (CLAUDE.md rule 2).
