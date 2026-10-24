"""Rule-12 guard for F61 call (1): a summary figure reads "Matches filing" only in the filed fact's own currency.

#1530 (D-058) made the figure check read a figure's currency (``provenance_service._shows_filed_value``): a figure
labelled in another currency than the filed fact's is a mismatch, and a bare "¥" names JPY or CNY, so it is compared
by its number against either and is a mismatch against any other. This matrix pins that rule for every label
``money_prefix_for`` writes for its currencies, the bare "¥", and the dollar prefixes "C$", "A$", "CA$", "AU$",
"NZ$" and "MX$", each against a fact filed in each currency, so a later edit cannot quietly match a figure labelled
in the wrong currency.

Each cell is read twice: by the check (``build_metric_source``) and as the row is served
(``enrich_financial_highlights``), once without the filed fact's tag and once with it, in the current period and in
the prior. The fact names its currency three ways (``SOURCES``): on itself in a filing that reports in it, on itself
in a filing that reports in another (a currency switcher's or a stray item's shape), and only through the filing's
reporting currency, which a fact with none inherits. The rule holds the same in all three, so a check that read the
filing's currency in place of the fact's would fail the divergent cells. On the diagonal the row matches and keeps the summary's figure. Off it the row never matches the
summary's figure. Without a tag the label may name another line, so the row is left unchecked ("Linked, not
checked"). With the top line's tag the filed figure replaces the summary's, written in the fact's currency, and
``source_replaced`` keeps the summary's text. The display grammar reads none of "CA$", "AU$", "NZ$" and "MX$"
(``app.utils.numbers._CURRENCY``), so a figure carrying one is never checked, against any fact, its own included.
"""

import traceback
from itertools import product
from types import SimpleNamespace

import pytest

from app.services import provenance_service as prov
from app.utils.numbers import display_currency, money_prefix_for, parse_display_number

FACT_CURRENCIES = ("USD", "CNY", "EUR", "JPY", "AED", "CAD", "AUD", "NZD", "MXN")
# #1530's stated rule: a bare "¥" names one of these two (``provenance_service._YEN_CURRENCIES``).
YEN = frozenset({"JPY", "CNY"})
# Each label, and the currencies it names to a reader.
LABELS = {
    **{money_prefix_for(code): frozenset({code}) for code in FACT_CURRENCIES},
    "¥": YEN,
    "C$": frozenset({"CAD"}), "A$": frozenset({"AUD"}),
    "CA$": frozenset({"CAD"}), "AU$": frozenset({"AUD"}), "NZ$": frozenset({"NZD"}), "MX$": frozenset({"MXN"}),
}
UNREAD_PREFIXES = frozenset({"CA$", "AU$", "NZ$", "MX$"})
# Alibaba-sized revenue, this year and last: the summary's figures, and the filed ones as a swap writes them
# (``schemas.summary._format_xbrl_value``).
SHOWN = {"current_period": "941.2B", "prior_period": "800.0B"}
FILED = {"current_period": "941,168,000,000", "prior_period": "800,000,000,000"}
# A tag a "Revenue" row names exactly (``provenance_service._EXACT_SCOPE_TAGS``), so a figure that differs is replaced.
TAG = "ifrs-full:Revenue"
# How the filing's data names the fact's currency: "own" on the fact, in a filing reporting in it; "divergent" on the
# fact, in a filing reporting in another; "inherited" only through the filing's reporting currency, the fact naming none.
SOURCES = ("own", "divergent", "inherited")


def _filing():
    return SimpleNamespace(id=42, content_cache=None,
                           document_url="https://www.sec.gov/Archives/edgar/data/1577552/000.../baba.htm",
                           sec_url="https://www.sec.gov/Archives/edgar/data/1577552/000.../")


def _xbrl(currency, raw_tag, source="own"):
    """One revenue line filed in ``currency``, this year and a comparable last year (``comparable_facts``), its
    currency named as ``source`` says (``SOURCES``)."""
    reporting = ("CNY" if currency == "USD" else "USD") if source == "divergent" else currency
    own_currency = {} if source == "inherited" else {"currency": currency}

    def fact(value, end, start):
        return {"value": value, "period": end, "period_start": start, "form": "20-F", "fiscal_period": "FY",
                **own_currency, **({"raw_tag": raw_tag} if raw_tag else {})}
    return {"reporting_currency": reporting, "revenue": {
        "current": fact(941_168e6, "2025-03-31", "2024-04-01"), "prior": fact(800_000e6, "2024-03-31", "2023-04-01")}}


def _expected(label, currency, tagged):
    if label in UNREAD_PREFIXES:
        return "unchecked"
    if currency in LABELS[label]:
        return "matched"
    return "replaced" if tagged else "unchecked"


def _currencies_named(text):
    """The currencies a served figure's label names: a bare "¥" names two."""
    named, code = display_currency(text)
    assert named, text
    return YEN if code is None else frozenset({code})


def _check_cell(field, currency, label, tagged, source):
    other = "prior_period" if field == "current_period" else "current_period"
    own = money_prefix_for(currency)
    row = {"metric": "Revenue", field: label + SHOWN[field], other: own + SHOWN[other]}
    xbrl = _xbrl(currency, TAG if tagged else None, source)
    expected = _expected(label, currency, tagged)

    checked = prov.build_metric_source(dict(row), _filing(), xbrl, None)
    served = prov.enrich_financial_highlights({"table": [dict(row)]}, _filing(), xbrl)["table"][0]

    # The rule: the summary's own figure matches on the diagonal only, and a served "Matches filing" figure is in
    # the filed fact's currency.
    assert checked["source_verified"] is (expected == "matched")
    assert (served["source_verified"] and "source_replaced" not in served) is (expected == "matched")
    if served["source_verified"]:
        assert currency in _currencies_named(served[field])

    # Exactly what main does with the cell.
    assert served[other] == row[other]
    if expected == "matched":
        assert (checked["source_checkable"], checked["xbrl_concept"]) == (True, "Revenue")
        assert "source_mismatched" not in checked
        assert checked["source_filed"][field].startswith(own)
        assert served[field] == row[field]
    elif expected == "replaced":
        assert checked["source_checkable"] is True
        assert checked["source_mismatched"] == [field]
        assert checked["source_filed"][field].startswith(own)
        assert served["source_verified"] is True
        assert served[field] == own + FILED[field]
        assert display_currency(served[field]) == (True, currency)
        assert served["source_replaced"] == {field: row[field]}
    else:
        assert checked["source_checkable"] is False
        assert "source_mismatched" not in checked
        assert (served["source_checkable"], served["source_verified"]) == (False, False)
        assert served[field] == row[field]
        assert "source_replaced" not in served


@pytest.mark.parametrize("currency", FACT_CURRENCIES)
def test_a_figure_matches_only_in_the_filed_facts_currency(currency):
    # One test per fact currency, its cells in a loop: a test's setup costs more than all its cells.
    cells = list(product(("current_period", "prior_period"), LABELS, (False, True), SOURCES))
    failures = []
    for field, label, tagged, source in cells:
        cell = f"{field} {label!r} {'tagged' if tagged else 'untagged'} {source}"
        try:
            _check_cell(field, currency, label, tagged, source)
        except AssertionError as exc:
            line = traceback.extract_tb(exc.__traceback__)[-1].lineno
            failures.append(f"{cell}: line {line}: {str(exc).splitlines()[0] if str(exc) else 'assert'}")
    assert not failures, f"{len(failures)} of {len(cells)} {currency} cells fail:\n" + "\n".join(failures)


def test_a_bare_yen_matches_a_yen_or_renminbi_fact_only():
    # #1530's documented policy (``_shows_filed_value``): "¥" is compared by its number against a JPY or a CNY
    # fact, and is a mismatch against any other.
    matched = {
        currency for currency in FACT_CURRENCIES
        if prov.build_metric_source(
            {"metric": "Revenue", "current_period": "¥941.2B"}, _filing(), _xbrl(currency, None), None,
        )["source_verified"]
    }
    assert matched == YEN


@pytest.mark.parametrize("prefix", sorted(UNREAD_PREFIXES))
def test_the_display_grammar_reads_no_unread_prefix(prefix):
    # Why the matrix expects these cells unchecked, their own currency's included. A grammar that learns one
    # moves it out of UNREAD_PREFIXES, and the matrix then holds it to the diagonal.
    assert parse_display_number(f"{prefix}941.2B")[0] is None
    assert display_currency(f"{prefix}941.2B") == (False, None)
