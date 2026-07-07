"""P0-1 guardrail (data-quality plan): the ticker repair script.

Pins: primary = FIRST file-order entry per CIK; padded and stripped CIK spellings both match;
rows absent from the SEC file are reported but never touched; dry run (the default) writes
NOTHING; --apply writes exactly the reported changes.
"""
from types import SimpleNamespace

import pytest

from scripts.repair_ticker_by_cik import build_primary_map, compute_changes, main
from app.database import SessionLocal
from app.models import Company


@pytest.fixture(scope="module", autouse=True)
def _tables():
    # These tests drive the schema via SessionLocal (no TestClient lifespan), so they must
    # build the tables themselves — otherwise they depend on collection order for another
    # test to have created them in the shared sqlite file.
    from app.database import Base, engine

    Base.metadata.create_all(bind=engine)


FIXTURE_TICKERS = {
    "0": {"cik_str": 19617, "ticker": "JPM", "title": "JPMORGAN CHASE & CO"},
    "1": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet Inc."},
    "2": {"cik_str": 19617, "ticker": "JPM-PC", "title": "JPMORGAN CHASE & CO"},
    "3": {"cik_str": 1652044, "ticker": "GOOGN", "title": "Alphabet Inc."},
    "4": {"cik_str": 19617, "ticker": "JPM-PM", "title": "JPMORGAN CHASE & CO"},
}


def test_build_primary_map_first_entry_wins():
    primary = build_primary_map(FIXTURE_TICKERS)
    assert primary == {"19617": "JPM", "1652044": "GOOGL"}


def test_compute_changes_matches_padded_and_stripped_cik():
    primary = build_primary_map(FIXTURE_TICKERS)
    rows = [
        SimpleNamespace(id=1, cik="0000019617", ticker="JPM-PM", name="JPM padded"),
        SimpleNamespace(id=2, cik="1652044", ticker="GOOGN", name="Alphabet stripped"),
        SimpleNamespace(id=3, cik="0000019617", ticker="JPM", name="already canonical"),
        SimpleNamespace(id=4, cik="0009999999", ticker="GONE", name="delisted"),
    ]
    changes, not_in_file = compute_changes(rows, primary)
    assert [(r.id, t) for r, t in changes] == [(1, "JPM"), (2, "GOOGL")]
    assert [r.id for r in not_in_file] == [4]


@pytest.fixture()
def seeded_db(monkeypatch):
    async def fake_tickers():
        return FIXTURE_TICKERS

    import scripts.repair_ticker_by_cik as script_mod

    monkeypatch.setattr(script_mod, "_fetch_tickers", fake_tickers)

    db = SessionLocal()
    db.query(Company).filter(Company.cik.in_(["0000019617", "0001652044"])).delete()
    db.commit()
    db.add(Company(cik="0000019617", ticker="JPM-PM", name="JPMORGAN CHASE & CO"))
    db.add(Company(cik="0001652044", ticker="GOOGL", name="Alphabet Inc."))
    db.commit()
    yield db
    db.rollback()
    db.query(Company).filter(Company.cik.in_(["0000019617", "0001652044"])).delete()
    db.commit()
    db.close()


def test_dry_run_default_writes_nothing(seeded_db, capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "'JPM-PM' -> 'JPM'" in out
    seeded_db.expire_all()
    assert (
        seeded_db.query(Company).filter(Company.cik == "0000019617").one().ticker == "JPM-PM"
    )


def test_apply_repairs_only_mismatched_rows(seeded_db, capsys):
    assert main(["--apply"]) == 0
    out = capsys.readouterr().out
    assert "APPLIED — 1 row(s) repaired." in out
    seeded_db.expire_all()
    assert seeded_db.query(Company).filter(Company.cik == "0000019617").one().ticker == "JPM"
    assert seeded_db.query(Company).filter(Company.cik == "0001652044").one().ticker == "GOOGL"


def test_apply_aborts_on_collision_without_writing(monkeypatch, capsys):
    """A post-repair collision (two rows converging on one ticker) must abort with exit 1 and
    write nothing (adversarial/review guard against ticker-key corruption)."""
    # Two DISTINCT CIKs both mapping to primary 'DUP' — an (unlikely) SEC-file state that would
    # shadow one company in every ticker-keyed lookup.
    collide = {
        "0": {"cik_str": 111, "ticker": "DUP", "title": "Alpha"},
        "1": {"cik_str": 222, "ticker": "DUP", "title": "Beta"},
    }

    async def fake_tickers():
        return collide

    import scripts.repair_ticker_by_cik as script_mod

    monkeypatch.setattr(script_mod, "_fetch_tickers", fake_tickers)

    db = SessionLocal()
    db.query(Company).filter(Company.cik.in_(["0000000111", "0000000222"])).delete()
    db.commit()
    db.add(Company(cik="0000000111", ticker="AAA", name="Alpha"))
    db.add(Company(cik="0000000222", ticker="BBB", name="Beta"))
    db.commit()
    try:
        assert main(["--apply"]) == 1
        out = capsys.readouterr().out
        assert "ERROR — post-repair ticker collisions" in out
        db.expire_all()
        # Nothing written — both rows keep their original tickers.
        assert db.query(Company).filter(Company.cik == "0000000111").one().ticker == "AAA"
        assert db.query(Company).filter(Company.cik == "0000000222").one().ticker == "BBB"
    finally:
        db.query(Company).filter(Company.cik.in_(["0000000111", "0000000222"])).delete()
        db.commit()
        db.close()
