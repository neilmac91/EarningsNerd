"""Optional LLM-judge dimension for the eval harness (Artifacts 1-2).

The deterministic scorers (schema/numeric/coverage + the hard gates in `scorers.py`) are the
reproducible PRIMARY gate. This judge is a SECONDARY, evidence-citing signal for the things
code cannot see without reading the filing:

  * G2 — fabricated comparatives (YoY/QoQ claims when the source has no comparative period)
  * G3 — hallucinated facts/events not present in the source
  * the prose dimensions: faithfulness, insight, clarity, specificity

It is OFF by default in the runner (needs the `anthropic` SDK + an API key, kept out of core
requirements). The message-construction and response-parsing helpers are pure and unit-tested
offline; only `judge_summary` touches the network.
"""
from __future__ import annotations

import json
import os
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from evals.scorers import parse_model_json

DEFAULT_JUDGE_MODEL = "claude-opus-4-8"  # strong reasoning; judging faithfulness > generating it
JUDGE_PASS_THRESHOLD = 4.0  # mean dimension score required to PASS when no gate fails (Artifact 1)
_DIMENSIONS = ("faithfulness", "insight", "clarity", "specificity")
_anthropic_client: Any = None  # shared lazily across calls to reuse the connection pool

_JUDGE_SYSTEM = (
    "You are a strict, adversarial evaluator of AI-generated SEC-filing summaries for an "
    "investor product. Catch errors; do not be charitable. Fluency never compensates for an "
    "unsupported claim or a fabricated comparison. Judge ONLY against the provided source "
    "excerpt and XBRL facts — if the source does not support a claim, it fails. When in doubt, "
    "fail it."
)

_JUDGE_INSTRUCTIONS = (
    "Evaluate the SUMMARY against the SOURCE.\n"
    "1. Hard gates — list a short failure string for EACH that fails, quoting the offending "
    "summary text:\n"
    "   - G2 fabricated_comparatives: a YoY/QoQ/prior-period claim the source does not contain.\n"
    "   - G3 hallucinated_facts: any event/figure/claim not supported by the source.\n"
    "2. Dimensions — score each 1-5 (5 = excellent), reserving 5 for genuinely excellent work: "
    "faithfulness, insight, clarity, specificity.\n"
    "Return ONLY this JSON, no prose:\n"
    '{"gate_failures": ["..."], '
    '"dimensions": {"faithfulness": 1-5, "insight": 1-5, "clarity": 1-5, "specificity": 1-5}, '
    '"verdict": "PASS|FAIL", "notes": "one-line rationale"}'
)


@dataclass
class JudgeVerdict:
    """Secondary, qualitative verdict from the LLM judge."""

    gate_failures: List[str] = field(default_factory=list)
    dimensions: Dict[str, int] = field(default_factory=dict)
    verdict: str = "FAIL"
    notes: str = ""
    error: Optional[str] = None
    raw: str = ""

    @property
    def mean_dimension(self) -> float:
        vals = [v for v in self.dimensions.values() if isinstance(v, (int, float))]
        return round(statistics.mean(vals), 4) if vals else 0.0

    @property
    def passed(self) -> bool:
        """Consistent with the final verdict (which already folds in gates / explicit FAIL /
        the dimension bar), so an explicit FAIL is never counted as a pass."""
        return self.verdict == "PASS"


def build_judge_messages(
    summary_payload: Dict[str, Any],
    company: str,
    filing_type: str,
    excerpt: str,
    xbrl_text: str,
) -> Tuple[str, str]:
    """Construct (system, user) messages. Gives the judge the source so it verifies, not vibes."""
    user = (
        f"Company: {company}\nFiling type: {filing_type}\n\n"
        f"=== XBRL FINANCIAL FACTS (ground truth) ===\n{xbrl_text or '(none available)'}\n\n"
        f"=== SOURCE FILING EXCERPT ===\n{(excerpt or '')[:60000]}\n\n"
        f"=== SUMMARY UNDER TEST ===\n{json.dumps(summary_payload, indent=2)[:20000]}\n\n"
        f"{_JUDGE_INSTRUCTIONS}"
    )
    return _JUDGE_SYSTEM, user


def parse_judge_response(raw: str) -> JudgeVerdict:
    """Parse the judge's JSON output into a verdict. Robust to fenced/garbage output."""
    payload, _ = parse_model_json(raw or "")
    if not isinstance(payload, dict):
        return JudgeVerdict(
            gate_failures=["judge response unparseable"], verdict="FAIL",
            error="unparseable judge response", raw=raw or "",
        )

    gate_failures = [str(g) for g in payload.get("gate_failures", []) if str(g).strip()]
    dims_in = payload.get("dimensions", {})
    dimensions: Dict[str, int] = {}
    if isinstance(dims_in, dict):
        for k in _DIMENSIONS:
            v = dims_in.get(k)
            if isinstance(v, (int, float)):
                dimensions[k] = int(v)

    verdict = JudgeVerdict(
        gate_failures=gate_failures,
        dimensions=dimensions,
        notes=str(payload.get("notes", ""))[:300],
        raw=raw or "",
    )
    # Resolve the final verdict. Gates always veto; an explicit FAIL is always respected (so a
    # FAIL with high dimension scores is never counted as a pass); an explicit PASS stands unless
    # a gate vetoes; with no explicit verdict we fall back to the dimension bar.
    explicit = str(payload.get("verdict", "")).strip().upper()
    meets_bar = not gate_failures and verdict.mean_dimension >= JUDGE_PASS_THRESHOLD
    if gate_failures or explicit == "FAIL":
        verdict.verdict = "FAIL"
    elif explicit == "PASS":
        verdict.verdict = "PASS"
    else:
        verdict.verdict = "PASS" if meets_bar else "FAIL"
    return verdict


async def judge_summary(
    summary_payload: Dict[str, Any],
    company: str,
    filing_type: str,
    excerpt: str,
    xbrl_text: str,
    model_id: str = DEFAULT_JUDGE_MODEL,
    max_tokens: int = 1024,
) -> JudgeVerdict:
    """Run the LLM judge via the anthropic SDK (lazy import). Network-touching."""
    try:
        import anthropic  # lazy: not a core dependency.
    except ImportError as exc:  # pragma: no cover - environment dependent
        return JudgeVerdict(verdict="FAIL", error=f"anthropic SDK not installed: {exc}")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return JudgeVerdict(verdict="FAIL", error="missing ANTHROPIC_API_KEY")

    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)
    client = _anthropic_client

    system, user = build_judge_messages(summary_payload, company, filing_type, excerpt, xbrl_text)
    try:
        resp = await client.messages.create(
            # temperature is intentionally omitted: claude-opus-4-8 (the default judge) rejects it
            # as deprecated. The judge grades on a strict rubric and variance is handled by
            # averaging over --runs, not a sampling-temperature knob.
            model=model_id, max_tokens=max_tokens,
            system=system, messages=[{"role": "user", "content": user}],
        )
        raw = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
    except Exception as exc:  # noqa: BLE001 - report, don't crash the bake-off
        return JudgeVerdict(verdict="FAIL", error=f"{type(exc).__name__}: {exc}")
    return parse_judge_response(raw)
