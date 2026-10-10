"""Grounded single-filing Q&A ("Ask this Filing" Copilot — A2 / P1).

A scoped assistant that answers questions about *one* SEC filing using only that filing's cached
text (plus a compact read-only XBRL block). It enforces honest, verifiable citations by reusing the
provenance primitives that already power Trace-to-Source:

* The model is told to answer ONLY from the provided content and to emit, after its prose, a JSON
  array of ``{n, excerpt, section}`` citations (or ``===NOT_DISCLOSED===`` when the filing does not
  disclose the answer).
* The server then **verifies** each WHOLE emitted excerpt against the (once-normalized) cached
  filing text via :func:`~app.services.provenance_service.verify_whole_excerpt_in_text` (only a
  quote pair wrapping the entire excerpt is stripped; an inner quoted span never stands in for it),
  and builds a ``#:~:text=`` deep-link to the start of that excerpt via
  :func:`~app.services.provenance_service.build_text_fragment_url`. A citation whose section label
  contains one of decision F's double quote marks (``"``, ``＂``, ``“``, ``”``, ``„``, ``‟``) is
  unverified too: the label is not checked against the filing, so it may not present a quotation.
  A citation the model references but that fails verification prevents publication of the entire
  answer. Answer prose remains private until citation admission and numbering finish; source
  matching does not prove the interpretation or establish that every uncited claim is supported.

This module is transport-agnostic: it yields plain ``dict`` events. The SSE router formats them for
the wire. Numeric tools use the viewed filing's accession and native currency; narrative
context is the cached excerpt, capped to ``COPILOT_CONTEXT_CHAR_CAP`` chars. No vector retrieval.
"""
from __future__ import annotations

import asyncio
import html  # noqa: F401 - preserve the facade import surface
import json
import logging
import math  # noqa: F401 - preserve the facade import surface
import re
import unicodedata  # noqa: F401 - preserve the facade import surface
from datetime import date  # noqa: F401 - preserve the facade import surface
from time import monotonic
from types import SimpleNamespace
from typing import Any, AsyncGenerator, Callable, Optional  # noqa: F401 - preserve the facade import surface

from markdown_it import MarkdownIt  # noqa: F401 - preserve the facade import surface

from app.config import settings
from app.services import citation_markers, copilot_tools
from app.services.ai.copilot_chat import chat_deadline
from app.services.openai_service import (
    STREAM_ACTIVITY_SENTINEL,
    STREAM_ERROR_SENTINEL,
    openai_service,
)
from app.services.provenance_service import (
    _MIN_VERIFIABLE_LEN,
    build_text_fragment_url,  # noqa: F401 - preserve the facade import surface
    normalize_for_match,
    strip_wrapping_quotes,  # noqa: F401 - preserve the facade import surface
    verify_whole_excerpt_in_text,  # noqa: F401 - preserve the facade import surface
)


from app.services.copilot.quotations import (
    _CLOSING_QUOTE_MARK,
    _DEFAULT_IGNORABLE_RE,
    _FAIL_CLOSED_CHARS_RE,
    _LINE_EDGE_SPACE_RE,
    _LINK_RE,
    _MARKDOWN,
    _MARKDOWN_BLOCKS,
    _MARKDOWN_BLOCK_ENDS,
    _MARKDOWN_BREAKS,
    _MARKDOWN_CONTAINERS,
    _MARKDOWN_EMPHASIS,
    _MARKDOWN_INLINE,
    _MAX_BRACKETS,
    _MAX_MARKDOWN_NESTING,
    _MAX_QUOTED_ANSWER_CHARS,
    _MAX_QUOTED_CHARS,
    _MAX_QUOTE_MARKS,
    _MAYBE_HIDDEN,
    _MIN_QUOTED_LEN,
    _OUTSIDE_SUBSET_RE,
    _QUOTED_MARKER_RE,
    _QUOTE_EDGE_CHARS,
    _QUOTE_ELLIPSIS_RE,
    _QUOTE_HINT_RE,
    _QUOTE_MARK_RE,
    _RAW_HTML_RE,
    _STRAIGHT_QUOTE_MARKS,
    _TABLE_DELIMITER_LIKE_RE,
    _TASK_CHECKBOX_RE,
    _TOP_LEVEL_BLOCKS,
    _UNICODE_SPACES,
    _beside,
    _display_may_differ,
    _displayed_quotation_reasons,
    _is_punctuation,
    _markdown_parser,
    _may_delimit,
    _quotation_reading,
    _rendered_inline,
    _rendered_text,
    _straight_reading,
    _withhold_unsupported_quotations,
    unsupported_plain_quotations,
    unsupported_prose_quotations,
)
from app.services.copilot.fact_guards import (
    _ADJACENCY_WINDOW_CHARS,
    _CLAUSE_BOUNDARY,
    _CONCEPT_PATTERNS,
    _CONCEPT_SYNONYMS,
    _CURRENCY_AFTER,
    _CURRENCY_ALIASES,
    _CURRENCY_BEFORE,
    _CURRENCY_TOKEN,
    _NUMBER_TOKEN,
    _adjacency_window,
    _claim_span_start,
    _fact_identity,
    _fact_matches_adjacent_concept,
    _fact_matches_adjacent_currency,
    _fact_matches_adjacent_number,
    _reporting_currency,
    _valid_fact_provenance,
)
from app.services.copilot.claim_repair import (
    _ANNUAL_DURATION_DAYS,
    _ANNUAL_FIGURE_CLAIM,
    _ANNUAL_REPORT_FORMS,
    _CLAIM_PHRASE_CONCEPT,
    _CLAIM_SCALES,
    _MONTH_NAMES,
    _PAIRED_ANNUAL_CLAIM,
    _REPAIRABLE_CLAIM_PHRASES,
    _SERVER_LOOKUP_ORIGIN,
    _fact_certifies_claim,
    _is_annual_report_form,
    _iso_day,
    _plan_uncited_fact_citation,
    _repair_paired_annual_claim,
    _repair_uncited_fact_claim,
)
from app.services.copilot.resolution import (
    _COPILOT_MARKER_RE,
    _resolve_citations,
    count_uncited_figures,
)
from app.services.copilot.envelope import (
    _FOLLOWUPS_RE,
    _HAS_JSON_REPAIR,
    _parse_citations,
    _parse_followups,
    _repair_json,
    _verify_citations,
    section_label_is_quoted,
)
from app.services.copilot.exceptions import (
    _RegenerableEvidenceMismatch,
    _UnpublishableAnswer,
)

__all__ = [
    'PROVIDER_STARTED_STAGE',
    'SYSTEM_PROMPT',
    '_ADJACENCY_WINDOW_CHARS',
    '_ANNUAL_DURATION_DAYS',
    '_ANNUAL_FIGURE_CLAIM',
    '_ANNUAL_REPORT_FORMS',
    '_CITATIONS_SENTINEL',
    '_CLAIM_PHRASE_CONCEPT',
    '_CLAIM_SCALES',
    '_CLAUSE_BOUNDARY',
    '_CLOSING_QUOTE_MARK',
    '_CONCEPT_PATTERNS',
    '_CONCEPT_SYNONYMS',
    '_COPILOT_MARKER_RE',
    '_CURRENCY_AFTER',
    '_CURRENCY_ALIASES',
    '_CURRENCY_BEFORE',
    '_CURRENCY_TOKEN',
    '_DEFAULT_IGNORABLE_RE',
    '_EVIDENCE_RETRY_GUIDANCE',
    '_FAIL_CLOSED_CHARS_RE',
    '_FOLLOWUPS_RE',
    '_FOLLOWUPS_SENTINEL',
    '_HAS_JSON_REPAIR',
    '_LINE_EDGE_SPACE_RE',
    '_LINK_RE',
    '_MARKDOWN',
    '_MARKDOWN_BLOCKS',
    '_MARKDOWN_BLOCK_ENDS',
    '_MARKDOWN_BREAKS',
    '_MARKDOWN_CONTAINERS',
    '_MARKDOWN_EMPHASIS',
    '_MARKDOWN_INLINE',
    '_MAX_BRACKETS',
    '_MAX_MARKDOWN_NESTING',
    '_MAX_QUOTED_ANSWER_CHARS',
    '_MAX_QUOTED_CHARS',
    '_MAX_QUOTE_MARKS',
    '_MAYBE_HIDDEN',
    '_MIN_QUOTED_LEN',
    '_MONTH_NAMES',
    '_NOT_DISCLOSED_SENTINEL',
    '_NUMBER_TOKEN',
    '_OUTSIDE_SUBSET_RE',
    '_PAIRED_ANNUAL_CLAIM',
    '_PUBLICATION_ERROR',
    '_QUOTED_MARKER_RE',
    '_QUOTE_EDGE_CHARS',
    '_QUOTE_ELLIPSIS_RE',
    '_QUOTE_HINT_RE',
    '_QUOTE_MARK_RE',
    '_RAW_HTML_RE',
    '_REPAIRABLE_CLAIM_PHRASES',
    '_RETRYABLE_QUOTATION_FAILURES',
    '_RegenerableEvidenceMismatch',
    '_SENTINEL_TAIL',
    '_SERVER_LOOKUP_ORIGIN',
    '_STRAIGHT_QUOTE_MARKS',
    '_STREAM_FAILURE',
    '_TABLE_DELIMITER_LIKE_RE',
    '_TASK_CHECKBOX_RE',
    '_TOP_LEVEL_BLOCKS',
    '_UNICODE_SPACES',
    '_UnpublishableAnswer',
    '_adjacency_window',
    '_answer_filing_question_attempt',
    '_beside',
    '_build_context_message',
    '_build_messages',
    '_claim_span_start',
    '_compact_xbrl_block',
    '_display_may_differ',
    '_displayed_quotation_reasons',
    '_fact_certifies_claim',
    '_fact_identity',
    '_fact_matches_adjacent_concept',
    '_fact_matches_adjacent_currency',
    '_fact_matches_adjacent_number',
    '_is_annual_report_form',
    '_is_punctuation',
    '_iso_day',
    '_markdown_parser',
    '_may_delimit',
    '_merge_consecutive_roles',
    '_parse_citations',
    '_parse_followups',
    '_plan_uncited_fact_citation',
    '_quotation_reading',
    '_rendered_inline',
    '_rendered_text',
    '_repair_json',
    '_repair_paired_annual_claim',
    '_repair_uncited_fact_claim',
    '_reporting_currency',
    '_resolve_citations',
    '_safe_activity_label',
    '_select_source_text',
    '_straight_reading',
    '_valid_fact_provenance',
    '_verify_citations',
    '_withhold_unsupported_quotations',
    '_without_source_durations',
    'answer_filing_question',
    'count_uncited_figures',
    'logger',
    'section_label_is_quoted',
    'snapshot_filing',
    'unsupported_plain_quotations',
    'unsupported_prose_quotations',
]

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
_PUBLICATION_ERROR = "I couldn't verify the cited evidence, so I couldn't provide this answer."
PROVIDER_STARTED_STAGE = "generating"  # progress stage emitted once the provider stream yields
_STREAM_FAILURE = "I couldn't complete this answer. Please try again."
_RETRYABLE_QUOTATION_FAILURES = frozenset({
    "Unsupported prose quotation: quotation_not_in_source",
    "Unsupported prose quotation: elided_quotation",
})
_EVIDENCE_RETRY_GUIDANCE = """Generate a fresh complete answer from the original filing and question.
The previous candidate failed source matching. Do not reconstruct it. Use only filing-supported
claims with the required source citations. Prefer concise paraphrases; any direct quotation must
copy one exact contiguous source span. Citation excerpts must preserve all source punctuation,
including quotation marks inside the passage; escape them correctly in JSON, never remove them.
Keep displayed follow-up questions and not-disclosed
explanations free of quotation marks. Finish the complete citation and follow-up envelopes."""


SYSTEM_PROMPT = f"""You are EarningsNerd's "Ask this Filing" assistant. You answer questions about a \
SINGLE SEC filing using ONLY the filing content provided in this conversation. You are scoped to \
this one filing — you are not a general market oracle.

RULES:
- Answer ONLY from the provided filing content. Never use outside knowledge or assumptions.
- Every factual claim MUST be supported by a verbatim excerpt quoted directly from the filing.
- Be precise, decisive, and concise. Use the filing's own numbers and language.
- Prefer concise paraphrases in answer prose, with the required source markers. If you use \
quotation marks, copy the entire quoted span contiguously and exactly from the supplied filing. \
Never stitch separate passages, insert ellipses, change source wording or numbers, or put a \
paraphrase inside quotation marks.
- Keep the DISPLAYED text of follow-up questions, not-disclosed explanations, and citation \
section labels free of quotation marks. JSON string delimiters are still required in the arrays.
- Citation EXCERPTS must preserve the source's wording and punctuation, including quotation \
marks inside the passage. Escape those marks in JSON; never remove them from the excerpt.
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
3. Then output a JSON array of citation objects for ONLY the plain numeric filing-text markers
   ([1], [2], ...) used in the answer. Each "n" must be that marker's positive JSON integer,
   never a string or an F marker. Tool [F#] markers already reference their returned facts;
   never include objects for them in this array. If there are no filing-text markers, output []
   after the citations line, including when all cited figures use tool markers. Example:
[{{"n": 1, "excerpt": "<verbatim quote copied exactly from the filing>", "section": "Item 7 — MD&A"}}]
   - "excerpt" MUST be copied verbatim from the filing content (so it can be verified). Keep each
     excerpt to the SHORTEST contiguous span that supports the claim — one sentence, at most ~30 words.
     Each text excerpt must contain at least {_MIN_VERIFIABLE_LEN} characters after whitespace is collapsed.
     When a span is too short, choose a longer contiguous source span; never pad or paraphrase it.
     Never stitch separated table cells or sentences together, or insert an ellipsis into an excerpt.
     If separate spans are needed, cite each exact span separately. For a tool-provided figure,
     reuse its existing [F#] marker; do not add a text citation merely to restate that same figure.
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
    report_period = getattr(filing, "period_end_date", None)
    if report_period is not None:
        report_period = report_period.date().isoformat() if hasattr(report_period, "date") else report_period.isoformat()
    return SimpleNamespace(
        accession_number=getattr(filing, "accession_number", None),
        period_of_report=report_period,
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


def _without_source_durations(xbrl_data: Any) -> Any:
    """Model-facing metrics without source durations or internal comparison descriptors."""
    if not isinstance(xbrl_data, dict):
        return xbrl_data
    return {
        key: [{k: v for k, v in point.items() if k != "period_start"}
              if isinstance(point, dict) else point for point in value]
        if isinstance(value, list) else value
        for key, value in xbrl_data.items()
        if key not in {"financing_comparison_source", "financial_classification"}
    }


def _compact_xbrl_block(xbrl_data: Any) -> str:
    """Render the filing's XBRL JSON compactly for context, or "" when absent/oversized.

    Numeric tools provide exact accession-scoped facts independently. This compact reference
    cannot crowd out the section excerpt.

    Source durations are dropped here even though extraction now preserves them: this block is
    truncated at a fixed cap, so every key added displaces excerpt content the model would
    otherwise see, and the tools already hand the model exact period provenance. Keeping the
    projection stable also keeps the prompt bytes — and their cache — unchanged. Widening what
    the model sees is a prompt change, gated on its own evidence.
    """
    if not xbrl_data:
        return ""
    try:
        rendered = json.dumps(_without_source_durations(xbrl_data), default=str,
                              separators=(",", ":"))
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

    currency = _reporting_currency(filing)
    currency_instruction = (
        f"REPORTING CURRENCY: {currency}. Use this native currency explicitly for monetary figures; "
        "never label them as another currency or use a bare dollar sign for non-USD amounts. "
        "Per-share values retain their currency-per-share unit; do not convert convenience translations."
        if currency else
        "REPORTING CURRENCY: unavailable. Preserve explicit currency units from each source; "
        "do not infer USD from a ticker, missing unit, or an ambiguous dollar symbol."
    )
    parts = [
        f"FILING: {company_name} ({ticker}) — {form} filed {date_str}.",
        "",
        f"VIEWED ACCESSION: {getattr(filing, 'accession_number', None) or 'unavailable'}. "
        f"REPORT PERIOD: {getattr(filing, 'period_of_report', None) or 'unavailable'}.",
        currency_instruction,
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


def _safe_activity_label(info: dict) -> str:
    """Keep model-controlled tool names and concept strings out of publication events."""
    name = info.get("name")
    if name not in ("list_available_concepts", "get_financial_fact", "compute_metric"):
        return "Reading financial information"
    args = info.get("args")
    args = args if isinstance(args, dict) else {}
    concept = args.get("concept")
    safe_args = {
        "concept": concept if isinstance(concept, str) and concept in copilot_tools._CONCEPT_LABELS else None,
        "kind": args.get("kind") if args.get("kind") in ("yoy_growth", "margin") else None,
    }
    return copilot_tools.describe_tool_call(name, safe_args)


async def answer_filing_question(
    *,
    filing: Any,
    question: str,
    history: Optional[list[dict]] = None,
) -> AsyncGenerator[dict, None]:
    """Publish one admitted answer, privately regenerating one mismatched evidence candidate.

    Both generations share the original source, usage accounting and provider deadline. Rejected
    prose is never exposed or reused; an incomplete envelope or another failure stays terminal.
    """
    try:
        source_text = _select_source_text(filing) or ""
        normalized_source = normalize_for_match(source_text)
        usage_sink: dict[str, Any] = {}
        deadline = chat_deadline()
        provider_started = False
        for attempt in range(2):
            candidate = _answer_filing_question_attempt(
                filing=filing, question=question, history=history,
                source_text=source_text, normalized_source=normalized_source,
                usage_sink=usage_sink, deadline=deadline, evidence_retry=bool(attempt),
            )
            try:
                async for event in candidate:
                    if event.get("type") == "progress" and event.get("stage") == PROVIDER_STARTED_STAGE:
                        if provider_started:
                            continue
                        provider_started = True
                    yield event
                return
            except _UnpublishableAnswer as exc:
                # Fixed owned reasons only. The discarded answer is never put into a new prompt.
                logger.warning("Copilot candidate withheld at citation publication boundary: %s", exc)
                if (attempt == 0 and (str(exc) in _RETRYABLE_QUOTATION_FAILURES
                                     or isinstance(exc, _RegenerableEvidenceMismatch))
                        and asyncio.get_running_loop().time() < deadline):
                    continue
                yield {"type": "error", "message": _PUBLICATION_ERROR}
                return
            finally:
                await candidate.aclose()
    except Exception:  # noqa: BLE001 — cancellation still propagates
        logger.exception("Copilot answer_filing_question failed")
        yield {"type": "error", "message": _STREAM_FAILURE}


async def _answer_filing_question_attempt(
    *, filing: Any, question: str, history: Optional[list[dict]], source_text: str,
    normalized_source: str, usage_sink: dict[str, Any], deadline: float, evidence_retry: bool,
) -> AsyncGenerator[dict, None]:
    """Stream a grounded answer to ``question`` about ``filing`` as event dicts.

    Yields (in order):
    * ``{"type": "progress", "stage": "reading"}`` before the model call.
    * ``{"type": "activity", "label", "phase", "ok"}`` as numeric tools run (live "show the work").
    * Fixed reading progress while candidate prose is buffered privately.
    * ``{"type": "not_disclosed", "answer": ...}`` if the model emits the not-disclosed sentinel.
    * ``{"type": "complete", "answer", "citations", "grounded", "kind", "followups"}`` at the end.
    * ``{"type": "error", "message": ...}`` on any failure.

    Ordinary failures become safe ``error`` events; cancellation still propagates. The question
    owner supplies the source normalized once and reused for every excerpt and generation.
    """
    provider_stream = None
    try:
        messages = _build_messages(filing, source_text, question, history)
        if evidence_retry:
            messages[0]["content"] += "\n\n" + _EVIDENCE_RETRY_GUIDANCE

        # P5/P6b numeric tool-use: bind tools to this filing's company, accession and native currency. ``run_tool`` opens its own
        # DB session per call (the request session is gone by now). Each distinct successful fact is
        # assigned a stable ``F#`` citation marker (deduped by exact provenance and expression operands) that
        # is fed back to the model via the tool result's ``cite`` field, so the model can cite the
        # figure inline as ``[F1]`` — rendering an inline chip, not just a Sources row.
        company_id = getattr(filing, "company_id", None)
        accession = getattr(filing, "accession_number", None)
        currency = _reporting_currency(filing)
        used_facts: list[dict] = []
        _fact_markers: dict[str, str] = {}

        def _register_fact(result: dict) -> str:
            """The stable ``F#`` marker for this exact fact/expression, deduped by provenance."""
            key = _fact_identity(result)
            marker = _fact_markers.get(key)
            if marker is None:
                marker = f"F{len(used_facts) + 1}"
                _fact_markers[key] = marker
                result["_marker"] = marker
                used_facts.append(result)
            return marker

        def _run_tool(name: str, args: dict) -> dict:
            result = copilot_tools.run_tool(name, args, company_id, accession_number=accession,
                                            reporting_currency=currency)
            if isinstance(result, dict) and "error" not in result and "value" in result:
                if not _valid_fact_provenance(result, accession, currency):
                    return {"error": "invalid_filing_provenance"}
                # Hand the model the exact inline marker to use for this figure (e.g. "[F1]").
                return {**result, "cite": _register_fact(result)}
            return result

        yield {"type": "progress", "stage": "reading"}

        answer_parts: list[str] = []          # private candidate prose (before any sentinel)
        citation_buffer: list[str] = []       # text after ===CITATIONS===
        not_disclosed_parts: list[str] = []   # text after ===NOT_DISCLOSED===
        pending = ""                          # carry-over tail for cross-chunk sentinel detection
        mode = "answer"                        # answer | citations | not_disclosed
        last_progress = monotonic()

        # The wrapper accumulates actual model, usage and recorded call costs across tool rounds.
        model_name = openai_service.model
        # Emitted once, on the provider stream's first non-error chunk: the proof the model call
        # started, which the ask-stream router meters on (not the `reading` progress above, which
        # precedes the call). A failure or disconnect before this point costs the user nothing.
        provider_started = False
        provider_stream = openai_service.stream_chat_with_tools(
            messages,
            copilot_tools.TOOLS,
            _run_tool,
            model=model_name,
            max_tokens=settings.COPILOT_MAX_TOKENS,
            temperature=0.2,
            usage_sink=usage_sink,
            deadline=deadline,
        )
        async for delta in provider_stream:
            if not delta:
                continue

            # The model stream wrapper signals an upstream/model failure with a sentinel-prefixed
            # chunk (rather than raising). Surface it as a real error event instead of letting the
            # bracketed text stream out as the answer body — a model outage must not look like a
            # confident, zero-grounded answer.
            if delta.startswith(STREAM_ERROR_SENTINEL):
                yield {"type": "error", "message": _STREAM_FAILURE}
                return

            if not provider_started:
                provider_started = True
                yield {"type": "progress", "stage": PROVIDER_STARTED_STAGE}

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
                    "label": _safe_activity_label(info),
                    "phase": "done" if info.get("phase") == "done" else "start",
                    "ok": bool(info.get("ok", True)),
                }
                continue

            if monotonic() - last_progress >= 3:
                yield {"type": "progress", "stage": "reading"}
                last_progress = monotonic()

            if mode == "citations":
                citation_buffer.append(delta)
                continue
            if mode == "not_disclosed":
                not_disclosed_parts.append(delta)
                continue

            # mode == "answer": scan the accumulated buffer for a sentinel, holding prose privately and
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
                    if cut == cit_at:
                        mode = "citations"
                        citation_buffer.append(pending[cut + len(_CITATIONS_SENTINEL):])
                    else:
                        mode = "not_disclosed"
                        not_disclosed_parts.append(pending[cut + len(_NOT_DISCLOSED_SENTINEL):])
                    pending = ""
                    break

                # No complete sentinel: buffer everything except a held-back tail that could be the
                # start of a sentinel spanning into the next chunk.
                if len(pending) > _SENTINEL_TAIL:
                    emit = pending[:-_SENTINEL_TAIL]
                    pending = pending[-_SENTINEL_TAIL:]
                    if emit:
                        answer_parts.append(emit)
                break

        # Preserve the per-call accounting, including unknown values and mixed-model totals.
        usage_payload = usage_sink or None

        # Flush any held-back tail that turned out to be plain prose.
        if mode == "answer" and pending:
            answer_parts.append(pending)

        if mode == "not_disclosed":
            if "".join(answer_parts).strip():
                raise _UnpublishableAnswer("Answer prose precedes not-disclosed verdict")
            # A complete not-disclosed verdict needs its reason and the whole required
            # followups envelope. Provider EOF or repaired JSON cannot establish completion.
            nd_raw = "".join(not_disclosed_parts)
            nd_match = _FOLLOWUPS_RE.search(nd_raw)
            if not nd_match:
                raise _UnpublishableAnswer("Missing not-disclosed followups envelope")
            answer = nd_raw[:nd_match.start()].strip()
            if not answer:
                raise _UnpublishableAnswer("Empty not-disclosed reason")
            if _CITATIONS_SENTINEL in answer or _NOT_DISCLOSED_SENTINEL in answer:
                raise _UnpublishableAnswer("Contradictory not-disclosed envelope")
            try:
                nd_followups = json.loads(nd_raw[nd_match.end():].strip())
            except (ValueError, TypeError) as exc:
                raise _UnpublishableAnswer("Incomplete not-disclosed followups array") from exc
            if (not isinstance(nd_followups, list) or not 2 <= len(nd_followups) <= 3
                    or any(not isinstance(item, str) or not item.strip() for item in nd_followups)):
                raise _UnpublishableAnswer("Invalid not-disclosed followups array")
            nd_followups = [item.strip()[:140] for item in nd_followups]
            await asyncio.to_thread(_withhold_unsupported_quotations, normalized_source, "", [answer, *nd_followups])
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
        if mode != "citations":
            raise _UnpublishableAnswer("Missing citation envelope")
        citations, followups = _parse_citations("".join(citation_buffer))

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
        referenced = {
            re.sub(r"\s+", "", match.group(1)).upper()
            for match in _COPILOT_MARKER_RE.finditer(full_answer)
        }
        text_citations_by_marker = _verify_citations(citations, filing, normalized_source, referenced)
        # Keep literal identities before repair/numbering; a later citation must not capture
        # an unrelated original [1]. Leading-zero markers keep their original identity.
        unresolved_literals = {key for key in referenced if not key.startswith("F")
                               and key not in text_citations_by_marker}
        # Supported uncited annual claims need positive certification, beyond marker removal.
        # Look up each claimed figure in the viewed filing and attach separate markers only
        # after every operand certifies; preserve every other byte of the answer.
        full_answer = _repair_uncited_fact_claim(
            full_answer, filing=filing, accession=accession, currency=currency,
            register=_register_fact,
        )
        # Single server-owned numbering pass: resolves every marker actually present in the answer
        # (text-excerpt or tool-figure alike) against its real source, assigns one continuous
        # sequential number in first-appearance order, and rewrites the answer's inline markers to
        # match — so the answer text and the returned citations list can never disagree, and a
        # declared-but-never-cited source can never leak into the Sources panel.
        filing_url = getattr(filing, "document_url", None) or getattr(filing, "sec_url", None) or None
        before_resolution = full_answer
        full_answer, verified_citations, grounded, misplaced = _resolve_citations(
            full_answer, text_citations_by_marker, used_facts, filing_url
        )
        # Unresolvable model F-markers can have hidden an otherwise eligible claim from
        # the first repair. Certify only the final visible, wholly uncited prose; never
        # reinterpret surviving citations or reuse a rejected marker as evidence.
        if not verified_citations and full_answer != before_resolution:
            repaired = _repair_uncited_fact_claim(
                full_answer, filing=filing, accession=accession, currency=currency,
                register=_register_fact,
            )
            if repaired != full_answer:
                full_answer, verified_citations, grounded, additional_misplaced = _resolve_citations(
                    repaired, {}, used_facts, filing_url,
                )
                misplaced += additional_misplaced
        if not full_answer:
            raise _UnpublishableAnswer("Empty resolved answer")
        if any(str(cite["n"]) in unresolved_literals or cite["verified"] is not True
               for cite in verified_citations):
            raise _UnpublishableAnswer("Unverified or colliding final citation")
        await asyncio.to_thread(_withhold_unsupported_quotations, normalized_source, full_answer, followups)
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
    except _UnpublishableAnswer:
        raise  # The question owner decides whether one fresh generation is possible.
    except Exception:  # noqa: BLE001 — never raise ordinary failures out of the SSE generator
        logger.exception("Copilot answer_filing_question failed")
        yield {"type": "error", "message": _STREAM_FAILURE}
    finally:
        if provider_stream is not None:
            await provider_stream.aclose()
