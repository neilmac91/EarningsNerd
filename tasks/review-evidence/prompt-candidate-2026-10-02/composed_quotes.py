"""Composed-quotation leg of acceptance checks 3 and 4 (registered measurement). Offline over a retained
copilot-eval.json; no app import, no provider call, no network.

It runs the unchanged #1021 audit, `prose_quote_audit.audit` (../pr1021-qualification-2026-10-01/), and reads each
row the audit flags (composed_quote_rows) again. Quotations are paired in order: the published answer gets the
audit's FOLD (curly double marks to straight) and, for the pairing only, PAIRING_FOLD (＂ „ ‟ to straight, one
character for one, so positions still match the audit's spans). The pairs are the matches of `"([^"]*)"` with no
floor: a pair may cross a line break, as F's pairs may, and may be empty (an empty pair reads as a sub-floor
label). Every pair is re-tested by decision F's per-span test: F's floor (`verdict` below), then F's source match
as copied in `quote_inventory.classify` (this folder): citation markers [n]/[F#] blanked, edge characters stripped,
and a copy of provenance_service.normalize_for_match (punctuation-spacing fold and the low/curly-mark, hyphen,
minus and invisible-character folds).

Why pairs: the audit's regex `"([^"]{8,})"` cannot match a quotation under 8 characters. After a short quoted label
(BABA's `"Revenue"`) it restarts at the label's closing mark and pairs it with the next quotation's opening mark, so
the text between two quotations becomes an audit span. Decision F pairs the marks correctly and publishes.

Classes. An audit span (one the audit flagged), first match wins:
- audit pairing difference: it is not one of the row's pairs (the text between two quotations). Reported, not
  composed;
- sub-floor label: the marker-blanked, edge-stripped, normalized text is under F's _MIN_QUOTED_LEN (8) and holds no
  interior ellipsis, so F exempts it as a label (copilot_service._displayed_quotation_reasons); the audit's own
  floor counts raw characters between the marks, so `"EBITDA [1]"` reaches it. Reported, not composed;
- audit normalization difference: F's per-span test finds it. Reported, not composed;
- composed: F's per-span test does not find it in the row's inputs.source_text.
A pair on the same row that the audit did not flag (for example a quotation the audit skipped while out of phase)
gets the same test: unflagged sub-floor label, unflagged verified (found), or unflagged composed. Composed spans are
the composed audit spans plus the unflagged composed pairs.

Unpaired marks: the two folds make all six of F's marks (" ＂ “ ” „ ‟) straight, so the in-order pairing leaves a
mark unpaired only when their count on the row is odd. The pairs are then not trusted on that row. Its audit spans
are re-tested as the audit pairs them (sub-floor label, audit normalization difference or composed), none is an
audit pairing difference, its other pairs are not read, and the row is counted. Such a row can still fail on the
text between two quotations (the pairing shape). F pairs every mark it reads, so an answer F publishes has an even
count as displayed; an odd count in the published text needs a mark that the text and the display count
differently, such as a character reference (`&quot;`). With an even count, the in-order pairs are F's pairs unless F
reads a nested quotation or a span's text differs from F's display of it (below).

Not copied from F: its display reading (copilot_service._rendered_text and its default-ignorable drop), so the
answer is read as written, not as displayed. The differences are not limited to this list: emphasis delimiters
* _ ~, backslash escapes, character references, code-span backticks, block markers on a quotation's continuation
lines (`>`, list markers) and default-ignorable characters. In general any span whose text differs from F's
display of it can read as composed when F publishes; such a span is printed with its row. So a published quotation
holding markdown emphasis (`"**Net income**"`) or a code span is read as composed, an escaped mark
(`\\"Revenue\\"`) leaves its backslash in the pair, and a character reference is read as written. Also not copied:
its nested reading, so `"x "y" z"`, which F reads whole and inner, is read in order: two pairs, with the inner text
as the gap between them. A row without source text is an absent quotation, as in the audit. Both raw audit counts
and the classified counts are printed, overall and for ASML (check 3).

Exit 0 = no composed span and no row without source text, in every run given; exit 1 otherwise.

Usage: python composed_quotes.py LABEL=path/copilot-eval.json [...]
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = load("prose_quote_audit", HERE.parent / "pr1021-qualification-2026-10-01" / "prose_quote_audit.py")
INVENTORY = load("quote_inventory", HERE / "quote_inventory.py")
F_MIN_QUOTED_LEN = 8  # copilot_service._MIN_QUOTED_LEN, unchanged from base (prompt_identity.txt, check 5)
COMPOSED, NORM_DIFF, SUB_FLOOR = "composed", "audit normalization difference", "sub-floor label"
PAIRING_DIFF, VERIFIED = "audit pairing difference", "verified"
PAIRING_FOLD = str.maketrans({"＂": '"', "„": '"', "‟": '"'})  # pairing only; one character for one
PAIR = re.compile(r'"([^"]*)"')  # in order, across line breaks, empty allowed, no floor
AUDIT_SPAN = re.compile(r'"([^"]{8,})"')  # the audit's own regex, used only to locate its spans (checked below)


def verdict(span, source_norm):
    """F's per-span test on one span: its floor first, then the source match (quote_inventory.classify)."""
    content = INVENTORY.MARKER.sub(" ", span).strip(INVENTORY.EDGE)
    if not INVENTORY.F_ELLIPSIS.search(content) and len(INVENTORY.norm(content)) < F_MIN_QUOTED_LEN:
        return SUB_FLOOR
    return NORM_DIFF if INVENTORY.classify(span, source_norm)[1] else COMPOSED


def read_row(answer, source_text, flagged):
    """(marks pair in order, [(flagged, class, span)] in text order) for one row the audit flagged."""
    folded = answer.translate(AUDIT.FOLD)
    audit_source = AUDIT.norm(source_text)
    located = [(m.start(1), m.end(1)) for m in AUDIT_SPAN.finditer(folded) if AUDIT.norm(m.group(1)) not in audit_source]
    if [folded[a:b] for a, b in located] != flagged:
        raise SystemExit(f"could not locate the audit's spans {flagged!r}")
    marks = folded.translate(PAIRING_FOLD)  # positions unchanged, so pairs and located spans compare
    pairs = [(m.start(1), m.end(1)) for m in PAIR.finditer(marks)]
    paired = marks.count('"') == 2 * len(pairs)
    source_norm = INVENTORY.norm(source_text)
    spans = []
    for at in sorted(set(located) | (set(pairs) if paired else set())):
        text = folded[at[0]:at[1]]
        if at not in located:
            cls = verdict(text, source_norm)
            spans.append((False, VERIFIED if cls == NORM_DIFF else cls, text))
        elif paired and at not in pairs:
            spans.append((True, PAIRING_DIFF, text))
        else:
            spans.append((True, verdict(text, source_norm), text))
    return paired, spans


def classify(path):
    """(raw audit result, [span dicts], rows whose marks do not pair in order, rows without source text)."""
    raw = AUDIT.audit(path)
    rows = {(r.get("ticker"), r.get("question_id"), r.get("run_index")): r
            for r in json.load(open(path, encoding="utf-8"))["results"]}
    spans, unpaired = [], []
    for hit in raw["composed_quote_rows"]:
        key = (hit["ticker"], hit["question_id"], hit["run_index"])
        row = rows[key]
        paired, read = read_row(row.get("answer") or "", (row.get("inputs") or {}).get("source_text"),
                                hit["composed_quotes"])
        if not paired:
            unpaired.append(key)
        for flagged, cls, span in read:
            spans.append({"ticker": hit["ticker"], "question_id": hit["question_id"], "run_index": hit["run_index"],
                          "flagged": flagged, "verdict": cls, "span": span})
    return raw, spans, unpaired, raw["rows_without_source_text"]


def count(spans, cls, ticker=None):
    return sum(s["verdict"] == cls and ticker in (None, s["ticker"]) for s in spans)


if __name__ == "__main__":
    failed = not sys.argv[1:]
    for arg in sys.argv[1:]:
        label, path = arg.split("=", 1)
        raw, spans, unpaired, absent = classify(path)
        flagged = [s for s in spans if s["flagged"]]
        other = [s for s in spans if not s["flagged"]]
        failed |= bool(count(spans, COMPOSED) or absent)
        print(f"{label}: audit composed_quote_rows {len(raw['composed_quote_rows'])} (raw, strict); flagged spans "
              f"{len(flagged)}: composed {count(flagged, COMPOSED)} (ASML {count(flagged, COMPOSED, 'ASML')}), audit "
              f"normalization difference {count(flagged, NORM_DIFF)}, sub-floor label {count(flagged, SUB_FLOOR)}, "
              f"audit pairing difference {count(flagged, PAIRING_DIFF)}; unflagged pairs on flagged rows {len(other)}: "
              f"composed {count(other, COMPOSED)} (ASML {count(other, COMPOSED, 'ASML')}), sub-floor label "
              f"{count(other, SUB_FLOOR)}, verified {count(other, VERIFIED)}; rows with unpaired marks {len(unpaired)}; "
              f"rows without source text {len(absent)} {absent}")
        for s in unpaired:
            print(f"   unpaired marks: {s[0]} {s[1]} d{s[2]} (audit spans read as the audit pairs them)")
        for s in spans:
            cls = s["verdict"] if s["flagged"] else f"unflagged {s['verdict']}"
            print(f"   {s['ticker']:5} {s['question_id']:30} d{s['run_index']} {cls:30} "
                  f"{json.dumps(s['span'], ensure_ascii=False)}")
    sys.exit(1 if failed else 0)
