#!/usr/bin/env python3
"""Offline, no-network preflight for the fresh paired thinking-low diagnostic."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPSULE_ROOT = HERE.parents[2]


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


class Captured(BaseException):
    """Stop exactly at the SDK boundary; deliberately outside Exception."""


class _Completions:
    def __init__(self) -> None:
        self.request: dict | None = None

    async def create(self, **kwargs):
        self.request = kwargs
        raise Captured()


class _Chat:
    def __init__(self) -> None:
        self.completions = _Completions()


class _Client:
    max_retries = 0

    def __init__(self) -> None:
        self.chat = _Chat()


def configure_offline_environment() -> None:
    # The fake client below prevents a network call. Never inherit a real provider key here.
    os.environ.update({
        "SECRET_KEY": "offline-preflight-only-000000000000000000",
        "OPENAI_API_KEY": "offline-preflight-no-network",
        "OPENAI_BASE_URL": "https://api.deepseek.com/v1",
        "AI_DEFAULT_MODEL": "deepseek-flash",
        "AI_FAST_MODEL": "",
        "AI_SECTION_RECOVERY_MODEL": "",
        "AI_FALLBACK_MODEL": "",
        "AI_FALLBACK_BASE_URL": "",
        "AI_SUMMARY_THINKING_EFFORT": "",
        "AI_SUMMARY_THINKING_MAX_TOKENS": "24000",
        "USE_STRUCTURED_OUTPUT": "false",
        "USE_EDGARTOOLS_SECTIONS": "true",
        "USE_STATEMENT_FINANCIALS": "true",
        "RICHER_FINANCIALS_ENABLED": "true",
        "AI_EVIDENCE_SNAP": "true",
        "AI_FIGURE_TRACE_GATE": "false",
        "AI_FORWARD_QUOTE_GATE": "false",
        "AI_ATTRIBUTION_GATE": "false",
        "AI_ATTRIBUTION_VERIFY": "false",
        "STREAM_SECTION_REVEAL": "true",
    })


async def capture_request(repo: Path, item: dict, effort: str) -> dict:
    if str(repo / "backend") not in sys.path:
        sys.path.insert(0, str(repo / "backend"))
    from app.config import settings
    from app.services.openai_service import OpenAIService

    settings.AI_SUMMARY_THINKING_EFFORT = effort
    service = OpenAIService()
    client = _Client()
    service.client = client
    service.fallback_client = None

    async def preview(_value):
        return None

    try:
        await service.generate_structured_summary(
            item["grounding_excerpt"], item["company_name"], item["filing_type"],
            item["xbrl_grounding"], filing_excerpt=item["grounding_excerpt"],
            stream_cb=preview, statement_source=item["statement_source"],
            sixk_class=item["sixk_class"],
        )
    except Captured:
        pass
    request = client.chat.completions.request
    if request is None:
        raise RuntimeError("production route did not reach the captured SDK boundary")
    return request


def request_record(request: dict) -> dict:
    raw = canonical(request)
    messages = request.get("messages") or []
    return {
        "request_sha256": hashlib.sha256(raw).hexdigest(),
        "canonical_request_bytes": len(raw),
        "message_content_bytes": [len(message["content"].encode("utf-8")) for message in messages],
        "input_token_upper_bound": len(raw) + 64 * len(messages) + 256,
        "max_output_tokens": request.get("max_tokens"),
        "request_fields": sorted(request),
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True, help="clean exact-47d subject checkout")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    manifest_path = HERE / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    lock = json.loads((HERE / "capsule-lock.json").read_text())
    observed = {
        "schema": "fresh-paired-thinking-low-preflight-v1",
        "manifest_sha256": sha(manifest_path),
        "capsule_lock_sha256": sha(HERE / "capsule-lock.json"),
        "repo_head": git(repo, "rev-parse", "HEAD"),
        "repo_tree": git(repo, "rev-parse", "HEAD^{tree}"),
        "git_status_porcelain": git(repo, "status", "--porcelain"),
        "files": {}, "requests": {}, "errors": [],
    }
    if observed["repo_head"] != manifest["code"]["head"]:
        observed["errors"].append("subject HEAD differs")
    if observed["repo_tree"] != manifest["code"]["tree"]:
        observed["errors"].append("subject tree differs")
    if observed["git_status_porcelain"]:
        observed["errors"].append("subject checkout is not clean")
    for name, expected in manifest["code"]["file_sha256"].items():
        got = sha(repo / name)
        observed["files"][name] = got
        if got != expected:
            observed["errors"].append(f"subject code hash differs: {name}")
    for name, expected in lock["files"].items():
        path = CAPSULE_ROOT / name
        got = sha(path)
        observed["files"][name] = got
        if got != expected:
            observed["errors"].append(f"capsule file hash differs: {name}")

    golden = json.loads((repo / "backend/evals/golden_set.json").read_text())["filings"]
    configure_offline_environment()
    for target in manifest["targets"]:
        path = HERE / target["input_path"]
        if sha(path) != target["input_sha256"]:
            observed["errors"].append(f"input hash differs: {target['ticker']}")
            continue
        item = json.loads(path.read_text())
        authority = next(row for row in golden if row["ticker"] == target["ticker"]
                         and row["filing_type"] == target["filing_type"])
        if (item["company_name"], item["accession_number"]) != (
                authority["company_name"], authority["accession_number"]):
            observed["errors"].append(f"golden identity differs: {target['ticker']}")
        requests: dict[str, dict] = {}
        raw_requests: dict[str, dict] = {}
        for label, effort in (("fresh_control", ""), ("pilot_thinking_low", "low")):
            request = await capture_request(repo, item, effort)
            raw_requests[label] = request
            requests[label] = request_record(request)
            expected = target[f"{label}_request"]
            if requests[label] != expected:
                observed["errors"].append(f"{label} request differs: {target['ticker']}")
        control, candidate = raw_requests["fresh_control"], raw_requests["pilot_thinking_low"]
        differing = {key for key in set(control) | set(candidate)
                     if control.get(key) != candidate.get(key)}
        requests["authorized_delta_fields"] = sorted(differing)
        if differing != {"temperature", "max_tokens", "extra_body", "reasoning_effort"}:
            observed["errors"].append(
                f"fresh pair has unauthorized request delta: {target['ticker']} {sorted(differing)}"
            )
        observed["requests"][target["ticker"]] = requests

    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(observed, indent=2, sort_keys=True) + "\n")
    print(args.receipt)
    if observed["errors"]:
        print("\n".join(observed["errors"]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
