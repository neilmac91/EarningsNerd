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
            note: str = "", fixed_id: Optional[str] = None) -> Optional[str]:
        if value is None:
            return None
        if fixed_id is None:
            self._counters[prefix] = self._counters.get(prefix, 0) + 1
            vid = f"{prefix}{self._counters[prefix]}"
        else:
            vid = fixed_id
        self.values[vid] = Value(vid, label, period, float(value), unit, formula, list(inputs or []), source, note)
        self.by_key[(key, period)] = vid
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
              data_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Candidate red flags with a severity (high / medium / low) and persistence (periods affected)."""
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
            if all(v.value < 0 for _, v in run):
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


# Pack version 2 (tasks/analysis-depth-2026-10/DEEPSEEK-ERRORS.md §2, fixes 3, 8 and 9). Everything here runs
# after the last version-1 value is registered (peers included) and numbers its red flags after the last
# version-1 flag, so no version-1 ID moves or changes value and a version-1 output still checks against a
# version-2 pack.

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
    Changes in the smaller lines are not tested: a current portion or short-term borrowings line comes and goes
    with genuine maturities and repayments (AMD), so its absence says little about the data."""
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


def debt_checks(reg: Registry, periods: list[str], profile: str, broken: list[str]) -> list[dict[str, Any]]:
    """Data checks for fix 8: one naming each span of broken years, and the implied-interest-rate test.

    The rate test (interest expense over average total debt, the year-end balance alone where the prior year is
    missing or broken) runs outside the broken spans, where it would only repeat them (COP, CVX, DE and KO
    exceed 12% there): it is the backstop for a debt line this pack does not map at all."""
    checks: list[dict[str, Any]] = []
    summed = profile not in ("bank", "insurer")  # banks and insurers carry no total debt or net cash
    for span in _spans(periods, broken):
        first, last = periods.index(span[0]), periods.index(span[-1])
        before = periods[first - 1] if first else None
        after = periods[last + 1] if last + 1 < len(periods) else None
        lines = [_long_term_debt(reg, p) for p in span]
        state = "reported as zero" if all(v is not None for v in lines) else "not reported"
        if before and not after:
            where, then = f"after {before}", "after that"
        elif after and not before:
            where, then = f"before {after}", "before that"
        else:
            where = f"in {span[0]}" if len(span) == 1 else f"in {span[0]}-{span[-1]}"
            then = "in that year" if len(span) == 1 else "in those years"
        detail = f"Long-term debt {state} {where}"
        if summed:
            detail += (f"; total debt and net cash {then} omit it, so this pack leaves them out, with the values built on "
                       "them (net cash % of revenue, debt growth across the break, the net-cash peer rank).")
        else:
            detail += "."
        evidence = [v.id for p in (before, after) if p and (v := _long_term_debt(reg, p))] + [v.id for v in lines if v]
        checks.append({"kind": "debt_break", "severity": "high", "period": ",".join(span), "detail": detail,
                       "evidence": evidence})
    if summed:
        rates = []
        for i, period in enumerate(periods):
            debt, interest = reg.get("total_debt", period), reg.get("interest_expense", period)
            if period in broken or debt is None or interest is None or debt.value <= 0 or interest.value <= 0:
                continue
            prior = reg.get("total_debt", periods[i - 1]) if i and periods[i - 1] not in broken else None
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


def withheld(reg: Registry, broken: list[str], flags: list[dict[str, Any]]) -> dict[str, str]:
    """IDs the render leaves out because they are built on a broken debt year (fix 8), each with its reason.

    Withheld rather than labelled: a label leaves a broken figure for the model to state, and in eval-v1 DeepSeek
    stated COP's, CVX's and KO's net cash as fact and read DE's dropped line as deleveraging (Sonnet, given the same
    packs, caught 4 of 6 breaks). The IDs stay in the pack, so a version-1 output citing one still checks. Seeds are total
    debt and net cash of each broken year (net cash too, as it is cash alone when no debt line is left); the rest
    follows every value's inputs (net cash % of revenue, debt growth across the break, the net-cash peer rank) and
    every red flag's evidence. A peer median goes with its withheld peer rank: alone, it invites a comparison
    with a level the pack no longer shows."""
    tainted = {vid for period in broken for key in ("total_debt", "net_cash") if (vid := reg.ref(key, period))}
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
    out = {vid: "debt_break" for vid in sorted(tainted, key=lambda v: (v[0], int(v[1:])))}
    for flag in flags:
        if tainted.intersection(flag["evidence"]):
            out[flag["id"]] = "debt_break"
    return out


def percentile_rank(value: float, peers: list[float]) -> float:
    """Share of peers strictly below ``value`` plus half the ties, as a 0-100 percentile."""
    if not peers:
        return 50.0
    below = sum(1 for p in peers if p < value)
    ties = sum(1 for p in peers if p == value)
    return (below + 0.5 * ties) / len(peers) * 100.0
