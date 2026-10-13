"""section_review_service and its router: the Pro review of a filing's Item 1A wording changes.

DB-backed on the suite's SQLite (tables via create_all). The comparisons come from the real
extractor over an injected fetcher and parser (no network; the gate would fail the test), on
synthetic text. Pins: labels hang on the content-addressed change ids and nothing else; the review
completes when every change is labelled and freezes a receipt naming the two texts; reopening
clears it; ids the live comparison no longer has are ignored; the endpoints gate on the
``section_changes`` entitlement and map the domain errors; the dashboard feed carries the counts
for a viewer with access and the review progress for one with the full list.
"""
import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from app.config import settings
from app.models import Company, Filing, User, Watchlist
from app.models.section_review import SectionReview
from app.services import filing_section_service as sections
from app.services import section_review_service as svc
from app.services.dashboard_feed_service import compose_feed

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
LATER_NOW = datetime(2026, 10, 13, 13, 0, tzinfo=timezone.utc)
TEASER = sections.SectionAccess(sections.ACCESS_TEASER, 3)

PRIOR_TEXT = (
    "Item 1A. Risk Factors\n\n"
    "We depend on a small number of customers for a large share of our revenue.\n\n"
    "Our products may contain defects that could harm our reputation.\n\n"
    "Changes in tax law could increase our effective tax rate."
)
LATER_TEXT = (
    "Item 1A. Risk Factors\n\n"
    "We depend on a limited number of customers for a large share of our revenue.\n\n"
    "Our products may contain defects that could harm our reputation.\n\n"
    "We face intense competition, and competitors may have greater resources than we do.\n\n"
    "Cyberattacks on our systems could expose confidential information."
)
# The later text with one more paragraph: a re-extraction that changes the comparison.
REVISED_TEXT = LATER_TEXT + "\n\nOur insurance may not cover every loss we suffer."
# The later text with one changed paragraph reworded: that change's id is replaced, the others stay.
REWORDED_TEXT = LATER_TEXT.replace(
    "We face intense competition, and competitors may have greater resources than we do.",
    "We face intense competition from rivals with far greater resources than ours.",
)


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


_WATCHLIST_ROWS: list[int] = []


@pytest.fixture
def db():
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        if _WATCHLIST_ROWS:
            session.query(Watchlist).filter(Watchlist.id.in_(_WATCHLIST_ROWS)).delete(synchronize_session=False)
            session.commit()
            _WATCHLIST_ROWS.clear()
        session.close()


@pytest.fixture
def flag_on(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", True)


def _company(db, *, watched_by=None):
    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=f"cik{suffix}", ticker=f"R{suffix[:5].upper()}", name=f"Co {suffix}")
    db.add(company)
    db.commit()
    if watched_by is not None:
        row = Watchlist(user_id=watched_by.id, company_id=company.id)
        db.add(row)
        db.commit()
        _WATCHLIST_ROWS.append(row.id)
    return company


def _filing(db, company, form, period, filed):
    suffix = uuid.uuid4().hex[:10]
    filing = Filing(
        company_id=company.id, accession_number=f"review-{suffix}", filing_type=form, filing_date=filed,
        period_end_date=period, document_url=f"https://sec.example/{suffix}/doc.htm", sec_url=f"https://sec.example/{suffix}/",
    )
    db.add(filing)
    db.commit()
    db.refresh(filing)
    return filing


def _user(db, *, is_pro=False):
    user = User(email=f"review-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x",
                email_verified=True, is_active=True, is_pro=is_pro)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _pair(db, *, watched_by=None):
    company = _company(db, watched_by=watched_by)
    prior = _filing(db, company, "10-K", datetime(2024, 12, 31, tzinfo=timezone.utc), datetime(2025, 2, 20, tzinfo=timezone.utc))
    later = _filing(db, company, "10-K", datetime(2025, 12, 31, tzinfo=timezone.utc), datetime(2026, 2, 19, tzinfo=timezone.utc))
    return company, prior, later


def _extract(db, filing, text, *, now=NOW):
    async def fetch(url):
        return "html"

    def parse(html, form):
        return sections.ExtractedSection(status=sections.STATUS_OK, text=text, detection_method="toc", confidence=0.9)

    return asyncio.run(sections.extract_for_filing(db, filing, fetch_document=fetch, parse=parse, now=now)).row


def _compared_pair(db, *, watched_by=None):
    company, prior, later = _pair(db, watched_by=watched_by)
    _extract(db, prior, PRIOR_TEXT)
    _extract(db, later, LATER_TEXT)
    return company, prior, later


def _ids(db, filing):
    block = sections.build_section_changes(db, filing, sections.FULL_SECTION_ACCESS)
    return [item["id"] for item in block["items"]]


# --- the service -------------------------------------------------------------------------------

def test_state_is_unavailable_without_a_comparison_or_with_the_flag_off(db, monkeypatch):
    user = _user(db, is_pro=True)
    _company, prior, later = _pair(db)
    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", True)
    pending = svc.review_state(db, user.id, later.id)
    assert pending["status"] == "unavailable" and pending["items_total"] == 0 and pending["labels"] == {}
    with pytest.raises(svc.ReviewUnavailable):
        svc.set_label(db, user.id, later.id, "anything", svc.LABEL_REVIEWED)

    _extract(db, prior, PRIOR_TEXT)
    _extract(db, later, LATER_TEXT)
    assert svc.review_state(db, user.id, later.id)["status"] == "ok"
    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", False)
    assert svc.review_state(db, user.id, later.id)["status"] == "unavailable"
    with pytest.raises(svc.ReviewUnavailable):
        svc.set_label(db, user.id, later.id, "anything", svc.LABEL_REVIEWED)
    with pytest.raises(svc.FilingNotFound):
        svc.review_state(db, user.id, 0)


def test_labels_count_toward_the_queue_and_completing_it_freezes_a_receipt(db, flag_on):
    user = _user(db, is_pro=True)
    _company, prior, later = _compared_pair(db)
    ids = _ids(db, later)
    assert len(ids) == 4

    state = svc.review_state(db, user.id, later.id)
    assert state["status"] == "ok" and state["items_total"] == 4 and state["labels"] == {}
    assert state["counts"] == {"reviewed": 0, "follow_up": 0, "unlabeled": 4}
    assert state["completed_at"] is None and state["receipt"] is None

    state = svc.set_label(db, user.id, later.id, ids[0], svc.LABEL_REVIEWED, now=NOW)
    state = svc.set_label(db, user.id, later.id, ids[1], svc.LABEL_FOLLOW_UP, now=NOW)
    state = svc.set_label(db, user.id, later.id, ids[2], svc.LABEL_REVIEWED, now=NOW)
    assert state["counts"] == {"reviewed": 2, "follow_up": 1, "unlabeled": 1}
    assert state["labels"] == {ids[0]: "reviewed", ids[1]: "follow_up", ids[2]: "reviewed"}
    assert state["completed_at"] is None, "three of four is not the end of the queue"
    assert state["completed_now"] is False

    state = svc.set_label(db, user.id, later.id, ids[3], svc.LABEL_REVIEWED, now=NOW)
    assert state["completed_at"] == "2026-10-13T12:00:00Z" and state["completed_now"] is True
    assert "completed_now" not in svc.review_state(db, user.id, later.id), "a read is not a transition"
    receipt = state["receipt"]
    assert receipt["version"] == 1 and receipt["completed_at"] == "2026-10-13T12:00:00Z"
    assert receipt["filing"]["accession_number"] == later.accession_number
    assert receipt["prior_filing"]["accession_number"] == prior.accession_number
    current_row, prior_row = sections.section_row(db, later.id), sections.section_row(db, prior.id)
    assert receipt["texts"]["current"]["sha256"] == current_row.sha256 and len(current_row.sha256) == 64
    assert receipt["texts"]["prior"]["sha256"] == prior_row.sha256
    assert receipt["texts"]["current"]["extractor_version"] == sections.EXTRACTOR_VERSION
    assert receipt["engine_version"] == state["engine_version"]
    assert receipt["items_total"] == 4 and receipt["counts"]["unchanged"] == 1
    assert receipt["labels"] == {"reviewed": 3, "follow_up": 1} and receipt["follow_up_ids"] == [ids[1]]
    assert "app_version" in receipt

    # Only the row's own user sees the review; another Pro reader starts fresh.
    other = _user(db, is_pro=True)
    assert svc.review_state(db, other.id, later.id)["labels"] == {}


def test_relabelling_while_complete_keeps_the_time_and_reopening_clears_the_receipt(db, flag_on):
    user = _user(db, is_pro=True)
    _company, _prior, later = _compared_pair(db)
    ids = _ids(db, later)
    for item_id in ids:
        state = svc.set_label(db, user.id, later.id, item_id, svc.LABEL_REVIEWED, now=NOW)
    assert state["completed_at"] == "2026-10-13T12:00:00Z" and state["receipt"]["follow_up_ids"] == []

    # A follow-up flag set after completion: still complete, same completion time, receipt refreshed,
    # and not a completion again (the client counts the E3 event on completed_now alone).
    state = svc.set_label(db, user.id, later.id, ids[2], svc.LABEL_FOLLOW_UP, now=LATER_NOW)
    assert state["completed_at"] == "2026-10-13T12:00:00Z" and state["completed_now"] is False
    assert state["receipt"]["follow_up_ids"] == [ids[2]] and state["receipt"]["labels"] == {"reviewed": 3, "follow_up": 1}

    # Clearing a label reopens the queue: no completion, no receipt; completing again is a new time.
    state = svc.set_label(db, user.id, later.id, ids[0], None, now=LATER_NOW)
    assert state["counts"]["unlabeled"] == 1 and state["completed_at"] is None and state["receipt"] is None
    state = svc.set_label(db, user.id, later.id, ids[0], svc.LABEL_REVIEWED, now=LATER_NOW)
    assert state["completed_at"] == "2026-10-13T13:00:00Z" and state["completed_now"] is True


def test_unknown_ids_and_labels_are_refused_and_stale_labels_are_dropped(db, flag_on):
    user = _user(db, is_pro=True)
    _company, _prior, later = _compared_pair(db)
    ids = _ids(db, later)
    with pytest.raises(svc.UnknownItem):
        svc.set_label(db, user.id, later.id, "not-a-change", svc.LABEL_REVIEWED)
    with pytest.raises(svc.InvalidLabel):
        svc.set_label(db, user.id, later.id, ids[0], "skimmed")
    with pytest.raises(svc.FilingNotFound):
        svc.set_label(db, user.id, 0, ids[0], svc.LABEL_REVIEWED)

    for item_id in ids:
        svc.set_label(db, user.id, later.id, item_id, svc.LABEL_REVIEWED, now=NOW)
    assert svc.review_state(db, user.id, later.id)["completed_at"] is not None

    # The later text is re-extracted with one more paragraph: the unchanged ids keep their labels,
    # the receipt no longer describes the live comparison, so the review reads as reopened.
    _extract(db, later, REVISED_TEXT, now=LATER_NOW)
    revised = _ids(db, later)
    assert set(ids) < set(revised) and len(revised) == 5
    state = svc.review_state(db, user.id, later.id)
    assert state["items_total"] == 5 and state["counts"] == {"reviewed": 4, "follow_up": 0, "unlabeled": 1}
    assert state["completed_at"] is None and state["receipt"] is None

    # Labelling the new change completes the new comparison with a fresh receipt.
    new_id = next(i for i in revised if i not in ids)
    state = svc.set_label(db, user.id, later.id, new_id, svc.LABEL_FOLLOW_UP, now=LATER_NOW)
    assert state["completed_at"] == "2026-10-13T13:00:00Z" and state["receipt"]["items_total"] == 5
    row = db.query(SectionReview).filter(SectionReview.user_id == user.id, SectionReview.filing_id == later.id).one()
    assert set(row.labels) == set(revised)


def test_a_reworded_change_replaces_its_id_and_the_old_label_is_left_behind(db, flag_on):
    """A re-extraction that rewords a changed paragraph retires that change's id: the read counts
    only the labels on live ids, and the next write drops the retired one from the row."""
    user = _user(db, is_pro=True)
    _company, _prior, later = _compared_pair(db)
    ids = _ids(db, later)
    for item_id in ids:
        svc.set_label(db, user.id, later.id, item_id, svc.LABEL_REVIEWED, now=NOW)

    _extract(db, later, REWORDED_TEXT, now=LATER_NOW)
    reworded = _ids(db, later)
    retired = set(ids) - set(reworded)
    fresh = set(reworded) - set(ids)
    assert len(reworded) == 4 and len(retired) == 1 and len(fresh) == 1
    state = svc.review_state(db, user.id, later.id)
    assert state["counts"] == {"reviewed": 3, "follow_up": 0, "unlabeled": 1}
    assert set(state["labels"]) == set(ids) & set(reworded)
    assert state["completed_at"] is None and state["receipt"] is None

    state = svc.set_label(db, user.id, later.id, fresh.pop(), svc.LABEL_FOLLOW_UP, now=LATER_NOW)
    assert state["completed_now"] is True and state["completed_at"] == "2026-10-13T13:00:00Z"
    row = db.query(SectionReview).filter(SectionReview.user_id == user.id, SectionReview.filing_id == later.id).one()
    assert set(row.labels) == set(reworded), "the retired id's label is gone from the row"


def test_a_text_re_read_with_the_same_changes_reopens_the_receipt_until_a_label_reissues_it(db, flag_on):
    """Only the fingerprint moved (a re-extraction that changed bytes, not wording): every change
    keeps its label, the review reads as not complete, and marking any change again, unchanged,
    completes it with a receipt naming the new text."""
    user = _user(db, is_pro=True)
    _company, _prior, later = _compared_pair(db)
    ids = _ids(db, later)
    for item_id in ids:
        state = svc.set_label(db, user.id, later.id, item_id, svc.LABEL_REVIEWED, now=NOW)
    assert state["completed_at"] == "2026-10-13T12:00:00Z"

    row = sections.section_row(db, later.id)
    row.sha256 = "f" * 64
    db.commit()
    state = svc.review_state(db, user.id, later.id)
    assert state["counts"] == {"reviewed": 4, "follow_up": 0, "unlabeled": 0}
    assert state["completed_at"] is None and state["receipt"] is None
    assert db.query(SectionReview).filter(SectionReview.user_id == user.id).one().completed_at is not None, "stored, not shown"

    state = svc.set_label(db, user.id, later.id, ids[0], svc.LABEL_REVIEWED, now=LATER_NOW)
    assert state["completed_now"] is True and state["completed_at"] == "2026-10-13T13:00:00Z"
    assert state["receipt"]["texts"]["current"]["sha256"] == "f" * 64


def test_two_first_labels_racing_on_the_insert_both_land(db, flag_on, monkeypatch):
    """The loser of the insert race (the unique row per reader, filing and section) re-reads the
    winner's row, locked, and labels that; nothing is lost and nothing raises."""
    user = _user(db, is_pro=True)
    _company, _prior, later = _compared_pair(db)
    ids = _ids(db, later)
    svc.set_label(db, user.id, later.id, ids[0], svc.LABEL_REVIEWED, now=NOW)

    real = svc._review_row
    reads: list[bool] = []

    def read_as_the_loser_saw_it(db_, user_id, filing_id, *, lock=False):
        reads.append(lock)
        if len(reads) == 1:
            return None  # the other request's row was not there when this one looked
        return real(db_, user_id, filing_id, lock=lock)

    monkeypatch.setattr(svc, "_review_row", read_as_the_loser_saw_it)
    state = svc.set_label(db, user.id, later.id, ids[1], svc.LABEL_FOLLOW_UP, now=NOW)
    assert reads == [True, True], "both reads of a write take the lock"
    assert state["labels"] == {ids[0]: "reviewed", ids[1]: "follow_up"}
    assert db.query(SectionReview).filter(SectionReview.user_id == user.id, SectionReview.filing_id == later.id).count() == 1


def test_a_write_reads_its_row_for_update_and_a_read_does_not(db, flag_on, monkeypatch):
    """SQLite renders FOR UPDATE as nothing, so the lock is pinned where it is asked for: the
    write's row query, and only there (PostgreSQL then serializes concurrent labels on one row)."""
    from sqlalchemy.orm import Query

    user = _user(db, is_pro=True)
    _company, _prior, later = _compared_pair(db)
    ids = _ids(db, later)
    real = Query.with_for_update
    locked: list[str] = []

    def spy(self, *args, **kwargs):
        locked.append(self.column_descriptions[0]["entity"].__tablename__)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Query, "with_for_update", spy)
    svc.review_state(db, user.id, later.id)
    assert locked == [], "a read holds no lock"
    svc.set_label(db, user.id, later.id, ids[0], svc.LABEL_REVIEWED, now=NOW)
    assert locked == ["section_reviews"]


# --- the endpoints -----------------------------------------------------------------------------

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as test_client:
        yield test_client


def test_endpoints_gate_on_the_entitlement_and_map_the_domain_errors(db, client, flag_on):
    from app.routers.auth import create_access_token

    _company, _prior, later = _compared_pair(db)
    ids = _ids(db, later)
    path = f"/api/summaries/filing/{later.id}/wording-review"

    assert client.get(path).status_code == 401
    free = _user(db, is_pro=False)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(data={"sub": free.email}))
    forbidden = client.get(path)
    assert forbidden.status_code == 403 and "Risk factor wording review" in forbidden.json()["detail"]
    assert client.put(f"{path}/labels", json={"item_id": ids[0], "label": "reviewed"}).status_code == 403

    pro = _user(db, is_pro=True)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(data={"sub": pro.email}))
    state = client.get(path)
    assert state.status_code == 200 and state.json()["status"] == "ok" and state.json()["items_total"] == 4

    labelled = client.put(f"{path}/labels", json={"item_id": ids[0], "label": "follow_up"})
    assert labelled.status_code == 200 and labelled.json()["labels"] == {ids[0]: "follow_up"}
    cleared = client.put(f"{path}/labels", json={"item_id": ids[0], "label": None})
    assert cleared.status_code == 200 and cleared.json()["labels"] == {}
    assert client.put(f"{path}/labels", json={"item_id": ids[0], "label": "skimmed"}).status_code == 422
    assert client.put(f"{path}/labels", json={"item_id": "not-a-change", "label": "reviewed"}).status_code == 422
    assert client.get("/api/summaries/filing/0/wording-review").status_code == 404
    assert client.put("/api/summaries/filing/0/wording-review/labels", json={"item_id": ids[0], "label": "reviewed"}).status_code == 404

    # A filing without a comparison yet: the state is unavailable and a label is a conflict.
    _c, _p, pending = _pair(db)
    assert client.get(f"/api/summaries/filing/{pending.id}/wording-review").json()["status"] == "unavailable"
    assert client.put(f"/api/summaries/filing/{pending.id}/wording-review/labels",
                      json={"item_id": ids[0], "label": "reviewed"}).status_code == 409
    client.cookies.clear()


# --- the dashboard feed ------------------------------------------------------------------------

def test_feed_carries_the_counts_for_a_viewer_with_access_and_the_review_for_the_full_list(db, flag_on):
    user = _user(db, is_pro=True)
    _company, _prior, later = _compared_pair(db, watched_by=user)
    ids = _ids(db, later)
    svc.set_label(db, user.id, later.id, ids[0], svc.LABEL_REVIEWED, now=NOW)

    def item(access):
        items = [i for i in compose_feed(db, user.id, section_access=access) if i["filing_id"] == later.id]
        assert len(items) == 1
        return items[0]

    assert item(sections.NO_SECTION_ACCESS)["wording_changes"] is None
    teaser = item(TEASER)["wording_changes"]
    assert teaser == {"items_total": 4, "has_changes": True, "reference_only": False,
                      "prior_reference_only": False, "review": None}
    full = item(sections.FULL_SECTION_ACCESS)["wording_changes"]
    assert full["items_total"] == 4 and full["review"] == {"labeled": 1, "completed_at": None}

    for item_id in ids[1:]:
        svc.set_label(db, user.id, later.id, item_id, svc.LABEL_REVIEWED, now=NOW)
    full = item(sections.FULL_SECTION_ACCESS)["wording_changes"]
    assert full["review"] == {"labeled": 4, "completed_at": "2026-10-13T12:00:00Z"}

    # The later text is re-extracted with one more paragraph: the card reads the review as the
    # endpoint does (the labels on live ids, no completion), never "Reviewed." off the stored row.
    _extract(db, later, REVISED_TEXT, now=LATER_NOW)
    full = item(sections.FULL_SECTION_ACCESS)["wording_changes"]
    endpoint = svc.review_state(db, user.id, later.id)
    assert full["items_total"] == 5 and endpoint["items_total"] == 5
    assert full["review"] == {"labeled": 4, "completed_at": None}
    assert full["review"]["labeled"] == len(endpoint["labels"]) and endpoint["completed_at"] is None

    # A watched company whose newest filing has no comparison yet shows no counts at all: no rows,
    # and an ok row whose prior is not extracted (its comparison fields are written as nulls).
    _c2, _p2, pending = _pair(db, watched_by=user)
    _c3, _p3, unpaired = _pair(db, watched_by=user)
    _extract(db, unpaired, LATER_TEXT)
    assert sections.section_row(db, unpaired.id).diff_prior_filing_id is None
    feed = compose_feed(db, user.id, section_access=sections.FULL_SECTION_ACCESS)
    assert next(i for i in feed if i["filing_id"] == pending.id)["wording_changes"] is None
    assert next(i for i in feed if i["filing_id"] == unpaired.id)["wording_changes"] is None


def test_feed_endpoint_resolves_the_viewer_access(db, client, flag_on):
    from app.routers.auth import create_access_token

    user = _user(db, is_pro=False)
    _company, _prior, later = _compared_pair(db, watched_by=user)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(data={"sub": user.email}))
    resp = client.get("/api/dashboard/feed")
    assert resp.status_code == 200
    item = next(i for i in resp.json()["items"] if i["filing_id"] == later.id)
    assert item["wording_changes"]["items_total"] == 4 and item["wording_changes"]["review"] is None
    client.cookies.clear()
