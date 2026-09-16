"""Generation-time attribution gate for model-authored explanations (the #805 path, step 4).

The `summary-2026-09-o` prompt condition halved the judge's unsupported-cause findings; what remains
is a model-authored "driven by / reflecting / due to" clause the filing never states for that line
(tasks/attribution-guard-plan-2026-09-17.md). This module is the code owner for that residue, in the
shape of ``forward_quote_gate``: every causal clause in an explanation slot is MEASURED against the
excerpt the model generated from, and DROPPED — the clause only, the movement stays — when
``AI_ATTRIBUTION_GATE`` is armed. Advisory-first: the audit persists on the row and the pipeline emits
the greppable ``attribution_unverified`` counter whether or not the flag is on.

What counts as verified: a source sentence that (a) is about the same subject — shares a content
token with the clause's own sentence, or with the P&L row's metric for table commentary — (b) itself
states a cause (carries a causal connective in the source's own words), and (c) carries the driver's
content tokens (coverage at or above the length-scaled threshold). Two figures moving together in the
source is therefore never a verification; only the filing's own attribution is.

Conservative by design, mirroring figure_trace and the quote gate:
- No source text → measure and drop nothing (callers pass the EXCERPT, the model's true prompt input).
- "attributable to <owner>" after income/loss/earnings is a measure name, not a cause; never a clause.
- Slots without a causal connective are untouched; verbatim quotes and evidence fields are exempt
  (already owned by the quote gate and evidence snap).
- Malformed values (non-strings) pass untouched.
- A drop removes ", driven by …" up to the clause end (an "offset" clause, a semicolon, or the
  sentence end) and repairs punctuation; nothing else in the slot changes.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.services.provenance_service import normalize_for_match

# Causal connectives a model uses to attach a driver to a movement. `attributable to` is guarded so the
# measure name "net income attributable to <owner>" never reads as a clause.
_CONNECTIVES = (
    r"driven (?:primarily |mainly |largely |principally )?by",
    r"reflecting",
    r"due (?:primarily |mainly |largely )?to",
    r"(?<!income )(?<!loss )(?<!earnings )(?<!net )(?<!\(loss\) )attributable (?:primarily |mainly )?to",
    r"as a result of", r"because of", r"owing to", r"led by", r"on the back of",
    r"helped by", r"supported by", r"boosted by", r"pressured by", r"weighed (?:down )?by",
    r"benefit(?:ed|ing|s|ted) from", r"amid", r"primarily (?:from|on|reflecting)", r"thanks to",
    r"attribut(?:es|ed|ing) (?:the [\w\s]{1,40}? )?to",
)
_LEAD_IN = r"(?:primarily |mainly |largely |principally |mostly |partly |partially |chiefly )?"
CONNECTIVE_RE = re.compile(r"\b(" + _LEAD_IN + r"(?:" + "|".join(_CONNECTIVES) + r"))\b", re.I)
# A filing states a cause in more ways than a summary does.
_SOURCE_CONNECTIVE_RE = re.compile(
    CONNECTIVE_RE.pattern
    + r"|\b(?:the result of|resulted? from|result(?:ed|ing) primarily|related to|in connection with"
    r"|impact of|increase[sd]? in|decrease[sd]? in|growth in|decline in|was due|were due|due primarily|as a result)\b",
    re.I,
)
_CLAUSE_END_RE = re.compile(r"(?:,\s*(?:partially |partly |more than )?offset|;|\.\s|\.$|\)\s*$|$)")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD_RE = re.compile(r"[a-z][a-z\-]{2,}")
_STEM_RE = re.compile(r"(?:ings?|ers?|es|s|ed|ly)$")
_STOP = frozenset("""the a an and or of to in on for by with from as at is are was were be been being this that these those it its
their his her our your we they he she which who whom whose than then there here into over under up down out off per vs versus
year years yoy qoq quarter quarters period periods prior current compared comparison increase increased increases increasing
decrease decreased decreases decreasing higher lower growth grew rose fell decline declined declines change changes changed net
total totals primarily mainly largely partially partly offset driven reflecting due attributable result because owing led amid
helped supported million billion thousand percent usd dollar dollars company companys firm firms group also both well other
others across during within between after before while more less most least much many some any each all""".split())
# Framing words a summary uses around a clause that are not the subject of the movement.
_FRAMING = frozenset({"management", "company", "filing", "firm", "attribut", "report", "said", "note", "state", "mda"})
_MIN_SOURCE_SENTENCE = 20
_AUDIT_TEXT_CAP = 160

# The model-authored explanation slots (path, kind). Verbatim quotes and evidence fields are exempt.
_PRINT_FIELDS = ("headline", "what_changed")
_LIQUIDITY_FIELDS = ("leverage", "liquidity", "working_capital")


def _tokens(text: str) -> set:
    out = set()
    for word in _WORD_RE.findall(text.lower()):
        if word in _STOP:
            continue
        out.add(_STEM_RE.sub("", word) if len(word) > 5 else word)
    return out


def _clauses(text: str) -> Iterator[Tuple[re.Match, str, str]]:
    """(connective match, driver clause, the clause's own sentence before the connective)."""
    for match in CONNECTIVE_RE.finditer(text):
        rest = text[match.end():]
        end = _CLAUSE_END_RE.search(rest)
        clause = (rest[: end.start()] if end else rest).strip(" ,")
        subject = text[: match.start()].rsplit(". ", 1)[-1]
        if _tokens(clause):
            yield match, clause, subject


def _source_index(source_text: str) -> List[Tuple[set, set, bool]]:
    """(sentence tokens, subject pool, states a cause). Filings often name the subject in one
    sentence and the cause in the next ("Net operating revenues increased 12%. The increase was
    driven by …"), so the subject pool is the sentence plus its predecessor."""
    out: List[Tuple[set, set, bool]] = []
    previous: set = set()
    for piece in _SENTENCE_SPLIT_RE.split(source_text):
        sentence = piece.strip()
        if len(sentence) < _MIN_SOURCE_SENTENCE:
            continue
        current = _tokens(sentence)
        out.append((current, current | previous, bool(_SOURCE_CONNECTIVE_RE.search(sentence))))
        previous = current
    return out


def _threshold(count: int) -> float:
    return 0.5 if count >= 4 else (0.67 if count == 3 else 1.0)


def _verify(clause: str, subject: str, index: List[Tuple[set, set, bool]]) -> Tuple[bool, float]:
    """Best coverage of the clause's tokens by a source sentence that states a cause about the subject."""
    clause_tokens = _tokens(clause)
    subject_tokens = _tokens(subject) - _FRAMING
    best = 0.0
    for sentence_tokens, subject_pool, states_cause in index:
        if not states_cause or (subject_tokens and not (subject_tokens & subject_pool)):
            continue
        coverage = len(clause_tokens & sentence_tokens) / len(clause_tokens)
        if coverage > best:
            best = coverage
    return best >= _threshold(len(clause_tokens)), round(best, 2)


def _drop_clause(text: str, match: re.Match, clause: str) -> str:
    """Remove ``<connective> <clause>`` and the separator before it; keep the movement and its end."""
    start = match.start()
    rest = text[match.end():]
    end = match.end() + rest.find(clause) + len(clause)
    before = text[:start].rstrip()
    after = text[end:]
    if before.endswith((",", ":", ";")):
        before = before[:-1].rstrip()
    if before.lower().endswith((" and", " which", " that", " as")):
        before = before.rsplit(" ", 1)[0].rstrip()
    after = after.lstrip(" ,")
    if after and not after.startswith((".", ";", ")")) and not before.endswith((".", ";")):
        joined = f"{before}, {after}"
    else:
        joined = f"{before}{after}"
    return re.sub(r"\s+([.;,)])", r"\1", joined).strip()


def _slots(sections: Dict[str, Any]) -> Iterator[Tuple[str, Any, Optional[str], Any, str]]:
    """(slot label, container, key, current value, subject anchor) for every model-authored slot."""
    print_section = sections.get("the_print")
    if isinstance(print_section, dict):
        for key in _PRINT_FIELDS:
            yield f"the_print.{key}", print_section, key, print_section.get(key), ""
        takeaways = print_section.get("key_takeaways")
        if isinstance(takeaways, list):
            for i, value in enumerate(takeaways):
                yield f"the_print.key_takeaways[{i}]", takeaways, i, value, ""
    results = sections.get("results_that_matter")
    table = results.get("table") if isinstance(results, dict) else None
    for i, row in enumerate(table or []):
        if isinstance(row, dict):
            yield f"results_that_matter.table[{i}].commentary", row, "commentary", row.get("commentary"), str(row.get("metric") or "")
    quality = sections.get("earnings_quality")
    if isinstance(quality, dict):
        yield "earnings_quality.operating_vs_one_time", quality, "operating_vs_one_time", quality.get("operating_vs_one_time"), ""
    for i, segment in enumerate(sections.get("segments") or []):
        if isinstance(segment, dict):
            yield f"segments[{i}].commentary", segment, "commentary", segment.get("commentary"), str(segment.get("segment") or "")
    liquidity = sections.get("balance_sheet_liquidity")
    if isinstance(liquidity, dict):
        for key in _LIQUIDITY_FIELDS:
            yield f"balance_sheet_liquidity.{key}", liquidity, key, liquidity.get(key), ""
        maturities = liquidity.get("maturities_covenants")
        if isinstance(maturities, list):
            for i, value in enumerate(maturities):
                yield f"balance_sheet_liquidity.maturities_covenants[{i}]", maturities, i, value, ""


def gate_attributions(sections: Dict[str, Any], source_text: str, armed: bool) -> Optional[Dict[str, Any]]:
    """Measure every causal clause in the model-authored explanation slots against ``source_text``;
    drop unverified clauses (the clause only) when ``armed``. Mutates ``sections`` in place (armed
    only). Returns the audit dict, or None when there was nothing to measure.

    ``source_text`` is the filing EXCERPT the model generated from. Callers gate ``armed`` on
    ``settings.AI_ATTRIBUTION_GATE``; this module stays settings-free (a pure leaf)."""
    if not isinstance(sections, dict) or not normalize_for_match(source_text):
        return None
    index = _source_index(source_text)
    if not index:
        return None
    checked = 0
    unverified: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    for slot, container, key, value, anchor in list(_slots(sections)):
        if not isinstance(value, str) or not value.strip():
            continue
        text = value
        # Walk clauses right-to-left so a drop never shifts the offsets of an earlier clause.
        for match, clause, subject in reversed(list(_clauses(value))):
            checked += 1
            verified, coverage = _verify(clause, anchor or subject, index)
            if verified:
                continue
            record = {"slot": slot, "connective": match.group(0), "clause": clause[:_AUDIT_TEXT_CAP], "coverage": coverage}
            unverified.append(record)
            if armed:
                text = _drop_clause(text, match, clause)
                dropped.append(record)
        if armed and text != value:
            container[key] = text
    if not checked:
        return None
    return {"checked": checked, "verified": checked - len(unverified), "unverified": unverified,
            "dropped": dropped, "armed": armed}


def audit_to_json(audit: Optional[Dict[str, Any]]) -> str:
    return json.dumps(audit or {}, ensure_ascii=False, sort_keys=True)
