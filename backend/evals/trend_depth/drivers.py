"""Driver evidence report: driver tree, common-size view and evidence availability per company.

    cd backend && python -m evals.trend_depth.drivers REGN SNAP JPM COST NVDA

Writes ``tasks/analysis-depth-2026-10/drivers/README.md`` and ``drivers/<TICKER>-common-size.csv``.

Availability classes for each node of the driver tree:

- ``structured``: the pack holds the values as XBRL facts (F, X, S) or values computed from them (D);
- ``text only``: no structured value, but the company's 10-K text discusses it (a regex finds it in the
  MD&A or notes of at least one filing in the window), so an analysis can cite a passage, not a figure;
- ``not available``: neither.

The text search runs over the full parsed text of every 10-K in the window, not only the passages the
pack selected, so "text only" says what the filings contain; whether the pack's passage selection found it
is a separate (recall) question.
"""
from __future__ import annotations

import csv
import re
import sys
from typing import Any

from evals.trend_depth import bootstrap
from evals.trend_depth.generate import load_pack

OUT = bootstrap.RECORDS / "drivers"

# (node, structured keys that count, text regex) — operating companies.
OPERATING_NODES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("Revenue by reportable segment", ("seg:segment",), r"reportable segments?|segment (revenue|net sales)"),
    ("Revenue by product or service", ("seg:product",), r"net product sales|revenue by product|net sales by (product|category)"),
    ("Revenue by geography", ("seg:geography",), r"(international|geographic) (revenue|net sales)|by geographic"),
    ("Price versus volume", (), r"(higher|lower) (net selling |average selling |net )?prices?|(sales|unit) volumes?"),
    ("Unit or customer metrics (users, members, units)", (), r"daily active users|DAU|ARPU|average revenue per user|paid members|cardholders|units (sold|delivered)|vehicles (produced|delivered)"),
    ("Comparable or same-store sales", (), r"comparable (store )?sales|same[- ]store sales"),
    ("Gross margin", ("gross_margin", "cs:cost_of_revenue"), r"gross margin"),
    ("R&D", ("cs:research_and_development",), r"research and development expenses?"),
    ("SG&A (or S&M and G&A)", ("cs:selling_general_admin", "cs:selling_marketing", "cs:general_admin"), r"selling, general and administrative|sales and marketing"),
    ("Stock-based compensation", ("cs:stock_based_compensation",), r"stock-based compensation"),
    ("Operating margin and its bridge", ("operating_margin", "bridge:"), r"operating (income|margin)"),
    ("Other income and tax rate", ("tax_rate", "other_nonoperating"), r"effective tax rate"),
    ("Cash conversion (OCF, FCF vs net income)", ("ocf_to_ni", "fcf_to_ni"), r"cash (provided by|flows? from) operating activities"),
    ("Working capital (receivables, inventory)", ("dso", "dio"), r"accounts receivable|inventor(y|ies)"),
    ("Capital expenditure and guidance", ("cs:capital_expenditures",), r"capital expenditures"),
    ("Net cash or net debt", ("net_cash", "total_debt"), r"(senior|convertible) notes|credit facility|borrowings"),
    ("Buybacks and dividends", ("shareholder_returns",), r"repurchase|dividends?"),
    ("Acquisitions", ("acquisitions",), r"acqui(red|sition)"),
    ("Peer percentiles (EarningsNerd store)", ("peer_pctile:",), r"$^"),
    ("Company guidance (forward figures)", (), r"we (currently )?expect|guidance|outlook"),
)
BANK_NODES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("Net interest income", ("net_interest_income",), r"net interest income"),
    ("Noninterest income", ("noninterest_income",), r"noninterest (income|revenue)"),
    ("Segment revenue and net income", ("seg:segment",), r"(line of business|segment) results"),
    ("Net interest margin", (), r"net interest (margin|yield)"),
    ("Noninterest expense and efficiency ratio", ("efficiency_ratio",), r"noninterest expense|overhead ratio|efficiency ratio"),
    ("Credit-loss provision", ("provision_to_revenue",), r"provision for credit losses"),
    ("Loans and deposits", ("loans_to_deposits",), r"(total )?loans|deposits"),
    ("Allowance coverage", ("allowance_to_loans",), r"allowance for (credit|loan) losses"),
    ("Net charge-offs", (), r"net charge-offs"),
    ("Regulatory capital (CET1)", (), r"CET1|common equity tier 1"),
    ("Return on equity", ("roe",), r"return on (average )?(tangible )?(common )?equity|ROTCE|ROE"),
    ("Buybacks and dividends", ("shareholder_returns",), r"repurchase|dividends?"),
    ("Peer percentiles (EarningsNerd store)", ("peer_pctile:",), r"$^"),
    ("Company guidance (forward figures)", (), r"we (currently )?expect|guidance|outlook"),
)


def _structured(pack: dict[str, Any], keys: tuple[str, ...]) -> tuple[list[str], int]:
    """Keys with values, and how many of the window's years have at least one of them."""
    hits, years = [], set()
    for key in keys:
        if key.startswith("seg:"):
            kind = key.split(":", 1)[1]
            found = [s for s in pack["segments"] if s["kind"] == kind and s["measure"] == "revenue"]
            if found:
                hits.append(key)
                years.update(period for s in found for period in s["ids"])
            continue
        matched = [sk for sk in pack["series_keys"] if sk.split("|")[0] == key or sk.split("|")[0].startswith(key)]
        if matched:
            hits.append(key)
            years.update(sk.split("|")[1] for sk in matched)
    return hits, len(years & {p["key"] for p in pack["periods"]})


def _text_hits(pack: dict[str, Any], pattern: str) -> int:
    regex = re.compile(pattern, re.IGNORECASE)
    count = 0
    for filing in pack["filings"]:
        parsed = bootstrap.read_cached(f"documents/{filing['accession']}.json") or {}
        text = (parsed.get("mda") or "") + "\n" + (parsed.get("full") or "")
        if regex.search(text):
            count += 1
    return count


def availability(pack: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = BANK_NODES if pack["profile"] == "bank" else OPERATING_NODES
    rows = []
    for node, keys, pattern in nodes:
        structured, years = _structured(pack, keys)
        filings = _text_hits(pack, pattern)
        latest = pack["periods"][-1]["key"]
        in_latest = any(f"{k}|{latest}" in pack["series_keys"] for k in structured) or any(
            latest in s["ids"] for k in structured if k.startswith("seg:")
            for s in pack["segments"] if s["kind"] == k.split(":", 1)[1] and s["measure"] == "revenue")
        if structured and in_latest:
            status = "structured"
        elif structured:
            status = "structured (partial)"
        else:
            status = "text only" if filings else "not available"
        rows.append({"node": node, "status": status, "structured_keys": structured, "years": years,
                     "filings_mentioning": filings, "filings_in_window": len(pack["filings"])})
    return rows


def common_size(pack: dict[str, Any]) -> list[list[str]]:
    periods = [p["key"] for p in pack["periods"]]
    keys = [k for k in dict.fromkeys(sk.split("|")[0] for sk in pack["series_keys"])
            if k.startswith(("cs:", "bridge:", "tax_rate", "ocf_to_ni", "fcf_to_ni", "efficiency_ratio", "provision_to_revenue", "nii_share"))
            or k in ("gross_margin", "operating_margin", "net_margin")]
    rows = [["metric", *periods]]
    for key in keys:
        label = None
        cells = []
        for period in periods:
            vid = pack["series_keys"].get(f"{key}|{period}")
            value = pack["values"].get(vid) if vid else None
            if value and label is None:
                label = value["label"]
            cells.append(f"{value['value']:.1f}" if value else "")
        rows.append([label or key, *cells])
    return rows


def driver_tree(pack: dict[str, Any]) -> list[str]:
    """The latest year's tree, as text: top line -> members -> margins -> earnings -> cash."""
    latest = pack["periods"][-1]["key"]
    values = pack["values"]

    def v(key: str, period: str = latest) -> str:
        vid = pack["series_keys"].get(f"{key}|{period}")
        if not vid:
            return "n/a"
        value = values[vid]
        unit = value["unit"]
        number = value["value"]
        text = (f"${number / 1e9:,.2f}B" if unit == "usd" else f"{number:.1f}%" if unit == "pct"
                else f"{number:+.1f}pp" if unit == "pp" else f"{number:.2f}x" if unit == "x" else f"{number:,.1f}")
        return f"{text} [{vid}]"

    bank = pack["profile"] == "bank"
    top = "bank_revenue" if bank else "revenue"
    lines = [f"{pack['ticker']} {latest}", f"{'Revenue (NII + noninterest income)' if bank else 'Revenue'}: {v(top)}, growth {v('g:' + top)}"]
    members = [s for s in pack["segments"] if s["measure"] == "revenue" and not s.get("subtotal") and latest in s["ids"]]
    members.sort(key=lambda s: -values[s["ids"][latest]]["value"])
    for member in members[:8]:
        key = member["key"]
        lines.append(f"  ├─ {member['label'][:60]} ({member['kind']}): {v(key)}; share {v('share:' + key)}; "
                     f"contribution {v('contrib:' + key)}")
    if bank:
        lines += [f"  ├─ Net interest income: {v('net_interest_income')}", f"  └─ Noninterest income: {v('noninterest_income')}",
                  f"Efficiency ratio: {v('efficiency_ratio')}; provision % revenue: {v('provision_to_revenue')}",
                  f"Net income: {v('net_income')}; ROE: {v('roe')}", f"Buybacks + dividends: {v('shareholder_returns')}"]
        return lines
    lines += [
        f"Gross margin: {v('gross_margin')}; cost of revenue % revenue: {v('cs:cost_of_revenue')}",
        f"  ├─ R&D % revenue: {v('cs:research_and_development')} (margin effect {v('bridge:cs:research_and_development')})",
        f"  ├─ SG&A % revenue: {v('cs:selling_general_admin')} (margin effect {v('bridge:cs:selling_general_admin')})",
        f"  └─ Other lines (margin effect {v('bridge:other')})",
        f"Operating margin: {v('operating_margin')} (change {v('ch:operating_margin')}); incremental margin {v('incremental_margin')}",
        f"Net margin: {v('net_margin')}; tax rate {v('tax_rate')}",
        f"Net income {v('net_income')} -> OCF {v('operating_cash_flow')} ({v('ocf_to_ni')}) -> FCF {v('free_cash_flow')} ({v('fcf_to_ni')})",
        f"  capex % revenue {v('cs:capital_expenditures')}; capex/D&A {v('capex_to_dna')}; SBC % OCF {v('sbc_to_ocf')}",
        f"Net cash {v('net_cash')} ({v('net_cash_to_revenue')} of revenue); buybacks + dividends {v('shareholder_returns')} ({v('returns_to_fcf')} of FCF)",
    ]
    return lines


def main(tickers: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Driver evidence: what the filings can support",
        "",
        "Generated by `python -m evals.trend_depth.drivers` from the evidence packs (`packs/`) and the cached 10-K texts. "
        "For each company: the latest year's driver tree with pack IDs, the availability of every driver node "
        "(structured XBRL / filing text only / not available), and a link to its common-size view.",
        "",
    ]
    summary: dict[str, dict[str, int]] = {}
    for ticker in tickers:
        pack = load_pack(ticker)
        rows = availability(pack)
        counts = {status: sum(1 for r in rows if r["status"] == status)
                  for status in ("structured", "structured (partial)", "text only", "not available")}
        summary[ticker] = counts
        with (OUT / f"{ticker}-common-size.csv").open("w", newline="") as handle:
            csv.writer(handle).writerows(common_size(pack))
        lines += [f"## {pack['company_name']} ({ticker}) · {pack['window']} · profile {pack['profile']}", "",
                  "Driver tree (latest year):", "", "```", *driver_tree(pack), "```", "",
                  "| Driver node | Availability | Structured keys | Years with values | 10-Ks whose text mentions it |",
                  "|---|---|---|---|---|"]
        for row in rows:
            lines.append(f"| {row['node']} | {row['status']} | {', '.join(row['structured_keys']) or '—'} | "
                         f"{row['years'] or '—'} of {len(pack['periods'])} | {row['filings_mentioning']} of {row['filings_in_window']} |")
        lines += ["", f"Common-size view: [`{ticker}-common-size.csv`]({ticker}-common-size.csv). "
                  f"Passages selected for the pack: {len(pack['passages'])}; data checks: {len(pack['data_checks'])}.", ""]
    lines += ["## Summary", "", "| Company | Structured | Structured (partial) | Text only | Not available |", "|---|---|---|---|---|"]
    for ticker, counts in summary.items():
        lines.append(f"| {ticker} | {counts['structured']} | {counts['structured (partial)']} | {counts['text only']} | {counts['not available']} |")
    (OUT / "README.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT / 'README.md'}")


if __name__ == "__main__":
    main(sys.argv[1:])
