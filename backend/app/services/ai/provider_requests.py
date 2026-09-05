"""Bounded, call-local summary requests; provider credentials never cross an implicit route."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from urllib.parse import urlsplit

import httpx
import httpx2
from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.config import settings
from app.services.ai.model_flags import _thinking_disabled_model
from app.services.ai_metrics import record_ai_call, record_ai_summary

SUMMARY_SECONDS = 75.0
ATTEMPT_SECONDS = 45.0
MAX_SUMMARY_ATTEMPTS = 3


class MalformedCompletion(ValueError):
    """The provider returned no usable completion; no old response may be reused."""


@dataclass
class RequestBudget:
    deadline: float
    summary_attempts: int = 0
    records: list[dict] = field(default_factory=list)

    def remaining(self) -> float:
        seconds = self.deadline - asyncio.get_running_loop().time()
        if seconds <= 0:
            raise TimeoutError("Summary request budget exhausted")
        return seconds


_budget: ContextVar[RequestBudget | None] = ContextVar("summary_request_budget", default=None)


def bounded_summary(*, report: bool = False):
    """Child recovery tasks inherit the same deadline/list; independent summaries never do."""

    def decorate(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            budget = _budget.get()
            token = None
            if budget is None:
                budget = RequestBudget(asyncio.get_running_loop().time() + SUMMARY_SECONDS)
                token = _budget.set(budget)
            outcome = "error"
            try:
                async with asyncio.timeout(budget.remaining()):
                    result = await func(*args, **kwargs)
                outcome = result.get("status", "complete") if isinstance(result, dict) else "success"
                return result
            except asyncio.CancelledError:
                outcome = "cancelled"
                raise
            except TimeoutError:
                outcome = "timeout"
                raise
            finally:
                if report:
                    record_ai_summary(budget.records, outcome)
                if token is not None:
                    _budget.reset(token)

        return wrapped

    return decorate


def transient(error: Exception) -> bool:
    if isinstance(error, APIStatusError):
        return error.status_code in (408, 409, 429) or error.status_code >= 500
    if isinstance(
        error, (APIConnectionError, httpx.TransportError, httpx2.TransportError, TimeoutError, MalformedCompletion)
    ):
        return True
    if isinstance(error, APIError):
        body = error.body if isinstance(error.body, dict) else {}
        status = body.get("status") or body.get("status_code")
        if type(status) is int:
            return status in (408, 409, 429) or status >= 500
        return body.get("type") in {"rate_limit_error", "server_error", "overloaded_error"} or body.get("code") in {
            "rate_limit_exceeded",
            "server_error",
            "service_unavailable",
        }
    return False


def retry_delay(error: Exception, attempt: int) -> float:
    """Respect a numeric Retry-After within a five-second cap; never extend the deadline."""
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {})
    try:
        delay = float(headers.get("retry-after", ""))
        if delay >= 0:
            return min(delay, 5.0)
    except (TypeError, ValueError):
        pass
    return min(0.25 * (2**attempt), 2.0)


def fallback_client() -> AsyncOpenAI | None:
    """A different HTTPS origin requires its own explicitly configured credential."""
    url, model = settings.AI_FALLBACK_BASE_URL.strip(), settings.AI_FALLBACK_MODEL.strip()
    if not model:
        return None
    url = url or settings.OPENAI_BASE_URL
    target, primary = urlsplit(url), urlsplit(settings.OPENAI_BASE_URL)
    if (
        target.scheme != "https"
        or not target.hostname
        or target.username
        or target.password
        or target.query
        or target.fragment
    ):
        raise ValueError("AI fallback requires an HTTPS API base URL without credentials/query/fragment")
    same_origin = (target.scheme, target.hostname, target.port or 443) == (
        primary.scheme,
        primary.hostname,
        primary.port or 443,
    )
    key = settings.AI_FALLBACK_API_KEY.strip() or (settings.OPENAI_API_KEY if same_origin else "")
    if not key:
        raise ValueError("AI fallback on another origin requires AI_FALLBACK_API_KEY")
    return AsyncOpenAI(api_key=key, base_url=url, max_retries=0)


async def close_stream(stream) -> None:
    closer = getattr(stream, "close", None) or getattr(stream, "aclose", None)
    if closer is not None:
        await closer()


class _ProviderRequestsMixin:
    @bounded_summary()
    async def _request_content(
        self,
        kwargs: dict,
        *,
        operation: str = "summary_primary",
        stream_cb=None,
        filing_type_key: str = "10-K",
        xbrl_metrics=None,
        timeout: float = ATTEMPT_SECONDS,
    ) -> str:
        budget = _budget.get()
        recovery = operation == "section_recovery"
        local_attempt = 0
        last_error = None
        primary_timed_out = False
        while local_attempt < (2 if recovery else MAX_SUMMARY_ATTEMPTS):
            budget.remaining()
            if not recovery and budget.summary_attempts >= MAX_SUMMARY_ATTEMPTS:
                break
            ordinal = local_attempt if recovery else budget.summary_attempts
            use_fallback = self.fallback_client is not None and (primary_timed_out or ordinal >= (1 if recovery else 2))
            client = self.fallback_client if use_fallback else self.client
            model = settings.AI_FALLBACK_MODEL if use_fallback else kwargs["model"]
            base_url = (
                (settings.AI_FALLBACK_BASE_URL or settings.OPENAI_BASE_URL)
                if use_fallback
                else settings.OPENAI_BASE_URL
            )
            request = dict(kwargs, model=model)
            request.pop("extra_body", None)
            if _thinking_disabled_model(model, base_url):
                request["extra_body"] = {"thinking": {"type": "disabled"}}
            elif "max_tokens" in request:
                request["max_tokens"] = min(request["max_tokens"], 8192)
            streaming = stream_cb is not None and ordinal == 0
            request.pop("stream_options", None)
            request.pop("stream", None)
            if streaming:
                request.update(stream=True, stream_options={"include_usage": True})
            observation = {"model": None, "usage": None}
            outcome = "error"
            local_attempt += 1
            if not recovery:
                budget.summary_attempts += 1
            try:
                async with asyncio.timeout(min(timeout, budget.remaining())):
                    if streaming:
                        content = await self._stream_collect(
                            request, stream_cb, filing_type_key, xbrl_metrics, _client=client, _observation=observation
                        )
                    else:
                        response = await client.chat.completions.create(**request)
                        observation.update(
                            model=getattr(response, "model", None), usage=getattr(response, "usage", None)
                        )
                        choices = getattr(response, "choices", None)
                        content = getattr(choices[0].message, "content", None) if choices else None
                    if not isinstance(content, str) or not content.strip():
                        raise MalformedCompletion("Provider returned no usable content")
                    outcome = "success"
                    return content
            except asyncio.CancelledError:
                outcome = "cancelled"
                raise
            except Exception as error:
                outcome = "timeout" if isinstance(error, TimeoutError) else "error"
                last_error = error
                if isinstance(error, (TimeoutError, APITimeoutError, httpx.TimeoutException, httpx2.TimeoutException)):
                    primary_timed_out = True
                if not transient(error):
                    raise
            finally:
                budget.records.append(
                    record_ai_call(
                        operation="section_recovery"
                        if recovery
                        else ("summary_fallback" if use_fallback else "summary_primary"),
                        provider="fallback" if use_fallback else "primary",
                        actual_model=observation["model"],
                        usage=observation["usage"],
                        outcome=outcome,
                    )
                )
            if local_attempt < (2 if recovery else MAX_SUMMARY_ATTEMPTS) and (
                recovery or budget.summary_attempts < MAX_SUMMARY_ATTEMPTS
            ):
                await asyncio.sleep(min(retry_delay(last_error, local_attempt - 1), budget.remaining()))
        raise last_error or RuntimeError("Summary attempt budget exhausted")
