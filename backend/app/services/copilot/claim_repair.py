"""Copilot claim repair extracted without changing admission behavior."""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Any, Callable, Optional

from app.services import copilot_tools
from app.services.copilot.fact_guards import (
    _CURRENCY_ALIASES,
    _CURRENCY_TOKEN,
    _adjacency_window,
    _fact_matches_adjacent_concept,
    _fact_matches_adjacent_currency,
    _fact_matches_adjacent_number,
    _valid_fact_provenance,
)

# ---------------------------------------------------------------------------------------------
# Server-owned repair for wholly uncited, explicitly supported annual claim shapes.
#
# The guards in fact_guards.py only ever REMOVE a marker the model placed wrongly. They cannot help the other
# failure shape the field reports keep surfacing: an answer that states one complete reported
# figure, correctly, having called no tool at all — right number, no attribution, nothing for a
# chip to open (retained evidence: the BABA 20-F revenue answer with empty tool results, empty
# citations and zero stripped markers). Asking the model to try again costs a call and still
# enforces nothing, so the server looks the figure up in the viewed filing itself and attaches a
# marker ONLY when the filing's own fact carries every identity the sentence asserts.
#
# Everything here is POSITIVE certification, which is the opposite of the falsification guards: an
# absent or ambiguous signal abstains. Amount coincidence is never enough, and neither is an
# annual-looking label — the fact must carry its own reported duration. Historical rows may
# still lack it and must abstain; fresh duration propagation does not prove every stored row.
# ---------------------------------------------------------------------------------------------

# Marks a fact this module looked up on the server's own initiative, so a diagnostic reading
# ``used_facts`` can tell it from a model tool call (which carries no origin key). It is absent
# from ``_fact_identity``'s key list and from ``fact_to_citation``'s, so it reaches neither the
# marker identity nor the citation.
_SERVER_LOOKUP_ORIGIN = "server_citation_lookup"

# The concepts this repair can certify, and the complete subject phrases that name them. Each
# phrase must name the CONSOLIDATED metric on its own: bare "sales" and any segment-qualified
# subject ("Cloud revenue") are deliberately absent, so those answers abstain instead of borrowing
# the consolidated fact. This is claim vocabulary, not the falsification vocabulary in
# ``_CONCEPT_SYNONYMS`` — that one may stay broad precisely because it can only KEEP a marker.
_REPAIRABLE_CLAIM_PHRASES: dict[str, tuple[str, ...]] = {
    "revenue": (
        "consolidated revenue", "consolidated revenues", "total net revenue", "total net revenues",
        "total net sales", "total revenue", "total revenues", "total sales", "net revenue",
        "net revenues", "net sales", "revenue", "revenues",
    ),
}
_CLAIM_PHRASE_CONCEPT = {p: c for c, phrases in _REPAIRABLE_CLAIM_PHRASES.items() for p in phrases}
_MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August",
                "September", "October", "November", "December")
_CLAIM_SCALES = {"thousand": 1e3, "million": 1e6, "billion": 1e9}

# The ONE finite claim shape this repair certifies: subject, explicit full fiscal end date, copula,
# native currency, amount and optional scale — and nothing else, because the pattern is anchored
# over the WHOLE answer. That anchor is what rejects multi-metric, comparative, causal, quoted,
# conditional, derived and incomplete-scope statements: a second proposition simply falls outside
# the match. Longest phrases first so the alternation binds the fullest subject.
# Case folds over ASCII letters only: Unicode re.IGNORECASE also folds ı/İ onto i, ſ onto s and the
# Kelvin sign onto k, so "net ſales" raised KeyError below and "thouſand" fell back to scale 1.0.
# Such an answer now does not match and abstains. Whitespace stays Unicode through (?u:\s): an NBSP
# is still a separator. \d is ASCII digits: a claim in non-ASCII digits also abstains.
_ANNUAL_FIGURE_CLAIM = re.compile(
    r"(?P<subject>" + "|".join(
        re.escape(p) for p in sorted(_CLAIM_PHRASE_CONCEPT, key=len, reverse=True)) + r")"
    r"(?u:\s)+(?:for|in)(?u:\s)+(?:the(?u:\s)+)?(?:fiscal(?u:\s)+)?year(?u:\s)+ended(?:(?u:\s)+on)?(?u:\s)+"
    r"(?P<month>" + "|".join(_MONTH_NAMES) + r")(?u:\s)+(?P<day>\d{1,2}),(?u:\s)+(?P<year>\d{4})"
    r"(?u:\s)+(?:was|were|totaled|totalled|amounted(?u:\s)+to)(?u:\s)+"
    r"(?P<currency>" + _CURRENCY_TOKEN + r")(?u:\s)*"
    r"(?P<amount>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:(?u:\s)*(?P<scale>billion|million|thousand))?"
    r"\.\Z",
    re.IGNORECASE | re.ASCII,
)

# Annual report forms: the ones whose period of report IS a full fiscal year. Same test
# ``facts_service._fiscal_period`` applies to decide which points get stamped ``fiscal_period="FY"``.
# NOTE this makes the FY label and the form the SAME signal, not two — see
# :func:`_fact_certifies_claim`. Amendments ("10-K/A") share the prefix.
_ANNUAL_REPORT_FORMS = ("10K", "20F", "40F")

# What counts as an annual slice, in days. One window, mirrored from the two places that already
# own it — ``facts_service._CF_ANNUAL_WINDOW`` and ``edgar.instance_extractor.DURATION_WINDOWS``
# for 10-K/20-F/40-F. ``test_copilot_citation_repair`` asserts the three stay equal, so a change
# there cannot silently widen what this module will certify.
_ANNUAL_DURATION_DAYS = (320, 390)


def _is_annual_report_form(filing_type: Any) -> bool:
    return str(filing_type or "").upper().replace("-", "").startswith(_ANNUAL_REPORT_FORMS)


def _iso_day(value: Any) -> Optional[str]:
    """The ISO date of a filing period field, whether it arrived as a string, date or datetime."""
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10]).isoformat()
        except ValueError:
            return None
    iso = getattr(value, "isoformat", None)
    return iso()[:10] if callable(iso) else None


def _plan_uncited_fact_citation(answer: str) -> Optional[dict]:
    """Read a wholly uncited answer as ONE complete reported annual figure, or return ``None``.

    Text only — no DB read and no filing metadata: this decides what the sentence CLAIMS, and the
    caller decides whether the filing supports it. ``answer`` must already be stripped (the caller
    holds the final answer). Returns the concept, claimed period end, canonical currency, the
    stated value with its display-rounding half-interval, and the offset the marker belongs at.
    """
    if re.search(r"\[\s*F?\s*\d+\s*\]", answer, re.IGNORECASE):
        return None  # already cites something — never rewrite it
    match = _ANNUAL_FIGURE_CLAIM.fullmatch(answer)
    if match is None:
        return None
    try:
        period_end = date(int(match["year"]),
                          _MONTH_NAMES.index(match["month"].capitalize()) + 1,
                          int(match["day"]))
    except ValueError:
        return None  # "February 30, 2025" is not a period end
    label = match["currency"].upper()
    currency = _CURRENCY_ALIASES.get(label, label)
    if not re.fullmatch(r"[A-Z]{3}", currency):
        return None
    digits = match["amount"].replace(",", "")
    scale = _CLAIM_SCALES.get((match["scale"] or "").lower(), 1.0)
    decimals = len(digits.partition(".")[2])
    return {
        "concept": _CLAIM_PHRASE_CONCEPT[match["subject"].lower()],
        "period_end": period_end.isoformat(),
        "currency": currency,
        "value": float(digits) * scale,
        # The filing value must ROUND to the numeral exactly as written — half a unit of the last
        # stated digit, at the stated scale. "996,347 million" admits 5e5; "996.3 billion" 5e7.
        "tolerance": 0.5 * (10.0 ** -decimals) * scale,
        # The claim ends with its terminal period; the marker goes just before it.
        "insert_at": match.end() - 1,
    }


# Reuse the existing annual revenue clause verbatim, with its flags; only this explicit second
# clause is admitted.
_PAIRED_ANNUAL_CLAIM = re.compile(
    _ANNUAL_FIGURE_CLAIM.pattern.removesuffix(r"\.\Z")
    + r"(?P<separator>, and net income was )"
    + r"(?P<income_currency>" + _CURRENCY_TOKEN + r")(?u:\s)*"
    + r"(?P<income_amount>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    + r"(?:(?u:\s)*(?P<income_scale>billion|million|thousand))?\.\Z", _ANNUAL_FIGURE_CLAIM.flags,
)


def _repair_paired_annual_claim(answer: str, *, filing: Any, accession: Optional[str],
                                currency: Optional[str], register: Callable[[dict], str]) -> str:
    """Certify both distinct annual operands before registering either; preserve prose bytes."""
    match = _PAIRED_ANNUAL_CLAIM.fullmatch(answer)
    if match is None:
        return answer
    first = _plan_uncited_fact_citation(answer[:match.start("separator")] + ".")
    # Parse the second explicit amount using the unchanged scalar grammar. This temporary
    # string is a parser input only, never user-visible prose or evidence for annual duration.
    second = _plan_uncited_fact_citation(
        f"Revenue for the year ended {match['month']} {match['day']}, {match['year']} was "
        f"{match['income_currency']}{match['income_amount']} {match['income_scale'] or ''}".rstrip() + "."
    )
    if first is None or second is None:
        return answer
    second.update(concept="net_income", insert_at=len(answer) - 1)
    claims = [first, second]
    facts = []
    previous = 0
    for claim in claims:
        fact = copilot_tools.run_tool("get_financial_fact", {"concept": claim["concept"]},
                                     getattr(filing, "company_id", None),
                                     accession_number=accession, reporting_currency=currency)
        if (not isinstance(fact, dict) or "error" in fact
                or not _valid_fact_provenance(fact, accession, currency)
                or not _fact_certifies_claim(fact, claim, filing)):
            return answer
        window = _adjacency_window(answer[:claim["insert_at"]] + " ", claim["insert_at"] + 1, previous)
        if not (_fact_matches_adjacent_number(fact, window)
                and _fact_matches_adjacent_concept(fact, window)
                and _fact_matches_adjacent_currency(fact, window)):
            return answer
        facts.append(fact)
        previous = claim["insert_at"]
    if any(facts[0].get(key) != facts[1].get(key) for key in ("period_start", "period_end", "unit", "accession")):
        return answer
    # No registration until every operand and the relationship have certified.
    markers = []
    for fact in facts:
        fact["_origin"] = _SERVER_LOOKUP_ORIGIN
        markers.append(register(fact))
    for claim, marker in reversed(list(zip(claims, markers))):
        offset = claim["insert_at"]
        answer = f"{answer[:offset]} [{marker}]{answer[offset:]}"
    return answer


def _fact_certifies_claim(fact: dict, claim: dict, filing: Any) -> bool:
    """True only when the viewed filing's own fact carries EVERY identity the claim asserts.

    The claim says "for the fiscal year ended <date>", so the fact must be shown to COVER that
    year. Only its own reported duration shows that, and nothing else here is a substitute:

    * The **form** cannot. ``facts_service._fiscal_period`` derives ``FY`` from the form, so the
      annual-form test and the ``FY`` label are one signal wearing two hats, not two signals.
    * The **companyfacts fallback** cannot. ``edgar/xbrl_companyfacts.py``'s ``filter_and_sort`` only
      *ranks* the durations sharing a period end and keeps the best one; a sole quarterly point is
      not rejected. Both fallback and selected-instance paths now retain the selected source
      start, so an FY-labelled quarterly point can be rejected by its actual duration. Older
      persisted rows may still have NULL starts and must continue to abstain.
    * **Comparative cadence** cannot: matching period ends a year apart are consistent with a
      quarterly point sitting among annual ones.

    So a fact with no ``period_start`` abstains, however annual everything around it looks. Adding
    a *verified* chip to an annual sentence on a possibly-quarterly figure would be a new error of
    our own making, which is worse than the uncited prose it replaces.
    """
    if not _is_annual_report_form(getattr(filing, "filing_type", None)):
        return False
    if fact.get("kind") or fact.get("value_kind") or fact.get("source_facts"):
        return False  # a derived result never certifies a reported figure
    if fact.get("concept") != claim["concept"] or fact.get("fiscal_period") != "FY":
        return False
    claimed = claim["period_end"]
    if fact.get("period_end") != claimed or _iso_day(getattr(filing, "period_of_report", None)) != claimed:
        return False
    # The binding proof: the fact's own reported duration must span an annual slice.
    start, end = _iso_day(fact.get("period_start")), _iso_day(fact.get("period_end"))
    if start is None or end is None:
        return False
    low, high = _ANNUAL_DURATION_DAYS
    if not low <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= high:
        return False
    if copilot_tools.canonical_unit(fact.get("unit")) != claim["currency"]:
        return False
    value = fact.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return False
    # Signed: a negative filing value can never certify a positively stated amount.
    return abs(float(value) - claim["value"]) <= claim["tolerance"]


def _repair_uncited_fact_claim(answer: str, *, filing: Any, accession: Optional[str],
                               currency: Optional[str], register: Callable[[dict], str]) -> str:
    """Attach source-owned markers to supported certified uncited claims; otherwise abstain.

    Inserts the marker and nothing else — every other byte of the answer, punctuation included,
    survives. The existing resolver still owns numbering, placement and citation provenance.
    """
    claim = _plan_uncited_fact_citation(answer)
    if claim is None:
        return _repair_paired_annual_claim(answer, filing=filing, accession=accession,
                                           currency=currency, register=register)
    # The existing DB-only, accession-bound owner, called with its plainest existing selector. It
    # opens and closes its own session, reaches no SEC endpoint and runs no model.
    fact = copilot_tools.run_tool("get_financial_fact", {"concept": claim["concept"]},
                                  getattr(filing, "company_id", None),
                                  accession_number=accession, reporting_currency=currency)
    if not isinstance(fact, dict) or "error" in fact or "value" not in fact:
        return answer  # missing, errored or ambiguous evidence abstains
    if not _valid_fact_provenance(fact, accession, currency) or not _fact_certifies_claim(fact, claim, filing):
        return answer
    # Last check, on the exact window the resolver will compute (no other marker exists, so the
    # window is bounded only by its own length). The guards are falsification-only and are NOT the
    # certification above; this just means we never ship a marker the resolver would strip.
    window = _adjacency_window(answer[:claim["insert_at"]] + " ", claim["insert_at"] + 1, 0)
    if not (_fact_matches_adjacent_number(fact, window)
            and _fact_matches_adjacent_concept(fact, window)
            and _fact_matches_adjacent_currency(fact, window)):
        return answer
    fact["_origin"] = _SERVER_LOOKUP_ORIGIN
    return f"{answer[:claim['insert_at']]} [{register(fact)}]{answer[claim['insert_at']:]}"
