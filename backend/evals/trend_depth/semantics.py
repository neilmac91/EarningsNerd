"""Semantic audit of verified claims: is each number said about the metric and period it matched?

    cd backend && python -m evals.trend_depth.semantics --label eval-v1 --systems deepseek-flash,gemini-3.8-flash,claude-sonnet-5-5

The gate matches a printed number to a cited value; it does not read the words around the number. A claim
"revenue grew 8.3%" that cites an 8.3% growth in cash would pass it. This audit measures how often that
happens: for every verified claim of an analysis, an auditor from another model family sees the sentence,
the claim, and the label and period of the value (or derivation) it matched, and marks the claim
``consistent`` or ``mismatch`` (the sentence attributes the number to a different metric, period or
basis). Results land in ``runs/<label>/semantics/<system>/<TICKER>.json``; ``--auditor <arm>`` audits every
system with that one model instead, in ``runs/<label>/semantics-by-<arm>/``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Optional

from evals.trend_depth import factcheck
from evals.trend_depth.causes import _auditor, audit_call, earlier_audit, reuse_audit
from evals.trend_depth.companies import eval_companies
from evals.trend_depth.generate import RUNS, load_pack, sentences_of
from evals.trend_depth.records import output_sha256, unsettled, write_json

SYSTEM = """You check that each number in a financial analysis is said about the right thing. For each numbered
item you get a sentence, one number from it, and what that number was matched to in the evidence (the
metric label and period of a cited value, or a calculation from cited values). Mark the item:
- "consistent": the sentence says the number is that metric for that period (or that calculation), allowing
  ordinary paraphrase ("sales" for revenue, "fell 10.3%" for a growth of -10.3%);
- "mismatch": the sentence attributes the number to a different metric, period, segment or basis than the
  match (for example it calls a cash-flow growth "revenue growth", or a FY2024 value "FY2025").
Return one JSON object only: {"items": [{"n": 1, "label": "consistent", "reason": "<= 20 words"}]}"""


def _describe(match: str, ids: list[str], pack: dict[str, Any]) -> str:
    parts = []
    for vid in ids:
        value = pack["values"].get(vid)
        if value:
            parts.append(f"{vid} = {value['label']}, {value['period']}")
        else:
            passage = next((p for p in pack["passages"] if p["id"] == vid), None)
            if passage:
                parts.append(f"{vid} = a figure in a {passage['fiscal_year']} 10-K passage")
            else:
                flag = next((f for f in pack.get("red_flags", []) if f["id"] == vid), None)
                parts.append(f"{vid} = red-flag text: {flag['detail'][:120]}" if flag else vid)
    return f"{match}: " + "; ".join(parts)


def classify_flag(item: dict[str, Any], sentences: list[dict[str, Any]], pack: dict[str, Any]) -> str:
    """Why the auditor's ``mismatch`` may not be an error, read deterministically from the gate:

    - ``bound``: the number is a bound ("below 1.0x", "at least 10%") that the cited value satisfies; the
      auditor sees only the value it was checked against, not that the claim is an inequality;
    - ``ambiguous``: two or more cited values with different labels match the number, so the one the gate
      reported may not be the one the sentence means;
    - ``substantive``: neither, so the sentence most likely gives the number the wrong metric, period or sign.
    """
    sentence = next((s for s in sentences if factcheck.CITATION_RE.sub("", s["text"]).strip() == item["sentence"]), None)
    if sentence is None:
        return "substantive"
    claim = next((c for c in factcheck.parse_claims(sentence["text"]) if c.text == item["claim"]), None)
    if claim is None:
        return "substantive"
    if claim.qualifier in ("at_least", "at_most"):
        return "bound"
    cited = [i for g in factcheck.CITATION_RE.findall(sentence["text"]) for i in factcheck.ID_RE.findall(g)]
    labels = {" + ".join(sorted(pack["values"][i]["label"] for i in c.ids if i in pack["values"])) or c.how
              for c in factcheck.candidates(cited, pack) if factcheck.matches(claim, c)}
    return "ambiguous" if len(labels) > 1 else "substantive"


async def audit(system: str, ticker: str, record: dict[str, Any], label: str, auditor: Optional[str] = None) -> None:
    out = RUNS / label / (f"semantics-by-{auditor}" if auditor else "semantics") / system / f"{ticker}.json"
    sha = output_sha256(record)
    earlier, spent = earlier_audit(out, sha)
    if earlier is not None:
        return
    pack = load_pack(ticker, system)
    result = factcheck.check(sentences_of(record["output"]), pack)
    items = []
    for detail in result["detail"]:
        for claim in detail["claims"]:
            if claim["status"] == "verified" and claim.get("ids"):
                items.append({"sentence": factcheck.CITATION_RE.sub("", detail["text"]).strip(), "claim": claim["claim"],
                              "match": _describe(claim.get("matched", ""), claim["ids"], pack)})
    auditor = auditor or _auditor(system)
    record_out: dict[str, Any] = {"system": system, "ticker": ticker, "split": pack["split"], "auditor": auditor, "items": [],
                                  "output_sha256": sha}
    if spent:
        record_out["prior_cost_usd"] = spent
    if items:  # an analysis with no verified number needs no auditor call
        user = "\n\n".join(f"[{n}] Sentence: {i['sentence']}\n    Number: {i['claim']}\n    Matched to: {i['match']}"
                           for n, i in enumerate(items, start=1)) + "\n\nMark every item now."
        answered = await audit_call(auditor, SYSTEM, user, f"semantics/{auditor}/{system}/{ticker}", record_out, out, "items", len(items))
        if answered is None:
            return
        response, labels = answered
        record_out.update({
            "cost_usd": response.cost_usd, "backend": response.backend, "input_tokens": response.input_tokens,
            "cached_input_tokens": response.cached_input_tokens, "output_tokens": response.output_tokens,
            "items": [{**item, "label": (labels.get(n) or {}).get("label", "missing"), "reason": (labels.get(n) or {}).get("reason", "")}
                      for n, item in enumerate(items, start=1)],
        })
    write_json(out, record_out)
    counts = {k: sum(1 for i in record_out["items"] if i["label"] == k) for k in ("consistent", "mismatch", "missing")}
    print(f"semantics {system:20} {ticker:5} {counts} auditor={auditor}", flush=True)


async def run(label: str, systems: list[str], tickers: list[str], concurrency: int, auditor: Optional[str] = None) -> None:
    semaphore = asyncio.Semaphore(concurrency)

    async def one(system: str, ticker: str) -> None:
        path = RUNS / label / system / f"{ticker}.json"
        record = json.loads(path.read_text()) if path.exists() else None
        why = unsettled(record)
        if why or not record.get("generation_ok"):  # audited once its output is final; a model's failure has none
            if why and path.exists():
                print(f"semantics {system} {ticker} skipped: {why}", flush=True)
            return
        reuse_audit(label, "semantics", system, ticker, auditor, output_sha256(record))
        async with semaphore:
            try:
                await audit(system, ticker, record, label, auditor)
            except Exception as exc:  # noqa: BLE001 - an audit failure is reported, never a verdict
                print(f"semantics {system} {ticker} failed: {exc}", flush=True)

    await asyncio.gather(*(one(system, ticker) for system in systems for ticker in tickers))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--label", required=True)
    parser.add_argument("--systems", required=True)
    parser.add_argument("--split", default="all", choices=("dev", "holdout", "all"))
    parser.add_argument("--tickers", default="")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--auditor", default="", help="audit every system with this one arm")
    args = parser.parse_args()
    tickers = args.tickers.split(",") if args.tickers else [c.ticker for c in eval_companies(None if args.split == "all" else args.split)]
    asyncio.run(run(args.label, args.systems.split(","), tickers, args.concurrency, args.auditor or None))


if __name__ == "__main__":
    main()
