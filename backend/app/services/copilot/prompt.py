"""Single-filing Copilot prompt bytes and context assembly.

Call-time collaborators are resolved on the facade inside the helpers that use them.
The lazy facade import keeps both import orders valid while retaining patch seams.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional

from app.services.provenance_service import _MIN_VERIFIABLE_LEN


# Sentinels the model emits to delimit the citation block / the not-disclosed verdict. We hold back a
# tail of ``_SENTINEL_TAIL`` chars across chunk boundaries so a sentinel split between two stream
# chunks is still detected.
_CITATIONS_SENTINEL = "===CITATIONS==="
_NOT_DISCLOSED_SENTINEL = "===NOT_DISCLOSED==="
_SENTINEL_TAIL = max(len(_CITATIONS_SENTINEL), len(_NOT_DISCLOSED_SENTINEL))
# Optional trailer after the citations JSON carrying 2-3 suggested follow-up questions. It only ever
# appears inside the (buffered) citations phase, so it's parsed post-hoc — no cross-chunk tail needed.
_FOLLOWUPS_SENTINEL = "===FOLLOWUPS==="

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
    from app.services import copilot_service as service

    cache = getattr(filing, "content_cache", None)
    company = getattr(filing, "company", None)
    report_period = getattr(filing, "period_end_date", None)
    if report_period is not None:
        report_period = report_period.date().isoformat() if hasattr(report_period, "date") else report_period.isoformat()
    return service.SimpleNamespace(
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
        content_cache=service.SimpleNamespace(
            critical_excerpt=getattr(cache, "critical_excerpt", None),
            markdown_content=getattr(cache, "markdown_content", None),
        ) if cache is not None else None,
        company=service.SimpleNamespace(
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
    """Render the filing's XBRL JSON compactly for context, cut at 8,000 characters; "" if absent or unserializable.

    Numeric tools provide exact accession-scoped facts independently. This compact reference
    cannot crowd out the section excerpt.

    Source durations are dropped here even though extraction now preserves them: this block is
    truncated at a fixed cap, so every key added displaces excerpt content the model would
    otherwise see, and the tools already hand the model exact period provenance. Keeping the
    projection stable also keeps the prompt bytes — and their cache — unchanged. Widening what
    the model sees is a prompt change, gated on its own evidence.
    """
    from app.services import copilot_service as service

    if not xbrl_data:
        return ""
    try:
        rendered = service.json.dumps(service._without_source_durations(xbrl_data), default=str,
                              separators=(",", ":"))
    except (TypeError, ValueError):
        return ""
    # Cap so a pathological XBRL payload can't dominate the context window.
    return rendered[:8000]


def _build_context_message(filing: Any, source_text: str) -> str:
    """Assemble the filing-meta + excerpt + XBRL context message for the model."""
    from app.services import copilot_service as service

    company = getattr(filing, "company", None)
    company_name = getattr(company, "name", None) or "Unknown company"
    ticker = getattr(company, "ticker", None) or "?"
    form = getattr(filing, "filing_type", None) or "filing"
    filing_date = getattr(filing, "filing_date", None)
    date_str = filing_date.strftime("%Y-%m-%d") if hasattr(filing_date, "strftime") else str(filing_date or "unknown")

    excerpt = (source_text or "")[: service.settings.COPILOT_CONTEXT_CHAR_CAP]
    xbrl_block = service._compact_xbrl_block(getattr(filing, "xbrl_data", None))

    currency = service._reporting_currency(filing)
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
    from app.services import copilot_service as service

    messages: list[dict] = [
        {"role": "system", "content": service.SYSTEM_PROMPT},
        {"role": "user", "content": service._build_context_message(filing, source_text)},
    ]
    if history:
        # Keep only the most recent turns; tolerate malformed entries.
        turns = history[-service.settings.COPILOT_HISTORY_TURNS:]
        for turn in turns:
            if not isinstance(turn, dict):
                continue
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                # Cap per-turn content so a malicious/oversized history entry can't stuff the prompt
                # (defense-in-depth — the API layer also bounds this; see AskRequest).
                messages.append({"role": role, "content": content[: service.settings.COPILOT_HISTORY_ITEM_CHAR_CAP]})
    messages.append({"role": "user", "content": question})
    # Collapse same-role runs (context+question, context+first-user-turn, malformed history) so
    # providers that require strict user/assistant alternation don't 400.
    return service._merge_consecutive_roles(messages)


