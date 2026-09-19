"""Measurement-only durable admission at the actual HTTP request boundary (never imported by app).

Prices verified 2026-09-19: https://api-docs.deepseek.com/quick_start/pricing/
Peak USD/M tokens: uncached input .30, cached input .006, output 1.20.
All amounts below are integer nanodollars. Settled amounts are conservative peak-price
upper bounds from provider-reported usage, not receipts or the application's zero cost field.
"""
from __future__ import annotations

import contextvars
import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

CAP = 5_000_000_000
CONTEXT = 1_048_576
MAX_OUTPUT = 393_216
MODEL = "deepseek-flash"
SLOT: contextvars.ContextVar[str] = contextvars.ContextVar("e8_slot", default="unassigned")


class AdmissionStopped(RuntimeError):
    """No provider request may be sent after admission has stopped."""


def durable_json(path: Path, value: Any) -> None:
    """Replace a complete JSON checkpoint and synchronize its directory entry."""
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class Ledger:
    """One programme, two corpora; fresh construction refuses any existing ledger."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "ledger.json"
        self.lock_path = directory / "programme.lock"
        # Exclusive creation also refuses a crashed programme whose JSON was never written.
        with self.lock_path.open("x") as handle:
            handle.write("E8 USD5 programme; do not reset or resume\n")
            handle.flush()
            os.fsync(handle.fileno())
        durable_json(self.path, {"cap_nanousd": CAP, "stopped": None, "requests": {}})

    def snapshot(self) -> dict:
        return json.loads(self.path.read_text())

    def _change(self, change: Any) -> Any:
        with self.lock_path.open("r+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            state = self.snapshot()
            result = change(state)
            durable_json(self.path, state)
            return result

    def stop(self, reason: str) -> None:
        def halt(state: dict) -> None:
            state["stopped"] = state["stopped"] or reason
        self._change(halt)

    def reserve(self, body: bytes, output_cap: int) -> str:
        reservation = CONTEXT * 300 + output_cap * 1200
        request_id = uuid4().hex

        def admit(state: dict) -> bool:
            occupied = sum(row["accounted_nanousd"] for row in state["requests"].values())
            if state["stopped"] or occupied + reservation > CAP:
                state["stopped"] = state["stopped"] or "USD5 admission ceiling"
                return False
            state["requests"][request_id] = {
                "slot": SLOT.get(), "reserved_nanousd": reservation,
                "accounted_nanousd": reservation, "state": "reserved",
                "output_cap": output_cap, "request_sha256": hashlib.sha256(body).hexdigest(),
            }
            return True

        if not self._change(admit):
            raise AdmissionStopped("USD5 programme admission stopped")
        try:
            with (self.directory / f"{request_id}.request.json").open("xb") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            self.stop("request capture failed; reservation retained")
            raise
        return request_id

    def finish(self, request_id: str, response: bytes, status: int, streaming: bool) -> None:
        """Only complete, coherent terminal usage can release an outstanding reservation."""
        usage = None
        error = None
        try:
            if status != 200:
                raise ValueError("non-200 response")
            if streaming:
                events = [line[5:].strip() for line in response.splitlines() if line.startswith(b"data:")]
                if not events or events[-1] != b"[DONE]":
                    raise ValueError("missing terminal SSE DONE")
                packets = [json.loads(event) for event in events[:-1]]
                if not packets or any(packet.get("model") != MODEL for packet in packets):
                    raise ValueError("response model identity mismatch")
                usages = [packet["usage"] for packet in packets if packet.get("usage") is not None]
                if len(usages) != 1 or packets[-1].get("usage") is None:
                    raise ValueError("missing or ambiguous terminal usage")
                usage = usages[0]
            else:
                packet = json.loads(response)
                if packet.get("model") != MODEL:
                    raise ValueError("response model identity mismatch")
                usage = packet["usage"]
            keys = ("prompt_tokens", "completion_tokens", "total_tokens",
                    "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")
            if not isinstance(usage, dict) or any(type(usage.get(key)) is not int or usage[key] < 0 for key in keys):
                raise ValueError("missing or invalid provider usage")
            if (usage["prompt_tokens"] != usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"]
                    or usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]):
                raise ValueError("inconsistent provider usage")
        except (ValueError, KeyError, TypeError) as exc:
            error = str(exc)

        def settle(state: dict) -> None:
            row = state["requests"][request_id]
            if row["state"] != "reserved":
                return
            row["response_sha256"] = hashlib.sha256(response).hexdigest()
            reason = error
            if not reason and (usage["prompt_tokens"] > CONTEXT or usage["completion_tokens"] > row["output_cap"]):
                reason = "provider exceeded reserved token envelope"
            if reason:
                row.update(state="unknown", accounting_error=reason)
                state["stopped"] = state["stopped"] or reason
                return
            actual_bound = (usage["prompt_cache_hit_tokens"] * 6
                            + usage["prompt_cache_miss_tokens"] * 300
                            + usage["completion_tokens"] * 1200)
            row.update(state="usage_settled", accounted_nanousd=actual_bound, provider_usage=usage)

        self._change(settle)


class CapturedStream(httpx.AsyncByteStream):
    def __init__(self, stream: httpx.AsyncByteStream, ledger: Ledger, request_id: str,
                 status: int, streaming: bool) -> None:
        self.stream, self.ledger, self.request_id = stream, ledger, request_id
        self.status, self.streaming = status, streaming
        self.path = ledger.directory / f"{request_id}.response.body"
        self.closed = False
        self.complete = False
        self.path.touch(exist_ok=False)

    async def __aiter__(self):
        async for chunk in self.stream:
            with self.path.open("ab") as handle:
                handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            yield chunk
        self.complete = True

    async def aclose(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            body = self.path.read_bytes()
            # The SDK closes an SSE stream immediately on DONE, before HTTP EOF. A complete
            # terminal protocol event is sufficient; non-streaming JSON requires HTTP EOF.
            status = self.status if self.streaming or self.complete else 0
            self.ledger.finish(self.request_id, body, status, self.streaming)
        finally:
            await self.stream.aclose()


class BudgetTransport(httpx.AsyncBaseTransport):
    """Each actual HTTP send is admitted; retries and concurrent recovery cannot bypass it."""

    def __init__(self, inner: httpx.AsyncBaseTransport, ledger: Ledger) -> None:
        self.inner, self.ledger = inner, ledger

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method != "POST" or str(request.url) != "https://api.deepseek.com/v1/chat/completions":
            self.ledger.stop("unexpected provider route")
            raise AdmissionStopped("unexpected provider route")
        body = await request.aread()
        data = json.loads(body)
        output_cap = data.get("max_tokens")
        if (data.get("model") != MODEL or type(output_cap) is not int
                or not 1 <= output_cap <= MAX_OUTPUT or data.get("n", 1) != 1
                or data.get("thinking") != {"type": "disabled"}):
            self.ledger.stop("unpriced provider request configuration")
            raise AdmissionStopped("unpriced provider request configuration")
        # Capture protocol bytes directly; do not negotiate compressed SSE/JSON bodies.
        request.headers["Accept-Encoding"] = "identity"
        request_id = self.ledger.reserve(body, output_cap)
        try:
            response = await self.inner.handle_async_request(request)
            response.stream = CapturedStream(response.stream, self.ledger, request_id,
                                             response.status_code, bool(data.get("stream")))
            return response
        except BaseException:
            # Cancellation/connection loss can still have incurred usage. No refund.
            self.ledger.finish(request_id, b"", 0, bool(data.get("stream")))
            raise

    async def aclose(self) -> None:
        await self.inner.aclose()
