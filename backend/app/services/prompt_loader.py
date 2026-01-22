from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict


@dataclass(frozen=True)
class PromptTemplate:
    system: str
    user: str
    raw: str


_PROMPT_FILES = {
    "10-K": "10k-analyst-agent.md",
    "10-Q": "10q-analyst-agent.md",
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


_PROMPTS = _load_prompts()


def get_prompt(filing_type: str) -> PromptTemplate:
    filing_key = (filing_type or "").upper()
    normalized = "10-K" if filing_key == "10K" else ("10-Q" if filing_key == "10Q" else filing_key)
    return _PROMPTS.get(normalized, _PROMPTS["10-K"])
