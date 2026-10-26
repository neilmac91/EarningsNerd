"""Calibration and form measures of an analysis (DEEPSEEK-ERRORS.md §1.3, fix 6 and §3 "Measures").

- ``judgement_outside_watch``: judgement sentences among the sentences outside the watch list. Watch items are left
  out because their type is a convention (Sonnet types them judgement, DeepSeek comparison), not calibration.
- ``evaluative``: fact and comparison sentences outside the arc and the watch list that use a word saying what the
  figures mean (``EVALUATIVE``), which fix 6 wants in a judgement sentence instead.
- ``watch_forecasts``: watch items that say what would follow, or forecast it (``FORECAST``), where fix 6 wants
  only the threshold, the direction that would confirm or reverse the trend, and the filing.
- ``form``: words, sentences and the sections present.

The two lexicons are proxies, so every hit is listed for hand reading (``report.py``).

``EVALUATIVE`` takes fix 6's own examples (structural, cushion, pressure, durable, likely, a sign of) and the
words of the same kinds in the recorded outputs: durability (persistent, cyclical, one-off, short-lived), buffer
and strain (headroom, little room, thin, strain, squeeze), risk and health (risk, robust, healthy, benign, worth
watching), inference (signals, suggests, implies), dependence (leans on, depends on) and verdicts on the data
(material, stale, distorted, unreliable, overstated, understates). Data words that only look evaluative are left out: "raw
material", "material costs", "risk-weighted", "basis points to". On eval-v1 it finds 20 of DeepSeek's 330 fact and
comparison sentences outside the arc and watch (6.1%; §1.3 counted 18, 5.5%, by hand) and 7 of Sonnet's 312 (2.2%, as
counted), and on eval-v1's development half DeepSeek's 6.2% of §1.3. ``FORECAST`` takes fix 6's "would keep" and
"will likely" and their kin: "will remain under", "it stays below ... if", "keeps pressure", and a consequence
after "would" (restore, ease, pressure, deepen the, move further) other than the confirm-or-reverse verbs and
"ease it" or "ease the concern", which only reverse the trend. On eval-v1 it finds 11 of DeepSeek's 60 watch
items (§1.3: 11, about 7 of them real), 1 of Sonnet's 60 (as counted) and none of Haiku-low's 59 (§1.3: 1).

Pure: reads sentences (``{"section", "text", "type"}``, as ``generate.sentences_of`` gives them), calls no model and
writes nothing.
"""
from __future__ import annotations

import re
from typing import Any, Sequence

from evals.trend_depth.factcheck import CITATION_RE

DATA_TYPES = ("fact", "comparison")
NOT_DATA_SECTIONS = ("arc", "watch")  # the arc narrates and the watch list looks ahead; neither is a data sentence's place

EVALUATIVE = re.compile(
    r"\b(?:structural(?:ly)?|durab(?:le|ility)|(?:un)?sustainab(?:le|ility)|persistent(?:ly)?|cyclical|one-offs?|"
    r"one-time|one-period|temporary|transitory|short-lived|"
    r"cushion\w*|headroom|buffers?|(?:little|limited|no|less)\s+room|pressur(?:e|es|ed|ing)|strain\w*|stress(?:ed|es)?|"
    r"squeez\w*|thin|stretched|"
    r"risks?(?!-weighted)|risky|vulnerab\w*|fragil\w*|healthy|robust|resilien\w*|comfortabl[ey]|ample|benign|"
    r"concerning|worrying|worth\s+watching|"
    r"(?:un)?likely|a\s+sign\s+of|signals?|suggests?|indicates?|implies|(?<!basis\s)(?<!percentage\s)points?\s+to|"
    r"underscores?|"
    r"leans?\s+on|depends?\s+on|relies\s+on|reliant|"
    r"stale|distorted|unreliable|(?:over|under)stat(?:e|es|ed|ing))\b"
    r"|(?<!raw\s)\bmaterial(?:ly)?\b(?!\s+(?:and|or|costs?|inflation|prices?)\b)",
    re.I,
)
FORECAST = re.compile(
    r"\b(?:will|would)\s+(?:likely|probably)\b|\blikely\s+(?:to\s+)?(?:remain|stay|keep|continue)\b"
    r"|\b(?:will|would)\s+(?:remain|stay)\s+(?:under|below|above|over|at|near|within)\b"
    r"|\b(?:it|this|that)\s+stays\s+(?:under|below|above|over|at|near)\b[^;]*?\bif\b"
    r"|\b(?:will|would)\s+keep\b|\bkeeps\s+(?:pressure|weighing|dragging)\b"
    r"|\bwould\s+(?:restore|pressure|lift|push|cut|weigh|drag|limit|force|require|widen\s+reliance|move\s+further)\b"
    r"|\bwould\s+ease\s+(?!(?:it|them|that|the\s+(?:concern|worry|flag|risk))\b)\w+"
    r"|\bwould\s+deepen\s+the\b",
    re.I,
)


def _clean(text: str) -> str:
    return " ".join(CITATION_RE.sub("", text).split())


def judgement_outside_watch(sentences: Sequence[dict[str, Any]]) -> dict[str, int]:
    """{"judgements", "sentences"}: judgement sentences among those outside the watch list."""
    outside = [s for s in sentences if s.get("section") != "watch"]
    return {"judgements": sum(1 for s in outside if s.get("type") == "judgement"), "sentences": len(outside)}


def evaluative(sentences: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """{"hits", "sentences"}: fact and comparison sentences outside the arc and watch list that say what the figures
    mean, each hit with its section, sentence and words, among all such sentences."""
    scope = [s for s in sentences if s.get("type") in DATA_TYPES and s.get("section") not in NOT_DATA_SECTIONS]
    hits = []
    for sentence in scope:
        words = [m.group(0) for m in EVALUATIVE.finditer(_clean(sentence["text"]))]
        if words:
            hits.append({"section": sentence.get("section", ""), "sentence": sentence["text"], "words": words})
    return {"hits": hits, "sentences": len(scope)}


def watch_forecasts(sentences: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """{"hits", "items"}: watch items with forecast or consequence wording, each with its wording, among all items."""
    items = [s for s in sentences if s.get("section") == "watch"]
    hits = []
    for item in items:
        found = FORECAST.search(_clean(item["text"]))
        if found:
            hits.append({"section": "watch", "sentence": item["text"], "wording": found.group(0)})
    return {"hits": hits, "items": len(items)}


def form(output: dict[str, Any], expected: Sequence[str]) -> dict[str, Any]:
    """Words (as ``generate.word_count`` counts them), sentences, and the expected sections with at least one sentence."""
    sections = [s for s in output.get("sections", []) if isinstance(s, dict)]
    texts = [sentence.get("text", "") for section in sections for sentence in section.get("sentences", [])]
    present = {section.get("key") for section in sections if section.get("sentences")}
    return {"words": len(" ".join(CITATION_RE.sub("", t) for t in texts).split()), "sentences": len(texts),
            "sections": sum(1 for key in expected if key in present), "missing": [key for key in expected if key not in present]}
