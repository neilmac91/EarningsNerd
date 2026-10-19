"""The AI-timeout fallback labels money in the filer's reporting currency, by the primary path's rule.

``generate_xbrl_summary`` is the summary the pipeline persists when the AI step times out. Standardized
XBRL values are in the filer's reporting currency, so a hardcoded "$" turned a CNY filer's
CNY 941.2B revenue into "$941.2B" (about 7x too large), and the read path then matched the number
and served it as SEC-verified. The primary path's deterministic filler (``ai/markdown_render.py``)
already labelled these figures "CNY 941.2B"; both producers now share one rule, and the parity test
below fails if either drifts from the other. The prior-period backfill both paths run before storing
(``schemas/summary.py`` ``attach_normalized_facts``) writes the same cells and uses the same rule.
"""
import ast
import copy
import inspect
import json
import symtable
from types import SimpleNamespace

import pytest

from app.schemas import summary as summary_schema
from app.schemas.summary import attach_normalized_facts
from app.services import fallback_summary
from app.services.ai import markdown_render
from app.services.fallback_summary import generate_xbrl_summary
from app.services.openai_service import openai_service
from app.services.provenance_service import build_metric_source
from app.services.summary_pipeline import _finalize_summary_projection
from app.utils.numbers import money_prefix_for


def _metrics(currency=None, **extra):
    metrics = {
        "revenue": {"current": {"value": 941_168_000_000.0, "period": "2025-03-31"},
                    "prior": {"value": 868_687_000_000.0, "period": "2024-03-31"}},
        "net_income": {"current": {"value": 12_480_000.0, "period": "2025-03-31"},
                       "prior": {"value": 950_000.0, "period": "2024-03-31"}},
        "earnings_per_share": {"current": {"value": 6.42, "period": "2025-03-31"},
                               "prior": {"value": -0.5, "period": "2024-03-31"}},
        **extra,
    }
    if currency is not None:
        metrics["reporting_currency"] = currency
    return metrics


def _table(out):
    return [(r["metric"], r["current_period"], r["prior_period"]) for r in out["financial_highlights"]["table"]]


def test_a_cny_filer_reads_in_cny_and_never_in_dollars():
    out = generate_xbrl_summary(_metrics("CNY"), "Example FPI Ltd", filing_type="20-F")

    assert "- **Revenue**: CNY 941.2B (Period: 2025-03-31)" in out["business_overview"]
    assert "- **Net Income**: CNY 12.5M (Period: 2025-03-31)" in out["business_overview"]
    assert _table(out) == [
        ("Revenue", "CNY 941.2B", "CNY 868.7B"),
        ("Net Income", "CNY 12.5M", "CNY 950,000"),
        ("EPS (Basic)", "CNY 6.42", "CNY -0.50"),
    ]
    # The v2 table is the same object, and no "$" anywhere in the fallback's payload (what the
    # pipeline then stores is pinned by the projection test below).
    assert out["raw_summary"]["sections"]["results_that_matter"] is out["financial_highlights"]
    assert "$" not in json.dumps(out)


def test_a_eur_filer_eps_cells_carry_no_dollar_sign():
    out = generate_xbrl_summary(_metrics("EUR"), "Example SE", filing_type="20-F")

    eps_row = out["financial_highlights"]["table"][-1]
    assert (eps_row["metric"], eps_row["current_period"], eps_row["prior_period"]) == (
        "EPS (Basic)", "EUR 6.42", "EUR -0.50")
    assert "$" not in json.dumps(out)


USD_OVERVIEW = (
    "## Example Ltd 10-K Summary\n\n### Financial Snapshot (XBRL)\n"
    "- **Revenue**: $941.2B (Period: 2025-03-31)\n"
    "- **Net Income**: $12.5M (Period: 2025-03-31)\n"
    "- **EPS**: 6.42 (Period: 2025-03-31)\n\n"
    "_Click 'Regenerate Analysis' for the full AI-powered insights._"
)


@pytest.mark.parametrize("currency", [None, "USD", "usd"])
def test_usd_and_unlabelled_filers_keep_the_dollar_output_unchanged(currency):
    out = generate_xbrl_summary(_metrics(currency), "Example Ltd", "2025-06-01", filing_type="10-K")

    # Pinned from main before the fix: a domestic filer's fallback is byte-identical.
    assert out["business_overview"] == USD_OVERVIEW
    assert _table(out) == [
        ("Revenue", "$941.2B", "$868.7B"),
        ("Net Income", "$12.5M", "$950,000"),
        ("EPS (Basic)", "$6.42", "$-0.50"),
    ]
    unlabelled = generate_xbrl_summary(_metrics(), "Example Ltd", "2025-06-01", filing_type="10-K")
    assert out == unlabelled


@pytest.mark.parametrize("currency", [None, "USD", "usd", "EUR", "CNY", "jpy"])
def test_the_fallback_labels_money_by_the_primary_path_rule(currency):
    """Rule 12 gate: one money-label rule for both producers of a summary's P&L figures."""
    metrics = _metrics(currency)
    sections: dict = {}
    openai_service._apply_structured_fallbacks(sections, {"company_name": "X"}, copy.deepcopy(metrics))
    primary = {r["metric"].lower(): (r["current_period"], r["prior_period"])
               for r in sections["results_that_matter"]["table"]}

    fallback = generate_xbrl_summary(metrics, "X", filing_type="20-F")
    revenue = fallback["financial_highlights"]["table"][0]

    assert (revenue["current_period"], revenue["prior_period"]) == primary["revenue"]


@pytest.mark.parametrize("currency,stored_prior", [(None, "$0"), ("EUR", "EUR 0")])
def test_the_stored_fallback_backfills_a_zero_prior_in_the_filer_currency(currency, stored_prior):
    """What the pipeline stores is ``_finalize_summary_projection``'s output, not the fallback's: its
    prior-period backfill refills the fallback's "—" for a zero prior from XBRL. A domestic filer's
    "$0" is unchanged."""
    metrics = _metrics(currency)
    metrics["revenue"]["prior"]["value"] = 0.0
    payload = generate_xbrl_summary(metrics, "Example SE", filing_type="20-F")
    assert payload["financial_highlights"]["table"][0]["prior_period"] == "—"

    _, raw_summary, _, _ = _finalize_summary_projection(payload, metrics, payload["status"])

    table = raw_summary["sections"]["results_that_matter"]["table"]
    assert (table[0]["metric"], table[0]["prior_period"]) == ("Revenue", stored_prior)
    if currency is not None:
        assert "$" not in json.dumps(table)


@pytest.mark.parametrize("currency", ["EUR", "AED", "SAR", "ILS"])
def test_the_stored_fallback_keeps_its_change_figure_in_any_reporting_currency(currency):
    """The stored fallback's revenue change, for a code the display parser read before (EUR) and
    for codes it did not: an AED, SAR or ILS row stored no change figure before the full list."""
    metrics = _metrics(currency)
    payload = generate_xbrl_summary(metrics, "Example", filing_type="20-F")

    _, raw_summary, _, _ = _finalize_summary_projection(payload, metrics, payload["status"])

    revenue = raw_summary["sections"]["results_that_matter"]["table"][0]
    assert (revenue["current_period"], revenue.get("change_display")) == (f"{currency} 941.2B", "+8.3%")


def test_the_primary_path_backfill_labels_a_blank_prior_in_the_filer_currency():
    """The same backfill runs on the primary path when the model leaves a prior cell blank; a CNY
    filer's prior revenue must not come back as "$868,687,000,000" (about 7x too large)."""
    metrics = _metrics("CNY", eps_diluted={"current": {"value": 6.40, "period": "2025-03-31"},
                                           "prior": {"value": -0.5, "period": "2024-03-31"}})
    section = {"table": [
        {"metric": "Revenue", "current_period": "CNY 941.2B", "prior_period": "—"},
        {"metric": "Diluted EPS", "current_period": "CNY 6.40", "prior_period": ""},
    ]}

    out = attach_normalized_facts(section, metrics)

    assert [r["prior_period"] for r in out["table"]] == ["CNY 868,687,000,000", "CNY -0.50"]


def test_the_read_path_verifies_the_relabelled_figure():
    """GET /api/summaries/filing/{id} matches the number only; the verified chip now sits on a figure
    whose label is the filer's own currency."""
    metrics = _metrics("CNY")
    row = generate_xbrl_summary(metrics, "Example FPI Ltd", filing_type="20-F")["financial_highlights"]["table"][0]
    filing = SimpleNamespace(document_url="https://www.sec.gov/Archives/edgar/data/1/000000000025000001/",
                             sec_url=None)

    source = build_metric_source(row, filing, metrics, "Standardized XBRL financial data")

    assert row["current_period"] == "CNY 941.2B"
    assert source["source_verified"] is True


def _function(module, name):
    """The one ``def`` named ``name`` in ``module``'s source (a method or a nested def included)."""
    defs = [n for n in ast.walk(ast.parse(inspect.getsource(module)))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    assert len(defs) == 1, f"{module.__name__} defines {len(defs)} functions named {name}"
    return defs[0]


def _scopes(table):
    """``table`` and every scope nested in it (defs, lambdas, comprehensions)."""
    yield table
    for child in table.get_children():
        yield from _scopes(child)


@pytest.mark.parametrize("module,writer,formatters", [
    (markdown_render, "_apply_structured_fallbacks", ()),
    (fallback_summary, "generate_xbrl_summary", ("format_currency",)),
    (summary_schema, "attach_normalized_facts", ("_format_xbrl_value",)),
])
def test_every_writer_takes_its_money_label_from_the_shared_helper(module, writer, formatters):
    """Rule 12 gate on the source: the output tests above pass a pasted copy of the rule, so each writer
    must call the shared ``money_prefix_for``, and neither it nor its formatters may carry a "$"-led or
    "USD" literal. The call must reach the module's import: no scope in the writer binds the name itself
    (an assignment, a parameter, a nested def, an import, ``global``), as Python's own symbol table
    resolves it. A new writer, or a new helper one of these calls, is review-checked."""
    fn = _function(module, writer)
    assert getattr(module, "money_prefix_for", None) is money_prefix_for, (
        f"{module.__name__}.money_prefix_for is not the shared helper")
    called = {n.func.id for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "money_prefix_for" in called, f"{writer} does not call money_prefix_for"
    [table] = [t for t in _scopes(symtable.symtable(inspect.getsource(module), module.__file__, "exec"))
               if t.get_type() == "function" and t.get_name() == writer]
    for scope in _scopes(table):
        if "money_prefix_for" in scope.get_identifiers():
            name = scope.lookup("money_prefix_for")
            assert name.is_global() and not name.is_declared_global(), (
                f"{scope.get_name()} binds money_prefix_for itself, so its call may not reach the shared helper")
    for node in [fn, *(_function(module, f) for f in formatters)]:
        literals = [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        copies = [s for s in literals if s.strip().upper() == "USD" or s.startswith("$")]
        assert not copies, f"{node.name} carries its own money-label rule: {copies}"
