"""Keep private feedback content out of error reporting, including SDK SQL breadcrumbs."""
from contextvars import ContextVar
from urllib.parse import urlsplit

private_feedback_request: ContextVar[bool] = ContextVar("private_feedback_request", default=False)


def is_private_feedback_path(value: str) -> bool:
    try:
        path = urlsplit(value).path
    except ValueError:
        return False
    return any(path == prefix or path.startswith(prefix + "/")
               for prefix in ("/api/feedback", "/api/admin/feedback"))


def withhold_feedback_event(item: dict) -> bool:
    # The context covers log/metric channels which omit request data. The URL covers an
    # HTTP event/transaction serialized after the middleware's request context has ended.
    if private_feedback_request.get():
        return True
    request = item.get("request")
    return isinstance(request, dict) and isinstance(request.get("url"), str) and is_private_feedback_path(request["url"])
