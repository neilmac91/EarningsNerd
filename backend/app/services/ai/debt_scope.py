"""The single owner of what a debt figure MEANS on every surface that shows or feeds one.

Two surfaces carried a debt claim and neither owned its scope:

* ``xbrl_narrative`` labelled every selected balance "Long-term Debt", whatever concept won —
  so a noncurrent-only balance and a current-plus-noncurrent balance read identically to the model;
* ``markdown_render`` left ``balance_sheet_liquidity.leverage`` entirely model-authored, and the
  retained outcomes show what that produced: "Total debt was $38.2B" for a filer whose only
  verifiable balance is $34,624M of NONCURRENT debt with short-term borrowings still missing;
  "cash ... exceed total debt" on a scope that omitted two components; "Long-term debt rose to
  $9,193M" for a concept that already includes current maturities, with a separate current figure
  added beside it; and, for a filer whose standardized debt is absent entirely, a "cash net of
  debt" claim mixing two different reporting entities.

This module is that missing owner, and it is deliberately the ONLY one (the
``arch-guard-every-model-facing-surface`` lesson: a scope guard applied to the render but not the
grounding feeds the model the exact claim the render just refused). It decides, from source
evidence alone:

* which observations are admissible and mutually consistent (same filing, instant, currency,
  basis and reporting entity; no duplicate or overlapping scope);
* whether a TOTAL may be stated — only from an issuer-reported combined-total concept, never from
  our own addition;
* whether an "identified borrowing components" subtotal may be stated — only when the observed
  scopes cover every borrowing the filing reports on one basis;
* what remains UNAVAILABLE, stated explicitly, so missing debt reads as unknown rather than zero
  or a net-cash position.

Nothing here infers a scope, context, entity, basis or lease policy from a convenient amount
match, and nothing rewrites a model sentence: an authored leverage claim is either admitted whole
because it makes no debt claim, or replaced whole by the source-qualified statement.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.services.edgar.debt_concepts import (
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

# The scope phrase used when a balance exists but its concept is not admissible (an issuer
# extension, an unrecognized namespace, or a pre-slice cached row with no recorded concept).
UNKNOWN_SCOPE_PHRASE = "reported debt balance of unestablished maturity scope"

# Borrowing scopes a complete partition could still be missing, in the order they are named when
# absent. `SCOPE_CURRENT_ALL` is omitted deliberately: it is the IFRS spelling of the two US-GAAP
# current bands, so naming both would report the same gap twice.
_NAMEABLE_GAPS: Tuple[str, ...] = (SCOPE_CURRENT_PORTION, SCOPE_SHORT_TERM, SCOPE_NONCURRENT)

# What even a COMPLETE borrowing partition does not cover. Stated with every subtotal so the
# number is never read as total obligations.
_SUBTOTAL_EXCLUSIONS = (
    "it covers borrowings only, not lease, deposit or other financial liabilities"
)

# A model-authored leverage sentence is admitted only when it makes no debt or leverage claim at
# all. Matching is deliberately broad and one-directional: a false rejection loses a sentence, a
# false admission keeps an unverifiable total on the page. Word-boundary anchored so "indebted"
# matches and "debut" does not.
_DEBT_CLAIM_RE = re.compile(
    r"\b("
    r"debts?|indebted(?:ness)?|"
    r"borrow(?:ing|ings|ed|er|ers)?|"
    r"leverag(?:e|ed|ing)|deleverag(?:e|ed|ing)|gearing|"
    r"refinanc(?:e|ed|ing)|"
    r"notes?\s+payable|loans?\s+payable|"
    r"net\s+cash\s+position|net\s+debt"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DebtObservation:
    """One source-qualified debt balance. Every field is observed, never defaulted."""

    concept: str
    scope: str
    basis: str
    value: float
    instant: Optional[str]
    currency: Optional[str]
    accn: Optional[str] = None
    form: Optional[str] = None
    unit_ref: Optional[str] = None
    context_ref: Optional[str] = None
    entity_identifier: Optional[str] = None
    entity_scheme: Optional[str] = None
    decimals: Optional[str] = None

    @property
    def phrase(self) -> str:
        """The scope phrase for this observation; unknown concepts never borrow a known phrase."""
        return SCOPE_PHRASE.get(self.scope, UNKNOWN_SCOPE_PHRASE)


@dataclass(frozen=True)
class DebtScopeView:
    """What this filing's standardized data does and does not establish about debt."""

    observations: Tuple[DebtObservation, ...] = ()
    reported_total: Optional[DebtObservation] = None
    components_subtotal: Optional[float] = None
    missing_scopes: Tuple[str, ...] = ()
    rejection: Optional[str] = None

    @property
    def has_evidence(self) -> bool:
        return bool(self.observations)

    @property
    def scope_is_complete(self) -> bool:
        """True only when a figure covering every reported borrowing may be stated."""
        return self.reported_total is not None or self.components_subtotal is not None


def _observation_from_record(record: Any) -> Optional[DebtObservation]:
    """Build an observation from one extractor record, or None when it is not admissible."""
    if not isinstance(record, dict):
        return None
    identity = classify_debt_concept(record.get("concept"))
    value = record.get("value")
    if identity is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value:  # NaN
        return None
    # The extractor classifies at entry; re-deriving scope/basis here from the concept keeps this
    # consumer from trusting a stored classification it cannot verify (rule 9 cuts the other way
    # for an EXTERNAL value, but a stored enum is cheap to re-derive and cannot then drift).
    return DebtObservation(
        concept=str(record.get("concept")),
        scope=identity.scope,
        basis=identity.basis,
        value=float(value),
        instant=record.get("instant"),
        currency=record.get("currency"),
        accn=record.get("accn"),
        form=record.get("form"),
        unit_ref=record.get("unit_ref"),
        context_ref=record.get("context_ref"),
        entity_identifier=record.get("entity_identifier"),
        entity_scheme=record.get("entity_scheme"),
        decimals=record.get("decimals"),
    )


def _mutually_consistent(observations: Sequence[DebtObservation]) -> Optional[str]:
    """None when the set may be reported together, else the reason it must be refused entirely.

    Fails the WHOLE set rather than dropping the odd one out: with two candidate readings of the
    same balance sheet there is no evidence for preferring either, and silently keeping one is how
    a wrong scope survives.
    """
    for field, label in (
        ("accn", "different source filings"),
        ("instant", "different balance dates"),
        ("currency", "different currencies"),
        ("basis", "different measurement bases"),
    ):
        distinct = {getattr(obs, field) for obs in observations}
        if len(distinct) > 1:
            return f"debt observations refused: {label}"
    entities = {obs.entity_identifier for obs in observations if obs.entity_identifier}
    if len(entities) > 1:
        return "debt observations refused: different reporting entities"
    scopes = [obs.scope for obs in observations]
    if len(set(scopes)) != len(scopes):
        return "debt observations refused: the same scope reported twice"
    return None


def _fallback_observation(xbrl_metrics: Dict[str, Any]) -> Optional[DebtObservation]:
    """The selected ``long_term_debt`` balance as one observation, for rows with no component
    evidence (every summary cached before this slice, and any filer whose instance yields no
    admissible concept through the component path). Its concept may be unadmitted or absent, in
    which case the scope is explicitly unknown — the label correction still applies."""
    entry = xbrl_metrics.get("long_term_debt")
    current = entry.get("current") if isinstance(entry, dict) else None
    if not isinstance(current, dict):
        return None
    value = current.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        return None
    raw_tag = current.get("raw_tag")
    identity = classify_debt_concept(raw_tag)
    return DebtObservation(
        concept=str(raw_tag) if isinstance(raw_tag, str) and raw_tag else "",
        scope=identity.scope if identity else "",
        basis=identity.basis if identity else "",
        value=float(value),
        instant=current.get("period"),
        currency=current.get("currency"),
        accn=current.get("accn"),
        form=current.get("form"),
    )


def build_debt_scope_view(xbrl_metrics: Optional[Dict[str, Any]]) -> DebtScopeView:
    """What may be claimed about this filing's debt, from its own standardized evidence only."""
    if not isinstance(xbrl_metrics, dict):
        return DebtScopeView()

    records = xbrl_metrics.get("debt_observations")
    observations = [
        obs for obs in (
            _observation_from_record(rec) for rec in (records if isinstance(records, list) else ())
        ) if obs is not None
    ]
    if not observations:
        fallback = _fallback_observation(xbrl_metrics)
        if fallback is None:
            return DebtScopeView()
        # A single balance establishes nothing beyond itself: no total, no subtotal, and every
        # borrowing band it does not name stays explicitly missing.
        return DebtScopeView(
            observations=(fallback,),
            missing_scopes=_missing_scopes((fallback,)),
        )

    refusal = _mutually_consistent(observations)
    if refusal is not None:
        return DebtScopeView(rejection=refusal)

    observations.sort(key=lambda obs: (-abs(obs.value), obs.concept))
    frozen = tuple(observations)

    reported_total = next(
        (obs for obs in frozen if obs.scope == SCOPE_COMBINED_TOTAL), None,
    )
    subtotal = None
    if reported_total is None:
        scopes = frozenset(obs.scope for obs in frozen)
        # A subtotal needs BOTH a complete partition and no overlapping pair inside it. The
        # partition table already excludes overlaps, but checking pairwise keeps the two rules
        # independent, so widening one table can never silently license a double count.
        if not _any_overlap(frozen):  # MUTATION: closure requirement removed
            subtotal = sum(obs.value for obs in frozen)
    return DebtScopeView(
        observations=frozen,
        reported_total=reported_total,
        components_subtotal=subtotal,
        missing_scopes=() if (reported_total or subtotal is not None) else _missing_scopes(frozen),
    )


def _any_overlap(observations: Sequence[DebtObservation]) -> bool:
    for i, first in enumerate(observations):
        for second in observations[i + 1:]:
            if scopes_overlap(first.scope, second.scope):
                return True
    return False


# What an observed scope already accounts for, so a band an aggregate covers is never reported as a
# gap. `us-gaap:LongTermDebt` spans the noncurrent balance AND its current maturities, so for a
# MELI/JD-shaped filing the only genuine gap is short-term borrowings; `ifrs-full:CurrentBorrowings`
# spans both current bands. Derived from the same overlap semantics as the partition table, kept
# explicit because "overlaps" and "subsumes" are different questions.
_SCOPE_COVERS: Dict[str, Tuple[str, ...]] = {
    SCOPE_LONG_TERM_INCL_CURRENT: (SCOPE_NONCURRENT, SCOPE_CURRENT_PORTION),
    SCOPE_CURRENT_ALL: (SCOPE_CURRENT_PORTION, SCOPE_SHORT_TERM),
}


def _missing_scopes(observations: Sequence[DebtObservation]) -> Tuple[str, ...]:
    """Borrowing bands this filing does not report at all, as phrases, in a stable order."""
    covered = {obs.scope for obs in observations}
    for obs in observations:
        covered.update(_SCOPE_COVERS.get(obs.scope, ()))
    return tuple(
        SCOPE_PHRASE[scope] for scope in _NAMEABLE_GAPS if scope not in covered
    )


# ---------------------------------------------------------------------------
# Surface 1: the grounding block the MODEL reads.


def debt_balance_label(view: DebtScopeView) -> str:
    """The scope-derived label for the selected debt balance row.

    Replaces the fixed "Long-term Debt", which asserted a maturity scope the winning concept did
    not always carry. An unadmitted or absent concept is labelled as an unestablished scope rather
    than promoted to the label of whichever concept usually wins.
    """
    # This label is only ever attached to a row that is PRINTING a balance, so it must never read
    # "not reported" — that contradicts the figure beside it. With no admissible observation (an
    # unadmitted concept, or a set refused for inconsistency) the honest label is the unavailable
    # scope.
    primary = view.observations[0] if view.observations else None
    if primary is not None and primary.scope:
        return f"Debt — {SCOPE_PHRASE[primary.scope]}"
    return "Debt Balance (maturity scope unavailable)"


def debt_grounding_lines(view: DebtScopeView) -> List[str]:
    """Extra grounding rows naming every observation's own source identity and the scope limit.

    Emitted beside the standardized debt row so the model reads the same scope the render shows.
    Empty when there is nothing observed to qualify.
    """
    if view.rejection is not None:
        return [
            f"- Debt scope: {view.rejection}. Do NOT state a debt total, net debt or "
            "debt-to-equity figure for this filing."
        ]
    if not view.observations:
        # Deliberately silent. A filing with no debt evidence gets NO added grounding prose: the
        # visible leverage slot is code-owned on every path, so the model's leverage claim cannot
        # reach the page whatever this block says, and an instruction line here would add
        # unmeasurable prompt text to every debt-free filing — the amplifier the
        # arch-drop-neutral-amplifiers-with-risk and arch-stop-tuning-prose-know-the-floor lessons
        # refuse. It also keeps the legacy grounding block byte-for-byte for filings with only
        # legacy metrics. Lines below appear only where there is real source identity to carry.
        return []
    lines: List[str] = []
    for obs in view.observations:
        identity = [f"concept: {obs.concept}" if obs.concept else "concept: not recorded"]
        if obs.basis:
            identity.append(f"basis: {obs.basis} amount")
        if obs.instant:
            identity.append(f"as of: {obs.instant}")
        if obs.currency:
            identity.append(f"currency: {obs.currency}")
        if obs.context_ref:
            identity.append(f"context: {obs.context_ref}")
        if obs.accn:
            identity.append(f"accession: {obs.accn}")
        lines.append(f"- Debt component — {obs.phrase}: {'; '.join(identity)}")
    if view.reported_total is not None:
        lines.append(
            "- Debt scope: the issuer reports a combined short-term and long-term debt total, "
            "shown above. Quote that figure for total debt; do not recompute it."
        )
    elif view.components_subtotal is not None:
        lines.append(
            "- Debt scope: the components above cover every borrowing this filing reports "
            f"separately on one basis, so their sum may be cited as identified borrowing "
            f"components — never as total debt or total obligations ({_SUBTOTAL_EXCLUSIONS})."
        )
    else:
        gaps = "; ".join(view.missing_scopes) or "other borrowings"
        lines.append(
            f"- Debt scope: NOT established. Not separately reported here: {gaps}. Report ONLY "
            "the component(s) above with their stated scope; do NOT add them into a total, call "
            "any of them total debt, net debt or net cash, or state a debt-to-equity ratio."
        )
    return lines


# ---------------------------------------------------------------------------
# Surface 2: the visible §8 leverage statement.


def model_leverage_is_admissible(text: Any) -> bool:
    """True when model-authored leverage prose may be kept beside the source-qualified statement.

    Admits only prose that makes no debt or leverage claim whatsoever — an equity, asset or cash
    observation, for instance, which the source statement does not cover and which is genuine
    analysis worth preserving. Judged on the WHOLE field: splitting a paragraph and relabelling the
    clause that happens to contain a number is exactly the brittle rewrite this design avoids.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    return _DEBT_CLAIM_RE.search(text) is None


def leverage_statement(
    view: DebtScopeView, format_currency: Any, retained_prose: Optional[str] = None,
) -> str:
    """The visible leverage text: source-qualified debt scope, then any admissible model prose.

    ``format_currency`` is the caller's own money formatter, so the figures read exactly like the
    rest of the section (currency-aware, same abbreviations). Scope wording comes from here alone.
    """
    parts: List[str] = [_scope_sentences(view, format_currency)]
    if retained_prose and retained_prose.strip():
        parts.append(retained_prose.strip())
    return " ".join(part for part in parts if part)


def _scope_sentences(view: DebtScopeView, format_currency: Any) -> str:
    if view.rejection is not None:
        return (
            f"Debt scope not established — {view.rejection.split(': ', 1)[-1]}; no total debt, "
            "net debt or debt-to-equity figure is stated."
        )
    if not view.observations:
        return (
            "This filing's standardized financial data reports no debt balance under a concept "
            "whose scope can be verified. That is an unestablished scope, not zero debt and not a "
            "net cash position; no total debt, net debt or debt-to-equity figure is stated."
        )
    listed = "; ".join(
        f"{obs.phrase} of {format_currency(obs.value) or 'an undisclosed amount'}"
        for obs in view.observations
    )
    primary = view.observations[0]
    dated = f" as of {primary.instant}" if primary.instant else ""
    basis = f" ({primary.basis} amount)" if primary.basis else ""

    if view.reported_total is not None:
        sentence = (
            f"Total debt of {format_currency(view.reported_total.value)}{dated}{basis} — the "
            "issuer's own combined short-term and long-term debt measure."
        )
        # Anything else observed is a COMPONENT of that total, so it is listed separately and never
        # added to it. The total itself is excluded from that list — restating it as one of its own
        # components would read as two balances.
        others = "; ".join(
            f"{obs.phrase} of {format_currency(obs.value) or 'an undisclosed amount'}"
            for obs in view.observations if obs is not view.reported_total
        )
        if others:
            sentence += f" Reported separately within it: {others}."
        return sentence
    if view.components_subtotal is not None:
        return (
            f"Identified borrowing components{dated}{basis}: {listed}. Together "
            f"{format_currency(view.components_subtotal)} — every borrowing this filing reports "
            f"separately on this basis, though {_SUBTOTAL_EXCLUSIONS}, so it is not a total "
            "obligations measure."
        )
    gaps = "; ".join(view.missing_scopes) or "other borrowings"
    scope_note = (
        f"Not separately reported in this filing's standardized data: {gaps}."
        if primary.scope else
        "The concept behind this balance does not establish which maturities it covers."
    )
    return (
        f"Identified debt{dated}{basis}: {listed}. {scope_note} Total debt, net debt and "
        "debt-to-equity are therefore not stated."
    )
