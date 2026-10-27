"""Render current and proposed analyses into one reader format: sections, numbered citations, sources.

Both the judge and the blind human pack read this format, so neither sees an arm name, a model name or
an internal ID scheme. Citations renumber to [1]..[n] in first-appearance order; the sources list states
what each number points at (a filed figure, a calculated figure, or a quoted filing passage with its
EDGAR location). Judgement sentences in proposed outputs are marked "Analysis:", which is how the
proposal presents them in the product.
"""
from __future__ import annotations

import re
from typing import Any

from evals.trend_depth import factcheck
from evals.trend_depth.render import fmt

TITLES = {
    "arc": "The arc", "drivers": "What drove growth", "margins": "Margins and costs", "cash": "Cash conversion",
    "balance_sheet": "Balance sheet and capital allocation", "red_flags": "Red flags", "watch": "What to watch",
}


def _source_line(n: int, ref: str, pack: dict[str, Any], passage_chars: int, links: bool = False) -> str:
    if ref.startswith("P"):
        passage = next((p for p in pack["passages"] if p["id"] == ref), None)
        if passage is None:
            return f"[{n}] (unknown passage)"
        text = passage["text"] if len(passage["text"]) <= passage_chars else passage["text"][:passage_chars].rsplit(" ", 1)[0] + " …"
        where = f"{passage['fiscal_year']} 10-K, {passage['section']}" + (f" › {passage['heading']}" if passage.get("heading") else "")
        return f"[{n}] Filing passage · {where} · “{text}”" + (f" {passage['url']}" if links and passage.get("url") else "")
    if ref.startswith("R"):
        flag = next((f for f in pack.get("red_flags", []) if f["id"] == ref), None)
        return f"[{n}] Screened flag · {flag['detail'] if flag else ref}"
    value = pack["values"].get(ref)
    if value is None:
        return f"[{n}] (unknown reference)"
    kind = {"filed": "Filed figure", "calculated": "Calculated figure", "peer": "Peer comparison"}.get(value.get("source", ""), "Calculated figure")
    return f"[{n}] {kind} · {value['label']} · {value['period']} · {fmt(value['value'], value['unit'])}"


def proposed_markdown(output: dict[str, Any], pack: dict[str, Any], *, passage_chars: int = 600, links: bool = False) -> str:
    """The reader format. ``links`` appends each passage's EDGAR link (the human pack); judges read it without."""
    numbers: dict[str, int] = {}

    def renumber(match: re.Match[str]) -> str:
        refs = factcheck.ID_RE.findall(match.group(1))
        out = []
        for ref in refs:
            if ref not in numbers:
                numbers[ref] = len(numbers) + 1
            out.append(f"[{numbers[ref]}]")
        return "".join(out)

    lines: list[str] = []
    for section in output.get("sections", []):
        lines.append(f"## {section.get('title') or TITLES.get(section.get('key', ''), section.get('key', ''))}")
        sentences = []
        for sentence in section.get("sentences", []):
            text = factcheck.CITATION_RE.sub(renumber, sentence.get("text", "")).strip()
            if sentence.get("type") == "judgement":
                text = f"*Analysis:* {text}"
            sentences.append(text)
        lines.append(" ".join(sentences) if section.get("key") not in ("red_flags", "watch")
                     else "\n".join(f"- {s}" for s in sentences))
        lines.append("")
    lines.append("### Sources")
    for ref, n in numbers.items():
        lines.append(_source_line(n, ref, pack, passage_chars, links))
    return "\n".join(lines).strip()


def current_markdown(record: dict[str, Any]) -> str:
    """The production narrative as the page shows it, with its own Sources list."""
    lines = [record["narrative"].strip(), "", "### Sources"]
    for citation in record.get("citations", []):
        lines.append(f"[{citation['n']}] {citation.get('excerpt', '')} · {citation.get('section_ref', '')}")
    return "\n".join(lines)
