"""Synthetic fixed filing bodies and an in-memory object boundary, never live SEC/GCS."""
from __future__ import annotations

import hashlib
from uuid import uuid4

from app import database
from app.models import Company, Filing, FilingContentCache
from app.services.filing_source_types import FilingSourceIdentity, SOURCE_REPRESENTATION, StoredSourceObject
from app.utils.datetimes import utcnow
from app.utils.sec_urls import build_sec_archive_url

PRIMARY = b'<html><body><h1>Quarterly report</h1><p>Revenue $5.1 billion. GAAP EPS $19.16. Cash flow $2.7 billion.</p></body></html>'
COVER = b'<p>Item 2.02 Results of Operations and Financial Condition.</p><p>Our earnings release is attached as <a href="release.htm">Exhibit 99.1</a>.</p>'
RELEASE = b'<h1>Third quarter results</h1><p>Revenue $5.1 billion. GAAP EPS $19.16. Cash flow $2.7 billion.</p>'
LEGACY = 'LEGACY EXCERPT MUST NOT BECOME ARTIFACT GROUNDING'


def seed_source(*, factory=None, form='10-Q', legacy=True):
    factory = factory or database.SessionLocal
    with factory() as db:
        company = Company(cik=str(800_000_000 + int(uuid4().hex[:9], 16)),
                          ticker=uuid4().hex[:8], name='Synthetic Source Fixture')
        db.add(company)
        db.flush()
        accession = f'0000872589-26-{int(uuid4().hex[:8], 16) % 1_000_000:06d}'
        archive = build_sec_archive_url(company.cik, accession)
        filing = Filing(company_id=company.id, accession_number=accession, filing_type=form,
                        filing_date=utcnow(), document_url=archive+'primary.htm', sec_url=archive)
        db.add(filing)
        db.flush()
        if legacy:
            db.add(FilingContentCache(filing_id=filing.id, critical_excerpt=LEGACY, risk_source_text=LEGACY))
        db.commit()
        snapshot = {'company_cik': company.cik, 'accession_number': accession,
                    'document_url': filing.document_url, 'filing_type': form}
        return FilingSourceIdentity.from_filing(filing.id, snapshot)


def source_metadata(identity, filename, body, content_type='text/html; charset=utf-8'):
    return {'representation': SOURCE_REPRESENTATION, 'cik': identity.cik,
            'accession_number': identity.accession, 'filename': filename,
            'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body),
            'requested_url': identity.url_for(filename), 'final_url': identity.url_for(filename),
            'status_code': 200, 'content_type': content_type, 'content_encoding': 'identity'}


class MemorySourceObjects:
    """Only replaces the verified object boundary; store/coordinator/pipeline stay real."""
    def __init__(self):
        self.bodies = {}
        self.puts = []
        self.reads = []

    async def put(self, identity_sha256, content, *, deadline):
        digest = hashlib.sha256(content).hexdigest()
        self.bodies[(identity_sha256, digest)] = content
        self.puts.append((identity_sha256, digest))
        return StoredSourceObject('1', digest, len(content))

    async def read(self, identity_sha256, content_sha256, byte_length, generation, *, deadline):
        self.reads.append((identity_sha256, content_sha256, generation))
        return self.bodies[(identity_sha256, content_sha256)]
