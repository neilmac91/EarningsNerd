"""E137: the two responses built outside ``add_security_headers`` carry its headers too.

``request_timeout_middleware`` sits outside ``add_security_headers``, so the 504 it builds never passes
back through it. Starlette answers the global ``Exception`` handler from ServerErrorMiddleware, outside
every user middleware, so the 500 does not either. /security says the API's responses under /api carry
a Content-Security-Policy of default-src 'none', so both set the headers themselves
(``main._security_headers``). Every other reply passes back through the middleware, and the last test
here fails if a middleware or a 500 handler joins these two outside it. test_security_headers.py checks
the middleware's own stamp on /health and an /api 404.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

import main

TIMEOUT_PROBE = "/api/__e137_timeout_probe"
ERROR_PROBE = "/api/__e137_error_probe"
ALLOWED_ORIGIN = "http://localhost:3000"

SECURITY_HEADERS = (
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "permissions-policy",
    "content-security-policy",
    "strict-transport-security",
)

# The set an /api reply carries outside production, where there is no HSTS.
API_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "geolocation=(), microphone=(), camera=()",
    "content-security-policy": "default-src 'none'",
}


@pytest.fixture
def probes(monkeypatch):
    """Two /api routes: one outlives its patched timeout, one raises an error nothing handles.

    Only the timeout probe's path gets the short timeout; every other request keeps the default, so a
    process's slow first request cannot turn the error probe's 500 or the 404 into a 504.
    """
    async def slow():  # pragma: no cover - never completes under the patched timeout
        await asyncio.sleep(0.5)
        return {"ok": True}

    async def broken():
        raise RuntimeError("probe failure")

    before = list(main.app.router.routes)
    main.app.add_api_route(TIMEOUT_PROBE, slow, methods=["GET"])
    main.app.add_api_route(ERROR_PROBE, broken, methods=["GET"])
    monkeypatch.setitem(main.REQUEST_TIMEOUT_SECONDS, TIMEOUT_PROBE, 0.01)
    try:
        yield TestClient(main.app, raise_server_exceptions=False)
    finally:
        main.app.router.routes[:] = before


def _security(response) -> dict[str, str]:
    return {name: response.headers[name] for name in SECURITY_HEADERS if name in response.headers}


def test_the_timeouts_504_carries_the_security_headers(probes):
    resp = probes.get(TIMEOUT_PROBE)

    assert resp.status_code == 504
    assert _security(resp) == API_HEADERS


def test_the_unhandled_errors_500_carries_the_security_headers(probes):
    resp = probes.get(ERROR_PROBE)

    assert resp.status_code == 500
    assert resp.json()["type"] == "internal_server_error"
    assert _security(resp) == API_HEADERS


def test_the_hand_built_responses_carry_what_the_middleware_stamps(probes):
    """The same set as an /api response that passes back through add_security_headers (a 404)."""
    stamped, timed_out, failed = (probes.get(path) for path in ("/api/__e137_no_such_route__", TIMEOUT_PROBE, ERROR_PROBE))

    assert (stamped.status_code, timed_out.status_code, failed.status_code) == (404, 504, 500)
    assert _security(timed_out) == _security(stamped)
    assert _security(failed) == _security(stamped)


def test_a_reply_to_the_bare_api_path_carries_the_csp_too(probes):
    resp = probes.get("/api")

    assert resp.status_code == 404
    assert _security(resp) == API_HEADERS


def test_in_production_the_504_and_the_500_carry_hsts(probes, monkeypatch):
    monkeypatch.setattr(main.settings, "ENVIRONMENT", "production")

    for path, status in ((TIMEOUT_PROBE, 504), (ERROR_PROBE, 500)):
        resp = probes.get(path)
        assert resp.status_code == status
        assert resp.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
        assert resp.headers["content-security-policy"] == "default-src 'none'"


@pytest.mark.parametrize("path, status", ((TIMEOUT_PROBE, 504), (ERROR_PROBE, 500)))
def test_from_an_allowed_origin_both_keep_their_cors_headers_beside_them(probes, path, status):
    """A browser's request carries an allowed Origin. The security headers join the CORS headers each reply
    re-applies; neither replaces the other."""
    resp = probes.get(path, headers={"origin": ALLOWED_ORIGIN})

    assert resp.status_code == status
    assert resp.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert _security(resp) == API_HEADERS


def _name(obj) -> str:
    return getattr(obj, "__name__", repr(obj))


def test_only_these_two_replies_are_built_outside_add_security_headers():
    """A middleware outside add_security_headers, or a 500 handler, builds replies that it never stamps."""
    assert not main.app.debug, (
        "in debug mode ServerErrorMiddleware answers an unhandled error with its traceback page, which carries none "
        "of the headers, and never calls global_exception_handler"
    )
    order = [_name(entry.kwargs.get("dispatch", entry.cls)) for entry in main.app.user_middleware]  # outermost first
    assert order[: order.index("add_security_headers")] == ["request_timeout_middleware"], (
        "a middleware outside add_security_headers builds replies it never stamps: set main._security_headers and "
        "main._error_response_cors_headers on them, as request_timeout_middleware does, then list it here"
    )
    # ServerErrorMiddleware, outside every user middleware, answers with one handler: the last keyed 500 or Exception.
    outside = {key: _name(handler) for key, handler in main.app.exception_handlers.items() if key in (500, Exception)}
    assert outside == {Exception: "global_exception_handler"}, (
        "Starlette answers an unhandled error with a single handler keyed 500 or Exception, outside every user "
        "middleware: keep global_exception_handler as that one, or give its replacement main._security_headers and "
        "main._error_response_cors_headers and name it here instead"
    )
