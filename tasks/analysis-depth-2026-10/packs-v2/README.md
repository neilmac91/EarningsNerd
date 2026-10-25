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
| 8 | `debt_break` data checks naming each span where the long-term debt line is missing or zero while debt is still evident (another debt line, or interest held), each also a red flag; an `implied_interest_rate` check outside those spans; `withheld`: every ID built on a broken year | Withheld values, cells and flags are not shown |
| 9 | `margin_gap:net_minus_operating`, net margin minus operating margin (pp) in each year that has both | Margin bridge group |
| 11 | `table_scale: "million"` on passages from sections that state their amounts in millions; the text stays as filed | Bare table-scale dollars read "$126 million"; derived cells in year order |

Debt breaks found: COP (not reported in FY2016, and after FY2020), CVX (after FY2021), DE (after FY2021),
KO (after FY2023), ORCL (zero in FY2022), USB (after FY2022; a bank, so there is no total debt to withhold). The
implied-rate check fires on none of the 20 outside those spans. Inside them it exceeds 12% in most years for COP,
CVX, DE (16–23% in FY2023–FY2025) and KO. It stays under 12% in the first year after each line stops, where the
average still includes the last complete year, and in ORCL's FY2022. The component test is the stronger detector.

**Why withhold rather than label.** A label still leaves a broken figure for the model to state. In eval-v1, DeepSeek
stated broken net cash as fact for COP, CVX, DE and KO. Every one of those sentences cites an ID that version 2
withholds. The IDs stay in the pack, so the gate still reconciles a version-1 output that cites them.

## Checked against version 1

- **IDs.** Every version-1 value, series key, passage, data check and red flag is unchanged in version 2, except
  the four reworded net-debt flags (same ID, kind, severity, persistence and evidence).
  `tests/unit/test_trend_depth_pack_v2.py` checks this on these committed files.
- **Size.** The rendered pack grows by 43 to 666 tokens (characters / 2.2): 338 on average, about 0.7%.
- **Gold examples.** REGN, SNAP and JPM pass the gate against these packs.
