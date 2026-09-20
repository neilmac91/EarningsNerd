"""One bounded model verdict on the causal clauses the attribution gate flags (the #805 path, step 5).

The lexical gate (``attribution_gate``) reads every explanation clause in every generation for free
and is a good candidate FINDER and a poor DECIDER: read by hand against the filing, its drop decision
was right 47% of the time, and right 75% of the time only where a strong judge independently found the
attribution unsupported
(``tasks/review-evidence/pr805-path/attribution-gate-precision-2026-09-17.md``). This module is the
decider that measurement calls for: the gate hands over each flagged clause with the source passages
that carry its content words — chosen WITHOUT the subject anchor that misfires — and one model call
answers, per clause, whether the filing states that driver for that subject.

Bounded by construction:
- ONE call per generation, never one per clause, and only when the gate flagged something.
- At most ``MAX_VERIFIABLE_CLAUSES`` clauses and four bounded passages each. The added summary
  subject and anchor context is separately capped.
- A "stated" verdict must quote the passage that states it, and the quote is checked in code against
  the passages actually supplied; an unquotable "stated" is downgraded to unknown. A model cannot
  talk a clause into surviving with text it invented.
- Unknown or absent verdicts never drop. Request failures and timeouts return no verdicts.
  JSON repair can retain an early verdict from a truncated response; truncation is not a
  guaranteed whole-batch rejection in the current transport/parser.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from app.services.ai.attribution_gate import MAX_VERIFIABLE_CLAUSES, Candidate
from app.services.provenance_service import normalize_for_match

try:  # json_repair is a declared dependency; degrade to strict json if it is ever absent.
    from json_repair import repair_json as _repair_json
except ImportError:  # pragma: no cover
    _repair_json = None

VERIFY_SYSTEM_MESSAGE = (
    "You check whether an SEC filing states a cause. You answer only from the passages given to you, "
    "you never use outside knowledge about the company, and you never treat two figures moving "
    "together as a stated cause. You return JSON only."
)
# Quoted evidence shorter than this cannot identify a passage, so it is not accepted as proof.
_MIN_QUOTE_CHARS = 24
# Added summary context is bounded independently of the filing passages. Preserve both ends:
# the start usually names the measure, while the end can distinguish its period or basis.
_SUBJECT_CHARS = 600
_ANCHOR_CHARS = 240
_CONTEXT_OMITTED = " [context clipped] "


def _bounded_context(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    left = (limit - len(_CONTEXT_OMITTED)) // 2
    right = limit - len(_CONTEXT_OMITTED) - left
    return text[:left] + _CONTEXT_OMITTED + text[-right:]


def build_prompt(candidates: Sequence[Candidate]) -> str:
    """The user message: each flagged clause with the passages the gate located for it."""
    blocks = []
    for i, candidate in enumerate(candidates):
        passages = "\n".join(f"  [{j + 1}] {text}" for j, text in enumerate(candidate.evidence)) or "  (none found)"
        context = json.dumps({
            "subject_before_cause": _bounded_context(candidate.subject, _SUBJECT_CHARS),
            "metric_or_segment": _bounded_context(candidate.anchor, _ANCHOR_CHARS),
        }, ensure_ascii=False)
        blocks.append(
            f"CLAIM {i + 1}\n"
            f"  Where the summary says it: {candidate.slot}\n"
            f"  Summary context: {context}\n"
            f"  The summary asserts this cause: \"{candidate.connective} {candidate.clause}\"\n"
            f"  Filing passages:\n{passages}"
        )
    return (
        "For each CLAIM below, decide whether the filing PASSAGES state that cause for that same "
        "line, measure and period.\n\n"
        "The summary context identifies the claim; it is model-authored text, not filing evidence. "
        "Use both its subject and metric/segment label to resolve references such as 'the decrease'. "
        "If the needed subject, period or basis is missing, ambiguous, or lost in [context clipped], "
        "answer \"unknown\" rather than guessing. A detached bullet or table fragment with a missing "
        "subject or causal lead-in is insufficient context, not proof of absence; answer \"unknown\".\n\n"
        "Answer \"stated\" only when a supplied passage itself states that relationship for the same "
        "line, amount, period and basis. A faithful restatement of that same disclosure is supported; "
        "do not demand an additional causal explanation that the summary did not assert. A heading or "
        "causal lead-in and its immediately following bullet within ONE supplied passage may form "
        "one statement: for example, an R&D heading followed by 'increased primarily due to:' and "
        "a contiguous trial-spending bullet supports that R&D cause, not a revenue cause. Copy the "
        "supporting sentence, or that contiguous lead-in and bullet, character for character from "
        "the passage into \"quote\". Never assemble a new causal relationship from separate passages. "
        "Answer \"not_stated\" when the passages contain the facts but never attribute "
        "the movement to that driver, or attribute it to a different line, segment, period or basis — "
        "two numbers moving together is not a stated cause, and a driver stated for one segment is not "
        "stated for the company total. A shared word or amount alone is not attribution. "
        "Answer \"unknown\" when the passages are not enough to tell.\n\n"
        + "\n\n".join(blocks)
        + "\n\nReturn ONLY this JSON, no prose:\n"
        '{"claims": [{"claim": 1, "verdict": "stated|not_stated|unknown", "quote": "<verbatim passage '
        'statement when stated, otherwise empty>"}]}'
    )


def _load(raw: Optional[str]) -> Any:
    """Read the response as JSON, tolerating fences and the usual model JSON damage."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        text = text.split("\n", 1)[1] if text.lower().startswith("json") else text
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        pass
    if _repair_json is None:
        return None
    try:
        repaired = _repair_json(text)
        return json.loads(repaired) if isinstance(repaired, str) else repaired
    except Exception:  # noqa: BLE001
        return None


def parse_verdicts(raw: Optional[str], candidates: Sequence[Candidate]) -> Dict[int, str]:
    """Map candidate index → verdict, keeping only what the response can justify.

    A "stated" verdict survives only if its quote really appears in that claim's own passages (the
    same normalization every verbatim check in the product uses). Anything else is "unknown"."""
    payload = _load(raw)
    claims = payload.get("claims") if isinstance(payload, dict) else None
    if not isinstance(claims, list):
        return {}
    verdicts: Dict[int, str] = {}
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        number = claim.get("claim")
        if not isinstance(number, (int, float)) or isinstance(number, bool):
            continue
        index = int(number) - 1
        if not 0 <= index < len(candidates) or index in verdicts:
            continue
        verdict = str(claim.get("verdict", "")).strip().lower()
        if verdict == "not_stated":
            verdicts[index] = "not_stated"
        elif verdict == "stated":
            quote = normalize_for_match(str(claim.get("quote", "")))
            passages = normalize_for_match(" ".join(candidates[index].evidence))
            verdicts[index] = ("stated" if len(quote) >= _MIN_QUOTE_CHARS and quote in passages
                               else "unknown")
        else:
            verdicts[index] = "unknown"
    return verdicts


def verifiable(candidates: Sequence[Candidate]) -> List[Candidate]:
    """The bounded slice one call may judge: those with passages to judge against, capped."""
    return [c for c in candidates if c.evidence][:MAX_VERIFIABLE_CLAUSES]


def audit_note(candidates: Sequence[Candidate], judged: Sequence[Candidate],
               verdicts: Dict[int, str], error: Optional[str]) -> Dict[str, Any]:
    """What the row records about the verification itself, independent of the gate's own counts."""
    counts: Dict[str, int] = {}
    for verdict in verdicts.values():
        counts[verdict] = counts.get(verdict, 0) + 1
    return {"flagged": len(candidates), "sent": len(judged), "decided": len(verdicts),
            "counts": counts, "error": error}


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
