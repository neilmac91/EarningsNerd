"""Real PostgreSQL completeness, concurrent ownership and restart proofs for default-off source artifacts."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app import database
from app.models import FilingContentCache, FilingSourceBundle, FilingSourceExtraction, FilingSourceMember, Summary
from app.services import filing_source_store as store
from app.services.filing_source_types import FilingSourceError, SourceBundle, SourceMember
from tests.support.filing_source_fixtures import PRIMARY, seed_source
from tests.support.hang_guard import HANG_GUARD_S


@pytest.fixture
def postgres_engine():
    url = os.environ.get('FILING_SOURCE_TEST_DATABASE_URL')
    if not url:
        pytest.skip('FILING_SOURCE_TEST_DATABASE_URL is not configured')
    assert make_url(url).get_backend_name() == 'postgresql'
    schema = f'filing_source_{uuid4().hex}'
    engine = create_engine(url, connect_args={'options': f'-csearch_path={schema} -cstatement_timeout=5000'})
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        database.Base.metadata.create_all(engine)
        yield engine
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


@pytest.fixture
def factory(postgres_engine, monkeypatch):
    factory = sessionmaker(**{**database.SessionLocal.kw, 'bind': postgres_engine})
    monkeypatch.setattr(database, 'SessionLocal', factory)
    return factory


def candidate(identity, body=PRIMARY):
    return SourceBundle(identity, (SourceMember(0, 'primary', identity.primary_filename,
        hashlib.sha256(body).hexdigest(), len(body), 'text/html; charset=utf-8', '1'),))


def test_two_independent_transactions_choose_one_complete_source(factory):
    identity = seed_source(factory=factory)
    proposals = [candidate(identity), candidate(identity, PRIMARY.replace(b'5.1', b'8.9'))]
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(store.commit_bundle, proposal) for proposal in proposals]
        results = [future.result(timeout=10) for future in futures]
    assert results[0] == results[1]
    with factory() as db:
        assert len(db.scalars(select(FilingSourceBundle)).all()) == 1
        assert len(db.scalars(select(FilingSourceMember)).all()) == 1
    assert store.lookup_bundle(identity) == results[0]


def test_uncommitted_members_are_invisible_and_rollback_publishes_nothing(factory, postgres_engine, monkeypatch):
    identity = seed_source(factory=factory)
    entered, release = Event(), Event()
    class PausedSession(Session):
        def commit(self):
            self.flush()
            entered.set()
            assert release.wait(HANG_GUARD_S)
            raise OperationalError('synthetic rollback', None, None)
    paused = sessionmaker(**{**database.SessionLocal.kw, 'bind': postgres_engine}, class_=PausedSession)
    # Only the writer's first session pauses; independent readers use normal sessions.
    calls = 0
    def session():
        nonlocal calls
        calls += 1
        return paused() if calls == 1 else factory()
    monkeypatch.setattr(database, 'SessionLocal', session)
    with ThreadPoolExecutor(max_workers=1) as worker:
        future = worker.submit(store.commit_bundle, candidate(identity))
        try:
            assert entered.wait(HANG_GUARD_S)
            assert store.lookup_bundle(identity) is None
        finally:
            release.set()
        with pytest.raises(FilingSourceError, match='artifact_commit_unverified'):
            future.result(timeout=10)
    with factory() as db:
        assert db.scalar(select(FilingSourceBundle)) is None
        assert db.scalar(select(FilingSourceMember)) is None


@pytest.mark.parametrize('phase', ['bundle', 'extraction'])
def test_lost_commit_acknowledgement_requires_fresh_committed_readback(factory, postgres_engine, monkeypatch, phase):
    identity = seed_source(factory=factory)
    bundle = candidate(identity)
    if phase == 'extraction':
        bundle = store.commit_bundle(bundle)
    calls = []
    class LostAckSession(Session):
        def commit(self):
            super().commit()
            calls.append('committed')
            raise OperationalError('synthetic lost acknowledgement', None, None)
    alternate = sessionmaker(**{**database.SessionLocal.kw, 'bind': postgres_engine}, class_=LostAckSession)
    def session():
        calls.append('session')
        return alternate() if 'committed' not in calls else factory()
    monkeypatch.setattr(database, 'SessionLocal', session)
    if phase == 'bundle':
        assert store.commit_bundle(bundle) == bundle
    else:
        assert store.commit_extraction(bundle, 'decoder', 'extractor', hashlib.sha256(PRIMARY).hexdigest(), len(PRIMARY))
    assert calls == ['session', 'committed', 'session']


def test_concurrent_extraction_same_version_cannot_change_content(factory):
    identity = seed_source(factory=factory)
    bundle = store.commit_bundle(candidate(identity))
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(store.commit_extraction, bundle, 'decoder', 'extractor', digit*64, 12) for digit in ('a', 'b')]
        success, failures = [], []
        for future in futures:
            try:
                success.append(future.result(timeout=10))
            except FilingSourceError as error:
                failures.append(error.code)
    assert len(success) == 1 and failures == ['artifact_extraction_conflict']
    with factory() as db:
        assert len(db.scalars(select(FilingSourceExtraction)).all()) == 1


def test_versioned_reextraction_does_not_overwrite_prior_record(factory):
    identity = seed_source(factory=factory)
    bundle = store.commit_bundle(candidate(identity))
    first = store.commit_extraction(bundle, 'decoder', 'extractor1', 'a'*64, 12)
    second = store.commit_extraction(bundle, 'decoder', 'extractor2', 'b'*64, 13)
    with factory() as db:
        assert db.get(FilingSourceExtraction, first).text_sha256 == 'a'*64
        assert db.get(FilingSourceExtraction, second).text_sha256 == 'b'*64


def test_database_checks_and_parent_references_refuse_incomplete_or_invalid_metadata(factory):
    identity = seed_source(factory=factory)
    bundle = store.commit_bundle(candidate(identity))
    with factory() as db:
        with pytest.raises(IntegrityError):
            db.execute(text('UPDATE earningsnerd_filing_source_bundles SET member_count=5 WHERE id=:id'), {'id': bundle.id})
            db.commit()
        db.rollback()
        with pytest.raises(IntegrityError):
            db.execute(text('DELETE FROM earningsnerd_filing_source_bundles WHERE id=:id'), {'id': bundle.id})
            db.commit()


def test_metadata_corruption_cannot_issue_a_committed_receipt(factory):
    identity = seed_source(factory=factory)
    bundle = store.commit_bundle(candidate(identity))
    with factory() as db:
        db.get(FilingSourceMember, (bundle.id, 0)).sha256 = 'a'*64
        db.commit()
    with pytest.raises(FilingSourceError, match='artifact_manifest_invalid'):
        store.lookup_bundle(identity)


def test_migration_replay_matches_orm_columns_constraints_and_preserves_rows(factory, postgres_engine):
    identity = seed_source(factory=factory)
    original = store.commit_bundle(candidate(identity))
    migration = Path(__file__).resolve().parents[2]/'migrations/20261102_earningsnerd_filing_source_bundles.sql'
    def schema_contract():
        inspector = inspect(postgres_engine)
        result = {}
        for name in ('earningsnerd_filing_source_bundles', 'earningsnerd_filing_source_members', 'earningsnerd_filing_source_extractions'):
            result[name] = {
                'columns': [(row['name'], str(row['type']), row['nullable'], row['default']) for row in inspector.get_columns(name)],
                'primary_key': inspector.get_pk_constraint(name)['constrained_columns'],
                'unique': sorted(tuple(row['column_names']) for row in inspector.get_unique_constraints(name)),
                'checks': sorted(row['sqltext'] for row in inspector.get_check_constraints(name)),
                'foreign_keys': sorted((tuple(row['constrained_columns']), row['referred_table'], tuple(row['referred_columns'])) for row in inspector.get_foreign_keys(name)),
                'indexes': sorted((tuple(row['column_names']), row['unique']) for row in inspector.get_indexes(name)),
            }
        return result
    original_schema = schema_contract()
    for _ in range(3):
        with postgres_engine.begin() as connection:
            connection.exec_driver_sql(migration.read_text())
    assert store.lookup_bundle(identity) == original
    # Exercise migration-created tables too, rather than only replay over create_all.
    tables = [FilingSourceExtraction.__table__, FilingSourceMember.__table__, FilingSourceBundle.__table__]
    with postgres_engine.begin() as connection:
        for table in tables:
            table.drop(connection)
        connection.exec_driver_sql(migration.read_text())
    assert schema_contract() == original_schema
    assert store.commit_bundle(original) == original
    assert store.commit_extraction(original, 'decoder', 'extractor', 'b'*64, 12)


@pytest.mark.parametrize('phase', ['crash_before_commit', 'crash_after_commit'])
def test_physical_process_crash_and_restart_never_trust_partial_capture(factory, postgres_engine, tmp_path, phase):
    identity = seed_source(factory=factory)
    with postgres_engine.connect() as connection:
        schema = connection.scalar(text('SELECT current_schema()'))
    request = {'dsn': postgres_engine.url.render_as_string(hide_password=False), 'schema': schema,
               'identity': asdict(identity), 'directory': str(tmp_path), 'mode': phase}
    command = [sys.executable, '-m', 'tests.support.filing_source_restart_probe']
    def run(mode):
        return subprocess.run(command, input=json.dumps({**request, 'mode': mode}), text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    crashed = run(phase)
    assert crashed.returncode == (17 if phase == 'crash_after_commit' else 18), crashed.stderr[-1000:]
    assert list(tmp_path.iterdir()), 'object writes occurred before the forced exit'
    if phase == 'crash_before_commit':
        assert store.lookup_bundle(identity) is None
        recovered = run('capture')
        expected_calls = ['primary']
    else:
        assert store.lookup_bundle(identity) is not None
        with factory() as db:
            assert db.scalar(select(FilingSourceExtraction)) is None
        recovered = run('reuse')
        expected_calls = []
    assert recovered.returncode == 0, recovered.stderr[-1000:]
    receipt = json.loads(recovered.stdout.splitlines()[-1])
    assert receipt['sec_calls'] == expected_calls
    assert receipt['text_sha256'] == hashlib.sha256(PRIMARY).hexdigest()


@pytest.mark.asyncio
async def test_losing_summary_insert_rolls_back_excerpt_and_source_publication(factory, monkeypatch):
    from app.services import summary_pipeline as pipeline
    from app.services.filing_source_types import CommittedFilingSource
    from app.services.summary_stages import finalize
    from app.services.summary_stages.generation_run import GenerationRun
    from tests.support.summary_stream_harness import CANONICAL_PAYLOAD

    identity = seed_source(factory=factory)
    bundle = store.commit_bundle(candidate(identity))
    digest = hashlib.sha256(PRIMARY).hexdigest()
    extraction = store.commit_extraction(bundle, 'decoder', 'extractor', digest, len(PRIMARY))
    safe = {'artifact': {'bundle_id': bundle.id, 'extraction_id': extraction}}
    receipt = CommittedFilingSource(bundle, extraction, PRIMARY.decode(), digest, 'decoder', 'extractor', safe)
    monkeypatch.setattr(pipeline.settings, 'FILING_SOURCE_ARTIFACTS_ENABLED', True)
    rendezvous = Barrier(2)
    original = finalize._filing_with_cache
    def simultaneous_snapshot(session, filing_id):
        value = original(session, filing_id)
        rendezvous.wait(timeout=HANG_GUARD_S)
        return value
    monkeypatch.setattr(finalize, '_filing_with_cache', simultaneous_snapshot)
    monkeypatch.setattr(pipeline, 'assess_quality', lambda *a, **k: {'tier': 'full', 'reasons': []})
    runs = []
    for excerpt in ('Revenue $5.1 billion.', 'GAAP EPS $19.16.'):
        run = GenerationRun(identity.filing_id, None, None, 'offline', None, {}, emit_funnel_telemetry=False)
        run.artifact_mode = True
        run.filing_fields = {'company_cik': identity.cik, 'accession_number': identity.accession,
                             'filing_type': identity.filing_type, 'document_url': identity.url_for(identity.primary_filename)}
        run.filing_text = PRIMARY.decode()
        run.filing_document_url = identity.url_for(identity.primary_filename)
        run.filing_source_provenance = safe
        run.committed_source = receipt
        run.excerpt = excerpt
        run.summary_status = 'complete'
        run.summary_payload = deepcopy(CANONICAL_PAYLOAD)
        run.summary_payload['business_overview'] = excerpt
        runs.append(run)
    async def finish(run):
        try:
            return [event async for event in finalize.finalize(run)]
        finally:
            await run.release()
    # Above the barrier's guard, so a snapshot left waiting breaks the barrier first.
    results = await asyncio.wait_for(asyncio.gather(*(finish(run) for run in runs)), timeout=HANG_GUARD_S + 10)
    assert all(result[-1]['type'] == 'complete' for result in results)
    with factory() as db:
        summaries = db.scalars(select(Summary).where(Summary.filing_id == identity.filing_id)).all()
        assert len(summaries) == 1
        cache = db.get(FilingContentCache, identity.filing_id)
        assert cache.critical_excerpt == summaries[0].business_overview
        assert cache.critical_excerpt in ('Revenue $5.1 billion.', 'GAAP EPS $19.16.')
        assert cache.risk_source_text is None
        assert summaries[0].raw_summary['filing_source_provenance'] == safe
