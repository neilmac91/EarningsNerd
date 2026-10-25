# Evidence packs, version 2

`trend-depth-pack-v2` for the 20 evaluation companies: version 1 (`../packs/`, the input of the frozen runs
eval-v1 and dev-v4) plus the pack fixes of `../DEEPSEEK-ERRORS.md` §2. Version 1 stays where it is and renders
exactly as before; the builder refuses to overwrite it.

```bash
cd backend
python -m evals.trend_depth.evidence --out ../tasks/analysis-depth-2026-10/packs-v2 --fulltext-end 2026-10-24 \
  REGN VRTX SNAP RIVN JPM USB COST TGT NVDA AMD COP CVX PG KO CAT DE NEE DUK MSFT ORCL
```

Built from the harness cache only (no network connection, no cache write). `--fulltext-end 2026-10-24` is the day
version 1 was built: the EDGAR full-text queries are cached under their end date. Run the same way from the
same cache, the version-1 code rebuilds every version-1 pack byte for byte.

## What version 2 adds

Every addition has a new ID after the last version-1 ID, peers included, and red flags are numbered after the
last version-1 flag. So every version-1 value keeps its ID and value, and a version-1 output still checks against
a version-2 pack.

| Fix | In the pack | In the render (`render.py`, version 2 only) |
|---|---|---|
| 3 | `low:ocf_to_ni` and `median:ocf_to_ni`, the window low and median of operating cash flow / net income (not for banks or insurers; no window high, no peer level) | Window reference levels group |
| 4 | The net-debt red flag reads "Net debt rose N years in a row to $X" when net cash was below zero throughout (DUK R3, NEE R2, ORCL R3); where an `unmapped_line` check names a year of the run it quotes no level and names the omission instead (CAT R1: "Net debt rose 2 years in a row through FY2025; its level is left out, as total debt and net cash omit long-term debt due within one year") | Net-cash rows carry "below zero = net debt; a higher percentile = more net cash than peers" |
| 8 | Data checks, each also a red flag, naming every year whose debt or cash basis is broken. `debt_break`: the long-term debt line is missing or zero while debt is still evident (another debt line, or interest held), or a smaller debt line first appears with a jump in total debt that interest expense does not follow. `liquidity_break`: a cash or investment line reported in most years is missing in a single year, beside years that report it at 10% or more of cash and investments, or short-term investments already sit inside cash. An `implied_interest_rate` check outside the debt-break spans. `unmapped_line`, appended after the others: a line the filer reports that the pack sums nowhere, at 10% or more of the total it is missing from, in a year no break check names: long-term debt due within one year (us-gaap LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths) while total debt sums no current-debt line and a noncurrent long-term tag, or the filer's own cash, cash equivalents and short-term investments total above the pack's cash plus short-term investments; it withholds nothing. `withheld`: every ID built on a broken year, a long-term line reported as zero there (ORCL's FY2022 [F185, X213]), and every net-cash peer rank and median built on a peer's broken year (`peer_break`), with a checked rank and median in its place under a new ID where three or more peers remain (`peers.checked`; series key `...|<year>|checked`; `peers.replaced` lists the version-1 IDs withheld) | Withheld values, cells and flags are not shown |
| 9 | `margin_gap:net_minus_operating`, net margin minus operating margin (pp) in each year that has both | Margin bridge group |
| 11 | `table_scale: "million"` on passages whose section declares its amounts in millions or, where the section declares no scale, whose document does; the text stays as filed | Bare table-scale dollars read "$126 million"; derived cells in year order |

Breaks and unmapped lines found:
- **Debt.** COP (long-term debt not reported in FY2016, and after FY2020), CVX (after FY2021), DE (after FY2021; and
  its current portion of debt is first reported in FY2020, when total debt jumps 36.7% while interest expense falls
  15%, so its FY2016–FY2019 total debt is long-term debt only), KO (after FY2023), ORCL (zero in FY2022), USB
  (after FY2022; a bank, so there is no total debt to withhold).
- **Cash.** Short-term investments missing in one year: MSFT FY2017 ($121.8bn in FY2018), ORCL FY2017, NVDA FY2026
  and COP FY2021. TGT in every year: Target tags its cash, cash equivalents and short-term investments total at its
  cash figure, so the short-term investments are already inside cash.
- **Unmapped lines** (`unmapped_line`, nothing withheld). CAT FY2016–FY2025: long-term debt due within one year of
  $5.3–9.1bn a year ($7,120m at FY2025, the balance sheet's "Long-term debt due within one year"), beside $30.7bn of
  noncurrent long-term debt, so its FY2025 net debt reads $26.2bn [D456] against $33.4bn with it. KO FY2016–FY2017 and
  FY2021–FY2025: its own cash, cash equivalents and short-term investments total exceeds the pack's cash and
  short-term investments by $5.5bn and $3.9bn, then $1.0–3.6bn a year. Run on every peer over its own ten-year
  window (PLD aside: too few years of core data for any pack), the test finds the same two and no other: KO (staples) and CAT (industrials), in their comparable FY2025
  too, where neither enters a rank or median the render shows (KO is left out of PG's for its debt break, and DE's
  own net cash, so its rank, is withheld).

The implied-rate check fires on none of the 20 outside the debt-break spans. Inside the long-term-debt spans, the
rate (interest expense over the average of the year's and the prior year's total debt) is above 12% in COP FY2016
and FY2022–FY2025, CVX FY2023 and FY2025, DE FY2023–FY2025 and KO FY2025, and under it in COP FY2021, CVX FY2022 and
FY2024, DE FY2022, KO FY2024 and ORCL FY2022. In DE's FY2016–FY2019 onset span it is 3–5%. So the rate alone misses
most first years after a line stops, a one-year gap and an onset: the line tests are the detectors.

**Why withhold rather than label.** A label still leaves a broken figure for the model to state. In eval-v1, DeepSeek
stated broken net cash as fact for COP, CVX, DE and KO. Every one of those sentences cites an ID that version 2
withholds. The IDs stay in the pack, so the gate still reconciles a version-1 output that cites them.

**Peers.** A peer has no data check to disclose a doubt, so its net cash % of revenue enters a version-2 median and
rank only when its comparable year passes the debt-break, onset, liquidity-gap and double-count tests over the
peer's own ten-year window (the one its pack reads), and has a long-term debt line unless that window shows no
borrowing: no other debt line, and interest expense implying, at 12%, debt under 10% of its cash and investments
(PINS, RDDT, TTD and VRTX stay in). Two tests
are not run on peers: the implied-rate test, which outside the break spans fires on a comparable year only for MPC
and PSX (energy), both left out already for having no long-term debt line, and the unmapped-line test, which
withholds nothing. The ranks and medians this changes (version 1's are withheld):

| Company | Version 1 | Version 2 | Peers left out |
|---|---|---|---|
| PG | 33rd percentile, median -1.0% (n=6) | 67th, -32.3% (n=3) | KO, KMB, MDLZ: debt line broken |
| CAT | 43rd, -35.6% (n=7) | 50th, -38.0% (n=6) | DE: debt line broken |
| COST | 100th, -4.4% (n=6) | 100th, -18.3% (n=4) | DG: no long-term debt line; TGT: cash line broken |
| AMD | 100th, -13.9% (n=6) | 100th, -17.3% (n=5) | NVDA: cash line broken |
| DUK | 25th, -228.4% (n=4) | 33rd, -235.4% (n=3) | SO: no long-term debt line |
| NEE | 0th, -228.4% (n=4) | 0th, -235.4% (n=3) | SO: no long-term debt line |
| RIVN | 75th, 17.8% (n=4) | none: two peers left | F, GM: no long-term debt line (GM's interest implies $37bn of debt) |

COP, CVX, DE and KO (debt), and NVDA and TGT (cash), lose their rank to their own broken latest year; their peer
groups also hold broken peers (MPC and PSX, energy). MSFT, ORCL, REGN, SNAP and VRTX are unchanged; JPM and USB
have no net-cash rank.

**Not detected.** A line the pack never maps reads as a consistent basis, so the break tests cannot see it; the
unmapped-line test sees one only through a figure the filer reports itself. These lines have no such figure, and
nothing names or withholds them (amounts from the cached companyfacts and 10-K text):
- **Debt.** TGT's current portion of long-term debt in FY2020–FY2025 ($1,144m, $171m, $130m, $1,116m, $1,636m and
  $2,130m, tagged LongTermDebtAndCapitalLeaseObligationsCurrent, which the pack does not map). Its long-term line is
  tagged LongTermDebt, which holds the current portion for other filers (DUK FY2016: $47.9bn, its $45.6bn noncurrent
  plus $2.3bn current), so the due-within-a-year test does not read it.
- **Cash.** PG's available-for-sale securities, a current asset beside cash in FY2017–FY2019 ($9,568m, $9,281m,
  $6,048m; PG tags no cash and short-term investments total), so its cash and investments are cash alone there: its
  FY2019 and FY2020 growth reads 65.0% [D116] and 281.7% [D167], about -13% and +57% with them. KO's short-term
  investments in FY2018–FY2020 ($2,025m, $1,467m, $1,771m), offset in the test by the marketable securities the pack
  maps, which KO's own total leaves out; and KO's marketable securities after FY2020 ($1.1–1.9bn), outside both, so
  KO's `unmapped_line` amounts are a floor. VRTX's current available-for-sale securities in FY2016–FY2017 ($251m,
  $423m). DE's marketable securities, which its 10-K counts as a source of liquidity ($0.45–1.41bn a year). CAT's
  available-for-sale debt securities and time deposits, "highly liquid and available for current operations" by its
  10-K, inside prepaid expenses and other assets ($3.85bn, $1.98bn and $1.23bn at FY2023–FY2025). An investment
  tag alone is no test: DUK's available-for-sale securities sit mostly in its nuclear decommissioning trusts, and
  NVDA's include its cash equivalents ($6.9bn at FY2018: $3.1bn of marketable securities and $3.8bn of cash
  equivalents).

## Checked against version 1

- **IDs.** Every version-1 value, series key, passage, data check and red flag is unchanged in version 2, except
  the four reworded net-debt flags (same ID, kind, severity, persistence and evidence).
  `tests/unit/test_trend_depth_pack_v2.py` checks this on these committed files.
- **Size.** The rendered pack grows by 5 to 985 tokens (characters / 2.2): 403 on average, about 0.8%.
- **Gold examples.** REGN, SNAP and JPM pass the gate against these packs, with and without the backstops.
