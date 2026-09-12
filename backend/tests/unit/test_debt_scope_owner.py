"""Debt scope: what a debt figure may claim, and who owns the visible leverage slot.

Two invariants are under test.

**Scope fidelity** — no debt figure on any surface asserts a broader maturity, measurement or
entity scope than its own source evidence establishes. A total comes only from an issuer-reported
combined-total concept; an "identified borrowing components" subtotal only from a complete,
non-overlapping set sharing one accession, instant, currency, basis and reporting entity. Absent
debt is unestablished scope, never zero and never a net-cash position.

**Visible ownership** — ``balance_sheet_liquidity.leverage`` is machine-authored on every delivery
path, so a contradictory model total cannot survive beside a correct block.

The fixtures are extractor-SHAPED: the same columns ``edgartools`` puts on a fact frame
(``is_dimensioned`` / ``period_instant`` / ``period_start`` / ``numeric_value`` / ``currency`` /
``decimals`` / ``context_ref`` / ``entity_identifier`` / ``element_period_type``). Concept,
value, instant and currency for the WMT-shaped and MELI-shaped cases are the retained observed
rows from the fourth #825 report; every ``context_ref`` here is synthetic and is NOT a claim that
any issuer's instance carried that context. The COMPONENT concepts are likewise exercised as
shapes: whether a given issuer tags them undimensioned is a runtime fact no offline fixture may
assert, and the controls below pin only that the code handles each shape correctly.
"""

import pandas as pd
import pytest
from unittest.mock import patch

from app.services.edgar import xbrl_service as xbrl_module
from app.services.edgar.debt_concepts import (
    DEBT_CONCEPTS,
    EXCLUDED_DEBT_CONCEPTS,
    SCOPE_COMBINED_TOTAL,
    SCOPE_CURRENT_ALL,
    SCOPE_CURRENT_PORTION,
    SCOPE_LONG_TERM_INCL_CURRENT,
    SCOPE_NONCURRENT,
    SCOPE_PHRASE,
    SCOPE_SHORT_TERM,
    classify_debt_concept,
    is_complete_borrowing_partition,
    scopes_overlap,
)
from app.services.edgar.instance_extractor import debt_component_observations
from app.services.edgar.xbrl_service import EdgarXBRLService, _extract_from_filing_instance_sync
from app.services.ai import debt_scope as debt_scope_module
from app.services.ai.debt_scope import (
    build_debt_scope_view,
    debt_balance_label,
    debt_grounding_lines,
    leverage_statement,
    model_leverage_is_admissible,
)
from app.services.summary_sections import render_sections, sections_to_markdown

PERIOD = "2026-01-31"
ACCN = "0000104169-26-000055"


def money(value):
    """The §8 money formatter's USD shape, so expectations read like the rendered text."""
    if value is None:
        return None
    return f"${value / 1_000_000_000:.1f}B" if abs(value) >= 1e9 else f"${value / 1_000_000:.1f}M"


def fact(value, **over):
    """One extractor-shaped undimensioned instant fact row."""
    row = {
        "is_dimensioned": False,
        "period_start": None,
        "period_end": None,
        "period_instant": PERIOD,
        "numeric_value": value,
        "currency": "USD",
        "decimals": "-6",
        "context_ref": "c-synthetic-1",
        "entity_identifier": "0000104169",
        "entity_scheme": "http://www.sec.gov/CIK",
        "unit_ref": "usd",
        "element_period_type": "instant",
    }
    row.update(over)
    return row


class FakeXB:
    """Minimal stand-in for the parsed instance's fact-query seam."""

    def __init__(self, frames):
        self.frames = frames
        self.queried = []

    class _Query:
        def __init__(self, outer):
            self.outer = outer
            self.frame = pd.DataFrame()

        def by_concept(self, concept, exact=True):
            assert exact is True
            self.outer.queried.append(concept)
            rows = self.outer.frames.get(concept)
            self.frame = pd.DataFrame(rows) if rows else pd.DataFrame()
            return self

        def to_dataframe(self):
            return self.frame

    @property
    def facts(self):
        outer = self

        class _Facts:
            def query(self_inner):
                return FakeXB._Query(outer)

        return _Facts()


def observations(frames, currency="USD"):
    return debt_component_observations(
        FakeXB(frames), PERIOD, reporting_currency=currency, accession_number=ACCN, form="10-K",
    )


# ---------------------------------------------------------------------------
# The registry: scope is declared, never derived from a name or an amount.


def test_registry_declares_every_admissible_concept_with_a_carrying_basis_and_a_reason():
    assert set(DEBT_CONCEPTS) == {
        "us-gaap:LongTermDebtNoncurrent",
        "us-gaap:LongTermDebt",
        "us-gaap:LongTermDebtCurrent",
        "us-gaap:ShortTermBorrowings",
        "us-gaap:DebtLongtermAndShorttermCombinedAmount",
        "ifrs-full:NoncurrentBorrowings",
        "ifrs-full:CurrentBorrowings",
    }
    for concept, identity in DEBT_CONCEPTS.items():
        assert identity.basis == "carrying", concept
        assert identity.reason.strip(), concept
        assert identity.scope in SCOPE_PHRASE, concept
    # Exactly one concept may ever produce a "total debt" claim.
    totals = [c for c, i in DEBT_CONCEPTS.items() if i.scope == SCOPE_COMBINED_TOTAL]
    assert totals == ["us-gaap:DebtLongtermAndShorttermCombinedAmount"]


def test_the_two_scope_traps_are_declared_the_right_way_round():
    # MELI/JD: the concept that INCLUDES current maturities must never read as noncurrent-only.
    assert classify_debt_concept("us-gaap:LongTermDebt").scope == SCOPE_LONG_TERM_INCL_CURRENT
    assert classify_debt_concept("us-gaap:LongTermDebtNoncurrent").scope == SCOPE_NONCURRENT
    assert SCOPE_PHRASE[SCOPE_LONG_TERM_INCL_CURRENT] != SCOPE_PHRASE[SCOPE_NONCURRENT]
    assert "noncurrent" not in SCOPE_PHRASE[SCOPE_LONG_TERM_INCL_CURRENT].replace(
        "including current maturities", ""
    )


@pytest.mark.parametrize("concept", [
    "LongTermDebt",                       # bare local name, no namespace
    "gaap:LongTermDebt",                  # wrong namespace
    "us-gaap:longtermdebt",               # case variant
    "us-gaap:LongTermDebtNoncurrentXyz",  # suffix extension
    "acme:LongTermDebt",                  # issuer extension
    "us-gaap:DebtInstrumentFaceAmount",   # principal, explicitly excluded
    "ifrs-full:Borrowings",               # unverified, explicitly excluded
    None,
    "",
])
def test_unadmitted_concepts_never_borrow_a_known_scope(concept):
    assert classify_debt_concept(concept) is None


def test_exclusions_are_recorded_with_reasons_and_never_also_admitted():
    assert not set(EXCLUDED_DEBT_CONCEPTS) & set(DEBT_CONCEPTS)
    for concept, reason in EXCLUDED_DEBT_CONCEPTS.items():
        assert reason.strip(), concept


def test_overlapping_scopes_are_never_a_component_pair():
    # An aggregate overlaps its own parts; a scope overlaps itself.
    assert scopes_overlap(SCOPE_LONG_TERM_INCL_CURRENT, SCOPE_NONCURRENT)
    assert scopes_overlap(SCOPE_LONG_TERM_INCL_CURRENT, SCOPE_CURRENT_PORTION)
    assert scopes_overlap(SCOPE_CURRENT_ALL, SCOPE_SHORT_TERM)
    assert scopes_overlap(SCOPE_NONCURRENT, SCOPE_NONCURRENT)
    for scope in (SCOPE_NONCURRENT, SCOPE_CURRENT_PORTION, SCOPE_SHORT_TERM, SCOPE_CURRENT_ALL):
        assert scopes_overlap(SCOPE_COMBINED_TOTAL, scope)
    # The genuinely disjoint bands are not flagged.
    assert not scopes_overlap(SCOPE_NONCURRENT, SCOPE_CURRENT_PORTION)
    assert not scopes_overlap(SCOPE_NONCURRENT, SCOPE_SHORT_TERM)
    assert not scopes_overlap(SCOPE_LONG_TERM_INCL_CURRENT, SCOPE_SHORT_TERM)


def test_a_partition_must_close_before_it_may_be_added():
    assert is_complete_borrowing_partition(
        frozenset({SCOPE_NONCURRENT, SCOPE_CURRENT_PORTION, SCOPE_SHORT_TERM})
    )
    assert is_complete_borrowing_partition(
        frozenset({SCOPE_LONG_TERM_INCL_CURRENT, SCOPE_SHORT_TERM})
    )
    assert is_complete_borrowing_partition(frozenset({SCOPE_NONCURRENT, SCOPE_CURRENT_ALL}))
    # noncurrent + current portion with short-term borrowings still MISSING is the retained WMT
    # defect (34,624 + 3,542 = 38,166, published as "total debt"). It must not be summable.
    assert not is_complete_borrowing_partition(
        frozenset({SCOPE_NONCURRENT, SCOPE_CURRENT_PORTION})
    )
    assert not is_complete_borrowing_partition(frozenset({SCOPE_NONCURRENT}))
    assert not is_complete_borrowing_partition(frozenset({SCOPE_COMBINED_TOTAL, SCOPE_NONCURRENT}))


# ---------------------------------------------------------------------------
# Acquisition: only an unambiguous, undimensioned, instant, same-date, same-currency fact.


def test_admissible_concepts_are_queried_independently_and_carry_full_source_identity():
    rows = observations({
        "us-gaap:LongTermDebtNoncurrent": [fact(34_624_000_000.0, context_ref="c-nc")],
        "us-gaap:ShortTermBorrowings": [fact(6_596_000_000.0, context_ref="c-st")],
    })
    assert [r["concept"] for r in rows] == [
        "us-gaap:LongTermDebtNoncurrent", "us-gaap:ShortTermBorrowings",
    ]
    noncurrent = rows[0]
    assert noncurrent == {
        "concept": "us-gaap:LongTermDebtNoncurrent",
        "scope": SCOPE_NONCURRENT,
        "basis": "carrying",
        "value": 34_624_000_000.0,
        "instant": PERIOD,
        "currency": "USD",
        "unit_ref": "usd",
        "context_ref": "c-nc",
        "entity_identifier": "0000104169",
        "entity_scheme": "http://www.sec.gov/CIK",
        "decimals": "-6",
        "accn": ACCN,
        "form": "10-K",
    }


@pytest.mark.parametrize("bad, why", [
    ({"is_dimensioned": True}, "a dimensioned segment/subsidiary context"),
    ({"period_start": "2025-02-01", "period_instant": None, "period_end": PERIOD}, "a duration fact"),
    ({"element_period_type": "duration"}, "an element declared as a duration"),
    ({"period_instant": "2025-01-31"}, "a comparative instant, not the filing's own date"),
    ({"currency": None}, "no currency, so no currency-qualified claim"),
    ({"numeric_value": None}, "no value"),
])
def test_a_fact_that_cannot_be_qualified_is_not_an_observation(bad, why):
    assert observations({"us-gaap:LongTermDebtNoncurrent": [fact(1.0, **bad)]}) == [], why


def test_two_distinct_values_at_the_same_instant_fail_closed_whatever_the_precision():
    """Duplicate contexts are not rescued by preferring the finest ``decimals``."""
    rows = observations({"us-gaap:LongTermDebtNoncurrent": [
        fact(34_624_000_000.0, context_ref="c-a", decimals="-6"),
        fact(34_600_000_000.0, context_ref="c-b", decimals="-8"),
    ]})
    assert rows == []


def test_the_same_balance_restated_in_two_contexts_is_still_one_observation():
    rows = observations({"us-gaap:LongTermDebtNoncurrent": [
        fact(34_624_000_000.0, context_ref="c-a"),
        fact(34_624_000_000.0, context_ref="c-b"),
    ]})
    assert len(rows) == 1 and rows[0]["value"] == 34_624_000_000.0


def test_two_reporting_entities_at_the_same_instant_fail_closed():
    """A finance subsidiary's balance is not the consolidated or the ex-subsidiary measure."""
    rows = observations({"us-gaap:LongTermDebtNoncurrent": [
        fact(19_595_000_000.0, entity_identifier="0000037996"),
        fact(137_531_000_000.0, entity_identifier="0000038777"),
    ]})
    assert rows == []


def test_a_convenience_translation_does_not_suppress_the_reported_balance():
    """A foreign issuer tags the same balance in EUR and in a USD convenience translation."""
    rows = observations(
        {"ifrs-full:NoncurrentBorrowings": [
            fact(2_709_000_000.0, currency="EUR"),
            fact(3_100_000_000.0, currency="USD"),
        ]},
        currency="EUR",
    )
    assert len(rows) == 1
    assert rows[0]["currency"] == "EUR" and rows[0]["value"] == 2_709_000_000.0
    assert rows[0]["scope"] == SCOPE_NONCURRENT


def test_an_excluded_concept_is_never_queried_or_retained():
    xb = FakeXB({"us-gaap:DebtInstrumentFaceAmount": [fact(7_300_000_000.0)]})
    rows = debt_component_observations(xb, PERIOD, reporting_currency="USD")
    assert rows == []
    assert "us-gaap:DebtInstrumentFaceAmount" not in xb.queried


def test_a_true_zero_balance_is_retained_as_zero_not_dropped_as_unknown():
    rows = observations({"us-gaap:ShortTermBorrowings": [fact(0.0)]})
    assert len(rows) == 1 and rows[0]["value"] == 0.0


# ---------------------------------------------------------------------------
# Composition: what may be claimed from a set of observations.


def obs(concept, value, **over):
    row = {
        "concept": concept, "value": value, "instant": PERIOD, "currency": "USD",
        "accn": ACCN, "form": "10-K", "context_ref": "c-1", "entity_identifier": "0000104169",
    }
    row.update(over)
    return row


def view_of(*records, **metrics):
    return build_debt_scope_view({"debt_observations": list(records), **metrics})


def test_a_single_noncurrent_balance_states_its_scope_and_names_what_is_missing():
    """The retained WMT shape: only the noncurrent carrying balance is verifiable."""
    view = view_of(obs("us-gaap:LongTermDebtNoncurrent", 34_624_000_000.0))
    assert view.reported_total is None
    assert view.components_subtotal is None
    assert not view.scope_is_complete
    assert view.missing_scopes == (
        SCOPE_PHRASE[SCOPE_CURRENT_PORTION], SCOPE_PHRASE[SCOPE_SHORT_TERM],
    )
    text = leverage_statement(view, money)
    assert "noncurrent long-term debt of $34.6B" in text
    assert "Total debt, net debt and debt-to-equity are therefore not stated." in text
    assert "total debt of" not in text.lower()


def test_a_complete_partition_may_be_added_but_is_never_called_total_debt():
    view = view_of(
        obs("us-gaap:LongTermDebtNoncurrent", 5_940_628_000.0),
        obs("us-gaap:LongTermDebtCurrent", 1_271_056_000.0),
        obs("us-gaap:ShortTermBorrowings", 564_610_000.0),
    )
    assert view.components_subtotal == pytest.approx(7_776_294_000.0)
    assert view.reported_total is None and view.scope_is_complete
    text = leverage_statement(view, money)
    assert "Identified borrowing components" in text
    assert "short-term borrowings of $564.6M" in text  # COIN's must not disappear
    assert "Together $7.8B" in text
    assert "not a total obligations measure" in text
    assert "total debt" not in text.lower()


def test_noncurrent_plus_current_portion_alone_is_never_summed():
    """The retained WMT defect, at the composition seam.

    Its two long-term bands ARE disjoint, so nothing about overlap stops them being added — only
    the requirement that a partition CLOSE does. 34,624 + 3,542 = 38,166 is exactly the figure the
    retained outcome published as "total debt" while $6,596M of short-term borrowings was still
    missing, so that sum must not appear as a figure of any kind.
    """
    view = view_of(
        obs("us-gaap:LongTermDebtNoncurrent", 34_624_000_000.0),
        obs("us-gaap:LongTermDebtCurrent", 3_542_000_000.0),
    )
    assert not scopes_overlap(SCOPE_NONCURRENT, SCOPE_CURRENT_PORTION)  # not overlap — closure
    assert view.components_subtotal is None
    assert view.reported_total is None
    assert not view.scope_is_complete
    assert view.missing_scopes == (SCOPE_PHRASE[SCOPE_SHORT_TERM],)
    text = leverage_statement(view, money)
    assert "38.2" not in text and "38,166" not in text and "38.166" not in text
    assert "Together" not in text
    assert "noncurrent long-term debt of $34.6B" in text
    assert "current portion of long-term debt of $3.5B" in text
    assert "Total debt, net debt and debt-to-equity are therefore not stated." in text


def test_an_aggregate_and_its_own_parts_are_never_added_together():
    """The retained MELI shape: LongTermDebt (current AND noncurrent) beside a current figure."""
    view = view_of(
        obs("us-gaap:LongTermDebt", 9_193_000_000.0),
        obs("us-gaap:LongTermDebtCurrent", 4_623_000_000.0),
    )
    assert view.components_subtotal is None and view.reported_total is None
    text = leverage_statement(view, money)
    assert "long-term debt including current maturities of $9.2B" in text
    assert "13.8B" not in text and "13,816" not in text  # the double count never appears
    assert "Total debt, net debt and debt-to-equity are therefore not stated." in text
    # The aggregate already SPANS both long-term bands, so neither is reported as a gap; the only
    # genuine gap is short-term borrowings.
    assert view.missing_scopes == (SCOPE_PHRASE[SCOPE_SHORT_TERM],)
    assert "noncurrent long-term debt" not in text.split("Not separately reported")[-1]


def test_only_an_issuer_reported_combined_concept_yields_a_total():
    view = view_of(obs("us-gaap:DebtLongtermAndShorttermCombinedAmount", 44_762_000_000.0))
    assert view.reported_total is not None and view.scope_is_complete
    text = leverage_statement(view, money)
    assert "Total debt of $44.8B" in text
    assert "the issuer's own combined short-term and long-term debt measure" in text


def test_a_reported_total_lists_its_components_without_restating_itself():
    view = view_of(
        obs("us-gaap:DebtLongtermAndShorttermCombinedAmount", 44_762_000_000.0),
        obs("us-gaap:ShortTermBorrowings", 6_596_000_000.0),
    )
    text = leverage_statement(view, money)
    assert text.count("$44.8B") == 1  # the total appears once, not again as its own component
    assert "Reported separately within it: short-term borrowings of $6.6B." in text
    assert "51.4B" not in text  # and the total is never added to its own part


def test_an_unresolvable_scope_is_never_labelled_not_reported_beside_a_printed_figure():
    """The grounding label rides a row that IS printing a balance, so "not reported" would lie."""
    refused = view_of(
        obs("us-gaap:LongTermDebtNoncurrent", 1.0),
        obs("us-gaap:LongTermDebtNoncurrent", 2.0),
    )
    assert refused.rejection is not None
    assert debt_balance_label(refused) == "Debt Balance (maturity scope unavailable)"
    assert "not reported" not in debt_balance_label(refused)


def test_an_unknown_element_period_type_does_not_discard_the_fact():
    """An absent/NaN column is unknown, not "duration"; the instant check remains load-bearing."""
    for unknown in (None, float("nan"), ""):
        rows = observations({"us-gaap:LongTermDebtNoncurrent": [
            fact(34_624_000_000.0, element_period_type=unknown),
        ]})
        assert len(rows) == 1, unknown
        assert rows[0]["value"] == 34_624_000_000.0


@pytest.mark.parametrize("second, reason", [
    (obs("us-gaap:ShortTermBorrowings", 1.0, accn="0000000-00-000000"), "different source filings"),
    (obs("us-gaap:ShortTermBorrowings", 1.0, instant="2025-01-31"), "different balance dates"),
    (obs("us-gaap:ShortTermBorrowings", 1.0, currency="EUR"), "different currencies"),
    (obs("us-gaap:ShortTermBorrowings", 1.0, entity_identifier="0000038777"),
     "different reporting entities"),
    (obs("us-gaap:LongTermDebtNoncurrent", 2.0), "the same scope reported twice"),
])
def test_an_inconsistent_set_is_refused_whole_and_never_partly_kept(second, reason):
    view = view_of(obs("us-gaap:LongTermDebtNoncurrent", 34_624_000_000.0), second)
    assert view.observations == () and view.rejection is not None
    assert reason in view.rejection
    text = leverage_statement(view, money)
    assert "Debt scope not established" in text
    assert "34.6B" not in text  # no surviving figure from a refused set
    assert "no total debt, net debt or debt-to-equity figure is stated" in text


def test_absent_debt_is_unestablished_scope_not_zero_and_not_net_cash():
    """The retained Ford and NVO shape: no standardized debt row at all."""
    view = build_debt_scope_view({"cash_and_equivalents": {"current": {"value": 17_649_000_000.0}}})
    assert not view.has_evidence and not view.scope_is_complete
    text = leverage_statement(view, money)
    assert "reports no debt balance" in text
    assert "not zero debt and not a net cash position" in text
    assert "$0" not in text and "zero debt" not in text.replace("not zero debt", "")


def test_a_legacy_row_with_no_component_evidence_still_gets_its_scope_corrected():
    """Rows cached before this slice carry only the selected balance and its raw_tag."""
    view = build_debt_scope_view({"long_term_debt": {"current": {
        "value": 9_193_000_000.0, "period": "2025-12-31", "currency": "USD",
        "raw_tag": "us-gaap:LongTermDebt",
    }}})
    assert [o.scope for o in view.observations] == [SCOPE_LONG_TERM_INCL_CURRENT]
    assert view.components_subtotal is None and view.reported_total is None
    assert "including current maturities" in debt_balance_label(view)


def test_a_legacy_row_whose_concept_is_unknown_is_labelled_unavailable_not_long_term():
    view = build_debt_scope_view({"long_term_debt": {"current": {
        "value": 1_000.0, "period": PERIOD, "currency": "USD", "raw_tag": None,
    }}})
    assert debt_balance_label(view) == "Debt Balance (maturity scope unavailable)"
    assert "unestablished maturity scope" in leverage_statement(view, money)


# ---------------------------------------------------------------------------
# Model prose: admitted whole or replaced whole, never rewritten.


@pytest.mark.parametrize("prose", [
    "Total debt was $38.2B as of January 31, 2026.",                    # WMT
    "Cash of EUR 12,916.0M exceed total debt.",                          # ASML net-cash comparison
    "Company cash net of debt (excluding finance leases) was $3.3B.",    # Ford, cross-entity
    "Long-term debt rose to $9,193M from $5,715M.",                      # MELI mislabel
    "Total debt increased with short-term debt of CNY 8.0B.",            # JD
    "Net debt/EBITDA held at 1.2x.",
    "Leverage improved on lower indebtedness.",
    "The company refinanced its notes payable.",
    "Borrowings were reduced during the period.",
])
def test_a_model_debt_claim_is_never_admitted(prose):
    assert model_leverage_is_admissible(prose) is False


@pytest.mark.parametrize("prose", [
    # NVO run 0's actual leverage paragraph: valid analysis the correction must not delete.
    "Total assets increased to DKK 542.9B from DKK 465.6B. Shareholders' equity rose to "
    "DKK 194.0B from DKK 143.5B. Cash and equivalents increased to DKK 26.5B from DKK 15.7B.",
    "Total liabilities of $15.37B against total assets of $28.85B.",
    "Equity rose on retained earnings.",
])
def test_model_prose_making_no_debt_claim_is_kept_verbatim(prose):
    assert model_leverage_is_admissible(prose) is True
    view = build_debt_scope_view({})
    assert leverage_statement(view, money, prose).endswith(prose)


@pytest.mark.parametrize("prose", ["", "   ", None, 42, [], {"a": 1}])
def test_empty_or_non_string_prose_is_not_admitted(prose):
    assert model_leverage_is_admissible(prose) is False


# ---------------------------------------------------------------------------
# One owner for both surfaces (lessons/arch-guard-every-model-facing-surface.md).


def test_the_grounding_label_and_the_visible_statement_come_from_one_module():
    from app.services.ai import markdown_render, xbrl_narrative

    assert markdown_render.build_debt_scope_view is debt_scope_module.build_debt_scope_view
    assert xbrl_narrative.build_debt_scope_view is debt_scope_module.build_debt_scope_view
    assert xbrl_narrative.debt_balance_label is debt_scope_module.debt_balance_label
    assert markdown_render.leverage_statement is debt_scope_module.leverage_statement


def test_the_grounding_carries_each_observations_own_source_identity_and_the_scope_limit():
    view = view_of(obs("us-gaap:LongTermDebtNoncurrent", 34_624_000_000.0, context_ref="c-nc"))
    lines = debt_grounding_lines(view)
    body = "\n".join(lines)
    assert "concept: us-gaap:LongTermDebtNoncurrent" in body
    assert "basis: carrying amount" in body
    assert f"as of: {PERIOD}" in body
    assert "currency: USD" in body
    assert "context: c-nc" in body
    assert f"accession: {ACCN}" in body
    assert "Debt scope: NOT established" in body
    assert "do NOT add them into a total" in body


def test_a_filing_with_no_debt_evidence_adds_no_grounding_prose():
    """Render ownership already guarantees the outcome; the prompt gains nothing."""
    assert debt_grounding_lines(build_debt_scope_view({})) == []
    assert debt_grounding_lines(build_debt_scope_view({"revenue": {"current": {"value": 1}}})) == []


# ---------------------------------------------------------------------------
# The integrated consumer: extraction -> standardization -> grounding -> visible render.


def _fake_filing(xb, form="10-K", period=PERIOD):
    class _Filing:
        def __init__(self):
            self.form = form
            self.period_of_report = period

        def xbrl(self):
            return xb

    return _Filing()


def _patch_company(filings):
    class _Company:
        def get_filings(self, accession_number=None, trigger_full_load=None):
            return list(filings)

    return patch.object(
        xbrl_module, "resolve_filing_by_accession",
        lambda cik, accession_number: (_Company(), list(filings)),
    )


@pytest.fixture(autouse=True)
def _clean_l1_cache():
    xbrl_module._xbrl_cache.clear()
    yield
    xbrl_module._xbrl_cache.clear()


def _income_fact(value):
    return {
        "is_dimensioned": False, "period_start": "2025-02-01", "period_end": PERIOD,
        "period_instant": None, "numeric_value": value, "currency": "USD", "decimals": "-6",
        "element_period_type": "duration",
    }


def _run_real_path(monkeypatch, debt_frames, model_sections):
    """The actual product path: instance extraction -> standardized metrics -> the filler."""
    from app.config import settings
    from app.services.openai_service import OpenAIService
    from app.services.ai.xbrl_narrative import build_xbrl_narrative_section

    frames = {"us-gaap:NetIncomeLoss": [_income_fact(21_900_000_000.0)]}
    frames.update(debt_frames)
    xb = FakeXB(frames)
    monkeypatch.setattr(settings, "RICHER_FINANCIALS_ENABLED", False)
    monkeypatch.setattr(settings, "USE_STATEMENT_FINANCIALS", False)
    monkeypatch.setattr(xbrl_module, "DURATION_CONCEPTS", {"net_income": ["NetIncomeLoss"]})
    monkeypatch.setattr(xbrl_module, "INSTANT_CONCEPTS", {
        "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt", "NoncurrentBorrowings"],
    })
    monkeypatch.setattr(xbrl_module, "dividend_component_sum_series", lambda *a: ([], None))
    monkeypatch.setattr(xbrl_module, "_extract_segments", lambda *a: [])
    with _patch_company([_fake_filing(xb)]):
        raw = _extract_from_filing_instance_sync("0000104169", ACCN)
    metrics = EdgarXBRLService().extract_standardized_metrics(raw)
    sections = {"balance_sheet_liquidity": dict(model_sections)}
    OpenAIService.__new__(OpenAIService)._apply_structured_fallbacks(
        sections, {"company_name": "Test Co"}, metrics,
    )
    markdown = sections_to_markdown(render_sections({"schema_version": 2, "sections": sections}))
    return raw, metrics, sections, build_xbrl_narrative_section(metrics), markdown


def test_the_incorrect_total_cannot_survive_the_whole_real_path(monkeypatch):
    """WMT-shaped: the selected noncurrent balance is the only verifiable one.

    The model's "Total debt was $38.2B" is the retained defect; it must not reach the rendered
    page, the correct scope must, and the selected metric's public shape must be unchanged.
    """
    raw, metrics, sections, grounding, markdown = _run_real_path(
        monkeypatch,
        {"us-gaap:LongTermDebtNoncurrent": [fact(34_624_000_000.0, context_ref="c-nc")]},
        {
            "leverage": "Total debt was $38.2B as of January 31, 2026, comprising $34.6B "
                        "long-term debt and $3.5B due within one year.",
            "liquidity": "Cash and cash equivalents were $10.7B, with $15.0B of undrawn "
                         "committed lines of credit.",
            "maturities_covenants": ["Annual maturities of long-term debt: $3.5B in fiscal 2027."],
        },
    )
    # Public numeric precedence and shape of the selected metric: unchanged.
    assert raw["long_term_debt"] == [{
        "period": PERIOD, "value": 34_624_000_000.0, "form": "10-K", "accn": ACCN,
        "currency": "USD", "raw_tag": "us-gaap:LongTermDebtNoncurrent",
    }]
    # Source-qualified evidence rides through standardization as an annotation.
    assert metrics["debt_observations"][0]["context_ref"] == "c-nc"
    assert metrics["debt_observations"][0]["scope"] == SCOPE_NONCURRENT

    # The visible slot is code-owned: the contradictory total is gone from EVERY surface.
    leverage = sections["balance_sheet_liquidity"]["leverage"]
    # No ASSERTED total survives. The statement's own "Total debt ... not stated" disclaimer is
    # the opposite of a claim, so the check is on the assertive forms and the figure itself.
    assert "$38.2B" not in leverage
    assert "Total debt of" not in leverage and "Total debt was" not in leverage
    assert "Total debt, net debt and debt-to-equity are therefore not stated." in leverage
    assert "noncurrent long-term debt of $34.6B" in leverage
    assert "current portion of long-term debt; short-term borrowings" in leverage
    assert "$38.2B" not in markdown
    assert "Leverage: Identified debt as of 2026-01-31" in markdown

    # Preserved material: liquidity verbatim, the maturity schedule where it belongs.
    assert sections["balance_sheet_liquidity"]["liquidity"].startswith("Cash and cash equivalents")
    assert "Annual maturities of long-term debt" in markdown

    # The grounding the model reads carries the same scope the render shows.
    assert "Debt — noncurrent long-term debt: $34,624,000,000" in grounding
    assert "concept: us-gaap:LongTermDebtNoncurrent" in grounding
    assert "Long-term Debt:" not in grounding


def test_a_complete_partition_reaches_the_page_as_components_with_a_subtotal(monkeypatch):
    _raw, _metrics, sections, grounding, markdown = _run_real_path(
        monkeypatch,
        {
            "us-gaap:LongTermDebtNoncurrent": [fact(5_940_628_000.0, context_ref="c-nc")],
            "us-gaap:LongTermDebtCurrent": [fact(1_271_056_000.0, context_ref="c-cp")],
            "us-gaap:ShortTermBorrowings": [fact(564_610_000.0, context_ref="c-st")],
        },
        {"leverage": "Total liabilities of $15.37B; long-term debt of $7.3B."},
    )
    leverage = sections["balance_sheet_liquidity"]["leverage"]
    assert "$7.3B" not in leverage                      # the principal figure never survives
    assert "short-term borrowings of $564.6M" in leverage
    assert "Together $7.8B" in leverage
    assert "total debt" not in leverage.lower()
    assert "Together $7.8B" in markdown
    assert "the components above cover every borrowing" in grounding


def test_preview_and_final_show_the_same_authored_leverage(monkeypatch):
    """A preview must not reveal the old mislabelled clause while the final hides it."""
    import json

    from app.services.openai_service import OpenAIService

    _raw, metrics, sections, _grounding, _markdown = _run_real_path(
        monkeypatch,
        {"us-gaap:LongTermDebtNoncurrent": [fact(34_624_000_000.0)]},
        {"leverage": "Total debt was $38.2B."},
    )
    service = OpenAIService.__new__(OpenAIService)
    partial = json.dumps({"sections": {"balance_sheet_liquidity": {
        "leverage": "Total debt was $38.2B.",
        "liquidity": "Cash of $10.7B.",
        "source_section_ref": "MD&A",
    }}})
    preview = service._partial_markdown_preview(partial, metrics)
    assert preview is not None
    assert "$38.2B" not in preview
    assert "noncurrent long-term debt of $34.6B" in preview
    assert sections["balance_sheet_liquidity"]["leverage"] in preview


def test_a_stored_historical_row_still_renders_its_own_recorded_leverage():
    """Nothing rewrites a stored payload: web, Markdown and export read it exactly as before."""
    stored = {"schema_version": 2, "sections": {"balance_sheet_liquidity": {
        "leverage": "Total debt was $38.2B as of January 31, 2026.",
        "liquidity": "Cash of $10.7B.",
    }}}
    markdown = sections_to_markdown(render_sections(stored))
    assert "Leverage: Total debt was $38.2B as of January 31, 2026." in markdown


def test_an_empty_section_is_not_created_just_to_report_missing_debt(monkeypatch):
    """A "we cannot verify debt" sentence must not flip an empty §8 to covered."""
    _raw, _metrics, sections, _grounding, _markdown = _run_real_path(monkeypatch, {}, {})
    assert "leverage" not in sections.get("balance_sheet_liquidity", {})
