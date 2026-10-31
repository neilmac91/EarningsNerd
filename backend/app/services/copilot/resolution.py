"""Copilot resolution extracted without changing admission behavior."""
from __future__ import annotations

import re
from typing import Optional

from app.services import copilot_tools
from app.services.copilot.fact_guards import (
    _NUMBER_TOKEN,
    _adjacency_window,
    _claim_span_start,
    _fact_matches_adjacent_concept,
    _fact_matches_adjacent_currency,
    _fact_matches_adjacent_number,
)

_COPILOT_MARKER_RE = re.compile(r"\[(F?\s*\d+)\]", re.IGNORECASE)
def count_uncited_figures(answer: str, valid_count: Optional[int] = None) -> tuple[int, int]:
    """Count financial-looking figures in a FINAL answer and how many lack a citation.

    Returns ``(figure_count, uncited_count)``. A figure is "cited" when it falls inside some
    marker's claim span (the same ``_adjacency_window`` rule the placement guards use). This is
    the COVERAGE telemetry: the misplacement guards convert wrongly-cited figures into UNCITED
    ones, so trust monitoring needs both counters — misplaced (stripped) and uncited (shipped
    without provenance).

    "Financial-looking" is deliberately narrower than the guards' matcher: a token counts only
    with a $ sign, a scale/percent suffix, a decimal point, or a non-year integer >= 1000 —
    so counts like "3 segments" and years never inflate the denominator.

    ``valid_count`` (the length of the resolved citations list) filters literal leftover
    brackets: the resolver numbers real citations 1..N, so a surviving ``[n]`` with n > N is
    quoted filing content, not a citation — it must not grant coverage credit. Its digits are
    still excluded from figure counting either way (bracketed digits are never figures).
    """
    brackets = list(re.finditer(r"\[(F?\s*\d+)\]", answer, re.IGNORECASE))
    marker_spans = [(m.start(), m.end()) for m in brackets]
    claim_spans: list[tuple[int, int]] = []
    prev_end = 0
    for m in brackets:
        digits = re.sub(r"\D", "", m.group(1))
        if valid_count is None or (digits and int(digits) <= valid_count):
            claim_spans.append((_claim_span_start(m.start(), prev_end), m.start()))
        prev_end = m.end()

    def _within(spans: list[tuple[int, int]], pos: int) -> bool:
        return any(s <= pos < e for s, e in spans)

    figures = 0
    uncited = 0
    for tok in _NUMBER_TOKEN.finditer(answer):
        if _within(marker_spans, tok.start()):
            continue  # the digits of a [12] marker, not a figure
        dollar, raw, suffix = tok.group(1), tok.group(2).replace(",", ""), (tok.group(3) or "")
        try:
            num = float(raw)
        except ValueError:
            continue
        if num.is_integer() and 1900 <= num <= 2100 and not dollar and not suffix:
            continue  # a year, not a figure
        if not dollar and not suffix and "." not in raw and num < 1000:
            continue  # a small bare count ("3 segments"), not a financial figure
        figures += 1
        if not _within(claim_spans, tok.start()):
            uncited += 1
    return figures, uncited


def _resolve_citations(
    full_answer: str,
    text_citations_by_marker: dict[str, dict],
    used_facts: list[dict],
    filing_url: Optional[str],
) -> tuple[str, list[dict], int, int]:
    """Single source of truth for citation numbering — the answer text and the Sources list can
    never disagree, because both come from this one left-to-right pass over ``full_answer``.

    The model reports two independent, self-assigned identifiers that used to be trusted blindly and
    separately: an inline marker in its prose, and (for filing-text excerpts) a same-numbered entry
    in a trailing JSON block emitted after the prose is already final. Nothing verified those two
    numbers actually agreed, or that a declared citation was ever placed inline at all — that gap is
    what let extra, uncited sources leak into the panel and let a misremembered marker (``[F13]``
    for what was really the 10th tool figure, say) fall back to unstyled literal text with no chip.

    This scans every ``[n]``/``[F n]``-shaped marker once, in the order it appears, resolves each
    against whichever candidate pool matches (declared text citations first, then tool-fetched
    facts), and assigns one continuous sequential number (1, 2, 3, ...) on first appearance — the
    same number is substituted back into the returned answer text. A marker with no matching
    candidate is left as literal text (the same "unmatched marker" contract the frontend already
    implements, now enforced server-side too, uniformly for both citation kinds).

    FACT markers additionally pass a value-adjacency guard on EVERY occurrence (including
    repeat mentions): the figure stated just before the marker must match the fact's value, or
    that occurrence is stripped as MISPLACED — a chip must never open provenance for a different
    metric than the claim it sits on. Returns the misplaced count as the 4th element for
    telemetry.
    """
    facts_by_marker = {f["_marker"]: f for f in used_facts if f.get("_marker")}

    resolved: list[dict] = []          # citation dicts, in final numbering order
    assigned: dict[str, int] = {}      # normalized original marker -> final n (repeat mentions reuse it)
    pieces: list[str] = []
    cursor = 0
    grounded = 0
    misplaced = 0
    prev_marker_end = 0

    for match in _COPILOT_MARKER_RE.finditer(full_answer):
        key = re.sub(r"\s+", "", match.group(1)).upper()

        # Adjacency guards for FACT-backed markers, on EVERY occurrence: the model reusing a
        # legit marker on a different figure — or mislabeling the metric a matching figure
        # belongs to — is exactly as misleading as inventing one (field report: revenue markers
        # reused as year markers across other metrics). VALUE: the adjacent figure must match
        # the fact. CONCEPT: the claim must not name a different metric. The window starts
        # after the previous KEPT marker — the already-cited figure of the prior claim
        # ("$81.46B [F1]. Gross profit fell to $20.85B [F1]") must not vouch for a reuse.
        #
        # STRIPPED markers must NOT bound the window: they vanish from the final text, so in a
        # dense run ("surged 19.4% [F3] to $15.00B [F2] in 2023 [F3]") letting the two strips
        # delimit the survivor would leave it a year-only, unfalsifiable window — while the
        # user-visible text puts it right next to figures it never vouched for (a confirmed
        # bypass: reused growth chips shipping on another metric's growth figures). Windows are
        # judged against what the FINAL answer will show; `_fact_matches_adjacent_number` scrubs
        # any stripped markers' leftover bracket text from the window.
        fact = facts_by_marker.get(key) if key not in text_citations_by_marker else None
        if fact is not None:
            window = _adjacency_window(full_answer, match.start(), prev_marker_end)
            if (not _fact_matches_adjacent_number(fact, window)
                    or not _fact_matches_adjacent_concept(fact, window)
                    or not _fact_matches_adjacent_currency(fact, window)):
                misplaced += 1
                pieces.append(full_answer[cursor:match.start()].rstrip(" "))
                cursor = match.end()
                continue

        # A marker cited more than once (e.g. "[F1]" mentioned twice) just reuses the number from
        # its first appearance — skip straight to rewriting, no need to re-resolve it.
        n = assigned.get(key)
        if n is not None:
            pieces.append(full_answer[cursor:match.start()])
            pieces.append(f"[{n}]")
            cursor = match.end()
            prev_marker_end = match.end()
            continue

        citation = text_citations_by_marker.get(key)
        if citation is None:
            if fact is not None:
                citation = {**copilot_tools.fact_to_citation(fact), "fragment_url": filing_url}
        if citation is None:
            # Unresolvable marker. A plain [n] stays literal (it may be quoted filing content —
            # the frontend's unmatched-marker contract). An F-marker can ONLY ever mean a
            # tool-provided figure, so an unresolvable one is a model artifact — fabricated, or
            # referencing a failed tool call (field report: an answer littered with [F1]..[F12]
            # and no matching sources). Strip it from the prose instead of shipping dead
            # brackets, swallowing the space before it so "value [F4]," reads "value,".
            if key.startswith("F"):
                # Trim the spaces LEADING INTO the marker and keep whatever follows:
                # "value [F4]," → "value,", "billion [F2] and" → "billion and".
                pieces.append(full_answer[cursor:match.start()].rstrip(" "))
                cursor = match.end()
            else:
                # Kept as literal text — it stays in the final answer, so it bounds claim spans.
                prev_marker_end = match.end()
            continue

        pieces.append(full_answer[cursor:match.start()])
        n = len(resolved) + 1
        assigned[key] = n
        resolved.append(citation)
        if citation["verified"]:
            grounded += 1
        pieces.append(f"[{n}]")
        cursor = match.end()
        prev_marker_end = match.end()

    pieces.append(full_answer[cursor:])
    # strip() guards a stripped F-marker at the very start/end leaving stray whitespace.
    rewritten_answer = "".join(pieces).strip()
    citations = [{"n": i + 1, **c} for i, c in enumerate(resolved)]
    return rewritten_answer, citations, grounded, misplaced
