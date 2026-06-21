"""Tests for the "Ask this Filing" Copilot (A2 / P1).

Covers:
* Service grounding — token events carry only prose; citations are verified against the source and
  get a ``#:~:text=`` fragment URL when found (``verified=True``) / base URL when not.
* Not-disclosed path — model emits the sentinel → a ``not_disclosed`` event, no fabricated citations.
* Endpoint gating — FREE user 403, PRO user 200 + streams.
* Metering — a PRO user's ``qa_count`` increments; exceeding the monthly cap → 429.

DB-touching tests are marked ``requires_db`` and override ``get_current_user`` with a stand-in whose
entitlements resolve to FREE vs PRO via ``is_pro`` (the ``require_entitlement`` dep resolves through
``get_current_user``). Mirrors ``test_notification_preferences_api.py``.
"""
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
from app.routers.auth import get_current_user
from app.dependencies import _resolve_current_user
from app.services import copilot_service


# --- Fakes -------------------------------------------------------------------------------------

_KNOWN_SENTENCE = "Revenue increased to 391.0 billion driven by strong iPhone demand."

_FAKE_SOURCE = (
    "Item 7 — Management's Discussion and Analysis. "
    + _KNOWN_SENTENCE
    + " Operating margins expanded year over year."
)


def _fake_filing():
    """A minimal duck-typed Filing with a content_cache + company, like the joinedload result."""
    cache = SimpleNamespace(critical_excerpt=_FAKE_SOURCE, markdown_content=None)
    company = SimpleNamespace(name="Apple Inc.", ticker="AAPL", cik="320193")
    return SimpleNamespace(
        id=1,
        filing_type="10-K",
        filing_date=None,
        document_url="https://www.sec.gov/Archives/edgar/data/320193/000.../aapl-10k.htm",
        sec_url="https://www.sec.gov/Archives/edgar/data/320193/000.../",
        xbrl_data=None,
        content_cache=cache,
        company=company,
    )


def _chunks_to_async_gen(chunks):
    async def _gen(*_args, **_kwargs):
        for c in chunks:
            yield c
    return _gen


async def _collect(filing, question, history=None):
    events = []
    async for ev in copilot_service.answer_filing_question(
        filing=filing, question=question, history=history
    ):
        events.append(ev)
    return events


# --- Service grounding -------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_grounds_verified_citation(monkeypatch):
    """A citation whose excerpt is in the source verifies True with a text-fragment URL.

    The ``===CITATIONS===`` sentinel is split across two chunks to exercise the boundary handling.
    """
    citations_json = (
        '[{"n":1,"excerpt":"' + _KNOWN_SENTENCE + '","section":"Item 7 — MD&A"}]'
    )
    chunks = [
        "Apple's revenue grew strongly [1].",
        " ===CITA",                      # sentinel split across this chunk ...
        "TIONS===\n" + citations_json,    # ... and this one
    ]
    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat", _chunks_to_async_gen(chunks)
    )

    events = await _collect(_fake_filing(), "How did revenue do?")

    types = [e["type"] for e in events]
    assert types[0] == "progress"
    assert "complete" in types

    token_text = "".join(e["text"] for e in events if e["type"] == "token")
    assert "Apple's revenue grew strongly [1]." in token_text
    # No sentinel/citation JSON leaked into the streamed prose.
    assert "===CITATIONS===" not in token_text
    assert "excerpt" not in token_text

    complete = next(e for e in events if e["type"] == "complete")
    assert complete["kind"] == "answer"
    assert complete["grounded"] == 1
    assert len(complete["citations"]) == 1
    cite = complete["citations"][0]
    assert cite["verified"] is True
    assert cite["section_ref"] == "Item 7 — MD&A"
    assert "#:~:text=" in cite["fragment_url"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_marks_unverifiable_citation_false(monkeypatch):
    """An excerpt not present in the source is surfaced as verified=False (base URL, no fragment)."""
    fabricated = "The company announced a special dividend of 5 dollars per share this quarter."
    citations_json = '[{"n":1,"excerpt":"' + fabricated + '","section":"Item 7 — MD&A"}]'
    chunks = ["A dividend was announced [1]. ===CITATIONS===\n" + citations_json]
    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat", _chunks_to_async_gen(chunks)
    )

    events = await _collect(_fake_filing(), "Any dividend?")
    complete = next(e for e in events if e["type"] == "complete")

    assert complete["grounded"] == 0
    cite = complete["citations"][0]
    assert cite["verified"] is False
    assert "#:~:text=" not in cite["fragment_url"]
    assert cite["fragment_url"] == _fake_filing().document_url


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_not_disclosed_path(monkeypatch):
    """The not-disclosed sentinel yields a not_disclosed event and no fabricated citations."""
    chunks = [
        "===NOT_DIS",
        "CLOSED===\nThis 10-K does not disclose forward revenue guidance.",
    ]
    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat", _chunks_to_async_gen(chunks)
    )

    events = await _collect(_fake_filing(), "What is next year's guidance?")
    types = [e["type"] for e in events]

    assert "not_disclosed" in types
    nd = next(e for e in events if e["type"] == "not_disclosed")
    assert "does not disclose" in nd["answer"]
    # No prose tokens should have been emitted.
    assert all(e["type"] != "token" for e in events)
    complete = next(e for e in events if e["type"] == "complete")
    assert complete["kind"] == "not_disclosed"
    assert complete["citations"] == []
    assert complete["grounded"] == 0


# --- Endpoint gating + metering ----------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@contextmanager
def _as_user(is_pro):
    """Create a real user row + override get_current_user with a matching stand-in."""
    from app.database import SessionLocal
    from app.models import User, UserUsage

    db = SessionLocal()
    user = User(email=f"copilot-{uuid.uuid4().hex}@example.com", hashed_password="x",
                email_verified=True, is_active=True, is_pro=is_pro)
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = user.id
    db.close()

    stand_in = SimpleNamespace(
        id=uid, is_pro=is_pro, subscription=None, email="x@example.com", full_name="Tester"
    )
    # require_entitlement resolves the user through _resolve_current_user (which lazily calls the
    # canonical get_current_user). Override both so the gate sees our stand-in regardless of which
    # dependency FastAPI injects for a given endpoint.
    app.dependency_overrides[get_current_user] = lambda: stand_in
    app.dependency_overrides[_resolve_current_user] = lambda: stand_in
    try:
        yield uid
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(_resolve_current_user, None)
        db = SessionLocal()
        db.query(UserUsage).filter(UserUsage.user_id == uid).delete()
        db.query(User).filter(User.id == uid).delete()
        db.commit()
        db.close()


@contextmanager
def _seed_filing():
    """Insert a Company + Filing (+ content cache) so the endpoint can load a real filing."""
    from app.database import SessionLocal
    from app.models import Company, Filing, FilingContentCache

    db = SessionLocal()
    suffix = uuid.uuid4().hex[:10]
    company = Company(cik=f"cik{suffix}", ticker=f"T{suffix[:4]}", name="Test Co")
    db.add(company)
    db.commit()
    db.refresh(company)
    filing = Filing(
        company_id=company.id,
        accession_number=f"acc-{suffix}",
        filing_type="10-K",
        filing_date=__import__("datetime").datetime(2026, 1, 1),
        document_url="https://www.sec.gov/Archives/edgar/data/1/x/doc.htm",
        sec_url="https://www.sec.gov/Archives/edgar/data/1/x/",
    )
    db.add(filing)
    db.commit()
    db.refresh(filing)
    db.add(FilingContentCache(filing_id=filing.id, critical_excerpt=_FAKE_SOURCE))
    db.commit()
    fid = filing.id
    cid = company.id
    db.close()
    try:
        yield fid
    finally:
        db = SessionLocal()
        db.query(FilingContentCache).filter(FilingContentCache.filing_id == fid).delete()
        db.query(Filing).filter(Filing.id == fid).delete()
        db.query(Company).filter(Company.id == cid).delete()
        db.commit()
        db.close()


@pytest.mark.requires_db
def test_endpoint_free_user_forbidden(client):
    with _as_user(is_pro=False), _seed_filing() as fid:
        resp = client.post(f"/api/summaries/filing/{fid}/ask-stream", json={"question": "Hi?"})
        assert resp.status_code == 403


@pytest.mark.requires_db
def test_endpoint_pro_user_streams(client, monkeypatch):
    async def _fake_answer(*, filing, question, history=None):
        yield {"type": "progress", "stage": "reading"}
        yield {"type": "token", "text": "hello"}
        yield {"type": "complete", "answer": "hello", "citations": [], "grounded": 0, "kind": "answer"}

    import app.routers.summaries as summaries_router
    monkeypatch.setattr(summaries_router, "answer_filing_question", _fake_answer)

    with _as_user(is_pro=True), _seed_filing() as fid:
        resp = client.post(f"/api/summaries/filing/{fid}/ask-stream", json={"question": "Hi?"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        assert '"type": "complete"' in resp.text


@pytest.mark.requires_db
def test_endpoint_increments_qa_count(client, monkeypatch):
    async def _fake_answer(*, filing, question, history=None):
        yield {"type": "complete", "answer": "ok", "citations": [], "grounded": 0, "kind": "answer"}

    import app.routers.summaries as summaries_router
    from app.services.subscription_service import get_current_month, get_user_qa_count
    from app.database import SessionLocal

    monkeypatch.setattr(summaries_router, "answer_filing_question", _fake_answer)

    with _as_user(is_pro=True) as uid, _seed_filing() as fid:
        resp = client.post(f"/api/summaries/filing/{fid}/ask-stream", json={"question": "Q?"})
        assert resp.status_code == 200
        db = SessionLocal()
        try:
            assert get_user_qa_count(uid, get_current_month(), db) == 1
        finally:
            db.close()


@pytest.mark.requires_db
def test_endpoint_over_cap_returns_429(client, monkeypatch):
    # check_qa_limit reads the cap off the shared settings singleton; a cap of 0 means any prior
    # usage (here: 0) is already at/over the soft cap → 429.
    from app.config import settings
    monkeypatch.setattr(settings, "COPILOT_MONTHLY_QUESTION_CAP", 0)

    with _as_user(is_pro=True), _seed_filing() as fid:
        resp = client.post(f"/api/summaries/filing/{fid}/ask-stream", json={"question": "Q?"})
        assert resp.status_code == 429


# --- Message assembly + snapshot ---------------------------------------------------------------

@pytest.mark.unit
def test_build_messages_no_history_merges_context_and_question():
    """No history → the filing-context user msg and the question collapse into one user message
    (no consecutive user roles, which some providers reject)."""
    msgs = copilot_service._build_messages(_fake_filing(), _FAKE_SOURCE, "What is revenue?", None)
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert "FILING CONTENT" in msgs[1]["content"]
    assert "What is revenue?" in msgs[1]["content"]


@pytest.mark.unit
def test_build_messages_alternates_with_history():
    """With history, roles strictly alternate and context folds into the first user turn."""
    history = [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
    ]
    msgs = copilot_service._build_messages(_fake_filing(), _FAKE_SOURCE, "new question", history)
    roles = [m["role"] for m in msgs]
    assert roles[0] == "system"
    assert all(roles[i] != roles[i + 1] for i in range(len(roles) - 1))  # no same-role run
    assert "FILING CONTENT" in msgs[1]["content"] and "earlier question" in msgs[1]["content"]
    assert msgs[-1]["content"] == "new question"


@pytest.mark.unit
def test_snapshot_filing_detaches_fields():
    """snapshot_filing copies the fields the generator needs into plain objects, and the generator
    runs off it unchanged."""
    snap = copilot_service.snapshot_filing(_fake_filing())
    assert snap.content_cache.critical_excerpt == _FAKE_SOURCE
    assert snap.company.ticker == "AAPL"
    assert snap.filing_type == "10-K"
    assert snap.document_url.startswith("https://www.sec.gov/")
