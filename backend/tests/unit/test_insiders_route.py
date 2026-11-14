"""GET /api/companies/{ticker}/insiders (ADR 0009): off unless the flag, then a signed-in beta account only,
always answered from the database, with one scan step handed off when one is due.

Rows live in the suite's database and are deleted afterwards. The handoff is recorded, never made: no test here
reaches the queue or SEC (the conftest's network gate fails any that would).
"""
import ast
import random
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from app.config import Settings, settings
from app.database import SessionLocal
from app.dependencies import _resolve_current_user
from app.models import Company, User
from app.models.insider import InsiderFiling, InsiderScan, InsiderTransaction
from app.routers import insiders as insiders_mod
from app.services import insider_scan_service
from app.services.rate_limiter import RateLimiter
from app.utils.datetimes import utcnow

APP_DIR = Path(__file__).resolve().parents[2] / "app"


@pytest.fixture
def company():
    """A stored company with a CIK and ticker no other test uses, and no insider rows left behind."""
    cik = str(random.SystemRandom().randrange(7_000_000_000, 7_999_999_999))
    ticker = f"I{cik[-5:]}"
    with SessionLocal() as db:
        db.add(Company(cik=cik.zfill(10), ticker=ticker, name="Insider Test Co"))
        db.commit()
    yield ticker, cik
    with SessionLocal() as db:
        for model in (InsiderTransaction, InsiderFiling, InsiderScan):
            db.query(model).filter(model.issuer_cik == cik).delete(synchronize_session=False)
        db.query(Company).filter(Company.ticker == ticker).delete(synchronize_session=False)
        db.commit()


@pytest.fixture
def handoffs(monkeypatch):
    """The flag on, fresh limits, and every handoff recorded instead of made."""
    made = []

    async def request_scan(cik):
        made.append(cik)
        return True

    monkeypatch.setattr(settings, "ENABLE_INSIDER_ACTIVITY", True)
    monkeypatch.setattr(insiders_mod.insider_scan_service, "request_scan", request_scan)
    monkeypatch.setattr(insiders_mod, "_insiders_rate_limiter", RateLimiter(limit=30, window_seconds=60))
    monkeypatch.setattr(insiders_mod, "_scan_handoffs", RateLimiter(limit=4, window_seconds=60))
    monkeypatch.setattr(insiders_mod, "_handed_off", {})
    return made


def signed_in(*, beta: bool):
    user = User(id=random.SystemRandom().randrange(10**8, 10**9), email="reader@example.test", is_active=True, is_beta=beta)
    main.app.dependency_overrides[_resolve_current_user] = lambda: user
    return user


@pytest.fixture
def client():
    yield TestClient(main.app)
    main.app.dependency_overrides.pop(_resolve_current_user, None)


def test_while_the_flag_is_off_everyone_gets_an_unknown_paths_404_and_nothing_is_read(client, company, handoffs, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_INSIDER_ACTIVITY", False)
    monkeypatch.setattr(insiders_mod.insider_service, "read_insider_activity",
                        lambda *args, **kwargs: pytest.fail("read while the flag is off"))
    unknown = client.get("/api/companies/AAPL/no-such-route")
    for sign_in in (None, False, True):
        if sign_in is not None:
            signed_in(beta=sign_in)
        for query in ("", "?window_days=0", "?window_days=abc"):
            response = client.get(f"/api/companies/{company[0]}/insiders{query}")
            assert (response.status_code, response.json()) == (unknown.status_code, unknown.json()) == (404, {"detail": "Not Found"})
    assert handoffs == []
    assert Settings.model_fields["ENABLE_INSIDER_ACTIVITY"].default is False


def test_a_caller_who_is_not_signed_in_gets_401_and_one_who_is_not_a_beta_tester_gets_403(client, company, handoffs):
    assert client.get(f"/api/companies/{company[0]}/insiders").status_code == 401
    signed_in(beta=False)
    refused = client.get(f"/api/companies/{company[0]}/insiders")
    assert (refused.status_code, refused.json()) == (403, {"detail": "This is available to beta testers."})
    assert handoffs == []
    with SessionLocal() as db:
        assert db.query(InsiderScan).filter(InsiderScan.issuer_cik == company[1]).count() == 0


def test_a_beta_readers_first_visit_is_answered_at_once_with_nothing_stored_and_hands_one_step_off(client, company, handoffs):
    ticker, cik = company
    signed_in(beta=True)
    response = client.get(f"/api/companies/{ticker.lower()}/insiders")

    assert response.status_code == 200
    body = response.json()
    assert (body["ticker"], body["cik"], body["transactions"], body["total_transactions"], body["window_days"]) == (ticker, cik, [], 0, 90)
    assert body["scan"] == {"status": "scanning", "filings_listed": 0, "filings_read": 0, "oldest_filed_date": None,
                            "refreshed_at": None, "retry_after_seconds": insider_scan_service.POLL_SECONDS}
    assert "scan_due" not in body
    assert handoffs == [cik]

    for _ in range(5):   # a page that polls while the first step is still queued
        assert client.get(f"/api/companies/{ticker}/insiders").status_code == 200
    assert handoffs == [cik]


def test_stored_trades_are_served_with_the_scans_progress_and_no_handoff_when_none_is_due(client, company, handoffs):
    ticker, cik = company
    now = utcnow()
    with SessionLocal() as db:
        db.add(InsiderScan(issuer_cik=cik, status="idle", pauses=0, steps=2, last_listed_at=now - timedelta(minutes=5),
                           created_at=now, updated_at=now - timedelta(minutes=5)))
        db.add(InsiderFiling(accession="0007000000-26-000001", issuer_cik=cik, filed_date=now.date() - timedelta(days=3),
                             status="ok", created_at=now, updated_at=now))
        db.add(InsiderTransaction(accession="0007000000-26-000001", ordinal=0, issuer_cik=cik, insider_name="Jane Doe",
                                  insider_title="Chief Financial Officer", is_officer=True, ticker=ticker,
                                  transaction_date=now.date() - timedelta(days=4), transaction_code="P",
                                  transaction_label="Purchase", shares=100.0, price=10.0, value=1000.0,
                                  acquired_disposed="A", is_10b5_1=False, filed_date=now.date() - timedelta(days=3),
                                  created_at=now))
        db.commit()
    signed_in(beta=True)
    body = client.get(f"/api/companies/{ticker}/insiders", params={"window_days": 30}).json()

    assert (body["window_days"], body["total_transactions"], body["summary"]["buy_count"], body["summary"]["buy_shares"]) == (30, 1, 1, 100.0)
    assert (body["transactions"][0]["insider_name"], body["transactions"][0]["value"]) == ("Jane Doe", 1000.0)
    assert (body["scan"]["status"], body["scan"]["filings_listed"], body["scan"]["filings_read"],
            body["scan"]["retry_after_seconds"]) == ("complete", 1, 1, None)
    assert handoffs == []


def test_a_paused_scan_is_reported_with_when_to_ask_again_and_is_not_handed_off(client, company, handoffs):
    ticker, cik = company
    now = utcnow()
    with SessionLocal() as db:
        db.add(InsiderScan(issuer_cik=cik, status="paused", pauses=1, steps=1, error_code="sec_403",
                           paused_until=now + timedelta(minutes=4), created_at=now, updated_at=now - timedelta(minutes=1)))
        db.commit()
    signed_in(beta=True)
    scan = client.get(f"/api/companies/{ticker}/insiders").json()["scan"]

    assert scan["status"] == "paused" and insider_scan_service.POLL_SECONDS < scan["retry_after_seconds"] <= insider_scan_service.MAX_POLL_SECONDS
    assert "error_code" not in scan and handoffs == []


def test_a_ticker_no_stored_company_has_is_404_for_a_beta_reader(client, handoffs):
    signed_in(beta=True)
    response = client.get("/api/companies/ZZNOSUCH/insiders")
    assert (response.status_code, response.json()) == (404, {"detail": "Company not found"})
    assert handoffs == []


def test_the_limit_is_per_account_not_per_address(client, company, handoffs, monkeypatch):
    monkeypatch.setattr(insiders_mod, "_insiders_rate_limiter", RateLimiter(limit=3, window_seconds=60))
    signed_in(beta=True)
    for _ in range(3):
        assert client.get(f"/api/companies/{company[0]}/insiders").status_code == 200
    blocked = client.get(f"/api/companies/{company[0]}/insiders")
    assert blocked.status_code == 429 and "Retry-After" in blocked.headers

    from app.services import rate_limiter

    monkeypatch.setattr(rate_limiter, "get_client_ip", lambda request: "203.0.113.9")   # the same account, elsewhere
    assert client.get(f"/api/companies/{company[0]}/insiders").status_code == 429

    signed_in(beta=True)   # another account, from the same address
    assert client.get(f"/api/companies/{company[0]}/insiders").status_code == 200


def test_the_process_hands_off_only_so_many_scans_a_minute_and_serves_the_rest_from_the_store(client, handoffs, monkeypatch):
    monkeypatch.setattr(insiders_mod, "_scan_handoffs", RateLimiter(limit=2, window_seconds=60))
    signed_in(beta=True)
    ciks = [str(7_100_000_000 + n) for n in range(3)]
    with SessionLocal() as db:
        for n, cik in enumerate(ciks):
            db.add(Company(cik=cik.zfill(10), ticker=f"IBUD{n}", name=f"Budget {n}"))
        db.commit()
    try:
        statuses = [client.get(f"/api/companies/IBUD{n}/insiders").status_code for n in range(3)]
        assert (statuses, handoffs) == ([200, 200, 200], ciks[:2])
        # Past the budget nothing was recorded for the third, so it is handed off once the window allows.
        monkeypatch.setattr(insiders_mod, "_scan_handoffs", RateLimiter(limit=2, window_seconds=60))
        assert client.get("/api/companies/IBUD2/insiders").status_code == 200
        assert handoffs == ciks
    finally:
        with SessionLocal() as db:
            db.query(Company).filter(Company.ticker.in_([f"IBUD{n}" for n in range(3)])).delete(synchronize_session=False)
            db.commit()


def test_the_route_no_longer_has_a_long_request_timeout():
    assert main.get_timeout_for_path("/api/companies/AAPL/insiders") == main.REQUEST_TIMEOUT_SECONDS["default"]


def test_a_handoff_the_queue_did_not_take_is_asked_for_again_on_the_readers_next_request(client, company, handoffs, monkeypatch):
    taken = []

    async def request_scan(cik):
        taken.append(cik)
        return len(taken) > 1   # the queue is unavailable the first time

    monkeypatch.setattr(insiders_mod.insider_scan_service, "request_scan", request_scan)
    signed_in(beta=True)
    for _ in range(3):
        assert client.get(f"/api/companies/{company[0]}/insiders").status_code == 200
    assert taken == [company[1], company[1]]   # asked again once, then remembered


def test_the_memo_of_handoffs_is_bounded(client, company, handoffs, monkeypatch):
    monkeypatch.setattr(insiders_mod, "_HANDED_OFF_ENTRIES", 2)
    monkeypatch.setattr(insiders_mod, "_handed_off", {"1": 1e18, "2": 1e18})
    signed_in(beta=True)
    assert client.get(f"/api/companies/{company[0]}/insiders").status_code == 200
    assert list(insiders_mod._handed_off) == ["2", company[1]]   # the oldest entry made room


def test_the_requests_session_holds_no_connection_while_the_handoff_is_awaited(client, company, monkeypatch):
    """The read finishes before the queue await: a connection held across it starves the pool under a burst
    (lessons/ops-release-cached-filing-reads-before-yield.md)."""
    from sqlalchemy import event

    from app.database import engine

    out, during = [0], []

    def checked_out(*args):
        out[0] += 1

    def checked_in(*args):
        out[0] -= 1

    async def request_scan(cik):
        during.append(out[0])
        return True

    monkeypatch.setattr(settings, "ENABLE_INSIDER_ACTIVITY", True)
    monkeypatch.setattr(insiders_mod, "_handed_off", {})
    monkeypatch.setattr(insiders_mod, "_scan_handoffs", RateLimiter(limit=4, window_seconds=60))
    monkeypatch.setattr(insiders_mod.insider_scan_service, "request_scan", request_scan)
    signed_in(beta=True)
    event.listen(engine, "checkout", checked_out)
    event.listen(engine, "checkin", checked_in)
    try:
        assert client.get(f"/api/companies/{company[0]}/insiders").status_code == 200
    finally:
        event.remove(engine, "checkout", checked_out)
        event.remove(engine, "checkin", checked_in)
    assert during == [0]


def test_a_scan_is_requested_only_by_the_insiders_route_behind_its_beta_check_and_budget():
    """``request_scan`` queues a task (exempt in test_durable_task_payloads_server_owned.py as a service-side
    enqueue). Its one caller is the route's handoff helper, which spends the process's budget first, and that
    helper's one caller is the route that takes a signed-in beta account."""
    def callers_of(name):
        found = []
        for path in sorted(APP_DIR.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for call in ast.walk(node):
                        if isinstance(call, ast.Call) and getattr(call.func, "attr", getattr(call.func, "id", None)) == name:
                            found.append((path.relative_to(APP_DIR).as_posix(), node.name))
        return found

    assert callers_of("request_scan") == [("routers/insiders.py", "_hand_off")]
    assert callers_of("_hand_off") == [("routers/insiders.py", "get_company_insiders")]

    functions = {node.name: node for node in ast.walk(ast.parse((APP_DIR / "routers/insiders.py").read_text(encoding="utf-8")))
                 if isinstance(node, ast.AsyncFunctionDef)}
    assert "Depends(require_beta)" in [ast.unparse(default) for default in functions["get_company_insiders"].args.defaults]
    handoff = next(node for node in ast.walk(functions["get_company_insiders"]) if isinstance(node, ast.If) and "_hand_off" in ast.unparse(node))
    assert ast.unparse(handoff.test) == "activity.pop('scan_due')"
    steps = [ast.unparse(statement) for statement in functions["_hand_off"].body]
    budget = next(i for i, step in enumerate(steps) if "_scan_handoffs.allow('insider-scan')" in step)
    asked = next(i for i, step in enumerate(steps) if "request_scan" in step)
    assert budget < asked and steps[budget].startswith("if not _scan_handoffs.allow('insider-scan'):\n    return")
