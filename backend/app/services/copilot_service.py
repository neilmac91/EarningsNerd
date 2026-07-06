"""Grounded single-filing Q&A ("Ask this Filing" Copilot — A2 / P1).

A scoped assistant that answers questions about *one* SEC filing using only that filing's cached
text (plus a compact read-only XBRL block). It enforces honest, verifiable citations by reusing the
provenance primitives that already power Trace-to-Source:

* The model is told to answer ONLY from the provided content and to emit, after its prose, a JSON
  array of ``{n, excerpt, section}`` citations (or ``===NOT_DISCLOSED===`` when the filing does not
  disclose the answer).
* The server then **verifies** each emitted excerpt against the (once-normalized) cached filing text
  via :func:`~app.services.provenance_service.verify_excerpt_in_text`, and builds a ``#:~:text=``
  deep-link via :func:`~app.services.provenance_service.build_text_fragment_url`. A citation the model
  invents but that does not appear verbatim in the filing is surfaced as ``verified=False`` rather
  than silently trusted — the same honest-labelling contract as the summary path.

This module is transport-agnostic: it yields plain ``dict`` events. The SSE router formats them for
the wire. **Out of scope for P1:** numeric/XBRL tool-use (that is P5) and any vector retrieval — the
context is the cached excerpt, capped to ``COPILOT_CONTEXT_CHAR_CAP`` chars.
"""
from __future__ import annotations

import json
import logging
import re
from types import SimpleNamespace
from typing import Any, AsyncGenerator, Optional

from app.config import settings
from app.services import citation_markers, copilot_tools
from app.services.openai_service import (
    STREAM_ACTIVITY_SENTINEL,
    STREAM_ERROR_SENTINEL,
    openai_service,
)
from app.services.provenance_service import (
    build_text_fragment_url,
    normalize_for_match,
    verify_excerpt_in_text,
)

try:
    from json_repair import repair_json as _repair_json
    _HAS_JSON_REPAIR = True
except ImportError:  # pragma: no cover - json_repair is a declared dependency
    _HAS_JSON_REPAIR = False
    _repair_json = None

logger = logging.getLogger(__name__)

# Sentinels the model emits to delimit the citation block / the not-disclosed verdict. We hold back a
# tail of ``_SENTINEL_TAIL`` chars across chunk boundaries so a sentinel split between two stream
# chunks is still detected.
_CITATIONS_SENTINEL = "===CITATIONS==="
_NOT_DISCLOSED_SENTINEL = "===NOT_DISCLOSED==="
_SENTINEL_TAIL = max(len(_CITATIONS_SENTINEL), len(_NOT_DISCLOSED_SENTINEL))
# Optional trailer after the citations JSON carrying 2-3 suggested follow-up questions. It only ever
# appears inside the (buffered) citations phase, so it's parsed post-hoc — no cross-chunk tail needed.
_FOLLOWUPS_SENTINEL = "===FOLLOWUPS==="

SYSTEM_PROMPT = f"""You are EarningsNerd's "Ask this Filing" assistant. You answer questions about a \
SINGLE SEC filing using ONLY the filing content provided in this conversation. You are scoped to \
this one filing — you are not a general market oracle.

RULES:
- Answer ONLY from the provided filing content. Never use outside knowledge or assumptions.
- Every factual claim MUST be supported by a verbatim excerpt quoted directly from the filing.
- Be precise, decisive, and concise. Use the filing's own numbers and language.
- If the filing does not disclose what is asked, say so honestly — do NOT guess or fabricate.
- For any specific financial figure (revenue, margins, EPS, YoY, etc.), you MUST call the provided \
tools to get the exact value — never state a number from memory or compute it yourself. \
Tool-provided numbers are authoritative.
- When a question spans MULTIPLE metrics or periods (e.g. "how did revenue, gross profit, and net \
income trend?"), call the tools for EACH metric and EACH period you discuss — one lookup per \
figure. Correct shape: "Revenue was $10.0B [F1], gross profit $2.0B [F2], and net income $1.1B \
[F3]" — three figures, three lookups, three markers. Never fetch one metric and reuse or infer \
it for the others. A figure you did not fetch must come from a quoted filing-text excerpt \
([1], [2], ...) or be left out entirely: simply discuss the metrics you can source, and never \
announce that a figure was omitted or unavailable.
- Each SUCCESSFUL tool result includes a "cite" field (e.g. "F1"). Immediately after you state that \
tool-provided number in your prose, place its marker inline in square brackets exactly as given, \
e.g. [F1].
- NEVER write an [F#] marker that was not returned in a tool result's "cite" field in THIS \
conversation — do not invent, renumber, or extrapolate them. Each marker names ONE figure \
(one concept, one period): place it ONLY immediately after that exact figure, and NEVER reuse \
it on a different number, metric, or year (markers are not year labels). If a tool returned an error (or you \
did not call one) and you state a number quoted from the filing text instead, cite it with a plain \
filing-text excerpt marker ([1], [2], ...) backed by a verbatim excerpt — never an [F#] marker.

OUTPUT FORMAT (follow exactly):
1. Write the answer as prose. Place inline citation markers immediately after each claim/number they \
support: [1], [2] for filing-text excerpts, and [F1], [F2] for tool-provided figures.
2. Then output a line containing exactly:
{_CITATIONS_SENTINEL}
3. Then output a JSON array of citation objects, one per marker you used, e.g.:
[{{"n": 1, "excerpt": "<verbatim quote copied exactly from the filing>", "section": "Item 7 — MD&A"}}]
   - "excerpt" MUST be copied verbatim from the filing content (so it can be verified). Keep each
     excerpt to the SHORTEST span that supports the claim — one sentence, at most ~30 words.
   - "section" is the filing section it came from (e.g. "Item 1A — Risk Factors").
   - Keep the citation list tight: cite each distinct source once and reuse its marker; never pad
     the list. ALWAYS finish with step 4 — an answer without the followups block is incomplete.
4. Finally, output a line containing exactly:
{_FOLLOWUPS_SENTINEL}
   then a JSON array of 2-3 short, specific follow-up questions the user is likely to ask next about \
THIS filing (each under 12 words), e.g. ["How did operating margin trend?", "What are the top risks?"].
   Suggest ONLY questions this filing's provided content can actually answer — never questions \
requiring data it lacks (e.g. quarterly breakdowns in an annual filing, or undisclosed segment detail).

IF THE FILING DOES NOT DISCLOSE THE ANSWER, do NOT write prose or citations. Instead output exactly:
{_NOT_DISCLOSED_SENTINEL}
<one sentence stating what is missing and why this filing would not contain it>
then the {_FOLLOWUPS_SENTINEL} line and a JSON array of 2-3 questions this filing CAN answer, so \
the user has a productive next step. For example:
{_NOT_DISCLOSED_SENTINEL}
Quarterly gross margin detail is not in this annual filing; only full-year figures are reported.
{_FOLLOWUPS_SENTINEL}
["How did annual gross margin trend?", "What drove operating expenses?"]"""


def _select_source_text(filing: Any) -> Optional[str]:
    """Pick the best cached filing text (no network fetch). Mirrors provenance_service."""
    cache = getattr(filing, "content_cache", None)
    if cache is None:
        return None
    return getattr(cache, "critical_excerpt", None) or getattr(cache, "markdown_content", None)


def snapshot_filing(filing: Any) -> SimpleNamespace:
    """Detach a plain, in-memory snapshot of just the fields the SSE generator reads.

    The streaming generator runs *after* the endpoint returns — once metering's ``db.commit()`` has
    expired the ORM instances (``expire_on_commit`` default) and, per the ``generate_summary_stream``
    pattern, the request session may already be gone. Touching ORM attributes there would trigger
    lazy-loads or ``DetachedInstanceError``. So the endpoint captures everything eagerly into this
    detached snapshot (mirroring the summary stream's eager value capture) and the generator only
    ever reads plain Python objects. ``db.expunge(filing)`` alone is insufficient: the default
    cascade doesn't expunge the joinedloaded ``content_cache``/``company``, so those would still be
    expired.
    """
    cache = getattr(filing, "content_cache", None)
    company = getattr(filing, "company", None)
    return SimpleNamespace(
        filing_type=getattr(filing, "filing_type", None),
        filing_date=getattr(filing, "filing_date", None),
        document_url=getattr(filing, "document_url", None),
        sec_url=getattr(filing, "sec_url", None),
        xbrl_data=getattr(filing, "xbrl_data", None),
        # company_id + cik power the P5 numeric tools, which open their own DB session (the request
        # session is gone by the time the SSE generator runs), so the company id is captured eagerly
        # here rather than dereferenced off a detached ORM instance later.
        company_id=getattr(filing, "company_id", None),
        cik=getattr(company, "cik", None),
        content_cache=SimpleNamespace(
            critical_excerpt=getattr(cache, "critical_excerpt", None),
            markdown_content=getattr(cache, "markdown_content", None),
        ) if cache is not None else None,
        company=SimpleNamespace(
            name=getattr(company, "name", None),
            ticker=getattr(company, "ticker", None),
        ) if company is not None else None,
    )


def _compact_xbrl_block(xbrl_data: Any) -> str:
    """Render the filing's XBRL JSON compactly for context, or "" when absent/oversized.

    Read-only context only — P1 does not let the model call XBRL tools (that is P5). Kept small so it
    cannot crowd out the section excerpt.
    """
    if not xbrl_data:
        return ""
    try:
        rendered = json.dumps(xbrl_data, default=str, separators=(",", ":"))
    except (TypeError, ValueError):
        return ""
    # Cap so a pathological XBRL payload can't dominate the context window.
    return rendered[:8000]


def _build_context_message(filing: Any, source_text: str) -> str:
    """Assemble the filing-meta + excerpt + XBRL context message for the model."""
    company = getattr(filing, "company", None)
    company_name = getattr(company, "name", None) or "Unknown company"
    ticker = getattr(company, "ticker", None) or "?"
    form = getattr(filing, "filing_type", None) or "filing"
    filing_date = getattr(filing, "filing_date", None)
    date_str = filing_date.strftime("%Y-%m-%d") if hasattr(filing_date, "strftime") else str(filing_date or "unknown")

    excerpt = (source_text or "")[: settings.COPILOT_CONTEXT_CHAR_CAP]
    xbrl_block = _compact_xbrl_block(getattr(filing, "xbrl_data", None))

    parts = [
        f"FILING: {company_name} ({ticker}) — {form} filed {date_str}.",
        "",
        "FILING CONTENT (the only source you may use):",
        excerpt or "(no cached content available for this filing)",
    ]
    if xbrl_block:
        parts += [
            "",
            "STRUCTURED FINANCIAL DATA (XBRL, for reference):",
            xbrl_block,
        ]
    return "\n".join(parts)


def _merge_consecutive_roles(messages: list[dict]) -> list[dict]:
    """Concatenate adjacent same-role messages so the sequence strictly alternates.

    Some providers (DeepSeek's reasoner lineage, Anthropic, strict OpenAI) reject consecutive
    same-role messages with a 400. This collapses any same-role run (e.g. the filing-context user
    message immediately followed by the first user turn / the question, or a malformed history) into
    one message, guaranteeing valid alternation regardless of the history shape we're handed.
    """
    merged: list[dict] = []
    for msg in messages:
        if merged and merged[-1]["role"] == msg["role"]:
            merged[-1] = {
                "role": msg["role"],
                "content": f"{merged[-1]['content']}\n\n{msg['content']}",
            }
        else:
            merged.append({"role": msg["role"], "content": msg["content"]})
    return merged


def _build_messages(filing: Any, source_text: str, question: str, history: Optional[list[dict]]) -> list[dict]:
    """system + context + last N history turns + the user question (with role alternation enforced)."""
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_context_message(filing, source_text)},
    ]
    if history:
        # Keep only the most recent turns; tolerate malformed entries.
        turns = history[-settings.COPILOT_HISTORY_TURNS:]
        for turn in turns:
            if not isinstance(turn, dict):
                continue
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                # Cap per-turn content so a malicious/oversized history entry can't stuff the prompt
                # (defense-in-depth — the API layer also bounds this; see AskRequest).
                messages.append({"role": role, "content": content[: settings.COPILOT_HISTORY_ITEM_CHAR_CAP]})
    messages.append({"role": "user", "content": question})
    # Collapse same-role runs (context+question, context+first-user-turn, malformed history) so
    # providers that require strict user/assistant alternation don't 400.
    return _merge_consecutive_roles(messages)


def _parse_citations(raw: str) -> list[dict]:
    """Parse the model's citation JSON array, repairing malformed JSON when needed."""
    text = (raw or "").strip()
    if not text:
        return []
    # The model may wrap the array in stray prose/fences; isolate the array span.
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        if _HAS_JSON_REPAIR and _repair_json is not None:
            try:
                data = json.loads(_repair_json(text))
            except (ValueError, TypeError):
                return []
        else:
            return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _parse_followups(raw: str) -> list[str]:
    """Parse the optional follow-up-questions trailer (a JSON array of short strings); max 3."""
    text = (raw or "").strip()
    if not text:
        return []
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        if _HAS_JSON_REPAIR and _repair_json is not None:
            try:
                data = json.loads(_repair_json(text))
            except (ValueError, TypeError):
                return []
        else:
            return []
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for item in data:
        if isinstance(item, str) and item.strip():
            out.append(item.strip()[:140])
        if len(out) >= 3:
            break
    return out


def _verify_citations(citations: list[dict], filing: Any, normalized_source: str) -> dict[str, dict]:
    """Verify each declared citation's excerpt; return a lookup keyed by its declared marker.

    Keyed by the citation's own ``n`` (stringified, e.g. ``"1"``), falling back to its 1-based
    position in the array when ``n`` isn't a valid int. This is a *candidate* pool only — a citation
    the model declares here but never actually places inline is never surfaced: the caller's unified
    :func:`_resolve_citations` pass looks entries up by the markers it finds in the answer text, not
    the other way around.
    """
    base_url = getattr(filing, "document_url", None) or getattr(filing, "sec_url", None) or ""
    by_marker: dict[str, dict] = {}
    for idx, cite in enumerate(citations, start=1):
        excerpt = str(cite.get("excerpt") or "").strip()
        section_ref = cite.get("section") or cite.get("section_ref")
        n = cite.get("n")
        if not isinstance(n, int):
            n = idx
        verified = verify_excerpt_in_text(excerpt, normalized_source)
        if verified:
            fragment_url = build_text_fragment_url(base_url, excerpt) if base_url else base_url
        else:
            fragment_url = base_url
        by_marker[str(n)] = {
            "excerpt": excerpt,
            "section_ref": section_ref,
            "verified": verified,
            "fragment_url": fragment_url,
        }
    return by_marker


# How far back (chars) to look for the figure a fact marker claims to support.
_ADJACENCY_WINDOW_CHARS = 64

_NUMBER_TOKEN = re.compile(
    r"(\$)?\s*([0-9][\d,]*(?:\.\d+)?)\s*(billion|million|thousand|bn|[bmk%])?",
    re.IGNORECASE,
)


def _claim_span_start(marker_start: int, prev_marker_end: int) -> int:
    """Where a marker's claim span begins: up to ``_ADJACENCY_WINDOW_CHARS`` back, bounded by the
    previous citation marker (a marker vouches for the claim SINCE the last citation). THE single
    window rule — shared by the adjacency guards, the coverage counter, and the eval scorer."""
    return max(0, marker_start - _ADJACENCY_WINDOW_CHARS, prev_marker_end)


def _adjacency_window(text: str, marker_start: int, prev_marker_end: int) -> str:
    """The claim span a fact marker vouches for (see :func:`_claim_span_start`)."""
    return text[_claim_span_start(marker_start, prev_marker_end):marker_start]


def _fact_matches_adjacent_number(fact: dict, window: str) -> bool:
    """True when the fact's value plausibly matches a figure stated just before its marker.

    The trust guard for TOOL citations (field report: the model reused revenue fact markers
    [F1]/[F2]/[F3] as year markers on gross-profit/operating-income/net-income figures, so
    chips opened provenance for a DIFFERENT metric than the claim). Text citations verify by
    excerpt matching; fact citations verify by VALUE ADJACENCY: some number in the preceding
    window must equal the fact's value (at display-rounding tolerance).

    Falsification-only: a window with NO number tokens can't be checked — the marker is kept
    (qualitative placements like "margins compressed [F1]" exist). Bare 4-digit integers that
    read as years (1900-2100, no $, no scale suffix) are ignored as context, not figures.

    The caller bounds ``window`` at the previous citation marker: a marker vouches for the
    claim SINCE the last citation, so a matching figure from the preceding, already-cited
    claim must not vouch for a reused marker sitting on a different number.
    """
    try:
        value = float(fact.get("value"))
    except (TypeError, ValueError):
        return True
    percent_like = fact.get("kind") in ("yoy_growth", "margin")
    # Prior markers in the window ([2], [F1]) are citations, not figures — scrub them.
    scrubbed = re.sub(r"\[\s*F?\s*\d+\s*\]", " ", window, flags=re.IGNORECASE)

    candidates: list[tuple[str, float]] = []
    saw_token = False
    for m in _NUMBER_TOKEN.finditer(scrubbed):
        dollar, raw, suffix = m.group(1), m.group(2).replace(",", ""), (m.group(3) or "").lower()
        try:
            num = float(raw)
        except ValueError:
            continue
        if not dollar and not suffix and num.is_integer() and 1900 <= num <= 2100:
            continue  # a year, not a figure
        saw_token = True
        scale = {"billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}.get(suffix)
        if suffix == "%":
            candidates.append(("pct", num))
        elif scale:
            candidates.append(("abs", num * scale))
        else:
            candidates.append(("plain", num))
    if not saw_token:
        return True

    def _close(a: float, b: float, *, rel: float = 0.01, absolute: float = 0.011) -> bool:
        return abs(a - b) <= max(rel * max(abs(a), abs(b)), absolute)

    for token_kind, num in candidates:
        if percent_like:
            # Prose states percents ("17.9%" or bare "17.9"); the fact value is a fraction.
            if token_kind in ("pct", "plain") and _close(num, abs(value) * 100.0, absolute=0.11):
                return True
        else:
            if token_kind == "pct":
                continue
            # Match the raw value or any display scaling of it ("$81.46B" / "81.46" / "$2.04").
            if any(_close(num, abs(value) / d) for d in (1.0, 1e3, 1e6, 1e9)):
                return True
    return False


# How prose names each standardized concept — the vocabulary for the CONCEPT adjacency check.
# Phrase-containment, lowercase. Deliberately curated and conservative: a paraphrase missing from
# a fact's own list can only cause a KEPT marker (the check is falsification-only), never a strip.
# Margin phrasings live under their numerator concept (compute_metric results carry the numerator
# as ``concept``). Unknown concepts aren't checkable and always keep their marker.
_CONCEPT_SYNONYMS: dict[str, tuple[str, ...]] = {
    "revenue": ("revenue", "net sales", "total sales", "sales", "top line", "top-line", "turnover"),
    "net_income": (
        "net income", "net earnings", "net profit", "net loss", "bottom line", "bottom-line",
        "net margin", "profit margin",
    ),
    "gross_profit": ("gross profit", "gross margin", "gross income", "gross loss"),
    "operating_income": (
        "operating income", "operating profit", "operating loss", "income from operations",
        "operating margin", "ebit",
    ),
    "total_assets": ("total assets",),
    "total_liabilities": ("total liabilities",),
    "stockholders_equity": (
        "stockholders' equity", "stockholders equity", "shareholders' equity",
        "shareholders equity", "total equity", "book value",
    ),
    "cash_and_equivalents": (
        "cash and cash equivalents", "cash and equivalents", "cash & equivalents",
        "cash position", "cash balance",
    ),
    "eps_basic": ("earnings per share", "eps", "per share", "loss per share"),
    "eps_diluted": ("earnings per share", "eps", "per share", "per diluted share", "loss per share"),
    "shares_outstanding": (
        "shares outstanding", "share count", "outstanding shares", "weighted average shares",
    ),
}


# Word-boundary alternations per concept — bare substring containment false-matches constantly in
# earnings prose ("ebit" in EBITDA/debit, "eps" in steps/keeps, "sales" in Salesforce).
_CONCEPT_PATTERNS: dict[str, re.Pattern] = {
    concept: re.compile(r"\b(?:" + "|".join(re.escape(p) for p in phrases) + r")\b")
    for concept, phrases in _CONCEPT_SYNONYMS.items()
}
# Clause boundaries: only the FINAL clause of the claim span names the figure the marker sits on;
# earlier clauses are context ("Driven by strong sales, the company earned $7.09B [F1]" — "sales"
# is a driver mention, not the figure's label). A period/comma followed by a digit is inside a
# number ("$96.77B", "1,023"), not a boundary.
_CLAUSE_BOUNDARY = re.compile(r"[;:()—–]|[.,](?![0-9])")


def _fact_matches_adjacent_concept(fact: dict, window: str) -> bool:
    """True unless the figure's own clause names a DIFFERENT known metric and the span never
    names the fact's own.

    The companion to the VALUE check: value adjacency can't catch a chip whose value matches but
    whose claim mislabels the metric ("operating income was $96.77B [F2]" where [F2] is the
    same-valued REVENUE fact) — right number, wrong label, and the chip would still open the wrong
    provenance. Falsification-only, doubly conservative: the fact's own concept must be absent
    from the WHOLE span, and another curated concept must be named (word-boundary match) in the
    figure's own final clause. Ambiguous or paraphrased claims keep their marker.
    """
    concept = str(fact.get("concept") or "").lower()
    own = _CONCEPT_PATTERNS.get(concept)
    if own is None:
        return True  # unknown concept — not checkable
    # Curly apostrophes are common in model prose ("stockholders’ equity") — normalize so the
    # straight-quote synonyms match; a missed OWN match is a false-strip vector.
    low = window.lower().replace("’", "'")
    if own.search(low):
        return True
    clause = _CLAUSE_BOUNDARY.split(low)[-1]
    for other, pattern in _CONCEPT_PATTERNS.items():
        if other != concept and pattern.search(clause):
            return False
    return True


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

    for match in re.finditer(r"\[(F?\s*\d+)\]", full_answer, re.IGNORECASE):
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
            if not _fact_matches_adjacent_number(fact, window) or not _fact_matches_adjacent_concept(
                fact, window
            ):
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


async def answer_filing_question(
    *,
    filing: Any,
    question: str,
    history: Optional[list[dict]] = None,
) -> AsyncGenerator[dict, None]:
    """Stream a grounded answer to ``question`` about ``filing`` as event dicts.

    Yields (in order):
    * ``{"type": "progress", "stage": "reading"}`` before the model call.
    * ``{"type": "activity", "label", "phase", "ok"}`` as numeric tools run (live "show the work").
    * ``{"type": "token", "text": ...}`` for answer prose only (never the citation JSON / sentinels).
    * ``{"type": "not_disclosed", "answer": ...}`` if the model emits the not-disclosed sentinel.
    * ``{"type": "complete", "answer", "citations", "grounded", "kind", "followups"}`` at the end.
    * ``{"type": "error", "message": ...}`` on any failure.

    The generator never raises — all exceptions become an ``error`` event so the SSE stream stays
    well-formed. The filing source text is normalized **once** here and reused for every excerpt.
    """
    try:
        source_text = _select_source_text(filing) or ""
        normalized_source = normalize_for_match(source_text)
        messages = _build_messages(filing, source_text, question, history)

        # P5/P6b numeric tool-use: bind the tools to this filing's company. ``run_tool`` opens its own
        # DB session per call (the request session is gone by now). Each distinct successful fact is
        # assigned a stable ``F#`` citation marker (deduped by raw_tag/accession/period_end/kind) that
        # is fed back to the model via the tool result's ``cite`` field, so the model can cite the
        # figure inline as ``[F1]`` — rendering an inline chip, not just a Sources row.
        company_id = getattr(filing, "company_id", None)
        used_facts: list[dict] = []
        _fact_markers: dict[tuple, str] = {}

        def _run_tool(name: str, args: dict) -> dict:
            result = copilot_tools.run_tool(name, args, company_id)
            if isinstance(result, dict) and "error" not in result and "value" in result:
                key = (
                    result.get("raw_tag"),
                    result.get("accession"),
                    result.get("period_end"),
                    result.get("kind"),
                )
                marker = _fact_markers.get(key)
                if marker is None:
                    marker = f"F{len(used_facts) + 1}"
                    _fact_markers[key] = marker
                    result["_marker"] = marker
                    used_facts.append(result)
                # Hand the model the exact inline marker to use for this figure (e.g. "[F1]").
                return {**result, "cite": marker}
            return result

        yield {"type": "progress", "stage": "reading"}

        answer_parts: list[str] = []          # emitted prose (before any sentinel)
        citation_buffer: list[str] = []       # text after ===CITATIONS===
        not_disclosed_parts: list[str] = []   # text after ===NOT_DISCLOSED===
        pending = ""                          # carry-over tail for cross-chunk sentinel detection
        mode = "answer"                        # answer | citations | not_disclosed

        # Token usage is accumulated here across tool rounds (opt-in via usage_sink) so the router
        # can emit per-answer inference cost from the `complete` event; empty if the provider
        # returns no usage.
        usage_sink: dict[str, int] = {}
        model_name = openai_service.model
        async for delta in openai_service.stream_chat_with_tools(
            messages,
            copilot_tools.TOOLS,
            _run_tool,
            model=model_name,
            max_tokens=settings.COPILOT_MAX_TOKENS,
            temperature=0.2,
            usage_sink=usage_sink,
        ):
            if not delta:
                continue

            # The model stream wrapper signals an upstream/model failure with a sentinel-prefixed
            # chunk (rather than raising). Surface it as a real error event instead of letting the
            # bracketed text stream out as the answer body — a model outage must not look like a
            # confident, zero-grounded answer.
            if delta.startswith(STREAM_ERROR_SENTINEL):
                message = delta[len(STREAM_ERROR_SENTINEL):].strip() or "model stream failed"
                yield {"type": "error", "message": message[:300]}
                return

            # Tool-activity signal from the wrapper → a live "show the work" event. Translate the raw
            # tool name/args into a human label here (the wrapper stays provider-generic).
            if delta.startswith(STREAM_ACTIVITY_SENTINEL):
                try:
                    info = json.loads(delta[len(STREAM_ACTIVITY_SENTINEL):])
                    if not isinstance(info, dict):
                        info = {}
                except (ValueError, TypeError):
                    info = {}
                yield {
                    "type": "activity",
                    "label": copilot_tools.describe_tool_call(info.get("name", ""), info.get("args")),
                    "phase": info.get("phase", "start"),
                    "ok": bool(info.get("ok", True)),
                }
                continue

            if mode == "citations":
                citation_buffer.append(delta)
                continue
            if mode == "not_disclosed":
                not_disclosed_parts.append(delta)
                continue

            # mode == "answer": scan the accumulated buffer for a sentinel, emitting safe prose and
            # holding back a tail so a sentinel split across chunks is still caught.
            pending += delta
            while True:
                cit_at = pending.find(_CITATIONS_SENTINEL)
                nd_at = pending.find(_NOT_DISCLOSED_SENTINEL)
                # Earliest sentinel wins (filter out the -1 "not found" sentinels).
                hits = [pos for pos in (cit_at, nd_at) if pos != -1]
                if hits:
                    cut = min(hits)
                    prose = pending[:cut]
                    if prose:
                        answer_parts.append(prose)
                        yield {"type": "token", "text": prose}
                    if cut == cit_at:
                        mode = "citations"
                        citation_buffer.append(pending[cut + len(_CITATIONS_SENTINEL):])
                    else:
                        mode = "not_disclosed"
                        not_disclosed_parts.append(pending[cut + len(_NOT_DISCLOSED_SENTINEL):])
                    pending = ""
                    break

                # No complete sentinel: emit everything except a held-back tail that could be the
                # start of a sentinel spanning into the next chunk.
                if len(pending) > _SENTINEL_TAIL:
                    emit = pending[:-_SENTINEL_TAIL]
                    pending = pending[-_SENTINEL_TAIL:]
                    if emit:
                        answer_parts.append(emit)
                        yield {"type": "token", "text": emit}
                break

        # Stream finished. Build the usage payload (tokens + model) for the per-answer cost
        # telemetry the router emits from the `complete` event; None if the provider gave no usage.
        usage_payload = {"model": model_name, **usage_sink} if usage_sink else None

        # Flush any held-back tail that turned out to be plain prose.
        if mode == "answer" and pending:
            answer_parts.append(pending)
            yield {"type": "token", "text": pending}

        if mode == "not_disclosed":
            # The not-disclosed verdict may carry a trailing followups block (questions this
            # filing CAN answer) — a dead end without a next step just strands the user.
            nd_raw = "".join(not_disclosed_parts)
            nd_followups: list[str] = []
            nd_match = re.search(r"===\s*FOLLOW-?UPS\s*===", nd_raw, re.IGNORECASE)
            if nd_match:
                nd_followups = _parse_followups(nd_raw[nd_match.end():])
                nd_raw = nd_raw[: nd_match.start()]
            answer = nd_raw.strip() or "This filing does not disclose the requested information."
            yield {"type": "not_disclosed", "answer": answer}
            yield {
                "type": "complete",
                "answer": answer,
                "citations": [],
                "grounded": 0,
                "kind": "not_disclosed",
                "followups": nd_followups,
                "usage": usage_payload,
            }
            return

        full_answer = "".join(answer_parts).strip()
        # The citations buffer may carry a trailing ===FOLLOWUPS=== block; split it off before parsing
        # the citation JSON so suggested next-questions can be surfaced as tappable chips. The match is
        # case/dash/space-tolerant: if a mis-cased sentinel slipped through, the followups JSON would
        # otherwise be left in the buffer and corrupt the citation parse (zero citations) — so this is
        # deliberately forgiving.
        citation_raw = "".join(citation_buffer)
        followups: list[str] = []
        followups_match = re.search(r"===\s*FOLLOW-?UPS\s*===", citation_raw, re.IGNORECASE)
        if followups_match:
            followups = _parse_followups(citation_raw[followups_match.end():])
            citation_raw = citation_raw[: followups_match.start()]
        citations = _parse_citations(citation_raw)
        text_citations_by_marker = _verify_citations(citations, filing, normalized_source)

        # Multi-reference bracket groups the model emits despite the one-marker-per-bracket
        # contract — "[F1, F2]", "[F1, 2]", "[F1 vs F2]" — previously stayed LITERAL in the
        # answer (the resolver's regex only matches single markers). Normalize them to adjacent
        # single brackets first (shared citation-group classification with the trend resolver),
        # so each reference resolves through the normal path. Guard semantics after the split:
        # the FIRST member carries the claim's adjacency window; later members' windows are the
        # single space between brackets, so they get the qualitative-placement treatment (same
        # as a chain the model writes itself) — split members are resolved, not value-checked.
        full_answer = citation_markers.expand_citation_marker_groups(
            full_answer,
            ref_re=citation_markers.COPILOT_GROUP_MEMBER_RE,
            normalize=citation_markers.copilot_normalize_ref,
            # Only groups with at least one F-ref expand: an ALL-plain-number group never does
            # (pinned resolver behavior, and "[1,234]" could be a bracketed thousands figure).
            require_re=citation_markers.MARKER_REF_RE,
        )
        # Single server-owned numbering pass: resolves every marker actually present in the answer
        # (text-excerpt or tool-figure alike) against its real source, assigns one continuous
        # sequential number in first-appearance order, and rewrites the answer's inline markers to
        # match — so the answer text and the returned citations list can never disagree, and a
        # declared-but-never-cited source can never leak into the Sources panel.
        filing_url = getattr(filing, "document_url", None) or getattr(filing, "sec_url", None) or None
        full_answer, verified_citations, grounded, misplaced = _resolve_citations(
            full_answer, text_citations_by_marker, used_facts, filing_url
        )
        if misplaced:
            # Trust telemetry: a nonzero rate here means the model is attaching fact markers to
            # figures they don't support — watch this after any prompt/model change.
            logger.warning("copilot: stripped %d misplaced fact marker(s) from answer", misplaced)
        # COVERAGE telemetry, the counterpart signal: stripping misplaced markers (and model
        # laziness) leaves figures with no citation at all. Counted on the FINAL answer — what
        # the user actually sees.
        figure_count, uncited_figures = count_uncited_figures(full_answer, len(verified_citations))
        if uncited_figures:
            logger.warning(
                "copilot: answer shipped %d uncited figure(s) of %d total",
                uncited_figures, figure_count,
            )

        yield {
            "type": "complete",
            "answer": full_answer,
            "citations": verified_citations,
            "grounded": grounded,
            "kind": "answer",
            "followups": followups,
            "misplaced_fact_markers": misplaced,
            "figure_count": figure_count,
            "uncited_figures": uncited_figures,
            "usage": usage_payload,
        }
    except Exception as e:  # noqa: BLE001 — never raise out of the SSE generator
        logger.exception("Copilot answer_filing_question failed")
        yield {"type": "error", "message": str(e)[:300]}
