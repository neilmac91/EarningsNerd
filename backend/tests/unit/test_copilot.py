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
        company_id=1,
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
        copilot_service.openai_service, "stream_chat_with_tools", _chunks_to_async_gen(chunks)
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
        copilot_service.openai_service, "stream_chat_with_tools", _chunks_to_async_gen(chunks)
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
        copilot_service.openai_service, "stream_chat_with_tools", _chunks_to_async_gen(chunks)
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
def _as_user(is_pro, free_taste_used=0):
    """Create a real user row + override get_current_user with a matching stand-in.

    ``free_taste_used`` seeds the lifetime Copilot free-taste counter (roadmap 2.2) on both the real
    row (so metering reads/writes it) and the stand-in (so the gate sees it).
    """
    from app.database import SessionLocal
    from app.models import User, UserUsage

    db = SessionLocal()
    user = User(email=f"copilot-{uuid.uuid4().hex}@example.com", hashed_password="x",
                email_verified=True, is_active=True, is_pro=is_pro,
                copilot_free_taste_used=free_taste_used)
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = user.id
    db.close()

    stand_in = SimpleNamespace(
        id=uid, is_pro=is_pro, subscription=None, email="x@example.com", full_name="Tester",
        copilot_free_taste_used=free_taste_used,
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
def test_endpoint_free_user_with_taste_streams(client, monkeypatch):
    # Roadmap 2.2: a Free user under their lifetime free-taste allowance can sample Copilot.
    async def _fake_answer(*, filing, question, history=None):
        yield {"type": "complete", "answer": "hi", "citations": [], "grounded": 0, "kind": "answer"}

    import app.routers.summaries as summaries_router
    monkeypatch.setattr(summaries_router, "answer_filing_question", _fake_answer)

    with _as_user(is_pro=False, free_taste_used=0), _seed_filing() as fid:
        resp = client.post(f"/api/summaries/filing/{fid}/ask-stream", json={"question": "Hi?"})
        assert resp.status_code == 200
        assert '"type": "complete"' in resp.text


@pytest.mark.requires_db
def test_endpoint_free_user_taste_exhausted_forbidden(client):
    # Free user who has already spent all 3 lifetime free questions → 403 upsell.
    with _as_user(is_pro=False, free_taste_used=3), _seed_filing() as fid:
        resp = client.post(f"/api/summaries/filing/{fid}/ask-stream", json={"question": "Hi?"})
        assert resp.status_code == 403


@pytest.mark.requires_db
def test_endpoint_free_taste_decrements_lifetime_counter(client, monkeypatch):
    # A successful free-taste answer increments the lifetime counter (not the monthly qa_count).
    async def _fake_answer(*, filing, question, history=None):
        yield {"type": "complete", "answer": "ok", "citations": [], "grounded": 0, "kind": "answer"}

    import app.routers.summaries as summaries_router
    from app.services.subscription_service import get_current_month, get_user_qa_count
    from app.database import SessionLocal
    from app.models import User

    monkeypatch.setattr(summaries_router, "answer_filing_question", _fake_answer)

    with _as_user(is_pro=False, free_taste_used=1) as uid, _seed_filing() as fid:
        resp = client.post(f"/api/summaries/filing/{fid}/ask-stream", json={"question": "Q?"})
        assert resp.status_code == 200
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == uid).first()
            assert user.copilot_free_taste_used == 2  # lifetime counter advanced 1 → 2
            assert get_user_qa_count(uid, get_current_month(), db) == 0  # monthly cap untouched
        finally:
            db.close()


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
    # P5: company_id + cik are captured eagerly so the numeric tools can query without the request DB.
    assert snap.company_id == 1
    assert snap.cik == "320193"


# --- P5: numeric XBRL tool-use -----------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_surfaces_xbrl_fact_as_verified_citation(monkeypatch):
    """When the model calls get_financial_fact, the resulting XBRL fact is appended to the complete
    event as a verified citation with a ``XBRL ·`` section_ref — without any frontend change."""
    revenue_fact = {
        "concept": "revenue",
        "value": 391035000000.0,
        "unit": "USD",
        "period_end": "2024-09-28",
        "fiscal_year": 2024,
        "fiscal_period": "FY",
        "raw_tag": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "accession": "0000320193-24-000123",
    }

    # Fake stream: (a) call the passed run_tool for get_financial_fact, then (b) yield an answer that
    # cites the figure inline with its assigned [F1] marker + the citations sentinel + empty text array.
    def _fake_stream(messages, tools, run_tool, **_kwargs):
        async def _gen():
            run_tool("get_financial_fact", {"concept": "revenue"})
            yield "Apple's revenue was strong [F1]. ===CITATIONS===\n[]"
        return _gen()

    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat_with_tools", _fake_stream
    )
    monkeypatch.setattr(copilot_service.copilot_tools, "run_tool",
                        lambda name, args, company_id: dict(revenue_fact))

    events = await _collect(_fake_filing(), "How much revenue?")
    complete = next(e for e in events if e["type"] == "complete")

    assert complete["kind"] == "answer"
    # One XBRL citation (no text citations were emitted) and it counts toward grounded.
    assert complete["grounded"] == 1
    assert len(complete["citations"]) == 1
    cite = complete["citations"][0]
    assert cite["verified"] is True
    assert cite["section_ref"].startswith("XBRL ·")
    assert "Revenue" in cite["excerpt"]
    assert cite["n"] == 1  # cited inline via its [F1] marker → renumbered as the answer's 1st citation
    assert cite["fragment_url"] == _fake_filing().document_url
    assert "[1]" in complete["answer"]  # the inline marker is rewritten to match the final numbering


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_drops_uncited_xbrl_fact(monkeypatch):
    """A fact the model fetched but never cited inline ([F1] absent) is dropped — no stray source,
    no grounded inflation (audit finding #4)."""
    revenue_fact = {
        "concept": "revenue",
        "value": 391035000000.0,
        "unit": "USD",
        "period_end": "2024-09-28",
        "fiscal_year": 2024,
        "fiscal_period": "FY",
        "raw_tag": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "accession": "0000320193-24-000123",
    }

    def _fake_stream(messages, tools, run_tool, **_kwargs):
        async def _gen():
            run_tool("get_financial_fact", {"concept": "revenue"})
            yield "Revenue held up, but I won't cite the figure. ===CITATIONS===\n[]"
        return _gen()

    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", _fake_stream)
    monkeypatch.setattr(copilot_service.copilot_tools, "run_tool",
                        lambda name, args, company_id: dict(revenue_fact))

    events = await _collect(_fake_filing(), "How much revenue?")
    complete = next(e for e in events if e["type"] == "complete")

    assert complete["grounded"] == 0
    assert complete["citations"] == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_matches_fact_marker_case_and_space_insensitive(monkeypatch):
    """A minor LLM marker variation ([f 1]) still grounds the fact — matching the frontend matcher."""
    revenue_fact = {
        "concept": "revenue",
        "value": 391035000000.0,
        "unit": "USD",
        "period_end": "2024-09-28",
        "fiscal_year": 2024,
        "fiscal_period": "FY",
        "raw_tag": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "accession": "0000320193-24-000123",
    }

    def _fake_stream(messages, tools, run_tool, **_kwargs):
        async def _gen():
            run_tool("get_financial_fact", {"concept": "revenue"})
            yield "Revenue was strong [f 1]. ===CITATIONS===\n[]"
        return _gen()

    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", _fake_stream)
    monkeypatch.setattr(copilot_service.copilot_tools, "run_tool",
                        lambda name, args, company_id: dict(revenue_fact))

    events = await _collect(_fake_filing(), "How much revenue?")
    complete = next(e for e in events if e["type"] == "complete")

    assert complete["grounded"] == 1
    assert complete["citations"][0]["n"] == 1
    assert "[1]" in complete["answer"]  # "[f 1]" is normalized + rewritten to the canonical "[1]"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_drops_uncited_text_citation(monkeypatch):
    """A text citation the model declares in the trailing JSON block but never places inline is
    dropped — mirrors test_service_drops_uncited_xbrl_fact, but for the text-citation path (the two
    citation kinds used to be verified asymmetrically; this is the same guarantee for both)."""
    citations_json = (
        '[{"n":1,"excerpt":"' + _KNOWN_SENTENCE + '","section":"Item 7 — MD&A"},'
        '{"n":2,"excerpt":"Operating margins expanded year over year.","section":"Item 7 — MD&A"}]'
    )
    chunks = ["Apple's revenue grew strongly [1]. ===CITATIONS===\n" + citations_json]
    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat_with_tools", _chunks_to_async_gen(chunks)
    )

    events = await _collect(_fake_filing(), "How did revenue do?")
    complete = next(e for e in events if e["type"] == "complete")

    # Only the citation actually placed inline ([1]) survives — the declared-but-uncited "n":2 must
    # not leak into the Sources panel.
    assert complete["grounded"] == 1
    assert len(complete["citations"]) == 1
    assert complete["citations"][0]["excerpt"] == _KNOWN_SENTENCE
    assert isinstance(complete["citations"][0]["n"], int)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_resolves_back_to_back_fact_markers(monkeypatch):
    """Multiple fact markers cited back-to-back with no separating text ("[F1][F2][F3]") each
    resolve to a distinct, correctly-ordered citation — the exact shape that produced unstyled,
    unlinked literal bracket text in the field report this test guards against."""
    facts = [
        {"concept": "revenue", "value": 34124000000.0, "unit": "USD", "period_end": "2023-12-31",
         "fiscal_year": 2023, "fiscal_period": "FY", "raw_tag": "us-gaap:Revenues", "accession": "a-2023"},
        {"concept": "revenue", "value": 45043000000.0, "unit": "USD", "period_end": "2024-12-31",
         "fiscal_year": 2024, "fiscal_period": "FY", "raw_tag": "us-gaap:Revenues", "accession": "a-2024"},
        {"concept": "revenue", "value": 65179000000.0, "unit": "USD", "period_end": "2025-12-31",
         "fiscal_year": 2025, "fiscal_period": "FY", "raw_tag": "us-gaap:Revenues", "accession": "a-2025"},
    ]
    call_count = {"n": 0}

    def _fake_run_tool(name, args, company_id):
        fact = dict(facts[call_count["n"]])
        call_count["n"] += 1
        return fact

    def _fake_stream(messages, tools, run_tool, **_kwargs):
        async def _gen():
            for _ in facts:
                run_tool("get_financial_fact", {"concept": "revenue"})
            yield "Revenue grew from $34.1B to $45.0B to $65.2B [F1][F2][F3]. ===CITATIONS===\n[]"
        return _gen()

    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", _fake_stream)
    monkeypatch.setattr(copilot_service.copilot_tools, "run_tool", _fake_run_tool)

    events = await _collect(_fake_filing(), "How did revenue trend?")
    complete = next(e for e in events if e["type"] == "complete")

    assert complete["grounded"] == 3
    assert [c["n"] for c in complete["citations"]] == [1, 2, 3]
    expected_excerpts = [copilot_service.copilot_tools.fact_to_citation(f)["excerpt"] for f in facts]
    assert [c["excerpt"] for c in complete["citations"]] == expected_excerpts
    assert "[1]" in complete["answer"] and "[2]" in complete["answer"] and "[3]" in complete["answer"]
    assert "[F1]" not in complete["answer"] and "[F2]" not in complete["answer"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_unifies_text_and_fact_citation_numbering(monkeypatch):
    """A text-excerpt citation and a tool-figure citation share ONE continuous numbering sequence,
    assigned in the order each marker first appears in the rendered answer — not "facts always come
    after text citations" or any other fixed ordering by kind."""
    revenue_fact = {
        "concept": "revenue", "value": 391035000000.0, "unit": "USD", "period_end": "2024-09-28",
        "fiscal_year": 2024, "fiscal_period": "FY",
        "raw_tag": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "accession": "0000320193-24-000123",
    }
    citations_json = '[{"n":1,"excerpt":"' + _KNOWN_SENTENCE + '","section":"Item 7 — MD&A"}]'

    def _fake_stream(messages, tools, run_tool, **_kwargs):
        async def _gen():
            run_tool("get_financial_fact", {"concept": "revenue"})
            yield (
                "Revenue was $391.0B [F1], as management noted [1]. "
                "===CITATIONS===\n" + citations_json
            )
        return _gen()

    monkeypatch.setattr(copilot_service.openai_service, "stream_chat_with_tools", _fake_stream)
    monkeypatch.setattr(copilot_service.copilot_tools, "run_tool",
                        lambda name, args, company_id: dict(revenue_fact))

    events = await _collect(_fake_filing(), "How much revenue, per management?")
    complete = next(e for e in events if e["type"] == "complete")

    assert complete["grounded"] == 2
    assert [c["n"] for c in complete["citations"]] == [1, 2]
    # [F1] appears before [1] in the rendered prose, so the fact citation wins the "[1]" slot — proof
    # numbering is driven by first-appearance order, not by citation kind.
    assert complete["citations"][0]["section_ref"].startswith("XBRL ·")
    assert complete["citations"][1]["section_ref"] == "Item 7 — MD&A"
    assert "[1]" in complete["answer"] and "[2]" in complete["answer"]
    assert "[F1]" not in complete["answer"]


# --- P6c: dynamic follow-up suggestions --------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_parses_followups(monkeypatch):
    """The ===FOLLOWUPS=== trailer is split off and surfaced on the complete event (max 3), without
    polluting the answer or the citation parse."""
    chunks = [
        "Revenue grew strongly [1]. ===CITATIONS===\n"
        + '[{"n":1,"excerpt":"' + _KNOWN_SENTENCE + '","section":"Item 7"}]'
        + "\n===FOLLOWUPS===\n"
        + '["How did margins trend?", "What are the top risks?", "Any guidance?", "Ignored fourth?"]'
    ]
    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat_with_tools", _chunks_to_async_gen(chunks)
    )

    events = await _collect(_fake_filing(), "How did revenue do?")
    complete = next(e for e in events if e["type"] == "complete")

    assert complete["followups"] == [
        "How did margins trend?", "What are the top risks?", "Any guidance?",
    ]
    assert complete["grounded"] == 1  # citations still parse (followups split off first)
    assert "===FOLLOWUPS===" not in complete["answer"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_followups_sentinel_case_tolerant(monkeypatch):
    """A mis-cased/dashed followups sentinel ([===Follow-ups===]) still splits cleanly, so the
    citations JSON before it is NOT corrupted (the high-severity failure mode)."""
    chunks = [
        "Revenue grew [1]. ===CITATIONS===\n"
        + '[{"n":1,"excerpt":"' + _KNOWN_SENTENCE + '","section":"Item 7"}]'
        + "\n===Follow-ups===\n"
        + '["What about margins?"]'
    ]
    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat_with_tools", _chunks_to_async_gen(chunks)
    )

    events = await _collect(_fake_filing(), "How did revenue do?")
    complete = next(e for e in events if e["type"] == "complete")

    assert complete["followups"] == ["What about margins?"]
    assert complete["grounded"] == 1  # citations intact despite the mis-cased sentinel
    assert len(complete["citations"]) == 1


@pytest.mark.unit
def test_parse_followups_tolerant():
    assert copilot_service._parse_followups('["a", "b"]') == ["a", "b"]
    assert copilot_service._parse_followups("") == []
    assert copilot_service._parse_followups("not json at all") == []
    assert copilot_service._parse_followups('["a","b","c","d"]') == ["a", "b", "c"]  # capped at 3
    assert copilot_service._parse_followups('[1, "ok", null, "  "]') == ["ok"]  # non/blank strings out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_chat_with_tools_assembles_tool_call_deltas():
    """stream_chat_with_tools concatenates tool-call argument fragments split across chunks, runs the
    tool with the assembled args, then streams the next round's content."""
    from app.services.openai_service import STREAM_ACTIVITY_SENTINEL, openai_service

    def _delta(content=None, tool_calls=None, finish_reason=None):
        return SimpleNamespace(
            choices=[SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=tool_calls),
                finish_reason=finish_reason,
            )]
        )

    def _tc(index, *, call_id=None, name=None, arguments=None):
        return SimpleNamespace(
            index=index,
            id=call_id,
            function=SimpleNamespace(name=name, arguments=arguments),
        )

    # Round 1: a single tool call whose JSON arguments are split across two chunks.
    round1 = [
        _delta(tool_calls=[_tc(0, call_id="call_1", name="get_financial_fact", arguments='{"conc')]),
        _delta(tool_calls=[_tc(0, arguments='ept":"revenue"}')], finish_reason="tool_calls"),
    ]
    # Round 2: the streamed final answer.
    round2 = [_delta(content="Revenue was "), _delta(content="$391B.", finish_reason="stop")]

    calls = []

    async def _fake_create(**kwargs):
        # First create() returns round1, second returns round2 (the loop advances after tools run).
        chunks = round1 if len(calls) == 0 else round2

        async def _aiter():
            for c in chunks:
                yield c
        calls.append(kwargs)
        return _aiter()

    captured = {}

    def _run_tool(name, args):
        captured["name"] = name
        captured["args"] = args
        return {"concept": "revenue", "value": 391035000000.0}

    import unittest.mock as mock
    with mock.patch.object(openai_service.client.chat.completions, "create", _fake_create):
        out = []
        async for piece in openai_service.stream_chat_with_tools(
            [{"role": "user", "content": "revenue?"}],
            tools=[{"type": "function", "function": {"name": "get_financial_fact"}}],
            run_tool=_run_tool,
        ):
            out.append(piece)

    # The split argument fragments were reassembled into valid JSON and passed to run_tool.
    assert captured["name"] == "get_financial_fact"
    assert captured["args"] == {"concept": "revenue"}
    # The second round's content was streamed out (filtering the activity-signal chunks).
    content = "".join(p for p in out if not p.startswith(STREAM_ACTIVITY_SENTINEL))
    assert content == "Revenue was $391B."
    # Activity start + done were emitted around the single tool call.
    activity = [p for p in out if p.startswith(STREAM_ACTIVITY_SENTINEL)]
    assert len(activity) == 2
    # Two create() calls: round 1 (tool call) + round 2 (answer).
    assert len(calls) == 2


# --- Audit fixes: stream-error handling, metering-on-success, history bounding ------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_stream_error_becomes_error_event(monkeypatch):
    """An upstream/model failure (sentinel-prefixed chunk) yields an ``error`` event — never a
    ``complete`` and never a prose token. A model outage must not look like a confident answer."""
    from app.services.openai_service import STREAM_ERROR_SENTINEL

    chunks = [f"{STREAM_ERROR_SENTINEL}upstream 503 from model"]
    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat_with_tools", _chunks_to_async_gen(chunks)
    )

    events = await _collect(_fake_filing(), "How did revenue do?")
    types = [e["type"] for e in events]

    assert "error" in types
    assert "complete" not in types
    assert all(e["type"] != "token" for e in events)  # nothing leaked as prose
    err = next(e for e in events if e["type"] == "error")
    assert "upstream 503" in err["message"]
    assert STREAM_ERROR_SENTINEL not in err["message"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_stream_error_after_prose_becomes_error_event(monkeypatch):
    """If the failure arrives mid-answer, prose already streamed but the stream still ends in an
    ``error`` event (not a ``complete``), so the client surfaces the failure rather than a partial
    answer dressed up as final."""
    from app.services.openai_service import STREAM_ERROR_SENTINEL

    chunks = ["Apple's revenue was strong ", f"{STREAM_ERROR_SENTINEL}connection reset"]
    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat_with_tools", _chunks_to_async_gen(chunks)
    )

    events = await _collect(_fake_filing(), "How did revenue do?")
    types = [e["type"] for e in events]

    assert types[-1] == "error"
    assert "complete" not in types
    token_text = "".join(e["text"] for e in events if e["type"] == "token")
    assert "[Error" not in token_text  # the old bracketed marker never reaches the user


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_chat_with_tools_yields_error_sentinel_on_failure():
    """The wrapper signals failure with a single sentinel-prefixed chunk rather than raising or
    emitting plain ``[Error: ...]`` prose."""
    import unittest.mock as mock

    from app.services.openai_service import STREAM_ERROR_SENTINEL, openai_service

    async def _boom(**_kwargs):
        raise RuntimeError("model exploded")

    with mock.patch.object(openai_service.client.chat.completions, "create", _boom):
        out = []
        async for piece in openai_service.stream_chat_with_tools(
            [{"role": "user", "content": "hi"}], tools=[], run_tool=lambda n, a: {}
        ):
            out.append(piece)

    assert len(out) == 1
    assert out[0].startswith(STREAM_ERROR_SENTINEL)
    assert "model exploded" in out[0]


@pytest.mark.requires_db
def test_endpoint_does_not_increment_qa_on_error(client, monkeypatch):
    """A generation that fails (only an ``error`` event, no ``complete``) must NOT consume quota."""
    async def _fake_answer(*, filing, question, history=None):
        yield {"type": "progress", "stage": "reading"}
        yield {"type": "error", "message": "model down"}

    import app.routers.summaries as summaries_router
    from app.database import SessionLocal
    from app.services.subscription_service import get_current_month, get_user_qa_count

    monkeypatch.setattr(summaries_router, "answer_filing_question", _fake_answer)

    with _as_user(is_pro=True) as uid, _seed_filing() as fid:
        resp = client.post(f"/api/summaries/filing/{fid}/ask-stream", json={"question": "Q?"})
        assert resp.status_code == 200
        db = SessionLocal()
        try:
            assert get_user_qa_count(uid, get_current_month(), db) == 0
        finally:
            db.close()


@pytest.mark.unit
def test_ask_request_caps_history():
    """AskRequest trims the history array length and truncates oversized per-turn content so a
    malicious client can't stuff the prompt (the ``question`` field is already capped)."""
    from app.config import settings
    from app.routers.summaries import AskRequest

    big = "x" * (settings.COPILOT_HISTORY_ITEM_CHAR_CAP + 5000)
    huge = [{"role": "user", "content": big}] * (settings.COPILOT_HISTORY_MAX_ITEMS + 20)

    req = AskRequest(question="hi", history=huge)

    assert len(req.history) == settings.COPILOT_HISTORY_MAX_ITEMS
    assert all(len(t["content"]) <= settings.COPILOT_HISTORY_ITEM_CHAR_CAP for t in req.history)


@pytest.mark.unit
def test_build_messages_truncates_oversized_history_content():
    """Defense in depth: even if an oversized turn reaches the generator, _build_messages truncates
    each turn's content to the per-item cap before it lands in the prompt."""
    from app.config import settings

    cap = settings.COPILOT_HISTORY_ITEM_CHAR_CAP
    big = "Z" * (cap + 1000)  # contiguous run of a marker that won't appear elsewhere in the prompt
    history = [{"role": "user", "content": big}, {"role": "assistant", "content": "ok"}]

    msgs = copilot_service._build_messages(_fake_filing(), _FAKE_SOURCE, "q", history)
    joined = "".join(m["content"] for m in msgs)

    assert big not in joined           # the oversized turn was not stuffed in verbatim
    assert ("Z" * cap) in joined       # ... it was truncated to exactly the per-item cap


# --- P6a: live "show the work" activity ticker -------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_emits_activity_events(monkeypatch):
    """Tool-activity sentinel chunks from the wrapper become `activity` events with human labels,
    and never leak into the answer prose."""
    import json as _json

    from app.services.openai_service import STREAM_ACTIVITY_SENTINEL

    start = STREAM_ACTIVITY_SENTINEL + _json.dumps(
        {"name": "get_financial_fact", "args": {"concept": "revenue"}, "phase": "start"}
    )
    done = STREAM_ACTIVITY_SENTINEL + _json.dumps(
        {"name": "get_financial_fact", "args": {"concept": "revenue"}, "phase": "done", "ok": True}
    )
    chunks = [start, done, "Revenue was strong [1]. ===CITATIONS===\n[]"]
    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat_with_tools", _chunks_to_async_gen(chunks)
    )

    events = await _collect(_fake_filing(), "How much revenue?")

    activities = [e for e in events if e["type"] == "activity"]
    assert [a["phase"] for a in activities] == ["start", "done"]
    assert "revenue" in activities[0]["label"].lower()
    assert activities[1]["ok"] is True

    token_text = "".join(e["text"] for e in events if e["type"] == "token")
    assert STREAM_ACTIVITY_SENTINEL not in token_text  # never leaked as prose
    assert "complete" in [e["type"] for e in events]


@pytest.mark.unit
def test_describe_tool_call_labels():
    """The activity labeler produces readable, tool-specific phrases (and a safe fallback)."""
    from app.services import copilot_tools

    assert copilot_tools.describe_tool_call(
        "get_financial_fact", {"concept": "revenue"}
    ).lower() == "looking up revenue"
    assert "margin" in copilot_tools.describe_tool_call(
        "compute_metric", {"kind": "margin", "concept": "gross_profit"}
    ).lower()
    assert "yoy" in copilot_tools.describe_tool_call(
        "compute_metric", {"kind": "yoy_growth", "concept": "net_income"}
    ).lower()
    assert copilot_tools.describe_tool_call("list_available_concepts", {})  # non-empty
    assert copilot_tools.describe_tool_call("mystery_tool", None)  # safe fallback, no raise
    # Non-dict args must not raise (a malformed tool-args payload is coerced to {}).
    assert copilot_tools.describe_tool_call("get_financial_fact", ["not", "a", "dict"])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_strips_fabricated_fact_markers(monkeypatch):
    """[F#] markers with NO backing tool result are stripped from the answer, not left as dead
    literal brackets (field report: an answer littered with [F1]..[F12] and only text sources).
    Spacing around the stripped marker collapses so prose reads naturally."""
    citations_json = '[{"n":1,"excerpt":"' + _KNOWN_SENTENCE + '","section":"Item 7 — MD&A"}]'
    chunks = [
        "Revenue grew 15% to $402.8 billion [F1], up from $350.0 billion [F2] and "
        "$307.4 billion [F3]. Margins held at 32% [1]. ===CITATIONS===\n" + citations_json
    ]
    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat_with_tools", _chunks_to_async_gen(chunks)
    )

    events = await _collect(_fake_filing(), "How did revenue trend?")
    complete = next(e for e in events if e["type"] == "complete")

    # The fabricated F-markers are gone from the prose — no dead brackets, no doubled spaces,
    # commas hug the value they follow.
    assert "[F" not in complete["answer"]
    assert "billion ," not in complete["answer"]
    assert "  " not in complete["answer"]
    assert "$402.8 billion, up from $350.0 billion and $307.4 billion." in complete["answer"]
    # The real text citation still resolves and renumbers normally.
    assert len(complete["citations"]) == 1
    assert "[1]" in complete["answer"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_keeps_plain_unmatched_markers_literal(monkeypatch):
    """A plain [n] with no matching citation stays literal text (it may be quoted filing
    content) — only F-markers get stripped, per the unmatched-marker contract."""
    chunks = ["See footnote [14] of the notes. ===CITATIONS===\n[]"]
    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat_with_tools", _chunks_to_async_gen(chunks)
    )

    events = await _collect(_fake_filing(), "Anything odd?")
    complete = next(e for e in events if e["type"] == "complete")

    assert "[14]" in complete["answer"]
    assert complete["citations"] == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_strips_fabricated_marker_between_words(monkeypatch):
    """Stripping an F-marker that sits between two words keeps exactly one space."""
    chunks = ["Revenue [F7] doubled this year. ===CITATIONS===\n[]"]
    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat_with_tools", _chunks_to_async_gen(chunks)
    )

    events = await _collect(_fake_filing(), "How did revenue do?")
    complete = next(e for e in events if e["type"] == "complete")

    assert complete["answer"].startswith("Revenue doubled this year.")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_not_disclosed_carries_followups(monkeypatch):
    """A not-disclosed verdict may carry a trailing followups block (questions the filing CAN
    answer) — parsed out of the verdict text and surfaced on the complete event, so a dead end
    still offers a productive next step (field report)."""
    chunks = [
        "===NOT_DISCLOSED===\nQuarterly gross margin detail is not in this annual filing. "
        '===FOLLOWUPS===\n["How did annual gross margin trend?", "What drove operating expenses?"]'
    ]
    monkeypatch.setattr(
        copilot_service.openai_service, "stream_chat_with_tools", _chunks_to_async_gen(chunks)
    )

    events = await _collect(_fake_filing(), "How did margin trend by quarter?")
    nd = next(e for e in events if e["type"] == "not_disclosed")
    complete = next(e for e in events if e["type"] == "complete")

    assert complete["kind"] == "not_disclosed"
    assert "FOLLOWUPS" not in nd["answer"] and "FOLLOWUPS" not in complete["answer"]
    assert complete["followups"] == [
        "How did annual gross margin trend?",
        "What drove operating expenses?",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_chat_with_tools_suppresses_tool_round_narration(monkeypatch):
    """Prose the model emits in a round that goes on to call tools ("Let me gather the
    figures…") is inter-tool narration — it must never reach the stream (field report: it
    opened the visible answer). The final round's prose still streams; short final answers
    that never cross the hold-back cap are flushed at round end."""
    from types import SimpleNamespace as NS

    from app.services.openai_service import openai_service as svc

    def _chunk(content=None, tool_call=None):
        delta = NS(content=content, tool_calls=[tool_call] if tool_call else None)
        return NS(choices=[NS(delta=delta)])

    async def _round(chunks):
        for c in chunks:
            yield c

    rounds = [
        # Round 1: narration then a tool call — the narration must be suppressed.
        _round([
            _chunk(content="Let me gather the key figures first."),
            _chunk(tool_call=NS(index=0, id="c1", function=NS(name="get_financial_fact", arguments='{"concept":"revenue"}'))),
        ]),
        # Round 2: the real (short) answer, no tool calls.
        _round([_chunk(content="Revenue was $10B "), _chunk(content="[F1].")]),
    ]
    calls = iter(rounds)

    async def _fake_create(**_kwargs):
        return next(calls)

    monkeypatch.setattr(svc, "client", NS(chat=NS(completions=NS(create=_fake_create))))

    out: list[str] = []
    async for delta in svc.stream_chat_with_tools(
        [{"role": "user", "content": "q"}],
        [{"type": "function", "function": {"name": "get_financial_fact"}}],
        lambda name, args: {"value": 1, "cite": "F1"},
    ):
        out.append(delta)

    from app.services.openai_service import STREAM_ACTIVITY_SENTINEL

    prose = [d for d in out if not d.startswith(STREAM_ACTIVITY_SENTINEL)]
    assert "".join(prose) == "Revenue was $10B [F1]."
    assert all("Let me gather" not in d for d in out)
    # The tool-activity events still flow (start + done).
    assert sum(1 for d in out if d.startswith(STREAM_ACTIVITY_SENTINEL)) == 2
