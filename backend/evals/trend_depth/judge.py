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
from evals.trend_depth.records import excerpt, output_sha256, read_same_output, unsettled, write_json
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
    """The judge's reply held no usable verdict; the pair is retried, never counted as a tie. ``order`` is the paid
    call, so its cost is recorded."""

    def __init__(self, message: str, order: dict[str, Any]) -> None:
        super().__init__(message)
        self.order = order


def _order(result: Any, verdict: dict[str, Any]) -> dict[str, Any]:
    return {"verdict": verdict, "cost_usd": result.cost_usd, "latency_s": result.latency_s, "backend": result.backend,
            "input_tokens": result.input_tokens, "cached_input_tokens": result.cached_input_tokens,
            "output_tokens": result.output_tokens, "reasoning_tokens": result.reasoning_tokens, "meta": result.meta,
            "raw": excerpt(result.text)}


def usable(order: Optional[dict[str, Any]]) -> bool:
    """A verdict on the overall question and on every criterion, each A, B or tie; anything less is retried, so a
    criterion the judge never gave is not counted as a tie."""
    verdict = (order or {}).get("verdict") or {}
    criteria = verdict.get("criteria")
    return (isinstance(criteria, dict)
            and all(str(value).strip().upper() in ("A", "B", "TIE")
                    for value in (verdict.get("overall", ""), *(criteria.get(key, "") for key in CRITERIA))))


async def _one_order(judge: str, pack: dict[str, Any], text_a: str, text_b: str, tag: str = "") -> dict[str, Any]:
    # 16,000 leaves room for a thinking judge. Gemma 4 once gave no verdict in 2,710 output tokens, under the cap
    # then in force; that record kept neither the reply's end nor its finish reason, which each order now keeps.
    try:
        result = await call(ARMS[judge], RUBRIC, _user(pack, text_a, text_b), max_tokens=16000, tag=tag)
    except Exception as exc:  # noqa: BLE001 - a truncated reply was paid for: carry it to the record
        if getattr(exc, "result", None) is not None:
            raise NoVerdict(str(exc), _order(exc.result, {})) from exc
        raise
    order = _order(result, parse_json_object(result.text) or {})
    if result.meta.get("stop_reason") == "refusal":
        order["refused"] = True  # the judge's own outcome: recorded once, never re-bought
        return order
    if not usable(order):
        raise NoVerdict(f"{judge} returned no usable verdict (${result.cost_usd:.4f} spent): {result.text[:160]!r}", order)
    return order


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
    rx, ry = _load(label, x, ticker), _load(label, y, ticker)
    for system, generation in ((x, rx), (y, ry)):
        why = unsettled(generation)
        if why:  # judged once both outputs are final, never against one that generate may still replace
            print(f"judge {judge:18} {ticker:5} {x} vs {y}: skipped, {system} has {why}", flush=True)
            return None
    shas = {"x_sha256": output_sha256(rx), "y_sha256": output_sha256(ry)}
    cached = json.loads(out_path.read_text()) if out_path.exists() else None
    current = cached is not None and all(read_same_output(cached, key, sha) for key, sha in shas.items())
    if current and "error" not in cached:  # a judge call that failed is retried by the next run
        return cached
    # Orders judged on drafts that have since changed are kept for their cost, never combined with new ones.
    superseded = [*(cached or {}).get("superseded", []), *([] if current else (cached or {}).get("orders", []))]
    # An order already judged and paid for, on these same drafts, is reused; only the missing one is bought.
    reuse = (cached or {}).get("orders", []) if current else []
    paid_first = reuse[0] if reuse and usable(reuse[0]) and reuse[0].get("position") != 2 else None
    pack = load_pack(ticker)  # what both drafts share (the company, its metrics table) from packs/
    tx, ty = reader_text(rx, load_pack(ticker, x)), reader_text(ry, load_pack(ticker, y))  # each its own sources
    record: dict[str, Any] = {"ticker": ticker, "split": pack["split"], "x": x, "y": y, "judge": judge, **shas}
    interrupted: Optional[BaseException] = None  # set before the forfeit branch, which sends no order to interrupt
    if tx is None or ty is None:  # the model itself failed to produce an analysis: the other side wins
        record["forfeit"] = x if tx is None and ty is not None else y if ty is None and tx is not None else "both"
    else:
        tag = f"{label}/judge/{judge}/{ticker}/{x}__{y}"
        # Unusable orders from earlier runs stay on the record, so its cost is the pair's whole cost.
        first, second, failed = paid_first, None, [o for o in reuse if o is not paid_first and not usable(o)]
        async with semaphore:
            try:
                if first is None:
                    first = await _one_order(judge, pack, tx, ty, tag)
                    first["position"] = 1
                    # On disk before order 2 is sent, so a run stopped during order 2 never buys order 1 again.
                    held = [first, *failed]
                    write_json(out_path, {**record, "orders": held, "error": "interrupted: order 2 had not returned",
                                          **({"superseded": superseded} if superseded else {}),
                                          "cost_usd": round(sum(o["cost_usd"] for o in [*held, *superseded]), 6)})
                if not first.get("refused"):
                    second = await _one_order(judge, pack, ty, tx, tag)
                    second["position"] = 2
                if first.get("refused") or (second or {}).get("refused"):
                    record["refused"] = judge  # recorded without an error: the judge declined this pair
                elif first and second:
                    record["result"] = _resolve(first, second, x, y)
            except Exception as exc:  # noqa: BLE001 - a judge failure is recorded with what it cost, never a verdict
                record["error"] = f"{type(exc).__name__}: {exc}"[:400]
                if isinstance(exc, NoVerdict):
                    failed.append({**exc.order, "position": 2 if first else 1, "unusable": True})
            except BaseException as exc:  # Ctrl-C or a cancelled task: the orders already paid for are kept, then it stops
                record["error"] = f"interrupted: {type(exc).__name__}"
                interrupted = exc
        record["orders"] = [o for o in (first, second) if o] + failed
    if superseded:
        record["superseded"] = superseded
    record["cost_usd"] = round(sum(o["cost_usd"] for o in [*record.get("orders", []), *superseded]), 6)
    write_json(out_path, record)
    if interrupted is not None:
        raise interrupted
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
