"""Redundant cross-check counter (declared method). Offline over a retained copilot-eval.json; no app import, no
provider call, no network.

A redundant cross-check is a filing-text citation on a row whose answer already uses tool figures, i.e. a row
whose tool_trace.tool_results is non-empty:
- published row (no `error`): count the final citations whose section_ref does not start with "XBRL";
- withheld row (`error` set): count the objects with a positive-integer "n" in the declared JSON array that follows
  the ===CITATIONS=== line of the joined tool_trace.candidate_deltas.
Each counted excerpt is listed with `restates_tool_figure`: some figure token in the excerpt
(\\d{1,3}(,\\d{3})+(\\.\\d+)?, \\d+\\.\\d+ or \\d{5,}) equals, at the excerpt's displayed decimals, a tool value on the
same row divided by 1, 1e3, 1e6 or 1e9. The tool values are the XBRL citations' `value` on a published row, and on a
withheld row the tool_results values whose [F#] cite appears in the candidate prose.
Text citations on tool-less rows are not cross-checks; they are counted separately.
Also listed, on every row (acceptance check 1 support): each declared object whose "n" is not a positive JSON
integer, an unparseable declaration, and every withheld row's error and captured withheld reason.

Usage: python crosscheck_count.py LABEL=path/copilot-eval.json [...]
"""
import json
import re
import sys
from collections import Counter

CITATIONS = re.compile(r"^\s*===\s*CITATIONS\s*===\s*$", re.I | re.M)
FOLLOWUPS = re.compile(r"^\s*===\s*FOLLOW-?UPS\s*===\s*$", re.I | re.M)
FIGURE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d{5,}")


def declared(candidate):
    """(objects, error) for the candidate's declared citation array; ([], None) when there is none."""
    parts = CITATIONS.split(candidate, maxsplit=1)
    if len(parts) < 2:
        return [], None
    body = FOLLOWUPS.split(parts[1], maxsplit=1)[0].strip()
    try:
        value, _ = json.JSONDecoder().raw_decode(body)
    except ValueError as exc:
        return [], f"unparseable: {exc}"
    return (value, None) if isinstance(value, list) else ([], "not a JSON array")


def positive_int(n):
    return isinstance(n, int) and not isinstance(n, bool) and n > 0


def restates(excerpt, values):
    for token in FIGURE.findall(excerpt or ""):
        decimals = len(token.split(".")[1]) if "." in token else 0
        shown = float(token.replace(",", ""))
        for v in values:
            if v and any(abs(round(v / scale, decimals) - shown) < 10 ** -(decimals + 3) for scale in (1, 1e3, 1e6, 1e9)):
                return True
    return False


def count(path):
    report = json.load(open(path, encoding="utf-8"))
    rows = []
    for row in report["results"]:
        trace = row.get("tool_trace") if isinstance(row.get("tool_trace"), dict) else {}
        candidate = "".join(d for d in trace.get("candidate_deltas") or [] if isinstance(d, str))
        objects, decl_error = declared(candidate)
        bad_ids = [o.get("n") if isinstance(o, dict) else o for o in objects
                   if not (isinstance(o, dict) and positive_int(o.get("n")))]
        tool_using = bool(trace.get("tool_results"))
        withheld = bool(row.get("error"))
        if withheld:
            prose = CITATIONS.split(candidate, maxsplit=1)[0]
            values = [((t.get("result") or {}).get("value")) for t in trace.get("tool_results") or []
                      if isinstance(t, dict) and f"[{(t.get('result') or {}).get('cite')}]" in prose]
            text = [o.get("excerpt") for o in objects if isinstance(o, dict) and positive_int(o.get("n"))]
        else:
            cits = row.get("citations") or []
            values = [c.get("value") for c in cits if str(c.get("section_ref") or "").startswith("XBRL")]
            text = [c.get("excerpt") for c in cits if not str(c.get("section_ref") or "").startswith("XBRL")]
        values = [v for v in values if isinstance(v, (int, float))]
        rows.append({"ticker": row.get("ticker"), "question_id": row.get("question_id"), "run_index": row.get("run_index"),
                     "withheld": withheld, "tool_using": tool_using, "text_citations": text,
                     "restates": [restates(e, values) for e in text], "bad_ids": bad_ids, "decl_error": decl_error,
                     "error": row.get("error"),
                     "withheld_reasons": trace.get("withheld_reasons") or (row.get("error") or {}).get("withheld_reason")})
    return report, rows


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        label, path = arg.split("=", 1)
        report, rows = count(path)
        cross = [r for r in rows if r["tool_using"]]
        pub = sum(len(r["text_citations"]) for r in cross if not r["withheld"])
        wh = sum(len(r["text_citations"]) for r in cross if r["withheld"])
        rest = sum(sum(r["restates"]) for r in cross)
        toolless = sum(len(r["text_citations"]) for r in rows if not r["tool_using"])
        per = Counter()
        for r in cross:
            per[r["ticker"]] += len(r["text_citations"])
        print(f"{label}: tool-using rows {len(cross)}/{len(rows)} (withheld {sum(r['withheld'] for r in cross)}); "
              f"redundant cross-check citations {pub + wh} (published {pub}, withheld-declared {wh}); "
              f"restating a tool figure {rest}; per ticker {dict(sorted(per.items()))}; "
              f"text citations on tool-less rows {toolless}")
        print(f"  declared identities: non-positive-integer n {sum(len(r['bad_ids']) for r in rows)} "
              f"{[(r['ticker'], r['run_index'], r['bad_ids']) for r in rows if r['bad_ids']]}; unparseable declarations "
              f"{[(r['ticker'], r['run_index'], r['decl_error']) for r in rows if r['decl_error']]}")
        for r in rows:
            if r["withheld"]:
                print(f"  withheld {r['ticker']} {r['question_id']} d{r['run_index']}: error {json.dumps(r['error'])}; "
                      f"captured reason {json.dumps(r['withheld_reasons'])}")
        for r in cross:
            for excerpt, flag in zip(r["text_citations"], r["restates"]):
                print(f"   {r['ticker']:5} {r['question_id']:30} d{r['run_index']} {'W' if r['withheld'] else 'P'} "
                      f"restates_tool_figure={flag!s:5} {json.dumps(excerpt, ensure_ascii=False)}")
