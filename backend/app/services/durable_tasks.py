"""Small HTTP-target Cloud Tasks adapter; no credentials or filing documents enter task bodies.

The metadata server supplies the runtime identity. Deterministic names make an ambiguous create
safe to retry; HTTP success at the worker means the existing service has finished persistence.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from typing import Literal
from urllib.parse import urlsplit

import httpx
import jwt
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.services.oauth_verify import _get_google_jwks, _GOOGLE_ISSUERS


class TaskUnavailable(RuntimeError):
    """The durable handoff was not confirmed; callers must not claim accepted work."""


class TaskEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["filings", "history", "companyfacts", "internal_job", "probe"]
    payload: dict


class CompanyTask(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    company_id: int = Field(gt=0)


class FilingsTask(CompanyTask):
    filing_types: list[str] = Field(min_length=1)


_token: str = ""
_token_expires: float = 0


def _queue_path() -> str:
    """Reject incomplete rollout configuration before touching metadata or the network."""
    parts = (settings.TASKS_PROJECT_ID, settings.TASKS_LOCATION, settings.TASKS_QUEUE)
    worker = urlsplit(settings.TASKS_WORKER_URL)
    if (
        not settings.DURABLE_TASKS_ENABLED
        or not all(parts)
        or any("/" in part for part in parts)
        or worker.scheme != "https"
        or not worker.hostname
        or not worker.hostname.endswith(".run.app")
        or worker.path not in ("", "/")
        or worker.query or worker.fragment or worker.username
        or not settings.TASKS_INVOKER_EMAIL.endswith(".iam.gserviceaccount.com")
    ):
        raise TaskUnavailable("Durable tasks are not configured")
    return f"projects/{parts[0]}/locations/{parts[1]}/queues/{parts[2]}"


async def _access_token() -> str:
    global _token, _token_expires
    if _token and time.monotonic() < _token_expires:
        return _token
    # Fixed infrastructure endpoint: task/user input cannot choose a metadata URL.
    async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
        response = await client.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"},
        )
        response.raise_for_status()
        data = response.json()
    _token = data["access_token"]
    _token_expires = time.monotonic() + max(0, int(data["expires_in"]) - 60)
    return _token


async def enqueue_task(
    kind: str, payload: dict, *, dedupe_key: str | None = None,
    dedupe_seconds: int | None = None,
) -> str:
    """Confirm creation (or an existing same-name task) before returning to the caller.

    A stable batch child key omits the time bucket. On-visit keys use a bounded bucket so a failed
    task's 24-hour name tombstone cannot suppress later visits indefinitely. Business services
    remain idempotent because delivery, including after successful responses, can be duplicated.
    """
    queue = _queue_path()
    envelope = TaskEnvelope(kind=kind, payload=payload)
    if kind == "filings":
        FilingsTask.model_validate(payload)
    elif kind in ("history", "companyfacts"):
        CompanyTask.model_validate(payload)
    elif kind == "probe" and payload:
        raise ValueError("Probe tasks contain no business payload")
    body = json.dumps(envelope.model_dump(), sort_keys=True, separators=(",", ":"))
    if len(body.encode()) > 28_000:
        raise ValueError("Task payload exceeds the bounded control-message size")
    key = dedupe_key or uuid.uuid4().hex
    if dedupe_seconds is not None:
        if dedupe_seconds <= 0:
            raise ValueError("dedupe_seconds must be positive")
        key += f":{int(time.time()) // dedupe_seconds}"
    # Include payload and kind: accidental caller-key collisions cannot discard different work.
    digest = hashlib.sha256(f"{key}:{body}".encode()).hexdigest()
    name = f"{queue}/tasks/{digest}"
    task = {
        "name": name,
        "dispatchDeadline": "540s",
        "httpRequest": {
            "httpMethod": "POST",
            "url": settings.TASKS_WORKER_URL.rstrip("/") + "/internal/tasks/execute",
            "headers": {"Content-Type": "application/json"},
            "body": base64.b64encode(body.encode()).decode(),
            "oidcToken": {
                "serviceAccountEmail": settings.TASKS_INVOKER_EMAIL,
                "audience": settings.TASKS_WORKER_URL.rstrip("/"),
            },
        },
    }
    try:
        token = await _access_token()
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                f"https://cloudtasks.googleapis.com/v2/{queue}/tasks",
                headers={"Authorization": f"Bearer {token}"}, json={"task": task},
            )
        if response.status_code == 409:
            return name
        response.raise_for_status()
        return name
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        # Do not log request headers, metadata tokens or response bodies.
        raise TaskUnavailable("Durable task handoff failed") from exc


async def verify_task_identity(token: str) -> None:
    """Verify the worker's Authorization token; spoofable task headers grant no access.

    Cloud Tasks uses Authorization, which retains its Google-signed token at private Cloud Run.
    X-Serverless-Authorization removes the signature and is deliberately not accepted here.
    """
    _queue_path()
    jwks = await _get_google_jwks()
    kid = jwt.get_unverified_header(token).get("kid")
    key = next((key for key in jwks.get("keys", []) if key.get("kid") == kid), None)
    if key is None:
        raise ValueError("Unknown task identity key")
    claims = jwt.decode(
        token, jwt.PyJWK(key).key, algorithms=["RS256"],
        audience=settings.TASKS_WORKER_URL.rstrip("/"),
        options={"require": ["exp", "aud", "iss", "sub", "email", "email_verified"]},
        leeway=settings.JWT_LEEWAY_SECONDS,
    )
    if (
        claims["iss"] not in _GOOGLE_ISSUERS
        or claims["email"] != settings.TASKS_INVOKER_EMAIL
        or claims["email_verified"] is not True
    ):
        raise ValueError("Unexpected task identity")
