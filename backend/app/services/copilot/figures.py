"""How a figure stated in Copilot prose reads against a fact: its magnitude and its sign.

The value guard (``fact_guards._fact_matches_adjacent_number``) keeps a fact marker only when some
figure in its claim span passes both readings here; the currency guard picks out the fact's figure by
magnitude alone. Both readings are falsification-only: they reject a figure that states a different
magnitude or the opposite sign, and never demand wording the prose may lack.
"""
from __future__ import annotations

import re

_SCALE_WORDS = {"billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
# A figure written negative: a minus sign on it ("-$1.2B", "$-1.2B", "−15.3%"), or accounting
# parentheses around it alone ("(1,200)", "$(1.2) billion", "($1.2B)", "(15.3%)"). A hyphen after a
# word character is a range or a compound ("10-15%"); a dash followed by a space is a list bullet.
_MINUS_BEFORE = re.compile(r"(?<!\w)[-−]\$?\Z")
_PAREN_BEFORE = re.compile(r"\(\s*\$?\s*\Z")
_PAREN_AFTER = re.compile(r"\s*\)")
# Wording that states a value below zero or a fall, and wording that states a rise.
_DECLINE_CUES = re.compile(
    r"\b(?:loss(?:es)?|lost|deficit|negative|minus|declin\w*|decreas\w*|fell|fall(?:s|ing)?|drop\w*|"
    r"dipped|down|lower(?:ed)?|contract(?:ed|ing|ion)|shr[aiu]nk\w*|slid|slipped|slump\w*|plung\w*|"
    r"plummet\w*|tumbl\w*|sank|eased|weaken\w*|soften\w*|retreat\w*|reduc\w*|used in|outflows?)\b"
)
_GROWTH_CUES = re.compile(
    r"\b(?:gr[eo]w\w*|rose|ris(?:e|es|ing)|increas\w*|up|higher|gain\w*|climb\w*|jump\w*|surg\w*|"
    r"expan\w*|improv\w*|rebound\w*|recover\w*|accelerat\w*)\b"
)


def _close(a: float, b: float, *, rel: float = 0.01, absolute: float = 0.011) -> bool:
    return abs(a - b) <= max(rel * max(abs(a), abs(b)), absolute)


def _is_year(token: re.Match) -> bool:
    """A bare 4-digit integer that reads as a year (1900-2100, no $, no scale suffix) is context."""
    num = float(token.group(2).replace(",", ""))
    return not token.group(1) and not token.group(3) and num.is_integer() and 1900 <= num <= 2100


def _figure_matches_value(fact: dict, token: re.Match) -> bool:
    """Magnitude only: whether a ``_NUMBER_TOKEN`` match renders the fact's value at display rounding.

    Only a bare figure may be a display-scaled rendering ("81.46" for $81.46B). A figure carrying its
    own scale word or dollar sign states its magnitude ("$1.2 million", "$2.04"), so it is read at face
    value: "$1.2 million" on a $1.2B fact is a 1,000x understatement, not a rendering of it.
    """
    try:
        value = abs(float(fact.get("value")))
    except (TypeError, ValueError):
        return True
    dollar, suffix = token.group(1), (token.group(3) or "").lower()
    num = float(token.group(2).replace(",", ""))
    if fact.get("kind") in ("yoy_growth", "margin"):
        # Prose states percents ("17.9%" or bare "17.9"); the fact value is a fraction.
        return suffix in ("%", "") and _close(num, value * 100.0, absolute=0.11)
    if suffix == "%":
        return False
    if dollar or suffix:
        return _close(num * _SCALE_WORDS.get(suffix, 1.0), value)
    return any(_close(num, value / d) for d in (1.0, 1e3, 1e6, 1e9))


def _figure_written_negative(text: str, token: re.Match) -> bool:
    before = text[:token.start(2)]
    return bool(_MINUS_BEFORE.search(before)
                or (_PAREN_BEFORE.search(before) and _PAREN_AFTER.match(text, token.end())))


def _figure_sign_agrees(fact: dict, span: str, token: re.Match, clause: str) -> bool:
    """False when the figure ``token`` in the claim ``span`` states the opposite sign of the fact.

    The same rule as the server's own claim certifier: a negative filing value never certifies a
    positively stated amount. A negative fact needs its figure written negative or a loss/decline cue
    anywhere in the span (the loss is often named in an earlier clause: "Net loss for 2024, after
    charges, was $1.2B"); "net income was $1.2B" on a loss is a profit claim. A positive rate is
    contradicted by a figure written negative, and a positive growth rate also by a decline cue in the
    figure's own ``clause`` with no growth cue there ("Revenue fell 15.3%"). A margin is a level, so
    a decline cue says nothing about its sign ("gross margin fell to 17.9%"). A positive amount is not
    sign-checked: parentheses around one are usually an aside ("Revenue ($96.8B) rose").
    """
    value = float(fact.get("value"))
    negative = _figure_written_negative(span, token)
    if value < 0:
        return negative or bool(_DECLINE_CUES.search(span.lower()))
    kind = fact.get("kind")
    if value == 0 or kind not in ("yoy_growth", "margin"):
        return True
    low = clause.lower()
    stated_decline = kind == "yoy_growth" and _DECLINE_CUES.search(low) and not _GROWTH_CUES.search(low)
    return not (negative or stated_decline)
