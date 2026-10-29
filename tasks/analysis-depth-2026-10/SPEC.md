# Content specification: the AI trend analysis

This document says what the "AI trend analysis" section of Multi-Period Analysis must contain. Three
things implement it. The proposed prompt (`backend/prompts/trends-depth-analyst-agent.md`) carries the
same rules in the generator's voice. The grounding rule (`GROUNDING-RULE.md`) defines what each sentence
may claim and what it must cite. The gold examples (`gold/`) show the specification applied by hand to an
operating company (Regeneron), a loss-maker (Snap) and a bank (JPMorgan Chase).

## Reader and job

The reader is a self-directed investor looking at up to ten fiscal years (or twelve quarters) of one
company. The metrics table and KPI strip already show every headline figure, so the analysis earns its
place only by saying what those figures do not show on their own:

1. which events bent the trend, and why;
2. what drove growth, and whether profit kept pace;
3. why margins and cash conversion moved;
4. how strong the balance sheet is, against the company's own history and its peers, and where the cash went;
5. what has gone wrong, ranked by how much it matters;
6. which numbers would change the picture in the next filing.

A sentence that restates a table cell without relating it to something else is padding. The census found
95.7% of the current section's numeric sentences add no figure the table lacks; the target is the
reverse.

Length: 450 to 700 words and at most 30 sentences of under 30 words each, seven sections in a fixed
order, every sentence typed (fact, comparison, cause or judgement) and cited under the grounding rule.
Development runs showed every model overshooting a bare word limit (780 to 1,070 words); naming a sentence
cap per section and a sentence length brought them into 547 to 731.

## Sections

### 1. The arc (3–5 sentences)

- **Purpose:** the shape of the window in one breath, and the turning points with their causes.
- **Required:** the top line at the start and end of the window and its CAGR. Then one to three
  inflection years: the year, the size of the move (revenue growth, margin change or the swing in net
  income) and the cause the company gave for it, quoted from that year's 10-K. If a data check affects an
  inflection (a recast year, a basis break), the sentence says so.
- **Not:** a year-by-year list, or a cause the filings do not state.

### 2. What drove growth

- **Revenue drivers:** the products or segments that contributed most to growth over the window and in
  the latest year, in percentage points of prior-year revenue, with each one's share of revenue. Name the
  concentration in the largest driver and the company's stated reason for the latest move.
- **Operating leverage:** whether operating income grew faster or slower than revenue: the incremental
  operating margin, or operating-cost growth against revenue growth. Say which cost line explains the gap.
- **Per share:** EPS growth against net income growth when the share count moved materially, and why
  (buybacks, dilution).

### 3. Margins and costs

- Operating margin, and gross margin where reported, in the latest year against the window median, high
  and low.
- The margin bridge for the latest year and for the largest move in the window: the percentage-point effect
  of each cost line (cost of revenue, R&D, SG&A, other). Each line's movement is explained from a passage
  where the 10-K gives one.
- Below-the-line items (tax rate, other income) when they make net margin diverge materially from
  operating margin.

### 4. Cash conversion

- Operating cash flow and free cash flow against net income, latest and typical (median), and the
  free-cash-flow margin.
- Capital intensity: capex against revenue and against D&A, with any stated investment programme.
- What moved conversion (working capital, capex step-ups, stock-based compensation, tax timing), with
  the cause cited.

### 5. Balance sheet and capital allocation

- Net cash or net debt (cash and investments less debt), its change, and its size against revenue.
- Liquidity (current ratio) where meaningful.
- Peer context: percentile rank and peer median for the metrics the pack carries, naming the peer group
  and its size. Peers come from EarningsNerd's own facts store, built the same way as the company's figures.
- Capital allocation: buybacks, dividends and acquisitions against free cash flow, and the share-count
  effect.

### 6. Red flags (up to four, ranked)

- Ranked by severity (high, medium, low), then by persistence (how many consecutive periods). Code screens
  the candidates: margin compression runs, revenue declines, weak cash conversion, receivables or inventory
  build, debt build, liquidity, runway, persistent losses, stock-compensation intensity, concentration in a
  declining product, tax-rate swings, bank efficiency and credit costs, and data-quality problems.
- Each flag, in one or two sentences, states what happened, how big it is, for how long, the stated cause
  if any, and why it matters.
- The writer may drop a candidate the evidence shows is benign (saying why) and may add one the evidence
  supports. If none apply, say which conditions were screened.

### 7. What to watch (2–3 items)

- Each item names a metric, a numeric threshold anchored on a cited level (the latest value, the window
  low, high or median, or guidance quoted from a passage), the direction that would confirm or reverse
  the story told above, and the filing it will appear in.
- Phrased as conditions, never as forecasts.

## Profiles

| Profile | What changes |
|---|---|
| **Bank** | There is no revenue, gross margin or current ratio. Revenue is net interest income plus noninterest income. The margin story is the efficiency ratio and the credit-loss provision as a share of revenue. Operating cash flow is not a meaningful earnings-quality measure for a bank, so the cash section says so and covers capital return (buybacks and dividends against net income) instead. The balance-sheet section covers return on average equity, loans against deposits and allowance coverage. Regulatory capital ratios (CET1) come only from passages. |
| **Loss-maker** | The margin story is the path to breakeven: operating loss as a share of revenue, incremental margin, and what the company says is driving costs. The cash story is burn and runway: cash and investments against burn. The capital story includes dilution (share-count growth) and stock-based compensation, both against revenue and against the operating loss. Positive free cash flow during net losses gets its own explanation (usually stock-based compensation). |
| **Insurer** | Premiums earned and the loss ratio carry the margin story. *(Not exercised in this evaluation: the current facts layer ingests insurers' and managed-care companies' top line as premiums, so the page offers no annual window for them at all. That is a separate defect, recorded in the report.)* |

## What the evidence can support

Driver evidence comes from three places, and the analysis can only be as deep as the evidence for the
company in front of it. `drivers/README.md` maps each node of the driver tree to its source for the five
companies examined: structured XBRL facts, filing text only, or not available. Where a node is text-only
or unavailable, the analysis says less, and it never fills the gap with a guess.

## Style

- Plain words; fiscal years named as the table names them (FY2025); the company's own product and segment
  names.
- Dollars to three significant figures; percentages and percentage points to one decimal; margin changes
  in pp.
- No hype, no hedging filler, no investment advice, no price targets, no forecasts beyond the company's
  own guidance.
- Judgements are few (one or two per section at most) and visibly marked as analysis.
- When evidence for a section is missing, one sentence says what is missing.
