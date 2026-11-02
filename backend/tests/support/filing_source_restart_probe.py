"""Local PostgreSQL crash/restart probe. Executed only with the test home's owned schema/files."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.config import settings
from app.services import filing_source_storage as storage
from app.services.edgar import filing_source_capture as capture
from app.services.filing_source_types import FilingSourceIdentity, StoredSourceObject
from app.services.request_work import RequestWork
from tests.support.filing_source_fixtures import PRIMARY, source_metadata


def main():
    request = json.loads(sys.stdin.read())
    engine = create_engine(request['dsn'], connect_args={'options': '-csearch_path='+request['schema']+' -cstatement_timeout=5000'})
    database.SessionLocal = sessionmaker(**{**database.SessionLocal.kw, 'bind': engine})
    identity = FilingSourceIdentity(**request['identity'])
    root = Path(request['directory'])
    calls = []

    class LocalObjects:
        async def put(self, identity_hash, body, *, deadline):
            digest = hashlib.sha256(body).hexdigest()
            (root/digest).write_bytes(body)
            return StoredSourceObject('1', digest, len(body))

        async def read(self, identity_hash, digest, length, generation, *, deadline):
            return (root/digest).read_bytes()

    storage.BoundedFilingSourceStorage = lambda bucket: LocalObjects()
    settings.FILING_SOURCE_ARTIFACTS_BUCKET = 'offline-test-only'

    async def primary(*args, **kwargs):
        if request['mode'] == 'reuse':
            raise AssertionError('restart contacted SEC')
        calls.append('primary')
        return PRIMARY, source_metadata(identity, identity.primary_filename, PRIMARY)

    capture.sec_edgar_service.get_filing_primary_bytes = primary
    if request['mode'] == 'crash_after_commit':
        actual = capture.store.commit_bundle
        def committed_then_crash(bundle):
            actual(bundle)
            os._exit(17)
        capture.store.commit_bundle = committed_then_crash
    elif request['mode'] == 'crash_before_commit':
        capture.store.commit_bundle = lambda bundle: os._exit(18)

    async def run():
        owner = RequestWork()
        try:
            result = await capture.load_or_capture_source(identity, deadline=time.monotonic()+20, owner=owner)
            print(json.dumps({'bundle_id': result.bundle.id, 'text_sha256': result.grounding_sha256, 'sec_calls': calls}))
        finally:
            await owner.drain()
    try:
        asyncio.run(run())
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
