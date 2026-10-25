"""Generate analyses for the depth bake-off and fact-check every one.

    cd backend && python -m evals.trend_depth.generate --label dev-v1 --arms deepseek-flash,claude-sonnet-5-5 --split dev
    cd backend && python -m evals.trend_depth.generate --label eval-v1 --arms current --split all

Arms are the proposed prompt (``prompts/trends-depth-analyst-agent.md``) on a model from
``providers.ARMS``, or ``current``: the production pipeline (``trend_analysis.narrative.stream_trend_narrative``,
deepseek-flash selecting code-rendered observations) over the same window, through the same facts store.

Each output lands in ``tasks/analysis-depth-2026-10/runs/<label>/<arm>/<TICKER>.json`` with the raw reply,
the parsed sections, the fact-check result, token usage, latency and cost. A reply that is not the
required JSON gets one retry that names the problem (the production pipeline's retry discipline); a
second failure is recorded as a failed generation, never repaired by hand.
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from evals.trend_depth import bootstrap
from evals.trend_depth import factcheck, render
from evals.trend_depth.companies import eval_companies
from evals.trend_depth.providers import ARMS, call, max_tokens_for, parse_json_object

# TREND_DEPTH_PROMPT points a run at a draft prompt without touching the checked-in one mid-run.
PROMPT_PATH = Path(os.environ.get("TREND_DEPTH_PROMPT") or bootstrap.BACKEND / "prompts" / "trends-depth-analyst-agent.md")
RUNS = bootstrap.RECORDS / "runs"
SECTION_KEYS = ("arc", "drivers", "margins", "cash", "balance_sheet", "red_flags", "watch")
SENTENCE_TYPES = ("fact", "comparison", "cause", "judgement")


def load_pack(ticker: str) -> dict[str, Any]:
    plain = bootstrap.RECORDS / "packs" / f"{ticker}.json"
    packed = bootstrap.RECORDS / "packs" / f"{ticker}.json.gz"
    if packed.exists():
        return json.loads(gzip.decompress(packed.read_bytes()))
    return json.loads(plain.read_text())


def system_prompt() -> str:
    return PROMPT_PATH.read_text()


def user_message(pack: dict[str, Any]) -> str:
    return render.render(pack) + "\n\nWrite the analysis for this company now. Return the JSON object only."


def validate(parsed: Optional[dict[str, Any]]) -> list[str]:
    """Structural problems with a reply (empty list when it is usable)."""
    if not isinstance(parsed, dict) or not isinstance(parsed.get("sections"), list):
        return ["reply is not a JSON object with a 'sections' list"]
    problems = []
    keys = [s.get("key") for s in parsed["sections"] if isinstance(s, dict)]
    missing = [k for k in SECTION_KEYS if k not in keys]
    if missing:
        problems.append(f"missing sections: {', '.join(missing)}")
    for section in parsed["sections"]:
        if not isinstance(section, dict) or not isinstance(section.get("sentences"), list):
            problems.append("a section has no 'sentences' list")
            continue
        for sentence in section["sentences"]:
            if not isinstance(sentence, dict) or not isinstance(sentence.get("text"), str):
                problems.append(f"section {section.get('key')}: a sentence is not an object with 'text'")
                break
            if sentence.get("type") not in SENTENCE_TYPES:
                problems.append(f"section {section.get('key')}: sentence type {sentence.get('type')!r} is not one of {SENTENCE_TYPES}")
                break
    return problems


def sentences_of(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for section in parsed.get("sections", []):
        for sentence in section.get("sentences", []):
            out.append({"section": section.get("key", ""), "text": sentence.get("text", ""), "type": sentence.get("type", "")})
    return out


def word_count(parsed: dict[str, Any]) -> int:
    clean = " ".join(factcheck.CITATION_RE.sub("", s["text"]) for s in sentences_of(parsed))
    return len(clean.split())


def _attempt(index: Any, result: Any, problems: list[str]) -> dict[str, Any]:
    return {
        "attempt": index, "input_tokens": result.input_tokens, "cached_input_tokens": result.cached_input_tokens,
        "output_tokens": result.output_tokens, "reasoning_tokens": result.reasoning_tokens,
        "latency_s": result.latency_s, "cost_usd": result.cost_usd, "backend": result.backend,
        "model_served": result.model_served, "meta": result.meta, "problems": problems, "raw": result.text,
    }


def _usage(attempts: list[dict[str, Any]]) -> dict[str, int]:
    return {key: sum(a[key] for a in attempts) for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")}


def _add_attempt(record: dict[str, Any], result: Any, problems: list[str]) -> None:
    """Add a repair call to a record: its attempt, usage, latency and cost."""
    record["attempts"].append(_attempt("repair", result, problems))
    for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens"):
        record["usage"][key] += getattr(result, key)
    record["latency_s"] = round(record["latency_s"] + result.latency_s, 3)
    record["cost_usd"] = round(record["cost_usd"] + result.cost_usd, 6)


class GenerationError(RuntimeError):
    """A provider failure part-way through a generation; ``attempts`` holds the calls already paid for."""

    def __init__(self, message: str, attempts: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.attempts = attempts


async def generate_proposed(arm_name: str, ticker: str, repair: bool = True, tag: str = "") -> dict[str, Any]:
    arm = ARMS[arm_name]
    pack = load_pack(ticker)
    system, user = system_prompt(), user_message(pack)
    attempts: list[dict[str, Any]] = []
    parsed: Optional[dict[str, Any]] = None
    problems: list[str] = []
    message = user
    for attempt in range(2):
        try:
            result = await call(arm, system, message, max_tokens=max_tokens_for(arm), tag=tag)
        except Exception as exc:  # noqa: BLE001 - re-raised with the paid attempts attached
            if getattr(exc, "result", None) is not None:  # a truncated reply was paid for: record it
                attempts.append(_attempt(attempt, exc.result, ["the reply stopped at max_tokens"]))
            raise GenerationError(f"{type(exc).__name__}: {exc}", attempts) from exc
        if result.meta.get("stop_reason") == "refusal":
            # The model declined: its own outcome, recorded and never retried with the same pack.
            problems = ["the model refused (stop_reason refusal)"]
            attempts.append(_attempt(attempt, result, problems))
            break
        parsed = parse_json_object(result.text)
        problems = validate(parsed)
        attempts.append(_attempt(attempt, result, problems))
        if not problems:
            break
        message = user + (
            "\n\nYour previous reply was rejected: " + "; ".join(problems)
            + ". Return only the JSON object with all seven sections, each sentence an object with 'type' and 'text'."
        )
    record: dict[str, Any] = {
        "ticker": ticker, "arm": arm_name, "family": arm.family, "model": arm.model, "split": pack["split"],
        "profile": pack["profile"], "window": pack["window"], "snapshot_id": pack["snapshot_id"],
        "prompt_sha256": hashlib.sha256(system.encode()).hexdigest(),
        "attempts": attempts,
        "usage": _usage(attempts),
        "latency_s": round(sum(a["latency_s"] for a in attempts), 3),
        "cost_usd": round(sum(a["cost_usd"] for a in attempts), 6),
        "generation_ok": not problems,
    }
    if problems:
        record["gate"] = {"passed": False, "failures": [{"failure": "generation failed: " + "; ".join(problems)}]}
        return record
    sentences = sentences_of(parsed)
    record["output"] = parsed
    record["words"] = word_count(parsed)
    record["gate"] = factcheck.check(sentences, pack)
    if repair and not record["gate"]["passed"]:
        await repair_or_mark(arm, system, user, record, pack, tag)
    return record


async def repair_or_mark(arm: Any, system: str, user: str, record: dict[str, Any], pack: dict[str, Any], tag: str) -> None:
    """Run the one repair. If the call fails, the paid first pass stands and the record carries ``repair_error``,
    so the next run retries only the repair (``run``), never the first pass."""
    try:
        await _repair(arm, system, user, record["output"], record, pack, tag)
        record.pop("repair_error", None)
    except Exception as exc:  # noqa: BLE001 - recorded on the record, which keeps its first pass
        if getattr(exc, "result", None) is not None:  # a truncated repair was paid for: record it
            _add_attempt(record, exc.result, ["the reply stopped at max_tokens"])
        record["repair_error"] = f"{type(exc).__name__}: {exc}"[:500]


def repair_message(user: str, parsed: dict[str, Any], failures: list[dict[str, Any]]) -> str:
    listing = "\n".join(f"- [{f['section']}] {f['failure']}\n  Sentence: {f['sentence']}" for f in failures)
    return (
        user + "\n\nYour analysis was checked against the evidence pack and these sentences failed:\n" + listing
        + "\n\nHere is your analysis:\n" + json.dumps(parsed)
        + "\n\nReturn the whole analysis again as the same JSON object, changing only what is needed to fix the "
          "failed sentences: cite the ID of every figure in its own sentence, use the cited value exactly, or "
          "remove a figure you cannot cite. Keep everything else as it was."
    )


async def _repair(arm: Any, system: str, user: str, parsed: dict[str, Any], record: dict[str, Any], pack: dict[str, Any],
                  tag: str = "") -> None:
    """The production fallback the grounding rule proposes: one regeneration that names the failures."""
    first_gate = record["gate"]
    result = await call(arm, system, repair_message(user, parsed, first_gate["failures"]), max_tokens=max_tokens_for(arm), tag=tag)
    refused = result.meta.get("stop_reason") == "refusal"
    repaired = None if refused else parse_json_object(result.text)
    problems = ["the model refused (stop_reason refusal)"] if refused else validate(repaired)
    _add_attempt(record, result, problems)
    record["first_pass_gate"] = {k: first_gate[k] for k in ("passed", "claims", "verified", "failed_claims", "failures")}
    record["first_pass_output"] = parsed
    if problems:
        record["repair_failed"] = problems
        return
    record["output"] = repaired
    record["words"] = word_count(repaired)
    record["gate"] = factcheck.check(sentences_of(repaired), pack)


async def generate_current(ticker: str) -> dict[str, Any]:
    """The production pipeline end to end (real deepseek-flash selection), over the pack's window."""
    from app.models import Company
    from app.services.trend_analysis.narrative import stream_trend_narrative

    pack = load_pack(ticker)
    start, end = pack["window"].split("..")
    db = bootstrap.SessionLocal()
    try:
        company_id = db.query(Company).filter(Company.ticker == ticker).one().id
    finally:
        db.close()
    started = time.monotonic()
    complete: Optional[dict[str, Any]] = None
    error = None
    async for event in stream_trend_narrative(company_id=company_id, mode="annual", start_period=start,
                                              end_period=end, force=True):
        if event.get("type") == "complete":
            complete = event
        elif event.get("type") == "error":
            error = event.get("message")
    latency = time.monotonic() - started
    record: dict[str, Any] = {
        "ticker": ticker, "arm": "current", "family": "deepseek", "model": bootstrap.PRODUCTION_MODEL,
        "split": pack["split"], "profile": pack["profile"], "window": pack["window"], "latency_s": round(latency, 3),
        "generation_ok": complete is not None and error is None,
    }
    if complete is None:
        record["error"] = error
        return record
    usage = complete.get("usage") or {}
    record["usage"] = usage
    record["cost_usd"] = usage.get("estimated_cost_usd")
    record["narrative"] = complete["narrative"]
    record["citations"] = complete["citations"]
    record["words"] = len(complete["narrative"].split())
    return record


async def run(label: str, arm_names: list[str], tickers: list[str], concurrency: int) -> None:
    out_root = RUNS / label
    semaphores = {name: asyncio.Semaphore(concurrency if name != "current" else 1) for name in arm_names}

    async def one(arm_name: str, ticker: str) -> None:
        path = out_root / arm_name / f"{ticker}.json"
        existing = json.loads(path.read_text()) if path.exists() else None
        if existing and "error" not in existing and "repair_error" not in existing:
            return  # a model's own outcome is kept; a provider error (quota, outage) is retried
        if existing and "repair_error" in existing:
            pack = load_pack(ticker)
            if (existing.get("prompt_sha256") == hashlib.sha256(system_prompt().encode()).hexdigest()
                    and existing.get("snapshot_id") == pack["snapshot_id"]):
                async with semaphores[arm_name]:  # the first pass was paid for and stands: retry only its repair
                    await repair_or_mark(ARMS[arm_name], system_prompt(), user_message(pack), existing, pack,
                                         f"{label}/repair/{arm_name}/{ticker}")
                path.write_text(json.dumps(existing, indent=1, default=str))
                gate = existing.get("gate") or {}
                print(f"{label} {arm_name:24} {ticker:5} repair retried: gate={gate.get('passed')} "
                      f"{existing.get('repair_error', '')}", flush=True)
                return
            # The prompt or the evidence pack changed since the first pass, so it is regenerated, below.
        async with semaphores[arm_name]:
            try:
                record = await (generate_current(ticker) if arm_name == "current"
                                else generate_proposed(arm_name, ticker, tag=f"{label}/generate/{arm_name}/{ticker}"))
            except Exception as exc:  # noqa: BLE001 - a provider failure is recorded, with what it already cost, and retried
                attempts = getattr(exc, "attempts", [])
                record = {"ticker": ticker, "arm": arm_name, "generation_ok": False, "error": f"{type(exc).__name__}: {exc}"[:500],
                          "attempts": attempts, "cost_usd": round(sum(a["cost_usd"] for a in attempts), 6)}
        prior = [*(existing or {}).get("prior_attempts", []), *(existing or {}).get("attempts", [])]
        if prior:  # the failed generation this one replaces was paid for: its calls stay on the record
            record["prior_attempts"] = prior
            record["prior_cost_usd"] = round(sum(a["cost_usd"] for a in prior), 6)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=1, default=str))
        gate = record.get("gate") or {}
        pending = record.get("error") or (f"repair_error, re-run generate: {record['repair_error']}" if "repair_error" in record else "")
        print(f"{label} {arm_name:24} {ticker:5} ok={record.get('generation_ok')} gate={gate.get('passed')} "
              f"claims={gate.get('claims')} failed={gate.get('failed_claims')} words={record.get('words')} "
              f"cost=${record.get('cost_usd')} {record.get('latency_s')}s {pending}", flush=True)

    await asyncio.gather(*(one(arm, ticker) for arm in arm_names for ticker in tickers))


AUDIT_FOLDERS = ("causes", "semantics")


def copy_systems(source: str, label: str, systems: list[str], tickers: list[str]) -> int:
    """Put ``source``'s outputs for ``systems`` under ``label`` without regenerating them: the records, their
    audits (default and same-auditor folders) and the verdicts between two copied systems.

    Every unit is checked before anything is written: a record holding a provider error is skipped (the next
    ``generate`` makes it), and a proposed record must come from the prompt now checked in and from the
    evidence pack now committed (``current`` must cover the pack's window). A record already under ``label`` is
    kept; its audits and verdicts are copied only when it is the same record byte for byte, so an audit never
    lands beside an output it did not read.
    """
    prompt_sha = hashlib.sha256(system_prompt().encode()).hexdigest()
    src, dst = RUNS / source, RUNS / label
    units: list[tuple[str, str]] = []
    for system in systems:
        for ticker in tickers:
            record_path = src / system / f"{ticker}.json"
            if not record_path.exists():
                continue
            record = json.loads(record_path.read_text())
            if "error" in record or "repair_error" in record:
                print(f"skip {system} {ticker}: the {source} record holds a provider error; generate it instead")
                continue
            pack = load_pack(ticker)
            if system == "current":
                if record.get("window") != pack["window"]:
                    raise SystemExit(f"{record_path}: window {record.get('window')} is not the pack's {pack['window']}")
            elif record.get("prompt_sha256") != prompt_sha or record.get("snapshot_id") != pack["snapshot_id"]:
                raise SystemExit(f"{record_path} was generated from another prompt or evidence pack; generate it instead")
            units.append((system, ticker))
    same: set[tuple[str, str]] = set()
    copied = 0
    for system, ticker in units:
        record_rel = Path(system) / f"{ticker}.json"
        target = dst / record_rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((src / record_rel).read_text())
            copied += 1
        elif target.read_text() != (src / record_rel).read_text():
            print(f"keep {label}/{record_rel}: it differs from {source}'s, so its audits and verdicts are not copied")
            continue
        same.add((system, ticker))
        for folder in (f for f in src.glob("*") if f.is_dir() and f.name.split("-by-")[0] in AUDIT_FOLDERS):
            audit = folder / system / f"{ticker}.json"
            audit_target = dst / audit.relative_to(src)
            if audit.exists() and not audit_target.exists():
                audit_target.parent.mkdir(parents=True, exist_ok=True)
                audit_target.write_text(audit.read_text())
                copied += 1
    for verdict in src.glob("judge/*/*.json"):
        ticker, x, y = verdict.stem.split("__")
        target = dst / verdict.relative_to(src)
        if (x, ticker) in same and (y, ticker) in same and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(verdict.read_text())
            copied += 1
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--label", required=True)
    parser.add_argument("--arms", required=True, help="comma-separated: current and/or providers.ARMS keys")
    parser.add_argument("--split", default="dev", choices=("dev", "holdout", "all"))
    parser.add_argument("--tickers", default="", help="comma-separated override of the split")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--copy-from", default="", help="copy these arms' outputs, audits and mutual verdicts from "
                                                       "another label instead of generating them")
    args = parser.parse_args()
    tickers = args.tickers.split(",") if args.tickers else [
        c.ticker for c in eval_companies(None if args.split == "all" else args.split)
    ]
    if args.copy_from:
        print(f"copied {copy_systems(args.copy_from, args.label, args.arms.split(','), tickers)} files from {args.copy_from}")
        return
    asyncio.run(run(args.label, args.arms.split(","), tickers, args.concurrency))


if __name__ == "__main__":
    main()
