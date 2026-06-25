from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromptTemplate:
    system: str
    user: str
    raw: str


_PROMPT_FILES = {
    "10-K": "10k-analyst-agent.md",
    "10-Q": "10q-analyst-agent.md",
    # 20-F = foreign private issuer annual report (FPI; analogue of a 10-K, different item
    # structure + non-USD reporting currency). See tasks/fpi-support-roadmap.md.
    "20-F": "20f-analyst-agent.md",
}

# Schema-first prompts used when USE_STRUCTURED_OUTPUT is enabled (roadmap S1). These keep the
# extraction/grounding guidance but omit the narrative-format instructions that contradict
# JSON output.
_STRUCTURED_PROMPT_FILES = {
    "10-K": "10k-structured-agent.md",
    "10-Q": "10q-structured-agent.md",
    "20-F": "20f-structured-agent.md",
}


def _split_prompt(markdown: str) -> tuple[str, str]:
    markers = [
        r"^##\s+Output Template.*$",
        r"^##\s+📍\s+PHASE 4: OUTPUT FORMAT.*$",
        r"^##\s+Output Format.*$",
    ]
    for marker in markers:
        match = re.search(marker, markdown, flags=re.MULTILINE)
        if match:
            system = markdown[: match.start()].strip()
            user = markdown[match.start() :].strip()
            return system, user
    return markdown.strip(), ""


def _load_prompts() -> Dict[str, PromptTemplate]:
    prompts_dir = Path(__file__).resolve().parents[2] / "prompts"
    loaded: Dict[str, PromptTemplate] = {}
    for filing_type, filename in _PROMPT_FILES.items():
        prompt_path = prompts_dir / filename
        raw = prompt_path.read_text(encoding="utf-8")
        system, user = _split_prompt(raw)
        loaded[filing_type] = PromptTemplate(system=system, user=user, raw=raw)
    return loaded


def _load_structured_prompts() -> Dict[str, str]:
    prompts_dir = Path(__file__).resolve().parents[2] / "prompts"
    return {
        filing_type: (prompts_dir / filename).read_text(encoding="utf-8").strip()
        for filing_type, filename in _STRUCTURED_PROMPT_FILES.items()
    }


_PROMPTS = _load_prompts()
_STRUCTURED_PROMPTS = _load_structured_prompts()


_HYPHENLESS = {"10K": "10-K", "10Q": "10-Q", "20F": "20-F", "6K": "6-K", "40F": "40-F"}


def _normalize_filing_type(filing_type: str) -> str:
    filing_key = (filing_type or "").upper().strip()
    return _HYPHENLESS.get(filing_key, filing_key)


def get_prompt(filing_type: str) -> PromptTemplate:
    key = _normalize_filing_type(filing_type)
    prompt = _PROMPTS.get(key)
    if prompt is None:
        # Explicit, logged fallback — a form without its own prompt (e.g. 6-K before Phase 4) is
        # summarized with the 10-K analyst prompt, which assumes a domestic annual-report
        # structure. Surfacing it prevents a silent mis-analysis from going unnoticed.
        logger.warning(
            "No analyst prompt registered for filing_type=%r; falling back to the 10-K prompt",
            filing_type,
        )
        return _PROMPTS["10-K"]
    return prompt


def get_structured_prompt(filing_type: str) -> str:
    """Schema-first system prompt (no narrative-format block) for USE_STRUCTURED_OUTPUT mode."""
    key = _normalize_filing_type(filing_type)
    prompt = _STRUCTURED_PROMPTS.get(key)
    if prompt is None:
        logger.warning(
            "No structured prompt registered for filing_type=%r; falling back to the 10-K prompt",
            filing_type,
        )
        return _STRUCTURED_PROMPTS["10-K"]
    return prompt
