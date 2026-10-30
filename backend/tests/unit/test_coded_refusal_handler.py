"""``main.app`` answers a coded refusal as the HTTPException it replaces did, plus its code (E31-H1).

``main.py`` registers ``app.api_errors.coded_http_exception_handler`` for ``CodedHTTPException``
(docs/audit/contracts/error-codes.md §4, "Registration"; this file is §6's item 5). No producer raises one yet, so an
override of ``get_current_user`` on ``/api/auth/me`` stands in for the first, the 401 A's producer will raise, and
another override raises the plain HTTPException it replaces, so the comparison holds whatever producers land. Through
every middleware the app runs (CORS, the security headers, the correlation id), the coded answer keeps the plain
one's status and headers, and its body is the plain body plus ``code``. The other two cases §6 names, an unknown
code and a known code on the wrong status, cannot be raised through ``CodedHTTPException``: ``test_api_error_codes.py``
refuses the first and pins each code's status on the exception itself.
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main
from app.api_errors import CodedHTTPException, coded_http_exception_handler
from app.error_codes import REGISTERED_STATUS, ErrorCode
from app.routers.auth import get_current_user

ROUTE = "/api/auth/me"
# An origin the app's CORS middleware allows, read from it so a local .env cannot change the answer, and a correlation
# id, which the app echoes instead of minting one.
REQUEST_HEADERS = {"Origin": main._cors_config["allow_origins"][0], "X-Correlation-ID": "e31h1probe"}
NOT_LOGGED_IN = {"detail": "You are not logged in.", "headers": {"WWW-Authenticate": "Bearer"}}


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _fresh():
    yield
    main.app.dependency_overrides.pop(get_current_user, None)


def _answer(client, exc: HTTPException):
    """The app's answer to the route when its user dependency raises ``exc``."""
    def refuse():
        raise exc
    main.app.dependency_overrides[get_current_user] = refuse
    return client.get(ROUTE, headers=REQUEST_HEADERS)


def _without_length(response) -> dict[str, str]:
    """Every header but the body's length, which the added ``code`` changes."""
    return {name: value for name, value in response.headers.items() if name != "content-length"}


def test_main_app_answers_a_coded_refusal_with_the_coded_handler():
    assert main.app.exception_handlers[CodedHTTPException] is coded_http_exception_handler


def test_a_coded_refusal_answers_as_the_plain_one_did_plus_its_code(client):
    plain = _answer(client, HTTPException(401, **NOT_LOGGED_IN))
    coded = _answer(client, CodedHTTPException(ErrorCode.AUTH_REQUIRED, **NOT_LOGGED_IN))
    assert plain.status_code == coded.status_code == 401
    assert plain.json() == {"detail": "You are not logged in."}
    assert coded.json() == {**plain.json(), "code": "auth_required"}
    assert _without_length(coded) == _without_length(plain)
    assert coded.headers["access-control-allow-origin"] == REQUEST_HEADERS["Origin"]
    assert coded.headers["www-authenticate"] == "Bearer"


# A producer raises with no headers (most do) or with some (get_current_user's 401 carries WWW-Authenticate). Each
# code's answer is the plain HTTPException's at its status, with the same headers, plus its code. Each exception gets
# headers of its own, so a handler that edits them in place cannot also edit what its answer is compared with.
@pytest.mark.parametrize("probe", [None, "e31h1"], ids=["no-headers", "a-header"])
@pytest.mark.parametrize("code", list(ErrorCode), ids=lambda code: code.value)
def test_every_code_answers_as_its_plain_refusal_did_plus_its_code(client, code, probe):
    def headers():
        return {"X-Probe": probe} if probe else None
    plain = _answer(client, HTTPException(REGISTERED_STATUS[code], "Words.", headers=headers()))
    coded = _answer(client, CodedHTTPException(code, "Words.", headers=headers()))
    assert plain.status_code == coded.status_code == REGISTERED_STATUS[code]
    assert coded.json() == {**plain.json(), "code": code.value}
    assert _without_length(coded) == _without_length(plain)
    assert coded.headers.get("x-probe") == probe
