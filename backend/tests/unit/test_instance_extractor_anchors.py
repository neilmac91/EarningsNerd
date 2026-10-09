"""Wave 0 anchors for the instance-extractor split (refactor plan 2026-10, module M6, PR I0).

I1 moves ``app/services/edgar/instance_extractor.py`` into an ``edgar/instance/`` sub-package
behind an explicit re-export façade, while ``app/services/edgar/xbrl_service.py:43-58`` keeps
binding 14 names from that façade by name. These characterization tests pin today's behaviour at
the seams that move cuts, so a pure move passes them unchanged and anything else fails:

* I0.1 — the façade surface: the exact names xbrl_service binds, identity of each binding with the
  façade's object (the namespace other tests monkeypatch), and the test-imported private names.
* I0.2 — ``_reporting_currency``'s full ranking, level by level.
* I0.3 — ``duration_series_with_starts``'s ``selected_sources`` collector contract.
* I0.4 — ``_one_undimensioned_instant_fact``'s currency and entity rules, observed through
  ``debt_component_observations``.
* I0.5 — ``_statement_period_columns`` for foreign annual forms and its (end, marker) de-dup.

Every façade name read here is one something else already depends on (xbrl_service's 14
bindings, the 7 private names other test files import, FINANCIAL_SIC_LOW/HIGH), so this file adds
no façade obligation of its own. Names are read through the façade module at call time, so a name
the façade drops fails only its own anchors. Nothing is patched. The edgartools boundary is faked
in-process on real pandas frames: the pinned pandas 3 turns a missing cell in a string column into
NaN, which is the shape the extractor's NaN guards exist for.
"""

import ast
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app.services.edgar import instance_extractor as ie
from app.services.edgar import xbrl_service
from app.services.edgar.debt_concepts import classify_debt_concept

pytestmark = pytest.mark.unit

POR = "2025-12-31"  # the filing's period_of_report in every fixture below


# ---------------------------------------------------------------------------
# Shared fake: the parsed instance's fact-query seam,
#   xb.facts.query().by_concept("<namespace>:<Local>", exact=True).to_dataframe()


class _FactQuery:
    def __init__(self, frames):
        self._frames = frames
        self._rows = None

    def by_concept(self, concept, exact=True):
        assert exact is True
        self._rows = self._frames.get(concept)
        return self

    def to_dataframe(self):
        # A fresh frame per query, as a real parse would give: nothing is shared between calls.
        return pd.DataFrame(self._rows) if self._rows else pd.DataFrame()


def _instance(frames):
    """A parsed-instance stand-in serving fact rows keyed by EXACT qualified concept."""
    return SimpleNamespace(facts=SimpleNamespace(query=lambda: _FactQuery(frames)))


# ---------------------------------------------------------------------------
# I0.1 — façade identity snapshot

# The 14 names xbrl_service binds from the façade, in source order (xbrl_service.py:43-58).
XBRL_SERVICE_FACADE_BINDINGS = (
    "DURATION_CONCEPTS",
    "DURATION_WINDOWS",
    "INSTANT_CONCEPTS",
    "RICHER_DURATION_CONCEPTS",
    "RICHER_INSTANT_CONCEPTS",
    "cash_financial_classification",
    "debt_component_observations",
    "dividend_component_sum_series",
    "duration_series_with_starts",
    "extract_financial_statement_metrics",
    "instant_series_with_currency",
    "instant_series_currency_concept",
    "normalize_form",
    "segment_series_by_member",
)

# Private helpers other test files import from the façade path:
# test_accession_xbrl_extraction.py:234,245,253; test_financial_statement_extraction.py:14-16;
# test_fpi_currency.py:15-16.
TEST_IMPORTED_PRIVATE_NAMES = (
    "_parse_decimals",
    "_resolve_period_value",
    "_period_marker",
    "_statement_period_columns",
    "_truthy_flag",
    "_currency",
    "_reporting_currency",
)

_FACADE = "app.services.edgar.instance_extractor"


def _facade_imports(module):
    """Every binding the module's source imports from the façade, anywhere in the file.

    Evaluates the import statements rather than matching text: relative imports resolve against
    the module's own package, an alias renders as ``"name as alias"``, and an import of the façade
    MODULE itself (the attribute-access style that bypasses name binding) renders as ``"<module>"``.
    """
    package = module.__name__.split(".")[:-1]
    found = []
    for node in ast.walk(ast.parse(Path(module.__file__).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            pairs = [("<module>", alias.asname) for alias in node.names if alias.name == _FACADE]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = ".".join(package[: len(package) - node.level + 1] + ([base] if base else []))
            pairs = [(alias.name, alias.asname) for alias in node.names if base == _FACADE]
            pairs += [("<module>", alias.asname) for alias in node.names if f"{base}.{alias.name}" == _FACADE]
        else:
            continue
        found += [name if asname is None else f"{name} as {asname}" for name, asname in pairs]
    return found


def test_i0_1_xbrl_service_binds_exactly_the_pinned_facade_names():
    """I0.1: xbrl_service imports exactly the 14 pinned names from the façade, by name, unaliased.

    Pins app/services/edgar/xbrl_service.py:43-58. Name binding is what lets the patches other
    tests set on xbrl_service's namespace (DURATION_CONCEPTS, INSTANT_CONCEPTS,
    dividend_component_sum_series, debt_component_observations, extract_financial_statement_metrics)
    reach the code that reads them; attribute access on a sub-module would blind them silently.
    An added, dropped or aliased name fails here until this pin is updated deliberately.
    """
    assert sorted(_facade_imports(xbrl_service)) == sorted(XBRL_SERVICE_FACADE_BINDINGS)


@pytest.mark.parametrize("name", XBRL_SERVICE_FACADE_BINDINGS)
def test_i0_1_each_xbrl_service_binding_is_the_facade_object(name):
    """I0.1: each binding on xbrl_service IS the façade's object, and a function keeps its own name.

    Pins app/services/edgar/xbrl_service.py:43-58 against the definitions in
    app/services/edgar/instance_extractor.py (constants :31-177, functions :180-1229). Identity, not
    equality: a copied registry or a re-wrapped function on either side breaks the shared object.
    """
    bound = getattr(xbrl_service, name)
    assert bound is getattr(ie, name)
    if callable(bound):
        assert bound.__name__ == name


@pytest.mark.parametrize("name", TEST_IMPORTED_PRIVATE_NAMES)
def test_i0_1_test_imported_private_names_resolve_from_the_facade(name):
    """I0.1: each private helper other tests import resolves from the façade as itself.

    Pins the definitions at app/services/edgar/instance_extractor.py:246, :262, :305, :318, :1053,
    :1060 and :1098, which the façade must keep re-exporting.
    """
    helper = getattr(ie, name)
    assert callable(helper)
    assert helper.__name__ == name


def test_i0_1_financial_sic_band_resolves_from_the_facade():
    """I0.1: FINANCIAL_SIC_LOW/HIGH resolve from the façade with today's values.

    Pins app/services/edgar/instance_extractor.py:907; test_fi_predicate_single_source.py:27-29
    reads these two attributes from this module path to keep fi_signals' copy in step.
    """
    assert (ie.FINANCIAL_SIC_LOW, ie.FINANCIAL_SIC_HIGH) == (6000, 6799)


# ---------------------------------------------------------------------------
# I0.2 — _reporting_currency's full ranking. In the first three cases the loser wins every LOWER
# key, so the expected winner proves the named key outranks all of those below it.


@pytest.mark.parametrize("ends_by_currency, expected", [
    pytest.param({"ZAR": [POR, POR], "USD": ["2024-12-31", "2023-12-31"]}, "USD",
                 id="more-distinct-period-ends-outranks-presence-non-usd-and-alphabetical"),
    pytest.param({"ZAR": ["2024-12-31", "2023-12-31"], "USD": [POR, "2024-12-31"]}, "USD",
                 id="equal-ends-presence-at-period-of-report-outranks-non-usd-and-alphabetical"),
    pytest.param({"USD": [POR, "2024-12-31"], "EUR": [POR, "2024-12-31"]}, "EUR",
                 id="equal-ends-and-presence-non-usd-outranks-alphabetical"),
    pytest.param({"EUR": [POR], "GBP": [POR]}, "GBP",
                 id="all-else-equal-the-alphabetically-last-code-wins"),
    pytest.param({None: [POR, "2024-12-31", "2023-12-31"], "USD": ["2024-12-31"]}, "USD",
                 id="a-candidate-without-currency-never-ranks"),
])
def test_i0_2_reporting_currency_full_tie_break(ends_by_currency, expected):
    """I0.2: most distinct period-ends, then presence at period_of_report, then non-USD, then the
    alphabetically LAST code (``max`` over the code), independent of candidate order.

    Pins app/services/edgar/instance_extractor.py:274-292 (distinct ends per currency :274-276,
    currency-less candidates excluded :277-279, the ranking key :284-292).
    test_fpi_currency.py:109-122 covers only the more-periods and all-None cases.
    """
    # Real call shape (instance_extractor.py:413): (end, value, currency, decimals).
    candidates = [(end, 1.0, ccy, -6.0) for ccy, ends in ends_by_currency.items() for end in ends]
    assert ie._reporting_currency(candidates, POR) == expected
    assert ie._reporting_currency(candidates[::-1], POR) == expected


# ---------------------------------------------------------------------------
# I0.3 — duration_series_with_starts' selected_sources collector

_LOSING_CONCEPT = "NetCashProvidedByUsedInFinancingActivities"
_WINNING_CONCEPT = "CashFlowsFromUsedInFinancingActivities"
_STALE = {"stale": "an earlier call's provenance"}


def _duration_fact(end, start, value, decimals, currency, context_ref, *, dimensioned=False):
    return {
        "is_dimensioned": dimensioned, "period_start": start, "period_end": end,
        "numeric_value": value, "decimals": decimals, "currency": currency, "context_ref": context_ref,
    }


def _winning_rows():
    """A EUR reporter's annual flow: what the winning resolution keeps, and what it never may."""
    return [
        _duration_fact(POR, "2025-01-01", 32_667_300_000.0, "-5", "EUR", "c-fine"),      # [0] selected value
        _duration_fact(POR, "2025-01-01", 32_700_000_000.0, "-8", "EUR", "c-coarse"),    # [1] same figure, rounded
        _duration_fact(POR, "2025-01-01", 35_000_000_000.0, "-6", "USD", "c-usd"),       # [2] convenience translation
        _duration_fact(POR, "2025-10-01", 8_100_000_000.0, "-6", "EUR", "c-q4"),         # [3] Q4: not a 10-K duration
        _duration_fact(POR, "2025-01-01", 9_999.0, "0", "EUR", "c-segment", dimensioned=True),  # [4]
        _duration_fact("2024-12-31", "2024-01-01", 30_000_000_000.0, "-6", "EUR", "c-prior-a"),  # [5]
        _duration_fact("2024-12-31", "2024-01-02", 30_000_000_000.0, "-6", "EUR", "c-prior-b"),  # [6] other start
        _duration_fact("2026-12-31", "2026-01-01", 1.0, "-6", "EUR", "c-future"),         # [7] after the period
    ]


@pytest.mark.parametrize("qualified_concept", [False, True])
@pytest.mark.parametrize("namespace", ["us-gaap", "ifrs-full"])
def test_i0_3_selected_sources_rows_come_from_the_winning_resolution(namespace, qualified_concept):
    """I0.3: the collector is cleared on entry, then holds one entry per returned period, shaped
    {value, period_end, period_start, currency, raw_tag, rows}.

    Pins app/services/edgar/instance_extractor.py:397-398 (clear on entry) and :434-438 (entry
    shape): ``raw_tag`` is the exact successful namespace query whatever ``qualified_concept`` says
    (:401, :436, contrast the return at :439); ``rows`` are the original rows of that period inside
    the winning resolution, including the coarser duplicate the precision resolver accepted, and
    never a losing candidate concept's rows, another currency's rows, a dimensioned row, an
    out-of-window duration or a later period. Collecting never changes the returned series.
    Exercised today only indirectly, through test_financing_source.py:67-150.
    """
    frames = {
        # The first candidate has no fact at the period of report, so resolution moves on.
        f"us-gaap:{_LOSING_CONCEPT}": [_duration_fact("2024-12-31", "2024-01-01", 1_959.0, "0", "EUR", "c-loser")],
        f"{namespace}:{_WINNING_CONCEPT}": _winning_rows(),
    }
    concepts = [_LOSING_CONCEPT, _WINNING_CONCEPT]
    selected = [dict(_STALE)]

    result = ie.duration_series_with_starts(
        _instance(frames), concepts, "10-K", POR,
        qualified_concept=qualified_concept, selected_sources=selected,
    )

    winner = f"{namespace}:{_WINNING_CONCEPT}"
    assert result == (
        [(POR, 32_667_300_000.0, "2025-01-01"), ("2024-12-31", 30_000_000_000.0, None)],
        "EUR",
        winner if qualified_concept else _WINNING_CONCEPT,
    )
    rows = _winning_rows()
    assert selected == [
        {"value": 32_667_300_000.0, "period_end": POR, "period_start": "2025-01-01", "currency": "EUR",
         "raw_tag": winner, "rows": [rows[0], rows[1]]},
        {"value": 30_000_000_000.0, "period_end": "2024-12-31", "period_start": None, "currency": "EUR",
         "raw_tag": winner, "rows": [rows[5], rows[6]]},
    ]
    assert ie.duration_series_with_starts(
        _instance(frames), concepts, "10-K", POR, qualified_concept=qualified_concept,
    ) == result


def test_i0_3_selected_sources_is_cleared_even_when_nothing_resolves():
    """I0.3: the clear on entry is unconditional, so a reused collector never carries stale rows.

    Pins app/services/edgar/instance_extractor.py:397-398 together with the empty return at :440.
    """
    frames = {f"us-gaap:{_LOSING_CONCEPT}": [
        _duration_fact("2024-12-31", "2024-01-01", 1_959.0, "0", "USD", "c-comparative-only"),
    ]}
    selected = [dict(_STALE)]

    result = ie.duration_series_with_starts(
        _instance(frames), [_LOSING_CONCEPT, _WINNING_CONCEPT], "10-K", POR, selected_sources=selected,
    )

    assert result == ([], None, None)
    assert selected == []


# ---------------------------------------------------------------------------
# I0.4 — _one_undimensioned_instant_fact, observed through debt_component_observations (its only
# caller, and one of xbrl_service's bindings), so no further private name is needed.

_DEBT_CONCEPT = "us-gaap:LongTermDebtNoncurrent"
_ACCN = "0000104169-26-000055"
_NO_OBSERVATION = "no observation"


def _balance_fact(value, **over):
    """One undimensioned instant fact at the period of report, in edgartools' fact-frame columns."""
    row = {
        "is_dimensioned": False, "period_start": None, "period_end": None, "period_instant": POR,
        "numeric_value": value, "currency": "USD", "decimals": "-6", "unit_ref": "usd",
        "context_ref": "c-a", "entity_identifier": "0000104169",
        "entity_scheme": "http://www.sec.gov/CIK", "element_period_type": "instant",
    }
    row.update(over)
    return row


def _observations(rows, reporting_currency):
    return ie.debt_component_observations(
        _instance({_DEBT_CONCEPT: rows}), POR,
        reporting_currency=reporting_currency, accession_number=_ACCN, form="10-K",
    )


def _expected_observation(**over):
    identity = classify_debt_concept(_DEBT_CONCEPT)  # the registry owns scope and basis
    observation = {
        "concept": _DEBT_CONCEPT, "scope": identity.scope, "basis": identity.basis,
        "value": 34_624_000_000.0, "instant": POR, "currency": "USD", "unit_ref": "usd",
        "context_ref": "c-a", "entity_identifier": "0000104169",
        "entity_scheme": "http://www.sec.gov/CIK", "decimals": "-6", "accn": _ACCN, "form": "10-K",
    }
    observation.update(over)
    return observation


@pytest.mark.parametrize("currency_cell", [
    pytest.param("<drop column>", id="no-currency-column"),
    pytest.param(None, id="None"),
    pytest.param(float("nan"), id="NaN"),
])
def test_i0_4_a_fact_without_currency_is_never_an_observation_without_a_reporting_currency(currency_cell):
    """I0.4: with no reporting currency there is no currency FILTER, yet a currency-less row is
    still never an observation.

    Pins app/services/edgar/instance_extractor.py:643-645, the only guard on this path when
    ``reporting_currency`` is None (xbrl_service.py:490-494 passes None when no metric carried a
    currency); with a known reporting currency :646-647 would also drop the row, which is all
    test_debt_scope_owner.py:248-257 exercises. The NaN case also needs the guard at :255-256.
    """
    row = _balance_fact(34_624_000_000.0)
    if currency_cell == "<drop column>":
        del row["currency"]
    else:
        row["currency"] = currency_cell

    assert _observations([row], reporting_currency=None) == []


def test_i0_4_a_currency_less_duplicate_does_not_make_the_balance_ambiguous():
    """I0.4: a currency-less row is skipped before the ambiguity count, so it cannot suppress the
    one balance that does carry a currency (here pandas 3 delivers its None cell as NaN).

    Pins app/services/edgar/instance_extractor.py:643-645 ahead of the count at :651-652.
    """
    rows = [
        _balance_fact(34_600_000_000.0, currency=None, context_ref="c-no-unit"),
        _balance_fact(34_624_000_000.0, context_ref="c-usd"),
    ]

    assert _observations(rows, reporting_currency=None) == [_expected_observation(context_ref="c-usd")]


@pytest.mark.parametrize("first_entity, second_entity, expected_entity", [
    pytest.param("  0000104169\t", "0000104169", "0000104169", id="a-padded-copy-is-the-same-entity"),
    pytest.param("0000104169", "   ", "0000104169", id="a-blank-identifier-is-not-an-entity"),
    pytest.param(None, None, None, id="no-identifier-at-all-is-not-ambiguous"),
    pytest.param("0000104169", "0000038777", _NO_OBSERVATION, id="two-entities-fail-closed"),
    # Today's behaviour: pandas 3 turns the None into NaN, and :649-650 count str(nan) == "nan".
    pytest.param("0000104169", None, _NO_OBSERVATION, id="a-missing-identifier-arrives-as-nan-and-counts"),
])
def test_i0_4_entity_identifiers_are_compared_after_normalisation(first_entity, second_entity, expected_entity):
    """I0.4: two contexts carrying the SAME balance are one observation unless they name two
    entities, compared after whitespace stripping; the first row's identity is the one reported.

    Pins app/services/edgar/instance_extractor.py:648-650 (None and blank skipped, then strip) with
    the entity count at :652 and first-row-wins at :651, :654 and :702. Same value throughout, so the
    entity rule is isolated (test_debt_scope_owner.py:277-283 also differs in value).
    """
    rows = [
        _balance_fact(34_624_000_000.0, context_ref="c-a", entity_identifier=first_entity),
        _balance_fact(34_624_000_000.0, context_ref="c-b", entity_identifier=second_entity),
    ]

    observed = _observations(rows, reporting_currency="USD")

    if expected_entity == _NO_OBSERVATION:
        assert observed == []
    else:
        assert observed == [_expected_observation(entity_identifier=expected_entity)]


# ---------------------------------------------------------------------------
# I0.5 — _statement_period_columns


def _statement_frame(columns):
    """An as-reported statement frame; the period selector reads only its column labels."""
    return pd.DataFrame([[None] * len(columns)], columns=list(columns))


_MIXED_ANNUAL_COLUMNS = (
    "concept", "label", "standard_concept",
    "2023-12-31 (FY)", "2025-12-31 (Q4)", "2025-12-31 (FY)", "2025-12-31 (YTD)", "2025-12-31",
    "2024-12-31 (FY)",
)
_FY_COLUMNS = [("2025-12-31", "2025-12-31 (FY)"), ("2024-12-31", "2024-12-31 (FY)"),
               ("2023-12-31", "2023-12-31 (FY)")]


@pytest.mark.parametrize("form, expected", [
    pytest.param("20-F", _FY_COLUMNS, id="20-F"),
    pytest.param("40-F", _FY_COLUMNS, id="40-F"),
    pytest.param("20-F/A", _FY_COLUMNS, id="20-F-amendment"),
    pytest.param("40-F/A", _FY_COLUMNS, id="40-F-amendment"),
    pytest.param("10-K", _FY_COLUMNS, id="10-K"),
    pytest.param("10-Q", [("2025-12-31", "2025-12-31 (Q4)")], id="10-Q-control"),
])
def test_i0_5_foreign_annual_forms_read_only_fy_columns(form, expected):
    """I0.5: 20-F and 40-F (amended or not) read the ``(FY)`` columns exactly as a 10-K does,
    newest first; the same frame read as a 10-Q keeps only the discrete quarter.

    Pins app/services/edgar/instance_extractor.py:1072 (the annual forms), :1081-1083 (FY only),
    :1084-1088 (the quarterly branch the control takes) and :1094 (newest first).
    test_financial_statement_extraction.py:379-389 covers only a 10-Q's quarter-versus-YTD choice.
    """
    assert ie._statement_period_columns(_statement_frame(_MIXED_ANNUAL_COLUMNS), form) == expected


@pytest.mark.parametrize("form, columns, expected", [
    pytest.param(
        "20-F",
        ("concept", "2025-12-31 (fy)", "2025-12-31 (FY)", "2024-12-31 (FY)", "2024-12-31 (FY)"),
        [("2025-12-31", "2025-12-31 (fy)"), ("2024-12-31", "2024-12-31 (FY)")],
        id="annual-the-first-column-per-end-and-marker-wins",
    ),
    pytest.param(
        "10-Q",
        ("concept", "2025-09-30 (q3)", "2025-09-30 (Q3)", "2025-09-30 (Q2)", "2024-09-30 (Q3)",
         "2024-09-30 (Q3)"),
        [("2025-09-30", "2025-09-30 (q3)"), ("2025-09-30", "2025-09-30 (Q2)"),
         ("2024-09-30", "2024-09-30 (Q3)")],
        id="quarterly-the-key-is-end-and-marker-not-end-alone",
    ),
])
def test_i0_5_period_columns_are_deduplicated_by_end_and_marker(form, columns, expected):
    """I0.5: columns sharing (period_end, upper-cased marker) collapse to the FIRST one in frame
    order; columns differing only in marker both stay, in frame order (the sort is stable).

    Pins app/services/edgar/instance_extractor.py:1089-1092 (the de-dup) with :1057 (marker
    upper-cased) and :1094 (stable newest-first sort).
    """
    assert ie._statement_period_columns(_statement_frame(columns), form) == expected
