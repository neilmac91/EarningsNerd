"""Offline probe: the registered composed-quotation reading (composed_quotes.py) against decision F's product
function, on synthetic published answers. No provider call, no network. Not a test (no test_ prefix and no _test
suffix): it is run by hand and its output is committed as composed_quotes_probe.txt.

Usage (from the repository root; real provider keys unset, the import needs conftest's non-calling mock key):
  env -u OPENAI_API_KEY -u DEEPSEEK_API_KEY -u OPENAI_BASE_URL OPENAI_API_KEY=sk-test-key-for-mocking \
      SECRET_KEY=offline-identity-check-not-a-secret-0 SKIP_REDIS_INIT=true PYTHONDONTWRITEBYTECODE=1 \
      python tasks/review-evidence/prompt-candidate-2026-10-02/composed_quotes_probe.py backend <copilot-eval.json>

Each case is one synthetic published answer on a retained row's inputs.source_text, taken from the given retained
report (the six source texts are identical in every retained run). Per case it prints:
- F: copilot_service.unsupported_prose_quotations(answer, provenance_service.normalize_for_match(source)), the
  product's own verdict ([] publishes, as in copilot_service's stream);
- audit: the spans the unchanged #1021 audit flags (prose_quote_audit.audit on a one-row report);
- round 2: the round-2 reading, `composed_quotes.verdict` on each audit span as the audit pairs it;
- reading: `composed_quotes.classify`, the registered reading (in-order pairs, audit pairing differences, unpaired
  marks), each span as flagged or unflagged with its class;
- on a row with unpaired marks only, "pairs only": what the in-order pairs would give without the unpaired-marks
  rule (every pair tested, every other audit span an audit pairing difference), to show why the rule exists;
- outcome:
  - agree: F publishes and the reading finds no composed span, or F withholds and the reading finds one;
  - F-withheld leg: F withholds and the reading finds no composed span (usually because the audit flags nothing).
    In a run such an answer is never published, so the audit never reads it; checks 3 and 4 fail it through
    f_attribution.py's F-withheld count and check 5 through its error row;
  - FALSE FAILURE: F publishes and the reading finds a composed span (a run would fail with no composed quotation).
Cases tagged "disclosed" are the documented differences: markdown emphasis, a nested quotation, a backslash-escaped
mark, a character reference, a code span and a blockquote marker on a quotation's continuation line.
Exit 0 when no untagged case is a FALSE FAILURE under the registered reading.
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("composed_quotes", HERE / "composed_quotes.py")
CQ = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CQ)

backend, report = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
SOURCES = {(r["ticker"], r["question_id"]): r["inputs"]["source_text"] for r in json.load(open(report))["results"]}
os.chdir(backend)
sys.path.insert(0, backend)
from app.services.copilot_service import unsupported_prose_quotations  # noqa: E402
from app.services.provenance_service import normalize_for_match  # noqa: E402

AAPL, ASML = ("AAPL", "sales-gross-profit-2025"), ("ASML", "us-gaap-sales-net-income-2025")
BABA_NATIVE, BABA_VIEWED = ("BABA", "native-revenue-2026"), ("BABA", "viewed-native-revenue-2025")
B2 = ("Net income for 2025 amounted to €9,609.4 million, representing 29.4% of total net sales and €24.73 basic net "
      "income per ordinary share")
MDA = "further increased by 3% to RMB1,023,670 million (US$148,401 million) in fiscal year 2026"
CASES = [
    # Round 3, model-behaviour finding: a sub-floor quoted label followed by another quotation.
    ("pairing", BABA_NATIVE, f'The "Revenue" line agrees, and MD&A says revenue "{MDA}" [1].', ""),
    ("pairing", BABA_VIEWED, 'The "Revenue" line shows RMB996,347 million [F1], up from RMB941,168 million on the same '
                             '"Revenue" line a year earlier [F2].', ""),
    ("pairing", BABA_VIEWED, "The “Revenue” line shows RMB996,347 million [F1], up from RMB941,168 million on "
                             "the same “Revenue” line a year earlier [F2].", ""),
    ("pairing", BABA_VIEWED, 'The "Revenue" line agrees, and the table reads "Revenue ... 996,347" [F1].', ""),
    ("pairing", BABA_NATIVE, f'MD&A says "{MDA[:26]}\n{MDA[27:]}" and the line is "Revenue [1]".', ""),
    ("pairing", BABA_VIEWED, 'MD&A says revenue "increased by\n3%" and the table reads "Revenue 996,347" [F1].', ""),
    # Rounds 2 and 3: one quotation per answer.
    ("floor", AAPL, 'The company reports no "EBITDA [1]" figure.', ""),
    ("floor", BABA_VIEWED, 'The cell reads "... 996,347" [F1].', ""),
    ("floor", BABA_VIEWED, 'The cell reads "996,347" [F1].', ""),
    ("floor", ASML, 'The cell reads "9,609.4" [F1].', ""),
    ("floor", BABA_VIEWED, 'The line is "Revenue." [F1]', ""),
    ("floor", BABA_VIEWED, 'Revenue was "RMB996,347" [F1].', ""),
    ("ellipsis", BABA_VIEWED, 'The table shows "Revenue ... 996,347" [F1].', ""),
    ("ellipsis", ASML, 'The table shows "Net income 7,571.6 ... 9,609.4" [F1].', ""),
    ("ellipsis", BABA_VIEWED, 'The table shows "Revenue . . . 996,347" [F1].', ""),
    ("ellipsis", BABA_VIEWED, 'The table shows "Revenue … 996,347" [F1].', ""),
    ("edge", BABA_NATIVE, 'MD&A says revenue rose "by 3% to RMB1,023,670 million …" [1].', ""),
    ("edge", BABA_NATIVE, 'MD&A says revenue "… further increased by 3% to RMB1,023,670 million" [1].', ""),
    ("normalization", ASML, f'The report states "{B2}" [1].', ""),
    ("normalization", AAPL, 'Apple labels this line "Gross margin," and reports it [F1].', ""),
    ("normalization", ASML, 'The line "Total net sales [1]" is the 2025 figure.', ""),
    ("verified", BABA_NATIVE, f'MD&A says revenue "{MDA}" [1].', ""),
    ("verified", ASML, 'The table reads "Net income 7,571.6" [F1].', ""),
    ("composition", ASML, 'The table reads "Total net sales 32,667.3" [F1].', ""),
    ("composition", ASML, 'The table reads "Net income 9,609.4" [F2].', ""),
    ("composition", AAPL, 'The table reads "Total net sales 416,161" [F1].', ""),
    ("composition", AAPL, 'The table reads "Gross margin 195,201" [F2].', ""),
    ("composition", ASML, 'The table reads "Total net sales [F1] 32,667.3".', ""),
    # Documented differences (composed_quotes.py docstring, PREREGISTRATION.md).
    ("markdown", ASML, 'The line is "**Net income**" [F1].', "disclosed"),
    ("nested", BABA_NATIVE, 'The filing says "revenue "further increased by 3%" in fiscal year 2026" [1].', "disclosed"),
    # Round 4, model-behaviour findings: a quotation across a line break, an empty quotation, F's other marks.
    ("pairing", BABA_NATIVE, f'The "Revenue" line agrees, and MD&A says revenue "{MDA[:26]}\n{MDA[27:]}" [1].', ""),
    ("pairing", BABA_NATIVE, f'An empty "" pair, the "Revenue" line, and MD&A says revenue "{MDA}" [1].', ""),
    ("pairing", BABA_NATIVE, f'The "Revenue＂ line agrees, and MD&A says revenue ＂{MDA}" [1].', ""),
    ("pairing", BABA_NATIVE, f'The "Revenue" line agrees, and MD&A says revenue „{MDA}” [1].', ""),
    ("pairing", BABA_NATIVE, f'The "Revenue" line agrees, and MD&A says revenue „{MDA}‟ [1].', ""),
    # Round 4: an odd mark count (the unpaired-marks rule), and F's markdown reading of escapes and references.
    ("odd count", BABA_NATIVE, f'The "Revenue" line agrees, and MD&A says revenue "{MDA} [1].', ""),
    ("odd count", BABA_NATIVE, f'The &quot;Revenue" line agrees, and MD&A says revenue "{MDA}" [1].', "disclosed"),
    ("escape", BABA_NATIVE, f'The \\"Revenue\\" line agrees, and MD&A says revenue "{MDA}" [1].', "disclosed"),
    # Round 5, model-behaviour finding: F's display reading of a code span and of a quotation's continuation line.
    ("code span", ASML, 'The table reads "Net income `7,571.6`" [F1].', "disclosed"),
    ("block marker", BABA_NATIVE, f'> MD&A says revenue "{MDA[:26]}\n> {MDA[27:]}" [1].', "disclosed"),
]


def one_row_report(directory, index, key, answer):
    path = os.path.join(directory, f"case{index}.json")
    row = {"ticker": key[0], "question_id": key[1], "run_index": 0, "answer": answer, "score": {},
           "citations": [], "tool_trace": {}, "inputs": {"source_text": SOURCES[key]}}
    json.dump({"results": [row]}, open(path, "w", encoding="utf-8"))
    return path


def pairs_only(answer, source_text, flagged):
    """The in-order pairs' verdicts with no unpaired-marks rule (illustration only, never the measurement)."""
    folded = answer.translate(CQ.AUDIT.FOLD).translate(CQ.PAIRING_FOLD)
    pairs = [m.group(1) for m in CQ.PAIR.finditer(folded)]
    verdicts = [(CQ.verdict(p, CQ.INVENTORY.norm(source_text)), p) for p in pairs]
    return verdicts + [(CQ.PAIRING_DIFF, q) for q in flagged if q not in pairs]


failures, outcomes = 0, {}
with tempfile.TemporaryDirectory() as directory:
    for index, (shape, key, answer, tag) in enumerate(CASES, 1):
        f_reasons = unsupported_prose_quotations(answer, normalize_for_match(SOURCES[key]))
        path = one_row_report(directory, index, key, answer)
        raw, spans, unpaired, _ = CQ.classify(path)
        flagged = [q for hit in raw["composed_quote_rows"] for q in hit["composed_quotes"]]
        round2 = [CQ.verdict(q, CQ.INVENTORY.norm(SOURCES[key])) for q in flagged]
        composed = any(s["verdict"] == CQ.COMPOSED for s in spans)
        if not f_reasons:
            outcome = "FALSE FAILURE" if composed else "agree"
        else:
            outcome = "agree" if composed else "F-withheld leg"
        round2_outcome = "FALSE FAILURE" if not f_reasons and CQ.COMPOSED in round2 else "-"
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        failures += outcome == "FALSE FAILURE" and tag != "disclosed"
        print(f"case {index:2} [{shape}{', ' + tag if tag else ''}] {key[0]} {key[1]}")
        print(f"  answer:  {json.dumps(answer, ensure_ascii=False)}")
        print(f"  F:       {f_reasons or '[] (publishes)'}")
        print(f"  audit:   {json.dumps(flagged, ensure_ascii=False)}")
        print(f"  round 2: {round2}{'  <- FALSE FAILURE under the round-2 reading' if round2_outcome != '-' else ''}")
        print(f"  reading: {'unpaired marks (audit spans read as the audit pairs them); ' if unpaired else ''}"
              + (", ".join(f"{'flagged' if s['flagged'] else 'unflagged'} {s['verdict']} "
                           f"{json.dumps(s['span'], ensure_ascii=False)}" for s in spans) or "nothing flagged"))
        if unpaired:
            alone = pairs_only(answer, SOURCES[key], flagged)
            alone_composed = any(cls == CQ.COMPOSED for cls, _ in alone)
            hidden = [q for q, v in zip(flagged, round2) if v == CQ.COMPOSED and (CQ.PAIRING_DIFF, q) in alone]
            print("  pairs only (no unpaired-marks rule, illustration): "
                  + ", ".join(f"{cls} {json.dumps(span, ensure_ascii=False)}" for cls, span in alone)
                  + (f"  <- FALSE FAILURE {'with or ' if composed else ''}without the rule"
                     if alone_composed and not f_reasons else "")
                  + (f"  <- {len(hidden)} composed audit span(s) become audit pairing differences without the rule"
                     if hidden else ""))
        print(f"  outcome: {outcome}\n")
print(f"{len(CASES)} cases: " + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items()))
      + f"; untagged FALSE FAILURE {failures}")
sys.exit(1 if failures else 0)
