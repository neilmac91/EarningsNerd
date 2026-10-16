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
from types import SimpleNamespace  # noqa: F401 - call-time prompt seam
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
    _MIN_VERIFIABLE_LEN,  # noqa: F401 - preserve the facade import surface
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

from app.services.copilot.prompt import (
    SYSTEM_PROMPT, _CITATIONS_SENTINEL, _NOT_DISCLOSED_SENTINEL, _SENTINEL_TAIL,
    _FOLLOWUPS_SENTINEL, _EVIDENCE_RETRY_GUIDANCE, _select_source_text, snapshot_filing,
    _without_source_durations, _compact_xbrl_block, _build_context_message,
    _merge_consecutive_roles, _build_messages,
)

__all__ = [
    'PROVIDER_STARTED_STAGE', 'SYSTEM_PROMPT',
    '_ADJACENCY_WINDOW_CHARS', '_ANNUAL_DURATION_DAYS',
    '_ANNUAL_FIGURE_CLAIM', '_ANNUAL_REPORT_FORMS',
    '_CITATIONS_SENTINEL', '_CLAIM_PHRASE_CONCEPT',
    '_CLAIM_SCALES', '_CLAUSE_BOUNDARY',
    '_CLOSING_QUOTE_MARK', '_CONCEPT_PATTERNS',
    '_CONCEPT_SYNONYMS', '_COPILOT_MARKER_RE',
    '_CURRENCY_AFTER', '_CURRENCY_ALIASES',
    '_CURRENCY_BEFORE', '_CURRENCY_TOKEN',
    '_DEFAULT_IGNORABLE_RE', '_EVIDENCE_RETRY_GUIDANCE',
    '_FAIL_CLOSED_CHARS_RE', '_FOLLOWUPS_RE',
    '_FOLLOWUPS_SENTINEL', '_HAS_JSON_REPAIR',
    '_LINE_EDGE_SPACE_RE', '_LINK_RE',
    '_MARKDOWN', '_MARKDOWN_BLOCKS',
    '_MARKDOWN_BLOCK_ENDS', '_MARKDOWN_BREAKS',
    '_MARKDOWN_CONTAINERS', '_MARKDOWN_EMPHASIS',
    '_MARKDOWN_INLINE', '_MAX_BRACKETS',
    '_MAX_MARKDOWN_NESTING', '_MAX_QUOTED_ANSWER_CHARS',
    '_MAX_QUOTED_CHARS', '_MAX_QUOTE_MARKS',
    '_MAYBE_HIDDEN', '_MIN_QUOTED_LEN',
    '_MONTH_NAMES', '_NOT_DISCLOSED_SENTINEL',
    '_NUMBER_TOKEN', '_OUTSIDE_SUBSET_RE',
    '_PAIRED_ANNUAL_CLAIM', '_PUBLICATION_ERROR',
    '_QUOTED_MARKER_RE', '_QUOTE_EDGE_CHARS',
    '_QUOTE_ELLIPSIS_RE', '_QUOTE_HINT_RE',
    '_QUOTE_MARK_RE', '_RAW_HTML_RE',
    '_REPAIRABLE_CLAIM_PHRASES', '_RETRYABLE_QUOTATION_FAILURES',
    '_RegenerableEvidenceMismatch', '_SENTINEL_TAIL',
    '_SERVER_LOOKUP_ORIGIN', '_STRAIGHT_QUOTE_MARKS',
    '_STREAM_FAILURE', '_TABLE_DELIMITER_LIKE_RE',
    '_TASK_CHECKBOX_RE', '_TOP_LEVEL_BLOCKS',
    '_UNICODE_SPACES', '_UnpublishableAnswer',
    '_adjacency_window', '_answer_filing_question_attempt',
    '_beside', '_build_context_message',
    '_build_messages', '_claim_span_start',
    '_compact_xbrl_block', '_display_may_differ',
    '_displayed_quotation_reasons', '_fact_certifies_claim',
    '_fact_identity', '_fact_matches_adjacent_concept',
    '_fact_matches_adjacent_currency', '_fact_matches_adjacent_number',
    '_is_annual_report_form', '_is_punctuation',
    '_iso_day', '_markdown_parser',
    '_may_delimit', '_merge_consecutive_roles',
    '_parse_citations', '_parse_followups',
    '_plan_uncited_fact_citation', '_quotation_reading',
    '_rendered_inline', '_rendered_text',
    '_repair_json', '_repair_paired_annual_claim',
    '_repair_uncited_fact_claim', '_reporting_currency',
    '_resolve_citations', '_safe_activity_label',
    '_select_source_text', '_straight_reading',
    '_valid_fact_provenance', '_verify_citations',
    '_withhold_unsupported_quotations', '_without_source_durations',
    'answer_filing_question', 'count_uncited_figures',
    'logger', 'section_label_is_quoted',
    'snapshot_filing', 'unsupported_plain_quotations',
    'unsupported_prose_quotations',
]

logger = logging.getLogger(__name__)

_PUBLICATION_ERROR = "I couldn't verify the cited evidence, so I couldn't provide this answer."
PROVIDER_STARTED_STAGE = "generating"  # progress stage emitted once the provider stream yields
_STREAM_FAILURE = "I couldn't complete this answer. Please try again."
_RETRYABLE_QUOTATION_FAILURES = frozenset({
    "Unsupported prose quotation: quotation_not_in_source",
    "Unsupported prose quotation: elided_quotation",
})
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


class _FactRegistry:
    """Keep the attempt's original tool closures and shared fact list together."""

    def __init__(self, filing: Any) -> None:
        # P5/P6b numeric tool-use: bind tools to this filing's company, accession and native currency. ``run_tool`` opens its own
        # DB session per call, in a worker thread (the request session is gone by now). Each distinct successful fact is
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

        self.accession = accession
        self.currency = currency
        self.used_facts = used_facts
        self.register = _register_fact
        self.run_tool = _run_tool


class _SentinelScanner:
    """Buffer candidate prose and split envelopes without owning stream events."""

    def __init__(self) -> None:
        self.answer_parts: list[str] = []          # private candidate prose (before any sentinel)
        self.citation_buffer: list[str] = []       # text after ===CITATIONS===
        self.not_disclosed_parts: list[str] = []   # text after ===NOT_DISCLOSED===
        self.pending = ""                          # carry-over tail for cross-chunk sentinel detection
        self.mode = "answer"                        # answer | citations | not_disclosed

    def feed(self, delta: str) -> None:
        if self.mode == "citations":
            self.citation_buffer.append(delta)
            return
        if self.mode == "not_disclosed":
            self.not_disclosed_parts.append(delta)
            return

        # mode == "answer": scan the accumulated buffer for a sentinel, holding prose privately and
        # holding back a tail so a sentinel split across chunks is still caught.
        self.pending += delta
        while True:
            cit_at = self.pending.find(_CITATIONS_SENTINEL)
            nd_at = self.pending.find(_NOT_DISCLOSED_SENTINEL)
            # Earliest sentinel wins (filter out the -1 "not found" sentinels).
            hits = [pos for pos in (cit_at, nd_at) if pos != -1]
            if hits:
                cut = min(hits)
                prose = self.pending[:cut]
                if prose:
                    self.answer_parts.append(prose)
                if cut == cit_at:
                    self.mode = "citations"
                    self.citation_buffer.append(self.pending[cut + len(_CITATIONS_SENTINEL):])
                else:
                    self.mode = "not_disclosed"
                    self.not_disclosed_parts.append(self.pending[cut + len(_NOT_DISCLOSED_SENTINEL):])
                self.pending = ""
                break

            # No complete sentinel: buffer everything except a held-back tail that could be the
            # start of a sentinel spanning into the next chunk.
            if len(self.pending) > _SENTINEL_TAIL:
                emit = self.pending[:-_SENTINEL_TAIL]
                self.pending = self.pending[-_SENTINEL_TAIL:]
                if emit:
                    self.answer_parts.append(emit)
            break

    def flush(self) -> None:
        # Flush any held-back tail that turned out to be plain prose.
        if self.mode == "answer" and self.pending:
            self.answer_parts.append(self.pending)


def _activity_event(delta: str) -> dict:
    try:
        info = json.loads(delta[len(STREAM_ACTIVITY_SENTINEL):])
        if not isinstance(info, dict):
            info = {}
    except (ValueError, TypeError):
        info = {}
    return {
        "type": "activity",
        "label": _safe_activity_label(info),
        "phase": "done" if info.get("phase") == "done" else "start",
        "ok": bool(info.get("ok", True)),
    }


async def _admit_not_disclosed(
    scanner: _SentinelScanner, normalized_source: str,
) -> tuple[str, list[str]]:
    if "".join(scanner.answer_parts).strip():
        raise _UnpublishableAnswer("Answer prose precedes not-disclosed verdict")
    # A complete not-disclosed verdict needs its reason and the whole required
    # followups envelope. Provider EOF or repaired JSON cannot establish completion.
    nd_raw = "".join(scanner.not_disclosed_parts)
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
    return answer, nd_followups


def _resolve_answer(
    full_answer: str, filing: Any, text_citations_by_marker: dict,
    accession: Any, currency: Any, used_facts: list[dict],
    _register_fact: Callable[[dict], str],
) -> tuple[str, list[dict], int, int]:
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
    return full_answer, verified_citations, grounded, misplaced


async def _admit_answer(
    scanner: _SentinelScanner, filing: Any, normalized_source: str,
    facts: _FactRegistry, usage_payload: Optional[dict],
) -> dict:
    full_answer = "".join(scanner.answer_parts).strip()
    if scanner.mode != "citations":
        raise _UnpublishableAnswer("Missing citation envelope")
    citations, followups = _parse_citations("".join(scanner.citation_buffer))

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
    # Claim-repair lookups can wait for a pool slot, so resolve in a worker thread, not on the loop.
    full_answer, verified_citations, grounded, misplaced = await asyncio.to_thread(
        _resolve_answer, full_answer, filing, text_citations_by_marker, facts.accession,
        facts.currency, facts.used_facts, facts.register)
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

    return {
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
        facts = _FactRegistry(filing)

        # This generator owns every stream suspension and the provider close.
        yield {"type": "progress", "stage": "reading"}
        scanner = _SentinelScanner()
        last_progress = monotonic()
        model_name = openai_service.model
        provider_started = False
        # Resolve the singleton and its stream method here, after the first reading yield.
        provider_stream = openai_service.stream_chat_with_tools(
            messages, copilot_tools.TOOLS, facts.run_tool, model=model_name,
            max_tokens=settings.COPILOT_MAX_TOKENS, temperature=0.2,
            usage_sink=usage_sink, deadline=deadline,
        )
        async for delta in provider_stream:
            if not delta:
                continue
            if delta.startswith(STREAM_ERROR_SENTINEL):
                yield {"type": "error", "message": _STREAM_FAILURE}
                return
            if not provider_started:
                provider_started = True
                yield {"type": "progress", "stage": PROVIDER_STARTED_STAGE}
            if delta.startswith(STREAM_ACTIVITY_SENTINEL):
                yield _activity_event(delta)
                continue
            if monotonic() - last_progress >= 3:
                yield {"type": "progress", "stage": "reading"}
                last_progress = monotonic()
            scanner.feed(delta)

        # Preserve unknown usage and mixed-model totals before flushing the private tail.
        usage_payload = usage_sink or None
        scanner.flush()
        if scanner.mode == "not_disclosed":
            answer, nd_followups = await _admit_not_disclosed(scanner, normalized_source)
            yield {"type": "not_disclosed", "answer": answer}
            yield {
                "type": "complete", "answer": answer, "citations": [], "grounded": 0,
                "kind": "not_disclosed", "followups": nd_followups, "usage": usage_payload,
            }
            return

        yield await _admit_answer(scanner, filing, normalized_source, facts, usage_payload)
    except _UnpublishableAnswer:
        raise  # The question owner decides whether one fresh generation is possible.
    except Exception:  # noqa: BLE001 — never raise ordinary failures out of the SSE generator
        logger.exception("Copilot answer_filing_question failed")
        yield {"type": "error", "message": _STREAM_FAILURE}
    finally:
        if provider_stream is not None:
            await provider_stream.aclose()
