"""Disposable source preparation uses real ORM/extraction, never expected answers or AI."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from evals import copilot_bootstrap as boot


def test_manifest_is_identity_only_and_hashes_exact_bytes(tmp_path):
    sources, digest = boot.load_sources()
    assert len(sources) == 6 and len({s["ticker"] for s in sources}) == 5
    assert len({s["accession_number"] for s in sources if s["ticker"] == "BABA"}) == 2
    assert digest == hashlib.sha256(boot.SOURCE_MANIFEST.read_bytes()).hexdigest()
    path = tmp_path / "sources.json"
    for change in ({"expected_facts": [100]}, {"expected_answer": "100"}, {"document_url": "https://example.com/source"},
                   {"accession_number": "wrong"}):
        bad = {**sources[0], **change}
        path.write_text(json.dumps({"schema_version": 1, "sources": [bad]}))
        with pytest.raises(ValueError):
            boot.load_sources(path)


def test_target_and_engine_guards_reject_existing_remote_and_aliases(tmp_path):
    existing = tmp_path / "existing.db"
    existing.write_bytes(b"keep me")
    alias = tmp_path / "alias.db"
    alias.symlink_to(existing)
    for target in (str(existing), str(alias), "relative.db", ":memory:", "postgresql://production/db"):
        with pytest.raises(ValueError):
            boot.validate_database(target)
    target = boot.validate_database(str(tmp_path / "new.db"))
    assert target == tmp_path / "new.db" and existing.read_bytes() == b"keep me"
    from sqlalchemy.engine import make_url
    for url in ("postgresql://production/db", "sqlite:///:memory:", "sqlite:///other.db", "sqlite:///" + str(target) + "?mode=ro"):
        with pytest.raises(ValueError, match="resolved_engine_target_mismatch"):
            boot.verify_engine(SimpleNamespace(url=make_url(url)), target)
    boot.verify_engine(SimpleNamespace(url=make_url("sqlite:///" + str(target))), target)


def test_existing_database_aborts_before_imports_and_retains_failed_artifact(tmp_path, monkeypatch):
    target = tmp_path / "existing.db"
    target.write_bytes(b"original")
    monkeypatch.setattr(boot, "_load_runtime", lambda: pytest.fail("unsafe runtime imported"))
    result = asyncio.run(boot.bootstrap(str(target), str(tmp_path / "evidence")))
    assert result["status"] == "unavailable" and result["sources"] == []
    assert result["errors"] == [{"stage": "target_guard", "error_type": "ValueError", "reason": "database_already_exists"}]
    assert target.read_bytes() == b"original"
    assert json.loads((tmp_path / "evidence/preparation.json").read_text()) == result


# Execute in fresh processes: app.config/database must NOT already exist when the bootstrap
# configures the target. Only network seams are stubbed; SQLite, normalization and excerpt cache
# are the production implementations. No golden values are used as source-service responses.
PREPARE = r'''
import asyncio, json, os
from pathlib import Path
from types import SimpleNamespace
from evals import copilot_bootstrap as b
root=Path(os.environ['PREP_ROOT'])
source_path=root/'copilot_sources.json'
sources,_=b.load_sources()
source_path.write_text(json.dumps({'schema_version':1,'sources':sources}))
(root/'copilot_golden_set.json').write_text(os.environ['GOLDEN_EXPECTATION'])
original_read=Path.read_bytes
original_text=Path.read_text
forbidden_reads=[]
def check_read(path):
    if 'golden' in path.name:
        forbidden_reads.append(str(path))
        raise AssertionError('expected answers were read')
def guarded_read(path):
    check_read(path)
    return original_read(path)
def guarded_text(path,*args,**kwargs):
    check_read(path)
    return original_text(path,*args,**kwargs)
Path.read_bytes=guarded_read
Path.read_text=guarded_text
original_load=b.load_sources
b.load_sources=lambda: original_load(source_path)
original_runtime=b._load_runtime
calls=[]
def runtime():
    rt=original_runtime()
    assert rt.settings.ENVIRONMENT=='test' and not rt.settings.ENABLE_HISTORY_BACKFILL_ON_VISIT
    assert rt.settings.USE_STATEMENT_FINANCIALS and rt.settings.USE_EDGARTOOLS_SECTIONS and rt.settings.ENABLE_FPI_FILINGS
    assert Path(rt.engine.url.database).resolve()==root/'facts.db'
    async def metadata(cik, forms, limit):
        assert limit==40
        return [{**s,'company_name':'SEC source issuer','filing_date':'2026-07-01',
                 'report_date':'2025-03-31','sec_url':s['document_url']} for s in sources
                if s['cik']==cik and s['filing_type'] in forms]
    async def document(url):
        calls.append(url)
        return '<html><body>Revenue was CNY 321 million. Selected filing operations. '+('source narrative '*1000)+'</body></html>'
    async def xbrl(accession,cik):
        if os.environ.get('FAIL_PREPARATION') and accession==sources[-1]['accession_number']: return None
        return {'revenue':[{'period':'2025-03-31','value':321000000,'currency':'CNY',
                'form':'20-F','accn':accession,'raw_tag':'us-gaap:Revenues'}],'reporting_currency':'CNY'}
    async def sections(*args):
        return {'financials':'Revenue CNY 321 million. '+('source table '*1000),
                'mda':'Selected source management discussion. '+('source prose '*1000)}
    rt.sec=SimpleNamespace(get_filings=metadata,get_filing_document=document)
    rt.xbrl=SimpleNamespace(get_xbrl_data=xbrl,get_filing_sections=sections)
    return rt
b._load_runtime=runtime
report=asyncio.run(b.bootstrap(str(root/'facts.db'),str(root/'evidence')))
assert not forbidden_reads, 'expected answers were read: '+repr(forbidden_reads)
from app.database import SessionLocal
from app.models import Company,Filing,Summary,User,FilingContentCache
from app.models.financial_fact import FinancialFact
with SessionLocal() as db:
    rows=[(r.accession,float(r.value),r.unit) for r in db.query(FinancialFact).order_by(FinancialFact.accession)]
    assert db.query(Summary).count()==0 and db.query(User).count()==0
    assert db.query(Company).count()==5 if not os.environ.get('FAIL_PREPARATION') else db.query(Company).count()==4
    caches=[r.critical_excerpt for r in db.query(FilingContentCache).order_by(FilingContentCache.filing_id)]
    babas=[f.accession_number for f in db.query(Filing).join(Company).filter(Company.ticker=='BABA')]
print('RESULT:'+json.dumps({'report':report,'rows':rows,'caches':caches,'babas':babas,'calls':calls}))
'''


def _prepare(tmp_path, *, expectation="999999", failure=False):
    tmp_path.mkdir()
    env = {**os.environ, "PREP_ROOT": str(tmp_path), "GOLDEN_EXPECTATION": expectation}
    if failure:
        env["FAIL_PREPARATION"] = "yes"
    result = subprocess.run([sys.executable, "-c", PREPARE], env=env, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(next(line[7:] for line in result.stdout.splitlines() if line.startswith("RESULT:")))


def test_actual_source_normalization_is_independent_of_expected_answers(tmp_path):
    first = _prepare(tmp_path / "one", expectation="999999")
    second = _prepare(tmp_path / "two", expectation="111111")
    assert first["rows"] == second["rows"] and first["caches"] == second["caches"]
    assert len(first["rows"]) == 6 and all(r[1:] == [321000000, "CNY"] for r in first["rows"])
    assert len(first["babas"]) == 2 and len(set(first["babas"])) == 2
    report = first["report"]
    assert report["status"] == "complete" and report["errors"] == []
    assert report["database_sha256"] == hashlib.sha256(Path(report["database_path"]).read_bytes()).hexdigest()
    assert report.get("database_artifact_path") == "prepared-source.db"
    archived = tmp_path / "one/evidence" / report["database_artifact_path"]
    assert archived.is_file(), "portable source database was not archived"
    assert archived.read_bytes() == Path(report["database_path"]).read_bytes()
    assert set(report["planned_accessions"]) == {r[0] for r in first["rows"]}
    assert len(first["calls"]) == 6
    for source in report["sources"]:
        assert source["status"] == "complete" and source["fact_count"] == 1
        assert source["reporting_currency"] == "CNY"
        assert set(source["artifacts"]) == {"html", "xbrl", "sections", "excerpt"}
        for artifact in source["artifacts"].values():
            relative = Path(source["accession_number"]) / Path(artifact["path"]).name
            assert artifact.get("relative_path") == str(relative)
            assert (tmp_path / "one/evidence" / relative).read_bytes() == Path(artifact["path"]).read_bytes()
            data = Path(artifact["path"]).read_bytes()
            assert artifact["sha256"] == hashlib.sha256(data).hexdigest() and artifact["bytes"] == len(data)


def test_missing_extraction_retains_declared_population_and_partial_evidence(tmp_path):
    result = _prepare(tmp_path / "failed", failure=True)
    report = result["report"]
    assert report["status"] == "unavailable" and len(report["planned_accessions"]) == 6
    assert len(report["sources"]) == 6 and len(result["rows"]) == 5
    failed = report["sources"][-1]
    assert failed["status"] == "unavailable"
    assert failed["error"] == {"stage": "xbrl", "error_type": "ValueError", "reason": "xbrl_unavailable"}
    assert set(failed["artifacts"]) == {"html", "xbrl"}


def test_cli_returns_nonzero_for_unavailable_preparation(monkeypatch):
    async def unavailable(*args):
        return {"status": "unavailable", "sources": []}
    monkeypatch.setattr(boot, "bootstrap", unavailable)
    monkeypatch.setattr(sys, "argv", ["copilot_bootstrap", "--database", "/unused.db", "--output", "/unused"])
    assert boot.main() == 1
