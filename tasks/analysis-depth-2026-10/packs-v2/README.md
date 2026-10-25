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
| 4 | The net-debt red flag reads "Net debt rose N years in a row to $X" when net cash was below zero throughout (CAT R1, DUK R3, NEE R2, ORCL R3) | Net-cash rows carry "below zero = net debt; a higher percentile = more net cash than peers" |
| 8 | Data checks, each also a red flag, naming every year whose debt or cash basis is broken. `debt_break`: the long-term debt line is missing or zero while debt is still evident (another debt line, or interest held), or a smaller debt line first appears with a jump in total debt that interest expense does not follow. `liquidity_break`: a cash or investment line reported in most years is missing in a single year, beside years that report it at 10% or more of cash and investments, or short-term investments already sit inside cash. An `implied_interest_rate` check outside the debt-break spans. `withheld`: every ID built on a broken year, and every net-cash peer rank and median built on a peer's broken year (`peer_break`), with a checked rank and median in its place under a new ID where three or more peers remain (`peers.checked`; series key `...|<year>|checked`; `peers.replaced` lists the version-1 IDs withheld) | Withheld values, cells and flags are not shown |
| 9 | `margin_gap:net_minus_operating`, net margin minus operating margin (pp) in each year that has both | Margin bridge group |
| 11 | `table_scale: "million"` on passages whose section declares its amounts in millions or, where the section declares no scale, whose document does; the text stays as filed | Bare table-scale dollars read "$126 million"; derived cells in year order |

Breaks found:
- **Debt.** COP (long-term debt not reported in FY2016, and after FY2020), CVX (after FY2021), DE (after FY2021; and
  its current portion of debt is first reported in FY2020, when total debt jumps 36.7% while interest expense falls
  15%, so its FY2016–FY2019 total debt is long-term debt only), KO (after FY2023), ORCL (zero in FY2022), USB
  (after FY2022; a bank, so there is no total debt to withhold).
- **Cash.** Short-term investments missing in one year: MSFT FY2017 ($121.8bn in FY2018), ORCL FY2017, NVDA FY2026
  and COP FY2021. TGT in every year: Target tags its cash, cash equivalents and short-term investments total at its
  cash figure, so the short-term investments are already inside cash.

The implied-rate check fires on none of the 20 outside the debt-break spans. Inside the long-term-debt spans, the
rate (interest expense over the average of the year's and the prior year's total debt) is above 12% in COP FY2016
and FY2022–FY2025, CVX FY2023 and FY2025, DE FY2023–FY2025 and KO FY2025, and under it in COP FY2021, CVX FY2022 and
FY2024, DE FY2022, KO FY2024 and ORCL FY2022. In DE's FY2016–FY2019 onset span it is 3–5%. So the rate alone misses
most first years after a line stops, a one-year gap and an onset: the line tests are the detectors.

**Why withhold rather than label.** A label still leaves a broken figure for the model to state. In eval-v1, DeepSeek
stated broken net cash as fact for COP, CVX, DE and KO. Every one of those sentences cites an ID that version 2
withholds. The IDs stay in the pack, so the gate still reconciles a version-1 output that cites them.

**Peers.** A peer has no data check to disclose a doubt, so its net cash % of revenue enters a version-2 median and
rank only when its comparable year passes every test above over the peer's own ten-year window (the one its pack
reads), and has a long-term debt line unless that window shows no borrowing: no other debt line, and interest
expense implying, at 12%, debt under 10% of its cash and investments (PINS, RDDT, TTD and VRTX stay in). The ranks
and medians this changes (version 1's are withheld):

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

**Not detected.** A line the pack never maps reads as a consistent basis, so none of these tests can see it:
CAT carries no current portion of long-term debt in any year (its companyfacts have no us-gaap current-debt tag),
and KO's short-term investments are in no year of its pack, which maps its marketable securities instead (KO's own
cash, cash equivalents and short-term investments total exceeds its cash by $1.0–3.6bn in FY2018–FY2025). A smaller
line that stops is not tested either, as such lines come and go with maturities: TGT's current portion of long-term
debt after FY2019, KO's marketable securities after FY2020.

## Checked against version 1

- **IDs.** Every version-1 value, series key, passage, data check and red flag is unchanged in version 2, except
  the four reworded net-debt flags (same ID, kind, severity, persistence and evidence).
  `tests/unit/test_trend_depth_pack_v2.py` checks this on these committed files.
- **Size.** The rendered pack grows by 5 to 785 tokens (characters / 2.2): 357 on average, about 0.7%.
- **Gold examples.** REGN, SNAP and JPM pass the gate against these packs, with and without the backstops.
