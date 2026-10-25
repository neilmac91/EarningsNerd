"""Driver tree, common-size view, red-flag candidates and data checks for one evidence pack.

Every number the analysis may state is registered once with an ID, a unit, a period, a formula and the
IDs of its inputs: ``F#`` dataset points (the metrics table's own markers), ``X#`` extended facts,
``S#`` disaggregated revenue/profit, ``D#`` values computed here, ``R#`` red-flag candidates. The model
cites IDs; the fact-check gate reconciles every printed number against the values behind them.

Units: ``usd`` (raw dollars), ``pct`` (a percentage, 24.9 means 24.9%), ``pp`` (percentage points),
``x`` (a multiple), ``days``, ``years``, ``shares``, ``usd_per_share``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Any, Optional


@dataclass
class Value:
    id: str
    label: str
    period: str
    value: float
    unit: str
    formula: str = ""
    inputs: list[str] = field(default_factory=list)
    source: str = ""  # "filed" | "calculated" | "derived" | "peer"
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in ("", [], None)}


class Registry:
    """ID allocation per prefix and lookup by (key, period)."""

    def __init__(self) -> None:
        self.values: dict[str, Value] = {}
        self._counters: dict[str, int] = {}
        self.by_key: dict[tuple[str, str], str] = {}

    def add(self, prefix: str, key: str, label: str, period: str, value: Optional[float], unit: str,
            formula: str = "", inputs: Optional[list[str]] = None, source: str = "derived",
            note: str = "", fixed_id: Optional[str] = None, tag: str = "") -> Optional[str]:
        """``tag`` files a second value of the same series and period beside the first, which keeps its place
        (the series key reads ``key|period|tag``): version 2's checked peer rank beside version 1's."""
        if value is None:
            return None
        if fixed_id is None:
            self._counters[prefix] = self._counters.get(prefix, 0) + 1
            vid = f"{prefix}{self._counters[prefix]}"
        else:
            vid = fixed_id
        self.values[vid] = Value(vid, label, period, float(value), unit, formula, list(inputs or []), source, note)
        self.by_key[(key, f"{period}|{tag}" if tag else period)] = vid
        return vid

    def get(self, key: str, period: str) -> Optional[Value]:
        vid = self.by_key.get((key, period))
        return self.values.get(vid) if vid else None

    def val(self, key: str, period: str) -> Optional[float]:
        hit = self.get(key, period)
        return hit.value if hit else None

    def ref(self, key: str, period: str) -> Optional[str]:
        return self.by_key.get((key, period))


def _ratio(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _growth(cur: Optional[float], prior: Optional[float]) -> Optional[float]:
    if cur is None or prior is None or prior == 0 or (cur != 0 and (cur > 0) != (prior > 0)):
        return None
    return (cur - prior) / abs(prior) * 100.0


def _sum(*values: Optional[float]) -> Optional[float]:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def _usd_words(value: float) -> str:
    """A red flag's dollar figure as a sentence states it: "$89.6 billion", "$596.3 million"."""
    return f"${value / 1e9:,.1f} billion" if abs(value) >= 1e9 else f"${value / 1e6:,.1f} million"


def register_dataset(reg: Registry, dataset: dict[str, Any]) -> None:
    """The metrics table's own points under their existing markers (F#), plus CAGR markers."""
    for series in dataset["series"]:
        concept = series["concept"]
        unit = "pct" if series["percent"] else ("x" if series["unit"] == "pure" else (
            "usd_per_share" if series["unit"].endswith("/shares") else "usd"))
        for point in series["points"]:
            if point.get("value") is None or not point.get("marker"):
                continue
            provenance = point.get("provenance") or {}
            reg.add("F", concept, series["label"], point["period"], point["value"], unit,
                    formula=str(provenance.get("formula") or ""),
                    source="calculated" if provenance.get("method") == "calculated" else "filed",
                    fixed_id=point["marker"])
        if series.get("cagr_marker") and series.get("cagr") is not None:
            reg.add("F", f"{concept}_cagr", f"{series['label']} CAGR", series.get("cagr_window") or "",
                    series["cagr"] * 100.0, "pct", formula="compound annual growth", source="calculated",
                    fixed_id=series["cagr_marker"])


def register_extended(reg: Registry, xseries: dict[str, Any], end_to_key: dict[str, str], labels: dict[str, str]) -> list[dict[str, Any]]:
    """Extended facts (X#). Returns recast checks (first-reported vs latest differ by more than 1%)."""
    recasts = []
    for concept, payload in xseries.items():
        unit = {"USD": "usd", "shares": "shares"}.get(payload["unit"], "usd")
        for end, point in payload["points"].items():
            key = end_to_key.get(end)
            if key is None:
                continue
            note = f"{point['tag']}; first reported in {point['first_accession']}"
            vid = reg.add("X", concept, labels.get(concept, concept.replace("_", " ")), key, point["first_value"], unit,
                          formula=f"us-gaap:{point['tag']}", source="filed", note=note)
            latest, first = point["latest_value"], point["first_value"]
            if first and abs(latest - first) / abs(first) > 0.01:
                recasts.append({"id": vid, "concept": concept, "period": key, "first": first, "latest": latest,
                                "first_accession": point["first_accession"],
                                "latest_accession": point["latest_accession"]})
    return recasts


X_LABELS = {
    "revenue_reported_total": "Total revenues as reported",
    "net_income_10k": "Net income as reported in that year's 10-K",
    "cost_of_revenue": "Cost of revenue",
    "research_and_development": "R&D expense",
    "acquired_in_process_rd": "Acquired in-process R&D",
    "selling_general_admin": "SG&A expense",
    "selling_marketing": "Selling and marketing expense",
    "general_admin": "General and administrative expense",
    "operating_expenses": "Total operating expenses",
    "depreciation_amortization": "Depreciation and amortization",
    "stock_based_compensation": "Stock-based compensation",
    "interest_expense": "Interest expense",
    "pretax_income": "Income before income taxes",
    "income_tax": "Income tax expense",
    "other_nonoperating": "Other income (expense)",
    "goodwill_impairment": "Goodwill impairment",
    "asset_impairment": "Asset impairment charges",
    "diluted_shares": "Diluted weighted-average shares",
    "share_repurchases": "Share repurchases (cash)",
    "dividends_paid": "Dividends paid (cash)",
    "acquisitions": "Acquisitions, net of cash acquired",
    "debt_issued": "Debt issued",
    "debt_repaid": "Debt repaid",
    "interest_income": "Interest income",
    "noninterest_expense": "Noninterest expense",
    "credit_loss_provision": "Provision for credit losses",
    "preferred_dividends": "Preferred dividends",
    "claims_incurred": "Losses and claims incurred",
    "short_term_investments": "Short-term investments",
    "long_term_investments": "Long-term investments",
    "debt_current": "Current portion of debt",
    "short_term_borrowings": "Short-term borrowings",
    "debt_noncurrent": "Long-term debt (noncurrent)",
    "inventory": "Inventory",
    "receivables": "Accounts receivable",
    "total_liabilities": "Total liabilities",
    "goodwill": "Goodwill",
    "loans": "Loans, net",
    "deposits": "Deposits",
    "credit_loss_allowance": "Allowance for credit losses",
}


def register_segments(reg: Registry, series: list[dict[str, Any]], end_to_key: dict[str, str]) -> list[dict[str, Any]]:
    """Disaggregated revenue/profit members (S#). Returns the members registered, for the driver tree."""
    registered = []
    for item in series:
        periods = {end_to_key[end]: point for end, point in item["points"].items() if end in end_to_key}
        if not periods:
            continue
        key = f"seg:{item['axis']}:{item['measure']}:{item['member']}"
        label = f"{item['label']} ({item['kind']}{'' if item['measure'] == 'revenue' else ', ' + item['measure']})"
        ids = {}
        for period, point in sorted(periods.items()):
            note = f"{item['axis']}={item['member']}; {point['accession']}"
            if point["first_value"] != point["value"]:
                note += f"; first reported {point['first_value']:.0f} in {point['first_accession']}"
            ids[period] = reg.add("S", key, label, period, point["value"], "usd",
                                  formula=f"{'/'.join(item['concepts'])} [{item['kind']}]", source="filed", note=note)
        registered.append({**item, "key": key, "ids": ids, "display": label})
    return registered


def build_derived(reg: Registry, periods: list[str], profile: str, segments: list[dict[str, Any]]) -> None:
    """Compute D# values over the aligned annual periods."""
    def f(concept: str, period: str) -> Optional[float]:
        return reg.val(concept, period)

    def r(concept: str, period: str) -> Optional[str]:
        return reg.ref(concept, period)

    top = "revenue" if any(reg.ref("revenue", p) for p in periods) else None
    for i, period in enumerate(periods):
        prior = periods[i - 1] if i else None
        # Common-size denominators: total revenues as first reported (the basis of the first-reported cost
        # lines in X) where the pack has them, else the metrics table's revenue. They differ only in a year
        # the table carries a later recast (Regeneron FY2018-FY2019).
        basis_key = "revenue_reported_total" if r("revenue_reported_total", period) else "revenue"
        revenue = f(basis_key, period) if top else None
        rev_ref = r(basis_key, period)

        # Common-size of revenue.
        for concept, label in (
            ("cost_of_revenue", "Cost of revenue % of revenue"),
            ("research_and_development", "R&D % of revenue"),
            ("selling_general_admin", "SG&A % of revenue"),
            ("selling_marketing", "Selling & marketing % of revenue"),
            ("general_admin", "G&A % of revenue"),
            ("stock_based_compensation", "Stock-based compensation % of revenue"),
            ("depreciation_amortization", "D&A % of revenue"),
            ("acquired_in_process_rd", "Acquired IPR&D % of revenue"),
            ("capital_expenditures", "Capex % of revenue"),
            ("free_cash_flow", "Free cash flow margin"),
            ("operating_cash_flow", "Operating cash flow % of revenue"),
        ):
            value = _ratio(f(concept, period), revenue)
            if value is not None:
                reg.add("D", f"cs:{concept}", label, period, abs(value) * 100.0 if concept == "capital_expenditures" else value * 100.0,
                        "pct", formula=f"{concept} / revenue", inputs=[r(concept, period), rev_ref])

        tax_rate = _ratio(f("income_tax", period), f("pretax_income", period))
        if tax_rate is not None and (f("pretax_income", period) or 0) > 0:
            reg.add("D", "tax_rate", "Effective tax rate", period, tax_rate * 100.0, "pct",
                    formula="income_tax / pretax_income", inputs=[r("income_tax", period), r("pretax_income", period)])

        # Cash conversion.
        ni = f("net_income", period)
        for concept, key, label in (
            ("operating_cash_flow", "ocf_to_ni", "Operating cash flow / net income"),
            ("free_cash_flow", "fcf_to_ni", "Free cash flow / net income"),
        ):
            if ni and ni > 0:
                value = _ratio(f(concept, period), ni)
                if value is not None:
                    reg.add("D", key, label, period, value, "x", formula=f"{concept} / net_income",
                            inputs=[r(concept, period), r("net_income", period)])
        capex, dna = f("capital_expenditures", period), f("depreciation_amortization", period)
        if capex is not None and dna:
            reg.add("D", "capex_to_dna", "Capex / D&A", period, abs(capex) / dna, "x",
                    formula="|capex| / depreciation_amortization", inputs=[r("capital_expenditures", period), r("depreciation_amortization", period)])
        sbc, ocf = f("stock_based_compensation", period), f("operating_cash_flow", period)
        if sbc is not None and ocf and ocf > 0:
            reg.add("D", "sbc_to_ocf", "Stock-based compensation % of operating cash flow", period, sbc / ocf * 100.0, "pct",
                    formula="stock_based_compensation / operating_cash_flow", inputs=[r("stock_based_compensation", period), r("operating_cash_flow", period)])

        # Liquidity, debt, net cash.
        liquidity = None if profile in ("bank", "insurer") else _sum(
            f("cash_and_equivalents", period), f("short_term_investments", period), f("long_term_investments", period))
        liquidity_inputs = [x for x in (r("cash_and_equivalents", period), r("short_term_investments", period), r("long_term_investments", period)) if x]
        if liquidity is not None:
            reg.add("D", "liquidity", "Cash and investments", period, liquidity, "usd",
                    formula="cash + short-term investments + long-term investments", inputs=liquidity_inputs)
        noncurrent = f("debt_noncurrent", period)
        noncurrent_ref = r("debt_noncurrent", period)
        if noncurrent is None:
            noncurrent, noncurrent_ref = f("long_term_debt", period), r("long_term_debt", period)
        # A bank's borrowings are its funding, not leverage in the operating-company sense; the store's
        # long-term debt also stops early for some banks, so the sum would be short-term borrowings only.
        debt = None if profile in ("bank", "insurer") else _sum(noncurrent, f("debt_current", period), f("short_term_borrowings", period))
        debt_inputs = [x for x in (noncurrent_ref, r("debt_current", period), r("short_term_borrowings", period)) if x]
        if debt is not None:
            reg.add("D", "total_debt", "Total debt", period, debt, "usd",
                    formula="long-term debt + current debt + short-term borrowings", inputs=debt_inputs)
        if liquidity is not None and profile not in ("bank", "insurer"):
            net_cash = liquidity - (debt or 0.0)
            reg.add("D", "net_cash", "Net cash (cash and investments less debt)", period, net_cash, "usd",
                    formula="liquidity - total_debt", inputs=[reg.ref("liquidity", period), *( [reg.ref("total_debt", period)] if debt is not None else [])])
            if revenue:
                reg.add("D", "net_cash_to_revenue", "Net cash % of revenue", period, net_cash / revenue * 100.0, "pct",
                        formula="net_cash / revenue", inputs=[reg.ref("net_cash", period), rev_ref])

        # Capital allocation.
        returned = _sum(f("share_repurchases", period), f("dividends_paid", period))
        if returned is not None:
            reg.add("D", "shareholder_returns", "Buybacks plus dividends", period, returned, "usd",
                    formula="share_repurchases + dividends_paid",
                    inputs=[x for x in (r("share_repurchases", period), r("dividends_paid", period)) if x])
            fcf = f("free_cash_flow", period)
            if fcf and fcf > 0:
                reg.add("D", "returns_to_fcf", "Buybacks plus dividends % of free cash flow", period, returned / fcf * 100.0, "pct",
                        formula="shareholder_returns / free_cash_flow", inputs=[reg.ref("shareholder_returns", period), r("free_cash_flow", period)])

        # Working-capital efficiency.
        receivables, inventory = f("receivables", period), f("inventory", period)
        if receivables is not None and revenue:
            reg.add("D", "dso", "Days sales outstanding (year-end receivables)", period, receivables / revenue * 365.0, "days",
                    formula="receivables / revenue x 365", inputs=[r("receivables", period), rev_ref])
        cogs = f("cost_of_revenue", period)
        if inventory is not None and cogs:
            reg.add("D", "dio", "Days inventory outstanding (year-end inventory)", period, inventory / cogs * 365.0, "days",
                    formula="inventory / cost_of_revenue x 365", inputs=[r("inventory", period), r("cost_of_revenue", period)])

        # Loss-making profile: burn and runway.
        fcf = f("free_cash_flow", period)
        if fcf is not None and fcf < 0:
            reg.add("D", "cash_burn", "Cash burn (negative free cash flow)", period, -fcf, "usd",
                    formula="-free_cash_flow", inputs=[r("free_cash_flow", period)])
            if liquidity:
                reg.add("D", "runway_years", "Years of burn covered by cash and investments", period, liquidity / -fcf, "years",
                        formula="liquidity / cash_burn", inputs=[reg.ref("liquidity", period), reg.ref("cash_burn", period)])
        oi = f("operating_income", period)
        if sbc is not None and oi is not None and oi < 0:
            reg.add("D", "sbc_to_operating_loss", "Stock-based compensation % of operating loss", period, sbc / -oi * 100.0, "pct",
                    formula="stock_based_compensation / -operating_income", inputs=[r("stock_based_compensation", period), r("operating_income", period)])

        # Banks.
        nii, nonint = f("net_interest_income", period), f("noninterest_income", period)
        if profile == "bank" and nii is not None:
            bank_revenue = _sum(nii, nonint)
            reg.add("D", "bank_revenue", "Net interest income plus noninterest income", period, bank_revenue, "usd",
                    formula="net_interest_income + noninterest_income",
                    inputs=[x for x in (r("net_interest_income", period), r("noninterest_income", period)) if x])
            nie = f("noninterest_expense", period)
            if nie is not None and bank_revenue:
                reg.add("D", "efficiency_ratio", "Efficiency ratio (noninterest expense / revenue)", period, nie / bank_revenue * 100.0, "pct",
                        formula="noninterest_expense / bank_revenue", inputs=[r("noninterest_expense", period), reg.ref("bank_revenue", period)])
            provision = f("credit_loss_provision", period)
            if provision is not None and bank_revenue:
                reg.add("D", "provision_to_revenue", "Credit-loss provision % of revenue", period, provision / bank_revenue * 100.0, "pct",
                        formula="credit_loss_provision / bank_revenue", inputs=[r("credit_loss_provision", period), reg.ref("bank_revenue", period)])
            if bank_revenue and nii is not None:
                reg.add("D", "nii_share", "Net interest income % of revenue", period, nii / bank_revenue * 100.0, "pct",
                        formula="net_interest_income / bank_revenue", inputs=[r("net_interest_income", period), reg.ref("bank_revenue", period)])
            if bank_revenue and ni is not None:
                reg.add("D", "bank_net_margin", "Net income % of revenue", period, ni / bank_revenue * 100.0, "pct",
                        formula="net_income / bank_revenue", inputs=[r("net_income", period), reg.ref("bank_revenue", period)])
            loans, deposits = f("loans", period), f("deposits", period)
            if loans is not None and deposits:
                reg.add("D", "loans_to_deposits", "Loans % of deposits", period, loans / deposits * 100.0, "pct",
                        formula="loans / deposits", inputs=[r("loans", period), r("deposits", period)])
            allowance = f("credit_loss_allowance", period)
            if allowance is not None and loans:
                reg.add("D", "allowance_to_loans", "Allowance % of loans", period, allowance / loans * 100.0, "pct",
                        formula="credit_loss_allowance / loans", inputs=[r("credit_loss_allowance", period), r("loans", period)])

        # Insurers.
        premiums, claims = f("premiums_earned", period), f("claims_incurred", period)
        if premiums and claims is not None:
            reg.add("D", "loss_ratio", "Losses and claims % of premiums earned", period, claims / premiums * 100.0, "pct",
                    formula="claims_incurred / premiums_earned", inputs=[r("claims_incurred", period), r("premiums_earned", period)])

        # Return on equity (average equity).
        if prior is not None and ni is not None:
            eq, eq_prior = f("shareholders_equity", period), f("shareholders_equity", prior)
            if eq and eq_prior and eq > 0 and eq_prior > 0:
                reg.add("D", "roe", "Return on average equity", period, ni / ((eq + eq_prior) / 2) * 100.0, "pct",
                        formula="net_income / average(shareholders_equity, prior)",
                        inputs=[r("net_income", period), r("shareholders_equity", period), r("shareholders_equity", prior)])

        if prior is None:
            continue
        # The metrics table's own year-over-year changes, as citable values (relative growth with the
        # sign-flip guard; percentage-point change for margins), so a sentence citing "+1.0%" cites a value.
        for concept in ("revenue", "operating_income", "net_income", "earnings_per_share", "eps_diluted",
                        "operating_cash_flow", "free_cash_flow", "capital_expenditures", "total_assets",
                        "cash_and_equivalents", "shareholders_equity", "long_term_debt", "net_interest_income",
                        "noninterest_income", "premiums_earned", "gross_profit", "current_liabilities"):
            cur_hit, prior_hit = reg.get(concept, period), reg.get(concept, prior)
            if cur_hit is None or prior_hit is None:
                continue
            if cur_hit.value < 0 and prior_hit.value < 0:
                # Both years are losses: "growth" of a negative number reads backwards. State the change in
                # the size of the loss instead (negative = the loss narrowed).
                reg.add("D", f"g:{concept}", f"{cur_hit.label}: change in size of loss", period,
                        (abs(cur_hit.value) / abs(prior_hit.value) - 1) * 100.0, "pct",
                        formula=f"|{concept}| / |prior| - 1", inputs=[cur_hit.id, prior_hit.id])
                continue
            value = _growth(cur_hit.value, prior_hit.value)
            if value is not None:
                reg.add("D", f"g:{concept}", f"{cur_hit.label} growth", period, value, "pct",
                        formula=f"{concept} / prior - 1", inputs=[cur_hit.id, prior_hit.id])
        for concept in ("gross_margin", "operating_margin", "net_margin"):
            cur_hit, prior_hit = reg.get(concept, period), reg.get(concept, prior)
            if cur_hit is not None and prior_hit is not None:
                reg.add("D", f"ch:{concept}", f"{cur_hit.label} change", period, cur_hit.value - prior_hit.value, "pp",
                        formula=f"{concept} - prior", inputs=[cur_hit.id, prior_hit.id])
        # Growth of cost lines and operating leverage.
        for concept, label in (
            ("cost_of_revenue", "Cost of revenue growth"),
            ("research_and_development", "R&D growth"),
            ("selling_general_admin", "SG&A growth"),
            ("operating_expenses", "Operating expenses growth"),
            ("stock_based_compensation", "Stock-based compensation growth"),
            ("diluted_shares", "Diluted share count change"),
            ("noninterest_expense", "Noninterest expense growth"),
            ("bank_revenue", "Bank revenue growth"),
            ("liquidity", "Cash and investments growth"),
            ("total_debt", "Total debt growth"),
            ("receivables", "Receivables growth"),
            ("inventory", "Inventory growth"),
        ):
            cur_val, prior_val = reg.val(concept, period), reg.val(concept, prior)
            value = _growth(cur_val, prior_val)
            if value is not None:
                reg.add("D", f"g:{concept}", label, period, value, "pct", formula=f"{concept} growth vs {prior}",
                        inputs=[reg.ref(concept, period), reg.ref(concept, prior)])
        rev, rev_prior = f("revenue", period), f("revenue", prior)
        oi, oi_prior = f("operating_income", period), f("operating_income", prior)
        if None not in (rev, rev_prior, oi, oi_prior) and rev_prior and abs(rev - rev_prior) > 0.01 * abs(rev_prior):
            reg.add("D", "incremental_margin", "Incremental operating margin (change in operating income / change in revenue)", period,
                    (oi - oi_prior) / (rev - rev_prior) * 100.0, "pct",
                    formula="(OI - OI prior) / (revenue - revenue prior)",
                    inputs=[r("operating_income", period), r("operating_income", prior), r("revenue", period), r("revenue", prior)])
        opex_cur = reg.val("operating_expenses", period)
        opex_prior = reg.val("operating_expenses", prior)
        if opex_cur is None and None not in (rev, oi):
            opex_cur = rev - oi
        if opex_prior is None and None not in (rev_prior, oi_prior):
            opex_prior = rev_prior - oi_prior
        opex_growth, rev_growth = _growth(opex_cur, opex_prior), _growth(rev, rev_prior)
        if opex_growth is not None and rev_growth is not None:
            reg.add("D", "operating_leverage_gap", "Revenue growth minus operating-cost growth", period, rev_growth - opex_growth, "pp",
                    formula="revenue growth - (revenue - operating income) growth",
                    inputs=[r("revenue", period), r("revenue", prior), r("operating_income", period), r("operating_income", prior)])

        # Operating-margin bridge (pp): what moved the margin, by cost line.
        prior_basis = "revenue_reported_total" if r("revenue_reported_total", prior) else "revenue"
        om = _ratio(f("operating_income", period), f(basis_key, period))
        om_prior = _ratio(f("operating_income", prior), f(prior_basis, prior))
        om = om * 100.0 if om is not None else None
        om_prior = om_prior * 100.0 if om_prior is not None else None
        if om is not None and om_prior is not None:
            explained = 0.0
            parts = []
            for key, sign, label in (
                ("cs:cost_of_revenue", -1, "cost of revenue"),
                ("cs:research_and_development", -1, "R&D"),
                ("cs:selling_general_admin", -1, "SG&A"),
                ("cs:acquired_in_process_rd", -1, "acquired IPR&D"),
            ):
                cur_cs, prior_cs = reg.val(key, period), reg.val(key, prior)
                if cur_cs is None or prior_cs is None:
                    continue
                contribution = sign * (cur_cs - prior_cs)
                explained += contribution
                parts.append(label)
                reg.add("D", f"bridge:{key}", f"Operating-margin effect of {label} (pp)", period, contribution, "pp",
                        formula=f"-(Δ {label} % of revenue)", inputs=[reg.ref(key, period), reg.ref(key, prior)])
            if parts:
                reg.add("D", "bridge:other", "Operating-margin effect of other lines (residual, pp)", period,
                        (om - om_prior) - explained, "pp",
                        formula="Δ (operating income / revenue on the cost lines' basis) - explained lines",
                        inputs=[r("operating_income", period), r(basis_key, period),
                                r("operating_income", prior), r(prior_basis, prior)])

    _segment_metrics(reg, periods, segments)
    _window_figures(reg, periods)


def _segment_metrics(reg: Registry, periods: list[str], segments: list[dict[str, Any]]) -> None:
    for item in segments:
        if item["measure"] != "revenue" or item.get("subtotal"):
            continue
        for i, period in enumerate(periods):
            value = reg.val(item["key"], period)
            # Members are reported on the basis of the filing that tagged them; total revenues as first
            # reported share that basis where the metrics table carries a later recast.
            total_key = "revenue_reported_total" if reg.ref("revenue_reported_total", period) else "revenue"
            revenue = reg.val(total_key, period)
            if value is None:
                continue
            share = _ratio(value, revenue)
            if share is not None:
                reg.add("D", f"share:{item['key']}", f"{item['display']} share of revenue", period, share * 100.0, "pct",
                        formula=f"member / {total_key}", inputs=[reg.ref(item["key"], period), reg.ref(total_key, period)])
            if i == 0:
                continue
            prior = periods[i - 1]
            prior_total_key = "revenue_reported_total" if reg.ref("revenue_reported_total", prior) else "revenue"
            prior_value, prior_revenue = reg.val(item["key"], prior), reg.val(prior_total_key, prior)
            growth = _growth(value, prior_value)
            if growth is not None:
                reg.add("D", f"g:{item['key']}", f"{item['display']} growth", period, growth, "pct",
                        formula="member growth", inputs=[reg.ref(item["key"], period), reg.ref(item["key"], prior)])
            if prior_value is not None and prior_revenue:
                reg.add("D", f"contrib:{item['key']}", f"{item['display']} contribution to revenue growth (pp)", period,
                        (value - prior_value) / prior_revenue * 100.0, "pp",
                        formula=f"(member - member prior) / {prior_total_key} prior",
                        inputs=[reg.ref(item["key"], period), reg.ref(item["key"], prior), reg.ref(prior_total_key, prior)])
    # Segment operating margin where segment profit is tagged.
    profit = {(s["axis"], s["member"]): s for s in segments if s["measure"] in ("OperatingIncomeLoss", "SegmentReportingInformationProfitLoss")}
    for item in segments:
        if item["measure"] != "revenue":
            continue
        match = profit.get((item["axis"], item["member"]))
        if not match:
            continue
        for period in periods:
            margin = _ratio(reg.val(match["key"], period), reg.val(item["key"], period))
            if margin is not None:
                reg.add("D", f"segmargin:{item['key']}", f"{item['label']} segment operating margin", period, margin * 100.0, "pct",
                        formula="segment profit / segment revenue", inputs=[reg.ref(match["key"], period), reg.ref(item["key"], period)])


def _window_figures(reg: Registry, periods: list[str]) -> None:
    """Window reference levels (low, high, median) and 3-year CAGRs for 'what to watch' thresholds."""
    for key, label, unit in (
        ("operating_margin", "Operating margin", "pct"), ("net_margin", "Net margin", "pct"),
        ("gross_margin", "Gross margin", "pct"), ("cs:free_cash_flow", "Free cash flow margin", "pct"),
        ("cs:research_and_development", "R&D % of revenue", "pct"), ("fcf_to_ni", "Free cash flow / net income", "x"),
        ("efficiency_ratio", "Efficiency ratio", "pct"), ("current_ratio", "Current ratio", "x"),
        ("loss_ratio", "Loss ratio", "pct"),
    ):
        points = [(p, reg.get(key, p)) for p in periods]
        points = [(p, v) for p, v in points if v is not None]
        if len(points) < 3:
            continue
        low = min(points, key=lambda pv: pv[1].value)
        high = max(points, key=lambda pv: pv[1].value)
        window = f"{points[0][0]}..{points[-1][0]}"
        reg.add("D", f"low:{key}", f"{label} window low ({low[0]})", window, low[1].value, unit,
                formula="minimum over window", inputs=[low[1].id])
        reg.add("D", f"high:{key}", f"{label} window high ({high[0]})", window, high[1].value, unit,
                formula="maximum over window", inputs=[high[1].id])
        reg.add("D", f"median:{key}", f"{label} window median", window, median(v.value for _, v in points), unit,
                formula="median over window", inputs=[v.id for _, v in points])
    for key, label in (("revenue", "Revenue"), ("net_income", "Net income"), ("operating_income", "Operating income"),
                       ("free_cash_flow", "Free cash flow"), ("bank_revenue", "Bank revenue")):
        if len(periods) < 4:
            continue
        end, start = periods[-1], periods[-4]
        cur, base = reg.val(key, end), reg.val(key, start)
        if cur and base and cur > 0 and base > 0:
            reg.add("D", f"cagr3:{key}", f"{label} 3-year CAGR", f"{start}..{end}", ((cur / base) ** (1 / 3) - 1) * 100.0, "pct",
                    formula="(end / start)^(1/3) - 1", inputs=[reg.ref(key, end), reg.ref(key, start)])


def red_flags(reg: Registry, periods: list[str], profile: str, segments: list[dict[str, Any]],
              data_checks: list[dict[str, Any]],
              unmapped: tuple[tuple[str, str, float], ...] | list[tuple[str, str, float]] = ()) -> list[dict[str, Any]]:
    """Candidate red flags with a severity (high / medium / low) and persistence (periods affected). ``unmapped``
    (``unmapped_lines``) names the years whose net cash leaves out a line the filer reports: a net-debt flag over such
    a year quotes no level."""
    flags: list[dict[str, Any]] = []

    def add(kind: str, severity: str, persistence: int, detail: str, evidence: list[Optional[str]]) -> None:
        flags.append({"kind": kind, "severity": severity, "persistence": persistence, "detail": detail,
                      "evidence": [e for e in evidence if e]})

    def series(key: str) -> list[tuple[str, Value]]:
        return [(p, v) for p in periods if (v := reg.get(key, p)) is not None]

    om = series("operating_margin")
    if len(om) >= 3:
        run = 0
        for (_, a), (_, b) in zip(om[:-1], om[1:]):
            run = run + 1 if b.value < a.value else 0
        if run >= 2:
            drop = om[-1 - run][1].value - om[-1][1].value
            add("margin_compression", "high" if drop >= 8 else "medium" if drop >= 3 else "low", run,
                f"Operating margin fell {run} years in a row, {drop:.1f}pp in total.",
                [v.id for _, v in om[-1 - run:]])
    rev = series("revenue") or series("bank_revenue")
    if len(rev) >= 3:
        declines = [p for (p, b), (_, a) in zip(rev[1:], rev[:-1]) if b.value < a.value]
        recent = [p for p in declines if p in periods[-3:]]
        if recent:
            add("revenue_decline", "high" if len(recent) >= 2 else "medium", len(recent),
                f"Revenue declined in {', '.join(recent)}.", [reg.ref("revenue", p) or reg.ref("bank_revenue", p) for p in recent])
    conv = series("fcf_to_ni")
    weak = [(p, v) for p, v in conv if p in periods[-3:] and v.value < 0.8]
    if len(weak) >= 2:
        add("weak_cash_conversion", "medium", len(weak),
            "Free cash flow ran below 80% of net income in " + ", ".join(p for p, _ in weak) + ".", [v.id for _, v in weak])
    for key, kind, label, threshold in (("dso", "receivables_build", "Days sales outstanding", 10.0),
                                        ("dio", "inventory_build", "Days inventory outstanding", 15.0)):
        pts = series(key)
        if len(pts) >= 2 and pts[-1][1].value - pts[-2][1].value >= threshold:
            add(kind, "medium", 1, f"{label} rose {pts[-1][1].value - pts[-2][1].value:.0f} days in {pts[-1][0]}.",
                [pts[-1][1].id, pts[-2][1].id])
    debt = series("total_debt")
    if len(debt) >= 2 and debt[-2][1].value > 0 and (debt[-1][1].value / debt[-2][1].value - 1) > 0.25:
        add("debt_build", "medium", 1, f"Total debt rose {(debt[-1][1].value / debt[-2][1].value - 1) * 100:.0f}% in {debt[-1][0]}.",
            [debt[-1][1].id, debt[-2][1].id])
    cr = series("current_ratio")
    if cr and cr[-1][1].value < 1.0 and profile not in ("bank", "insurer"):
        add("liquidity", "high" if cr[-1][1].value < 0.8 else "medium", 1, f"Current ratio below 1.0x in {cr[-1][0]}.", [cr[-1][1].id])
    runway = series("runway_years")
    if runway and runway[-1][1].value < 3:
        add("runway", "high" if runway[-1][1].value < 1.5 else "medium", 1,
            f"Cash and investments cover {runway[-1][1].value:.1f} years of the latest burn.", [runway[-1][1].id])
    ni = series("net_income")
    losses = 0
    for _, v in reversed(ni):
        if v.value < 0:
            losses += 1
        else:
            break
    if losses >= 2:
        add("persistent_losses", "high" if losses >= 4 else "medium", losses, f"Net loss in each of the last {losses} years.",
            [v.id for _, v in ni[-losses:]])
    sbc = series("cs:stock_based_compensation")
    if sbc and sbc[-1][1].value >= 10:
        run = 0
        for _, v in reversed(sbc):
            if v.value >= 10:
                run += 1
            else:
                break
        add("stock_compensation", "high" if run >= 5 else "medium", run,
            f"Stock-based compensation was {sbc[-1][1].value:.1f}% of revenue in {sbc[-1][0]}, and at least 10% "
            f"in each of the last {run} years.", [v.id for _, v in sbc[-run:]])
    returns = series("returns_to_fcf")
    over = [(p, v) for p, v in returns if p in periods[-3:] and v.value > 100]
    if len(over) >= 2:
        add("returns_exceed_fcf", "medium", len(over),
            "Buybacks and dividends exceeded free cash flow in " + ", ".join(p for p, _ in over) + ".", [v.id for _, v in over])
    net_cash = series("net_cash")
    if len(net_cash) >= 3:
        falls = 0
        for (_, a), (_, b) in zip(net_cash[:-1], net_cash[1:]):
            falls = falls + 1 if b.value < a.value else 0
        if falls >= 2 and net_cash[-1][1].value < 0:
            run = net_cash[-1 - falls:]
            years = {p for p, _ in run}
            omitted = [f"{UNMAPPED[line][1]} omit {UNMAPPED[line][0]}" for line in UNMAPPED
                       if any(key == line and year in years for key, year, _ in unmapped)]
            if all(v.value < 0 for _, v in run) and omitted:
                # A level on a total that leaves a reported line out is wrong by that line: CAT's $26.2bn of FY2025
                # net debt [D456] leaves out $7.1bn of long-term debt due within one year. So no level is quoted, and
                # the omission stands beside the flag that would have quoted it.
                detail = f"Net debt rose {falls} years in a row through {run[-1][0]}; its level is left out, as {' and '.join(omitted)}."
            elif all(v.value < 0 for _, v in run):
                # In net debt throughout: "net cash fell into net debt" reads as a crossing from net cash, and the
                # model then wrote "net debt" with net cash's minus signs (CAT, DUK, NEE; DEEPSEEK-ERRORS.md §1.2).
                detail = f"Net debt rose {falls} years in a row to {_usd_words(-run[-1][1].value)} in {run[-1][0]}."
            else:
                detail = f"Net cash fell {falls} years in a row into net debt in {net_cash[-1][0]}."
            add("net_debt_build", "medium", falls, detail, [v.id for _, v in run])
    for item in segments:
        if (item["measure"] != "revenue" or item.get("subtotal") or item.get("generic")
                or item["kind"] not in ("product", "segment")):
            continue
        shares = series(f"share:{item['key']}")
        growth = series(f"g:{item['key']}")
        if shares and shares[-1][1].value >= 25 and growth and growth[-1][1].value <= -10:
            add("concentration_decline", "high" if growth[-1][1].value <= -25 else "medium", 1,
                f"{item['label']} was {shares[-1][1].value:.0f}% of revenue and fell {abs(growth[-1][1].value):.0f}% in {growth[-1][0]}.",
                [shares[-1][1].id, growth[-1][1].id])
    tax = series("tax_rate")
    if len(tax) >= 2 and abs(tax[-1][1].value - tax[-2][1].value) >= 8:
        add("tax_rate_swing", "low", 1, f"Effective tax rate moved {tax[-1][1].value - tax[-2][1].value:+.1f}pp in {tax[-1][0]}.",
            [tax[-1][1].id, tax[-2][1].id])
    if profile == "bank":
        eff = series("efficiency_ratio")
        if len(eff) >= 2 and eff[-1][1].value - eff[-2][1].value >= 3:
            add("efficiency_deterioration", "medium", 1, f"Efficiency ratio rose {eff[-1][1].value - eff[-2][1].value:.1f}pp in {eff[-1][0]}.",
                [eff[-1][1].id, eff[-2][1].id])
        prov = series("provision_to_revenue")
        if len(prov) >= 2 and prov[-1][1].value - prov[-2][1].value >= 2:
            add("credit_costs", "medium", 1, f"Provision rose to {prov[-1][1].value:.1f}% of revenue in {prov[-1][0]}.",
                [prov[-1][1].id, prov[-2][1].id])
    for check in data_checks:
        add("data_quality", check.get("severity", "medium"), 1, check["detail"], check.get("evidence", []))
    rank = {"high": 0, "medium": 1, "low": 2}
    flags.sort(key=lambda fl: (rank[fl["severity"]], -fl["persistence"]))
    for n, flag in enumerate(flags, start=1):
        flag["id"] = f"R{n}"
    return flags


# Pack version 2 (tasks/analysis-depth-2026-10/DEEPSEEK-ERRORS.md §2, fixes 3, 8 and 9). Everything here that
# registers a value runs after the last version-1 value is registered (peers included), and its red flags number
# after the last version-1 flag, so no version-1 ID moves or changes value and a version-1 output still checks
# against a version-2 pack. ``unmapped_lines`` registers nothing and runs before the red flags, which read it.

def version_two_values(reg: Registry, periods: list[str], profile: str) -> None:
    """The values version 2 adds, each under a new ID."""
    # Fix 3: a typical operating cash flow / net income level. Without one the model borrowed the free-cash-flow
    # median for it (CVX, DE, PG, TGT) or made a range up (DUK). No window high: it comes from years of depressed
    # net income (CVX 9.34x, CAT 7.52x). Banks and insurers are skipped: their operating cash flow moves with
    # funding and trading balances, not earnings quality (JPM would get a 0.19x median).
    points = [(p, v) for p in periods if (v := reg.get("ocf_to_ni", p)) is not None]
    if profile not in ("bank", "insurer") and len(points) >= 3:
        window = f"{points[0][0]}..{points[-1][0]}"
        low = min(points, key=lambda pv: pv[1].value)
        reg.add("D", "low:ocf_to_ni", f"Operating cash flow / net income window low ({low[0]})", window, low[1].value, "x",
                formula="minimum over window", inputs=[low[1].id])
        reg.add("D", "median:ocf_to_ni", "Operating cash flow / net income window median", window,
                median(v.value for _, v in points), "x", formula="median over window", inputs=[v.id for _, v in points])
    # Fix 9: net against operating margin within one year, so the comparison never pairs two years (DE set
    # FY2025 net margin against FY2024 operating margin, the last year its operating-margin row has).
    for period in periods:
        net, operating = reg.get("net_margin", period), reg.get("operating_margin", period)
        if net is not None and operating is not None:
            reg.add("D", "margin_gap:net_minus_operating", "Net margin minus operating margin (pp, same year)", period,
                    net.value - operating.value, "pp", formula="net_margin - operating_margin", inputs=[net.id, operating.id])


_OTHER_DEBT = ("debt_current", "short_term_borrowings")


def _long_term_debt(reg: Registry, period: str) -> Optional[Value]:
    """The long-term line total debt sums: the noncurrent tag, else the metrics table's long-term debt."""
    return reg.get("debt_noncurrent", period) or reg.get("long_term_debt", period)


def debt_breaks(reg: Registry, periods: list[str]) -> list[str]:
    """Years whose long-term debt line is missing or zero while the window reports it in other years, so total
    debt and net cash there sum the other lines only (fix 8): the line stops after COP FY2020, CVX FY2021,
    DE FY2021, KO FY2023 and USB FY2022, is zero in ORCL FY2022 and missing in COP FY2016. Such a year counts only
    while debt is still evident: another debt line is positive, or (after the line was last reported) interest
    expense held at least half its level of that year. A company that repaid its long-term debt is not a break.
    A smaller line's absence alone is not tested here: a current portion or short-term borrowings line comes and
    goes with genuine maturities and repayments (AMD), so its absence says little about the data; ``debt_onsets``
    tests the one shape that does (DE)."""
    lines = {p: _long_term_debt(reg, p) for p in periods}
    reported = [i for i, p in enumerate(periods) if (v := lines[p]) is not None and v.value > 0]
    if not reported:
        return []
    broken = []
    for i, period in enumerate(periods):
        if i in reported:
            continue
        other = any((reg.val(key, period) or 0) > 0 for key in _OTHER_DEBT)
        if i < reported[0]:
            # Before the line first appears: a company that had not borrowed yet has no other debt line either
            # (REGN, SNAP, RIVN); COP's FY2016 has a current portion of long-term debt and no long-term debt.
            if other:
                broken.append(period)
            continue
        anchor = periods[max(j for j in reported if j < i)]
        interest, anchor_interest = reg.val("interest_expense", period), reg.val("interest_expense", anchor)
        if other or (interest and anchor_interest and anchor_interest > 0 and interest >= 0.5 * anchor_interest):
            broken.append(period)
    return broken


ONSET_JUMP = 0.25  # total debt rising more than this as a line first appears (the debt_build flag's threshold)


def debt_onsets(reg: Registry, periods: list[str]) -> list[tuple[str, list[str]]]:
    """(line, the years before it first appears) for a smaller debt line that is not reported in the window's
    early years and is reported in every year from its first to the window's end, where total debt jumps by more
    than ``ONSET_JUMP`` as it appears (the line carrying at least half the rise) while interest expense, that year
    and the next, does not rise by even half as much: the debt was there before, under a tag this pack does not
    map, so total debt and net cash before the onset leave it out. DE's current portion of debt first appears in
    FY2020 at $8,582m (total debt +36.7%, interest expense -15%): its FY2016-FY2019 total debt is long-term only.
    A line that first appears at zero (AMD's and NVDA's) or while total debt falls (SNAP's) is no onset."""
    onsets = []
    for key in _OTHER_DEBT:
        present = [i for i, p in enumerate(periods) if reg.get(key, p) is not None]
        if not present or present[0] == 0 or present != list(range(present[0], len(periods))):
            continue
        first = present[0]
        onset, before = periods[first], periods[first - 1]
        line, debt, prior = reg.val(key, onset), reg.val("total_debt", onset), reg.val("total_debt", before)
        if not (line and line > 0 and debt and prior and prior > 0):
            continue
        jump = debt / prior - 1
        if jump <= ONSET_JUMP or line < 0.5 * (debt - prior):
            continue
        base = reg.val("interest_expense", before)
        after = [reg.val("interest_expense", p) for p in periods[first:first + 2]]
        if not base or base <= 0 or any(v is None or v > base * (1 + jump / 2) for v in after):
            continue
        onsets.append((key, periods[:first]))
    return onsets


_LIQUIDITY = ("cash_and_equivalents", "short_term_investments", "long_term_investments")
GAP_SHARE = 0.10  # a missing line's neighbours must carry at least this share of their year's cash and investments


def liquidity_gaps(reg: Registry, periods: list[str]) -> list[tuple[str, str]]:
    """(line, year) for a cash or investment line reported in most years of the window but missing in one, where
    the year on each side reports it at ``GAP_SHARE`` or more of that year's cash and investments: cash and
    investments that year sum the other lines only. MSFT's short-term investments are missing in FY2017 ($121.8bn
    in FY2018), NVDA's in FY2026, ORCL's in FY2017, COP's in FY2021. A line missing beside a year that reports it
    at zero or near it (AMD's FY2016 short-term investments, $0.0m in FY2017) is no gap, nor is a run of missing
    years: a line that starts or stops may be genuine (VRTX's long-term investments begin in FY2022)."""
    gaps = []
    for key in _LIQUIDITY:
        if sum(reg.get(key, p) is not None for p in periods) * 2 <= len(periods):
            continue
        for i, period in enumerate(periods):
            if reg.get(key, period) is not None or reg.get("liquidity", period) is None:
                continue
            sides = [periods[j] for j in (i - 1, i + 1) if 0 <= j < len(periods)]
            if all(reg.get(key, p) is not None and (total := reg.val("liquidity", p))
                   and (reg.val(key, p) or 0) >= GAP_SHARE * total for p in sides):
                gaps.append((key, period))
    return gaps


def double_counted(reg: Registry, periods: list[str], combined: dict[str, float]) -> list[str]:
    """Years whose short-term investments are already inside cash and cash equivalents, so cash and investments
    count them twice: the filer's own cash, cash equivalents and short-term investments total (``combined``,
    us-gaap CashCashEquivalentsAndShortTermInvestments by period) equals cash alone within 0.5%, while short-term
    investments are more than 1% of cash. TGT tags that total at its cash figure in every year ($5,488m in FY2025,
    beside $4,611m of short-term investments); the filers that tag it at cash plus short-term investments (MSFT,
    GOOGL, ADBE) are not double counts."""
    years = []
    for period in periods:
        cash, investments, total = (reg.val("cash_and_equivalents", period), reg.val("short_term_investments", period),
                                    combined.get(period))
        if (cash and cash > 0 and investments and investments > 0.01 * cash and total is not None
                and reg.get("liquidity", period) is not None and abs(total - cash) <= 0.005 * cash):
            years.append(period)
    return years


UNMAPPED_LINE_SHARE = 0.10  # an unmapped line counts at this share or more of the total it is missing from
# A line the filer reports that this pack maps nowhere (``unmapped_lines``): what it is, and the totals that omit it.
# The one wording of the omission, for its data check and for the net-debt red flag that quotes no level beside it.
UNMAPPED = {"debt_current": ("long-term debt due within one year", "total debt and net cash"),
            "short_term_investments": ("a short-term investment line", "cash and investments and net cash")}


def unmapped_lines(reg: Registry, periods: list[str], due: dict[str, float],
                   combined: dict[str, float]) -> list[tuple[str, str, float]]:
    """(line, year, amount) for a line the filer reports and this pack sums nowhere, at ``UNMAPPED_LINE_SHARE`` or more
    of the total it is missing from, in a year no break check names already (fix 8). Each test reads a figure the
    filer reports itself, against the lines the pack sums; a break test cannot see such a line, as the pack's own
    basis stays the same in every year:

    - ``debt_current``: long-term debt maturing within one year (``due``: us-gaap
      LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths by period) while total debt sums no current-debt
      line and its long-term line is a noncurrent tag, which leaves the current portion out by definition. CAT's
      balance sheet shows "Long-term debt due within one year" of $7,120m at FY2025 under no tag the pack maps, and its
      maturities within twelve months are the same $7,120m; its total debt [D455] is $30,696m of noncurrent long-term
      debt plus $5,514m of short-term borrowings. A long-term line tagged LongTermDebt is not tested: that tag holds the
      current portion for DUK (FY2016 $47.9bn: $45.6bn noncurrent plus $2.3bn current) and not for TGT (FY2025
      $14.4bn, with the $2,130m current portion its 10-K shows beside it in no line of the pack).
    - ``short_term_investments``: the filer's own cash, cash equivalents and short-term investments total (``combined``)
      above the pack's cash plus short-term investments. The amount is a floor on what is left out: KO's FY2016 total
      of $18,150m exceeds $8,555m of cash and $4,051m of marketable securities by $5,544m, while its $9,595m of
      short-term investments are left out, the marketable securities sitting outside its total. A filer that tags no
      such total (PG) is not tested: an investment tag alone cannot tell liquidity from restricted holdings (DUK's
      available-for-sale securities sit mostly in its nuclear decommissioning trusts) nor from cash equivalents (NVDA's
      FY2018 $6.9bn of available-for-sale securities are its $3.1bn of marketable securities and $3.8bn of cash
      equivalents).

    Nothing is withheld: the pack keeps every figure, and its data check names the omission (``unmapped_checks``). A
    bank or insurer has neither total debt nor cash and investments, so neither test reads it."""
    debt_named = set(debt_breaks(reg, periods)) | {p for _, years in debt_onsets(reg, periods) for p in years}
    cash_named = {p for _, p in liquidity_gaps(reg, periods)} | set(double_counted(reg, periods, combined))
    found: list[tuple[str, str, float]] = []
    for period in periods:
        line, total, amount = _long_term_debt(reg, period), reg.val("total_debt", period), due.get(period)
        if (period not in debt_named and reg.get("debt_current", period) is None and line is not None and line.value > 0
                and line.formula.endswith("Noncurrent") and total and amount and amount >= UNMAPPED_LINE_SHARE * total):
            found.append(("debt_current", period, amount))
    for period in periods:
        liquidity, own = reg.val("liquidity", period), combined.get(period)
        if period in cash_named or not liquidity or own is None:
            continue
        short = own - (reg.val("cash_and_equivalents", period) or 0.0) - (reg.val("short_term_investments", period) or 0.0)
        if short >= UNMAPPED_LINE_SHARE * liquidity:
            found.append(("short_term_investments", period, short))
    return found


def _amounts(points: list[tuple[str, float]]) -> str:
    """"$5.5 billion in FY2016 and $3.9 billion in FY2017", or for a longer span "from $1.0 billion to $3.6 billion a
    year, $3.6 billion in FY2025"."""
    if len(points) <= 2:
        return " and ".join(f"{_usd_words(amount)} in {year}" for year, amount in points)
    low, high = min(a for _, a in points), max(a for _, a in points)
    return f"from {_usd_words(low)} to {_usd_words(high)} a year, {_usd_words(points[-1][1])} in {points[-1][0]}"


def unmapped_checks(reg: Registry, periods: list[str], found: tuple[tuple[str, str, float], ...] | list[tuple[str, str, float]]
                    ) -> list[dict[str, Any]]:
    """Data checks of kind ``unmapped_line``, one for each span of years ``unmapped_lines`` found a line in, with the
    amounts the filer reports. The evidence is the span's last year's lines and total, none of them withheld."""
    checks: list[dict[str, Any]] = []
    for line, (what, totals) in UNMAPPED.items():
        amounts = {year: amount for key, year, amount in found if key == line}
        for span in _spans(periods, list(amounts)):
            where, then = _where(periods, span)
            figures = _amounts([(year, amounts[year]) for year in span])
            if line == "debt_current":
                detail = (f"Long-term debt due within one year is in no line of this pack {where}: the filer reports "
                          f"{figures}, beside the noncurrent long-term debt this pack sums, so {totals} {then} omit it.")
                keys = ("debt_noncurrent", "total_debt")
            else:
                detail = (f"Cash and short-term investments in this pack fall short of the filer's own cash, cash "
                          f"equivalents and short-term investments total {where} ({figures}): {what} this pack does not "
                          f"map, so {totals} {then} omit it.")
                keys = ("cash_and_equivalents", "short_term_investments", "liquidity")
            checks.append({"kind": "unmapped_line", "severity": "high", "period": ",".join(span), "detail": detail,
                           "evidence": [vid for key in keys if (vid := reg.ref(key, span[-1]))]})
    return checks


UNMAPPED_SHARE = 0.10  # debt the interest implies, against the peer's cash and investments (fix 8 for peers)


def peer_left_out(reg: Registry, periods: list[str], period: str, combined: Optional[dict[str, float]] = None) -> Optional[str]:
    """Why a peer's net cash for ``period`` (its comparable year) stays out of a version-2 peer median and rank, else
    None. ``reg`` holds the peer's own window, as its pack would, and every test of its pack runs on it: a debt break
    or onset ("debt line broken"), a liquidity gap or double count ("cash line broken"). A peer has no data check to
    disclose a doubt, so one more test leaves it out: no long-term debt line that year while the window shows
    borrowing, as another debt line in any year or interest expense implying, at ``IMPLIED_RATE_CEILING``, debt of
    ``UNMAPPED_SHARE`` or more of its cash and investments ("no long-term debt line"). Each was a broken value in a
    version-1 peer median: KO, KMB and MDLZ (staples), DE (industrials), CVX and COP, MPC and PSX (energy), SO
    (utilities), DG and TGT (retail), F and GM (autos; GM's interest implies $37bn of debt it maps no line for), NVDA's
    FY2026 (semis). A peer that never borrowed (PINS, RDDT, TTD, VRTX: interest implying at most 5% of its cash) stays
    in."""
    if period in debt_breaks(reg, periods) or any(period in years for _, years in debt_onsets(reg, periods)):
        return "debt line broken"
    if period in {p for _, p in liquidity_gaps(reg, periods)} or period in double_counted(reg, periods, combined or {}):
        return "cash line broken"
    line = _long_term_debt(reg, period)
    if line is not None and line.value > 0:
        return None
    lines = any((reg.val(key, p) or 0) > 0 for p in periods for key in ("debt_noncurrent", "long_term_debt", *_OTHER_DEBT))
    interest = max((reg.val("interest_expense", p) or 0.0) for p in periods)
    liquidity = reg.val("liquidity", period) or 0.0
    if lines or (interest > 0 and interest / (IMPLIED_RATE_CEILING / 100.0) >= UNMAPPED_SHARE * liquidity):
        return "no long-term debt line"
    return None


def _spans(periods: list[str], years: list[str]) -> list[list[str]]:
    spans: list[list[str]] = []
    for period in periods:
        if period not in years:
            continue
        if spans and periods.index(spans[-1][-1]) == periods.index(period) - 1:
            spans[-1].append(period)
        else:
            spans.append([period])
    return spans


IMPLIED_RATE_CEILING = 12.0  # % a year: interest above this is more than the debt the pack sums could carry


def _left_out(reg: Registry, periods: list[str], span: list[str], growth: str) -> str:
    """What a check's span takes with it, as the render withholds it. The runway is named only where the span has
    one, and the net-cash peer rank, which compares the latest year only, only where the span holds that year and
    the pack has the rank (ORCL's FY2022 break leaves its FY2026 rank in place)."""
    built = ["net cash % of revenue", growth]
    if growth.startswith("cash") and any(reg.ref("runway_years", p) for p in span):
        built.append("years of burn covered")
    if periods[-1] in span and reg.ref("peer_pctile:net_cash_to_revenue", periods[-1]):
        built.append("the net-cash peer rank")
    return f"so this pack leaves them out, with the values built on them ({', '.join(built)})."


def _where(periods: list[str], span: list[str]) -> tuple[str, str]:
    """("after FY2021", "after that") for a span that runs to the window's end, ("before FY2017", "before that") for
    one that starts it, else ("in FY2022", "in that year") or ("in FY2016-FY2025", "in those years")."""
    first, last = periods.index(span[0]), periods.index(span[-1])
    before = periods[first - 1] if first else None
    after = periods[last + 1] if last + 1 < len(periods) else None
    if before and not after:
        return f"after {before}", "after that"
    if after and not before:
        return f"before {after}", "before that"
    if len(span) == 1:
        return f"in {span[0]}", "in that year"
    return f"in {span[0]}-{span[-1]}", "in those years"


def debt_checks(reg: Registry, periods: list[str], profile: str, broken: list[str],
                onsets: tuple[tuple[str, list[str]], ...] | list[tuple[str, list[str]]] = (),
                gaps: tuple[tuple[str, str], ...] | list[tuple[str, str]] = (),
                double: tuple[str, ...] | list[str] = ()) -> list[dict[str, Any]]:
    """Data checks for fix 8: one naming each span of years whose long-term debt line is broken (``broken``), each
    debt line's onset (``onsets``, kind ``debt_break`` too), each liquidity gap (``gaps``) and the years whose
    short-term investments sit inside cash (``double``), both kind ``liquidity_break``, then the
    implied-interest-rate test.

    The rate test (interest expense over average total debt, the year-end balance alone where the prior year is
    missing or broken) runs outside the debt-break spans, where it would only repeat them (COP, CVX, DE and KO
    exceed 12% there): it is the backstop for a debt line this pack does not map at all."""
    checks: list[dict[str, Any]] = []
    summed = profile not in ("bank", "insurer")  # banks and insurers carry no total debt or net cash
    for span in _spans(periods, broken):
        lines = [_long_term_debt(reg, p) for p in span]
        state = "reported as zero" if all(v is not None for v in lines) else "not reported"
        where, then = _where(periods, span)
        detail = f"Long-term debt {state} {where}"
        if summed:
            detail += (f"; total debt and net cash {then} omit it, "
                       + _left_out(reg, periods, span, "debt growth across the break"))
        else:
            detail += "."
        first, last = periods.index(span[0]), periods.index(span[-1])
        sides = [periods[j] for j in (first - 1, last + 1) if 0 <= j < len(periods)]
        # The years the line was reported on either side; a zero line inside the span is withheld, not evidence.
        evidence = [v.id for p in sides if (v := _long_term_debt(reg, p))]
        checks.append({"kind": "debt_break", "severity": "high", "period": ",".join(span), "detail": detail,
                       "evidence": evidence})
    if summed:
        for key, years in onsets:
            onset = periods[periods.index(years[-1]) + 1]
            label = X_LABELS.get(key, key.replace("_", " "))
            detail = (f"{label} not reported before {onset}, when total debt jumps as it first appears and interest "
                      "expense does not; total debt and net cash before that omit it, "
                      + _left_out(reg, periods, years, "debt growth across the break"))
            evidence = [vid for vid in (reg.ref(key, onset), reg.ref("interest_expense", years[-1]),
                                        reg.ref("interest_expense", onset)) if vid]
            checks.append({"kind": "debt_break", "severity": "high", "period": ",".join(years), "detail": detail,
                           "evidence": evidence})
        for key, year in gaps:
            label = X_LABELS.get(key, key.replace("_", " "))
            i = periods.index(year)
            sides = [periods[j] for j in (i - 1, i + 1) if 0 <= j < len(periods)]
            detail = (f"{label} not reported in {year}, though reported in {' and '.join(sides)}; cash and investments "
                      "and net cash in that year omit them, "
                      + _left_out(reg, periods, [year], "cash and investments growth across the gap"))
            checks.append({"kind": "liquidity_break", "severity": "high", "period": year, "detail": detail,
                           "evidence": [vid for p in sides if (vid := reg.ref(key, p))]})
        for span in _spans(periods, list(double)):
            where = f"in {span[0]}" if len(span) == 1 else f"in {span[0]}-{span[-1]}"
            detail = (f"Short-term investments are already inside cash and cash equivalents {where} (the filing tags "
                      "cash, cash equivalents and short-term investments together at the cash figure); cash and "
                      "investments and net cash there count them twice, "
                      + _left_out(reg, periods, span, "cash and investments growth"))
            evidence = [vid for vid in (reg.ref("cash_and_equivalents", span[-1]), reg.ref("short_term_investments", span[-1]))
                        if vid]
            checks.append({"kind": "liquidity_break", "severity": "high", "period": ",".join(span), "detail": detail,
                           "evidence": evidence})
        rates = []
        skip = set(broken) | {p for _, years in onsets for p in years}
        for i, period in enumerate(periods):
            debt, interest = reg.get("total_debt", period), reg.get("interest_expense", period)
            if period in skip or debt is None or interest is None or debt.value <= 0 or interest.value <= 0:
                continue
            prior = reg.get("total_debt", periods[i - 1]) if i and periods[i - 1] not in skip else None
            base = [debt] + ([prior] if prior is not None and prior.value > 0 else [])
            rate = interest.value / (sum(v.value for v in base) / len(base)) * 100.0
            if rate > IMPLIED_RATE_CEILING:
                rates.append((period, rate, [interest.id, *(v.id for v in base)]))
        if rates:
            listing = ", ".join(f"{rate:.1f}% in {period}" for period, rate, _ in rates)
            checks.append({
                "kind": "implied_interest_rate", "severity": "medium", "period": ",".join(p for p, _, _ in rates),
                "detail": (f"Interest expense over average total debt was {listing}, above about {IMPLIED_RATE_CEILING:.0f}%: "
                           "total debt there may omit a borrowing line; check it before stating total debt or net cash."),
                "evidence": [vid for _, _, ids in rates for vid in ids],
            })
    return checks


def append_flags(flags: list[dict[str, Any]], checks: list[dict[str, Any]]) -> None:
    """Version 2's data checks as red-flag candidates, numbered after the last version-1 flag. The list is not
    re-sorted (that would renumber version-1 flags); the render orders flags by severity for reading."""
    for n, check in enumerate(checks, start=len(flags) + 1):
        flags.append({"kind": "data_quality", "severity": check.get("severity", "medium"), "persistence": 1,
                      "detail": check["detail"], "evidence": check.get("evidence", []), "id": f"R{n}"})


def _built_on(reg: Registry, seeds: set[str]) -> set[str]:
    """``seeds`` and every value built on them, through inputs; a peer median goes with its peer rank."""
    tainted = set(seeds)
    grew = True
    while grew:
        grew = False
        for vid, value in reg.values.items():
            if vid not in tainted and tainted.intersection(value.inputs):
                tainted.add(vid)
                grew = True
    for (key, period), vid in reg.by_key.items():
        if key.startswith("peer_median:") and reg.ref("peer_pctile:" + key.split(":", 1)[1], period) in tainted:
            tainted.add(vid)
    return tainted


def withheld(reg: Registry, broken: list[str], flags: list[dict[str, Any]], short: tuple[str, ...] | list[str] = (),
             replaced: Optional[dict[str, str]] = None) -> dict[str, str]:
    """IDs the render leaves out, each with its reason: ``debt_break`` for what is built on a broken debt year
    (``broken``: a long-term line's break or a line's onset), ``liquidity_break`` for what is built on a year whose
    cash and investments are broken (``short``: a gap or a double count), and ``replaced``'s own reason for a
    version-1 value a checked one replaces (a peer rank or median built on a peer's broken year, ``peer_break``).

    Withheld rather than labelled: a label leaves a broken figure for the model to state, and in eval-v1 DeepSeek
    stated COP's, CVX's and KO's net cash as fact and read DE's dropped line as deleveraging (Sonnet, given the same
    packs, caught 4 of 6 breaks). The IDs stay in the pack, so a version-1 output citing one still checks. Seeds are
    total debt and net cash of each broken debt year (net cash too, as it is cash alone when no debt line is left), a
    long-term line reported as zero there (ORCL's FY2022 long-term debt of $0.0m [F185, X213], which reads as debt
    repaid), and cash and investments and net cash of each broken liquidity year; the rest follows every value's inputs
    (net cash % of revenue, growth across the break, runway, the net-cash peer rank) and every red flag's evidence. A
    peer median goes with its withheld peer rank: alone, it invites a comparison with a level the pack no longer shows.
    A positive long-term line of a broken year stays (DE's FY2016-FY2019 onset span: the line is right, the total
    lacks another)."""
    zero = {v.id for period in broken for key in ("debt_noncurrent", "long_term_debt")
            if (v := reg.get(key, period)) is not None and v.value <= 0}
    debt = _built_on(reg, zero | {vid for period in broken for key in ("total_debt", "net_cash") if (vid := reg.ref(key, period))})
    cash = _built_on(reg, {vid for period in short for key in ("liquidity", "net_cash") if (vid := reg.ref(key, period))}) - debt
    reasons = {**{vid: "debt_break" for vid in debt}, **{vid: "liquidity_break" for vid in cash}}
    for vid, reason in (replaced or {}).items():
        reasons.setdefault(vid, reason)
    out = {vid: reasons[vid] for vid in sorted(reasons, key=lambda v: (v[0], int(v[1:])))}
    for flag in flags:
        hit = [reasons[vid] for vid in flag["evidence"] if vid in reasons]
        if hit:
            out[flag["id"]] = hit[0]
    return out


def percentile_rank(value: float, peers: list[float]) -> float:
    """Share of peers strictly below ``value`` plus half the ties, as a 0-100 percentile."""
    if not peers:
        return 50.0
    below = sum(1 for p in peers if p < value)
    ties = sum(1 for p in peers if p == value)
    return (below + 0.5 * ties) / len(peers) * 100.0
