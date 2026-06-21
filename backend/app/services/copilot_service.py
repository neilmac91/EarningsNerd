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
from types import SimpleNamespace
from typing import Any, AsyncGenerator, Optional

from app.config import settings
from app.services import copilot_tools
from app.services.openai_service import STREAM_ERROR_SENTINEL, openai_service
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

OUTPUT FORMAT (follow exactly):
1. Write the answer as prose. Place inline citation markers like [1], [2] immediately after each \
claim they support.
2. Then output a line containing exactly:
{_CITATIONS_SENTINEL}
3. Then output a JSON array of citation objects, one per marker you used, e.g.:
[{{"n": 1, "excerpt": "<verbatim quote copied exactly from the filing>", "section": "Item 7 — MD&A"}}]
   - "excerpt" MUST be copied verbatim from the filing content (so it can be verified).
   - "section" is the filing section it came from (e.g. "Item 1A — Risk Factors").

IF THE FILING DOES NOT DISCLOSE THE ANSWER, do NOT write prose or citations. Instead output exactly:
{_NOT_DISCLOSED_SENTINEL}
<one sentence stating what is missing and why this filing would not contain it>"""


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


def _verify_citations(citations: list[dict], filing: Any, normalized_source: str) -> tuple[list[dict], int]:
    """Verify each citation excerpt against the normalized source; return (citations, grounded)."""
    base_url = getattr(filing, "document_url", None) or getattr(filing, "sec_url", None) or ""
    verified_list: list[dict] = []
    grounded = 0
    for idx, cite in enumerate(citations, start=1):
        excerpt = str(cite.get("excerpt") or "").strip()
        section_ref = cite.get("section") or cite.get("section_ref")
        n = cite.get("n")
        if not isinstance(n, int):
            n = idx
        verified = verify_excerpt_in_text(excerpt, normalized_source)
        if verified:
            grounded += 1
            fragment_url = build_text_fragment_url(base_url, excerpt) if base_url else base_url
        else:
            fragment_url = base_url
        verified_list.append({
            "n": n,
            "excerpt": excerpt,
            "section_ref": section_ref,
            "verified": verified,
            "fragment_url": fragment_url,
        })
    return verified_list, grounded


async def answer_filing_question(
    *,
    filing: Any,
    question: str,
    history: Optional[list[dict]] = None,
) -> AsyncGenerator[dict, None]:
    """Stream a grounded answer to ``question`` about ``filing`` as event dicts.

    Yields (in order):
    * ``{"type": "progress", "stage": "reading"}`` before the model call.
    * ``{"type": "token", "text": ...}`` for answer prose only (never the citation JSON / sentinels).
    * ``{"type": "not_disclosed", "answer": ...}`` if the model emits the not-disclosed sentinel.
    * ``{"type": "complete", "answer", "citations", "grounded", "kind"}`` at the end.
    * ``{"type": "error", "message": ...}`` on any failure.

    The generator never raises — all exceptions become an ``error`` event so the SSE stream stays
    well-formed. The filing source text is normalized **once** here and reused for every excerpt.
    """
    try:
        source_text = _select_source_text(filing) or ""
        normalized_source = normalize_for_match(source_text)
        messages = _build_messages(filing, source_text, question, history)

        # P5 numeric tool-use: bind the tools to this filing's company. ``run_tool`` opens its own DB
        # session per call (the request session is gone by now), and every successful fact result is
        # collected — deduped by (raw_tag, accession, period_end) — to surface as verified citations.
        company_id = getattr(filing, "company_id", None)
        used_facts: list[dict] = []
        _seen_facts: set[tuple] = set()

        def _run_tool(name: str, args: dict) -> dict:
            result = copilot_tools.run_tool(name, args, company_id)
            if isinstance(result, dict) and "error" not in result and "value" in result:
                key = (result.get("raw_tag"), result.get("accession"), result.get("period_end"))
                if key not in _seen_facts:
                    _seen_facts.add(key)
                    used_facts.append(result)
            return result

        yield {"type": "progress", "stage": "reading"}

        answer_parts: list[str] = []          # emitted prose (before any sentinel)
        citation_buffer: list[str] = []       # text after ===CITATIONS===
        not_disclosed_parts: list[str] = []   # text after ===NOT_DISCLOSED===
        pending = ""                          # carry-over tail for cross-chunk sentinel detection
        mode = "answer"                        # answer | citations | not_disclosed

        async for delta in openai_service.stream_chat_with_tools(
            messages,
            copilot_tools.TOOLS,
            _run_tool,
            model=openai_service.model,
            max_tokens=settings.COPILOT_MAX_TOKENS,
            temperature=0.2,
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

        # Stream finished. Flush any held-back tail that turned out to be plain prose.
        if mode == "answer" and pending:
            answer_parts.append(pending)
            yield {"type": "token", "text": pending}

        if mode == "not_disclosed":
            answer = "".join(not_disclosed_parts).strip() or "This filing does not disclose the requested information."
            yield {"type": "not_disclosed", "answer": answer}
            yield {
                "type": "complete",
                "answer": answer,
                "citations": [],
                "grounded": 0,
                "kind": "not_disclosed",
            }
            return

        full_answer = "".join(answer_parts).strip()
        citations = _parse_citations("".join(citation_buffer))
        verified_citations, grounded = _verify_citations(citations, filing, normalized_source)

        # Append the XBRL facts the tools returned as verified citations (existing citation shape, so
        # the frontend renders them in the Sources list / chips with a Verified badge — no frontend
        # change). Numbering continues after the text citations; their count adds to ``grounded``.
        filing_url = getattr(filing, "document_url", None) or getattr(filing, "sec_url", None) or None
        next_n = len(verified_citations) + 1
        for fact in used_facts:
            cite = copilot_tools.fact_to_citation(fact)
            cite["n"] = next_n
            cite["fragment_url"] = filing_url
            verified_citations.append(cite)
            grounded += 1
            next_n += 1

        yield {
            "type": "complete",
            "answer": full_answer,
            "citations": verified_citations,
            "grounded": grounded,
            "kind": "answer",
        }
    except Exception as e:  # noqa: BLE001 — never raise out of the SSE generator
        logger.exception("Copilot answer_filing_question failed")
        yield {"type": "error", "message": str(e)[:300]}
