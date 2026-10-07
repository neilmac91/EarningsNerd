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
import html
import json
import logging
import math
import re
import unicodedata
from datetime import date
from time import monotonic
from types import SimpleNamespace
from typing import Any, AsyncGenerator, Callable, Optional

from markdown_it import MarkdownIt

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
    build_text_fragment_url,
    normalize_for_match,
    strip_wrapping_quotes,
    verify_whole_excerpt_in_text,
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
_FOLLOWUPS_RE = re.compile(r"===\s*FOLLOW-?UPS\s*===", re.IGNORECASE)
_COPILOT_MARKER_RE = re.compile(r"\[(F?\s*\d+)\]", re.IGNORECASE)
_PUBLICATION_ERROR = "I couldn't verify the cited evidence, so I couldn't provide this answer."
PROVIDER_STARTED_STAGE = "generating"  # progress stage emitted once the provider stream yields
_STREAM_FAILURE = "I couldn't complete this answer. Please try again."
_RETRYABLE_QUOTATION_FAILURE = "Unsupported prose quotation: quotation_not_in_source"
_QUOTATION_RETRY_GUIDANCE = """Generate a fresh complete answer from the original filing and question.
The previous candidate failed quotation matching. Do not reconstruct it. Use only filing-supported
claims with the required source citations. Prefer concise paraphrases; any direct quotation must
copy one exact contiguous source span. Keep displayed follow-up questions and not-disclosed
explanations free of quotation marks. Finish the complete citation and follow-up envelopes."""


class _UnpublishableAnswer(ValueError):
    """A candidate cannot cross the publication boundary."""


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


def _reporting_currency(filing: Any) -> Optional[str]:
    data = getattr(filing, "xbrl_data", None)
    unit = copilot_tools.canonical_unit(data.get("reporting_currency")) if isinstance(data, dict) else None
    return unit if unit and re.fullmatch(r"[A-Z]{3}", unit) else None


def _valid_fact_provenance(fact: dict, accession: Optional[str], currency: Optional[str] = None) -> bool:
    """The tool boundary must attest the trusted filing before a result earns a verified marker."""
    if not isinstance(accession, str) or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
        return False
    if not isinstance(fact, dict) or fact.get("accession") != accession:
        return False
    if not isinstance(fact.get("concept"), str) or not fact["concept"].strip():
        return False
    raw_tag = fact.get("raw_tag")
    if raw_tag is not None and (not isinstance(raw_tag, str) or not raw_tag.strip()):
        return False
    value = fact.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return False
    unit = copilot_tools.canonical_unit(fact.get("unit"))
    if unit is None or (currency and unit not in {"pure", "shares", currency, f"{currency}/shares"}):
        return False
    try:
        end = date.fromisoformat(fact["period_end"])
        start = date.fromisoformat(fact["period_start"]) if fact.get("period_start") else None
        if start and start > end:
            return False
    except (KeyError, TypeError, ValueError):
        return False
    kind = fact.get("kind") or fact.get("value_kind")
    if kind is not None and kind not in {"margin", "yoy_growth"}:
        return False
    if kind in {"margin", "yoy_growth"}:
        operands = fact.get("source_facts")
        if unit != "pure" or not isinstance(operands, list) or len(operands) != 2:
            return False
        if any(not _valid_fact_provenance(item, accession, currency) or item.get("kind") or item.get("value_kind")
               for item in operands):
            return False
    return True


def _fact_identity(fact: dict) -> str:
    """One marker per exact fact/expression; different operands cannot alias a result."""
    keys = ("concept", "raw_tag", "accession", "unit", "period_start", "period_end", "fiscal_year",
            "fiscal_period", "kind", "value", "denominator_concept", "source_facts")
    return json.dumps({key: fact.get(key) for key in keys}, sort_keys=True, separators=(",", ":"))


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


def _parse_citations(raw: str) -> tuple[list[dict], list[str]]:
    """Admit one complete citation array, then the optional followups envelope.

    Decode before looking for FOLLOWUPS: sentinel text inside a JSON excerpt is data.
    Never repair incomplete JSON or discard a malformed declaration as if it were absent.
    """
    text = raw.strip()
    fenced = re.match(r"^```(?:json)?\s*\n", text, re.IGNORECASE)
    if fenced:
        text = text[fenced.end():].lstrip()

    def unique_fields(pairs: list[tuple[str, Any]]) -> dict:
        result: dict = {}
        for key, value in pairs:
            if key in result:
                raise _UnpublishableAnswer("Duplicate citation field")
            result[key] = value
        return result

    def reject_constant(_value: str) -> None:
        raise _UnpublishableAnswer("Non-JSON citation value")

    try:
        data, end = json.JSONDecoder(
            object_pairs_hook=unique_fields, parse_constant=reject_constant,
        ).raw_decode(text)
    except (ValueError, TypeError) as exc:
        raise _UnpublishableAnswer("Incomplete citation array") from exc
    trailer = text[end:].strip()
    if fenced:
        if not trailer.startswith("```"):
            raise _UnpublishableAnswer("Unclosed citation fence")
        trailer = trailer[3:].strip()
    followups: list[str] = []
    if trailer:
        followups_match = _FOLLOWUPS_RE.match(trailer)
        if not followups_match:
            raise _UnpublishableAnswer("Unexpected citation trailer")
        followups = _parse_followups(trailer[followups_match.end():])
    if not isinstance(data, list):
        raise _UnpublishableAnswer("Citation declaration is not an array")
    for item in data:
        if (not isinstance(item, dict)
                or type(item.get("n")) is not int or item["n"] <= 0
                or not isinstance(item.get("excerpt"), str)
                or any(item.get(key) is not None and not isinstance(item[key], str)
                       for key in ("section", "section_ref"))):
            raise _UnpublishableAnswer("Invalid citation declaration")
    return data, followups


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


# A section label is published as-is and never matched against the filing (most legitimate labels
# are not filing text), so a label carrying a double quote mark would present an unverified
# quotation beside "Source match found"; its citation is unverified (the founder's section_ref rule).
# The marks are decision F's, read from its one definition (_QUOTE_MARK_RE below) so the two rules
# cannot drift; a label displays as plain text, so a character reference is not a mark. The Copilot
# eval's CITATION scorer reads this predicate too.
def section_label_is_quoted(label: object) -> bool:
    """Whether a citation's section label carries one of decision F's double quote marks."""
    return isinstance(label, str) and _QUOTE_MARK_RE.search(label) is not None


def _verify_citations(
    citations: list[dict], filing: Any, normalized_source: str, referenced: set[str],
) -> dict[str, dict]:
    """Verify original declarations before duplicate IDs can overwrite rejected evidence.

    Unused valid declarations remain a candidate pool only. A referenced ID must have an
    unambiguous declaration and every declaration for it must pass the whole-excerpt verifier
    (the Sources panel displays the whole excerpt as filing text) with a quote-free section label.
    The published excerpt is the declared one, never trimmed or substituted.
    """
    base_url = getattr(filing, "document_url", None) or getattr(filing, "sec_url", None) or ""
    by_marker: dict[str, dict] = {}
    declared: dict[str, dict] = {}
    for cite in citations:
        excerpt = cite["excerpt"].strip()
        section_ref = cite.get("section") or cite.get("section_ref")
        key = str(cite["n"])
        verified = (verify_whole_excerpt_in_text(excerpt, normalized_source)
                    and not section_label_is_quoted(section_ref))
        if key in referenced and (
            not verified or (key in declared and declared[key] != cite)
        ):
            raise _UnpublishableAnswer("Unverified or ambiguous referenced citation")
        declared[key] = cite
        fragment_url = (
            build_text_fragment_url(base_url, strip_wrapping_quotes(excerpt), source_span=True)
            if verified and base_url else base_url
        )
        by_marker[key] = {
            "excerpt": excerpt,
            "section_ref": section_ref,
            "verified": verified,
            "fragment_url": fragment_url,
        }
    return by_marker


# Prose quotations (decision F). The marks are the double quotes normalize_for_match folds to '"'
# (straight, “ ” „) plus ‟ (U+201F) and the fullwidth ＂ (U+FF02). Single quotes are left alone
# (apostrophes), and so are ″ (U+2033, far more often an inch or seconds sign), 〝〞〟, ❝❞, 🙶🙷 and ʺ:
# decision F's scope is these double quotes, not every quotation form. This is the one definition of
# the set: the markdown pre-filter below and the section_ref rule (section_label_is_quoted) read it.
_STRAIGHT_QUOTE_MARKS = '"\uff02'
_CLOSING_QUOTE_MARK = "\u201d"
_QUOTE_MARK_RE = re.compile('["\uff02\u201c\u201d\u201e\u201f]')
_QUOTE_EDGE_CHARS = " \t\r\n\u00a0.,;:!?\u2026"
_QUOTE_ELLIPSIS_RE = re.compile(r"\.\s*\.\s*\.|\u2026")
# The shortest quoted text checked against the filing (the founder's decision on PR #1029): shorter
# quoted terms ("ROE", "EBITDA") are labels. Citation excerpts keep the verifier's own floor,
# provenance_service._MIN_VERIFIABLE_LEN (24).
_MIN_QUOTED_LEN = 8
# The work per answer is bounded: an answer that may quote and is longer than this, holds more
# quote marks than this, or whose quotations (nested ones counted again) span more characters than
# this, fails closed unchecked. Realistic answers run to 2-3k characters; the retained evaluation
# answers hold at most 8 marks in 330 characters.
_MAX_QUOTED_ANSWER_CHARS = 8_000
_MAX_QUOTE_MARKS = 64
_MAX_QUOTED_CHARS = 20_000
# Link-label parsing grows with the brackets ('[' runs reach about 100 ms at the character bound);
# an answer that may quote and opens more than this many fails closed. Realistic answers hold a few
# dozen citation markers at most.
_MAX_BRACKETS = 256
# A mark, or a character reference that may name one (a bare "&", as in R&D, is not one).
_QUOTE_HINT_RE = re.compile(
    _QUOTE_MARK_RE.pattern + "|&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});")
# Characters that change what a reader sees without being plain visible text: C0 and C1 controls
# other than line breaks (a tab fails closed in the answer below), the Ogham space mark and the line
# and paragraph separators (a space or a break, by reader), the byte-order mark, and the bidi
# controls and right-to-left scripts (whose blocks hold the Arabic letter mark), around which the
# browser reorders marks and text. Text that may quote and holds one fails closed: it is not read,
# and it is not dropped (see _display_may_differ, which adds the astral and unassigned characters).
_FAIL_CLOSED_CHARS_RE = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u1680\u2028\u2029\ufeff\u200e\u200f\u202a-\u202e\u2066-\u2069"
    "\u0590-\u08ff\ufb1d-\ufdff\ufe70-\ufefe]")
# Unicode Default_Ignorable_Code_Point (DerivedCoreProperties, Unicode 17.0; checked against ICU) in
# the Basic Multilingual Plane and assigned in Python's tables, less the bidi controls and U+FEFF:
# never displayed, so dropped before a mark's neighbours are read. The rest fail closed.
_DEFAULT_IGNORABLE_RE = re.compile(
    "[\u00ad\u034f\u115f\u1160\u17b4\u17b5\u180b-\u180f\u200b-\u200d\u2060-\u2064\u206a-\u206f\u3164"
    "\ufe00-\ufe0f\uffa0]")
# Citation markers inside a quotation are not quoted text; anything longer is read as written.
_QUOTED_MARKER_RE = re.compile(r"\[F?\d{1,3}\]")
# The answer is displayed by react-markdown 10 with remark-gfm (micromark). It is read here with
# markdown-it-py, and only within a small subset that both parsers are assumed to read alike:
# paragraphs, headings, thematic breaks, lists, blockquotes, GFM tables, emphasis, code spans, and
# code blocks. An answer that may quote and uses anything else fails closed: link syntax (inline
# links, reference definitions, autolinks) and the raw URL and email literals GFM links by itself,
# raw HTML, images, footnotes, task-list checkboxes, tabs, runs of three or more emphasis delimiters
# or two different delimiters side by side, Unicode spaces at a line's edge, nesting past
# _MAX_MARKDOWN_NESTING, and the forms below on which a fuzz against the display found the parsers
# to differ (lazy lines, stray table rows, some list openings). A URL or address built from
# character references or escapes (www&#46;sec.gov) is linked by the display too, but it shows the
# same text, so it is read as text. Within the subset some guards remain: a delimiter left as text
# may still vanish when displayed, so a mark's direction that one decides is ambiguous; a '*' or
# '_' left as text where there is emphasis, one delimiter run split between two emphasis tokens, a
# tilde beside emphasis, or a backtick left as text may change what the display pairs. That the two
# parsers agree on this subset is the residual assumption; it is not exact parity with the display.


def _markdown_parser() -> MarkdownIt:
    """The shared parser, its rules compiled. markdown-it compiles its rule chains on first use, and
    mdurl fills its encoding and decoding caches on first use, each publishing an empty cache before
    filling it, so a first parse in two worker threads at once could run without them. Link syntax
    never reaches the reading (it fails closed before parsing, so mdurl is not called on one); the
    autolink parsed here fills both mdurl caches, and the inline link is a harmless extra. After this
    one parse the instance is only read."""
    parser = MarkdownIt("commonmark", {"html": False}).enable("table")
    parser.parse("[x](y) <http://z>")
    return parser


_MARKDOWN = _markdown_parser()
# Block ends, and a thematic break, show as line breaks.
_MARKDOWN_BLOCK_ENDS = frozenset({
    "paragraph_close", "heading_close", "blockquote_close", "list_item_close", "bullet_list_close",
    "ordered_list_close", "thead_close", "tbody_close", "tr_close", "th_close", "td_close", "table_close", "hr",
})
_MARKDOWN_BLOCKS = _MARKDOWN_BLOCK_ENDS | {
    "paragraph_open", "heading_open", "blockquote_open", "list_item_open", "bullet_list_open",
    "ordered_list_open", "thead_open", "tbody_open", "tr_open", "th_open", "td_open", "table_open",
    "inline", "fence", "code_block",
}
_MARKDOWN_INLINE = frozenset({
    "text", "softbreak", "hardbreak", "em_open", "em_close", "strong_open", "strong_close", "code_inline",
})
_MARKDOWN_BREAKS = ("softbreak", "hardbreak")
_MARKDOWN_EMPHASIS = ("em_open", "em_close", "strong_open", "strong_close")
_MARKDOWN_CONTAINERS = {"blockquote_open": 1, "blockquote_close": -1, "bullet_list_open": 1,
                        "bullet_list_close": -1, "ordered_list_open": 1, "ordered_list_close": -1}
# Nested blockquotes and lists, together. This keeps every token far below markdown-it's maxNesting
# (20), past which it stops parsing; the display has no such cap.
_MAX_MARKDOWN_NESTING = 4
# Found in the source text before parsing, since each always fails closed: an image, footnote
# syntax, a tab (expanded differently in indentation and table rows), a run of three or more '*' or
# '_' (which the parsers pair differently), two different emphasis or strikethrough delimiters side
# by side (micromark lets a '*' or '_' run beside any other of '*', '_' and GFM's '~' open or close,
# where CommonMark and markdown-it read that neighbour as punctuation), and raw HTML of any kind
# (markdown-it's HTML parsing stays off; it also catches autolinks such as <https://...>).
_OUTSIDE_SUBSET_RE = re.compile(r"!\[|\[\^|\t|\*{3}|_{3}|\*[_~]|_[*~]|~[*_]")
_RAW_HTML_RE = re.compile(r"<[A-Za-z/!?]")
# Link syntax and raw URL and email literals, also found before parsing: an inline link or a
# reference definition (the only markdown here that reaches markdown-it's link normalization, so
# mdurl never runs on a reading), or a literal GFM links by itself: a URL, a www. address, or an
# email address ('@' between two characters, which also finds mailto: and xmpp: addresses and
# '<...@...>' autolinks; '<scheme:...>' autolinks are found as raw HTML). No answer in the retained
# evaluation runs holds one (0 of 576).
_LINK_RE = re.compile(r"\]\(|\]:|www\.|https?://|\S@\S", re.IGNORECASE)
# A Unicode space at a line's edge, also found before parsing (in the answer with its line endings
# normalized, as markdown-it normalizes them). These are the whitespace characters Python's
# str.strip() removes besides those that fail closed anyway (_display_may_differ) and the space,
# tab and line endings: U+00A0, U+2000-U+200A, U+202F, U+205F and U+3000. markdown-it strips them
# from a table row (rules_block/table.py), a paragraph (paragraph.py), a setext heading
# (lheading.py) and an ATX heading's content (heading.py), where micromark trims only spaces and
# tabs, so at a line's edge they can change the blocks the display shows (a table header the
# display does not take as one, a line the display breaks after a trailing backslash). Elsewhere in
# a line the only differences are whitespace at the edge of a table cell, a heading, or a paragraph
# that starts after a blockquote or list marker, and the padding of a code span that holds only
# whitespace; the reading and the shared normalization treat these alike.
_UNICODE_SPACES = "\u00a0\u2000-\u200a\u202f\u205f\u3000"
_LINE_EDGE_SPACE_RE = re.compile(f"(?m)^[ \t]*[{_UNICODE_SPACES}]|[{_UNICODE_SPACES}][ \t]*$")
# A GFM task-list checkbox, which the display draws as a box instead of this text.
_TASK_CHECKBOX_RE = re.compile(r"\[[ \txX]\]")
# Blockquotes and GFM tables are read only outside any container and with every line starting with
# their marker (no lazy continuation lines). Any other line that GFM might take for a table's
# delimiter row (pipes and dashes, perhaps behind container markers) is outside the subset.
_TOP_LEVEL_BLOCKS = {"blockquote_open": re.compile(r" {0,3}>"), "table_open": re.compile(r" {0,3}\|")}
_TABLE_DELIMITER_LIKE_RE = re.compile(r"[ \t>+*0-9.):-]*\|[ \t>+*0-9.):|-]*")
_MAYBE_HIDDEN = "*_~"


def _rendered_text(answer: str) -> Optional[str]:
    """The answer's text as the reader sees it, or None when it uses markdown outside the subset.

    Character references and escapes show their characters, block ends show as line breaks, and code
    is shown verbatim. Used only to decide; never published.
    """
    env: dict = {}
    tokens = _MARKDOWN.parse(answer, env)
    if env.get("references"):
        return None
    lines = re.split(r"\r\n?|\n", answer)
    delimiter_rows = {at for at, line in enumerate(lines) if "-" in line and _TABLE_DELIMITER_LIKE_RE.fullmatch(line)}
    parts: list[str] = []
    depth = 0
    for index, token in enumerate(tokens):
        outer = depth
        depth += _MARKDOWN_CONTAINERS.get(token.type, 0)
        if token.type not in _MARKDOWN_BLOCKS or depth > _MAX_MARKDOWN_NESTING:
            return None
        start, end = token.map or (0, 0)
        if token.type in _TOP_LEVEL_BLOCKS:
            if outer or not all(_TOP_LEVEL_BLOCKS[token.type].match(line) for line in lines[start:end]):
                return None
            if token.type == "table_open":
                delimiter_rows.discard(start + 1)
        if token.type == "code_block" and start and lines[start - 1].strip(" "):
            return None  # indented code right after text, where GFM continues the text instead
        if token.type == "list_item_open" and (tokens[index + 1].type == "list_item_close"
                                               or (tokens[index + 1].map or (start,))[0] > start):
            return None  # an item opening on a blank line, which the display may show as its marker
        number = token.attrGet("start")
        if token.type == "ordered_list_open" and number not in (None, 1) and (
                (index and tokens[index - 1].type == "code_block") or not re.match(f" *0*{number}[.)]", lines[start])):
            return None  # numbered past 1 after a code block or another marker: GFM may show it as text
        if token.type == "inline":
            inline = _rendered_inline(token.children or [])
            if inline is None or _TASK_CHECKBOX_RE.match(token.content):
                return None
            parts.append(inline)
        elif token.type in ("fence", "code_block"):
            parts.append(token.content)
        elif token.type in _MARKDOWN_BLOCK_ENDS:
            parts.append("\n")
    text = "".join(parts)
    # Character references can name what the source text may not hold.
    return None if delimiter_rows or _display_may_differ(text) else text


def _rendered_inline(children: list) -> Optional[str]:
    parts: list[str] = []
    emphasis = any(child.type in _MARKDOWN_EMPHASIS for child in children)
    for index, child in enumerate(children):
        if child.type not in _MARKDOWN_INLINE:
            return None
        if (index and child.type in _MARKDOWN_EMPHASIS and children[index - 1].type in _MARKDOWN_EMPHASIS
                and child.markup[0] == children[index - 1].markup[0]):
            return None  # one delimiter run split between two emphasis tokens: GFM may pair it otherwise
        if child.type in _MARKDOWN_BREAKS:
            parts.append("\n")
        elif child.type == "code_inline":
            parts.append(child.content)
        else:
            text = child.content
            before = children[index - 1].type if index else "softbreak"
            after = children[index + 1].type if index + 1 < len(children) else "softbreak"
            if "`" in text:
                return None  # a backtick left as text may open a code span when displayed
            if text and ((text[0] == "~" and before in _MARKDOWN_EMPHASIS)
                         or (text[-1] == "~" and after in _MARKDOWN_EMPHASIS)):
                return None  # a tilde beside emphasis: GFM may pair the runs otherwise
            if emphasis and _may_delimit(text):
                return None  # a '*' or '_' left as text where there is emphasis: GFM may pair them otherwise
            parts.append(text)
    return "".join(parts)


def _display_may_differ(text: str) -> bool:
    """Whether ``text`` holds a character the display may show differently from this reading: one
    in _FAIL_CLOSED_CHARS_RE, an astral character (micromark classifies those by UTF-16 unit), or
    one unassigned in Python's Unicode tables (the browser's tables may assign it)."""
    return bool(_FAIL_CLOSED_CHARS_RE.search(text)) or any(
        char > "\uffff" or unicodedata.category(char) == "Cn" for char in text if char > "\x7f")


def _may_delimit(text: str) -> bool:
    """Whether a '*' or '_' left as text could open or close emphasis: not one between spaces, nor an
    underscore inside a word."""
    for at, char in enumerate(text):
        if char in "*_":
            before, after = text[at - 1:at], text[at + 1:at + 2]
            if not (before.isspace() and after.isspace()) and not (
                    char == "_" and before.isalnum() and after.isalnum()):
                return True
    return False


def _is_punctuation(char: str) -> bool:
    return unicodedata.category(char)[0] in "PS"


def _beside(text: str, at: int, step: int, maybe_hidden: str) -> set[str]:
    """What a reader may see just before (step -1) or after (step 1) the mark at ``at``.

    Combining marks draw on a neighbour, so they are passed over; text edges read as whitespace. A
    delimiter in ``maybe_hidden`` may still vanish when displayed, so beside one the character beyond
    it is possible too.
    """
    seen: set[str] = set()
    index = at + step
    while True:
        while 0 <= index < len(text) and unicodedata.category(text[index]) in ("Mn", "Me"):
            index += step
        char = text[index] if 0 <= index < len(text) else " "
        seen.add(char)
        if char not in maybe_hidden:
            return seen
        index += step


def _straight_reading(marks: list[tuple[int, str]]) -> tuple[int, list[tuple[int, int]]]:
    """How many balanced readings one stretch of straight marks admits (0, 1, or 2 for two or more),
    and the pairs of the reading when there is exactly one.

    ``layers[k]`` maps each depth reachable after ``k`` marks to the number of readings reaching it,
    capped at 2, so the work is marks times depths rather than the number of readings.
    """
    layers: list[dict[int, int]] = [{0: 1}]
    for _, role in marks:
        layer: dict[int, int] = {}
        for depth, count in layers[-1].items():
            if role != "close":
                layer[depth + 1] = min(2, layer.get(depth + 1, 0) + count)
            if role != "open" and depth:
                layer[depth - 1] = min(2, layer.get(depth - 1, 0) + count)
        layers.append(layer)
    count = layers[-1].get(0, 0)
    if count != 1:
        return count, []
    # Walk the one reading back from its end: each step on it has exactly one predecessor.
    closings: list[bool] = []
    depth = 0
    for index in range(len(marks), 0, -1):
        closing = marks[index - 1][1] != "open" and depth + 1 in layers[index - 1]
        closings.append(closing)
        depth += 1 if closing else -1
    opened: list[int] = []
    pairs: list[tuple[int, int]] = []
    for (at, _), closing in zip(marks, reversed(closings)):
        if closing:
            pairs.append((opened.pop(), at))
        else:
            opened.append(at)
    return 1, pairs


def _quotation_reading(text: str, maybe_hidden: str) -> list[tuple[int, int]] | str:
    """(opening, closing) mark offsets of the one reading the marks admit.

    “ „ ‟ open and ” closes; a straight mark takes its direction from its neighbours, as CommonMark
    reads emphasis. A mark can open when the next character is not whitespace and is not
    punctuation (Unicode P or S) unless whitespace or punctuation precedes the mark; closing
    mirrors this. A straight mark that can do both or neither may do either. Curly marks pair
    with curly marks by glyph; straight marks pair only with straight marks of the same stretch
    between curly marks. So '"x "y" z"' and '"x ("y") z"' read only as nested quotations, and
    every span is checked. Every balanced reading is counted (``_straight_reading``). Returns a
    reason code instead when a curly mark faces the wrong way, when a mark's direction depends on
    whether a delimiter shows, when no balanced reading exists, when more than one does, or when
    there are more than ``_MAX_QUOTE_MARKS`` marks.
    """
    found = list(_QUOTE_MARK_RE.finditer(text))
    if len(found) > _MAX_QUOTE_MARKS:
        return "ambiguous_quotation"
    curly_open: list[int] = []
    stretches: dict[int, list[tuple[int, str]]] = {-1: []}
    pairs: list[tuple[int, int]] = []
    for match in found:
        at, glyph = match.start(), match.group()
        roles: set[str | bool] = set()
        for before in _beside(text, at, -1, maybe_hidden):
            for after in _beside(text, at, 1, maybe_hidden):
                opens = not after.isspace() and (
                    not _is_punctuation(after) or before.isspace() or _is_punctuation(before))
                closes = not before.isspace() and (
                    not _is_punctuation(before) or after.isspace() or _is_punctuation(after))
                if glyph in _STRAIGHT_QUOTE_MARKS:
                    roles.add("either" if opens == closes else "open" if opens else "close")
                else:
                    roles.add(closes if glyph == _CLOSING_QUOTE_MARK else opens)
        if len(roles) > 1 or False in roles:
            return "ambiguous_quotation"
        if glyph in _STRAIGHT_QUOTE_MARKS:
            stretches[curly_open[-1] if curly_open else -1].append((at, roles.pop()))
        elif glyph != _CLOSING_QUOTE_MARK:
            curly_open.append(at)
            stretches[at] = []
        elif curly_open:
            pairs.append((curly_open.pop(), at))
        else:
            return "unbalanced_quotation"
    if curly_open:
        return "unbalanced_quotation"
    counts: list[int] = []
    for marks in stretches.values():
        count, stretch_pairs = _straight_reading(marks)
        counts.append(count)
        pairs += stretch_pairs
    if 0 in counts:
        return "unbalanced_quotation"
    return "ambiguous_quotation" if max(counts) > 1 else sorted(pairs)


def unsupported_prose_quotations(answer: str, normalized_source: str) -> list[str]:
    """Reason codes for double-quoted spans of a markdown answer the filing text cannot show contiguously.

    Only double quotation marks are in scope; single quotes, guillemets, other marks and markdown
    blockquotes are not checked. The answer is read as displayed (``_rendered_text``), for this
    decision only; the published answer is never rewritten. A quotation is in scope when it holds
    at least ``_MIN_QUOTED_LEN`` characters after the shared normalization (the one place this
    floor is read) or an interior ellipsis; shorter quoted terms ("ROE", "EBITDA") are labels, not
    source quotations. An in-scope quotation must occur
    contiguously in ``normalized_source``; citation markers and edge punctuation are not quoted
    text. A nested quotation is checked both whole and inner, and reasons follow the opening
    marks, so an outer quotation's reason precedes its inner one's. Missing source text, marks
    that admit no reading or more than one, markdown outside the read subset, characters the
    display may show otherwise (``_display_may_differ``), and answers past the work bounds fail
    closed. Nothing is repaired or stitched: any reason withholds the whole answer.
    """
    if not _QUOTE_HINT_RE.search(answer):
        return []
    text = None
    if not (len(answer) > _MAX_QUOTED_ANSWER_CHARS or answer.count("[") > _MAX_BRACKETS
            or _display_may_differ(answer) or _OUTSIDE_SUBSET_RE.search(answer) or _LINK_RE.search(answer)
            or _RAW_HTML_RE.search(answer) or _LINE_EDGE_SPACE_RE.search(re.sub(r"\r\n?", "\n", answer))):
        text = _rendered_text(answer)
    if text is None:
        return ["ambiguous_quotation"] if _QUOTE_MARK_RE.search(html.unescape(answer)) else []
    return _displayed_quotation_reasons(_DEFAULT_IGNORABLE_RE.sub("", text), normalized_source, _MAYBE_HIDDEN)


def unsupported_plain_quotations(text: str, normalized_source: str) -> list[str]:
    """``unsupported_prose_quotations`` for prose displayed as plain text, with no markdown: the
    not-disclosed reason and the follow-up questions."""
    if not _QUOTE_MARK_RE.search(text):
        return []
    if len(text) > _MAX_QUOTED_ANSWER_CHARS or _display_may_differ(text):
        return ["ambiguous_quotation"]
    return _displayed_quotation_reasons(_DEFAULT_IGNORABLE_RE.sub("", text), normalized_source, "")


def _displayed_quotation_reasons(text: str, normalized_source: str, maybe_hidden: str) -> list[str]:
    """The reason codes for ``text`` as displayed, where ``maybe_hidden`` delimiters may yet vanish."""
    reading = _quotation_reading(text, maybe_hidden)
    if isinstance(reading, str):
        return [reading]
    if sum(end - start for start, end in reading) > _MAX_QUOTED_CHARS:
        return ["ambiguous_quotation"]
    reasons: list[str] = []
    for start, end in reading:
        raw = text[start + 1:end]
        content = _QUOTED_MARKER_RE.sub(" ", raw).strip(_QUOTE_EDGE_CHARS)
        needle = normalize_for_match(content)
        elided = bool(_QUOTE_ELLIPSIS_RE.search(content))
        if not elided and len(needle) < _MIN_QUOTED_LEN:
            continue
        if not normalized_source:
            reasons.append("quotation_source_unavailable")
        elif (needle not in normalized_source
              and normalize_for_match(raw.strip(_QUOTE_EDGE_CHARS)) not in normalized_source):
            # Literal second: a filing can print "Note [7]".
            reasons.append("elided_quotation" if elided else "quotation_not_in_source")
    return reasons


def _withhold_unsupported_quotations(normalized_source: str, markdown: str, plain: list[str]) -> None:
    """Raise when published prose quotes text the filing cannot show; the log gets only the code.

    ``markdown`` is displayed as markdown (the answer), ``plain`` as plain text (the not-disclosed
    reason, the follow-up questions). Any failure withholds the whole response.
    """
    failures = unsupported_prose_quotations(markdown, normalized_source) if markdown else []
    for text in plain:
        failures = failures or unsupported_plain_quotations(text, normalized_source)
    if failures:
        raise _UnpublishableAnswer(f"Unsupported prose quotation: {failures[0]}")


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


# Explicit currency labels attached to a financial figure; absent labels remain unknown.
_CURRENCY_TOKEN = r"(?:U\.S\. dollars?|US dollars?|euros?|pounds sterling|Chinese yuan|renminbi|US\$|NT\$|HK\$|RMB|CNY|USD|TWD|EUR|GBP|JPY|CAD|AUD|HKD|DKK|CHF|€|£|\$)"
_CURRENCY_BEFORE = re.compile(r"(?<![A-Za-z])(" + _CURRENCY_TOKEN + r")\s*$", re.I)
_CURRENCY_AFTER = re.compile(r"^\s*(" + _CURRENCY_TOKEN + r")(?![A-Za-z])", re.I)
_CURRENCY_ALIASES = {"US$": "USD", "$": "USD", "NT$": "TWD", "HK$": "HKD", "€": "EUR", "£": "GBP", "RMB": "CNY", "U.S. DOLLAR": "USD", "U.S. DOLLARS": "USD", "US DOLLAR": "USD", "US DOLLARS": "USD", "EURO": "EUR", "EUROS": "EUR", "POUNDS STERLING": "GBP", "CHINESE YUAN": "CNY", "RENMINBI": "CNY"}


def _fact_matches_adjacent_currency(fact: dict, window: str) -> bool:
    """Falsify explicit wrong currency on a matching figure, without guessing absent currency."""
    unit = copilot_tools.canonical_unit(fact.get("unit"))
    if unit is None or unit in {"pure", "shares"}:
        return True
    expected = unit.split("/", 1)[0]
    # Supported inline emphasis/code delimiters do not separate currency from its figure.
    window = re.sub(r"[*_`]+", "", window)
    scrubbed = re.sub(r"\[\s*F?\s*\d+\s*\]", " ", window, flags=re.I)
    for match in _NUMBER_TOKEN.finditer(scrubbed):
        if not _fact_matches_adjacent_number(fact, match[0]):
            continue
        before = _CURRENCY_BEFORE.search(scrubbed[:match.start()].rstrip())
        # The number token owns an optional bare $, so inspect the currency prefix including it.
        if match[1]:
            before = _CURRENCY_BEFORE.search(scrubbed[:match.start(1) + 1].rstrip())
        after = _CURRENCY_AFTER.match(scrubbed[match.end():])
        for declared in (before, after):
            if declared:
                label = declared[1].upper()
                if _CURRENCY_ALIASES.get(label, label) != expected:
                    return False
    return True


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


# ---------------------------------------------------------------------------------------------
# Server-owned repair for wholly uncited, explicitly supported annual claim shapes.
#
# The guards above only ever REMOVE a marker the model placed wrongly. They cannot help the other
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
    * The **companyfacts fallback** cannot. ``edgar/xbrl_service.py``'s ``filter_and_sort`` only
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


async def answer_filing_question(
    *,
    filing: Any,
    question: str,
    history: Optional[list[dict]] = None,
) -> AsyncGenerator[dict, None]:
    """Publish one admitted answer, privately regenerating one mismatched quotation candidate.

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
                usage_sink=usage_sink, deadline=deadline, quotation_retry=bool(attempt),
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
                if (attempt == 0 and str(exc) == _RETRYABLE_QUOTATION_FAILURE
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
    normalized_source: str, usage_sink: dict[str, Any], deadline: float, quotation_retry: bool,
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
        if quotation_retry:
            messages[0]["content"] += "\n\n" + _QUOTATION_RETRY_GUIDANCE

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
