"""``main.app`` answers a coded refusal as the HTTPException it replaces did, plus its code (E31-H1).

``main.py`` registers ``app.api_errors.coded_http_exception_handler`` for ``CodedHTTPException``
(docs/audit/contracts/error-codes.md §4, "Registration"; this file is §6's item 5). No producer raises one yet, so an
override of ``get_current_user`` on ``/api/auth/me`` stands in for the first: the 401 it will raise once A's producer
lands. Through every middleware the app runs (CORS, the security headers, the correlation id), that answer keeps the
plain 401's status and headers, and its body is the plain body plus ``code``. ``test_api_error_codes.py`` holds the
handler and the exception on an app of its own.
"""
import pytest
from fastapi.testclient import TestClient

import main
from app.api_errors import CodedHTTPException, coded_http_exception_handler
from app.error_codes import REGISTERED_STATUS, ErrorCode
from app.routers.auth import get_current_user

ROUTE = "/api/auth/me"
# An allowed origin, so the CORS middleware answers, and a correlation id, which the app echoes instead of minting one.
REQUEST_HEADERS = {"Origin": "https://earningsnerd.io", "X-Correlation-ID": "e31h1probe"}


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _fresh(client):
    client.cookies.clear()
    yield
    main.app.dependency_overrides.pop(get_current_user, None)


def _refusing(code, detail, headers=None):
    def refuse():
        raise CodedHTTPException(code, detail, headers=headers)
    return refuse


def _without_length(response) -> dict[str, str]:
    """Every header but the body's length, which the added ``code`` changes."""
    return {name: value for name, value in response.headers.items() if name != "content-length"}


def test_main_app_answers_a_coded_refusal_with_the_coded_handler():
    assert main.app.exception_handlers[CodedHTTPException] is coded_http_exception_handler


def test_a_coded_refusal_answers_as_the_plain_one_did_plus_its_code(client):
    plain = client.get(ROUTE, headers=REQUEST_HEADERS)
    main.app.dependency_overrides[get_current_user] = _refusing(
        ErrorCode.AUTH_REQUIRED, "You are not logged in.", headers={"WWW-Authenticate": "Bearer"})
    coded = client.get(ROUTE, headers=REQUEST_HEADERS)
    assert plain.status_code == coded.status_code == 401
    assert plain.json() == {"detail": "You are not logged in."}
    assert coded.json() == {**plain.json(), "code": "auth_required"}
    assert _without_length(coded) == _without_length(plain)
    assert coded.headers["access-control-allow-origin"] == REQUEST_HEADERS["Origin"]
    assert coded.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("code", list(ErrorCode), ids=lambda code: code.value)
def test_every_code_answers_at_its_registered_status(client, code):
    main.app.dependency_overrides[get_current_user] = _refusing(code, "Words.")
    resp = client.get(ROUTE, headers=REQUEST_HEADERS)
    assert resp.status_code == REGISTERED_STATUS[code]
    assert resp.json() == {"detail": "Words.", "code": code.value}
