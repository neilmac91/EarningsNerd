"""Pairwise, position-swapped judging of analyses by a model from neither output's family.

    cd backend && python -m evals.trend_depth.judge --label eval-v1 --systems current,deepseek-flash,gemini-3.8-flash,claude-sonnet-5-5 --split all

For every company and every pair of systems, the judge reads both analyses in the common reader format
(``readable.py``: sections, numbered citations, a sources list quoting each cited filing passage) plus the
company's metrics table, once as (A, B) and once as (B, A). A verdict counts only when both orders agree;
otherwise the pair is a tie and the disagreement is reported as position bias.

Judge choice excludes the families of both outputs (``current`` is the deepseek family, since deepseek-flash
selects its sentences). In order of preference: Claude Opus 5.5 judges every pair without a Claude output,
DeepSeek V4 Pro every remaining pair without a DeepSeek output, and Gemini 3.8 Flash the pairs of a Claude
output with a DeepSeek one. ``--second-judge`` adds the next eligible judge on every pair, for agreement.

Gemma 4 31B (Google's open model, on the Gemini API's free tier) is the last neutral judge, used when the
Gemini 3.8 Flash quota is spent: ``--exclude-judges gemini-3.8-flash``. When no judge outside both families is
available (``--exclude-judges gemini-3.8-flash,gemma-4-31b``), the pair gets a consensus panel instead: one judge
from each output's family. Each may favour its own family, so the report counts a consensus verdict only
when both judges agree on it, and prefers a neutral judge's verdict wherever one exists.
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
from typing import Any, Optional

from evals.trend_depth import readable
from evals.trend_depth.companies import eval_companies
from evals.trend_depth.generate import RUNS, load_pack
from evals.trend_depth.providers import ARMS, call, canonical_pair, parse_json_object
from evals.trend_depth.render import fmt

JUDGE_ORDER = ("claude-opus-5-5", "deepseek-v4-pro", "gemini-3.8-flash", "gemma-4-31b")  # V4 Pro: ADR-0008 addendum
CRITERIA = ("depth", "grounding", "coverage", "clarity", "calibration")

RUBRIC = """You are an experienced equity analyst reviewing two drafts of the "trend analysis" that sits above a
company's multi-year financial metrics table on a research website for self-directed investors. Readers can
already see every number in the table. Judge which draft serves that reader better.

Score each criterion as "A", "B" or "tie":
- depth: explains what the table cannot show on its own: what drove growth (segments, products, cost
  lines), why margins and cash conversion moved, inflection points with their causes, comparison with the
  company's own history and its peers. Restating table values without interpretation earns nothing.
- grounding: every factual and causal statement is supported by the draft's own cited sources. Check each
  causal claim against the quoted passage it cites; a cause the passage does not state, a misread figure,
  or an interpretation presented as fact counts against the draft. A draft that says less but is fully
  supported beats one that says more with unsupported claims.
- coverage: addresses, where the evidence allows: the shape of the period and its inflections, growth
  drivers and operating leverage, margin drivers, cash conversion, balance sheet and capital allocation,
  ranked red flags, and concrete things to watch with numeric thresholds.
- clarity: plain, specific, well-organised prose a non-professional investor can follow; no padding,
  no repetition, no jargon without need.
- calibration: judgements are proportionate and visibly separated from facts; uncertainty and data
  problems are disclosed; no hype, no advice, no forecasts beyond what the company itself guided.

Then give an overall preference ("A", "B" or "tie") weighing grounding first, depth second, then the rest,
the strength of the preference ("slight", "clear" or "strong"), and a rationale of at most 80 words.
Do not prefer a draft for being longer. Do not favour a format for its own sake.

Return one JSON object only:
{"criteria": {"depth": "A", "grounding": "B", "coverage": "A", "clarity": "tie", "calibration": "B"},
 "overall": "A", "strength": "clear", "rationale": "..."}"""


def _metrics_table(pack: dict[str, Any]) -> str:
    rows: dict[str, list[str]] = {}
    for vid, value in pack["values"].items():
        if vid.startswith("F") and "CAGR" not in value["label"]:
            rows.setdefault(value["label"], []).append(f"{value['period']} {fmt(value['value'], value['unit'])}")
    return "\n".join(f"- {label}: " + " · ".join(cells) for label, cells in rows.items())


def _family(system: str) -> str:
    return "deepseek" if system == "current" else ARMS[system].family


def judge_for(a: str, b: str, order: tuple[str, ...] = JUDGE_ORDER) -> Optional[str]:
    excluded = {_family(a), _family(b)}
    return next((name for name in order if ARMS[name].family not in excluded), None)


def panel_for(a: str, b: str, order: tuple[str, ...] = JUDGE_ORDER, second_judge: bool = False) -> list[str]:
    """The judges for a pair: a neutral judge (two with ``second_judge``), else one from each output's family."""
    excluded = {_family(a), _family(b)}
    neutral = [name for name in order if ARMS[name].family not in excluded]
    if neutral:
        return neutral[: 2 if second_judge else 1]
    own = [next((name for name in order if ARMS[name].family == family), None) for family in sorted(excluded)]
    return [name for name in own if name] if len(excluded) == 2 and all(own) else []


def _load(label: str, system: str, ticker: str) -> Optional[dict[str, Any]]:
    path = RUNS / label / system / f"{ticker}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def reader_text(record: dict[str, Any], pack: dict[str, Any]) -> Optional[str]:
    if not record or not record.get("generation_ok"):
        return None
    if record["arm"] == "current":
        return readable.current_markdown(record)
    return readable.proposed_markdown(record["output"], pack)


def _user(pack: dict[str, Any], text_a: str, text_b: str) -> str:
    return (
        f"Company: {pack['company_name']} ({pack['ticker']}), annual window {pack['window']}, profile {pack['profile']}.\n\n"
        f"Metrics table the reader sees:\n{_metrics_table(pack)}\n\n"
        f"===== DRAFT A =====\n{text_a}\n\n===== DRAFT B =====\n{text_b}\n\n"
        "Judge the drafts now. Return the JSON object only."
    )


class NoVerdict(ValueError):
    """The judge's reply held no overall verdict; the pair is retried, never counted as a tie."""


async def _one_order(judge: str, pack: dict[str, Any], text_a: str, text_b: str, tag: str = "") -> dict[str, Any]:
    # 16,000 leaves room for a thinking judge (Gemma 4 has spent 2,700 tokens thinking and then stopped before its JSON).
    result = await call(ARMS[judge], RUBRIC, _user(pack, text_a, text_b), max_tokens=16000, tag=tag)
    verdict = parse_json_object(result.text) or {}
    if str(verdict.get("overall", "")).strip().upper() not in ("A", "B", "TIE"):
        raise NoVerdict(f"{judge} returned no overall verdict (${result.cost_usd:.4f} spent): {result.text[:160]!r}")
    return {"verdict": verdict, "cost_usd": result.cost_usd, "latency_s": result.latency_s, "backend": result.backend,
            "input_tokens": result.input_tokens, "cached_input_tokens": result.cached_input_tokens,
            "output_tokens": result.output_tokens, "reasoning_tokens": result.reasoning_tokens, "meta": result.meta,
            "raw": result.text[:4000]}





def _resolve(first: dict[str, Any], second: dict[str, Any], x: str, y: str) -> dict[str, Any]:
    """first judged (A=x, B=y); second judged (A=y, B=x). Map both to system names and reconcile."""
    def name(letter: Any, a: str, b: str) -> str:
        return {"A": a, "B": b}.get(str(letter).strip().upper(), "tie")

    out: dict[str, Any] = {}
    for key in (*CRITERIA, "overall"):
        v1 = name((first["verdict"].get("criteria") or {}).get(key) if key != "overall" else first["verdict"].get("overall"), x, y)
        v2 = name((second["verdict"].get("criteria") or {}).get(key) if key != "overall" else second["verdict"].get("overall"), y, x)
        out[key] = {"order1": v1, "order2": v2, "agreed": v1 == v2, "final": v1 if v1 == v2 else "tie"}
    return out


async def judge_pair(label: str, ticker: str, x: str, y: str, judge: str, semaphore: asyncio.Semaphore) -> Optional[dict[str, Any]]:
    out_path = RUNS / label / "judge" / judge / f"{ticker}__{x}__{y}.json"
    if out_path.exists():
        cached = json.loads(out_path.read_text())
        if "error" not in cached:  # a judge call that failed is retried by the next run
            return cached
    pack = load_pack(ticker)
    rx, ry = _load(label, x, ticker), _load(label, y, ticker)
    if rx is None or ry is None or "error" in rx or "error" in ry:
        # Not generated yet (or a provider error, retried by generate): judge it once both outputs exist.
        print(f"judge {judge:18} {ticker:5} {x} vs {y}: skipped, an output is missing", flush=True)
        return None
    tx, ty = reader_text(rx, pack), reader_text(ry, pack)
    record: dict[str, Any] = {"ticker": ticker, "split": pack["split"], "x": x, "y": y, "judge": judge}
    if tx is None or ty is None:  # the model itself failed to produce an analysis: the other side wins
        record["forfeit"] = x if tx is None and ty is not None else y if ty is None and tx is not None else "both"
    else:
        tag = f"{label}/judge/{judge}/{ticker}/{x}__{y}"
        first = second = None
        async with semaphore:
            try:
                first = await _one_order(judge, pack, tx, ty, tag)
                second = await _one_order(judge, pack, ty, tx, tag)
            except Exception as exc:  # noqa: BLE001 - a judge failure is recorded with what it cost, never a verdict
                record["error"] = f"{type(exc).__name__}: {exc}"[:400]
                record["orders"] = [o for o in (first, second) if o]
                record["cost_usd"] = round(sum(o["cost_usd"] for o in record["orders"]), 6)
        if first and second:
            record["orders"] = [first, second]
            record["result"] = _resolve(first, second, x, y)
            record["cost_usd"] = round(first["cost_usd"] + second["cost_usd"], 6)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=1))
    overall = (record.get("result") or {}).get("overall", {})
    print(f"judge {judge:18} {ticker:5} {x} vs {y}: {overall.get('order1')} / {overall.get('order2')} -> "
          f"{overall.get('final')} {record.get('forfeit', '')}{record.get('error', '')}", flush=True)
    return record


async def run(label: str, systems: list[str], tickers: list[str], concurrency: int, second_judge: bool,
              exclude: tuple[str, ...] = ()) -> None:
    semaphores = {name: asyncio.Semaphore(concurrency) for name in JUDGE_ORDER}
    order = tuple(j for j in JUDGE_ORDER if j not in exclude)
    jobs = []
    for x, y in (canonical_pair(a, b) for a, b in itertools.combinations(systems, 2)):
        for judge in panel_for(x, y, order, second_judge):
            for ticker in tickers:
                jobs.append(judge_pair(label, ticker, x, y, judge, semaphores[judge]))
    await asyncio.gather(*jobs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--label", required=True)
    parser.add_argument("--systems", required=True)
    parser.add_argument("--split", default="all", choices=("dev", "holdout", "all"))
    parser.add_argument("--tickers", default="")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--second-judge", action="store_true")
    parser.add_argument("--exclude-judges", default="", help="judges to leave out, e.g. one whose quota is spent")
    args = parser.parse_args()
    tickers = args.tickers.split(",") if args.tickers else [
        c.ticker for c in eval_companies(None if args.split == "all" else args.split)
    ]
    exclude = tuple(j for j in args.exclude_judges.split(",") if j)
    asyncio.run(run(args.label, args.systems.split(","), tickers, args.concurrency, args.second_judge, exclude))


if __name__ == "__main__":
    main()
