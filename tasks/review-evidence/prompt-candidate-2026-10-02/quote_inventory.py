"""Quote inventory (declared method): every quoted span a Copilot run wrote, in every quote form, classified.
Offline over a retained copilot-eval.json; no app import, no provider call, no network.

Surfaces, per row:
- published row: the answer (or not-disclosed reason) and every follow-up chip of the `complete` service event
  (row.answer when the event is absent);
- withheld row (no published answer): the candidate the service rejected, i.e. the joined
  tool_trace.candidate_deltas: its prose up to the first ===CITATIONS=== / ===NOT_DISCLOSED=== / ===FOLLOWUPS===
  line; its not-disclosed reason (the text after ===NOT_DISCLOSED=== up to ===FOLLOWUPS===, surface
  withheld-reason); and the strings of its follow-up JSON array when it parses.
Forms (scanned on each surface's text):
- double: straight "...", and decision F's other marks paired as “...”, „...“/„...”, ‟...”, ＂...＂;
- single: ‘...’, and straight '...' whose opening mark does not follow a letter or digit and whose closing mark
  is not followed by one (apostrophes are not openers; an apostrophe between two word characters inside the span,
  as in 'ASML's net sales', does not close it);
- backtick: `...`;  guillemet: «...» and ‹...›;  blockquote: each line starting with '>' (up to 3 spaces first).
Classes, first match wins:
- table-figure: the span holds a figure token (\\d{1,3}(,\\d{3})+(\\.\\d+)?, \\d+\\.\\d+ or \\d{5,}) and at most four
  words once figure tokens, ellipses, currency signs and punctuation are removed. This is the label-plus-cell and
  bare-cell shape ("Total net sales 32,667.3", "9,609.4", "Revenue ... 996,347"); an MD&A sentence that carries a
  figure has more words and is classed on its own merits. A short prose figure phrase ("€9,609.4 million") is also
  classed table-figure, so read in_source alongside the class;
- sub-floor: under 8 normalized characters (decision F's _MIN_QUOTED_LEN) with no interior ellipsis;
- verified: the span occurs contiguously in the row's normalized inputs.source_text;
- other: everything else (8 or more characters or an interior ellipsis, not found in the source, not a
  table-figure shape).
The per-span test copies decision F's (copilot_service._displayed_quotation_reasons at base): citation markers
[n]/[F#] blanked, edge characters _QUOTE_EDGE_CHARS stripped, an interior ellipsis is _QUOTE_ELLIPSIS_RE, and
the text is normalized by a copy of provenance_service.normalize_for_match (both files are byte-identical to base,
scope_hashes.txt). F's markdown reading and work bounds are not copied, so this is not F's verdict.
Every span also reports in_source and interior_ellipsis, so a table figure that F would verify stays visible.
This is context for the qualification (where table figures go: double quotes or another form), never a threshold;
the classes are a declared heuristic, not decision F's parser.

Usage: python quote_inventory.py LABEL=path/copilot-eval.json [...]   (prints a summary and every span)
"""
import json
import re
import sys
from collections import Counter

# Copy of provenance_service.normalize_for_match and of decision F's per-span constants (copilot_service.py).
FOLDS = str.maketrans({"‘": "'", "’": "'", "‚": "'", "“": '"', "”": '"', "„": '"', "–": "-", "—": "-", "―": "-",
                       "‑": "-", "−": "-", "\u00ad": None, "\u200b": None, "\u200c": None, "\u200d": None,
                       "\ufeff": None})
SPACE_BEFORE_PUNCT, SPACE_AFTER_OPEN = re.compile(r"\s+(?=[,.;:%)\]])"), re.compile(r"(?<=[(\[])\s+")
EDGE = " \t\r\n\u00a0.,;:!?\u2026"
F_ELLIPSIS = re.compile(r"\.\s*\.\s*\.|\u2026")
MARKER = re.compile(r"\[F?\d{1,3}\]")
SENTINEL = re.compile(r"^\s*===\s*(CITATIONS|NOT[_ -]?DISCLOSED|FOLLOW-?UPS)\s*===\s*$", re.I | re.M)
FOLLOWUPS = re.compile(r"^\s*===\s*FOLLOW-?UPS\s*===\s*$", re.I | re.M)
NOT_DISCLOSED = re.compile(r"^\s*===\s*NOT[_ -]?DISCLOSED\s*===\s*$", re.I | re.M)
FORMS = [
    ("double", re.compile(r'"([^"\n]+)"|“([^”\n]+)”|„([^“”\n]+)[“”]|‟([^”\n]+)”|＂([^＂\n]+)＂')),
    ("single", re.compile(r"‘([^’\n]+)’|(?<![\w])'((?:[^'\n]|(?<=\w)'(?=\w))+?)'(?!\w)")),
    ("backtick", re.compile(r"`([^`\n]+)`")),
    ("guillemet", re.compile(r"«([^»\n]+)»|‹([^›\n]+)›")),
    ("blockquote", re.compile(r"^ {0,3}>[ \t]?(.+)$", re.M)),
]
FIGURE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d{5,}")
ELLIPSIS = re.compile(r"\.\.\.|…")
WORD = re.compile(r"[^\W\d_][\w'&-]*")


def norm(text):
    folded = re.sub(r"\s+", " ", (text or "").translate(FOLDS).strip().lower())
    return SPACE_AFTER_OPEN.sub("", SPACE_BEFORE_PUNCT.sub("", folded))


def classify(span, source_norm):
    content = MARKER.sub(" ", span).strip(EDGE)
    needle = norm(content)
    in_source = bool(needle) and (needle in source_norm or norm(span.strip(EDGE)) in source_norm)
    figures = FIGURE.findall(span)
    words = WORD.findall(ELLIPSIS.sub(" ", FIGURE.sub(" ", span)))
    ellipsis = bool(F_ELLIPSIS.search(content))
    if figures and len(words) <= 4:
        cls = "table-figure"
    elif len(needle) < 8 and not ellipsis:
        cls = "sub-floor"
    elif in_source:
        cls = "verified"
    else:
        cls = "other"
    return cls, in_source, ellipsis, figures


def surfaces(row):
    """[(surface, text)] for one row, as described in the module docstring."""
    trace = row.get("tool_trace") if isinstance(row.get("tool_trace"), dict) else {}
    complete = next((e for e in trace.get("service_events") or [] if isinstance(e, dict) and e.get("type") == "complete"), None)
    if row.get("answer") or complete:
        main = (complete or {}).get("answer") or (complete or {}).get("reason") or row.get("answer") or ""
        return [("answer", main)] + [("chip", c) for c in (complete or {}).get("followups") or [] if isinstance(c, str)]
    candidate = "".join(d for d in trace.get("candidate_deltas") or [] if isinstance(d, str))
    if not candidate:
        return []
    out = [("withheld-prose", SENTINEL.split(candidate, maxsplit=1)[0])]
    reason = NOT_DISCLOSED.split(candidate, maxsplit=1)
    if len(reason) == 2:
        out.append(("withheld-reason", FOLLOWUPS.split(reason[1], maxsplit=1)[0]))
    tail = FOLLOWUPS.split(candidate, maxsplit=1)
    if len(tail) == 2:
        try:
            chips, _ = json.JSONDecoder().raw_decode(tail[1].strip())
            out += [("withheld-chip", c) for c in chips if isinstance(c, str)]
        except ValueError:
            pass
    return out


def inventory(path):
    report = json.load(open(path, encoding="utf-8"))
    spans = []
    for row in report["results"]:
        source_norm = norm((row.get("inputs") or {}).get("source_text"))
        for surface, text in surfaces(row):
            for form, pattern in FORMS:
                for match in pattern.finditer(text):
                    span = next(g for g in match.groups() if g)
                    cls, in_source, ellipsis, figures = classify(span, source_norm)
                    spans.append({"ticker": row.get("ticker"), "question_id": row.get("question_id"),
                                  "run_index": row.get("run_index"), "withheld": bool(row.get("error")),
                                  "surface": surface, "form": form, "class": cls, "in_source": in_source,
                                  "interior_ellipsis": ellipsis, "figures": figures, "span": span})
    return report, spans


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        label, path = arg.split("=", 1)
        report, spans = inventory(path)
        rows = len(report["results"])
        by = Counter((s["form"], s["class"]) for s in spans)
        print(f"{label}: rows {rows}; quoted spans {len(spans)}; rows with any span "
              f"{len({(s['ticker'], s['question_id'], s['run_index']) for s in spans})}")
        print("  form x class: " + (", ".join(f"{f}/{c} {n}" for (f, c), n in sorted(by.items())) or "none"))
        print(f"  table-figure spans: {sum(s['class'] == 'table-figure' for s in spans)} "
              f"(outside double quotes: {sum(s['class'] == 'table-figure' and s['form'] != 'double' for s in spans)}); "
              f"non-double spans: {sum(s['form'] != 'double' for s in spans)}")
        for s in spans:
            print(f"   {s['ticker']:5} {s['question_id']:30} d{s['run_index']} {'W' if s['withheld'] else 'P'} "
                  f"{s['surface']:14} {s['form']:10} {s['class']:12} in_source={s['in_source']!s:5} "
                  f"ellipsis={s['interior_ellipsis']!s:5} {json.dumps(s['span'], ensure_ascii=False)}")
