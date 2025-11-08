from __future__ import annotations

from typing import Dict, Tuple


SCORE_WEIGHTS = {
    "accuracy": 5,
    "clarity": 4,
    "insight_density": 4,
    "numerical_precision": 4,
    "narrative_flow": 4,
    "section_balance": 4,
    "brevity": 5,
}


class QualityError(RuntimeError):
    pass


def _score_markdown(markdown: str) -> Dict[str, int]:
    words = [word for word in markdown.replace("##", "").split() if word]
    length = len(words)
    scores: Dict[str, int] = {}
    scores["accuracy"] = 5 if "Not disclosed" not in markdown else 0
    scores["clarity"] = 4 if length > 150 else 3
    scores["insight_density"] = 4 if markdown.count("$") >= 3 else 3
    scores["numerical_precision"] = 4 if ".." not in markdown else 2
    scores["narrative_flow"] = 4 if markdown.count("Executive Summary") == 1 else 3
    scores["section_balance"] = 4 if markdown.count("##") >= 2 else 2
    if 200 <= length <= 300:
        scores["brevity"] = 5
    elif length < 200:
        scores["brevity"] = 3
    else:
        scores["brevity"] = 2
    return scores


def ensure_quality(markdown: str) -> Tuple[str, Dict[str, int]]:
    """Score draft and enforce threshold."""

    scores = _score_markdown(markdown)
    total = sum(scores.values())
    if total < 28 or any(section.strip() == "##" for section in markdown.splitlines()):
        raise QualityError(f"Draft failed quality gate with score {total}/35")
    return markdown, scores
