"""Synthetic controls on the REAL retained source texts (run 36809122540), plus fail-closed cases.

Each case: (id, kind, ticker-or-literal-source, answer, expected reasons). Also runs the audit's own
regex/fold on the same answer so audit artifacts are visible. Writes controls-results.json.
"""
from __future__ import annotations

import json
import os
import re
import sys

from app.services.provenance_service import normalize_for_match

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prose_quote_predicate as P  # noqa: E402
from replay import audit_spans  # noqa: E402

SCRATCH = os.path.dirname(HERE)
ROWS = json.load(open(f"{SCRATCH}/copilot-36809122540/copilot-eval.json"))["results"]
SOURCES = {r["ticker"]: r["inputs"]["source_text"] for r in ROWS}
LITERAL = "As shown in Note [7] to the financial statements, revenue grew in fiscal 2025."

NI = "Net income for 2025 amounted to €9,609.4 million, representing 29.4% of total net sales"
N, E, U, S = P.NOT_IN_SOURCE, P.ELIDED, P.UNBALANCED, P.SOURCE_UNAVAILABLE

CASES = [
    # --- valid quotations: must NOT be flagged -------------------------------------------------
    ("V01", "valid: supported whitespace (newlines, NBSP, space-before-comma in source)", "ASML", f'The filing says "{NI}" [1].', []),
    ("V02", "valid: curly quote marks", "ASML", f"The filing says “{NI}” [1].", []),
    ("V03", "valid: period inside closing quote", "ASML", f'The filing says "{NI}." [1]', []),
    ("V04", "valid: comma inside closing quote", "ASML", 'It notes "Net income for 2025 amounted to €9,609.4 million," which is cited [1].', []),
    ("V05", "valid: leading/trailing truncation ellipsis", "ASML", '"...amounted to €9,609.4 million, representing 29.4%..." [1]', []),
    ("V06", "valid: unicode edge ellipsis", "ASML", '"…amounted to €9,609.4 million, representing 29.4%…" [1]', []),
    ("V07", "valid: resolved marker inside quote, at end", "ASML", f'The filing says "{NI} [1]".', []),
    ("V08", "valid: marker inside quote, mid-span", "ASML", '"Net income for 2025 amounted to €9,609.4 million [1], representing 29.4% of total net sales"', []),
    ("V09", "valid: F-marker inside quote (pre-resolution form)", "ASML", f'"{NI} [F2]"', []),
    ("V10", "valid: em dash in source, hyphen typed", "MSFT", 'The filing is organised under "NOTE 2 - EARNINGS PER SHARE" [1].', []),
    ("V11", "valid: curly apostrophe + NBSP + space-before-comma in source", "ASML", '"For a comparison of ASML\'s operating results for the year ended December 31, 2024, with the year ended" [1]', []),
    ("V12", "valid: nested straight quotes from source (the \"Company\")", "TSLA", 'The auditor covered "consolidated balance sheets of Tesla, Inc. and its subsidiaries (the "Company") as of December 31, 2024 and 2023" [1].', []),
    ("V13", "valid: nested curly-in-straight quotes from source", "AAPL", 'The filing refers to "the Company’s chief operating decision maker (“CODM”). In addition, ASU 2023-07 requires the Company to disclose" [1].', []),
    ("V14", "valid: literal dot leaders in source (interior dots, contiguous)", "BABA", '"Date of event requiring this shell company report............... For the transition period from" [1]', []),
    ("V15", "valid: source-literal bracket kept (literal-first check)", LITERAL, '"As shown in Note [7] to the financial statements" [1]', []),
    ("V16", "valid: whitespace inside the model quote", "ASML", '"Net income for 2025\n amounted to   €9,609.4 million" [1]', []),
    ("V17", "term below floor, NOT in source: ROE", "ASML", 'Return on equity ("ROE") is not reported [1].', []),
    ("V18", "term below floor, NOT in source: Adjusted EBIT", "ASML", 'ASML does not report "Adjusted EBIT" [1].', []),
    ("V19", "term below floor, NOT in source: 22-char label", "ASML", 'It does not use "Adjusted EBITDA margin" [1].', []),
    ("V20", "terms below floor, audit mispairing bait", "ASML", 'The "ROE" line, which this filing never names or defines anywhere, sits beside "Revenue" [1].', []),
    ("V21", "no quotes; ellipsis outside quotes", "ASML", "Total net sales were €32,667.3 million ... and net income €9,609.4 million [1].", []),
    ("V22", "empty quotation", "ASML", 'The label is "" here [1].', []),
    # --- composed / unsupported: must be flagged ------------------------------------------------
    ("C01", "composed: retained elided cell quote", "BABA", 'which report "Revenue ... 996,347" for the year [2].', [E]),
    ("C02", "composed: retained label+skipped-cell quote", "ASML", 'showing "Total net sales 32,667.3" and "Net income 9,609.4" for 2025 [3].', [N]),
    ("C03", "unsupported: paraphrased >= floor", "ASML", '"Net income for 2025 was €9,609.4 million" [1]', [N]),
    ("C04", "composed: two sentences stitched, no ellipsis", "ASML", '"Net income for 2025 amounted to €9,609.4 million. This compares to €7,571.6 million" [1]', [N]),
    ("C05", "composed: unicode interior ellipsis", "ASML", '"Net income for 2025 amounted to … 29.4% of total net sales" [1]', [E]),
    ("C06", "composed: spaced . . . interior elision", "ASML", '"Net income for 2025 . . . 29.4% of total net sales" [1]', [E]),
    ("C07", "composed: curly marks", "ASML", "showing “Total net sales 32,667.3” [3].", [N]),
    ("C08", "composed: low-9 + curly close", "ASML", "showing „Total net sales 32,667.3” [3].", [N]),
    ("C09", "composed: marker inside does not launder", "ASML", 'showing "Total net sales [1] 32,667.3" [3].', [N]),
    ("C10", "composed: edge period does not launder", "ASML", 'showing "Total net sales 32,667.3." [3]', [N]),
    ("C11", "fail-closed: unbalanced (unterminated quote)", "ASML", 'The table shows "Total net sales 32,667.3 [1].', [U]),
    ("C12", "fail-closed: unbalanced, valid quote plus stray inch mark", "ASML", f'"{NI}" [1] on a 12" wafer.', [U]),
    ("C13", "fail-closed: missing source", "", f'The filing says "{NI}" [1].', [S]),
    ("C14", "fail-closed: missing source, elided", "", '"Revenue ... 996,347" [1]', [S]),
    ("C15", "ordering/determinism: two failures in span order", "ASML", '"Net income for 2025 was €9,609.4 million" and "Revenue ... 996,347" [1]', [N, E]),
    ("C16", "term >= floor NOT in source (by design flagged)", "ASML", 'It does not use "Adjusted EBITDA excluding special items" [1].', [N]),
    # --- known false negatives (documented residual) -------------------------------------------
    ("R01", "residual FN: short label+cell stitch alone", "ASML", 'showing "Net income 9,609.4" [1].', []),
    ("R02", "residual FN: short label+cell stitch alone", "BABA", 'reporting "Revenue 996,347" [1].', []),
    ("R03", "residual FN: single-quoted composed span", "ASML", "showing 'Total net sales 32,667.3' [1].", []),
]


def main():
    out, failures = [], []
    for cid, kind, src_key, answer, expected in CASES:
        source = SOURCES.get(src_key, src_key) if src_key else ""
        ns = normalize_for_match(source)
        got = P.unsupported_prose_quotations(answer, ns)
        again = P.unsupported_prose_quotations(answer, ns)
        audit = audit_spans(answer, source) if source else "n/a (no source)"
        ok = got == expected and got == again
        if not ok:
            failures.append(cid)
        out.append({"id": cid, "kind": kind, "source": src_key if src_key in SOURCES else ("literal" if src_key else "missing"),
                    "answer": answer, "expected": expected, "got": got, "deterministic": got == again,
                    "ok": ok, "audit_flags": audit})
    json.dump({"cases": out, "failures": failures}, open(f"{HERE}/controls-results.json", "w"), indent=1, ensure_ascii=False)
    for c in out:
        print(f'{c["id"]} {"OK " if c["ok"] else "BAD"} got={c["got"]!s:40} audit={c["audit_flags"]!s:.70} | {c["kind"]}')
    print("failures:", failures)
    # The None-source variant must fail closed too.
    assert P.unsupported_prose_quotations(f'"{NI}"', None) == [S]
    assert P.unsupported_prose_quotations(None, "x") == [] and P.unsupported_prose_quotations("", None) == []
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
