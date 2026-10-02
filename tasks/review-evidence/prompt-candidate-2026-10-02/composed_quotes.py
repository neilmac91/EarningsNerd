"""Composed-quotation leg of acceptance checks 3 and 4 (registered measurement). Offline over a retained
copilot-eval.json; no app import, no provider call, no network.

It runs the unchanged #1021 audit, `prose_quote_audit.audit` (../pr1021-qualification-2026-10-01/), and re-tests
every span in the audit's composed_quote_rows with decision F's per-span test: F's floor (`verdict` below), then F's
source match as copied in `quote_inventory.classify` (this folder): citation markers [n]/[F#] blanked, edge
characters stripped, and a copy of provenance_service.normalize_for_match (punctuation-spacing fold and the
low/curly-mark, hyphen, minus and invisible-character folds). Per span, first match wins:
- sub-floor label: the marker-blanked, edge-stripped, normalized text is under F's _MIN_QUOTED_LEN (8) and holds no
  interior ellipsis, so F exempts it as a label (copilot_service._displayed_quotation_reasons); the audit's own
  floor counts raw characters between the marks, so `"EBITDA [1]"` reaches it. Reported, not composed;
- audit normalization difference: the audit flags it, but F's per-span test finds it (reported, not composed);
- composed: the audit flags it AND F's per-span test does not find it in the row's inputs.source_text.
F's markdown reading (emphasis delimiters * _ ~) and its quote pairing are not copied: the span is the one the
audit's regex pairs, so a published quotation holding markdown emphasis (`"**Net income**"`) is read as composed
and printed with its span.
A row without source text is an absent quotation, as in the audit. Both raw audit counts and the classified counts
are printed, overall and for ASML (check 3).

Exit 0 = no composed span and no row without source text, in every run given; exit 1 otherwise.

Usage: python composed_quotes.py LABEL=path/copilot-eval.json [...]
"""
import importlib.util
import json
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


def verdict(span, source_norm):
    """F's per-span test on one audit span: its floor first, then the source match (quote_inventory.classify)."""
    content = INVENTORY.MARKER.sub(" ", span).strip(INVENTORY.EDGE)
    if not INVENTORY.F_ELLIPSIS.search(content) and len(INVENTORY.norm(content)) < F_MIN_QUOTED_LEN:
        return SUB_FLOOR
    return NORM_DIFF if INVENTORY.classify(span, source_norm)[1] else COMPOSED


def classify(path):
    """(raw audit result, [span dicts], rows without source text)."""
    raw = AUDIT.audit(path)
    rows = {(r.get("ticker"), r.get("question_id"), r.get("run_index")): r
            for r in json.load(open(path, encoding="utf-8"))["results"]}
    spans = []
    for hit in raw["composed_quote_rows"]:
        row = rows[(hit["ticker"], hit["question_id"], hit["run_index"])]
        source_norm = INVENTORY.norm((row.get("inputs") or {}).get("source_text"))
        for span in hit["composed_quotes"]:
            spans.append({"ticker": hit["ticker"], "question_id": hit["question_id"], "run_index": hit["run_index"],
                          "verdict": verdict(span, source_norm), "span": span})
    return raw, spans, raw["rows_without_source_text"]


if __name__ == "__main__":
    failed = not sys.argv[1:]
    for arg in sys.argv[1:]:
        label, path = arg.split("=", 1)
        raw, spans, absent = classify(path)
        composed = [s for s in spans if s["verdict"] == COMPOSED]
        asml = [s for s in composed if s["ticker"] == "ASML"]
        failed |= bool(composed or absent)
        print(f"{label}: audit composed_quote_rows {len(raw['composed_quote_rows'])} (raw, strict); flagged spans "
              f"{len(spans)}: composed {len(composed)} (ASML {len(asml)}), audit normalization difference "
              f"{sum(s['verdict'] == NORM_DIFF for s in spans)}, sub-floor label "
              f"{sum(s['verdict'] == SUB_FLOOR for s in spans)}; rows without source text {len(absent)} {absent}")
        for s in spans:
            print(f"   {s['ticker']:5} {s['question_id']:30} d{s['run_index']} {s['verdict']:30} "
                  f"{json.dumps(s['span'], ensure_ascii=False)}")
    sys.exit(1 if failed else 0)
