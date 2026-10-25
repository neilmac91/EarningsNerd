"""Semantic audit of verified claims: is each number said about the metric and period it matched?

    cd backend && python -m evals.trend_depth.semantics --label eval-v1 --systems deepseek-flash,gemini-3.8-flash,claude-sonnet-5-5

The gate matches a printed number to a cited value; it does not read the words around the number. A claim
"revenue grew 8.3%" that cites an 8.3% growth in cash would pass it. This audit measures how often that
happens: for every verified claim of an analysis, an auditor from another model family sees the sentence,
the claim, and the label and period of the value (or derivation) it matched, and marks the claim
``consistent`` or ``mismatch`` (the sentence attributes the number to a different metric, period or
basis). Results land in ``runs/<label>/semantics/<system>/<TICKER>.json``; ``--auditor <arm>`` audits every
system with that one model instead, in ``runs/<label>/semantics-by-<arm>/``.

The auditor's view of each match is versioned (``VIEW``, stored as ``view`` on each audit; an audit without one,
eval-v1's for example, saw view 1). View 2 (DEEPSEEK-ERRORS.md fix 14) adds what view 1 left the auditor to guess,
so that correct statements stop drawing flags: each matched value's signed value (view 1 showed only "ID = label,
period", so a correct "net debt of $26.2 billion" for a net cash of -26.2 billion looked like a sign error), the
value of a calculation, whether the claim is a bound the value satisfies ("below 1.0x"), and the IDs whose value is
identical to a matched value or to one of its inputs (VRTX's "buybacks plus dividends" is its buybacks, as it pays
no dividend). A twin is another name for that one value: an input's twin is shown only when every input is of the
value's own period, and an ID the pack withholds is never a twin (``_describe``, ``_withheld``), so that no twin
licenses a wrong number. The record format is unchanged: the view is in each item's ``match`` text. An audit made
under an earlier view is redone, its cost carried forward, unless the same auditor's other folder already holds one
of this output under the current view, which is copied.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from evals.trend_depth import factcheck
from evals.trend_depth.causes import _auditor, audit_call, earlier_audit, reuse_audit
from evals.trend_depth.companies import eval_companies
from evals.trend_depth.generate import RUNS, load_pack, sentences_of
from evals.trend_depth.records import output_sha256, own_spend, read_same_output, unsettled, write_json

VIEW = 2
SYSTEM = """You check that each number in a financial analysis is said about the right thing. For each numbered
item you get a sentence, one number from it, and what that number was matched to in the evidence (the
metric label, period and signed value of a cited value, or a calculation from cited values and its result). Mark
the item:
- "consistent": the sentence says the number is that metric for that period (or that calculation), with its sign,
  allowing ordinary paraphrase ("sales" for revenue, "fell 10.3%" for a growth of -10.3%);
- "mismatch": the sentence attributes the number to a different metric, period, segment, sign or basis than the
  match (for example it calls a cash-flow growth "revenue growth", a FY2024 value "FY2025", a growth of -10.3% a
  rise, or a level a change).
How to read a match:
- Values are signed as the evidence stores them, and the sentence must give the value's sign, by a minus sign or in
  words ("fell 10.3%", "a loss of $2.1 billion", "used $3.0 billion" for a negative value). The opposite sign is a
  mismatch: a negative value stated as a positive amount ("net income of $2.1 billion" for -$2.1 billion), or a
  positive one given the opposite sign ("a loss of $2.1 billion" for net income of $2.1 billion). Net cash below
  zero is net debt: "net debt of $26.2 billion" is consistent with a net cash of -$26.2 billion; "net cash of $26.2
  billion" for it, "net debt" for a net cash above zero, a minus sign printed under "net debt", and "better" or
  "worse" that the signed values contradict are mismatches.
- "A bound" means the sentence states an inequality ("below 1.0x", "at least 10%") that the matched value satisfies:
  it is consistent when the sentence applies the bound to that metric and period.
- "Same value as" names other evidence values identical to the value it follows, in that period: other names for
  that value, and for nothing else.
  - After the value of a "cited" match, the sentence may give the number under any of those names.
  - After an input of the cited value ("its input ... has the same value as") or after one value of a calculation,
    a name may replace that input or value inside the same calculation only: "share repurchases were 63% of free
    cash flow" is consistent with "buybacks plus dividends % of free cash flow" whose input "buybacks plus
    dividends" has the same value as share repurchases. The number stated as anything else about that name (its
    level, its growth, a ratio or share the match does not compute) is a mismatch.
Return one JSON object only: {"items": [{"n": 1, "label": "consistent", "reason": "<= 20 words"}]}"""
_NO_TWINS = ("pctile",)  # percentile ranks share values by coincidence, not by construction
_MAX_TWINS = 3


def _signed(value: float, unit: str) -> str:
    """A value as the evidence stores it, sign included, in its unit."""
    sign = "-" if value < 0 else ""
    if unit == "usd":
        size = abs(value)
        for scale, word in ((1e12, "trillion"), (1e9, "billion"), (1e6, "million")):
            if size >= scale:
                return f"{sign}${size / scale:,.2f} {word}"
        return f"{sign}${size:,.2f}"
    if unit == "usd_per_share":
        return f"{sign}${abs(value):,.2f} per share"
    if unit == "pp":
        return f"{value:+.2f}pp"
    suffix = {"pct": "%", "x": "x", "multiple": "x", "days": " days", "years": " years", "pctile": " (percentile)",
              "shares": " shares"}.get(unit, "")
    return f"{value:,.2f}{suffix}"


def _withheld(pack: dict[str, Any]) -> set[str]:
    """The IDs a version-2 pack withholds (``derived.withheld``: a dict of ID to its reason, ``debt_break``,
    ``liquidity_break`` or ``peer_break``; a list in an earlier build), whatever the reason. None is ever a twin: the
    generator was never shown it, and it is not the quantity its label names. COP's FY2025 "Total debt" (D336) is its
    current portion of debt alone, so as a twin it would present "total debt was $1.0 billion [X203]" to the auditor
    as a correct label, while the measure of broken net cash, reading cited IDs, would not see it either."""
    return set(pack.get("withheld") or ())


def _one_period(ids: list[str], pack: dict[str, Any], period: Optional[str] = None) -> bool:
    """Every ID is a pack value, all of one period (``period`` when given). Only then may a twin of one of them
    stand in for it inside the calculation: across periods, a twin of one year's value is not a twin of the result.
    AMD's FY2019 total debt growth (D170, -61.1%) has an FY2019 input equal to long-term debt, but not an FY2018 one,
    so long-term debt fell 56.4% (D157), and the twin would have licensed "long-term debt fell 61.1%"."""
    values = pack["values"]
    periods = {values[i]["period"] if i in values else None for i in ids}
    return bool(ids) and None not in periods and len(periods) == 1 and (period is None or periods == {period})


def _twins(vid: str, pack: dict[str, Any], shown: tuple[str, ...] = ()) -> list[str]:
    """Other IDs whose value is identical to ``vid``'s, in the same unit and period: one quantity under two names.
    Zeros and percentile ranks are left out, as they coincide by chance, and so are the IDs in ``shown`` and those
    the pack withholds (``_withheld``)."""
    value = pack["values"][vid]
    if not value["value"] or value["unit"] in _NO_TWINS:
        return []
    hidden = {vid, *shown, *_withheld(pack)}
    tolerance = 1e-9 * max(1.0, abs(value["value"]))
    return [other for other, v in pack["values"].items() if other not in hidden and v["unit"] == value["unit"]
            and v["period"] == value["period"] and abs(v["value"] - value["value"]) <= tolerance][:_MAX_TWINS]


def _twin_text(twins: list[str], pack: dict[str, Any]) -> str:
    return "same value as " + ", ".join(f"{t} = {pack['values'][t]['label']}" for t in twins)


def _computed(match: str, ids: list[str], pack: dict[str, Any]) -> Optional[str]:
    """The signed result of the calculation a claim matched, or None for a cited value or a passage's figure."""
    if match.startswith("reversed ") and ids and ids[0] in pack["values"]:  # "revenue growth minus cost growth" read the other way
        value = pack["values"][ids[0]]
        return _signed(-value["value"], value["unit"])
    if match == "cited" or match.startswith("passage ") or not ids:
        return None
    found = next((c for c in factcheck.candidates(ids, pack) if c.how == match), None)
    return _signed(found.value, found.unit) if found else None


def _describe(match: str, ids: list[str], pack: dict[str, Any]) -> str:
    """The auditor's view of a match (view 2): each matched value's label, period and signed value and the IDs it is
    identical to; for a cited value, those of its inputs too ("buybacks plus dividends % of free cash flow" built on
    a "buybacks plus dividends" that is the buybacks line); a calculation's result; a passage's year; a red flag's
    whole text (cut at 120 characters, it hid the figure the claim matched from the auditor in 2 of the 18 such
    claims of eval-v1's DeepSeek and Sonnet analyses: CAT's 0.06% and JPM's 0.10%).

    A twin stands in for an input, or for one value of a calculation, only when all of them are of the result's
    period (``_one_period``): a growth, a CAGR or a cross-year difference shows none, as a twin of one of its years
    would license a different metric's change. A cited value's own twins are always shown: they equal it."""
    calculation = match != "cited" and not match.startswith(("reversed ", "passage "))
    operands_alike = not calculation or _one_period([i for i in ids if i in pack["values"]], pack)
    parts = []
    for vid in ids:
        value = pack["values"].get(vid)
        if value:
            text = [f"{vid} = {value['label']}, {value['period']}, {_signed(value['value'], value['unit'])}"]
            twins = _twins(vid, pack) if operands_alike else []
            if twins:
                text.append(_twin_text(twins, pack))
            inputs = [] if calculation else value.get("inputs") or []
            for i in inputs if _one_period(inputs, pack, value["period"]) else []:
                inner = _twins(i, pack, (vid, *twins))
                if inner:
                    text.append(f"its input {i} = {pack['values'][i]['label']} has the {_twin_text(inner, pack)}")
            parts.append("; ".join(text))
        else:
            passage = next((p for p in pack["passages"] if p["id"] == vid), None)
            if passage:
                parts.append(f"{vid} = a figure in a {passage['fiscal_year']} 10-K passage")
            else:
                flag = next((f for f in pack.get("red_flags", []) if f["id"] == vid), None)
                parts.append(f"{vid} = red-flag text: {flag['detail']}" if flag else vid)
    result = _computed(match, ids, pack)
    return f"{match}{f' = {result}' if result else ''}: " + " | ".join(parts)


def _bound(claim: dict[str, Any]) -> str:
    """The view's note on a claim the gate read as an inequality, which the matched value satisfies."""
    side = {"at_least": "at least", "at_most": "at most"}.get(claim.get("qualifier") or "")
    return f" (a bound: the sentence says the value is {side} this number, and the matched value is)" if side else ""


def _current_view_copy(out: Path, label: str, system: str, ticker: str, auditor: Optional[str], sha: str,
                       spent: float) -> bool:
    """Copy the same auditor's audit of this output under the current view from its other folder (default or
    same-auditor), as ``causes.reuse_audit`` does for a missing one; True if one was copied."""
    default_auditor = _auditor(system)
    if (auditor or default_auditor) != default_auditor:
        return False
    default = RUNS / label / "semantics" / system / f"{ticker}.json"
    other = RUNS / label / f"semantics-by-{default_auditor}" / system / f"{ticker}.json" if out == default else default
    if not other.exists():
        return False
    record = json.loads(other.read_text())
    if ("error" in record or record.get("view", 1) < VIEW or not read_same_output(record, "output_sha256", sha)
            or record.get("auditor") != default_auditor):
        return False
    write_json(out, {**record, "copied_from": other.parent.parent.name, "prior_cost_usd": spent})
    return True


def classify_flag(item: dict[str, Any], sentences: list[dict[str, Any]], pack: dict[str, Any]) -> str:
    """Why the auditor's ``mismatch`` may not be an error, read deterministically from the gate:

    - ``bound``: the number is a bound ("below 1.0x", "at least 10%") that the cited value satisfies; under view 1
      the auditor saw only the value it was checked against, not that the claim is an inequality;
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
        if earlier.get("view", 1) >= VIEW or earlier.get("refused"):  # a refusal is the auditor's outcome, never retried
            return
        spent = own_spend(earlier)  # an audit under an earlier view is not a measurement under this one: redone
        if _current_view_copy(out, label, system, ticker, auditor, sha, spent):
            return
    pack = load_pack(ticker, system)
    result = factcheck.check(sentences_of(record["output"]), pack)
    items = []
    for detail in result["detail"]:
        for claim in detail["claims"]:
            if claim["status"] == "verified" and claim.get("ids"):
                items.append({"sentence": factcheck.CITATION_RE.sub("", detail["text"]).strip(), "claim": claim["claim"],
                              "match": _describe(claim.get("matched", ""), claim["ids"], pack) + _bound(claim)})
    auditor = auditor or _auditor(system)
    record_out: dict[str, Any] = {"system": system, "ticker": ticker, "split": pack["split"], "auditor": auditor, "items": [],
                                  "output_sha256": sha, "view": VIEW}
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
