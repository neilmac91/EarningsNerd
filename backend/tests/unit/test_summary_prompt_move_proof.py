"""Synthetic counterexamples for the executable boundaries erased by O2's proof."""
import pytest

from tests.support.summary_prompt_move_proof import compare

IMPORTS = '''
from __future__ import annotations
from typing import Any, Dict, Optional
from app.config import settings
from app.services.prompt_loader import get_prompt
from app.services.ai.xbrl_narrative import build_xbrl_narrative_section
'''
METHOD = '''
class OpenAIService:
    async def generate_structured_summary(
        self, filing_type_key, sixk_class, xbrl_metrics, financial_data,
        company_name, filing_type, filing_sample,
    ):
'''
OLD = IMPORTS + METHOD + '''
        config = self._get_type_config(filing_type_key)
        prompt_template = get_prompt(filing_type_key, sixk_class=sixk_class)
        xbrl_section = build_xbrl_narrative_section(xbrl_metrics)
        data_summary = financial_data["revenue"] + xbrl_section
        analysis_focus_lines = [filing_type_key]
        schema_template = "{schema}"
        structured_mode = settings.USE_STRUCTURED_OUTPUT
        prompt = f"{company_name}:{filing_type}:{filing_sample}:{prompt_template}:{data_summary}:{analysis_focus_lines}:{schema_template}"
        create_kwargs: Dict[str, Any] = dict(
            model=self.get_model_for_filing(filing_type_key), messages=[prompt],
            temperature=0.1 if structured_mode else 0.2, max_tokens=config.get("max_tokens", 1500),
        )
        return create_kwargs
'''
NEW = IMPORTS + '''
import sys
from app.services.ai import summary_prompt
''' + METHOD + '''
        create_kwargs: Dict[str, Any] = summary_prompt.build_primary_request(
            self, sys.modules[__name__], filing_type_key, sixk_class, xbrl_metrics,
            financial_data, company_name, filing_type, filing_sample,
        )
        return create_kwargs
'''
PROMPT = '''
"""An inert module docstring is allowed."""
from __future__ import annotations
from types import ModuleType
from typing import Any, Dict, Optional
SCHEMA_TEMPLATE = "{schema}"

def _build_context(financial_data: Dict, xbrl_section: str, filing_type_key: str) -> tuple[str, list[str]]:
    data_summary = financial_data["revenue"] + xbrl_section
    analysis_focus_lines = [filing_type_key]
    return data_summary, analysis_focus_lines

def build_primary_request(
    service: Any, facade: ModuleType, filing_type_key: str, sixk_class: Optional[str],
    xbrl_metrics: Optional[Dict], financial_data: Dict, company_name: str,
    filing_type: str, filing_sample: str,
) -> Dict[str, Any]:
    """An inert helper docstring is allowed."""
    config = service._get_type_config(filing_type_key)
    prompt_template = facade.get_prompt(filing_type_key, sixk_class=sixk_class)
    xbrl_section = facade.build_xbrl_narrative_section(xbrl_metrics)
    data_summary, analysis_focus_lines = _build_context(financial_data, xbrl_section, filing_type_key)
    schema_template = SCHEMA_TEMPLATE
    structured_mode = facade.settings.USE_STRUCTURED_OUTPUT
    prompt = f"{company_name}:{filing_type}:{filing_sample}:{prompt_template}:{data_summary}:{analysis_focus_lines}:{schema_template}"
    return _request_kwargs(service, filing_type_key, prompt, structured_mode, config)

def _request_kwargs(
    service: Any, filing_type_key: str, prompt: str, structured_mode: bool, config: Dict,
) -> Dict[str, Any]:
    return dict(
        model=service.get_model_for_filing(filing_type_key), messages=[prompt],
        temperature=0.1 if structured_mode else 0.2, max_tokens=config.get("max_tokens", 1500),
    )
'''


def test_prompt_reassembly_preserves_the_method():
    assert compare(OLD, NEW, PROMPT) == ""


@pytest.mark.parametrize(("target", "before", "after"), [
    pytest.param("prompt", "0.1 if", "0.3 if", id="body-drift"),
    pytest.param("facade", "financial_data, company_name, filing_type, filing_sample,",
                 "financial_data, filing_type, company_name, filing_sample,", id="primary-argument-swap"),
    pytest.param("prompt", "_build_context(financial_data, xbrl_section, filing_type_key)",
                 "_build_context(financial_data, filing_type_key, xbrl_section)", id="context-argument-swap"),
    pytest.param("prompt", "_request_kwargs(service, filing_type_key, prompt, structured_mode, config)",
                 "_request_kwargs(service, prompt, filing_type_key, structured_mode, config)", id="request-argument-swap"),
    pytest.param("facade", "sys.modules[__name__]", "sys.modules['other']", id="facade-miswire"),
    pytest.param("facade", "from app.services.ai import summary_prompt",
                 "from another_package import summary_prompt", id="module-miswire"),
    pytest.param("prompt", "facade.get_prompt(", "get_prompt(", id="bare-collaborator"),
    pytest.param("prompt", "{company_name}:", "{facade.company_name}:", id="facade-local-confusion"),
    pytest.param("prompt", 'SCHEMA_TEMPLATE = "{schema}"',
                 'SCHEMA_TEMPLATE = register("{schema}")', id="constant-side-effect"),
    pytest.param("prompt", 'SCHEMA_TEMPLATE = "{schema}"',
                 'SCHEMA_TEMPLATE = "{schema}"\nregister()', id="module-side-effect"),
    pytest.param("prompt", "    return dict(", "    config.clear()\n    return dict(", id="helper-side-effect"),
    pytest.param("prompt", "return data_summary, analysis_focus_lines",
                 "return analysis_focus_lines, data_summary", id="return-tuple-swap"),
    pytest.param("prompt", '    schema_template = SCHEMA_TEMPLATE',
                 '    if structured_mode:\n        return {}\n    schema_template = SCHEMA_TEMPLATE', id="early-return"),
    pytest.param("prompt", "config: Dict,", "config: Dict = register(),", id="default-side-effect"),
    pytest.param("prompt", "def _request_kwargs(", "@register\ndef _request_kwargs(", id="decorator-side-effect"),
    pytest.param("prompt", "def _build_context(", "async def _build_context(", id="async-boundary"),
    pytest.param("prompt", "service: Any, facade: ModuleType", "facade: ModuleType, service: Any", id="signature-swap"),
    pytest.param("prompt", "SCHEMA_TEMPLATE =", "def unused():\n    register()\nSCHEMA_TEMPLATE =", id="unused-helper"),
    pytest.param("facade", "create_kwargs: Dict[str, Any] =", "create_kwargs =", id="assignment-annotation"),
    pytest.param("facade", "import sys", "import sys\nsys = replacement", id="namespace-rebinding"),
])
def test_prompt_reassembly_rejects_changes(target, before, after):
    facade, prompt = NEW, PROMPT
    source = facade if target == "facade" else prompt
    assert before in source, "mutation must change the synthetic source"
    source = source.replace(before, after, 1)
    if target == "facade":
        facade = source
    else:
        prompt = source
    try:
        diff = compare(OLD, facade, prompt)
    except AssertionError:
        return
    assert diff, f"{target}: {before!r} incorrectly passed as a pure move"
