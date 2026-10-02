"""Composed-quotation leg of acceptance checks 3 and 4 (registered measurement). Offline over a retained
copilot-eval.json; no app import, no provider call, no network.

It runs the unchanged #1021 audit, `prose_quote_audit.audit` (../pr1021-qualification-2026-10-01/), and re-tests
every span in the audit's composed_quote_rows with decision F's per-span test as copied in
`quote_inventory.classify` (this folder): citation markers [n]/[F#] blanked, edge characters stripped, and a copy of
provenance_service.normalize_for_match (punctuation-spacing fold and the low/curly-mark, hyphen, minus and
invisible-character folds). Per span:
- composed: the audit flags it AND F's per-span test does not find it in the row's inputs.source_text;
- audit normalization difference: the audit flags it, but F's per-span test finds it (reported, not composed).
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
            in_source = INVENTORY.classify(span, source_norm)[1]
            spans.append({"ticker": hit["ticker"], "question_id": hit["question_id"], "run_index": hit["run_index"],
                          "verdict": "audit normalization difference" if in_source else "composed", "span": span})
    return raw, spans, raw["rows_without_source_text"]


if __name__ == "__main__":
    failed = not sys.argv[1:]
    for arg in sys.argv[1:]:
        label, path = arg.split("=", 1)
        raw, spans, absent = classify(path)
        composed = [s for s in spans if s["verdict"] == "composed"]
        asml = [s for s in composed if s["ticker"] == "ASML"]
        failed |= bool(composed or absent)
        print(f"{label}: audit composed_quote_rows {len(raw['composed_quote_rows'])} (raw, strict); flagged spans "
              f"{len(spans)}: composed {len(composed)} (ASML {len(asml)}), audit normalization difference "
              f"{len(spans) - len(composed)}; rows without source text {len(absent)} {absent}")
        for s in spans:
            print(f"   {s['ticker']:5} {s['question_id']:30} d{s['run_index']} {s['verdict']:30} "
                  f"{json.dumps(s['span'], ensure_ascii=False)}")
    sys.exit(1 if failed else 0)
