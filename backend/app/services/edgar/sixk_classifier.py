"""Deterministic 6-K pre-classifier (wave-3 W3-8b).

A 6-K has no item structure; what it *is* (an earnings release, a governance notice, or some
other press release) decides how it should be summarised. Production used to leave that
judgement to the model inside one generic prompt. This module makes the decision before the
model call, from the exhibit text alone, with no network and no model, so the choice is
reproducible, testable and recorded on the stored summary (``raw_summary["sixk_class"]``).

Three classes, matching the governing design (``tasks/handover-wave3-2026-09.md`` W3-8b):

- ``earnings``      results/interim releases: period results with several monetary figures
- ``governance``    AGM/EGM notices and results, board or officer changes, dividend declarations,
                    buyback authorisations, articles/proxy matters, with no results
- ``press_release`` everything else (product, transaction, capital-action, regulatory returns,
                    and any text too thin to classify)

The rules are counts of fixed cue phrases over a bounded prefix of the text; ties fall to
``press_release`` so an ambiguous filing gets the neutral prompt rather than a fabricated
results narrative. Exchange monthly returns (HKEX "Monthly Return") carry ``dividend``/``board``
words without being governance events; they are pinned to ``press_release`` explicitly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

SixKClass = Literal["earnings", "governance", "press_release"]
SIXK_CLASSES: tuple[SixKClass, ...] = ("earnings", "governance", "press_release")

# Bound the scan so a pathological multi-exhibit filing cannot dominate the counts.
_SCAN_CHARS = 60_000

_EARNINGS_CUES = re.compile(
    r"\b(results|revenue|revenues|net sales|total net sales|net income|net profit|net earnings|"
    r"earnings per share|earnings per ads|operating income|operating profit|gross margin|"
    r"quarter ended|three months ended|six months ended|nine months ended|half[- ]year|"
    r"interim results|fiscal (?:year|quarter)|guidance|outlook)\b",
    re.IGNORECASE,
)
_GOVERNANCE_CUES = re.compile(
    r"\b(annual general meeting|extraordinary general meeting|general meeting|agm|egm|"
    r"board of directors|appoint(?:ed|ment|s)|resign(?:ed|ation|s)|retire(?:d|ment)|"
    r"dividend|share repurchase|repurchase program|buy-?back|proxy|articles of association|"
    r"notice of meeting|shareholders? meeting|nominat(?:ed|ion))\b",
    re.IGNORECASE,
)
# A monetary amount with a currency marker; several of these are what distinguish a results
# release from a notice that merely mentions revenue in passing.
_MONEY = re.compile(
    r"(?:US\$|HK\$|NT\$|S\$|A\$|C\$|\$|€|£|¥|RMB|DKK|SEK|NOK|CHF|JPY|EUR|USD|GBP)\s?\d[\d,.]*"
    r"(?:\s?(?:million|billion|thousand|mn|bn|m|b))?",
    re.IGNORECASE,
)
# Exchange periodic returns (e.g. HKEX FF301 "Monthly Return for Equity Issuer") are regulatory
# forms, not governance events, whatever cue words they carry.
_REGULATORY_RETURN = re.compile(
    r"monthly return for equity issuer|monthly return on movements? in securities|"
    r"next day disclosure return",
    re.IGNORECASE,
)

_EARNINGS_MIN_CUES = 4
_EARNINGS_MIN_MONEY = 8
_GOVERNANCE_MIN_CUES = 3


@dataclass(frozen=True)
class SixKClassification:
    sixk_class: SixKClass
    earnings_cues: int
    governance_cues: int
    money_tokens: int
    regulatory_return: bool

    def as_audit(self) -> dict:
        """Compact, JSON-safe record for ``raw_summary["sixk_class_audit"]``."""
        return {
            "class": self.sixk_class,
            "earnings_cues": self.earnings_cues,
            "governance_cues": self.governance_cues,
            "money_tokens": self.money_tokens,
            "regulatory_return": self.regulatory_return,
        }


def classify_sixk_text(text: str | None) -> SixKClassification:
    """Classify a 6-K from its grounding text. Never raises; empty text is ``press_release``."""
    scan = (text or "")[:_SCAN_CHARS]
    earnings = len(_EARNINGS_CUES.findall(scan))
    governance = len(_GOVERNANCE_CUES.findall(scan))
    money = len(_MONEY.findall(scan))
    regulatory = bool(_REGULATORY_RETURN.search(scan))
    if regulatory:
        cls: SixKClass = "press_release"
    elif earnings >= _EARNINGS_MIN_CUES and money >= _EARNINGS_MIN_MONEY:
        cls = "earnings"
    elif governance >= _GOVERNANCE_MIN_CUES:
        cls = "governance"
    else:
        cls = "press_release"
    return SixKClassification(cls, earnings, governance, money, regulatory)
