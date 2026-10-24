"""Render an evidence pack as the text the generator reads.

Values print at a precision that lets a sentence round them honestly: dollars in millions with one
decimal, percentages and percentage points with one decimal, multiples with two. The gate compares a
printed claim with the raw value behind the cited ID, never with this rendering.
"""
from __future__ import annotations

from typing import Any


def fmt(value: float, unit: str) -> str:
    if unit == "usd":
        return f"${value / 1e6:,.1f}m"
    if unit == "usd_per_share":
        return f"${value:,.2f}/share"
    if unit == "pct":
        return f"{value:.1f}%"
    if unit == "pp":
        return f"{value:+.1f}pp"
    if unit == "x":
        return f"{value:.2f}x"
    if unit == "days":
        return f"{value:.0f} days"
    if unit == "years":
        return f"{value:.1f} years"
    if unit == "pctile":
        n = int(round(value))
        suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix} percentile"
    if unit == "shares":
        return f"{value / 1e6:,.1f}m shares"
    return f"{value:g}"


def _series_lines(pack: dict[str, Any], prefix: str) -> list[str]:
    """One line per (label) over periods, for F/X/S values."""
    rows: dict[str, list[tuple[str, str]]] = {}
    order: list[str] = []
    for vid, value in pack["values"].items():
        if not vid.startswith(prefix):
            continue
        label = value["label"]
        if label not in rows:
            rows[label] = []
            order.append(label)
        rows[label].append((value["period"], f"{value['period']} {fmt(value['value'], value['unit'])} [{vid}]"))
    out = []
    for label in order:
        cells = [cell for _, cell in sorted(rows[label])]
        out.append(f"- {label}: " + " · ".join(cells))
    return out


_D_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Year-over-year changes shown in the metrics table", ("g:revenue", "g:operating_income", "g:net_income", "g:earnings_per_share",
     "g:eps_diluted", "g:operating_cash_flow", "g:free_cash_flow", "g:capital_expenditures", "g:total_assets",
     "g:cash_and_equivalents", "g:shareholders_equity", "g:long_term_debt", "g:net_interest_income",
     "g:noninterest_income", "g:premiums_earned", "g:gross_profit", "g:current_liabilities", "ch:", "g:revenue_as_first_reported")),
    ("Revenue drivers (disaggregation shares, growth, contribution to total growth in pp)", ("share:", "g:seg", "contrib:", "segmargin:")),
    ("Common-size income statement (% of revenue) and cost-line growth", ("cs:", "g:cost_of_revenue", "g:research_and_development",
     "g:selling_general_admin", "g:operating_expenses", "g:stock_based_compensation", "tax_rate")),
    ("Operating leverage and operating-margin bridge (pp effect of each cost line)", ("incremental_margin", "operating_leverage_gap", "bridge:")),
    ("Cash conversion", ("ocf_to_ni", "fcf_to_ni", "capex_to_dna", "sbc_to_ocf", "cash_burn", "runway_years", "sbc_to_operating_loss")),
    ("Balance sheet, liquidity and working capital", ("liquidity", "total_debt", "net_cash", "net_cash_to_revenue", "dso", "dio",
     "g:liquidity", "g:total_debt", "g:receivables", "g:inventory", "roe")),
    ("Capital allocation", ("shareholder_returns", "returns_to_fcf", "g:diluted_shares")),
    ("Bank and insurer metrics", ("bank_revenue", "g:bank_revenue", "efficiency_ratio", "provision_to_revenue", "nii_share",
     "bank_net_margin", "loans_to_deposits", "allowance_to_loans", "g:noninterest_expense", "loss_ratio")),
    ("Window reference levels and 3-year CAGRs (for thresholds)", ("low:", "high:", "median:", "cagr3:")),
    ("Peer context (latest fiscal year)", ("peer_pctile:", "peer_median:")),
)


def _derived_lines(pack: dict[str, Any]) -> list[str]:
    keyed = {vid: key.split("|")[0] for key, vid in pack["series_keys"].items()}
    groups: dict[str, dict[str, list[str]]] = {title: {} for title, _ in _D_GROUPS}
    for vid, value in pack["values"].items():
        if not vid.startswith("D"):
            continue
        key = keyed.get(vid, "")
        title = next((t for t, prefixes in _D_GROUPS if any(key == p or key.startswith(p) for p in prefixes)), "Other")
        groups.setdefault(title, {}).setdefault(value["label"], []).append(
            f"{value['period']} {fmt(value['value'], value['unit'])} [{vid}]"
        )
    lines: list[str] = []
    for title, rows in groups.items():
        if not rows:
            continue
        lines.append(f"\n### {title}")
        for label, cells in rows.items():
            lines.append(f"- {label}: " + " · ".join(cells))
    return lines


def render(pack: dict[str, Any]) -> str:
    lines = [
        f"# Evidence pack: {pack['company_name']} ({pack['ticker']}), annual {pack['window']}",
        f"Sector: {pack['sector']} · SIC {pack.get('sic')} {pack.get('industry') or ''} · profile: {pack['profile']}",
        "IDs: F = the metrics table shown above the analysis; X = other filed XBRL lines; S = disaggregated revenue "
        "or segment profit from the 10-K's XBRL; D = computed by EarningsNerd from the cited inputs; R = red-flag "
        "candidates; P = filing passages. Cite the ID of every figure you state.",
        "",
        "## A. Metrics table (F)",
        *_series_lines(pack, "F"),
        "",
        "## B. Other filed lines (X)",
        *_series_lines(pack, "X"),
        "",
        "## C. Revenue and segment disaggregation (S)",
    ]
    for segment in pack["segments"]:
        tags = [segment["kind"]]
        if segment["measure"] != "revenue":
            tags.insert(0, {"OperatingIncomeLoss": "operating income", "SegmentReportingInformationProfitLoss": "segment profit",
                            "InterestIncomeExpenseNet": "net interest income", "NoninterestIncome": "noninterest income",
                            "NetIncomeLoss": "net income", "NoninterestExpense": "noninterest expense"}.get(segment["measure"], segment["measure"]))
        if segment.get("subtotal"):
            tags.append("subtotal")
        if segment.get("generic"):
            tags.append("category")
        cells = []
        for period, vid in sorted(segment["ids"].items()):
            value = pack["values"][vid]
            cells.append(f"{period} {fmt(value['value'], value['unit'])} [{vid}]")
        lines.append(f"- {segment['label']} ({', '.join(tags)}): " + " · ".join(cells))
    lines.append("\n## D. Derived drivers (D)")
    lines.extend(_derived_lines(pack))
    peers = pack.get("peers") or {}
    if peers.get("peers"):
        lines.append(f"\nPeer group '{peers['group']}': {', '.join(peers['peers'])}"
                     + (f" (missing: {', '.join(peers['missing'])})" if peers.get("missing") else ""))
    lines.append("\n## E. Red-flag candidates (R), ranked by severity then persistence")
    for flag in pack["red_flags"]:
        lines.append(f"- [{flag['id']}] {flag['severity']}, {flag['persistence']} period(s): {flag['detail']} "
                     f"Evidence: {' '.join('[' + e + ']' for e in flag['evidence'])}")
    lines.append("\n## F. Data checks (disclose any that affect a figure you use)")
    for check in pack["data_checks"]:
        lines.append(f"- {check['kind']} ({check['severity']}): {check['detail']}")
    if not pack["data_checks"]:
        lines.append("- none")
    lines.append(f"\nInflection years (large moves in revenue, operating margin or net income): {', '.join(pack['inflection_years']) or 'none'}")
    lines.append("\n## G. Filing passages (P), quoted from the company's 10-K filings")
    for passage in pack["passages"]:
        where = f"{passage['fiscal_year']} 10-K ({passage['accession']}), {passage['section']}"
        if passage.get("heading"):
            where += f" › {passage['heading']}"
        lines.append(f"[{passage['id']}] {where} [{passage['kind']}]\n\"{passage['text']}\"")
    return "\n".join(lines)
