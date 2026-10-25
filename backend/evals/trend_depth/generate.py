"""Generate analyses for the depth bake-off and fact-check every one.

    cd backend && python -m evals.trend_depth.generate --label dev-v1 --arms deepseek-flash,claude-sonnet-5-5 --split dev
    cd backend && python -m evals.trend_depth.generate --label eval-v1 --arms current --split all
    cd backend && python -m evals.trend_depth.generate --label dev-v5-r1 --arms deepseek-flash,deepseek-flash-c --pipeline v2

Arms are a model from ``providers.ARMS`` on the prompt and evidence packs the arm pins (the frozen prompt
on ``packs/`` unless it names others), or ``current``: the production pipeline
(``trend_analysis.narrative.stream_trend_narrative``, deepseek-flash selecting code-rendered observations) over
the same window, through the same facts store. Each record carries the hashes of the prompt and the pack it read.

Each output lands in ``tasks/analysis-depth-2026-10/runs/<label>/<arm>/<TICKER>.json`` with the raw reply,
the parsed sections, the fact-check result, token usage, latency and cost. A reply that is not the
required JSON gets one retry that names the problem (the production pipeline's retry discipline); a
second failure is recorded as a failed generation, never repaired by hand.

``--pipeline`` picks what happens between the first pass and the gate's verdict. ``v1`` (the default) is eval-v1's
procedure, the gate and then one full repair if it failed, under the gate as it is now: fix 7's narrowings changed
some verdicts, so a v1 run does not repeat eval-v1's repair decisions (``replay.py`` and the report's old gate give
eval-v1's own verdicts). ``v2`` (DEEPSEEK-ERRORS.md fixes 1, 2, 5 and 13):

- the user message opens with a short nonce of the analysis (``analysis_nonce``: label, arm, ticker), recorded as
  ``nonce``, so no first request reads an earlier run's pack from DeepSeek's prompt cache, as a company's first
  analysis in production would not; its repair repeats the message, nonce included;
- the gate on the model's own output is kept as ``raw_first_pass_gate``; code retypes figures-only ``cause``
  sentences that cite no passage (``retyped``) and appends a figure's missing ID where exactly one fits
  (``autocite``, both in ``autocite.py``); the gate with its backstops then decides;
- a repair, only if failures remain, asks for patches to the failed sentences alone, says what each cited ID
  holds, and never asks for "the cited value"; code applies the patches, keyed on each sentence's text, so every
  other sentence stays byte for byte. A patch list that is invalid or does not apply falls back to the full repair
  (``repair_kind``); a reply that is the whole analysis instead is taken as the full repair, with no second call;
- a repair that only retypes a passage-less ``cause`` sentence to fact or comparison, keeping an explanatory clause
  ("because", "so", "as", "due to"), still fails, whatever else it edits: the sentence in the failed one's place is
  the one its patch wrote or, after a full repair, the one aligned with it.

A record made under ``v2`` carries ``pipeline: "v2"``; one without ``pipeline`` is version 1. A label holds one
build of each arm: ``run`` refuses to generate an arm into a label that holds records of that arm made with another
pipeline, prompt or evidence pack, and names each one.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import difflib
import gzip
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Optional

from evals.trend_depth import bootstrap
from evals.trend_depth import autocite, factcheck, render
from evals.trend_depth.companies import eval_companies
from evals.trend_depth.providers import ARMS, call, max_tokens_for, packs_dir, parse_json_object, prompt_path
from evals.trend_depth.records import pack_sha256, read_same_output, same_inputs, unsettled, write_json, write_text

# TREND_DEPTH_PROMPT points the candidate arms at a draft without touching the checked-in candidate mid-run; an arm
# pinned to the frozen prompt ignores it (providers.prompt_path).
PROMPT_DRAFT = os.environ.get("TREND_DEPTH_PROMPT", "")
RUNS = bootstrap.RECORDS / "runs"
SECTION_KEYS = ("arc", "drivers", "margins", "cash", "balance_sheet", "red_flags", "watch")
SENTENCE_TYPES = ("fact", "comparison", "cause", "judgement")
PIPELINES = ("v1", "v2")
NO_PASSAGE = "cause sentence cites no filing passage"  # the gate's failure for a cause without its passage


def load_pack(ticker: str, system: str = "") -> dict[str, Any]:
    """The evidence pack ``system`` reads (``providers.packs_dir``); ``current``, gold and no system read packs/."""
    folder = packs_dir(system, bootstrap.RECORDS)
    packed = folder / f"{ticker}.json.gz"
    if packed.exists():
        return json.loads(gzip.decompress(packed.read_bytes()))
    return json.loads((folder / f"{ticker}.json").read_text())


def system_prompt(arm_name: str) -> str:
    return prompt_path(arm_name, bootstrap.BACKEND.parent, PROMPT_DRAFT).read_text()


def user_message(pack: dict[str, Any]) -> str:
    return render.render(pack) + "\n\nWrite the analysis for this company now. Return the JSON object only."


def analysis_nonce(label: str, arm_name: str, ticker: str) -> str:
    """Version 2's tag of one analysis: the same for a label's retries of it, different in every other label."""
    return hashlib.sha256(f"{label}|{arm_name}|{ticker}".encode()).hexdigest()[:12]


def opening(user: str, nonce: str) -> str:
    """``user`` led by the analysis' nonce line (none without a nonce), so its prompt shares only the system prompt
    with any earlier request."""
    return f"Request {nonce}.\n\n{user}" if nonce else user


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


async def generate_proposed(arm_name: str, ticker: str, repair: bool = True, tag: str = "",
                            checkpoint: Optional[Callable[[dict[str, Any]], None]] = None,
                            pipeline: str = "v1", label: str = "") -> dict[str, Any]:
    """One analysis: up to two attempts at valid JSON, then the gate (under ``v2``, after the code fixes), then one
    repair if it failed. ``checkpoint`` is handed what is already paid for before each further call is sent, so a
    run stopped mid-call (Ctrl-C, a kill) loses nothing paid: the first attempt, as an interrupted generation,
    before the JSON retry; the first pass, marked as owed its repair, before the repair (and again before a
    patch's fallback), so the next run retries only the repair. Under ``v2`` the user message opens with the
    analysis' nonce (``label``, the arm, the ticker)."""
    arm = ARMS[arm_name]
    pack = load_pack(ticker, arm_name)
    nonce = analysis_nonce(label, arm_name, ticker) if pipeline == "v2" else ""
    system, user = system_prompt(arm_name), opening(user_message(pack), nonce)
    attempts: list[dict[str, Any]] = []
    parsed: Optional[dict[str, Any]] = None
    problems: list[str] = []
    message = user
    for attempt in range(2):
        if checkpoint and attempts:  # before the JSON retry is sent, the attempt already paid for is on disk
            checkpoint({"ticker": ticker, "arm": arm_name, "generation_ok": False, "attempts": list(attempts),
                        "error": "interrupted: the JSON retry had not returned",
                        "cost_usd": round(sum(a["cost_usd"] for a in attempts), 6)})
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
        "packs": packs_dir(arm_name, bootstrap.RECORDS).name, "pack_sha256": pack_sha256(pack),
        "attempts": attempts,
        "usage": _usage(attempts),
        "latency_s": round(sum(a["latency_s"] for a in attempts), 3),
        "cost_usd": round(sum(a["cost_usd"] for a in attempts), 6),
        "generation_ok": not problems,
    }
    if pipeline == "v2":
        record["pipeline"], record["nonce"] = "v2", nonce
    if problems:
        record["gate"] = {"passed": False, "failures": [{"failure": "generation failed: " + "; ".join(problems)}]}
        return record
    sentences = sentences_of(parsed)
    record["output"] = parsed
    record["words"] = word_count(parsed)
    if pipeline == "v2":
        fix_first_pass(record, pack)
    else:
        record["gate"] = factcheck.check(sentences, pack)
    if repair and not record["gate"]["passed"]:
        if checkpoint:
            checkpoint({**record, "repair_error": "interrupted: the repair had not returned"})
        await repair_or_mark(arm, system, user, record, pack, tag, checkpoint=checkpoint)
    return record


def fix_first_pass(record: dict[str, Any], pack: dict[str, Any]) -> None:
    """Version 2 before any repair: the gate on the model's own output (``raw_first_pass_gate``), fix 5's retyping
    and fix 1's auto-citation by code, then the gate with its backstops on what they leave."""
    parsed = record["output"]
    record["raw_first_pass_gate"] = factcheck.check(sentences_of(parsed), pack, backstops=True)
    fixed, record["retyped"] = autocite.retype(parsed, pack)
    fixed, record["autocite"] = autocite.autocite(fixed, pack)
    record["output"] = fixed
    record["words"] = word_count(fixed)
    record["gate"] = factcheck.check(sentences_of(fixed), pack, backstops=True)


async def repair_or_mark(arm: Any, system: str, user: str, record: dict[str, Any], pack: dict[str, Any], tag: str,
                         checkpoint: Optional[Callable[[dict[str, Any]], None]] = None) -> None:
    """Run the one repair, of the record's own pipeline. If the call fails, the paid first pass stands and the record
    carries ``repair_error``, so the next run retries only the repair (``run``), never the first pass."""
    try:
        if record.get("pipeline") == "v2":
            await _repair_v2(arm, system, user, record["output"], record, pack, tag, checkpoint)
        else:
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


def _cited(vid: str, pack: dict[str, Any]) -> str:
    """What a cited ID holds, as the repair message lists it: a value's label, period and value."""
    if vid in pack["values"]:
        value = pack["values"][vid]
        return f"[{vid}] {value['label']}, {value['period']} = {render.fmt(value['value'], value['unit'])}"
    flag = next((f for f in pack.get("red_flags", []) if f["id"] == vid), None)
    if flag is not None:
        return f"[{vid}] red flag: {flag['detail']}"
    return f"[{vid}] a filing passage" if any(p["id"] == vid for p in pack.get("passages", [])) else f"[{vid}] not in the pack"


def failure_listing(failures: list[dict[str, Any]], pack: dict[str, Any]) -> str:
    """Fix 2: each failed sentence once, with its failures; for a number matching nothing, what each cited ID holds
    and the rule against swapping in another metric's or year's value; for a cause without its passage, the
    three ways out."""
    grouped: dict[tuple[str, str], list[str]] = {}
    for failure in failures:
        grouped.setdefault((failure["section"], failure["sentence"]), []).append(failure["failure"])
    blocks = []
    for (section, sentence), found in grouped.items():
        lines = [f"- [{section}] {sentence}", *(f"  Failed: {f}" for f in found)]
        if any("matches nothing" in f for f in found):
            ids = dict.fromkeys(autocite.citations(sentence))
            lines.append("  The IDs it cites: " + ("; ".join(_cited(i, pack) for i in ids) if ids else "none"))
            lines.append("  If the number you meant is not in the pack, delete it; never replace it with a cited value "
                         "of a different metric or year.")
        if NO_PASSAGE in found:
            lines.append("  Fix it one of three ways: cite, in this sentence, the filing passage that states the cause; "
                         "retype it as judgement if it states no figure it does not cite; or delete the causal clause.")
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def repair_message_v2(user: str, parsed: dict[str, Any], failures: list[dict[str, Any]], pack: dict[str, Any],
                      patch: bool = True) -> str:
    """Fixes 2 and 13: the failed sentences with fix 2's notes, the analysis, and a request for patches to the failed
    sentences alone (``patch``), or, as the fallback, for the whole analysis again."""
    head = (user + "\n\nYour analysis was checked against the evidence pack and these sentences failed:\n"
            + failure_listing(failures, pack) + "\n\nHere is your analysis:\n" + json.dumps(parsed))
    if not patch:
        return head + ("\n\nReturn the whole analysis again as the same JSON object, changing only what is needed to "
                       "fix the failed sentences: cite the ID of every figure in its own sentence, or remove a figure "
                       "you cannot cite. Keep everything else as it was.")
    return head + (
        '\n\nReturn only a JSON object {"patches": [...]} with one patch per failed sentence: {"section": its section '
        'key, "original": the failed sentence\'s text exactly as above, "type": one of fact, comparison, cause, '
        'judgement, "text": the corrected sentence}, or {"section": ..., "original": ..., "delete": true} to remove '
        "it. Cite the ID of every figure in its own sentence, or remove a figure you cannot cite. Leave out every "
        "sentence that did not fail: it stays as it is.")


_LISTING_PREFIX = re.compile(r"^\s*(?:-\s*)?\[(?:" + "|".join(SECTION_KEYS) + r")\]\s*")  # "- [cash] ", as listed


def _quoted(item: Any, failed: set[tuple[str, str]]) -> Optional[tuple[str, str]]:
    """The failed sentence a patch quotes, as (section, text): its ``section`` and ``original`` strings, the original
    as listed or without the "[<section>] " the failure listing prints before it; None when it quotes none."""
    if not isinstance(item, dict) or not isinstance(item.get("section"), str) or not isinstance(item.get("original"), str):
        return None
    for original in (item["original"].strip(), _LISTING_PREFIX.sub("", item["original"], count=1).strip()):
        if (item["section"], original) in failed:
            return item["section"], original
    return None


def apply_patches(parsed: dict[str, Any], reply: Any, failures: list[dict[str, Any]]
                  ) -> tuple[Optional[dict[str, Any]], list[str], dict[tuple[str, str], list[dict[str, Any]]]]:
    """Fix 13: ``parsed`` with each patch applied to the failed sentence whose text it quotes, the problems that make
    the reply unusable (none when it applied), and what took each patched sentence's place (its new sentence, or
    none when deleted), keyed on (section, failed text). Every other sentence is the one in ``parsed``, byte for byte.
    A reply is unusable when it is no non-empty ``patches`` list, or a patch quotes no failed sentence by a string
    section and original (or one that appears twice), patches a sentence twice, or carries neither ``delete: true``
    nor a text. A patch without a type keeps the sentence's own; ``validate`` then checks the patched analysis, the
    new types included."""
    patches = reply.get("patches") if isinstance(reply, dict) else None
    if not isinstance(patches, list) or not patches:
        return None, ["reply is not a JSON object with a non-empty 'patches' list"], {}
    patched = copy.deepcopy(parsed)
    places: dict[tuple[Any, str], list[tuple[list[Any], int]]] = {}
    for section in patched["sections"]:
        for index, sentence in enumerate(section["sentences"]):
            places.setdefault((section.get("key"), sentence["text"].strip()), []).append((section["sentences"], index))
    failed = {(f["section"], f["sentence"].strip()) for f in failures}
    problems: list[str] = []
    edits: dict[tuple[str, str], dict[str, Any]] = {}
    for n, item in enumerate(patches, 1):
        key = _quoted(item, failed)
        if key is None or len(places.get(key, [])) != 1:
            problems.append(f"patch {n} does not quote one failed sentence of its section")
        elif key in edits:
            problems.append(f"patch {n} patches a sentence already patched")
        elif item.get("delete") is not True and not (isinstance(item.get("text"), str) and item["text"].strip()):
            problems.append(f"patch {n} has neither 'delete': true nor a 'text'")
        else:
            edits[key] = item
    if problems:
        return None, problems, {}
    deleted: list[tuple[list[Any], int]] = []
    replaced: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for key, item in edits.items():
        sentences, index = places[key][0]
        if item.get("delete") is True:
            deleted.append((sentences, index))
            replaced[key] = []
        else:
            sentences[index] = {**sentences[index], "type": item.get("type") or sentences[index].get("type"), "text": item["text"]}
            replaced[key] = [sentences[index]]
    for sentences, index in sorted(deleted, key=lambda place: -place[1]):
        del sentences[index]
    return patched, [], replaced


def read_patch_reply(parsed: dict[str, Any], text: str, failures: list[dict[str, Any]]
                     ) -> tuple[Optional[dict[str, Any]], list[str], Optional[dict[tuple[str, str], list[dict[str, Any]]]]]:
    """The patch reply ``text`` read: the repaired analysis, the problems that make it unusable, and what took each
    patched sentence's place (``apply_patches``). A reply that is a whole valid analysis instead of patches is taken
    as it stands, with None for the places (``successors`` aligns them)."""
    reply = parse_json_object(text)
    if isinstance(reply, dict) and "patches" not in reply and not validate(reply):
        return reply, [], None
    patched, problems, replaced = apply_patches(parsed, reply, failures)
    return patched, problems or validate(patched), replaced


def successors(first: dict[str, Any], repaired: dict[str, Any], failures: list[dict[str, Any]]
               ) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """For each failed sentence of ``first``, keyed on (section, text), the sentences of ``repaired`` in its place,
    by aligning each section's sentence texts (difflib): the one at its position when the section kept it or
    replaced it one for one, every sentence of the block that replaced it otherwise, none when it was deleted."""
    failed = {(f["section"], f["sentence"].strip()) for f in failures}
    after = {s.get("key"): s.get("sentences", []) for s in repaired.get("sections", []) if isinstance(s, dict)}
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for section in first.get("sections", []):
        old, new = section.get("sentences", []), after.get(section.get("key"), [])
        matcher = difflib.SequenceMatcher(None, [s["text"].strip() for s in old], [s["text"].strip() for s in new],
                                          autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            for i in range(i1, i2):
                key = (section.get("key"), old[i]["text"].strip())
                if key not in failed:
                    continue
                one_for_one = tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1)
                out.setdefault(key, []).extend([new[j1 + i - i1]] if one_for_one else new[j1:j2])
    return out


def retype_escapes(failures: list[dict[str, Any]], replaced: dict[tuple[str, str], list[dict[str, Any]]],
                   pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Fix 5's repair rule: a passage-less cause sentence whose replacement (``replaced``, from ``apply_patches`` or
    ``successors``) is typed fact or comparison, cites no passage and still opens an explanatory clause ("so
    conversion is diluted") still fails, whatever else the repair changed in it. A retype to judgement is fix 2's own
    way out and stands."""
    passages = {p["id"] for p in pack.get("passages", [])}
    out: list[dict[str, Any]] = []
    for failure in failures:
        if failure["failure"] != NO_PASSAGE:
            continue
        for sentence in replaced.get((failure["section"], failure["sentence"].strip()), []):
            word = autocite.explanatory(sentence["text"])
            escape = {"section": failure["section"], "sentence": sentence["text"], "type": sentence.get("type"),
                      "failure": f"retyped from cause without a passage but keeps its explanatory '{word}' clause"}
            if (sentence.get("type") in ("fact", "comparison") and word and escape not in out
                    and not any(i in passages for i in autocite.citations(sentence["text"]))):
                out.append(escape)
    return out


async def _repair_v2(arm: Any, system: str, user: str, parsed: dict[str, Any], record: dict[str, Any], pack: dict[str, Any],
                     tag: str = "", checkpoint: Optional[Callable[[dict[str, Any]], None]] = None) -> None:
    """Version 2's one repair: patches to the failed sentences, applied by code; the full repair only when the
    patches are unusable (the record keeps both calls and its ``repair_kind``). Each call is on the record before its
    reply is read, so a reply that cannot be read still counts. A refusal stands, as in version 1."""
    first_gate = record["gate"]
    failures = first_gate["failures"]
    result = await call(arm, system, repair_message_v2(user, parsed, failures, pack), max_tokens=max_tokens_for(arm), tag=tag)
    _add_attempt(record, result, [])
    record["first_pass_gate"] = {k: first_gate[k] for k in ("passed", "claims", "verified", "failed_claims", "failures",
                                                            "backstop_failures") if k in first_gate}
    record["first_pass_output"] = parsed
    refused = result.meta.get("stop_reason") == "refusal"
    repaired, problems, replaced = (None, ["the model refused (stop_reason refusal)"], {}) if refused else read_patch_reply(
        parsed, result.text, failures)
    record["attempts"][-1]["problems"] = problems
    record["repair_kind"] = "full" if replaced is None else "patch"
    if problems and not refused:
        if checkpoint:  # the paid patch call is on disk before the full repair is sent
            checkpoint({**record, "repair_error": "interrupted: the full repair had not returned"})
        result = await call(arm, system, repair_message_v2(user, parsed, failures, pack, patch=False),
                            max_tokens=max_tokens_for(arm), tag=tag)
        _add_attempt(record, result, [])
        refused = result.meta.get("stop_reason") == "refusal"
        repaired = None if refused else parse_json_object(result.text)
        problems = ["the model refused (stop_reason refusal)"] if refused else validate(repaired)
        record["attempts"][-1]["problems"] = problems
        record["repair_kind"], replaced = "full", None
    if problems:
        record["repair_failed"] = problems
        return
    record["output"] = repaired
    record["words"] = word_count(repaired)
    gate = factcheck.check(sentences_of(repaired), pack, backstops=True)
    escapes = retype_escapes(failures, successors(parsed, repaired, failures) if replaced is None else replaced, pack)
    if escapes:
        gate = {**gate, "passed": False, "failures": [*gate["failures"], *escapes]}
    record["gate"] = gate


async def generate_current(ticker: str) -> dict[str, Any]:
    """The production pipeline end to end (real deepseek-flash selection), over the pack's window."""
    from app.models import Company
    from app.services.trend_analysis.narrative import stream_trend_narrative

    pack = load_pack(ticker, "current")
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


def label_conflicts(label: str, arm_names: list[str], pipeline: str) -> list[str]:
    """Each record under ``label`` of the arms ``arm_names`` that this run would not have made: another pipeline,
    prompt or evidence pack. A record of a failed generation (``error``) is skipped: this run makes it again. A run
    over the others would pool two builds into one arm's measures."""
    out = []
    for arm_name in arm_names:
        folder = RUNS / label / arm_name
        if arm_name == "current" or not folder.is_dir():
            continue
        prompt_sha = hashlib.sha256(system_prompt(arm_name).encode()).hexdigest()
        for path in sorted(folder.glob("*.json")):
            record = json.loads(path.read_text())
            if "prompt_sha256" not in record or "error" in record:
                continue
            where, made_with = f"{label}/{arm_name}/{path.stem}", record.get("pipeline", "v1")
            if made_with != pipeline:
                out.append(f"{where} was made with pipeline {made_with}, not {pipeline}")
            if record["prompt_sha256"] != prompt_sha:
                out.append(f"{where} was made with prompt sha256 {str(record['prompt_sha256'])[:12]}, not {prompt_sha[:12]}")
            pack = load_pack(record.get("ticker", path.stem), arm_name)
            if record.get("snapshot_id") != pack["snapshot_id"] or not read_same_output(record, "pack_sha256", pack_sha256(pack)):
                out.append(f"{where} was made from evidence pack sha256 {str(record.get('pack_sha256'))[:12]} of snapshot "
                           f"{record.get('snapshot_id')}, not {pack_sha256(pack)[:12]} of {pack['snapshot_id']}")
    return out


async def run(label: str, arm_names: list[str], tickers: list[str], concurrency: int, pipeline: str = "v1") -> None:
    out_root = RUNS / label
    conflicts = label_conflicts(label, arm_names, pipeline)
    if conflicts:  # nothing is sent: the label would mix two builds of an arm
        raise SystemExit(f"{label} holds records made another way than this run would make them; run under a new label "
                         "or with the pipeline, prompt and packs they were made with:\n  " + "\n  ".join(conflicts))
    semaphores = {name: asyncio.Semaphore(concurrency if name != "current" else 1) for name in arm_names}
    options = {"pipeline": pipeline, "label": label} if pipeline != "v1" else {}  # v1: generate_proposed's defaults

    async def one(arm_name: str, ticker: str) -> None:
        path = out_root / arm_name / f"{ticker}.json"
        existing = json.loads(path.read_text()) if path.exists() else None
        if existing and not unsettled(existing):
            return  # a model's own outcome is kept, a failure included; a provider error (quota, outage) is retried
        if existing and "repair_error" in existing:  # label_conflicts found it made from this run's inputs
            pack, system = load_pack(ticker, arm_name), system_prompt(arm_name)
            user = opening(user_message(pack), existing.get("nonce", ""))  # the message its first pass was sent
            async with semaphores[arm_name]:  # the first pass was paid for and stands: retry only its repair
                await repair_or_mark(ARMS[arm_name], system, user, existing, pack, f"{label}/repair/{arm_name}/{ticker}",
                                     checkpoint=lambda record: write_json(path, record))
            write_json(path, existing)
            gate = existing.get("gate") or {}
            print(f"{label} {arm_name:24} {ticker:5} repair retried: gate={gate.get('passed')} "
                  f"{existing.get('repair_error', '')}", flush=True)
            return
        prior = [*(existing or {}).get("prior_attempts", []), *(existing or {}).get("attempts", [])]

        def save(record: dict[str, Any]) -> None:
            if prior:  # the failed generation this one replaces was paid for: its calls stay on the record
                record = {**record, "prior_attempts": prior, "prior_cost_usd": round(sum(a["cost_usd"] for a in prior), 6)}
            write_json(path, record)

        async with semaphores[arm_name]:
            try:
                record = await (generate_current(ticker) if arm_name == "current"
                                else generate_proposed(arm_name, ticker, tag=f"{label}/generate/{arm_name}/{ticker}",
                                                       checkpoint=save, **options))
            except Exception as exc:  # noqa: BLE001 - a provider failure is recorded, with what it already cost, and retried
                attempts = getattr(exc, "attempts", [])
                record = {"ticker": ticker, "arm": arm_name, "generation_ok": False, "error": f"{type(exc).__name__}: {exc}"[:500],
                          "attempts": attempts, "cost_usd": round(sum(a["cost_usd"] for a in attempts), 6)}
        save(record)
        gate = record.get("gate") or {}
        pending = record.get("error") or (f"repair_error, re-run generate: {record['repair_error']}" if "repair_error" in record else "")
        print(f"{label} {arm_name:24} {ticker:5} ok={record.get('generation_ok')} gate={gate.get('passed')} "
              f"claims={gate.get('claims')} failed={gate.get('failed_claims')} words={record.get('words')} "
              f"cost=${record.get('cost_usd')} {record.get('latency_s')}s {pending}", flush=True)

    await asyncio.gather(*(one(arm, ticker) for arm in arm_names for ticker in tickers))


AUDIT_FOLDERS = ("causes", "semantics")


def copy_systems(source: str, label: str, systems: list[str], tickers: list[str], pipeline: str = "v1") -> int:
    """Put ``source``'s outputs for ``systems`` under ``label`` without regenerating them: the records, their
    audits (default and same-auditor folders) and the verdicts between two copied systems.

    Every unit is checked before anything is written: a record holding a provider error is skipped (the next
    ``generate`` makes it), and a proposed record must come from the prompt and the evidence pack its arm runs
    on now, under ``pipeline`` (``current`` must cover the pack's window). A record already under ``label`` is
    kept; its audits and verdicts are copied only when it is the same record byte for byte, so an audit never lands
    beside an output it did not read.
    """
    src, dst = RUNS / source, RUNS / label
    units: list[tuple[str, str]] = []
    for system in systems:
        prompt_sha = "" if system == "current" else hashlib.sha256(system_prompt(system).encode()).hexdigest()
        for ticker in tickers:
            record_path = src / system / f"{ticker}.json"
            if not record_path.exists():
                continue
            record = json.loads(record_path.read_text())
            if "error" in record or "repair_error" in record:
                print(f"skip {system} {ticker}: the {source} record holds a provider error; generate it instead")
                continue
            pack = load_pack(ticker, system)
            if system == "current":
                if record.get("window") != pack["window"]:
                    raise SystemExit(f"{record_path}: window {record.get('window')} is not the pack's {pack['window']}")
            elif not same_inputs(record, prompt_sha, pack):
                raise SystemExit(f"{record_path} was generated from another prompt or evidence pack; generate it instead")
            elif record.get("pipeline", "v1") != pipeline:
                raise SystemExit(f"{record_path} was made with pipeline {record.get('pipeline', 'v1')}, not {pipeline}; "
                                 "generate it instead")
            units.append((system, ticker))
    same: set[tuple[str, str]] = set()
    copied = 0
    for system, ticker in units:
        record_rel = Path(system) / f"{ticker}.json"
        target = dst / record_rel
        if not target.exists():
            write_text(target, (src / record_rel).read_text())
            copied += 1
        elif target.read_text() != (src / record_rel).read_text():
            print(f"keep {label}/{record_rel}: it differs from {source}'s, so its audits and verdicts are not copied")
            continue
        same.add((system, ticker))
        for folder in (f for f in src.glob("*") if f.is_dir() and f.name.split("-by-")[0] in AUDIT_FOLDERS):
            audit = folder / system / f"{ticker}.json"
            audit_target = dst / audit.relative_to(src)
            if audit.exists() and not audit_target.exists():
                write_text(audit_target, audit.read_text())
                copied += 1
    for verdict in src.glob("judge/*/*.json"):
        ticker, x, y = verdict.stem.split("__")
        target = dst / verdict.relative_to(src)
        if (x, ticker) in same and (y, ticker) in same and not target.exists():
            write_text(target, verdict.read_text())
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
    parser.add_argument("--pipeline", default="v1", choices=PIPELINES,
                        help="v1: the gate, then one full repair (eval-v1); v2: code fixes, the gate with backstops, a patch repair")
    args = parser.parse_args()
    tickers = args.tickers.split(",") if args.tickers else [
        c.ticker for c in eval_companies(None if args.split == "all" else args.split)
    ]
    if args.copy_from:
        copied = copy_systems(args.copy_from, args.label, args.arms.split(","), tickers, args.pipeline)
        print(f"copied {copied} files from {args.copy_from}")
        return
    asyncio.run(run(args.label, args.arms.split(","), tickers, args.concurrency, args.pipeline))


if __name__ == "__main__":
    main()
