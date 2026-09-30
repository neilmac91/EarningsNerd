"""Consent-gated observations of one authenticated HTTP summary request.

Request outcomes describe what the server offered, not browser receipt or provider billing.
Client action/retry labels are untrusted correlation hints; request and account IDs are server-owned.
An absent terminal (for example process loss) remains unknown in the readout.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import time
from typing import Any
from uuid import UUID, uuid4

import anyio

from app.services.posthog_client import capture_funnel_event


class SummaryRequestEvidence:
    def __init__(
        self, *, consent: bool, account_id: int, filing_id: int,
        logical_request_id: UUID | None, client_attempt: int | None,
        transport_attempt: int | None, entry_point: str | None,
    ) -> None:
        self.enabled = consent
        self.account_id = str(account_id)
        self.properties: dict[str, Any] = {
            "evidence_version": 1, "request_id": str(uuid4()),
            "logical_request_id": str(logical_request_id) if logical_request_id else None,
            "client_attempt": client_attempt, "transport_attempt": transport_attempt,
            "account_id_at_event": self.account_id, "auth_state_at_event": "authenticated",
            "identity_evidence": "server_authenticated", "filing_id": filing_id,
            "analytics_consent_at_event": True, "consent_evidence": "client_declaration",
            "entry_point": (entry_point or "")[:64] or None,
        }
        self.delivery_path = "route"
        self.summary_service_invoked = False
        self.reason: str | None = None
        self.started_at: float | None = None
        self.finished = False

    def start(self) -> None:
        if self.started_at is not None:
            return
        self.started_at = time.monotonic()
        if self.enabled:
            capture_funnel_event(self.account_id, "summary_request_started", **self.properties)

    def finish(self, outcome: str, *, summary_id: int | None = None) -> None:
        if self.finished:
            return
        self.start()
        self.finished = True
        if self.enabled:
            capture_funnel_event(
                self.account_id, "summary_request_finished", **self.properties,
                outcome=outcome, reason=self.reason, summary_id=summary_id,
                delivery_path=self.delivery_path, summary_service_invoked=self.summary_service_invoked,
                duration_ms=max(0, int((time.monotonic() - self.started_at) * 1000)),
            )

    def observe_terminal(self, event: dict) -> None:
        kind = event.get("type")
        if kind in {"complete", "partial", "error"}:
            outcome = "timed_out" if self.reason == "pipeline_timeout" else kind
            self.finish(outcome, summary_id=event.get("summary_id"))

    async def wrap_stream(self, stream: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
        """Own stream closure, including suspension at a yielded frame on disconnect."""
        self.start()
        try:
            async for frame in stream:
                yield frame
        except (asyncio.CancelledError, GeneratorExit):
            self.finish("cancelled")
            raise
        except Exception:
            self.finish("error")
            raise
        else:
            self.finish("incomplete")
        finally:
            with anyio.CancelScope(shield=True):
                await stream.aclose()
