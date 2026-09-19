"""E8 measurement only: two n corpora from complete retained E2 grounding, one USD5 ledger.

Reuses evals.runner._run_one and its existing baseline owner. This is not a production
orchestrator/extraction test. Run only in the reviewed CI branch; no local keys or resume.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from evals.e8_budget import BudgetTransport, Ledger, SLOT, durable_json

BASE = "73cc31162c3dfe7ec497c8c88c43cf397afce4a7"
CONTROL_HASHES = (
    "8574ee7ccac4976e66b20fe9ee2bc64a509d36d3275f1f400ec29f64408c5fee",
    "2c1fb37fae2c719fa016b8c55c53d3532973afeb7229d9c4218bf3424e1053e9",
)
CHANNELS = ("grounding_excerpt", "xbrl_grounding", "statement_source", "sixk_class",
            "source_provenance", "coverage_inventory")


def input_digest(row: dict) -> str:
    return hashlib.sha256(json.dumps({key: row.get(key) for key in CHANNELS},
                                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def load_controls(paths: list[Path], harness: dict) -> list[dict]:
    controls = []
    for path, expected in zip(paths, CONTROL_HASHES, strict=True):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Control artifact SHA mismatch")
        report = json.loads(path.read_text())
        for key, value in harness.items():
            if key != "source_sha" and report["harness"].get(key) != value:
                raise ValueError(f"Control configuration mismatch: {key}")
        rows = report["results"]
        identities = {(row["ticker"], row["filing_type"], row["run"]) for row in rows}
        if (len(rows) != 70 or len(identities) != 70
                or any(row.get("error") or not row.get("score") or not row.get("grounding_excerpt", "").strip()
                       or row.get("candidate") != "baseline" for row in rows)):
            raise ValueError("Control corpus is incomplete or cannot be replayed")
        controls.append(report)
    for first, second in zip(controls[0]["results"], controls[1]["results"], strict=True):
        if ((first["ticker"], first["filing_type"], first["run"])
                != (second["ticker"], second["filing_type"], second["run"])
                or input_digest(first) != input_digest(second)):
            raise ValueError("E2 paired source channels differ")
    return controls


async def read_balance(key: str, output: Path) -> None:
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False, timeout=20) as client:
        response = await client.get("https://api.deepseek.com/user/balance",
                                    headers={"Authorization": f"Bearer {key}"})
        response.raise_for_status()
        balance = response.json()
    # Only the account balance response is retained; never request headers or credentials.
    durable_json(output / "balance-before.json", balance)
    usd = [Decimal(row["total_balance"]) for row in balance.get("balance_infos", [])
           if row.get("currency") == "USD"]
    if balance.get("is_available") is not True or len(usd) != 1 or not usd[0].is_finite() or usd[0] < 5:
        raise ValueError("Provider balance does not establish USD5 available")


async def main(paths: list[Path], output: Path) -> None:
    if (os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
            or os.environ.get("GITHUB_REF") != "refs/heads/codex/wave3-e8-n-pilot"):
        raise ValueError("Pilot is CI-only on its measurement branch; reruns are forbidden")
    from app.config import settings
    from app.services import ai_metrics
    from app.services.openai_service import openai_service
    from evals import runner
    from evals.schema import GoldenFiling

    harness = runner._harness_metadata()
    if (harness["model"] != "deepseek-flash" or harness["base_url"] != "https://api.deepseek.com/v1"
            or harness["fallback_model"] or harness["fallback_base_url"]
            or settings.AI_SUMMARY_THINKING_EFFORT):
        raise ValueError("Pilot model, route, fallback or reasoning configuration drift")
    controls = load_controls(paths, harness)
    data = json.loads(runner.GOLDEN_PATH.read_text())
    filings = [GoldenFiling.from_dict(row) for row in data["filings"]]
    filings = [filing for filing in filings if filing.verified and filing.document_url]
    expected = {(filing.ticker, filing.filing_type, repeat) for filing in filings for repeat in range(2)}
    if len(filings) != 35 or expected != {
            (row["ticker"], row["filing_type"], row["run"]) for row in controls[0]["results"]}:
        raise ValueError("Golden identities differ from E2")
    ledger = Ledger(output / "provider")
    await read_balance(settings.OPENAI_API_KEY, output)
    transport = BudgetTransport(httpx.AsyncHTTPTransport(retries=0), ledger)
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL,
                         max_retries=0, http_client=httpx.AsyncClient(
                             transport=transport, follow_redirects=False, trust_env=False))
    old_client = openai_service.client
    openai_service.client = client
    ai_metrics.set_trigger("eval")
    runner._configure_eval_telemetry()
    try:
        for corpus, control in enumerate(controls, 1):
            results = []
            rows = {(row["ticker"], row["filing_type"], row["run"]): row for row in control["results"]}
            metadata = {**harness, "candidates": ["baseline"], "runs_per_candidate": 2,
                        "filings": control["harness"]["filings"], "transient_retries": 1,
                        "retry_delay_seconds": runner.RETRY_DELAY_SECONDS,
                        "experiment": "E8 n retained-grounding pilot", "corpus": corpus,
                        "base_source_sha": BASE, "control_sha256": CONTROL_HASHES[corpus - 1],
                        "prompt_version": "summary-2026-09-n", "usd_ceiling_shared": 5,
                        "filing_concurrency": 2, "expected_slots": 70,
                        "raw_document_retained": False, "sixk_class_audit_retained": False}

            def checkpoint() -> None:
                ordered = sorted(results, key=lambda row: (row["ticker"], row["filing_type"], row["run"]))
                durable_json(output / f"n-corpus-{corpus}.json", {
                    "summary": runner._summarize(ordered), "results": ordered,
                    "harness": metadata, "admission_stopped": ledger.snapshot()["stopped"],
                    "complete": len(ordered) == 70,
                })

            semaphore = asyncio.Semaphore(2)

            async def one_filing(filing: GoldenFiling) -> None:
                async with semaphore:
                    for repeat in range(2):
                        if ledger.snapshot()["stopped"]:
                            return
                        row = rows[(filing.ticker, filing.filing_type, repeat)]
                        # At exact base, _parse_and_clean_text ignores raw filing_text whenever
                        # filing_excerpt is nonempty; all 140 retained excerpts satisfy that.
                        grounding = {"filing_text": row["grounding_excerpt"],
                                     "excerpt": row["grounding_excerpt"],
                                     "xbrl_metrics": row["xbrl_grounding"],
                                     **{key: row.get(key) for key in CHANNELS[2:]}}
                        slot = f"n{corpus}:{filing.ticker}:{filing.filing_type}:{repeat}"
                        token = SLOT.set(slot)
                        try:
                            result = await runner._run_one("baseline", filing, grounding, repeat, None,
                                                           transient_retries=1)
                            results.append({**result, "input_sha256": input_digest(row),
                                            "accession_number": filing.accession_number})
                            checkpoint()
                        finally:
                            SLOT.reset(token)

            checkpoint()
            tasks = [asyncio.create_task(one_filing(filing)) for filing in filings]
            try:
                await asyncio.gather(*tasks)
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                checkpoint()
    finally:
        openai_service.client = old_client
        await client.close()
        durable_json(output / "programme-final.json", ledger.snapshot())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controls", nargs=2, type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.controls, args.output))
