# Methods appendix

Everything below ran on 2026-10-24 in a Claude Code cloud container. This appendix keeps the code
that produced each number, so a reader can rerun it. The scripts stay here as text, not as
executable files in the repository (CLAUDE.md: one-offs live in `backend/scripts/`, and this
report adds none).

## Production census through public endpoints

The cloud container has no route to Cloud SQL, and the Ops workflow runs only main's committed SQL.
So the census reads production through two public, read-only endpoints:
- `GET /api/companies/{ticker}/peers?metric={concept}`: one indexed read, no SEC call, no write.
  For a company with no SIC code it scopes to the company alone. It returns the company's newest
  `is_latest` FY row for the concept, with the same `provenance_for_fact` projection the analysis
  dataset uses.
- `GET /api/filings/{id}/fundamentals`: a filing's own FY rows, with provenance.

The population is the 687 companies in the production sitemap, times the 26 annual concepts of
`DATASET_CONCEPT_ORDER`: 17,862 requests at two workers, about 7 requests a second, with no
errors. Of those companies, 27 hold annual facts at all. The per-year pass then made one
`/api/filings/company/{ticker}` read per company that holds facts. That endpoint serves from the
database and refreshes from SEC in the background, as any page view does. It then read the
fundamentals of each company's three newest annual filings. Sector comes from SEC's
`company_tickers.json` and `submissions/CIK##########.json`, paced at 4 requests a second under
the app's public identity, because production stores no SIC codes.

The full population, every company and every fiscal year, needs the database. That run is
[`ops/detection/mpa_notation_frequency.sql`](../../ops/detection/mpa_notation_frequency.sql). It
reaches production only through the Ops workflow's `detection-sql` operation, after it merges to
main. Its classifier was checked against `provenance_for_fact` on a local PostgreSQL. Every branch
gave the same review, withheld, dagger, reason and legacy counts in both
([parity script](#detection-sql-parity-script)).

### `census.py`

```python
"""Read-only production census of MPA notation flags through the public peers endpoint.

For each sitemap company and each MPA annual concept, GET /api/companies/{t}/peers?metric=c and
record the subject's latest FY is_latest value state (method, validation, reasons, fiscal_year).
Two workers, so production's pool keeps headroom. Resumable: skips (ticker, concept) already written.
"""
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

OUT = Path(sys.argv[1])
TICKERS = [t.strip() for t in Path(sys.argv[2]).read_text().split() if t.strip()]
CONCEPTS = [
    "revenue", "net_interest_income", "noninterest_income", "premiums_earned", "net_investment_income",
    "gross_profit", "gross_margin", "operating_income", "operating_margin", "net_income", "net_margin",
    "earnings_per_share", "eps_diluted", "operating_cash_flow", "capital_expenditures", "free_cash_flow",
    "investing_cash_flow", "financing_cash_flow", "total_assets", "cash_and_equivalents", "current_assets",
    "current_liabilities", "working_capital", "current_ratio", "long_term_debt", "shareholders_equity",
]
done = set()
if OUT.exists():
    for line in OUT.read_text().splitlines():
        row = json.loads(line)
        done.add((row["ticker"], row["concept"]))
lock = threading.Lock()
session = requests.Session()
session.headers["User-Agent"] = "EarningsNerd-notation-census/1.0 (read-only)"


def fetch(ticker: str, concept: str) -> None:
    url = f"https://api.earningsnerd.io/api/companies/{ticker}/peers"
    for attempt in range(4):
        try:
            r = session.get(url, params={"metric": concept}, timeout=30)
            if r.status_code == 200:
                d = r.json()
                s = d.get("subject") or {}
                pv = s.get("provenance") or {}
                row = {
                    "ticker": ticker, "concept": concept, "sic": d.get("sic"), "unit": d.get("unit"),
                    "has_value": s.get("value") is not None, "has_row": bool(s.get("period_end")),
                    "fiscal_year": s.get("fiscal_year"), "period_end": s.get("period_end"),
                    "method": pv.get("method"), "validation": pv.get("validation"),
                    "reasons": pv.get("reasons"), "calculation_version": pv.get("calculation_version"),
                    "formula": pv.get("formula"),
                }
            else:
                row = {"ticker": ticker, "concept": concept, "http": r.status_code}
                if r.status_code >= 500 and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
            break
        except requests.RequestException as exc:
            row = {"ticker": ticker, "concept": concept, "error": type(exc).__name__}
            time.sleep(2 ** attempt)
    with lock:
        with OUT.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
    time.sleep(0.15)


jobs = [(t, c) for t in TICKERS for c in CONCEPTS if (t, c) not in done]
print(f"{len(jobs)} requests to make", flush=True)
start = time.time()
with ThreadPoolExecutor(max_workers=2) as pool:
    for i, _ in enumerate(pool.map(lambda job: fetch(*job), jobs)):
        if i % 500 == 0:
            print(f"{i} done, {time.time() - start:.0f}s", flush=True)
print("finished", flush=True)
```

### `sic.py`

```python
"""Ticker -> CIK (SEC company_tickers.json) -> SIC (submissions), paced at 4 req/s, app identity."""
import json, sys, time
from pathlib import Path
import requests
UA = "EarningsNerd/1.0 (support@earningsnerd.io)"
s = requests.Session(); s.headers.update({"User-Agent": UA, "Accept-Encoding": "gzip"})
tickers = Path("tickers.txt").read_text().split()
m = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in s.get("https://www.sec.gov/files/company_tickers.json", timeout=60).json().values()}
out = {}
if Path("sic.json").exists(): out = json.loads(Path("sic.json").read_text())
for t in tickers:
    if t in out: continue
    cik = m.get(t.upper()) or m.get(t.upper().replace(".", "-"))
    if not cik: out[t] = None; continue
    r = s.get(f"https://data.sec.gov/submissions/CIK{cik}.json", timeout=60)
    if r.status_code == 200:
        d = r.json(); out[t] = {"cik": cik, "sic": d.get("sic"), "sicDescription": d.get("sicDescription"), "category": d.get("category"), "fy_end": d.get("fiscalYearEnd")}
    else:
        out[t] = {"cik": cik, "http": r.status_code}
    time.sleep(0.25)
Path("sic.json").write_text(json.dumps(out))
print(len(out), sum(1 for v in out.values() if v and v.get("sic")))
```

### `analyze.py`

```python
"""Summarize the production peers census: notation frequency by metric, sector, fiscal year, reason."""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
rows = [json.loads(line) for line in (HERE / "peers.jsonl").read_text().splitlines()]
sic = json.loads((HERE / "sic.json").read_text())

DIVISIONS = [  # SEC/OSHA SIC divisions by two-digit major group
    (1, 9, "Agriculture"), (10, 14, "Mining"), (15, 17, "Construction"), (20, 39, "Manufacturing"),
    (40, 49, "Transport, comms & utilities"), (50, 51, "Wholesale trade"), (52, 59, "Retail trade"),
    (60, 67, "Finance, insurance & real estate"), (70, 89, "Services"), (91, 99, "Public administration"),
]
PHARMA = {"2834", "2835", "2836"}


def sector(ticker):
    info = sic.get(ticker) or {}
    code = info.get("sic")
    if not code:
        return "Unknown"
    if code in PHARMA:
        return "Pharma & biotech (2834-2836)"
    major = int(str(code)[:2])
    return next((name for lo, hi, name in DIVISIONS if lo <= major <= hi), "Other")


errors = [r for r in rows if "http" in r or "error" in r]
cells = [r for r in rows if r.get("has_row")]
companies = {r["ticker"] for r in rows}
print(f"requests {len(rows)}, errors {len(errors)} ({collections.Counter(r.get('http') or r.get('error') for r in errors)})")
print(f"companies {len(companies)}, latest-year cells with a row {len(cells)}")


def state(r):
    if not r["has_value"] or r["validation"] == "unavailable":
        return "withheld"
    return r["validation"]


def table(key, title, top=None, min_cells=0):
    groups = collections.defaultdict(list)
    for r in cells:
        groups[key(r)].append(r)
    out = []
    for k, g in groups.items():
        n = len(g)
        if n < min_cells:
            continue
        review = sum(state(r) == "needs_review" for r in g)
        withheld = sum(state(r) == "withheld" for r in g)
        calc = sum(r["method"] == "calculated" for r in g)
        legacy = sum(r["calculation_version"] is None and r["method"] == "calculated" and "legacy_calculation" in (r["reasons"] or []) for r in g)
        out.append((k, n, review, withheld, calc, legacy, len({r["ticker"] for r in g})))
    out.sort(key=lambda t: (-t[2] / t[1], -t[1]))
    print(f"\n### {title}\n| {title.split(' by ')[-1]} | companies | cells | needs review (a) | % | withheld (b) | calculated † | % | legacy calc |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for k, n, review, withheld, calc, legacy, comp in out[:top]:
        print(f"| {k} | {comp} | {n} | {review} | {100 * review / n:.1f}% | {withheld} | {calc} | {100 * calc / n:.1f}% | {legacy} |")
    return out


total = table(lambda r: "all", "Latest-year cells by all")
table(lambda r: r["concept"], "Latest-year cells by metric")
table(lambda r: sector(r["ticker"]), "Latest-year cells by sector")
table(lambda r: r["fiscal_year"], "Latest-year cells by fiscal year", min_cells=20)
table(lambda r: "+".join(sorted(r["reasons"] or [])) or "none", "Latest-year cells by reason")
table(lambda r: f"{r['method']} / {state(r)}", "Latest-year cells by method and state")

# Company exposure: how many companies show >=1 review cell among the 20 table metrics' latest values.
by_company = collections.defaultdict(list)
for r in cells:
    by_company[r["ticker"]].append(r)
exposure = collections.Counter()
for t, g in by_company.items():
    n = sum(state(r) == "needs_review" for r in g)
    exposure["0" if n == 0 else "1-2" if n <= 2 else "3-5" if n <= 5 else ">5"] += 1
print("\n### Companies by count of latest-year cells needing review\n| review cells | companies | % |\n|---|---:|---:|")
for k in ("0", "1-2", "3-5", ">5"):
    print(f"| {k} | {exposure[k]} | {100 * exposure[k] / len(by_company):.1f}% |")
headline = {"free_cash_flow", "net_margin", "revenue", "net_income", "operating_margin"}
hit = sum(any(state(r) == "needs_review" and r["concept"] in headline for r in g) for g in by_company.values())
print(f"\nCompanies whose latest revenue, net income, FCF, operating or net margin needs review: {hit} of {len(by_company)} ({100 * hit / len(by_company):.1f}%)")
json.dump({"companies": len(by_company), "cells": len(cells), "exposure": exposure, "headline_hit": hit},
          open(HERE / "summary.json", "w"), indent=1)
```

### `years.py`

```python
"""Per-fiscal-year notation state of filing-owned annual rows for the companies that hold facts.

For each such company: one filings-list read (DB-first, as a page view), then the fundamentals of its
three newest annual filings (10-K/20-F/40-F). Read-only GETs, paced.
"""
import collections, json, time
from pathlib import Path
import requests
HERE = Path(__file__).parent
rows = [json.loads(l) for l in (HERE / "peers.jsonl").read_text().splitlines()]
tickers = sorted({r["ticker"] for r in rows if r.get("has_row")})
s = requests.Session(); s.headers["User-Agent"] = "EarningsNerd-notation-census/1.0 (read-only)"
out = []
for t in tickers:
    filings = s.get(f"https://api.earningsnerd.io/api/filings/company/{t}", timeout=60).json()
    annual = [f for f in filings if f.get("filing_type") in ("10-K", "20-F", "40-F")][:3]
    for f in annual:
        d = s.get(f"https://api.earningsnerd.io/api/filings/{f['id']}/fundamentals", timeout=60).json()
        for c in d.get("concepts", []):
            for p in c["points"]:
                pv = p["provenance"]
                out.append({"ticker": t, "filing": f["id"], "filed": f["filing_date"][:10], "concept": c["concept"],
                            "fiscal_year": p["fiscal_year"], "method": pv["method"], "validation": pv["validation"],
                            "reasons": pv["reasons"], "has_value": p["value"] is not None})
        time.sleep(0.3)
    time.sleep(0.3)
(HERE / "years.json").write_text(json.dumps(out))
print(len(tickers), "companies,", len(out), "filing-owned annual rows")
```

## Local reproduction of the REGN page

The analysis routes need a Pro session, so the page and its exports were reproduced on a local stack
on the same commit as this report's base (`a41c6e4`):
- PostgreSQL 16.
- `uvicorn main:app` with `ENVIRONMENT=development` and the production model provider (DeepSeek,
  `deepseek-flash`). The DeepSeek balance read USD 44.97 before the first run, under a USD 0.25
  ceiling. The backend log records exactly one model call for the whole study: `analysis_chat`,
  `deepseek-flash`, estimated USD 0.000206. Every later run served that narrative from cache. The
  balance read USD 43.85 afterwards. The key is shared, and other usage accounts for the rest of
  the drop.
- `next dev` with `NEXT_PUBLIC_ENABLE_ANALYSIS=true`, `NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS=true`
  and `WAITLIST_MODE=false`.
- A local Pro user.

REGN was ingested by the app's own coverage route (SEC companyfacts, the app's SEC identity). A
fresh ingest gives zero review flags, because every row it writes carries version-1 lineage.
Production differs because some rows are owned by filings written before 2026-10-10. The local
database was calibrated to production by removing the lineage record from the 11 cells whose state
reproduces production's counts exactly:

```sql
UPDATE financial_fact SET provenance = NULL
WHERE is_latest AND fiscal_period = 'FY' AND (
  (concept IN ('operating_margin','net_margin','free_cash_flow') AND fiscal_year IN (2023,2024,2025))
  OR (concept IN ('working_capital','current_ratio') AND fiscal_year = 2024));
```

After that, the local dataset's notes read: 11 figures need review (a), 16 comparisons carry note
a, 3 unavailable (b), 50 calculated †. That is production's strip, character for character.
Production's citation for the FY2025 current ratio ("Calculated from recorded inputs") rules out
the alternative split of working capital and current ratio across FY2024 and FY2025.

### `capture.js`

```js
// Drive the local MPA page for REGN: run the analysis once, then capture both themes and every export.
// Usage: node capture.js <outDir> [--exports]
const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const OUT = process.argv[2]
const BASE = 'http://localhost:3000'
fs.mkdirSync(path.join(OUT, 'screens'), { recursive: true })
fs.mkdirSync(path.join(OUT, 'exports'), { recursive: true })

async function setTheme(page, theme) {
  const current = await page.evaluate(() => document.documentElement.classList.contains('dark') ? 'dark' : 'light')
  if (current !== theme) {
    await page.getByRole('button', { name: `Switch to ${theme} mode` }).first().click()
    await page.waitForFunction((t) => document.documentElement.classList.contains('dark') === (t === 'dark'), theme)
    await page.waitForTimeout(800)
  }
}

async function shot(page, locator, name) {
  await locator.scrollIntoViewIfNeeded()
  await page.waitForTimeout(300)
  await locator.screenshot({ path: path.join(OUT, 'screens', `${name}.png`) })
}

async function download(page, trigger, name) {
  const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 120000 }), trigger()])
  const target = path.join(OUT, 'exports', `${name}${path.extname(dl.suggestedFilename()) || ''}`)
  await dl.saveAs(target)
  return { file: target, suggested: dl.suggestedFilename() }
}

;(async () => {
  const browser = await chromium.launch()
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true })
  const page = await context.newPage()
  page.on('pageerror', (e) => console.log('pageerror', e.message))
  await page.goto(`${BASE}/login`)
  const consent = page.getByRole('button', { name: 'Essential only' })
  if (await consent.isVisible().catch(() => false)) await consent.click()
  await page.getByRole('button', { name: 'Continue with email' }).click()
  await page.locator('input[type="email"]').fill('<local-pro-user-email>')
  await page.locator('input[type="password"]').fill('<local-test-password>')
  await page.locator('form button[type="submit"]').first().click()
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 60000 })
  await page.goto(`${BASE}/analysis?ticker=REGN`)
  if (await consent.isVisible().catch(() => false)) await consent.click()
  await page.getByRole('group', { name: 'Recent period presets' }).getByRole('button', { name: /Last 10/ }).click()
  await page.getByRole('button', { name: 'Run analysis' }).click()
  await page.getByRole('button', { name: /Export PDF/ }).waitFor({ timeout: 240000 })
  await page.getByText('Sources', { exact: false }).first().waitFor({ timeout: 240000 })
  await page.waitForTimeout(4000)
  const results = {}
  for (const theme of ['light', 'dark']) {
    await setTheme(page, theme)
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: path.join(OUT, 'screens', `before-${theme}-full.png`), fullPage: true })
    await shot(page, page.locator('[data-analysis-kpi]').first().locator('xpath=ancestor::dl[1]'), `before-${theme}-kpis`)
    const notes = page.locator('[data-analysis-data-notes]')
    await shot(page, notes, `before-${theme}-datanotes-closed`)
    await notes.locator('summary').first().click()
    await shot(page, notes, `before-${theme}-datanotes-open`)
    await notes.locator('summary').first().click()
    if (process.argv.includes('--exports')) {
      results[theme] = {}
      results[theme].pdf = await download(page, () => page.getByRole('button', { name: /Export PDF/ }).click(), `REGN-analysis-${theme}`)
      results[theme].xlsx = await download(page, () => page.getByRole('button', { name: /Export Excel/ }).click(), `REGN-metrics-${theme}`)
      results[theme].png = await download(page, () => page.getByRole('button', { name: 'Download chart as PNG' }).first().click(), `REGN-chart-revenue-${theme}`)
    }
  }
  fs.writeFileSync(path.join(OUT, 'exports', 'downloads.json'), JSON.stringify(results, null, 2))
  console.log(JSON.stringify(results, null, 2))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
```

### `capture_before.js`

```js
// Clean full-page captures of the local REGN analysis (cached narrative: no model call) for the
// heuristic evaluation. Usage: node capture_before.js <screensDir> <prefix>
const { chromium } = require('playwright')
const path = require('path')
const OUT = process.argv[2]
const PREFIX = process.argv[3] || 'before'
const BASE = 'http://localhost:3000'

async function dismissConsent(page) {
  const consent = page.getByRole('button', { name: 'Essential only' })
  if (await consent.isVisible().catch(() => false)) { await consent.click(); await page.waitForTimeout(500) }
}

async function run(browser, width, label) {
  const context = await browser.newContext({ viewport: { width, height: 900 } })
  const page = await context.newPage()
  await page.goto(`${BASE}/login`)
  await dismissConsent(page)
  await page.getByRole('button', { name: 'Continue with email' }).click()
  await page.locator('input[type="email"]').fill('<local-pro-user-email>')
  await page.locator('input[type="password"]').fill('<local-test-password>')
  await page.locator('form button[type="submit"]').first().click()
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 60000 })
  await page.goto(`${BASE}/analysis?ticker=REGN`)
  await page.getByRole('group', { name: 'Recent period presets' }).getByRole('button', { name: /Last 10/ }).click()
  await page.getByRole('button', { name: 'Run analysis' }).click()
  await page.getByRole('button', { name: /Export PDF/ }).waitFor({ timeout: 240000 })
  await page.waitForTimeout(4000)
  await dismissConsent(page)
  for (const theme of ['light', 'dark']) {
    const dark = await page.evaluate(() => document.documentElement.classList.contains('dark'))
    if (dark !== (theme === 'dark')) {
      const toggle = page.getByRole('button', { name: `Switch to ${theme} mode` }).first()
      if (await toggle.isVisible().catch(() => false)) await toggle.click()
      else await page.evaluate((t) => { localStorage.setItem('theme', t); document.documentElement.classList.toggle('dark', t === 'dark') }, theme)
      await page.waitForTimeout(1000)
    }
    await dismissConsent(page)
    await page.addStyleTag({ content: 'nextjs-portal{display:none!important}' })
    await page.waitForTimeout(4500)
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: path.join(OUT, `${PREFIX}-${theme}-${label}.png`), fullPage: true })
    console.log('saved', `${PREFIX}-${theme}-${label}.png`)
    if (label === 'full') {
      await page.locator('[data-analysis-kpi]').first().locator('xpath=ancestor::dl[1]').screenshot({ path: path.join(OUT, `${PREFIX}-${theme}-kpis.png`) })
      const notes = page.locator('[data-analysis-data-notes]')
      await notes.screenshot({ path: path.join(OUT, `${PREFIX}-${theme}-datanotes-closed.png`) })
      await notes.locator('summary').first().click(); await page.waitForTimeout(400)
      await notes.screenshot({ path: path.join(OUT, `${PREFIX}-${theme}-datanotes-open.png`) })
      await notes.locator('summary').first().click()
      const head = page.locator('[data-analysis-metrics]')
      await head.screenshot({ path: path.join(OUT, `${PREFIX}-${theme}-table.png`) })
    }
  }
  await context.close()
}

;(async () => {
  const browser = await chromium.launch()
  await run(browser, 1440, 'full')
  await run(browser, 390, 'mobile')
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
```

## Competitor captures

The captures these scripts wrote, and their `captures.json` log, are not committed: the repository
is public (founder, 2026-10-25; D-061). The report's §4.3 keeps the written teardown.

Stock Analysis, Simply Wall St, GuruFocus, Seeking Alpha, TipRanks, Stockrow and Fiscal.ai turned
the headless browser away at a bot check. Morningstar served an image captcha, and solving
captchas is out of bounds. Alpha Spread served a Cloudflare challenge on the second visit, so
requests to it stopped. Its first-visit capture is kept as a supplement.

One Finviz run followed an ad redirect to a third-party page. That capture was deleted, and the
reshoot blocked every host outside the product's own domains.

Roic.ai ignores `prefers-color-scheme`, so its dark capture uses its own theme control. Yahoo Finance
has no dark theme for a signed-out reader.

### `comp_capture2.js`

```js
// Competitor teardown captures (REGN, annual multi-period views), viewport tiles so lazy charts render.
// Third-party hosts (ads, trackers) are blocked: one Finviz run was redirected to an ad page.
// Usage: node comp_capture2.js <outDir>
const { chromium } = require('playwright')
const path = require('path')
const fs = require('fs')
const OUT = process.argv[2]
fs.mkdirSync(OUT, { recursive: true })
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
const FIRST_PARTY = /(^|\.)(roic\.ai|finviz\.com|finviz\.net|yahoo\.com|yimg\.com|yahooapis\.com)$/
const log = []

async function tile(page, name, y) {
  await page.evaluate((top) => window.scrollTo(0, top), y)
  await page.waitForTimeout(2500)
  const file = `${name}.jpg`
  await page.screenshot({ path: path.join(OUT, file), type: 'jpeg', quality: 80 })
  const theme = await page.evaluate(() => {
    const bg = getComputedStyle(document.body).backgroundColor
    return { bodyBackground: bg, htmlClass: document.documentElement.className.slice(0, 80) }
  })
  log.push({ file, url: page.url(), scrollY: y, ...theme })
  console.log('saved', file, theme.bodyBackground, page.url().slice(0, 80))
}

async function newPage(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, userAgent: UA })
  await ctx.route('**/*', (route) => {
    const host = new URL(route.request().url()).hostname
    return FIRST_PARTY.test(host) ? route.continue() : route.abort()
  })
  const page = await ctx.newPage()
  return { ctx, page }
}

;(async () => {
  const browser = await chromium.launch()

  // 1. Roic.ai — Financials, 15 fiscal years. Light is its default; dark through its own theme control.
  for (const theme of ['light', 'dark']) {
    const { ctx, page } = await newPage(browser)
    await page.goto('https://www.roic.ai/quote/REGN/financials', { waitUntil: 'domcontentloaded', timeout: 60000 })
    await page.waitForTimeout(6000)
    if (theme === 'dark') {
      await page.getByRole('button', { name: /toggle theme/i }).first().click().catch((e) => console.log('roic toggle', e.message.slice(0, 80)))
      await page.waitForTimeout(800)
      const dark = page.getByRole('menuitem', { name: /dark/i }).first()
      if (await dark.isVisible().catch(() => false)) await dark.click()
      await page.waitForTimeout(1500)
    }
    await tile(page, `roic-financials-chart-${theme}`, 0)
    const table = await page.getByText('Income Statement (USD)').first().boundingBox().catch(() => null)
    await tile(page, `roic-financials-statement-${theme}`, table ? Math.max(0, table.y - 80) : 760)
    await ctx.close()
  }

  // 2. Yahoo Finance (Finance Plus gates 10Y/20Y/ALL) — Financials › Income Statement, annual.
  {
    const { ctx, page } = await newPage(browser)
    await page.goto('https://finance.yahoo.com/quote/REGN/financials/', { waitUntil: 'domcontentloaded', timeout: 60000 })
    await page.waitForTimeout(7000)
    const consent = page.getByRole('button', { name: /accept all|reject all/i }).first()
    if (await consent.isVisible().catch(() => false)) await consent.click()
    const header = await page.getByText('Income Statement', { exact: true }).first().boundingBox().catch(() => null)
    await tile(page, 'yahoo-financials-chart-light', header ? Math.max(0, header.y - 220) : 420)
    const table = await page.getByText('Total Revenue').first().boundingBox().catch(() => null)
    await tile(page, 'yahoo-financials-statement-light', table ? Math.max(0, table.y - 160) : 1200)
    await ctx.close()
  }

  // 3. Finviz (Elite) — Financials › Revenue, annual. Dark is its default here; light through its switch.
  for (const theme of ['dark', 'light']) {
    const { ctx, page } = await newPage(browser)
    await page.goto('https://finviz.com/quote.ashx?t=REGN&p=d&ty=re', { waitUntil: 'domcontentloaded', timeout: 60000 })
    await page.waitForTimeout(6000)
    if (theme === 'light') {
      const toggle = page.locator('header, nav, body').locator('[data-testid*="theme" i], [aria-label*="theme" i], [title*="theme" i], [aria-label*="dark" i], [title*="dark" i]').first()
      if (await toggle.isVisible().catch(() => false)) await toggle.click()
      else await page.mouse.click(1197, 176)
      await page.waitForTimeout(3000)
    }
    const annual = page.getByRole('button', { name: 'Annual', exact: true }).first()
    if (await annual.isVisible().catch(() => false)) await annual.click()
    await page.waitForTimeout(3000)
    await tile(page, `finviz-financials-revenue-${theme}`, 120)
    await tile(page, `finviz-financials-revenue-table-${theme}`, 760)
    await ctx.close()
  }
  fs.writeFileSync(path.join(OUT, 'captures.json'), JSON.stringify(log, null, 1))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
```

### `comp_capture3.js`

```js
// Competitor teardown captures (REGN, annual multi-period views), viewport tiles so lazy charts render.
// Third-party hosts (ads, trackers) are blocked: one Finviz run was redirected to an ad page.
// Usage: node comp_capture2.js <outDir>
const { chromium } = require('playwright')
const path = require('path')
const fs = require('fs')
const OUT = process.argv[2]
fs.mkdirSync(OUT, { recursive: true })
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
const FIRST_PARTY = /(^|\.)(roic\.ai|finviz\.com|finviz\.net|yahoo\.com|yimg\.com|yahooapis\.com)$/
const log = []

async function tile(page, name, y) {
  await page.evaluate((top) => window.scrollTo(0, top), y)
  await page.waitForTimeout(2500)
  const file = `${name}.jpg`
  await page.screenshot({ path: path.join(OUT, file), type: 'jpeg', quality: 80 })
  const theme = await page.evaluate(() => {
    const bg = getComputedStyle(document.body).backgroundColor
    return { bodyBackground: bg, htmlClass: document.documentElement.className.slice(0, 80) }
  })
  log.push({ file, url: page.url(), scrollY: y, ...theme })
  console.log('saved', file, theme.bodyBackground, page.url().slice(0, 80))
}

async function newPage(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, userAgent: UA })
  await ctx.route('**/*', (route) => {
    const host = new URL(route.request().url()).hostname
    return FIRST_PARTY.test(host) ? route.continue() : route.abort()
  })
  const page = await ctx.newPage()
  return { ctx, page }
}


;(async () => {
  const browser = await chromium.launch()
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, userAgent: UA })
    const page = await ctx.newPage()
    await page.goto('https://finance.yahoo.com/quote/REGN/financials/', { waitUntil: 'domcontentloaded', timeout: 60000 })
    await page.waitForTimeout(8000)
    const consent = page.getByRole('button', { name: /accept all|reject all/i }).first()
    if (await consent.isVisible().catch(() => false)) await consent.click()
    await tile(page, 'yahoo-financials-chart-light', 420)
    const table = await page.getByText('Total Revenue').first().boundingBox().catch(() => null)
    await tile(page, 'yahoo-financials-statement-light', table ? Math.max(0, table.y + 420 - 200) : 1100)
    await ctx.close()
  }
  for (const theme of ['dark', 'light']) {
    const { ctx, page } = await newPage(browser)
    await page.goto('https://finviz.com/quote.ashx?t=REGN&p=d', { waitUntil: 'domcontentloaded', timeout: 60000 })
    await page.waitForTimeout(6000)
    const isDark = await page.evaluate(() => document.documentElement.classList.contains('dark'))
    if ((theme === 'light') === isDark) { await page.mouse.click(1197, 176); await page.waitForTimeout(3000) }
    const statements = await page.getByText('Income Statement', { exact: false }).last().boundingBox().catch(() => null)
    await tile(page, `finviz-statements-${theme}`, statements ? Math.max(0, statements.y - 120) : 2400)
    await ctx.close()
  }
  const prior = fs.existsSync(path.join(OUT, 'captures.json')) ? JSON.parse(fs.readFileSync(path.join(OUT, 'captures.json'))) : []
  fs.writeFileSync(path.join(OUT, 'captures.json'), JSON.stringify([...prior.filter(r => !log.some(l => l.file === r.file)), ...log], null, 1))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
```

## Export inspection script

```python
"""Inspect the REGN Multi-Period Analysis exports as files and print a pass/fail table.

Usage: python -I inspect_exports.py <exports dir>
Checks per artefact and theme: company name (and its display form), period range, notation legend,
sources, disclaimer, branding, theme correctness, legibility at print size, plus the notation
visible where the figures are. PDF via pdfplumber, workbook via openpyxl, PNG via Pillow pixels
(no OCR is installed: the PNG's words are read by eye and marked so).
"""
import collections
import json
import re
import sys
import zipfile
from pathlib import Path

import openpyxl
import pdfplumber
from PIL import Image

D = Path(sys.argv[1])
rows = []


def check(artefact, theme, name, ok, evidence):
    rows.append({"artefact": artefact, "theme": theme, "check": name,
                 "result": {True: "PASS", False: "FAIL", None: "PARTIAL"}[ok], "evidence": evidence})


def pdf_checks(theme):
    path = D / f"REGN-analysis-{theme}.pdf"
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        chars = [c for page in pdf.pages for c in page.chars]
        pages = len(pdf.pages)
        meta = dict(pdf.metadata)
        tagged = "StructTreeRoot" in pdf.doc.catalog or "MarkInfo" in pdf.doc.catalog
        legend_page = next(i for i, page in enumerate(pdf.pages, 1) if "Letters refer to Data notes" in (page.extract_text() or ""))
        table_page = next(i for i, page in enumerate(pdf.pages, 1) if "Metrics by period" in (page.extract_text() or "") and "METRIC" in (page.extract_text() or ""))
        methods_from = next(i for i, page in enumerate(pdf.pages, 1) if "Sources & methods" in (page.extract_text() or "") and "Raw values retain" in (page.extract_text() or ""))
        about = next(i for i, page in enumerate(pdf.pages, 1) if "About this document" in (page.extract_text() or ""))
    a = "PDF"
    check(a, theme, "company name", None if "REGENERON PHARMACEUTICALS, INC." in text and "Regeneron Pharmaceuticals" not in text else True,
          "Present on every page header, but as EDGAR capitals 'REGENERON PHARMACEUTICALS, INC.'; the web page and chart PNG print 'Regeneron Pharmaceuticals, Inc.'")
    check(a, theme, "period range", "FY2016–FY2025" in text, f"'FY2016–FY2025' {text.count('FY2016–FY2025')}x; title block 'REGN · Annual · FY2016–FY2025'")
    legend = "Letters refer to Data notes" in text and "† Calculated figure" in text and re.search(r"\ba\. This saved calculation", text)
    check(a, theme, "notation legend", None if legend and legend_page != table_page else bool(legend),
          f"Data notes a/b on p1; the letters/† key is on p{legend_page}, not on the table's page p{table_page}; summary says '16 comparisons need review' where the web says 'carry note a'")
    check(a, theme, "sources", "Narrative sources" in text and "Source filing" in text,
          f"Narrative sources list + Sources & methods p{methods_from}–p{about} ({about - methods_from + 1} of {pages} pages); legacy calculated sources [8]–[11],[13] carry no filing link and print raw keys ('operating_margin')")
    check(a, theme, "disclaimer", "not investment advice" in text and "not affiliated with or endorsed by the SEC" in text, f"About this document, p{about}")
    check(a, theme, "branding", "EarningsNerd" in text and "earningsnerd.io" in text, "Logo lockup in the p1 header; 'EarningsNerd · earningsnerd.io' footer on every page")
    sizes = collections.Counter(round(c["size"], 1) for c in chars)
    fallback = collections.Counter(c["text"] for c in chars if "DejaVu" in c["fontname"])
    check(a, theme, "legibility at print size", None if fallback else min(sizes) >= 7,
          f"A4/A4-landscape; smallest text {min(sizes)}pt (note letters), body 8.5pt; {pages} pages; glyphs set in a fallback font: {dict(fallback)}; timestamps print as raw ISO with microseconds")
    check(a, theme, "document metadata / tagging", bool(meta.get("Title")) and tagged,
          f"metadata {meta}; tagged={tagged}")
    return text


def pdf_theme_parity():
    texts = []
    for theme in ("light", "dark"):
        with pdfplumber.open(D / f"REGN-analysis-{theme}.pdf") as pdf:
            texts.append(re.sub(r"\d{4}-\d{2}-\d{2}T[\d:.]+Z", "<ts>", "\n".join(p.extract_text() or "" for p in pdf.pages)))
    return texts[0] == texts[1]


def xlsx_checks(theme):
    path = D / f"REGN-metrics-{theme}.xlsx"
    wb = openpyxl.load_workbook(path)
    ov, m = wb["Overview"], wb["Metrics"]
    cells = {c.coordinate: c.value for row in ov.iter_rows() for c in row if c.value is not None}
    text = "\n".join(str(v) for v in cells.values())
    a = "Excel"
    check(a, theme, "company name", None, "Overview A7 'REGENERON PHARMACEUTICALS, INC. · Multi-Period Analysis' (EDGAR capitals)")
    check(a, theme, "period range", "FY2016–FY2025" in text, "Overview 'Periods: FY2016–FY2025 · 10 periods'; Metrics header FY2016..FY2025")
    comments = [(c.coordinate, c.comment.text) for row in m.iter_rows() for c in row if c.comment]
    review = [ref for ref, t in comments if t.startswith("Data note a")]
    calc_only = [ref for ref, t in comments if t.startswith("Calculated figure")]
    visible_marks = sum(1 for row in m.iter_rows() for c in row if isinstance(c.value, str) and re.search(r"†|\b[ab]\b$", c.value))
    styled = sum(1 for ref in review if m[ref].fill.fill_type or (m[ref].font.color and m[ref].font.color.type == "rgb"))
    check(a, theme, "notation legend", "Data note a" in text and "50 calculated †" in text,
          "Overview A26–A29 states the counts and notes a/b; † appears only in that count line")
    check(a, theme, "notation visible in the grid", False,
          f"{len(review)} review cells and {len(calc_only)} calculated cells both carry only a comment triangle; {visible_marks} cells show a mark, {styled} review cells are styled: a reviewed figure looks like any calculated one")
    sm = wb["Sources & methods"]
    check(a, theme, "sources", sm.max_row > 1 and "Source URL" in [c.value for c in sm[1]], f"Sources & methods sheet, {sm.max_row - 1} rows, Source URL and Accession columns")
    check(a, theme, "disclaimer", "not investment advice" in text, "Overview A31")
    check(a, theme, "branding", len(ov._images) == 1 and "EarningsNerd" in text, "Logo image at Overview A1; 'EarningsNerd · earningsnerd.io' source line")
    sizes = collections.Counter(c.font.sz for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value is not None and c.font.sz)
    check(a, theme, "legibility at print size", None,
          f"font sizes {dict(sizes)}; Metrics freezes B2; no print area, fit-to-width or landscape setup: {m.page_setup.orientation or 'default'} orientation, fitToWidth={m.page_setup.fitToWidth}; raw concept keys in column B")
    check(a, theme, "document metadata", bool(wb.properties.title), f"title={wb.properties.title!r}, creator={wb.properties.creator!r}")


def xlsx_theme_parity():
    a, b = (zipfile.ZipFile(D / f"REGN-metrics-{t}.xlsx") for t in ("light", "dark"))
    differ = [n for n in a.namelist() if a.read(n) != b.read(n)]
    return differ


def luminance(rgb):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def png_checks(theme, chart):
    path = D / f"REGN-chart-{chart}-{theme}.png"
    im = Image.open(path).convert("RGB")
    bg = im.getpixel((5, 5))
    expected = {"light": (251, 250, 246), "dark": (31, 41, 55)}[theme]
    # Footer band (source, notes, disclaimer) sits below the x-axis title: measure its darkest/lightest ink.
    band = im.crop((20, int(im.height * 0.62), im.width - 20, int(im.height * 0.9)))
    inks = [p for p in band.getdata() if abs(luminance(p) - luminance(bg)) > 0.05]
    ink = (min if theme == "light" else max)(inks, key=luminance)
    l1, l2 = sorted((luminance(ink), luminance(bg)), reverse=True)
    contrast = (l1 + 0.05) / (l2 + 0.05)
    a = f"PNG ({chart})"
    check(a, theme, "company name", True, "Title 'Regeneron Pharmaceuticals, Inc.' (read by eye)")
    check(a, theme, "period range", False, "No fiscal-year range in the image; only '16–'25 ticks; the range is in the file name alone")
    if chart == "margins":
        check(a, theme, "notation legend", None, "'Note a: …' with its figures, 'Includes figures calculated by EarningsNerd'; the hollow-ring marker for a noted point is not explained; letters are grey, not the review colour (read by eye)")
    else:
        check(a, theme, "notation legend", True, "No noted figure on this chart, so no legend is needed (read by eye)")
    check(a, theme, "sources", True, "'Source: SEC filings via EarningsNerd · data as of Oct 24, 2026' (read by eye)")
    check(a, theme, "disclaimer", True, "'Research only. Not investment advice…' + earningsnerd.io/terms (read by eye)")
    check(a, theme, "branding", True, "EN mark + wordmark bottom right (read by eye)")
    check(a, theme, "theme correctness", bg == expected,
          f"background {bg} = panel token {expected}; footer ink contrast {contrast:.1f}:1. The image follows the page theme while the PDF and workbook stay light")
    width_in = 6.5
    check(a, theme, "legibility at print size", None,
          f"{im.width}x{im.height}px, no DPI tag; at {width_in}in wide it prints at {im.width / width_in:.0f}dpi, where the ~20px axis text is ~{20 / (im.width / width_in) * 72:.1f}pt")


pdf_checks("light"); pdf_checks("dark")
parity = pdf_theme_parity()
for theme in ("light", "dark"):
    check("PDF", theme, "theme correctness", parity, "Text identical across themes once timestamps are masked: the PDF is always the light print layout")
xlsx_checks("light"); xlsx_checks("dark")
differ = xlsx_theme_parity()
for theme in ("light", "dark"):
    check("Excel", theme, "theme correctness", differ == ["docProps/core.xml", "xl/worksheets/sheet1.xml"] or not differ,
          f"Parts that differ between the two downloads: {differ} (export timestamps only)")
for chart in ("revenue", "margins"):
    for theme in ("light", "dark"):
        png_checks(theme, chart)

Path(D / "inspection.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
order = ["company name", "period range", "notation legend", "notation visible in the grid", "sources", "disclaimer",
         "branding", "theme correctness", "legibility at print size", "document metadata", "document metadata / tagging"]
print("| Artefact | Theme | Check | Result | Evidence |\n|---|---|---|---|---|")
for row in sorted(rows, key=lambda r: (r["artefact"], order.index(r["check"]), r["theme"])):
    print(f"| {row['artefact']} | {row['theme']} | {row['check']} | {row['result']} | {row['evidence']} |")
print({k: v for k, v in collections.Counter(r["result"] for r in rows).items()})
```

## Detection SQL parity script

It drops and recreates every table, so it runs against a scratch database of its own (`parity`), never
the reproduction's: `DATABASE_URL=postgresql://postgres@localhost:5433/parity` for the app, and the same
database for `psql`. The review of 2026-10-25 added the cases for a withheld cell (no YoY on either side,
no dagger) and an empty `raw_tag`; the SQL before that fix fails them (`AssertionError: ('6', 4)` on the
YoY count).

```python
"""Parity: ops/detection/mpa_notation_frequency.sql classifies cells as provenance_for_fact does.

Builds the schema on the local Postgres, plants one company per classification branch, runs the
SQL's set 1 and compares its 'all' and 'reason' rows with the Python projection of the same rows.
"""
import subprocess
import sys
from datetime import date

sys.path.insert(0, "/home/user/EarningsNerd/backend")
from sqlalchemy import text  # noqa: E402

from app.database import Base, engine, SessionLocal  # noqa: E402
import app.models  # noqa: E402,F401
from app.models import Company, FinancialFact  # noqa: E402
from app.services.fact_provenance import provenance_for_fact  # noqa: E402

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
db = SessionLocal()
co = Company(cik="0000000001", ticker="PAR", name="Parity Co")
db.add(co)
db.flush()
v1 = lambda method, validation, reasons: {"version": 1, "method": method, "validation": validation, "reasons": reasons}  # noqa: E731
cases = [
    # concept, fy, source, raw_tag, reconciled, provenance
    ("revenue", 2020, "companyfacts", "us-gaap:Revenues", True, v1("reported", "passed", [])),
    ("revenue", 2021, "companyfacts", "us-gaap:Revenues", False, v1("reported", "needs_review", ["source_check_needed"])),
    ("revenue", 2022, "edgar_xbrl", "us-gaap:Revenues", True, None),  # legacy reported, reconciled
    ("revenue", 2023, "edgar_xbrl", "us-gaap:Revenues", False, None),  # legacy reported, not reconciled
    ("operating_margin", 2022, "edgar_xbrl", None, True, None),  # legacy calculation (REGN shape)
    ("operating_margin", 2023, "derived", None, True, v1("calculated", "passed", [])),
    ("free_cash_flow", 2023, "derived", None, False, None),  # legacy derived
    ("current_ratio", 2023, "edgar_xbrl", "current_ratio", True, None),  # raw_tag == concept
    ("eps_diluted", 2023, "derived", None, True, v1("calculated", "passed", [])),  # withheld EPS
    ("net_margin", 2023, "derived", None, False,
     v1("calculated", "needs_review", ["mixed_vintage", "unit_mismatch"])),
    ("net_income", 2023, "companyfacts", "us-gaap:NetIncomeLoss", True, {"version": 0}),  # unknown version
    ("eps_diluted", 2022, "companyfacts", "us-gaap:EarningsPerShareDiluted", True, v1("reported", "passed", [])),
    ("gross_margin", 2023, "edgar_xbrl", "", True, None),  # empty raw_tag: a legacy calculation, as in Python
    ("free_cash_flow", 2024, "derived", None, True, v1("calculated", "unavailable", ["legacy_calculation_not_supported"])),
]
rows = []
for concept, fy, source, raw_tag, reconciled, provenance in cases:
    row = FinancialFact(company_id=co.id, concept=concept, raw_tag=raw_tag, unit="USD",
                        period_end=date(fy, 12, 31), fiscal_year=fy, fiscal_period="FY", value=1,
                        accession=f"0000000001-{fy % 100:02d}-000001", source=source,
                        reconciled=reconciled, provenance=provenance, is_latest=True)
    db.add(row)
    rows.append(row)
db.commit()

from app.services.fact_provenance import published_value  # noqa: E402
expected_review = expected_withheld = expected_calc = 0
published = {(r.concept, r.fiscal_year): published_value(r) is not None for r in rows}
expected_yoy = sum(1 for (c, fy), ok in published.items() if ok and published.get((c, fy - 1)))
expected_reasons: dict[str, int] = {}
for row in rows:
    pv = provenance_for_fact(row)
    expected_review += pv["validation"] == "needs_review"
    expected_withheld += pv["validation"] == "unavailable"
    expected_calc += pv["method"] == "calculated" and published_value(row) is not None
    key = "+".join(sorted(pv["reasons"])) or "none"
    expected_reasons[key] = expected_reasons.get(key, 0) + 1

out = subprocess.run(
    ["psql", "postgresql://postgres@localhost:5433/parity", "-X", "-A", "-F", "|", "-v", "ON_ERROR_STOP=1",
     "-f", "/home/user/EarningsNerd/ops/detection/mpa_notation_frequency.sql"],
    capture_output=True, text=True, check=True).stdout
got_reasons = {}
for line in out.splitlines():
    parts = line.split("|")
    if parts[0] == "all":
        _, _, companies, cells, _, review, withheld, calc_pct, calc_review, _, yoy, _ = parts
        print("SQL all:", "cells", cells, "review", review, "withheld", withheld, "calc_pct", calc_pct, "yoy", yoy)
        assert int(yoy) == expected_yoy, (yoy, expected_yoy)
        assert abs(float(calc_pct) - round(100.0 * expected_calc / len(rows), 1)) < 0.05, (calc_pct, expected_calc)
        assert int(cells) == len(rows), (cells, len(rows))
        assert int(review) == expected_review, (review, expected_review)
        assert int(withheld) == expected_withheld, (withheld, expected_withheld)
    if parts[0] == "reason":
        got_reasons[parts[1]] = int(parts[3])
print("python reasons:", expected_reasons)
print("sql reasons:   ", got_reasons)
assert got_reasons == expected_reasons
print("PARITY OK: review", expected_review, "withheld", expected_withheld, "calculated", expected_calc)
print("\n".join(l for l in out.splitlines() if l.startswith(("all|","reason|","owner|"))))
```


## Notation variant test

The test is described in [verification/notation-variant-test.md](verification/notation-variant-test.md).
The four designs ran on the local stack above, with REGN's FY2018–FY2019 revenue rows planted as
`source_conflict` (the SQL is in that file).
- The variants came from one build, switched by `NEXT_PUBLIC_NOTATION_VARIANT` (`current`, `quiet`
  or `none`; see [`prototype/notation-quiet.diff`](prototype/notation-quiet.diff)).
- The ring design came from [`prototype/notation-prototype.diff`](prototype/notation-prototype.diff).
- Captures used `capture_before.js` (above) with the design's prefix: full page, 1440px, light.
- Each full page was cut with Pillow into 1500px-tall tiles, `page-<label>-1..3.png`.

The workflow script ran eight blind verdicts and the rules check in parallel. The re-test ran the
same `testPrompt` and `VERDICT` for the labels `R2` and `S2` only.

```js
export const meta = {
  name: 'mpa-notation-variant-test',
  description: 'Blind-test four notation designs for trust calibration and visual appeal, and check repo rules that dropping marks would collide with',
  phases: [
    { title: 'Blind test', detail: '4 unlabelled designs x 2 personas, structured verdicts' },
    { title: 'Rules check', detail: 'documented decisions, gates and promises that a quieter notation must update' },
  ],
}

const DIR = '<scratch>/blind'
const DESIGNS = ['P', 'Q', 'R', 'S']
const PERSONAS = [
  { key: 'retail', text: 'a self-directed retail investor who pays for this research tool and checks a company before buying its shares' },
  { key: 'pro', text: 'a professional equity analyst at a small fund who uses paid data terminals daily and is sceptical of any figure that is not sourced' },
]

const VERDICT = {
  type: 'object',
  properties: {
    trust_overall: { type: 'integer', minimum: 1, maximum: 5, description: 'How far you would rely on the page\'s numbers overall (1 = not at all, 5 = fully)' },
    trust_fcf_fy2025: { type: 'integer', minimum: 1, maximum: 5, description: 'Trust in the FY2025 Free cash flow figure of $4.1B' },
    trust_fcf_reason: { type: 'string' },
    trust_revenue_fy2018: { type: 'integer', minimum: 1, maximum: 5, description: 'Trust in the FY2018 Revenue figure ($5.1B, shown with -12.4% growth)' },
    trust_revenue_reason: { type: 'string' },
    noticed_issue_with_fy2018_revenue: { type: 'boolean', description: 'Did anything on the page itself (not your own knowledge) tell you the FY2018 revenue might be problematic?' },
    page_evidence_for_revenue: { type: 'string', description: 'Quote what on the page told you, or "nothing on the page"' },
    used_outside_knowledge: { type: 'boolean', description: 'Did your FY2018 revenue judgement rely on what you already know about the company rather than the page?' },
    figures_you_would_check: { type: 'array', items: { type: 'string' } },
    visual_cleanliness: { type: 'integer', minimum: 1, maximum: 5, description: '1 = cluttered or alarming, 5 = clean and calm' },
    alarming_or_distracting: { type: 'array', items: { type: 'string' }, description: 'Elements that felt alarming, dramatic or distracting, quoted or described' },
    site_feels_trustworthy: { type: 'integer', minimum: 1, maximum: 5, description: 'Does the product as a whole feel trustworthy and professional?' },
    where_to_find_source: { type: 'string', description: 'Where on this page would you go to see where a figure came from?' },
    what_marks_mean: { type: 'string', description: 'Any symbols or letters next to figures, and what you think they mean; "none seen" if none' },
    one_change: { type: 'string', description: 'The one change you would make to how this page signals data quality' },
  },
  required: ['trust_overall', 'trust_fcf_fy2025', 'trust_fcf_reason', 'trust_revenue_fy2018', 'trust_revenue_reason',
    'noticed_issue_with_fy2018_revenue', 'page_evidence_for_revenue', 'used_outside_knowledge', 'figures_you_would_check',
    'visual_cleanliness', 'alarming_or_distracting', 'site_feels_trustworthy', 'where_to_find_source', 'what_marks_mean', 'one_change'],
}

const RULES = {
  type: 'object',
  properties: {
    collisions: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          quote: { type: 'string', description: 'The exact words that the change would contradict' },
          kind: { type: 'string', enum: ['founder-decision', 'adr', 'design-rule', 'lesson', 'test-gate', 'public-promise', 'legal', 'other'] },
          severity: { type: 'string', enum: ['blocker-needs-founder', 'must-update-in-same-pr', 'note'] },
          what_to_do: { type: 'string' },
        },
        required: ['file', 'quote', 'kind', 'severity', 'what_to_do'],
      },
    },
    public_promises_that_depend_on_visible_marks: { type: 'array', items: { type: 'string' } },
    verdict: { type: 'string', description: 'Can the quiet scheme ship as a design change, or does any item need a founder decision first? One paragraph.' },
  },
  required: ['collisions', 'public_promises_that_depend_on_visible_marks', 'verdict'],
}

function testPrompt(design, persona) {
  return `You are ${persona.text}. You have opened the "Multi-Period Analysis" page of a paid SEC-filing research product for Regeneron (REGN), fiscal years 2016-2025. Look ONLY at these three screenshots, which are the page from top to bottom, using the Read tool on each, and open nothing else (no other files, no code, no web search):
${DIR}/page-${design}-1.png
${DIR}/page-${design}-2.png
${DIR}/page-${design}-3.png

Judge the page as it appears, as that user would. Base every trust judgement on what the page shows you; if you also know something about the company from memory, say so in used_outside_knowledge and keep it out of the page-based answers. Be candid about anything that feels alarming, dramatic, cluttered or untrustworthy, and about anything that feels missing. Return the structured verdict.`
}

phase('Blind test')
const cells = DESIGNS.flatMap((design) => PERSONAS.map((persona) => ({ design, persona })))
const testsPromise = parallel(cells.map((cell) => () =>
  agent(testPrompt(cell.design, cell.persona), { label: `design ${cell.design} · ${cell.persona.key}`, phase: 'Blind test', schema: VERDICT })
    .then((verdict) => verdict && ({ design: cell.design, persona: cell.persona.key, ...verdict }))))

const rulesPromise = agent(`You are reviewing a proposed change to the EarningsNerd repository (working tree at /home/user/EarningsNerd; read-only task: do not edit, commit or run anything that writes). The Multi-Period Analysis page (frontend/features/analysis/) currently marks every calculated figure with a dagger (†) and marks figures by lettered "data notes" (DataNoteMark, DataNotes, DataNotesLink), with review concerns in warning ink, and shows a "Data notes" strip right under the headline KPI cards.

The proposed "quiet" scheme:
1. No dagger on figures anywhere on the page; one sentence above the metrics table says which metrics are calculated, and each figure's evidence dialog (SourceValue) still states method, inputs and checks.
2. No on-figure mark for a figure whose only note is a missing calculation record (reason legacy_calculation), for unavailable figures (they already show "—"), or for a missing validation record. Those stay in the evidence dialog and the data notes.
3. Only a note that questions the number itself (for example the company's filings disagree, a calculation mismatch, an unresolved source check) keeps a small neutral superscript letter, no warning colour.
4. The Data notes strip moves below the metrics table as one line of fine print, neutral ink.
5. Exports (PDF, workbook, chart PNG) follow the same policy.

Find every place in the repository this would contradict or require changing: founder decisions and design decision records (look for D-0xx entries and decision logs under tasks/ and docs/), ADRs in docs/adr/, DESIGN.md (especially "The Calculation Provenance Rule"), frontend/DESIGN_SYSTEM.md (the "Data note mark", "Data notes strip" recipes and §10), lessons/ (especially the brand and evidence-label lessons), test gates and specs that pin the dagger, the letters, warning ink or the strip's position (frontend/tests/unit, frontend/tests/e2e, backend/tests), and any public promise in marketing, landing, pricing, legal or brand copy (docs/brand/, frontend/app, frontend/features/marketing) that depends on visible per-figure marks. For each, give the file, line, the exact words, the kind, and whether it is a blocker that needs the founder's decision, something that must be updated in the same PR, or a note. Then give a one-paragraph verdict.`, { label: 'rules check', phase: 'Rules check', schema: RULES })

const [tests, rules] = await Promise.all([testsPromise, rulesPromise])
const results = tests.filter(Boolean)
log(`${results.length} of ${cells.length} blind verdicts returned; rules check ${rules ? 'returned' : 'missing'}`)
return { results, rules }
```

## File-overlap script

```python
"""File-overlap matrix: this plan's work packages, the sibling plans' scopes, the live branches.

Live branches are measured (git diff --name-only against their merge base with origin/main).
Work packages list the files the change edits. Sibling scopes list the files their areas own,
because no sibling branch exists yet (checked 2026-10-24 20:05 and 21:10 UTC).
"""
import itertools
import subprocess

A = "frontend/features/analysis/"
PLAN = {
    "WP0 lineage backfill": [
        "backend/app/services/filing_lineage_repair.py", "backend/scripts/repair_filing_lineage.py",
        ".github/workflows/ops.yml", "backend/tests/unit/test_filing_lineage_repair.py",
        "backend/tests/unit/test_ops_workflow_wiring.py", "backend/tests/unit/test_migration_lock_safety.py",
        "docs/filing-lineage-repair.md", "docs/DEPLOYMENT.md", "ops/detection/mpa_notation_frequency.sql", "tasks/todo.md",
    ],
    "WP1 quiet notation": [
        A + "components/DataNoteMark.tsx", A + "components/DataNotesLink.tsx", A + "components/DataNotesContext.tsx",
        A + "components/MetricsTable.tsx", A + "components/KpiStrip.tsx", A + "components/TrendCharts.tsx",
        A + "components/NarrativePane.tsx", A + "components/DataNotes.tsx", A + "components/AnalysisPageClient.tsx",
        A + "components/AnalysisTeaser.tsx", A + "lib/dataNotes.ts", A + "lib/tableFormat.ts",
        "frontend/features/marketing/components/AnalysisDemo.tsx",
        "DESIGN.md", ".impeccable/design.json", "frontend/DESIGN_SYSTEM.md",
        "lessons/arch-reconciliation-follows-values-and-growth.md", "docs/design/analysis-data-notes-redesign-2026-10.md",
        "docs/brand/decisions-log.md",
        "frontend/tests/unit/metrics-table.spec.tsx", "frontend/tests/unit/kpi-strip.spec.tsx",
        "frontend/tests/unit/analysis-source-quality.spec.tsx", "frontend/tests/unit/narrative-pane.spec.tsx",
        "frontend/tests/unit/trend-charts-annotation.spec.tsx", "frontend/tests/unit/data-notes.spec.ts",
        "frontend/tests/unit/analysis-table-format.spec.ts", "frontend/tests/e2e/analysis-layout.spec.ts",
        "frontend/tests/e2e/fixtures/analysisLayoutApi.ts", "frontend/tests/e2e/text-floors.spec.ts",
    ],
    "WP2 data-notes words": [
        "backend/app/services/trend_analysis/data_notes.py", "backend/tests/unit/test_analysis_data_notes.py",
        "backend/tests/fixtures/analysis_data_notes.json", A + "components/DataNotes.tsx", A + "lib/dataNotes.ts",
        A + "lib/provenance.ts", "backend/app/services/analysis_export_metadata.py", "frontend/tests/unit/data-notes.spec.ts",
        "frontend/tests/unit/analysis-source-quality.spec.tsx", "frontend/tests/unit/analysisPeriodWindows.spec.tsx",
    ],
    "WP3 exports": [
        "backend/app/services/export_service.py", "backend/app/services/excel_export_service.py",
        "backend/app/services/analysis_export_metadata.py", "backend/app/services/pdf_branding.py", A + "lib/chartExport.ts",
        "backend/tests/unit/test_export_service.py", "backend/tests/unit/test_excel_export.py",
        "backend/tests/unit/test_export_voice.py", "frontend/tests/unit/chart-export.spec.ts",
    ],
    "WP4 surfaces + results header": [
        A + "components/AnalysisPageClient.tsx", A + "components/KpiStrip.tsx",
        "frontend/features/feedback/components/FeedbackWidget.tsx", "frontend/tests/unit/bottomChromeLadder.spec.ts",
        "frontend/tests/e2e/analysis-layout.spec.ts", "DESIGN.md", "frontend/DESIGN_SYSTEM.md", ".impeccable/design.json",
    ],
    "WP5 restatement note": [
        "backend/app/services/trend_analysis/dataset.py", "backend/app/services/trend_analysis/dataset_quality.py",
        "backend/app/services/trend_analysis/data_notes.py", A + "lib/dataNotes.ts", A + "components/DataNoteMark.tsx",
        "backend/tests/unit/test_trend_analysis_service.py", "backend/tests/unit/test_analysis_data_notes.py",
    ],
}
SIBLINGS = {
    "charts steps 5-7 (scope)": [
        A + "components/TrendCharts.tsx", A + "components/TrendChartsV2.tsx", A + "lib/chartExport.ts",
        A + "lib/charts/model.ts", A + "lib/charts/layout.ts", "frontend/tests/unit/trend-charts-annotation.spec.tsx",
        "frontend/tests/unit/chart-export.spec.ts", "frontend/DESIGN_SYSTEM.md",
    ],
    "analysis plan (scope)": [
        A + "components/NarrativePane.tsx", A + "lib/narrativeDisplay.ts", A + "lib/narrativePresentation.ts",
        "backend/app/services/trend_analysis/narrative.py", "backend/app/services/trend_analysis/narrative_display.py",
        "backend/app/services/export_service.py", "frontend/tests/unit/narrative-pane.spec.tsx",
    ],
}
LIVE = {
    "#1606 table plan": "proto/kpi-table-number-system",
    "#1609 charts renderer": "claude/charts-v2-renderer",
    "#1601 export-source": "claude/brave-bohr-hai5vi-export-source",
    "#1583 per-filing-currency": "claude/implementation-launch-prompt-ofvuc1-per-filing-currency",
    "#1608 admin units": "claude/brave-edison-rvsfqz",
}


def measured(branch):
    base = subprocess.run(["git", "merge-base", "origin/main", f"origin/{branch}"], capture_output=True, text=True, check=True).stdout.strip()
    return subprocess.run(["git", "diff", "--name-only", base, f"origin/{branch}"], capture_output=True, text=True, check=True).stdout.split()


sets = {**{k: set(v) for k, v in PLAN.items()}, **{k: set(v) for k, v in SIBLINGS.items()}, **{k: set(measured(b)) for k, b in LIVE.items()}}
names = list(sets)
short = {n: n.split(" ")[0] if n.startswith(("WP", "#")) else n.split(" ")[0] for n in names}
print("| | " + " | ".join(short[n] for n in names) + " |")
print("|---|" + "---:|" * len(names))
for a in names:
    cells = []
    for b in names:
        cells.append("—" if a == b else (str(len(sets[a] & sets[b])) if sets[a] & sets[b] else "·"))
    print(f"| **{a}** ({len(sets[a])} files) | " + " | ".join(cells) + " |")
print("\nShared files by pair:\n")
for a, b in itertools.combinations(names, 2):
    shared = sorted(sets[a] & sets[b])
    if shared:
        print(f"- {a} × {b}: " + ", ".join(f"`{f.replace(A, 'analysis/')}`" for f in shared))
```
