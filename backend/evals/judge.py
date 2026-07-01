"""Optional LLM-judge dimension for the eval harness (Artifacts 1-2).

The deterministic scorers (schema/numeric/coverage + the hard gates in `scorers.py`) are the
reproducible PRIMARY gate. This judge is a SECONDARY, evidence-citing signal for the things
code cannot see without reading the filing:

  * G2 — fabricated comparatives (YoY/QoQ claims when the source has no comparative period)
  * G3 — hallucinated facts/events not present in the source
  * the prose dimensions: faithfulness, insight, clarity, specificity

It is OFF by default in the runner. The message-construction and response-parsing helpers are
pure and unit-tested offline; only the `_judge_via_*` backends touch the network.

## Judge backends (pick via the model id passed to `--judge` / `judge_summary(model_id=...)`)

The judge dispatches on the model id so a run can trade cost for authority without code changes:

  * ``claude-opus-4-8`` (and any other bare ``claude-*``) → **anthropic SDK** on ``ANTHROPIC_API_KEY``.
    Strongest, but bills API credits. This is the DEFAULT and the authoritative-audit judge.
  * ``cli:sonnet`` / ``cli:opus`` (``cli:<alias>``) → **subscription CLI** (`claude -p --output-format
    json`) with ``ANTHROPIC_API_KEY`` unset in the child env, so it authenticates via the logged-in
    Claude subscription (OAuth) instead of API credits. For local/manual gates only — there is no
    OAuth session in CI.
  * ``glm-5.2`` (or ``openai:<model>``) → **OpenAI-compatible** chat API (e.g. Zhipu GLM via z.ai),
    reading ``JUDGE_OPENAI_BASE_URL``/``JUDGE_OPENAI_API_KEY`` (falling back to ``OPENAI_BASE_URL``/
    ``OPENAI_API_KEY``). The cheap CI/fallback judge.

Before trusting a cheaper backend as the gate, run an agreement check against the Opus default on a
small sample (RUNBOOK) so we don't silently weaken the quality bar.
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from evals.scorers import parse_model_json

try:  # json_repair is a declared dependency; degrade gracefully if absent.
    from json_repair import repair_json as _repair_json
except ImportError:  # pragma: no cover
    _repair_json = None

DEFAULT_JUDGE_MODEL = "claude-opus-4-8"  # strong reasoning; judging faithfulness > generating it
JUDGE_PASS_THRESHOLD = 4.0  # mean dimension score required to PASS when no gate fails (Artifact 1)
_DIMENSIONS = ("faithfulness", "insight", "clarity", "specificity")
_CLI_TIMEOUT_SECONDS = 300  # subscription CLI can be slow on a 200k-char excerpt + reasoning
# The judge MUST see the same source the model grounded on, or it false-flags real facts as
# hallucinations. The generator grounds on the full critical-sections excerpt (filing_sample =
# filing_excerpt), which runs ~120–165k chars; a smaller cap truncates capital-return/obligations/
# segment disclosures (which sit late in a 10-K) out of the judge's view, tanking faithfulness.
# 200k chars (~50k tokens) covers observed excerpts and fits the judge model's context comfortably.
_JUDGE_EXCERPT_CHAR_CAP = 200_000
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
        f"=== SOURCE FILING EXCERPT ===\n{(excerpt or '')[:_JUDGE_EXCERPT_CHAR_CAP]}\n\n"
        f"=== SUMMARY UNDER TEST ===\n{json.dumps(summary_payload, indent=2)[:20000]}\n\n"
        f"{_JUDGE_INSTRUCTIONS}"
    )
    return _JUDGE_SYSTEM, user


def parse_judge_response(raw: str) -> JudgeVerdict:
    """Parse the judge's JSON output into a verdict. Robust to fenced/garbage output."""
    payload, _ = parse_model_json(raw or "")
    if not isinstance(payload, dict) and _repair_json is not None and (raw or "").strip():
        # Fallback: repair malformed JSON (trailing commas, smart quotes, …) before giving up.
        try:
            repaired = _repair_json(raw)
            cand = json.loads(repaired) if isinstance(repaired, str) else repaired
            if isinstance(cand, dict) and isinstance(cand.get("dimensions"), dict):
                payload = cand
        except Exception:  # noqa: BLE001
            pass
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


def judge_backend(model_id: str) -> str:
    """Route a judge model id to a backend: 'cli' | 'openai' | 'anthropic'.

    Dispatch is by prefix so the mapping is explicit and testable offline:
      - ``cli:<alias>`` / ``subscription:<alias>`` → the subscription CLI (`claude -p`)
      - ``openai:<model>`` or any id starting ``glm`` → the OpenAI-compatible chat API
      - everything else (default ``claude-opus-4-8``) → the anthropic SDK on the API key
    """
    m = (model_id or "").strip().lower()
    if m.startswith(("cli:", "subscription:")):
        return "cli"
    if m.startswith("openai:") or m.startswith("glm"):
        return "openai"
    return "anthropic"


async def _judge_with_retry(call_once: Callable[[], Awaitable[str]]) -> JudgeVerdict:
    """Run `call_once` up to twice, parsing its raw text into a verdict.

    Backends occasionally return unparseable/malformed JSON or a transient upstream error; a
    second attempt clears most of those. `parse_judge_response` extracts/repairs the ``{...}``
    object, so a model preamble is harmless. Errors are reported, never raised, so one bad
    filing can't crash a bake-off."""
    last = JudgeVerdict(verdict="FAIL", error="judge not run")
    for _attempt in range(2):
        try:
            raw = await call_once()
        except Exception as exc:  # noqa: BLE001 - report, don't crash the bake-off
            last = JudgeVerdict(verdict="FAIL", error=f"{type(exc).__name__}: {exc}")
            continue
        last = parse_judge_response(raw)
        if not last.error:
            return last
    return last


async def _judge_via_anthropic(
    system: str, user: str, model_id: str, max_tokens: int
) -> JudgeVerdict:
    """Anthropic SDK path (default; bills API credits). Reuses one client for its pool."""
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

    # temperature is omitted (claude-opus-4-8 rejects it as deprecated) and assistant-prefill is
    # also rejected; a generous max_tokens keeps the JSON from being truncated when the model
    # prepends a rationale.
    async def call_once() -> str:
        resp = await client.messages.create(
            model=model_id, max_tokens=max_tokens,
            system=system, messages=[{"role": "user", "content": user}],
        )
        return next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")

    return await _judge_with_retry(call_once)


async def _judge_via_openai(
    system: str, user: str, model_id: str, max_tokens: int
) -> JudgeVerdict:
    """OpenAI-compatible path (e.g. GLM-5.2 via z.ai). The cheap CI/fallback judge.

    Reads ``JUDGE_OPENAI_BASE_URL``/``JUDGE_OPENAI_API_KEY`` so the judge provider is
    configured independently of the generation pipeline's ``OPENAI_*`` (which points at
    DeepSeek); falls back to ``OPENAI_*`` when the judge-specific vars are unset."""
    try:
        from openai import AsyncOpenAI  # lazy: keep the eval harness importable without it.
    except ImportError as exc:  # pragma: no cover - environment dependent
        return JudgeVerdict(verdict="FAIL", error=f"openai SDK not installed: {exc}")

    # base_url is optional: when unset the SDK targets the official OpenAI endpoint (so
    # "openai:gpt-4o" works with just an API key); set it for GLM/z.ai and other compatible providers.
    base_url = os.environ.get("JUDGE_OPENAI_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or None
    api_key = os.environ.get("JUDGE_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return JudgeVerdict(
            verdict="FAIL", error="missing JUDGE_OPENAI_API_KEY (or OPENAI_API_KEY)",
        )
    # "openai:<model>" is an explicit backend selector; strip it. Bare ids (e.g. "glm-5.2") pass through.
    model = model_id.split(":", 1)[1] if model_id.lower().startswith("openai:") else model_id

    # Context-manage the client so its httpx connections are closed even across retries (no leak).
    async with AsyncOpenAI(api_key=api_key, base_url=base_url) as client:
        async def call_once() -> str:
            resp = await client.chat.completions.create(
                model=model, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            return (resp.choices[0].message.content or "") if resp.choices else ""

        return await _judge_with_retry(call_once)


async def _kill_and_reap(proc: Any) -> None:
    """Kill a subprocess and await it so it's reaped (no zombie). Safe if it already exited."""
    try:
        proc.kill()
    except ProcessLookupError:  # already exited between the check and the kill
        pass
    await proc.wait()


async def _judge_via_cli(
    system: str, user: str, model_id: str, max_tokens: int
) -> JudgeVerdict:
    """Subscription CLI path: `claude -p --output-format json` with the API key removed from the
    child env, so it authenticates via the logged-in Claude subscription (OAuth) instead of
    billing API credits. Manual/local only — CI has no OAuth session.

    The judge framing goes via ``--append-system-prompt`` and the (large) source+summary via
    stdin. ``--output-format json`` wraps the reply in ``{"result": "..."}``; we hand ``result``
    to the same `parse_judge_response` used by every backend."""
    alias = model_id.split(":", 1)[1].strip() if ":" in model_id else ""
    model = alias or "sonnet"
    # Force subscription/OAuth auth: an inherited ANTHROPIC_API_KEY would bill API credits instead.
    child_env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

    async def call_once() -> str:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", "--model", model, "--output-format", "json",
            "--append-system-prompt", system,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=child_env,
        )
        try:
            out, err = await asyncio.wait_for(
                proc.communicate(user.encode("utf-8")), timeout=_CLI_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            await _kill_and_reap(proc)
            raise RuntimeError(f"claude CLI timed out after {_CLI_TIMEOUT_SECONDS}s")
        except BaseException:
            # asyncio.CancelledError is a BaseException (not Exception), so it slips past the
            # TimeoutError handler above; reap the child on any cancellation/error, then re-raise
            # so a cancelled judge run never leaks a zombie subprocess.
            await _kill_and_reap(proc)
            raise
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude CLI exit {proc.returncode}: {err.decode('utf-8', 'replace')[:300]}"
            )
        outer = json.loads(out.decode("utf-8"))
        if isinstance(outer, dict):
            if outer.get("is_error") or outer.get("subtype") not in (None, "success"):
                raise RuntimeError(f"claude CLI error result: {str(outer)[:300]}")
            return str(outer.get("result", ""))
        return out.decode("utf-8")  # unexpected shape — let the parser try

    return await _judge_with_retry(call_once)


async def judge_summary(
    summary_payload: Dict[str, Any],
    company: str,
    filing_type: str,
    excerpt: str,
    xbrl_text: str,
    model_id: str = DEFAULT_JUDGE_MODEL,
    max_tokens: int = 4096,
) -> JudgeVerdict:
    """Run the LLM judge, dispatching to the backend selected by `model_id`. Network-touching.

    See the module docstring for the model-id → backend routing (`judge_backend`)."""
    system, user = build_judge_messages(summary_payload, company, filing_type, excerpt, xbrl_text)
    backend = judge_backend(model_id)
    if backend == "cli":
        return await _judge_via_cli(system, user, model_id, max_tokens)
    if backend == "openai":
        return await _judge_via_openai(system, user, model_id, max_tokens)
    return await _judge_via_anthropic(system, user, model_id, max_tokens)
