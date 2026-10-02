"""Offline replay: the Copilot CITATION scorer before and after this branch, against Copilot's own
publication verdict, over the retained copilot-eval artifacts. Also scans every section label.

Read-only. No network, no provider calls. Imports the backend of the checkout this file sits in.

Usage (keys unset; hermetic dummy Settings as tests/conftest.py):
    env -u OPENAI_API_KEY -u DEEPSEEK_API_KEY -u OPENAI_BASE_URL \\
        python replay_scorer_alignment.py <dir holding copilot-<run>/copilot-eval.json> <out.json> [run ...]
Without run ids it replays RUNS, the 15 retained copilot-eval runs the close-out research used.

Columns per published text citation, against ``normalize_for_match(row.inputs.source_text)`` (the
exact source the runner scores, ``copilot_runner.py`` -> ``score_copilot_answer(filing_text=...)``):

* ``old``     - main 06ad809a's scorer, re-implemented below (``verify_excerpt_in_text``, no label
                rule). The reproduction check proves it matches every retained score.
* ``new``     - this branch's ``evals.copilot_scorers.score_citation_faithfulness`` itself.
* ``product`` - this branch's ``copilot_service._verify_citations`` itself (whole excerpt AND
                ``section_label_is_quoted``), called with an empty ``referenced`` set so it never raises.

Withheld rows publish nothing; their declared citations are rebuilt from the retained candidate
deltas with the product's own parser and scored the same way. The label scan covers every
``section``/``section_ref`` string in the artifacts plus the withheld rows' declared labels.
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-long-enough-123")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_mock_stripe_key_12345")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_mock_stripe_webhook_12345")
os.environ.setdefault("SKIP_REDIS_INIT", "true")
for _k in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY"):
    os.environ.pop(_k, None)
# openai_service constructs (never calls) a client at import: the conftest dummy key and a discard-port
# base URL, so even an accidental call could not leave this machine. No request is made here.
os.environ["OPENAI_API_KEY"] = "sk-test-key-for-mocking"
os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:9/v1"

BACKEND = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "backend"))
sys.path.insert(0, BACKEND)

from app.services import copilot_service as cs  # noqa: E402
from app.services import provenance_service as prov  # noqa: E402
from evals import copilot_scorers as sc  # noqa: E402

FILING = SimpleNamespace(document_url="https://www.sec.gov/Archives/edgar/data/0/0/doc.htm", sec_url=None)
# Independently written: main's section_ref set, and decision F's set.
MAIN_LABEL_MARKS = '"“”'
F_MARKS = '"＂“”„‟'
RUNS = ("36777581481", "36798834277", "36800236360", "36809122540", "36870677818", "36963789557", "36964503116",
        "36965303868", "36994753645", "36997852891", "37000691174", "37003942265", "37004589548", "37005114216",
        "37005546506")
COUNTS = ("scored_rows", "withheld_rows", "text_citations", "xbrl_citations", "old_unverified", "new_unverified",
          "product_unverified", "verdict_changes")


def old_score_citation_faithfulness(citations, normalized_source):
    """Main 06ad809a's scorer verbatim, except the name."""
    text_citations = [c for c in citations if not sc._is_xbrl_citation(c)]
    if not text_citations:
        return 1.0, []
    unverified = []
    for cite in text_citations:
        excerpt = str(cite.get("excerpt") or "")
        if not prov.verify_excerpt_in_text(excerpt, normalized_source):
            unverified.append(excerpt)
    verified = len(text_citations) - len(unverified)
    return round(verified / len(text_citations), 4), unverified


def verdicts(excerpt, section, norm):
    published = {"excerpt": excerpt, "section_ref": section}
    declared = {"n": 1, "excerpt": excerpt, "section": section}
    return {
        "old": not old_score_citation_faithfulness([published], norm)[1],
        "new": not sc.score_citation_faithfulness([published], norm)[1],
        "product": cs._verify_citations([declared], FILING, norm, set())["1"]["verified"],
    }


def declared_from_candidate(row):
    text = "".join(row.get("tool_trace", {}).get("candidate_deltas") or [])
    if cs._CITATIONS_SENTINEL not in text:
        return None, "no citation sentinel"
    _prose, _, tail = text.partition(cs._CITATIONS_SENTINEL)
    try:
        data, _ = cs._parse_citations(tail)
    except Exception as exc:  # noqa: BLE001 - the parser's rejection is the finding
        return None, f"parse rejected: {exc}"
    return data, None


def _walk_labels(node, out):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("section", "section_ref") and isinstance(value, str):
                out[value] += 1
            _walk_labels(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk_labels(value, out)


def main(artifacts_dir, out_path, runs):
    report = {"artifacts": [], "changes": [], "product_disagreements": [], "reproduction_mismatches": [],
              "withheld_rows": []}
    tot = collections.Counter()
    transitions = collections.Counter()
    structured_labels = collections.Counter()
    declared_labels = collections.Counter()
    for run in runs:
        raw = open(os.path.join(artifacts_dir, f"copilot-{run}", "copilot-eval.json"), "rb").read()
        rep = json.loads(raw)
        _walk_labels(rep, structured_labels)
        per = collections.Counter()
        for row in rep["results"]:
            norm = prov.normalize_for_match(row.get("inputs", {}).get("source_text") or "")
            rid = f"{row['ticker']}/{row['question_id']}/r{row['run_index']}"
            if "error" in row:
                per["withheld_rows"] += 1
                decls, why = declared_from_candidate(row)
                entry = {"run_id": run, "row": rid, "error": row["error"], "declared": []}
                if why:
                    entry["note"] = why
                for decl in decls or []:
                    sec = decl.get("section") or decl.get("section_ref")
                    declared_labels[sec] += 1
                    entry["declared"].append({"n": decl["n"], "excerpt": decl["excerpt"], "section": sec,
                                              **verdicts(decl["excerpt"], sec, norm)})
                report["withheld_rows"].append(entry)
                continue
            per["scored_rows"] += 1
            cites = row.get("citations") or []
            text = [c for c in cites if not sc._is_xbrl_citation(c)]
            per["text_citations"] += len(text)
            per["xbrl_citations"] += len(cites) - len(text)
            replayed = old_score_citation_faithfulness(cites, norm)
            retained = (row["score"]["citation_faithfulness"], row["score"]["unverified_excerpts"])
            if replayed != retained:
                report["reproduction_mismatches"].append({"run_id": run, "row": rid, "replayed": replayed,
                                                          "retained": retained})
            for c in text:
                v = verdicts(c.get("excerpt"), c.get("section_ref"), norm)
                for k in ("old", "new", "product"):
                    per[f"{k}_unverified"] += not v[k]
                transitions[f"old {v['old']} -> new {v['new']} (product {v['product']})"] += 1
                if v["old"] != v["new"]:
                    per["verdict_changes"] += 1
                    report["changes"].append({"run_id": run, "row": rid, "excerpt": c.get("excerpt"),
                                              "section_ref": c.get("section_ref"), **v})
                if v["new"] != v["product"]:
                    report["product_disagreements"].append({"run_id": run, "row": rid, **v})
        report["artifacts"].append({"run_id": run, "artifact_sha256": hashlib.sha256(raw).hexdigest(),
                                    "source_sha": rep.get("source_sha"), "rows": len(rep["results"]),
                                    **{k: per[k] for k in COUNTS}})
        tot.update(per)
    declared = [d for w in report["withheld_rows"] for d in w["declared"]]
    all_labels = {lab for lab in set(structured_labels) | set(declared_labels) if isinstance(lab, str)}
    report["totals"] = {
        "artifacts": len(runs), **{k: tot[k] for k in COUNTS},
        "transitions": dict(transitions),
        "withheld_declared_text_citations": len(declared),
        "withheld_declared_old_new_diffs": sum(d["old"] != d["new"] for d in declared),
        "withheld_declared_new_product_diffs": sum(d["new"] != d["product"] for d in declared),
        "withheld_parser_rejections": sum("note" in w for w in report["withheld_rows"]),
    }
    report["label_scan"] = {
        "structured_occurrences": sum(structured_labels.values()),
        "structured_distinct": len(structured_labels),
        "withheld_declared_occurrences": sum(declared_labels.values()),
        "withheld_declared_distinct": len(declared_labels),
        "distinct_with_main_marks": sorted(lab for lab in all_labels if any(m in lab for m in MAIN_LABEL_MARKS)),
        "distinct_with_f_marks": sorted(lab for lab in all_labels if any(m in lab for m in F_MARKS)),
        "distinct_quoted_per_branch_predicate": sorted(lab for lab in all_labels if cs.section_label_is_quoted(lab)),
        "non_ascii_chars": sorted({f"U+{ord(ch):04X}" for lab in all_labels for ch in lab if ord(ch) > 127}),
        "structured_labels": dict(structured_labels.most_common()),
        "withheld_declared_labels": {str(k): v for k, v in declared_labels.most_common()},
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"totals": report["totals"], "changes": len(report["changes"]),
                      "product_disagreements": len(report["product_disagreements"]),
                      "reproduction_mismatches": len(report["reproduction_mismatches"]),
                      "label_scan": {k: v for k, v in report["label_scan"].items() if not k.endswith("_labels")}},
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], tuple(sys.argv[3:]) or RUNS)
