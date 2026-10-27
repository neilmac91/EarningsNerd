"""Gate: one error-code vocabulary on both sides of the wire, and a coded refusal that keeps its answer (E31).

`app/error_codes.py` holds the codes a producer may send (ErrorCode), the HTTP status each is sent with
(REGISTERED_STATUS) and the codes a stream's error event may carry (STREAM_CODES). The browser honours a code only
where it is registered (`frontend/lib/api/client.ts` ERROR_CODES, read by parseErrorCode), and the contract
(`docs/audit/contracts/error-codes.md` §3) states the same table for the agents who add producers. A code added,
dropped or moved to another status on one side alone fails here: the browser would ignore it, or honour it where the
backend never sends it.

The handler and the exception are checked through a real app: a CodedHTTPException answers with the status, headers
and detail of the HTTPException it replaces plus `code`, and, before `main.py` registers the handler, exactly as
that HTTPException did, so a producer can land first.
"""
import re
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api_errors import CodedHTTPException, coded_http_exception_handler
from app.error_codes import REGISTERED_STATUS, STREAM_CODES, ErrorCode, sse_error

REPO = Path(__file__).resolve().parents[3]
CLIENT = REPO / "frontend" / "lib" / "api" / "client.ts"
CONTRACT = REPO / "docs" / "audit" / "contracts" / "error-codes.md"


def _backend_table() -> dict[str, tuple[int, bool]]:
    return {code.value: (REGISTERED_STATUS[code], code in STREAM_CODES) for code in ErrorCode}


def _client_table() -> dict[str, tuple[int, bool]]:
    source = CLIENT.read_text(encoding="utf-8")
    block = re.search(r"export const ERROR_CODES = \{\n(.*?)\n\} as const", source, re.S)
    assert block, "ERROR_CODES not found in frontend/lib/api/client.ts"
    rows = re.findall(r"^\s*(\w+): \{ status: (\d+), stream: (true|false) \},$", block.group(1), re.M)
    # Every line of the block is a row the pattern reads, so a row written another way fails instead of vanishing.
    assert len(rows) == len(block.group(1).splitlines()), block.group(1)
    return {name: (int(status), stream == "true") for name, status, stream in rows}


def _contract_table() -> dict[str, tuple[int, bool]]:
    section = CONTRACT.read_text(encoding="utf-8").split("## 3. Vocabulary", 1)[1].split("\n## ", 1)[0]
    table = {}
    for code, channel in re.findall(r"^\| `(\w+)` \| ([^|]+) \|", section, re.M):
        status = re.match(r"(\d{3})", channel.strip())
        assert status, f"{code}: no status in {channel!r}"
        table[code] = (int(status.group(1)), "SSE" in channel)
    return table


def test_the_client_knows_exactly_the_backend_s_codes_on_their_statuses_and_channels():
    assert _client_table() == _backend_table()


def test_the_contract_states_the_same_table():
    assert _contract_table() == _backend_table()


def test_every_code_is_spelled_as_the_contract_requires():
    assert all(re.fullmatch(r"[a-z][a-z0-9_]{2,63}", code.value) for code in ErrorCode)
    assert set(REGISTERED_STATUS) == set(ErrorCode)


def _app(*, registered: bool) -> FastAPI:
    app = FastAPI()
    if registered:
        app.add_exception_handler(CodedHTTPException, coded_http_exception_handler)

    @app.get("/coded")
    def coded():
        raise CodedHTTPException(ErrorCode.AUTH_REQUIRED, "You are not logged in.", headers={"WWW-Authenticate": "Bearer"})

    @app.get("/plain")
    def plain():
        raise HTTPException(status_code=401, detail="You are not logged in.", headers={"WWW-Authenticate": "Bearer"})

    return app


def test_a_coded_refusal_answers_as_the_plain_one_did_plus_its_code():
    with TestClient(_app(registered=True)) as client:
        coded, plain = client.get("/coded"), client.get("/plain")
    assert (coded.status_code, coded.headers["www-authenticate"]) == (plain.status_code, plain.headers["www-authenticate"])
    assert plain.json() == {"detail": "You are not logged in."}
    assert coded.json() == {"detail": "You are not logged in.", "code": "auth_required"}


def test_before_main_registers_the_handler_a_coded_refusal_answers_exactly_as_the_plain_one():
    with TestClient(_app(registered=False)) as client:
        coded, plain = client.get("/coded"), client.get("/plain")
    assert (coded.status_code, dict(coded.headers), coded.content) == (plain.status_code, dict(plain.headers), plain.content)


@pytest.mark.parametrize("code", list(ErrorCode), ids=lambda code: code.value)
def test_a_coded_refusal_takes_its_code_s_registered_status(code):
    assert CodedHTTPException(code, "Words.").status_code == REGISTERED_STATUS[code]


def test_a_stream_error_event_keeps_its_keys_and_adds_its_code():
    assert sse_error("Words.", ErrorCode.PRO_FAIR_USE_LIMIT) == {
        "type": "error", "message": "Words.", "code": "pro_fair_use_limit",
    }
    assert sse_error("Words.", ErrorCode.FREE_ALLOWANCE_EXHAUSTED, summary_id=7)["summary_id"] == 7


@pytest.mark.parametrize("code", sorted(set(ErrorCode) - STREAM_CODES), ids=lambda code: code.value)
def test_a_code_the_client_ignores_on_a_stream_is_refused_there(code):
    with pytest.raises(ValueError, match="not a stream code"):
        sse_error("Words.", code)
