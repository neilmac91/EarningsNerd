"""Authenticated Cloud Tasks receiver. Acknowledgement follows successful persistence."""
from __future__ import annotations

import logging

import httpx
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import ValidationError

from app.services.task_process_service import run_task_process as run_background_task
from app.services.durable_tasks import TaskEnvelope, TaskUnavailable, verify_task_identity

router = APIRouter()
logger = logging.getLogger(__name__)


async def require_task_identity(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Task identity required")
    try:
        await verify_task_identity(authorization[7:])
    except TaskUnavailable as exc:
        raise HTTPException(503, "Task worker is not configured") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Task identity verification unavailable") from exc
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise HTTPException(401, "Invalid task identity") from exc


@router.post("/tasks/execute", dependencies=[Depends(require_task_identity)])
async def execute_task(envelope: TaskEnvelope) -> dict:
    try:
        await run_background_task(envelope)
    except ValidationError as exc:
        raise HTTPException(422, "Invalid task payload") from exc
    except Exception as exc:
        logger.exception("Durable task failed kind=%s", envelope.kind)
        raise HTTPException(503, "Task failed; retry delivery") from exc
    logger.info("Durable task completed kind=%s", envelope.kind)
    return {"status": "completed"}
