"""Decision F attribution over retained copilot-eval runs: which published surface a withheld response fails.

Offline tooling only: no provider call, no network, no database. Run from ``backend/`` with provider
keys unset, e.g.::

    env -u OPENAI_API_KEY -u DEEPSEEK_API_KEY -u OPENAI_BASE_URL python f_attribution.py \
        --out f-attribution.json path/to/copilot-eval.json [...]
    env -u OPENAI_API_KEY -u DEEPSEEK_API_KEY -u OPENAI_BASE_URL python f_attribution.py --self-test

For every row whose ``tool_trace.candidate_deltas`` were retained (copilot_runner, main 02628e57),
the script replays the service's own ``answer_filing_question`` offline: the recorded tool results
are served back in order, then the raw candidate deltas are streamed. Every publication transform
therefore runs as in production (citation parsing and resolution, the not-disclosed envelope, chip
trimming, length and count limits). The decision F check is observed at its single call site,
``_withhold_unsupported_quotations``: the final checked strings are recorded and each surface is
checked separately with the service's predicates, while the replay is let through so that its
terminal event can be compared with the retained ``service_events`` (replay fidelity). From the
deltas the script also splits the raw answer, NOT_DISCLOSED reason and FOLLOWUPS envelope.

Rows the run itself published: the surfaces F would withhold (answer, reason, chip with its index),
the exact checked text, the source binding (the text the service selected: content_cache
.critical_excerpt, i.e. the row's inputs.source_text, with its sha256 and length) and the
deterministic reason codes; each withheld response is counted once, however many surfaces fail.

Rows the run itself withheld or errored are classified:
  F-withheld        the replay reaches the check and it fails (the surfaces and codes are reported);
  other reason      the replay ends in an error before or without failing the check (the logged,
                    application-owned reason is reported);
  UNEXPLAINED       anything else: the replay made a repair lookup the trace does not serve (so the
                    replay may not be the run, and neither verdict is attributed), the replay
                    publishes with no F reason, or there is no trace to replay. UNEXPLAINED rows
                    are printed loudly, never counted as not-F, and make the exit status 3.

Replay mismatches (replayed terminal event differs from the retained one) are reported with their
cause: a lookup the uncited-claim repair makes server-side (get_financial_fact) that the trace does
not record, or UNEXPLAINED. Each run's ``source_sha`` is recorded next to the code the tool imported.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace

# Hermetic settings, as backend/tests/conftest.py sets them: mock credentials, a closed local port
# for the provider, no Redis, an in-memory database. Nothing here may reach a network.
for key in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_BASE_URL"):
    os.environ.pop(key, None)
os.environ.update({
    "SECRET_KEY": "offline-attribution-secret-key-0123456789",
    "OPENAI_API_KEY": "sk-offline-attribution",
    "OPENAI_BASE_URL": "http://127.0.0.1:9/v1",
    "STRIPE_SECRET_KEY": "sk_test_offline",
    "STRIPE_WEBHOOK_SECRET": "whsec_offline",
    "SKIP_REDIS_INIT": "true",
    "PWNED_PASSWORD_CHECK_ENABLED": "false",
    "DATABASE_URL": "sqlite://",
})
sys.path.insert(0, os.getcwd())
logging.disable(logging.ERROR - 1)   # keep the service's publication-boundary warnings off the console

from app.services import copilot_service as cs  # noqa: E402
from app.services import copilot_tools  # noqa: E402
from app.services.openai_service import STREAM_ERROR_SENTINEL  # noqa: E402
from app.services.provenance_service import normalize_for_match  # noqa: E402

REPAIR_CAUSE = "unrecorded server-side get_financial_fact lookup in the uncited-claim repair step"


def code_identity():
    """The code this tool imported: the service's sha256, and the git commit and state of its tree."""
    path = os.path.abspath(cs.__file__)
    identity = {"service": path, "service_sha256": hashlib.sha256(open(path, "rb").read()).hexdigest()}
    try:
        root = os.path.dirname(path)
        identity["git_head"] = subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD"], text=True).strip()
        identity["git_dirty"] = bool(subprocess.check_output(["git", "-C", root, "status", "--porcelain"], text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        identity["git_head"], identity["git_dirty"] = None, None
    return identity


def split_deltas(text):
    """The raw answer, NOT_DISCLOSED reason and FOLLOWUPS envelope, split at the service's sentinels."""
    parts = {"answer": text, "reason": None, "followups_envelope": None}
    nd, cit = text.find(cs._NOT_DISCLOSED_SENTINEL), text.find(cs._CITATIONS_SENTINEL)
    if nd != -1 and (cit == -1 or nd < cit):
        parts["answer"], rest = text[:nd], text[nd + len(cs._NOT_DISCLOSED_SENTINEL):]
        match = cs._FOLLOWUPS_RE.search(rest)
        parts["reason"] = (rest[:match.start()] if match else rest).strip()
        parts["followups_envelope"] = rest[match.end():].strip() if match else None
    elif cit != -1:
        parts["answer"], rest = text[:cit], text[cit + len(cs._CITATIONS_SENTINEL):]
        match = cs._FOLLOWUPS_RE.search(rest)
        parts["followups_envelope"] = rest[match.end():].strip() if match else None
    parts["answer"] = parts["answer"].strip()
    return parts


def snapshot(row, source_meta):
    inputs = row.get("inputs") or {}
    meta = source_meta.get(row["accession_number"], {})
    return SimpleNamespace(
        accession_number=inputs.get("accession_number") or row["accession_number"],
        period_of_report=inputs.get("period_of_report"), filing_type=meta.get("filing_type"),
        filing_date=(meta.get("metadata") or {}).get("filing_date"), document_url=meta.get("document_url"),
        sec_url=(meta.get("metadata") or {}).get("sec_url"), xbrl_data=inputs.get("xbrl_data"), company_id=None,
        cik=meta.get("cik"), content_cache=SimpleNamespace(critical_excerpt=inputs.get("source_text"), markdown_content=None),
        company=SimpleNamespace(name=(meta.get("metadata") or {}).get("company_name"), ticker=row.get("ticker")),
    )


def surfaces(normalized_source, markdown, plain, path):
    """Each checked surface with its exact text and reason codes, as the service checks it."""
    out = []
    if markdown:
        out.append({"surface": "answer", "index": None, "text": markdown,
                    "reasons": cs.unsupported_prose_quotations(markdown, normalized_source)})
    for index, text in enumerate(plain):
        reason = path == "not_disclosed" and index == 0
        out.append({"surface": "reason" if reason else "chip", "index": None if reason else index - (path == "not_disclosed"),
                    "text": text, "reasons": cs.unsupported_plain_quotations(text, normalized_source)})
    return out


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record)


async def replay(row, source_meta):
    trace = row["tool_trace"]
    recorded = list(trace.get("tool_results") or [])
    all_recorded = list(recorded)
    observed, unrecorded = [], []
    in_stream = {"on": False}

    def raw(result):
        result = copy.deepcopy(result)
        if isinstance(result, dict):
            result.pop("cite", None)
            result.pop("_marker", None)
        return result

    def run_tool(name, args, *_args, **_kwargs):
        if in_stream["on"] and recorded:
            call = recorded.pop(0)
            assert call["name"] == name and call["args"] == args, "tool replay out of order"
            return raw(call["result"])
        # The uncited-claim repair looks figures up itself; the trace does not record those calls.
        # Serve the same lookup the model made, when it made one; otherwise it is unavailable.
        for call in all_recorded:
            if call["name"] == name and call["args"] == args:
                unrecorded.append({"name": name, "args": args, "served_from_trace": True})
                return raw(call["result"])
        unrecorded.append({"name": name, "args": args, "served_from_trace": False})
        return {"error": "unavailable_offline"}

    async def stream(messages, tools, service_run_tool, **_kwargs):
        in_stream["on"] = True
        for call in list(recorded):
            service_run_tool(call["name"], copy.deepcopy(call["args"]))
        in_stream["on"] = False
        for delta in trace["candidate_deltas"]:
            yield delta
        if any(control.get("type") == "error" for control in trace.get("provider_controls") or []):
            yield STREAM_ERROR_SENTINEL

    def observe(normalized_source, markdown, plain):
        observed.append((normalized_source, markdown, list(plain)))

    capture = _Capture()
    saved = (copilot_tools.run_tool, cs.openai_service.stream_chat_with_tools, cs._withhold_unsupported_quotations)
    copilot_tools.run_tool, cs.openai_service.stream_chat_with_tools, cs._withhold_unsupported_quotations = (
        run_tool, stream, observe)
    logging.disable(logging.NOTSET)
    cs.logger.addHandler(capture)
    propagate, cs.logger.propagate = cs.logger.propagate, False
    try:
        filing = snapshot(row, source_meta)
        events = [event async for event in cs.answer_filing_question(filing=filing, question=row["question"])]
    finally:
        cs.logger.removeHandler(capture)
        cs.logger.propagate = propagate
        logging.disable(logging.ERROR - 1)
        copilot_tools.run_tool, cs.openai_service.stream_chat_with_tools, cs._withhold_unsupported_quotations = saved
    logged = []
    for record in capture.records:
        if record.exc_info:
            logged.append(f"exception {record.exc_info[0].__name__}")
        elif "publication boundary" in record.msg:
            logged.append(str(record.args[0]) if record.args else record.getMessage())
    return events, observed, unrecorded, logged


def comparable(event):
    return {k: event.get(k) for k in ("type", "answer", "citations", "grounded", "kind", "followups", "message")}


def analyse(paths):
    report = {"code": code_identity(), "runs": [], "rows": []}
    for path in paths:
        raw = open(path, "rb").read()
        data = json.loads(raw)
        run_id = (re.search(r"(\d{11})", os.path.basename(path)) or re.search(r"(\d{11})", path)
                  or re.search(r"(.*)", path)).group(1)
        source_meta = {s["accession_number"]: s for s in (data.get("preparation") or {}).get("sources", [])}
        run = {"run": run_id, "file_sha256": hashlib.sha256(raw).hexdigest(), "source_sha": data.get("source_sha"),
               "tool_code": report["code"], "rows": len(data["results"]), "with_deltas": 0}
        for row in data["results"]:
            source = (row.get("inputs") or {}).get("source_text") or ""
            normalized_source = normalize_for_match(source)
            trace = row.get("tool_trace") or {}
            retained_events = trace.get("service_events") or []
            retained = retained_events[-1] if retained_events else {}
            run_withheld = row.get("answer") is None or "error" in row or retained.get("type") == "error"
            entry = {"run": run_id, "row": f'{row["ticker"]} {row["question_id"]} d{row["run_index"]}',
                     "run_outcome": "withheld or errored" if run_withheld else "published",
                     "run_error": row.get("error"),
                     "source_binding": {"field": "content_cache.critical_excerpt (inputs.source_text)",
                                        "accession": row["accession_number"], "chars": len(source),
                                        "sha256": hashlib.sha256(source.encode()).hexdigest()}}
            deltas = trace.get("candidate_deltas")
            if deltas is None:
                entry["mode"] = "answer-only (no candidate deltas retained; chips unknown)"
                answer = row.get("answer")
                if answer is None:
                    entry["surfaces"] = []
                elif row.get("kind") == "not_disclosed":
                    entry["surfaces"] = surfaces(normalized_source, "", [answer], "not_disclosed")
                else:
                    entry["surfaces"] = surfaces(normalized_source, answer, [], "answer")
                entry["fidelity"] = None
            else:
                run["with_deltas"] += 1
                entry["mode"] = "replayed from candidate deltas"
                entry["raw"] = split_deltas("".join(deltas))
                events, observed, unrecorded, logged = asyncio.run(replay(row, source_meta))
                entry["unrecorded_tool_calls"] = unrecorded
                entry["replay_logged"] = logged
                entry["terminal"] = {"replay": events[-1].get("type"), "retained": retained.get("type")}
                replayed = []
                if observed:
                    checked_source, markdown, plain = observed[-1]
                    assert checked_source == normalized_source
                    replayed = surfaces(normalized_source, markdown, plain, events[-1].get("kind"))
                entry["check_reached"] = bool(observed)
                entry["replay_surfaces"] = replayed
                # The replay lets the check through; with F the service withholds where it fails. The
                # retained run may predate F, so its terminal event may match either.
                with_f = ({"type": "error", "message": cs._PUBLICATION_ERROR} if any(x["reasons"] for x in replayed)
                          else events[-1])
                matches = [name for name, event in (("without F", events[-1]), ("with F", with_f))
                           if comparable(event) == comparable(retained)]
                entry["fidelity"] = bool(matches)
                entry["fidelity_matches"] = matches
                if retained.get("type") == "complete":
                    # The retained terminal event holds the final published strings; the check runs on
                    # exactly these, after every transform. They decide; the replay must agree.
                    kind = retained.get("kind")
                    final = retained.get("followups") or []
                    entry["surfaces"] = (surfaces(normalized_source, retained["answer"], final, "answer") if kind == "answer"
                                         else surfaces(normalized_source, "", [retained["answer"], *final], "not_disclosed"))
                    entry["verdict_source"] = "retained final strings"
                else:
                    entry["surfaces"] = replayed
                    entry["verdict_source"] = "replay (the run published nothing)"
                entry["replay_agrees"] = ([(x["surface"], x["index"], x["reasons"]) for x in replayed]
                                          == [(x["surface"], x["index"], x["reasons"]) for x in entry["surfaces"]])
                if not entry["fidelity"]:
                    entry["mismatch_cause"] = (REPAIR_CAUSE if any(not u["served_from_trace"] for u in unrecorded)
                                               else "UNEXPLAINED")
                entry["chips_with_double_quotes"] = sum(
                    1 for x in entry["surfaces"] if x["surface"] == "chip" and cs._QUOTE_MARK_RE.search(x["text"]))
            failed = [s for s in entry["surfaces"] if s["reasons"]]
            entry["failed"] = [{"surface": s["surface"], "index": s["index"], "text": s["text"], "reasons": s["reasons"]}
                               for s in failed]
            entry["withheld_by_f"] = bool(failed)
            if run_withheld:
                unserved = deltas is not None and any(not u["served_from_trace"] for u in entry["unrecorded_tool_calls"])
                if unserved:
                    entry["classification"] = "UNEXPLAINED"
                    entry["unexplained_because"] = ("the replay made a repair lookup the trace does not serve, so its"
                                                    " verdict is not attributed")
                elif failed:
                    entry["classification"] = "F-withheld"
                elif deltas is not None and events[-1].get("type") == "error" and entry["fidelity"]:
                    entry["classification"] = "other reason"
                    entry["other_reason"] = logged or [events[-1].get("message")]
                else:
                    entry["classification"] = "UNEXPLAINED"
                    entry["unexplained_because"] = (
                        "no candidate deltas retained to replay" if deltas is None
                        else "the replay publishes with no F reason" if events[-1].get("type") == "complete"
                        else "the replay errs differently from the run")
            report["rows"].append(entry)
        report["runs"].append(run)
    rows = report["rows"]
    replayed = [r for r in rows if r["fidelity"] is not None]
    withheld_by_run = [r for r in rows if r["run_outcome"] != "published"]
    report["summary"] = {
        "code": report["code"],
        "runs": [{"run": r["run"], "source_sha": r["source_sha"], "rows": r["rows"], "with_deltas": r["with_deltas"]}
                 for r in report["runs"]],
        "rows": len(rows), "replayed": len(replayed), "answer_only": len(rows) - len(replayed),
        "replay_mismatches": [{"row": r["row"] + " @" + r["run"], "cause": r["mismatch_cause"]}
                              for r in replayed if not r["fidelity"]],
        "replay_mismatch_causes": {cause: sum(1 for r in replayed if not r["fidelity"] and r["mismatch_cause"] == cause)
                                   for cause in sorted({r["mismatch_cause"] for r in replayed if not r["fidelity"]})},
        "replay_verdict_disagreements": [r["row"] + " @" + r["run"] for r in replayed if not r["replay_agrees"]],
        "published_by_run": {
            "rows": len(rows) - len(withheld_by_run),
            "f_would_withhold": sum(r["withheld_by_f"] for r in rows if r["run_outcome"] == "published"),
            "by_surface": {k: sum(any(f["surface"] == k for f in r["failed"]) for r in rows if r["run_outcome"] == "published")
                           for k in ("answer", "reason", "chip")},
        },
        "withheld_or_errored_by_run": {
            "rows": len(withheld_by_run),
            "F-withheld": [r["row"] + " @" + r["run"] for r in withheld_by_run if r["classification"] == "F-withheld"],
            "other reason": [r["row"] + " @" + r["run"] for r in withheld_by_run if r["classification"] == "other reason"],
            "UNEXPLAINED": [r["row"] + " @" + r["run"] for r in withheld_by_run if r["classification"] == "UNEXPLAINED"],
        },
        "not_disclosed_rows": sum(any(s["surface"] == "reason" for s in r["surfaces"]) for r in rows),
        "rows_with_chips": sum(any(s["surface"] == "chip" for s in r["surfaces"]) for r in replayed),
        "chips_checked": sum(sum(s["surface"] == "chip" for s in r["surfaces"]) for r in replayed),
        "rows_with_double_quoted_chips": sum(bool(r.get("chips_with_double_quotes")) for r in replayed),
        "chips_with_double_quotes": sum(r.get("chips_with_double_quotes", 0) for r in replayed),
        "failing_chips": sum(sum(f["surface"] == "chip" for f in r["failed"]) for r in rows),
    }
    return report


def print_report(report):
    summary = report["summary"]
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    for r in report["rows"]:
        if r["withheld_by_f"]:
            print("F", r["run_outcome"], r["run"], r["row"], [(f["surface"], f["index"], f["reasons"]) for f in r["failed"]])
    unexplained = [r for r in report["rows"] if r.get("classification") == "UNEXPLAINED"
                   or r.get("mismatch_cause") == "UNEXPLAINED"]
    for r in unexplained:
        print("!" * 100, file=sys.stderr)
        print(f"UNEXPLAINED: {r['run']} {r['row']}: {r.get('unexplained_because') or 'replay mismatch with no known cause'}"
              " (not counted as not-F)", file=sys.stderr)
    if unexplained:
        print("!" * 100, file=sys.stderr)
    return 3 if unexplained else 0


def self_test():
    """Synthetic rows through the real classifier: F-withheld on each surface (the answer, a
    not-disclosed reason, a not-disclosed chip, an answer-path chip, each with its chip index), one
    withheld for another reason, one errored row that replays as published with no F reason, and one
    whose replay made a repair lookup the trace does not serve (both UNEXPLAINED, although the latter
    also fails a chip)."""
    from app.services.copilot_service import _PUBLICATION_ERROR

    source = "Net income for 2025 amounted to 9,609.4 million, representing 29.4% of total net sales."
    citations = '[{"n": 1, "excerpt": "Net income for 2025 amounted to 9,609.4 million"}]'
    followups = '["What changed in margins?", "What are the risks?"]'

    def row(index, deltas):
        return {"ticker": "SYN", "question_id": f"synthetic-{index}", "run_index": 0, "question": "q",
                "accession_number": "0000000000-26-000001", "answer": None, "kind": None,
                "error": {"type": "ValueError", "stage": "answer_or_score"},
                "inputs": {"source_text": source, "xbrl_data": None, "period_of_report": None,
                           "accession_number": "0000000000-26-000001"},
                "tool_trace": {"candidate_deltas": deltas, "tool_results": [], "provider_controls": [],
                               "service_events": [{"type": "error", "message": _PUBLICATION_ERROR}]}}

    invented_chip = 'Why does the filing say "Invented text missing from the source"?'
    run = {"source_sha": "synthetic", "results": [
        row(1, ['The filing says "Invented text missing from the source" [1].',
                f"\n===CITATIONS===\n{citations}\n===FOLLOWUPS===\n{followups}"]),
        row(2, ["Net income for 2025 amounted to 9,609.4 million [1]."]),
        row(3, [f"Net income for 2025 amounted to 9,609.4 million [1].\n===CITATIONS===\n{citations}"]),
        row(4, ['===NOT_DISCLOSED===\nSegment margins are not broken out; the filing only says "Invented text'
                f' missing from the source".\n===FOLLOWUPS===\n{followups}']),
        row(5, ["===NOT_DISCLOSED===\nSegment margins are not broken out.\n===FOLLOWUPS===\n"
                + json.dumps(["What changed in margins?", invented_chip])]),
        row(6, [f"Net income for 2025 amounted to 9,609.4 million [1].\n===CITATIONS===\n{citations}"
                "\n===FOLLOWUPS===\n" + json.dumps([invented_chip, "What are the risks?"])]),
        row(7, ["Net sales for the fiscal year ended September 27, 2025 were $416,161 million.\n===CITATIONS===\n[]"
                "\n===FOLLOWUPS===\n" + json.dumps(["What changed in margins?", invented_chip])]),
    ]}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "copilot-eval-99999999999.json")
        json.dump(run, open(path, "w"))
        report = analyse([path])
    classes = {r["row"]: r["classification"] for r in report["rows"]}
    assert classes == {"SYN synthetic-1 d0": "F-withheld", "SYN synthetic-2 d0": "other reason",
                       "SYN synthetic-3 d0": "UNEXPLAINED", "SYN synthetic-4 d0": "F-withheld",
                       "SYN synthetic-5 d0": "F-withheld", "SYN synthetic-6 d0": "F-withheld",
                       "SYN synthetic-7 d0": "UNEXPLAINED"}, classes
    by_run = report["summary"]["withheld_or_errored_by_run"]
    assert by_run["UNEXPLAINED"] == ["SYN synthetic-3 d0 @99999999999", "SYN synthetic-7 d0 @99999999999"]
    assert len(by_run["other reason"]) == 1
    failed = {r["row"]: [(f["surface"], f["index"], f["reasons"]) for f in r["failed"]] for r in report["rows"]}
    assert failed["SYN synthetic-1 d0"] == [("answer", None, ["quotation_not_in_source"])]
    assert failed["SYN synthetic-4 d0"] == [("reason", None, ["quotation_not_in_source"])]
    assert failed["SYN synthetic-5 d0"] == [("chip", 1, ["quotation_not_in_source"])]
    assert failed["SYN synthetic-6 d0"] == [("chip", 0, ["quotation_not_in_source"])]
    seventh = report["rows"][6]
    assert [u["name"] for u in seventh["unrecorded_tool_calls"] if not u["served_from_trace"]] == ["get_financial_fact"]
    assert seventh["failed"] and "repair lookup" in seventh["unexplained_because"]
    assert report["rows"][1]["other_reason"] == ["Missing citation envelope"]
    status = print_report(report)
    assert status == 3
    print("self-test passed: F-withheld on the answer, a not-disclosed reason, a not-disclosed chip and an"
          " answer-path chip (with chip indexes), other reason, and UNEXPLAINED (incl. an unserved repair"
          " lookup) classified; UNEXPLAINED is loud and exit 3")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("runs", nargs="*")
    parser.add_argument("--out", default="f-attribution.json")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        report = self_test()
        json.dump(report, open(args.out, "w"), indent=1, ensure_ascii=False)
        return 0
    report = analyse(args.runs)
    json.dump(report, open(args.out, "w"), indent=1, ensure_ascii=False)
    return print_report(report)


if __name__ == "__main__":
    sys.exit(main())
