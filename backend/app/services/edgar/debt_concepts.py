"""Source-layer registry: which XBRL concepts are admissible debt balances, and what each MEANS.

One hand-audited literal table is the single authority on a debt observation's *scope* (which
maturity/obligation slice the balance covers) and *basis* (carrying amount vs anything else). It
exists because the normalized ``long_term_debt`` label is not a completeness certificate: the
extractor's first-candidate-wins selection resolves ``us-gaap:LongTermDebtNoncurrent`` for one
filer and ``us-gaap:LongTermDebt`` for the next, and those two concepts do NOT cover the same
obligations. Labelling both "Long-term Debt" collapsed a noncurrent-only balance and a
current-plus-noncurrent balance into one claim (#808 / #821 / #825 retained outcomes).

Scope is NEVER inferred from a concept's name suffix, its namespace, a statement section guessed
from a label, or a value that happens to match another figure. Every entry below is enumerated
explicitly with the reason it is admissible. The edgartools bundle ships
``xbrl/standardization/gaap_mappings.json``, which looks like a taxonomy definition but is a
STATISTICAL display-name mapping and is wrong for this purpose: it files ``us-gaap:LongTermDebt``
under "Non-Current Liabilities" (that element includes current maturities) and reports
``us-gaap:DebtInstrumentFaceAmount`` — an instrument-level PRINCIPAL disclosure — as a
balance-sheet total. It is used here only as corroboration for IFRS names, never as the authority.

Deliberate exclusions are listed in ``EXCLUDED_DEBT_CONCEPTS`` with their reason, so a later reader
can see that absence is a decision rather than an oversight.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, NamedTuple, Optional, Tuple

# ---------------------------------------------------------------------------
# Scope vocabulary. Each value names the obligation slice a balance covers, in the issuer's own
# reporting, on a carrying basis. These are the ONLY scopes a visible debt claim may assert.
SCOPE_NONCURRENT = "noncurrent_long_term"
SCOPE_CURRENT_PORTION = "current_portion_long_term"
SCOPE_SHORT_TERM = "short_term_borrowings"
SCOPE_LONG_TERM_INCL_CURRENT = "long_term_incl_current"
SCOPE_CURRENT_ALL = "current_all_borrowings"
SCOPE_COMBINED_TOTAL = "combined_total_debt"

# Basis vocabulary. Only CARRYING-basis consolidated balances are admissible. Principal /
# face amounts, contractual maturity schedules and cash-flow borrowing proceeds are different
# measurements and are never mixed with these (see EXCLUDED_DEBT_CONCEPTS).
BASIS_CARRYING = "carrying"

# Human-readable scope phrasing, shared by every surface (grounding label and visible text) so the
# two cannot drift. Phrasing states what IS covered; it never implies completeness.
SCOPE_PHRASE: Dict[str, str] = {
    SCOPE_NONCURRENT: "noncurrent long-term debt",
    SCOPE_CURRENT_PORTION: "current portion of long-term debt",
    SCOPE_SHORT_TERM: "short-term borrowings",
    SCOPE_LONG_TERM_INCL_CURRENT: "long-term debt including current maturities",
    SCOPE_CURRENT_ALL: "current borrowings (current maturities and short-term borrowings)",
    SCOPE_COMBINED_TOTAL: "combined short-term and long-term debt",
}


class DebtIdentity(NamedTuple):
    """What one admissible debt concept means. ``reason`` records why it is admissible."""

    scope: str
    basis: str
    reason: str


# The admissible set, keyed by the EXACT qualified concept the extractor's successful namespace
# query returned ("<namespace>:<LocalName>"). A concept absent from this table is unknown scope and
# can never be promoted to a total or a component — it stays a "reported debt balance" whose
# maturity scope is unavailable.
DEBT_CONCEPTS: Dict[str, DebtIdentity] = {
    # us-gaap. Definitions per the FASB element documentation for each element.
    "us-gaap:LongTermDebtNoncurrent": DebtIdentity(
        SCOPE_NONCURRENT, BASIS_CARRYING,
        "carrying amount of long-term debt EXCLUDING amounts due within one year",
    ),
    "us-gaap:LongTermDebt": DebtIdentity(
        SCOPE_LONG_TERM_INCL_CURRENT, BASIS_CARRYING,
        "carrying amount of long-term debt INCLUDING current maturities; not noncurrent-only",
    ),
    "us-gaap:LongTermDebtCurrent": DebtIdentity(
        SCOPE_CURRENT_PORTION, BASIS_CARRYING,
        "carrying amount of long-term debt due within one year",
    ),
    "us-gaap:ShortTermBorrowings": DebtIdentity(
        SCOPE_SHORT_TERM, BASIS_CARRYING,
        "carrying amount of short-term borrowings, separate from long-term debt maturities",
    ),
    "us-gaap:DebtLongtermAndShorttermCombinedAmount": DebtIdentity(
        SCOPE_COMBINED_TOTAL, BASIS_CARRYING,
        "issuer-reported combined short-term and long-term debt — the one admissible TOTAL",
    ),
    # ifrs-full, for foreign private issuers filing under IFRS. Both names are corroborated by the
    # installed edgartools mapping's section placement AND by the IFRS element definitions
    # ("the amount of non-current borrowings" / "the amount of current borrowings"); neither is
    # accepted on its name alone.
    "ifrs-full:NoncurrentBorrowings": DebtIdentity(
        SCOPE_NONCURRENT, BASIS_CARRYING,
        "IFRS amount of non-current borrowings; excludes the current portion",
    ),
    "ifrs-full:CurrentBorrowings": DebtIdentity(
        SCOPE_CURRENT_ALL, BASIS_CARRYING,
        "IFRS amount of current borrowings; covers current maturities AND short-term borrowings",
    ),
}

# Concepts deliberately NOT admitted, with the reason. Kept as data so the exclusion is reviewable
# and a future reader does not re-add one by assuming it was simply forgotten.
EXCLUDED_DEBT_CONCEPTS: Dict[str, str] = {
    "us-gaap:LongTermDebtAndCapitalLeaseObligations":
        "bundles finance-lease obligations; lease policy must not be inferred into a debt measure",
    "us-gaap:LongTermDebtAndCapitalLeaseObligationsCurrent":
        "bundles the current finance-lease obligation; same reason as the noncurrent sibling",
    "us-gaap:CommercialPaper":
        "may already be inside ShortTermBorrowings for the same filer; overlap is not established",
    "us-gaap:OtherShortTermBorrowings":
        "an 'other' residual whose disjointness from ShortTermBorrowings is not established",
    "us-gaap:DebtInstrumentFaceAmount":
        "instrument-level PRINCIPAL, not a consolidated carrying balance; never summed with carrying",
    "us-gaap:DebtInstrumentCarryingAmount":
        "instrument-level, not a consolidated balance; multiple instruments would double count",
    "us-gaap:LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths":
        "a contractual maturity schedule row, not a balance-sheet carrying amount",
    "us-gaap:ProceedsFromIssuanceOfLongTermDebt":
        "a cash-flow duration flow, not an instant balance",
    "ifrs-full:Borrowings":
        "IFRS total-borrowings element is not corroborated by the installed mapping; unverified",
    "ifrs-full:LeaseLiabilities":
        "lease obligations are a separate measure from borrowings",
    "us-gaap:Deposits":
        "deposit liabilities are a funding liability of a bank, not a borrowing in this measure",
}

# Scope pairs that cover overlapping obligations. A subtotal is never formed across an overlapping
# pair, and an aggregate never sits in the same sum as one of its own parts. Stored unordered.
_OVERLAPPING_SCOPES: FrozenSet[FrozenSet[str]] = frozenset(
    {
        frozenset({SCOPE_LONG_TERM_INCL_CURRENT, SCOPE_NONCURRENT}),
        frozenset({SCOPE_LONG_TERM_INCL_CURRENT, SCOPE_CURRENT_PORTION}),
        frozenset({SCOPE_CURRENT_ALL, SCOPE_CURRENT_PORTION}),
        frozenset({SCOPE_CURRENT_ALL, SCOPE_SHORT_TERM}),
        frozenset({SCOPE_COMBINED_TOTAL, SCOPE_NONCURRENT}),
        frozenset({SCOPE_COMBINED_TOTAL, SCOPE_CURRENT_PORTION}),
        frozenset({SCOPE_COMBINED_TOTAL, SCOPE_SHORT_TERM}),
        frozenset({SCOPE_COMBINED_TOTAL, SCOPE_LONG_TERM_INCL_CURRENT}),
        frozenset({SCOPE_COMBINED_TOTAL, SCOPE_CURRENT_ALL}),
    }
)

# Scope sets that together cover EVERY borrowing the issuer reports on this basis, so their sum is
# a defensible "identified borrowing components" subtotal. A set that leaves a maturity band
# unobserved (e.g. noncurrent + current portion with NO short-term borrowings line) is deliberately
# absent: summing it reproduces the exact figure the retained WMT outcome mislabelled "total debt"
# while short-term borrowings were still missing.
COMPLETE_BORROWING_PARTITIONS: Tuple[FrozenSet[str], ...] = (
    frozenset({SCOPE_NONCURRENT, SCOPE_CURRENT_PORTION, SCOPE_SHORT_TERM}),
    frozenset({SCOPE_LONG_TERM_INCL_CURRENT, SCOPE_SHORT_TERM}),
    frozenset({SCOPE_NONCURRENT, SCOPE_CURRENT_ALL}),
)

# Every admissible concept, as the extractor needs them: each is queried INDEPENDENTLY (the
# dividend-components precedent), never first-candidate-wins, because disjoint scopes are not
# alternative spellings of one another.
DEBT_COMPONENT_CONCEPTS: Tuple[str, ...] = tuple(DEBT_CONCEPTS)


def classify_debt_concept(qualified_concept: Optional[str]) -> Optional[DebtIdentity]:
    """The admissible identity for an EXACT qualified concept, or None when it is not admissible.

    Matching is exact on "<namespace>:<LocalName>". A bare local name, a different namespace, a
    case variant or an issuer extension concept returns None — unknown scope, never a guess.
    """
    if not isinstance(qualified_concept, str):
        return None
    return DEBT_CONCEPTS.get(qualified_concept.strip())


def scopes_overlap(first: str, second: str) -> bool:
    """True when two scopes cover overlapping obligations (so they must never be summed).

    A scope always overlaps itself: two observations of the SAME scope are either the same balance
    or a genuine conflict, and neither is a component pair.
    """
    return first == second or frozenset({first, second}) in _OVERLAPPING_SCOPES


def is_complete_borrowing_partition(scopes: FrozenSet[str]) -> bool:
    """True when this exact scope set covers every reported borrowing on one carrying basis."""
    return frozenset(scopes) in COMPLETE_BORROWING_PARTITIONS
