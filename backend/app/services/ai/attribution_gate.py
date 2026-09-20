"""Generation-time attribution gate for model-authored explanations (the #805 path, step 4).

The `summary-2026-09-o` prompt condition halved the judge's unsupported-cause findings; what remains
is a model-authored "driven by / reflecting / due to" clause the filing never states for that line
(tasks/attribution-guard-plan-2026-09-17.md). This module is the code owner for that residue, in the
shape of ``forward_quote_gate``: every causal clause in an explanation slot is MEASURED against the
excerpt the model generated from. Advisory-first: the audit persists on the row and the pipeline emits
the greppable ``attribution_unverified`` counter whether or not a flag is on.

**This lexical measurement alone never deletes text.** Its drop decision was read by hand against the
filing for all 34 clauses it flagged across two judged runs and was right 47% of the time
(``tasks/review-evidence/pr805-path/attribution-gate-precision-2026-09-17.md``): about half the flags
are drivers the filing does state, reachable only through a label or an abbreviation the lexical
anchor cannot connect to the slot. A clause is therefore removed only when a MODEL verdict says the
filing does not state it (``attribution_verify``, ``settings.AI_ATTRIBUTION_VERIFY``) AND
``settings.AI_ATTRIBUTION_GATE`` is armed. Arming the gate without the verifier drops nothing and
records the refusal in the audit: the 47% measurement is encoded here, not left in a document.

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

Two-phase API: ``find_attributions`` is pure and returns every candidate with the source windows a
verifier needs; ``apply_attributions`` consumes verdicts and writes the audit. ``gate_attributions``
composes them for callers that only measure.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.services.provenance_service import normalize_for_match

# Causal connectives a model uses to attach a driver to a movement. `attributable to` is guarded so the
# measure name "net income attributable to <owner>" never reads as a clause.
_CONNECTIVES = (
    r"driven (?:primarily |mainly |largely |principally )?by",
    r"reflecting",
    r"due (?:primarily |mainly |largely )?to",
    r"attributable (?:primarily |mainly )?to (?!(?:common|controlling|non-?controlling|the parent|parent|shareholders|"
    r"shareowners|stockholders|unitholders|owners|members|ordinary|holders|the company|(?-i:[A-Z])))",
    r"as a result of", r"because of", r"owing to", r"led by", r"on the back of",
    r"helped by", r"supported by", r"boosted by", r"pressured by", r"weighed (?:down )?by",
    r"benefit(?:ed|ing|s|ted) from", r"amid", r"primarily (?:from|on|reflecting)", r"thanks to",
    r"attribut(?:es|ed|ing) (?:primarily |mainly |largely )?(?:the [\w\s]{1,40}? )?to",
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
_CLAUSE_END_RE = re.compile(
    r"(?:,\s*(?:partially |partly |more than )?offset|,\s*(?:and|while|whereas|but|which|with)\s|;|\.\s|\.$|\)\s*$|$)"
)

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
# Older retained summaries prefix segment commentary with a machine margin ("42% operating margin — ").
# Keep their audit parsing compatible; new generation no longer authors this unqualified ratio.
_MACHINE_PREFIX_RE = re.compile(r"^\s*-?\d+(?:\.\d+)?%\s+operating margin\s*[—–-]\s*")
_AUDIT_TEXT_CAP = 160
# What a verifier is shown per flagged clause: the source windows carrying the most of the clause's
# content words, chosen WITHOUT the subject anchor the lexical decision applies. The anchor is exactly
# what misfires, so the passage that would prove a driver stated must still reach the verifier.
_EVIDENCE_WINDOWS = 4
_EVIDENCE_WINDOW_CHARS = 600
# One bounded verification call per generation: beyond this many clauses the extra ones are reported
# unverifiable rather than silently unchecked, so a pathological summary cannot inflate the call.
MAX_VERIFIABLE_CLAUSES = 12

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


@dataclass
class _Window:
    """One candidate source passage: its tokens, the subjects it may speak for, and whether it states
    a cause in the filing's own words. ``text`` is the passage as a verifier would read it."""

    tokens: set
    subject_pool: set
    states_cause: bool
    text: str


@dataclass
class Candidate:
    """One causal clause the model wrote, with everything needed to judge and to remove it."""

    slot: str
    connective: str
    clause: str
    coverage: float
    evidence: List[str] = field(default_factory=list)
    container: Any = None
    key: Any = None
    value: str = ""
    match: Any = None
    # Preserve the identity the lexical pass already used; the model decider needs both the
    # actual pre-connective subject and a table/segment label when the commentary is elliptical.
    subject: str = ""
    anchor: str = ""

    def record(self) -> Dict[str, Any]:
        """The audit shape — text capped, no container references, no source passages."""
        return {"slot": self.slot, "connective": self.connective,
                "clause": self.clause[:_AUDIT_TEXT_CAP], "coverage": self.coverage}


def _source_index(source_text: str) -> List[_Window]:
    """One window per source piece: its tokens, subject pool, whether it states a cause, and its text.

    The excerpt is not clean prose: a filing sentence arrives line-broken into several pieces, a
    heading or table label names the subject of what follows it, and a cause stated as a lead-in to
    a list ("decreased primarily due to:" then bullets) belongs to every bullet. So a candidate is a
    piece with its two neighbours (the window), the subject pool reaches one piece further back, and
    the window states a cause when any of its pieces does."""
    pieces = [piece.strip() for piece in _SENTENCE_SPLIT_RE.split(source_text) if piece.strip()]
    tokens = [_tokens(piece) for piece in pieces]
    causes = [bool(_SOURCE_CONNECTIVE_RE.search(piece)) for piece in pieces]
    out: List[_Window] = []
    for i, piece in enumerate(pieces):
        if len(piece) < _MIN_SOURCE_SENTENCE:
            continue
        lo, hi = max(0, i - 1), min(len(pieces), i + 2)
        out.append(_Window(
            tokens=set().union(*tokens[lo:hi]),
            subject_pool=set().union(*tokens[lo:hi]) | (tokens[i - 2] if i >= 2 else set()),
            states_cause=any(causes[lo:hi]),
            text=" ".join(pieces[lo:hi])[:_EVIDENCE_WINDOW_CHARS],
        ))
    return out


def _threshold(count: int) -> float:
    return 0.5 if count >= 4 else (0.67 if count == 3 else 1.0)


def _verify(clause: str, subject: str, index: List[_Window]) -> Tuple[bool, float]:
    """Best coverage of the clause's tokens by a source window that states a cause about the subject."""
    clause_tokens = _tokens(clause)
    subject_tokens = _tokens(subject) - _FRAMING
    best = 0.0
    for window in index:
        if not window.states_cause or (subject_tokens and not (subject_tokens & window.subject_pool)):
            continue
        best = max(best, len(clause_tokens & window.tokens) / len(clause_tokens))
    return best >= _threshold(len(clause_tokens)), round(best, 2)


def _evidence(clause: str, index: List[_Window]) -> List[str]:
    """The passages a verifier must see: highest token overlap with the clause, ANCHOR IGNORED.

    Deliberately unanchored — a driver the filing states under a different label is precisely what the
    anchored decision misses, so the passage proving it must still be offered.

    Ranking matters as much as selection. A long clause's content words recur all over a filing, so
    many windows tie at full coverage and a naive tie-break by document order hands the verifier the
    boilerplate that happens to appear first (a "Trading Volume" definition, a risk factor about cost
    structure) while the MD&A sentence that actually states the driver, further down, never arrives.
    Measured on the 2026-09-17 verification run: three of six wrong drops were passages that simply
    were not supplied. So ties break first toward windows that state a cause in the filing's own
    words, then toward the tightest match (Jaccard — a window packed with the clause's words beats a
    long one that merely contains them), and only then by position."""
    clause_tokens = _tokens(clause)
    if not clause_tokens:
        return []
    def rank(item):
        i, window = item
        shared = len(clause_tokens & window.tokens)
        coverage = shared / len(clause_tokens)
        union = len(clause_tokens | window.tokens) or 1
        return (-coverage, not window.states_cause, -shared / union, i)
    seen: List[str] = []
    for i, window in sorted(enumerate(index), key=rank):
        if not (clause_tokens & window.tokens) or len(seen) >= _EVIDENCE_WINDOWS:
            break
        if window.text not in seen:
            seen.append(window.text)
    return seen


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


def find_attributions(sections: Dict[str, Any], source_text: str) -> Tuple[int, List[Candidate]]:
    """Pure: (clauses checked, candidates the source does not visibly support).

    Each candidate carries the source passages a verifier needs and the pointers a drop needs.
    ``source_text`` is the filing EXCERPT the model generated from; no source → nothing checked."""
    if not isinstance(sections, dict) or not normalize_for_match(source_text):
        return 0, []
    index = _source_index(source_text)
    if not index:
        return 0, []
    checked = 0
    candidates: List[Candidate] = []
    for slot, container, key, value, anchor in list(_slots(sections)):
        if not isinstance(value, str) or not value.strip():
            continue
        # Walk clauses right-to-left so a later drop never shifts an earlier clause's offsets.
        for match, clause, subject in reversed(list(_clauses(value))):
            checked += 1
            verified, coverage = _verify(clause, f"{anchor} {_MACHINE_PREFIX_RE.sub('', subject)}", index)
            if verified:
                continue
            candidates.append(Candidate(
                slot=slot, connective=match.group(0), clause=clause, coverage=coverage,
                evidence=_evidence(clause, index),
                container=container, key=key, value=value, match=match,
                subject=_MACHINE_PREFIX_RE.sub('', subject).strip(), anchor=anchor,
            ))
    return checked, candidates


def apply_attributions(
    checked: int,
    candidates: List[Candidate],
    verdicts: Optional[Dict[int, str]],
    armed: bool,
) -> Optional[Dict[str, Any]]:
    """Write the audit and, when ``armed`` AND a verdict says the filing does not state it, remove the
    clause (the clause only, in place). Returns None when there was nothing to measure.

    ``verdicts`` maps a candidate's index in ``candidates`` to "not_stated" / "stated" / anything else
    (treated as unknown). ``None`` means no verifier ran: nothing is ever dropped, however the gate is
    flagged — the lexical measurement alone is 47% precise and may not delete text on its own."""
    if not checked:
        return None
    decided = verdicts if isinstance(verdicts, dict) else {}
    dropped: List[Dict[str, Any]] = []
    by_slot: Dict[Tuple[int, Any], List[Candidate]] = {}
    for i, candidate in enumerate(candidates):
        if armed and verdicts is not None and decided.get(i) == "not_stated":
            by_slot.setdefault((id(candidate.container), candidate.key), []).append(candidate)
            dropped.append(candidate.record())
    for group in by_slot.values():
        # Right-to-left within a slot: `candidates` is already in that order, so later drops in the
        # same string never move an earlier clause's match offsets.
        text = group[0].value
        for candidate in group:
            text = _drop_clause(text, candidate.match, candidate.clause)
        group[0].container[group[0].key] = text
    audit = {
        "checked": checked,
        "verified": checked - len(candidates),
        "unverified": [c.record() for c in candidates],
        "dropped": dropped,
        "armed": armed,
        "decider": "model" if verdicts is not None else "none",
    }
    if verdicts is not None:
        audit["verdicts"] = {c.slot: decided.get(i, "unknown") for i, c in enumerate(candidates)}
    return audit


def gate_attributions(
    sections: Dict[str, Any],
    source_text: str,
    armed: bool,
    verdicts: Optional[Dict[int, str]] = None,
) -> Optional[Dict[str, Any]]:
    """Measure, and drop only what ``verdicts`` says the filing does not state. Mutates ``sections``
    in place (armed only). Returns the audit dict, or None when there was nothing to measure.

    Callers gate ``armed`` on ``settings.AI_ATTRIBUTION_GATE``; this module stays settings-free."""
    checked, candidates = find_attributions(sections, source_text)
    return apply_attributions(checked, candidates, verdicts, armed)


def audit_to_json(audit: Optional[Dict[str, Any]]) -> str:
    return json.dumps(audit or {}, ensure_ascii=False, sort_keys=True)
