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
from evals.trend_depth.records import (
    excerpt, labelled, output_sha256, own_spend, read_same_output, text_sha256, unsettled, write_json,
)

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


class NoLabels(ValueError):
    """The auditor's reply left an item unlabelled; it is written as a failed audit, so the next run retries it."""


def labels_or_raise(result: Any, entries: Any, expected: int) -> dict[int, dict[str, Any]]:
    """Every requested item's label, or NoLabels. A partial reply is not a finished audit: the report counts each
    verified claim of an audited analysis in its denominator, so an item the auditor skipped would read as checked."""
    labels = labelled(entries, expected)
    if len(labels) < expected:
        raise NoLabels(f"the auditor's reply labelled {len(labels)} of {expected} items (${result.cost_usd:.4f} spent): "
                       f"{result.text[:160]!r}")
    return labels


def reuse_audit(label: str, kind: str, system: str, ticker: str, auditor: Optional[str], sha: str) -> None:
    """Copy an audit already made by the same auditor between the default folder (``kind``) and the same-auditor
    folder (``kind-by-<auditor>``), in whichever direction it is wanted, so the same audit is never paid for twice.
    Only a finished audit of the output whose hash is ``sha`` is copied, marked ``copied_from``. It replaces a
    failed audit, or one of an earlier output, that the target held, and carries what the target's folder had
    spent there (``records.own_spend``), so each folder's records count each paid call once."""
    default_auditor = _auditor(system)
    default = RUNS / label / kind / system / f"{ticker}.json"
    same = RUNS / label / f"{kind}-by-{default_auditor}" / system / f"{ticker}.json"
    if auditor and auditor != default_auditor:
        return
    source, target = (same, default) if auditor is None else (default, same)
    if not source.exists():
        return
    record = json.loads(source.read_text())
    if ("error" in record or not read_same_output(record, "output_sha256", sha)
            or record.get("auditor") not in (default_auditor, None)):  # trust the record, not the folder it sits in
        return
    held = json.loads(target.read_text()) if target.exists() else None
    if held is not None and "error" not in held and read_same_output(held, "output_sha256", sha):
        return  # already a finished audit of this output
    copy = {**record, "copied_from": source.parent.parent.name, "prior_cost_usd": own_spend(held) if held else 0.0}
    write_json(target, copy)


def earlier_audit(out_path: Any, sha: str) -> tuple[Optional[dict[str, Any]], float]:
    """The finished audit of this output at ``out_path``, else None and what the audits it replaces cost: a failed
    one (retried), or one of an output that has since changed (redone)."""
    if not out_path.exists():
        return None, 0.0
    earlier = json.loads(out_path.read_text())
    if "error" not in earlier and read_same_output(earlier, "output_sha256", sha):
        return earlier, 0.0
    return None, own_spend(earlier)


def write_failed(record: dict[str, Any], result: Any, exc: Exception, out_path: Any) -> None:
    """Record an audit call that was paid for but left an item unlabelled, with its reply and cost, so the next run
    retries it knowing what it already spent."""
    record.update({"error": f"{type(exc).__name__}: {exc}"[:400], "raw": excerpt(result.text), "cost_usd": result.cost_usd,
                   "backend": result.backend, "input_tokens": result.input_tokens,
                   "cached_input_tokens": result.cached_input_tokens, "output_tokens": result.output_tokens})
    write_json(out_path, record)


async def audit_call(auditor: str, system_prompt: str, user: str, tag: str, record: dict[str, Any], out_path: Any,
                     key: str, expected: int) -> Optional[tuple[Any, dict[int, dict[str, Any]]]]:
    """The auditor's call and its labels. A refusal is written as the outcome (None is returned); a reply that
    stopped at its cap or left any item unlabelled is written as a failed audit and raised, so the next run retries it."""
    try:
        result = await call(ARMS[auditor], system_prompt, user, max_tokens=16000, tag=tag)
    except Exception as exc:
        if getattr(exc, "result", None) is not None:  # a truncated reply was paid for
            write_failed(record, exc.result, exc, out_path)
        raise
    if result.meta.get("stop_reason") == "refusal":
        record.update({"refused": True, "cost_usd": result.cost_usd, "backend": result.backend})  # recorded once
        write_json(out_path, record)
        return None
    try:
        labels = labels_or_raise(result, (parse_json_object(result.text) or {}).get(key), expected)
    except NoLabels as exc:
        write_failed(record, result, exc, out_path)
        raise
    return result, labels


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
                auditor: Optional[str] = None, sha: str = "") -> dict[str, Any]:
    earlier, spent = earlier_audit(out_path, sha)
    if earlier is not None:
        return earlier
    items = cause_items(sentences, pack)
    record: dict[str, Any] = {"system": system, "ticker": ticker, "split": pack["split"], "claims": len(items),
                              "output_sha256": sha}
    if spent:
        record["prior_cost_usd"] = spent
    if items:
        auditor = auditor or _auditor(system)
        record["auditor"] = auditor
        user = "\n\n".join(
            f"[{n}] Sentence: {item['sentence']}\n" + "\n".join(f"  Passage {p['id']} ({p['filing']}): {p['text']}" for p in item["passages"])
            for n, item in enumerate(items, start=1)
        ) + "\n\nLabel every claim now."
        answered = await audit_call(auditor, SYSTEM, user, f"causes/{auditor}/{system}/{ticker}", record, out_path, "claims", len(items))
        if answered is None:
            return record
        result, labels = answered
        record["items"] = [{**item, "label": (labels.get(n) or {}).get("label", "missing"), "reason": (labels.get(n) or {}).get("reason", "")}
                           for n, item in enumerate(items, start=1)]
        record.update({"cost_usd": result.cost_usd, "backend": result.backend, "input_tokens": result.input_tokens,
                       "cached_input_tokens": result.cached_input_tokens, "output_tokens": result.output_tokens})
    write_json(out_path, record)
    counts = {k: sum(1 for i in record.get("items", []) if i["label"] == k) for k in ("supported", "partial", "unsupported")}
    print(f"causes {system:20} {ticker:5} {counts} auditor={record.get('auditor')}", flush=True)
    return record


async def run(label: str, systems: list[str], tickers: list[str], concurrency: int, auditor: Optional[str] = None) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    folder = f"causes-by-{auditor}" if auditor else "causes"

    async def one(system: str, ticker: str) -> None:
        async with semaphore:
            out = RUNS / label / folder / system / f"{ticker}.json"
            if system == "gold":
                from evals.trend_depth.gold import GOLD
                path = GOLD / f"{ticker}.md"
                if not path.exists():
                    return
                text = path.read_text()
                reuse_audit(label, "causes", system, ticker, auditor, text_sha256(text))
                try:
                    await audit(system, ticker, factcheck.sentences_from_markdown(text), pack_with_extras(ticker), out, auditor,
                                text_sha256(text))
                except Exception as exc:  # noqa: BLE001 - an audit failure is reported, never a verdict, and never cancels the rest
                    print(f"causes {system} {ticker} failed: {exc}", flush=True)
                return
            path = RUNS / label / system / f"{ticker}.json"
            record = json.loads(path.read_text()) if path.exists() else None
            why = unsettled(record)
            if why or not record.get("generation_ok"):  # audited once its output is final; a model's failure has none
                if why and path.exists():
                    print(f"causes {system} {ticker} skipped: {why}", flush=True)
                return
            reuse_audit(label, "causes", system, ticker, auditor, output_sha256(record))
            try:
                await audit(system, ticker, sentences_of(record["output"]), load_pack(ticker, system), out, auditor,
                            output_sha256(record))
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
