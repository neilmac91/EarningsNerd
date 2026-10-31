"""How a figure stated in Copilot prose reads against a fact: its magnitude and its sign.

The value guard (``fact_guards._fact_matches_adjacent_number``) keeps a fact marker only when some
figure in its claim span passes both readings here; the currency guard picks out the fact's figure by
magnitude alone. Both readings are falsification-only: they reject a figure only when it states a
different magnitude or the prose states the opposite sign, and wording that says neither keeps the
marker. The known false keeps and false strips are listed in ``_figure_sign_agrees`` and, for the
magnitude reading, in ``_figure_matches_value``.
"""
from __future__ import annotations

import re
from typing import Optional

_SCALE_WORDS = {"trillion": 1e12, "tn": 1e12, "t": 1e12, "billion": 1e9, "bn": 1e9, "b": 1e9,
                "million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
# What may sit between a minus sign or an article and the figure's digits: emphasis and one currency
# label, `$` with up to three letters before it (US$, NT$, HK$), €, £, ¥, or an uppercase code (RMB).
_UP_TO_DIGITS = r"[*_]*(?:(?:[A-Z]{0,3}\$|[€£¥]|[A-Z]{3})\s*)?[*_]*\Z"
# A figure written negative: a minus sign or the word on it ("-$1.2B", "−€1.2B", "-RMB1.2B",
# "negative 15.3%"), or accounting parentheses around it alone ("(1,200)", "$(1.2) billion",
# "($1.2B)", "(15.3)%"). A hyphen after a word character is a range or a compound ("10-15%"); a dash
# followed by a space is a list bullet. The figure's own `$` and scale word may sit outside its
# parentheses ("$(1.2) million").
_MINUS_BEFORE = re.compile(r"(?:(?<!\w)[-−]|\b(?i:negative|minus)\s+)" + _UP_TO_DIGITS)
_PAREN_OPEN = re.compile(r"(\$)?\s*\(\s*\$?\s*\Z")
_PAREN_CLOSE = re.compile(r"\s*\)\s*(%|trillion|billion|million|thousand|tn|bn|[bmkt](?![a-z]))?", re.IGNORECASE)
# Words that state a value below zero; the subject of a loss, whose change reads inverted ("the net
# loss narrowed" is a rise); and the metric names that, on an unsigned figure, state a positive level.
_SIGN_CUES = re.compile(r"\b(?:loss(?:es)?|lost|deficits?|negative|minus|used|spent|outflows?|burn\w*)\b")
_LOSS_SUBJECT = re.compile(r"\b(?:loss(?:es)?|deficits?)\b")
_LEVEL_NAMES = re.compile(
    r"\b(?:income|profit\w*|earn\w*|eps|margins?|cash flows?|equity|working capital|provided|generat\w*|inflows?)\b"
)
# The label a figure follows ("Net income: $1.2B", "**Net income:** $1.2B"), which names it although
# the colon ends a clause; and a figure used attributively ("a $1.2B [F1] loss", "a roughly €1.2B [F1]
# loss", "an RMB1.2B [F1] loss", "a **$1.2B** [F1] loss"), whose noun follows the marker, beyond the
# claim span. Between the article and the figure only a hedge adverb, a currency label and emphasis
# may sit: each still needs that noun. An adjective that completes the amount's own noun phrase ("a
# record $1.2B", "an estimated $1.2B") does not, and a comparative states a margin's level ("a
# narrower 5.2%").
_LABEL = re.compile(r"([^;:()—–.,]*):[\s*_]*\Z")
_ATTRIBUTIVE = re.compile(r"\b[Aa]n?\s+(?:(?:roughly|approximately|nearly|almost)\s+)?" + _UP_TO_DIGITS)
# Wording that states a fall ("negative growth" is one), and wording that states a rise.
_DECLINE_CUES = re.compile(
    r"\b(?:declin\w*|decreas\w*|fell|fall(?:s|ing)?|drop\w*|dipped|down|lower(?:ed)?|contract(?:ed|ing|ion)|"
    r"shr[aiu]nk\w*|slid|slipped|slump\w*|plung\w*|plummet\w*|tumbl\w*|sank|eased|weaken\w*|soften\w*|"
    r"retreat\w*|reduc\w*|negative\s+growth)\b"
)
_GROWTH_CUES = re.compile(
    r"\b(?:(?<!negative\s)gr[eo]w\w*|rose|ris(?:e|es|ing)|increas\w*|up|higher|gain\w*|climb\w*|jump\w*|"
    r"surg\w*|expan\w*|improv\w*|rebound\w*|recover\w*|accelerat\w*)\b"
)
# The subject of a causal verb before the figure names the cause, not the figure: in "higher rates
# drove a 15.3% [F1] decline" the rate's own direction follows the marker. "Boosted" states a rise
# and "weighed on" a fall of what follows them.
_CAUSE = re.compile(
    r"\b(?:drove|driv(?:e|es|ing)|caus(?:e|ed|es|ing)|(?:led|leads?|leading)\s+to|result(?:ed|s|ing)?\s+in|"
    r"push(?:ed|es|ing)?|(boost(?:ed|s|ing)?)|(weigh(?:ed|s|ing)?\s+on))\b",
    re.IGNORECASE,
)


def _close(a: float, b: float, *, rel: float = 0.01, absolute: float = 0.011) -> bool:
    return abs(a - b) <= max(rel * max(abs(a), abs(b)), absolute)


def _is_year(token: re.Match) -> bool:
    """A bare 4-digit integer that reads as a year (1900-2100, with no $ or scale suffix on it or on
    parentheses around it alone: "$(2,023) million" is a figure) is context."""
    num = float(token.group(2).replace(",", ""))
    around = _parens(token)
    if around and (around[0].group(1) or around[1].group(1)):
        return False
    return not token.group(1) and not token.group(3) and num.is_integer() and 1900 <= num <= 2100


def _parens(token: re.Match) -> Optional[tuple[re.Match, re.Match]]:
    """The accounting parentheses around the figure ``token`` alone, as (opening, closing) matches."""
    opened = _PAREN_OPEN.search(token.string, 0, token.start(2))
    closed = opened and _PAREN_CLOSE.match(token.string, token.end())
    return (opened, closed) if closed else None


def _figure_extent(token: re.Match) -> tuple[int, int]:
    """Where the figure sits in its text, including parentheses around it alone and their unit."""
    around = _parens(token)
    return (around[0].start(), around[1].end()) if around else (token.start(), token.end())


def _figure_matches_value(fact: dict, token: re.Match) -> bool:
    """Magnitude only: whether a ``_NUMBER_TOKEN`` match renders the fact's value at display rounding.

    Only a bare figure may be a display-scaled rendering ("81.46" for $81.46B). A figure carrying its
    own scale word or dollar sign, inside or outside accounting parentheses, states its magnitude
    ("$1.2 million", "$(1.2) million", "$2.04"), so it is read at face value: "$1.2 million" on a
    $1.2B fact is a 1,000x understatement, not a rendering of it. Known false strip: a scale stated
    only in a label or a table header is not read ("| Revenue ($B) | $1.2 [F1] |", "Revenue (in
    billions): $1.2 [F1]").
    """
    try:
        value = abs(float(fact.get("value")))
    except (TypeError, ValueError):
        return True
    dollar, suffix = bool(token.group(1)), (token.group(3) or "").lower()
    around = _parens(token)
    if around:
        dollar, suffix = dollar or bool(around[0].group(1)), suffix or (around[1].group(1) or "").lower()
    num = float(token.group(2).replace(",", ""))
    if fact.get("kind") in ("yoy_growth", "margin"):
        # Prose states percents ("17.9%" or bare "17.9"); the fact value is a fraction.
        return suffix in ("%", "") and _close(num, value * 100.0, absolute=0.11)
    if suffix == "%":
        return False
    if dollar or suffix:
        return _close(num * _SCALE_WORDS.get(suffix, 1.0), value)
    return any(_close(num, value / d) for d in (1.0, 1e3, 1e6, 1e9))


def _written_negative(token: re.Match, *, rate: bool = False) -> bool:
    """Whether the figure itself is written negative (see ``_MINUS_BEFORE``). On a positive rate only
    the table form "(15.3)%" counts as parentheses: "(15.3%)" in prose is usually an aside ("revenue
    rose to $96.8B (15.3%)"), and an aside cannot contradict the rate."""
    if _MINUS_BEFORE.search(token.string, 0, token.start(2)):
        return True
    around = _parens(token)
    return bool(around) and (not rate or around[1].group(1) == "%")


def _stated_direction(token: re.Match, clause: slice) -> int:
    """+1 when the figure's clause states a rise, -1 a fall, and 0 when it states both, neither, or
    names a loss, whose change reads inverted: "the net loss narrowed 15.3%" is a positive growth
    rate. After a causal verb before the figure, only the verb and what follows it are read."""
    causes = list(_CAUSE.finditer(token.string, clause.start, token.start(2)))
    verb = causes[-1] if causes else None
    low = token.string[verb.start() if verb else clause.start:clause.stop].lower()
    if _LOSS_SUBJECT.search(low):
        return 0
    rise = bool(_GROWTH_CUES.search(low) or verb and verb[1])
    fall = bool(_DECLINE_CUES.search(low) or verb and verb[2])
    return int(rise) - int(fall)


def _figure_sign_agrees(fact: dict, token: re.Match, clause: slice) -> bool:
    """False when the prose states the opposite sign of the fact for the figure ``token``.

    ``token.string`` is the claim span and ``clause`` the slice of it that is the figure's own clause.
    The server's claim certifier sets the rule: a negative filing value never certifies a positively
    stated amount. Only stated wording contradicts:

    * A negative amount or margin, written unsigned, is contradicted when its own clause, or the
      label it follows, names it as a positive level: a profit-type metric name, with no sign word
      anywhere in the span ("net income was $1.2B", "Net income: $1.2B", or "net income fell to
      $1.2B": a direction word states a change, not a sign). An unsigned figure that names no
      metric keeps its marker ("Net loss was $1.2B [F1], compared with $0.8B [F2]"), and so does one
      used attributively, whose noun follows the marker ("a $1.2B [F1] loss", "a roughly €1.2B [F1]
      loss"; see ``_ATTRIBUTIVE``).
    * A negative growth rate, written unsigned, is contradicted by a rise stated in its clause
      ("revenue grew 15.3%" on a decline), though not in the subject of a causal verb before the
      figure ("higher rates drove a 15.3% [F1] decline"; see ``_CAUSE``).
    * A positive rate is contradicted by a figure written negative, and a positive growth rate also
      by a fall stated in its clause ("revenue fell 15.3%"), read the same way. A margin is a level,
      so a fall says nothing about its sign ("gross margin fell to 17.9%"). A positive amount is not
      sign-checked.

    Known false keeps: a sign word anywhere in the span vouches even when it names another item
    ("despite a gross loss, net income was $1.2B"); a profit name in an earlier clause, or before a
    parenthesis, is not read ("net income, after charges, was $1.2B", "net income (GAAP) was
    $1.2B"); a negative amount named without a profit-type word ("the bottom line was $1.2B") or
    used attributively before a profit noun ("a $1.2B profit"); a rate whose direction noun follows
    the marker ("revenue posted a 15.3% [F1] decline" on a rise, "higher prices drove a 15.3% [F1]
    increase" on a fall), or whose direction is stated only before a causal verb, which is not read
    even where it names the figure's own item ("revenue grew as higher prices drove a 15.3% [F1]
    rise" on a fall); on a negative rate, "(15.3%)" reads as written negative even after a rise
    word ("revenue grew strongly (15.3%)"); and a rate's clause that names any loss is not read for
    direction ("revenue fell 15.3% as losses mounted"). Known false strips: a profit-named loss
    figure whose sign noun follows the marker after an adjective, which cannot be told apart from a
    stated profit ("net income swung to a record $1.2B [F1] loss" reads as "net income was a record
    $1.2B"; also "an estimated" and the comparatives "a wider", "a deeper"); and the subject of a
    causal verb ``_CAUSE`` does not list ("lower costs lifted operating income 15.3% [F1]" on a rise).
    """
    value, kind = float(fact.get("value")), fact.get("kind")
    if value < 0:
        if _written_negative(token):
            return True
        if kind == "yoy_growth":
            return _stated_direction(token, clause) <= 0
        if _ATTRIBUTIVE.search(token.string, 0, token.start(2)):
            return True
        label = _LABEL.search(token.string, 0, _figure_extent(token)[0])
        names = (token.string[clause] + (label.group(1) if label else "")).lower()
        return not _LEVEL_NAMES.search(names) or bool(_SIGN_CUES.search(token.string.lower()))
    if value == 0 or kind not in ("yoy_growth", "margin"):
        return True
    if _written_negative(token, rate=True):
        return False
    return kind == "margin" or _stated_direction(token, clause) >= 0
