#!/usr/bin/env python3
"""Run one fresh control/thinking-low pair through the existing summary service."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

from pilot_meter import PilotMeter

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure_base() -> None:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise SystemExit("sanctioned OPENAI_API_KEY mapping is unavailable")
    os.environ.update({
        "OPENAI_BASE_URL": "https://api.deepseek.com/v1",
        "AI_DEFAULT_MODEL": "deepseek-flash",
        "AI_FAST_MODEL": "", "AI_SECTION_RECOVERY_MODEL": "",
        "AI_FALLBACK_MODEL": "", "AI_FALLBACK_BASE_URL": "",
        "AI_SUMMARY_THINKING_EFFORT": "",
        "AI_SUMMARY_THINKING_MAX_TOKENS": "24000",
        "USE_STRUCTURED_OUTPUT": "false", "USE_EDGARTOOLS_SECTIONS": "true",
        "USE_STATEMENT_FINANCIALS": "true", "RICHER_FINANCIALS_ENABLED": "true",
        "AI_EVIDENCE_SNAP": "true", "AI_FIGURE_TRACE_GATE": "false",
        "AI_FORWARD_QUOTE_GATE": "false", "AI_ATTRIBUTION_GATE": "false",
        "AI_ATTRIBUTION_VERIFY": "false", "STREAM_SECTION_REVEAL": "true",
        "SKIP_REDIS_INIT": "true",
    })


async def run_arm(repo: Path, state_dir: Path, pair_id: str, arm: str, target: dict,
                  manifest_sha256: str) -> bool:
    from app.config import settings
    from app.services.ai.provider_requests import measure_provider_requests
    from app.services.openai_service import OpenAIService

    settings.AI_SUMMARY_THINKING_EFFORT = "low" if arm == "thinking-low" else ""
    slot_id = f"{pair_id}-{arm}"
    meter = PilotMeter(state_dir / "pilot-ledger.sqlite3", slot_id, manifest_sha256)
    if meter.slot_has_attempt(slot_id):
        raise RuntimeError("slot already has a provider attempt; redraw refused")
    item_path = HERE / target["input_path"]
    if sha(item_path) != target["input_sha256"]:
        raise RuntimeError("pilot input hash changed")
    item = json.loads(item_path.read_text())
    out_dir = state_dir / "runs" / slot_id
    out_dir.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "thinking-low-arm-receipt-v1", "slot_id": slot_id,
               "pair_id": pair_id, "arm": arm, "input_sha256": target["input_sha256"],
               "status": "error", "preview_count": 0}
    service = OpenAIService()

    async def preview(_value):
        receipt["preview_count"] += 1

    try:
        with measure_provider_requests(meter):
            result = await service.generate_structured_summary(
                item["grounding_excerpt"], item["company_name"], item["filing_type"],
                item["xbrl_grounding"], filing_excerpt=item["grounding_excerpt"],
                stream_cb=preview, statement_source=item["statement_source"],
                sixk_class=item["sixk_class"])
        payload = out_dir / "payload.json"
        payload.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        receipt.update(status="complete", payload_sha256=sha(payload))
        return True
    except BaseException as exc:
        receipt["error_type"] = type(exc).__name__
        return False
    finally:
        receipt["ledger"] = meter.snapshot()
        (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--pair-id", required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--preflight-receipt", type=Path, required=True)
    parser.add_argument("--prepare-receipt", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = HERE / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest_hash = sha(manifest_path)
    preflight = json.loads(args.preflight_receipt.read_text())
    prepared = json.loads(args.prepare_receipt.read_text())
    if (preflight.get("errors") != [] or preflight.get("manifest_sha256") != manifest_hash
            or preflight.get("capsule_lock_sha256") != sha(HERE / "capsule-lock.json")):
        raise SystemExit("offline preflight is not bound to this capsule")
    if prepared.get("status") != "prepared" or prepared.get("pair_id") != args.pair_id:
        raise SystemExit("durable state is not prepared for this pair")
    if args.pair_id not in manifest["pair_order"]:
        raise SystemExit("pair is not in the frozen sequence")
    pair_path = args.state_dir / "pairs" / f"{args.pair_id}.json"
    pair_path.parent.mkdir(parents=True, exist_ok=True)
    pair_receipt = {"schema": "thinking-low-pair-run-v1", "pair_id": args.pair_id,
                    "arm_order": ["control", "thinking-low"], "status": "error"}
    pair_path.write_text(json.dumps(pair_receipt, indent=2, sort_keys=True) + "\n")
    target = next(target for target in manifest["targets"]
                  if args.pair_id.startswith(f"{target['ticker']}-{target['filing_type']}-run"))
    try:
        configure_base()
        repo = args.repo.resolve()
        if str(repo / "backend") not in sys.path:
            sys.path.insert(0, str(repo / "backend"))
        control_ok = await run_arm(
            repo, args.state_dir, args.pair_id, "control", target, manifest_hash)
        candidate_ok = False
        if control_ok:
            candidate_ok = await run_arm(
                repo, args.state_dir, args.pair_id, "thinking-low", target, manifest_hash)
        pair_receipt.update(control_complete=control_ok, candidate_complete=candidate_ok,
                            status="complete" if control_ok and candidate_ok else "error")
    except BaseException as exc:
        pair_receipt["error_type"] = type(exc).__name__
        raise
    finally:
        pair_path.write_text(json.dumps(pair_receipt, indent=2, sort_keys=True) + "\n")
    return 0 if control_ok and candidate_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
