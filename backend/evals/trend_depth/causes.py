"""Causal-support audit: does each cited filing passage actually state the cause a sentence gives?

    cd backend && python -m evals.trend_depth.causes --label eval-v1 --systems deepseek-flash,gemini-3.8-flash,claude-sonnet-5-5

The fact-check gate proves a cause sentence cites a passage and that its numbers reconcile; it cannot tell
whether the passage says what the sentence claims. Here a model from a different family than the
generator (the judge order in ``judge.py``) reads every cause sentence of one analysis with the full text
of the passages it cites, and labels each sentence ``supported`` (the passage states this cause),
``partial`` (the passage supports part of the claim, or a weaker version) or ``unsupported``.
Results land in ``runs/<label>/causes/<system>/<TICKER>.json`` and the report reads them.

``--auditor <arm>`` instead audits every system with that one model and writes to
``runs/<label>/causes-by-<arm>/``, so systems can be compared under the same auditor (one of them is then
audited by its own family, which the report says).
"""
from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Optional

from evals.trend_depth import factcheck
from evals.trend_depth.companies import eval_companies
from evals.trend_depth.generate import RUNS, load_pack, sentences_of
from evals.trend_depth.gold import pack_with_extras
from evals.trend_depth.judge import JUDGE_ORDER, _family
from evals.trend_depth.providers import ARMS, call, parse_json_object

SYSTEM = """You audit financial analysis for faithfulness to its sources. For each numbered claim you get the
sentence and the full text of the 10-K passages it cites. Decide whether the passages state the cause the
sentence gives:
- "supported": a cited passage states this cause for this movement (wording may differ);
- "partial": a passage supports part of the claim, a weaker version of it, or the right cause for a
  different period or line item;
- "unsupported": no cited passage states this cause.
Judge only causation; figures are checked elsewhere. Return one JSON object only:
{"claims": [{"n": 1, "label": "supported", "reason": "<= 25 words"}]}"""


def _auditor(system: str) -> Optional[str]:
    family = "gold" if system == "gold" else _family(system)
    return next((name for name in JUDGE_ORDER if ARMS[name].family != family), None)


def cause_items(sentences: list[dict[str, Any]], pack: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {p["id"]: p for p in pack["passages"]}
    items = []
    for sentence in sentences:
        if sentence.get("type") != "cause":
            continue
        refs = [r for g in factcheck.CITATION_RE.findall(sentence["text"]) for r in factcheck.ID_RE.findall(g)]
        cited = [by_id[r] for r in refs if r in by_id]
        items.append({"sentence": factcheck.CITATION_RE.sub("", sentence["text"]).strip(),
                      "passages": [{"id": p["id"], "filing": f"{p['fiscal_year']} 10-K {p.get('section', '')}", "text": p["text"]}
                                   for p in cited]})
    return items


async def audit(system: str, ticker: str, sentences: list[dict[str, Any]], pack: dict[str, Any], out_path: Any,
                auditor: Optional[str] = None) -> dict[str, Any]:
    if out_path.exists():
        return json.loads(out_path.read_text())
    items = cause_items(sentences, pack)
    record: dict[str, Any] = {"system": system, "ticker": ticker, "split": pack["split"], "claims": len(items)}
    if items:
        auditor = auditor or _auditor(system)
        record["auditor"] = auditor
        user = "\n\n".join(
            f"[{n}] Sentence: {item['sentence']}\n" + "\n".join(f"  Passage {p['id']} ({p['filing']}): {p['text']}" for p in item["passages"])
            for n, item in enumerate(items, start=1)
        ) + "\n\nLabel every claim now."
        result = await call(ARMS[auditor], SYSTEM, user, max_tokens=4000)
        verdict = parse_json_object(result.text) or {}
        labels = {int(c.get("n", 0)): c for c in verdict.get("claims", []) if isinstance(c, dict)}
        record["items"] = [{**item, "label": (labels.get(n) or {}).get("label", "missing"), "reason": (labels.get(n) or {}).get("reason", "")}
                           for n, item in enumerate(items, start=1)]
        record["cost_usd"] = result.cost_usd
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=1))
    counts = {k: sum(1 for i in record.get("items", []) if i["label"] == k) for k in ("supported", "partial", "unsupported")}
    print(f"causes {system:20} {ticker:5} {counts} auditor={record.get('auditor')}", flush=True)
    return record


async def run(label: str, systems: list[str], tickers: list[str], concurrency: int, auditor: Optional[str] = None) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    folder = f"causes-by-{auditor}" if auditor else "causes"

    async def one(system: str, ticker: str) -> None:
        async with semaphore:
            out = RUNS / label / folder / system / f"{ticker}.json"
            default = RUNS / label / "causes" / system / f"{ticker}.json"
            if auditor and auditor == _auditor(system) and default.exists() and not out.exists():
                out.parent.mkdir(parents=True, exist_ok=True)  # the default audit already used this auditor
                out.write_text(default.read_text())
            if system == "gold":
                from evals.trend_depth.gold import GOLD
                path = GOLD / f"{ticker}.md"
                if not path.exists():
                    return
                await audit(system, ticker, factcheck.sentences_from_markdown(path.read_text()), pack_with_extras(ticker), out, auditor)
                return
            path = RUNS / label / system / f"{ticker}.json"
            if not path.exists():
                return
            record = json.loads(path.read_text())
            if not record.get("generation_ok"):
                return
            try:
                await audit(system, ticker, sentences_of(record["output"]), load_pack(ticker), out, auditor)
            except Exception as exc:  # noqa: BLE001 - an audit failure is reported, never a verdict
                print(f"causes {system} {ticker} failed: {exc}", flush=True)

    await asyncio.gather(*(one(system, ticker) for system in systems for ticker in tickers))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--label", required=True)
    parser.add_argument("--systems", required=True, help="proposed arms, and/or 'gold' for the hand-written examples")
    parser.add_argument("--split", default="all", choices=("dev", "holdout", "all"))
    parser.add_argument("--tickers", default="")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--auditor", default="", help="audit every system with this one arm (a same-auditor comparison)")
    args = parser.parse_args()
    tickers = args.tickers.split(",") if args.tickers else [c.ticker for c in eval_companies(None if args.split == "all" else args.split)]
    asyncio.run(run(args.label, args.systems.split(","), tickers, args.concurrency, args.auditor or None))


if __name__ == "__main__":
    main()
