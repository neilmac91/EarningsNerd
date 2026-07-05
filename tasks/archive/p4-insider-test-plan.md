# P4 — Insider Activity (SEC Form 4): Production Test Plan

**Feature:** Company insider-trading signal derived from SEC Form 4 filings.
**Endpoint:** `GET /api/companies/{ticker}/insiders`
**Status:** Backend complete; **needs live validation on PROD** (the EdgarTools
Form 4 object shapes can only be confirmed against live SEC data — the sandbox
has no `edgartools`/network, so unit tests mock the shapes).
**Owner test pass:** Neil (PROD).

---

## 1. What this feature does

For a given ticker, it pulls the company's most recent **Form 4** filings from
SEC EDGAR (insider transactions by directors, officers, and 10%+ owners),
extracts the **open-market trades only** (buys/sells — not grants or option
mechanics), and returns:

- A **trailing-window summary** (default 90 days): buy/sell counts, share
  totals, dollar values, and **net shares**.
- A **Rule 10b5-1 split** — separating discretionary trades from pre-scheduled
  plan sales (a key signal-quality distinction; plan sales are far less
  informative than discretionary ones).
- The **most recent individual transactions** (up to 30).

It is a **live SEC read** (no database); results are cached in-process for 30
minutes per ticker. Changing `window_days` re-windows the cached data in memory
— it does **not** re-hit SEC.

---

## 2. Components shipped

| File | Role |
|------|------|
| `backend/app/services/ownership_extractor.py` | Pure, defensive Form 4 → row-dict extractor + window aggregator. No edgartools/pandas import (unit-testable). |
| `backend/app/services/insider_service.py` | Async orchestration: resolve ticker → pull Form 4s via EdgarTools (thread pool + circuit breaker) → extract → aggregate → cache. |
| `backend/app/schemas/insiders.py` | Pydantic response models. |
| `backend/app/routers/insiders.py` | `GET /{ticker}/insiders` (mounted at `/api/companies`). 404 unknown ticker, 502 on SEC failure. |
| `backend/main.py` | Router registration. |
| `backend/tests/unit/test_ownership_extractor.py` | 25 unit tests (parsing, coercion, aggregation, 10b5-1 split). |
| `backend/tests/unit/test_insider_service.py` | 5 unit tests (windowing, caching, recent-sort, propagation). |
| `backend/scripts/verify_insider_extraction.py` | **Live** verification: prints raw EdgarTools shapes + extractor output against real SEC data. |

---

## 3. Pre-deploy checks (offline — already green)

Run from `backend/`:

```bash
# Logic tests (no network / edgartools needed):
python3 -m pytest tests/unit/test_ownership_extractor.py tests/unit/test_insider_service.py -v
# Expect: 30 passed.

# Lint:
ruff check app/services/ownership_extractor.py app/services/insider_service.py \
           app/routers/insiders.py app/schemas/insiders.py
```

---

## 4. Live shape verification (run this FIRST after deploy)

This is the most important step — it confirms the EdgarTools Form 4 contract our
extractor relies on still matches live SEC data. Run **on an environment with
`edgartools` installed and SEC network access** (PROD container, or local with
deps):

```bash
cd backend
# Defaults to AAPL, NVDA, JPM:
python scripts/verify_insider_extraction.py
# Or specify tickers known for active insider trading:
python scripts/verify_insider_extraction.py NVDA TSLA JPM
```

**What to look for:**
- Each ticker prints `market_trades columns: [...]` — confirm columns include a
  date, code, shares, price, and acquired/disposed field (casing may vary; the
  extractor matches case-insensitively).
- `obj() type:` should be an `edgar.ownership...Form4` (or similar).
- The summary line shows non-zero buys/sells for at least one ticker.
- Final line: `✅ Extracted N open-market insider transactions ...`
- **Exit code 0** = healthy contract. **Exit code 1** = no transactions
  extracted anywhere → the EdgarTools contract likely drifted; inspect the
  printed raw shapes and adjust `ownership_extractor.py` column aliases.

> If a ticker shows `total_transactions: 0` but others work, that's fine — some
> companies' recent Form 4s are grants/derivatives only (no open-market trades).

---

## 5. API test cases (PROD)

Base URL: `https://api.earningsnerd.io`

### TC-1 — Happy path, active insider trader
```bash
curl -s "https://api.earningsnerd.io/api/companies/NVDA/insiders?window_days=90" | jq .
```
**Expect:** `200`. JSON with `ticker`, `company_name`, `cik`, `window_days: 90`,
a populated `summary` object, and a `transactions` array. `summary.sell_count`
and/or `summary.buy_count` ≥ 1 for an active name.

**Verify the schema** (every key present):
```
ticker, company_name, cik, window_days, total_transactions,
summary: { window_days, buy_count, sell_count, buy_shares, sell_shares,
           buy_value, sell_value, net_shares, net_value,
           discretionary_net_shares, plan_10b5_1_sell_shares,
           last_transaction_date },
transactions: [ { insider_name, insider_title, is_director, is_officer,
                  is_ten_pct_owner, ticker, transaction_date, transaction_code,
                  transaction_label, shares, price, value, acquired_disposed,
                  is_10b5_1, accession, filed_date } ]
```

### TC-2 — Window narrowing reuses cache (fast)
```bash
time curl -s "https://api.earningsnerd.io/api/companies/NVDA/insiders?window_days=90"  > /dev/null
time curl -s "https://api.earningsnerd.io/api/companies/NVDA/insiders?window_days=30"  > /dev/null
```
**Expect:** First call slower (live SEC fetch); second call fast (in-process
cache, just re-windowed). `window_days=30` should return a `summary` covering a
shorter window (counts ≤ the 90-day counts), and `last_transaction_date` stable.

### TC-3 — 10b5-1 split is populated
```bash
curl -s "https://api.earningsnerd.io/api/companies/AAPL/insiders?window_days=180" \
  | jq '.summary | {sell_shares, plan_10b5_1_sell_shares, discretionary_net_shares}'
```
**Expect:** For a large-cap with scheduled selling, `plan_10b5_1_sell_shares`
> 0 and `discretionary_net_shares` distinct from `net_shares`. (If `is_10b5_1`
comes back `null` for all rows, note it — see §7.)

### TC-4 — Unknown ticker → 404
```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://api.earningsnerd.io/api/companies/ZZZZNOTREAL/insiders"
```
**Expect:** `404` with `{"detail":"Company not found"}`.

### TC-5 — Bad `window_days` → 422 (validation)
```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://api.earningsnerd.io/api/companies/AAPL/insiders?window_days=0"
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://api.earningsnerd.io/api/companies/AAPL/insiders?window_days=99999"
```
**Expect:** `422` for both (allowed range is 1–730).

### TC-5b — Error-code reference (for interpreting failures)
| Code | Meaning |
|------|---------|
| `200` | OK (including `total_transactions: 0` — a valid empty answer). |
| `404` | Unknown ticker. |
| `422` | `window_days` outside 1–730. |
| `502` | SEC/EdgarTools fetch failed (incl. the 60s fetch timeout). |
| `503` | SEC EDGAR circuit breaker open (transient — retry shortly). |
| `504` | Request exceeded the 75s endpoint ceiling (should be rare; the 60s fetch timeout normally fires first → 502). |

### TC-6 — Company with no open-market insider trades
Pick a small/quiet company or an ETF-like ticker.
```bash
curl -s "https://api.earningsnerd.io/api/companies/<quiet_ticker>/insiders" \
  | jq '{total_transactions, buys: .summary.buy_count, sells: .summary.sell_count}'
```
**Expect:** `200` with `total_transactions: 0` and zeroed summary — **not** an
error. Empty is a valid answer.

### TC-7 — Data sanity spot-check vs SEC
Open the company on SEC EDGAR's "Insider transactions" view (or
`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=4&CIK=<ticker>`)
and confirm a recent transaction in the API response matches a real Form 4
(insider name, date, shares, buy/sell direction). Numbers won't be exhaustive
(we pull the most recent N filings), but the ones shown should be real.

---

## 6. Interpreting the signal (for the UI/product later)

- **`net_shares > 0`** (net buying) is a classic bullish insider signal;
  net selling is weaker (insiders sell for many non-signal reasons).
- **`discretionary_net_shares`** strips out 10b5-1 plan sales — this is the
  cleaner signal. Lead with it over raw `net_shares`.
- **`transaction_code`** `P`=open-market buy, `S`=open-market sale are the
  meaningful ones; `transaction_label` is the human string.
- `is_ten_pct_owner` / `is_director` / `is_officer` let you weight by who traded.

---

## 7. Known limitations & "needs live validation" notes

1. **EdgarTools shape dependence.** `market_trades` column casing and the
   presence of `get_ownership_summary().has_10b5_1_plan` vary across edgartools
   releases. The extractor is defensive (case-insensitive lookup, `getattr`,
   never raises) but **§4 must be run on PROD** to confirm real columns map. If
   a field is consistently `null` in §5, cross-check against §4's raw dump.
2. **10b5-1 flag is filing-level.** We read the plan flag once per Form 4 and
   apply it to that filing's trades. If a release doesn't expose the flag,
   `is_10b5_1` will be `null` and `plan_10b5_1_sell_shares` will be `0` — the
   buy/sell totals are still correct.
3. **Open-market only.** Grants (`A`), option exercises (`M`), tax withholding
   (`F`), gifts (`G`) etc. are intentionally excluded from `market_trades`, so
   they won't appear. This is by design (signal quality).
4. **Recency-bounded.** We pull the most recent `limit_filings` (default 60)
   Form 4s, then window them. A 730-day window on a hyper-active issuer could be
   truncated by the filing cap; `total_transactions` reflects what was pulled.
5. **No frontend yet.** This PR is backend + endpoint only. UI is a follow-up.

---

## 8. Rollback

The endpoint is additive and read-only (no DB writes, no migration). To disable,
remove the `insiders` router registration in `backend/main.py` and redeploy, or
revert the PR. Nothing else depends on it.

---

## 9. Sign-off checklist

- [ ] §3 offline tests green in CI.
- [ ] §4 live verify script exits 0 on PROD (raw shapes look sane).
- [ ] TC-1 returns full schema with real data.
- [ ] TC-2 second call is fast (cache works).
- [ ] TC-3 10b5-1 split populated (or limitation noted per §7.2).
- [ ] TC-4 unknown ticker → 404.
- [ ] TC-5 invalid window → 422.
- [ ] TC-6 quiet company → 200 with zeros (not an error).
- [ ] TC-7 spot-check matches a real SEC Form 4.
