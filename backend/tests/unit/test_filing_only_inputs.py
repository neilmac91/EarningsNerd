"""Rule 2: retired cross-filing summary inputs cannot return through another spelling site.

Scan executable Python, not historical plans or test fixtures. Current-filing comparative
periods and the explicitly separate Change Report remain supported.
"""
import ast
import inspect
from pathlib import Path

import pytest


BACKEND = Path(__file__).resolve().parents[2]
RETIRED = {"previous_filings", "previous_filings_context"}
PROMPT_MARKER = "PREVIOUS 10-K EXCERPTS FOR CONTEXT"


def _retired_literal(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in RETIRED


def _violations(source):
    hits = []
    for node in ast.walk(ast.parse(source)):
        name = None
        if isinstance(node, ast.arg):
            name = node.arg
        elif isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.keyword):
            name = node.arg
        if name in RETIRED:
            hits.append((node.lineno, type(node).__name__, name))
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if _retired_literal(key):
                    hits.append((key.lineno, "dict key", key.value))
        elif isinstance(node, ast.Subscript) and _retired_literal(node.slice):
            hits.append((node.lineno, "subscript key", node.slice.value))
        elif isinstance(node, ast.Call):
            func = node.func
            key = None
            if (isinstance(func, ast.Name) and func.id in {"getattr", "setattr", "hasattr", "delattr"}
                    and len(node.args) >= 2):
                key = node.args[1]
            elif (isinstance(func, ast.Attribute) and func.attr in {"get", "pop", "setdefault"}
                  and node.args):
                key = node.args[0]
            if _retired_literal(key):
                hits.append((key.lineno, "runtime key", key.value))
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if PROMPT_MARKER in " ".join(node.value.upper().split()):
                hits.append((node.lineno, "prior-context prompt", PROMPT_MARKER))
    return hits


def test_production_python_has_no_retired_cross_filing_summary_inputs():
    paths = {BACKEND / "main.py"}
    for directory in ("app", "scripts", "prompts"):
        paths.update((BACKEND / directory).rglob("*.py"))
    failures = []
    for path in sorted(paths):
        for line, kind, name in _violations(path.read_text(encoding="utf-8")):
            failures.append(f"{path.relative_to(BACKEND)}:{line}: {kind}: {name}")
    assert not failures, "Retired cross-filing summary inputs reintroduced:\n" + "\n".join(failures)


def test_gate_permits_current_filing_comparatives_and_separate_change_report():
    assert _violations('''
def build_change_report(current_filing, prior_filing):
    return {"current": current_filing, "prior": prior_filing}

def summarize_current_filing(xbrl_metrics):
    previous_period = xbrl_metrics["prior"]
    return {"comparatives": previous_period, "current": xbrl_metrics.get("current")}
''') == []


@pytest.mark.parametrize("method", ["generate_structured_summary", "summarize_filing"])
def test_actual_entrypoint_signatures_bind_only_current_filing_inputs(method):
    from app.services.openai_service import OpenAIService

    signature = inspect.signature(getattr(OpenAIService, method))
    assert list(signature.parameters) == [
        "self", "filing_text", "company_name", "filing_type", "xbrl_metrics", "filing_excerpt", "stream_cb"
    ]
    metrics = {"current": {"revenue": 120}, "prior": {"revenue": 100}}
    callback = object()
    bound = signature.bind(object(), "chosen filing", "Company", "10-K", metrics, "chosen excerpt", callback)
    assert bound.arguments["xbrl_metrics"] is metrics
    assert bound.arguments["filing_excerpt"] == "chosen excerpt"
    assert bound.arguments["stream_cb"] is callback


@pytest.mark.asyncio
async def test_facade_forwards_selected_filing_and_its_comparatives_unchanged(monkeypatch):
    from app.services.openai_service import OpenAIService

    service = OpenAIService()
    metrics = {"current": {"revenue": 120}, "prior": {"revenue": 100}}
    captured = []

    async def callback(_markdown):
        pass

    async def capture(filing_text, company_name, filing_type, *, xbrl_metrics, filing_excerpt, stream_cb):
        captured.append((filing_text, company_name, filing_type, xbrl_metrics, filing_excerpt, stream_cb))
        raise TimeoutError("stop after observing the actual facade forwarding boundary")

    monkeypatch.setattr(service, "generate_structured_summary", capture)
    with pytest.raises(TimeoutError, match="stop after observing"):
        await service.summarize_filing("selected filing text", "Selected company", "20-F", metrics,
                                       "selected filing excerpt", callback)
    assert len(captured) == 1
    text, company, form, forwarded, excerpt, cb = captured[0]
    assert (text, company, form, excerpt) == (
        "selected filing text", "Selected company", "20-F", "selected filing excerpt"
    )
    assert forwarded is metrics and forwarded["prior"]["revenue"] == 100
    assert cb is callback
