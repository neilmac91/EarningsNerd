"""Separate summary delivery from the background queue and its account-mail worker.

Configuration is checked before metadata/network access. Distinct origins reject an obvious
shared worker; deployment evidence must also establish distinct Cloud Run service resources,
because aliases can name the same service. This module opens no database or provider client.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal
from urllib.parse import urlsplit

from app.config import settings

WorkerRole = Literal["background", "summary"]


class TaskUnavailable(RuntimeError):
    """The durable handoff was not confirmed; callers must not claim accepted work."""


@dataclass(frozen=True)
class TaskRoute:
    queue: str
    worker_url: str
    invoker_email: str


def _route(queue_name: str, worker_url: str, invoker_email: str) -> TaskRoute:
    parts = (settings.TASKS_PROJECT_ID, settings.TASKS_LOCATION, queue_name)
    try:
        worker = urlsplit(worker_url)
        valid_worker = (
            worker.scheme == "https" and bool(worker.hostname)
            and worker.hostname.endswith(".run.app")
            and worker.port in (None, 443)
            and worker.path in ("", "/")
            and not (worker.query or worker.fragment or worker.username or worker.password)
        )
    except ValueError:
        valid_worker = False
    if (
        not settings.DURABLE_TASKS_ENABLED
        or not all(re.fullmatch(r"[A-Za-z0-9_-]+", part) for part in parts)
        or not valid_worker
        or not re.fullmatch(r"[A-Za-z0-9._-]+@[A-Za-z0-9.-]+\.iam\.gserviceaccount\.com", invoker_email)
    ):
        raise TaskUnavailable("Durable tasks are not configured")
    # Cloud Run's audience is the canonical origin, not its optional slash/default port.
    return TaskRoute(
        queue=f"projects/{parts[0]}/locations/{parts[1]}/queues/{parts[2]}",
        worker_url=f"https://{worker.hostname}",
        invoker_email=invoker_email,
    )


def background_route() -> TaskRoute:
    return _route(settings.TASKS_QUEUE, settings.TASKS_WORKER_URL, settings.TASKS_INVOKER_EMAIL)


def summary_route() -> TaskRoute:
    background = background_route()
    summary = _route(
        settings.SUMMARY_TASKS_QUEUE, settings.SUMMARY_TASKS_WORKER_URL,
        settings.SUMMARY_TASKS_INVOKER_EMAIL,
    )
    if summary.queue == background.queue or summary.worker_url == background.worker_url:
        raise TaskUnavailable("Summary tasks require an isolated queue and worker")
    return summary


def task_route(kind: str) -> TaskRoute:
    return summary_route() if kind == "summary" else background_route()


def worker_role() -> WorkerRole:
    role = settings.TASKS_WORKER_ROLE
    if role not in ("background", "summary"):
        raise TaskUnavailable("Task worker role is not configured")
    return role


def worker_route() -> TaskRoute:
    return summary_route() if worker_role() == "summary" else background_route()


def require_worker_kind(kind: str) -> None:
    role = worker_role()
    if kind != "probe" and (kind == "summary") != (role == "summary"):
        raise TaskUnavailable("Task kind is not served by this worker")
