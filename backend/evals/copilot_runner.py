"""Complete, three-draw Copilot evaluation against a source-only scratch database.

The opt-in same-repository PR workflow prepares actual SEC sources first. No local/production
DB inference, unverified-case promotion, or answered-only denominator is accepted.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from copy import deepcopy
from unittest.mock import patch
import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from evals.copilot_schema import CopilotGoldenCase

GOLDEN_PATH = Path(__file__).with_name('copilot_golden_set.json')
SOURCES_PATH = Path(__file__).with_name('copilot_sources.json')
REPORTS_DIR = Path(__file__).with_name('reports')


def _load_cases(path: Path) -> list[CopilotGoldenCase]:
    data = json.loads(path.read_text())
    return [CopilotGoldenCase.from_dict(c) for c in data.get('cases', [])]


def _plan(cases: list[CopilotGoldenCase], runs: int) -> list[dict]:
    if isinstance(runs, bool) or not isinstance(runs, int) or runs < 3:
        raise ValueError('acceptance requires at least three complete draws')
    if len(cases) < 6 or len({c.ticker for c in cases}) < 5:
        raise ValueError('acceptance requires six accessions and five verified issuers')
    if len({c.accession_number for c in cases}) != len(cases):
        raise ValueError('duplicate accession in golden cohort')
    rows = []
    for c in cases:
        if not c.verified or not c.qa or not re.fullmatch(r'\d{10}-\d{2}-\d{6}', c.accession_number):
            raise ValueError('unverified or malformed golden case')
        try:
            date.fromisoformat(c.period_of_report)
            if not re.fullmatch(r'[A-Z]{3}', c.reporting_currency):
                raise ValueError('invalid native reporting currency')
            for q in c.qa:
                if set(q.expected_periods) != {f.metric for f in q.expected_facts}:
                    raise ValueError('every expected metric needs an explicit period')
                if any(date.fromisoformat(p) > date.fromisoformat(c.period_of_report) for p in q.expected_periods.values()):
                    raise ValueError('expected period outside viewed filing')
        except (TypeError, ValueError):
            raise ValueError('invalid golden period/currency metadata') from None
        ids = [q.question_id for q in c.qa]
        if any(not isinstance(i, str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('questions require unique stable identities')
        for q in c.qa:
            for repeat in range(runs):
                rows.append({'ticker': c.ticker, 'accession_number': c.accession_number,
                             'question_id': q.question_id, 'run_index': repeat})
    return rows


def _identity(row: dict) -> tuple:
    return tuple(row.get(k) for k in ('ticker', 'accession_number', 'question_id', 'run_index'))


def validate_report(report: dict, *, expected_plan: list[dict] | None = None) -> list[str]:
    """Completeness is independent of pass-rate statistics: every planned row must be scored."""
    failures = []
    plan = report.get('planned_attempts')
    rows = report.get('results')
    if not isinstance(plan, list) or not plan or not isinstance(rows, list):
        return ['missing planned cohort/results']
    try:
        expected = [_identity(r) for r in plan]
        actual = [_identity(r) for r in rows]
        if len(set(expected)) != len(expected) or len(set(actual)) != len(actual) or set(actual) != set(expected):
            failures.append('missing/duplicate/unexpected attempt identities')
    except (AttributeError, TypeError):
        return ['malformed attempt identities']
    if len({r['accession_number'] for r in plan}) < 6 or len({r['ticker'] for r in plan}) < 5:
        failures.append('incomplete verified issuer cohort')
    runs = report.get('runs')
    if type(runs) is not int or runs < 3:
        failures.append('fewer than three draws')
    else:
        groups = {(r['ticker'], r['accession_number'], r['question_id']) for r in plan}
        if set(expected) != {(*g, n) for g in groups for n in range(runs)}:
            failures.append('planned repeats incomplete')
    if expected_plan is None:
        try:
            expected_plan = _plan(_load_cases(GOLDEN_PATH), runs)
        except (ValueError, TypeError):
            failures.append('authoritative golden plan unavailable')
    if expected_plan is not None and set(expected) != {_identity(r) for r in expected_plan}:
        failures.append('declared plan differs from full verified golden cohort')
    scored = [r for r in rows if isinstance(r.get('score'), dict)]
    errors = sum(bool(r.get('error')) for r in rows)
    for row in rows:
        score = row.get('score')
        if row.get('error') or row.get('terminal_complete') is not True or not isinstance(score, dict):
            failures.append('operationally incomplete attempt')
        elif score.get('passed') is not True or score.get('gate_failures') != []:
            failures.append('deterministic trust/accuracy veto')
    summary = report.get('summary', {})
    if (summary.get('expected') != len(plan) or summary.get('completed') != len(rows)
            or summary.get('scored') != len(scored) or summary.get('errors') != errors):
        failures.append('inconsistent attempt counts')
    return list(dict.fromkeys(failures))


def validate_preparation(path: Path, cases: list[CopilotGoldenCase]) -> dict:
    prep = json.loads(path.read_text())
    expected = {c.accession_number for c in cases}
    if prep.get('status') != 'complete' or prep.get('errors') != []:
        raise ValueError('source preparation incomplete')
    if prep.get('source_manifest_sha256') != hashlib.sha256(SOURCES_PATH.read_bytes()).hexdigest():
        raise ValueError('source manifest differs from preparation')
    sources = prep.get('sources', [])
    if (set(prep.get('planned_accessions', [])) != expected or len(sources) != len(expected)
            or {r.get('accession_number') for r in sources} != expected
            or any(r.get('status') != 'complete' for r in sources)):
        raise ValueError('source preparation cohort incomplete')
    # Resolve only declared portable members inside the downloaded artifact directory. Original
    # host paths remain provenance metadata; they are never fallback reads from another checkout.
    bundle = path.resolve().parent
    if prep.get('database_artifact_path') != 'prepared-source.db':
        raise ValueError('portable prepared database locator unavailable')
    database = bundle / 'prepared-source.db'
    if not database.is_file() or database.is_symlink():
        raise ValueError('prepared scratch database is unavailable')
    if prep.get('database_sha256') != hashlib.sha256(database.read_bytes()).hexdigest():
        raise ValueError('prepared database changed')
    cases_by_accession = {c.accession_number: c for c in cases}
    filenames = {'html':'filing.html', 'xbrl':'xbrl.json', 'sections':'sections.json', 'excerpt':'excerpt.txt'}
    for source in sources:
        case = cases_by_accession[source['accession_number']]
        if source.get('reporting_currency') != case.reporting_currency:
            raise ValueError('extracted native currency differs from verified source')
        for kind, filename in filenames.items():
            artifact = source.get('artifacts', {}).get(kind, {})
            expected = f"{case.accession_number}/{filename}"
            artifact_path = bundle / expected
            if (artifact.get('relative_path') != expected or artifact_path.is_symlink()
                    or not artifact_path.is_file() or artifact_path.resolve().parent != (bundle / case.accession_number).resolve()
                    or (bundle / case.accession_number).is_symlink()
                    or hashlib.sha256(artifact_path.read_bytes()).hexdigest() != artifact.get('sha256')):
                raise ValueError('prepared source artifact changed or missing')
    prep['original_database_path'] = prep.get('database_path')
    prep['database_path'] = str(database)
    return prep


def _snapshot_for_case(case: CopilotGoldenCase):
    from sqlalchemy.orm import joinedload
    from app.database import SessionLocal
    from app.models import Company, Filing
    from app.services.copilot_service import snapshot_filing
    with SessionLocal() as db:
        filing = (db.query(Filing).options(joinedload(Filing.content_cache), joinedload(Filing.company))
                  .join(Company, Filing.company_id == Company.id)
                  .filter(Company.cik == case.cik, Filing.accession_number == case.accession_number).first())
        return snapshot_filing(filing) if filing else None


async def _answer(filing_snap, question: str, *, trace: dict | None = None) -> tuple[str, list[dict], str, int]:
    from app.services.copilot_service import answer_filing_question, openai_service
    original_stream = openai_service.stream_chat_with_tools
    def observed_stream(messages, tools, run_tool, **kwargs):
        trace['initial_messages'] = deepcopy(messages)
        trace['tool_schema'] = deepcopy(tools)
        trace['generation_options'] = {k: kwargs.get(k) for k in ('model','max_tokens','temperature')}
        def observed_tool(name, args):
            result = run_tool(name, args)
            trace['tool_results'].append({'name': name, 'args': deepcopy(args), 'result': deepcopy(result)})
            return result
        return original_stream(messages, tools, observed_tool, **kwargs)
    if trace is not None:
        trace['tool_results'] = []
    observer = patch.object(openai_service, 'stream_chat_with_tools', observed_stream) if trace is not None else nullcontext()
    complete = None
    with observer:
        async for event in answer_filing_question(filing=filing_snap, question=question):
            if not isinstance(event, dict):
                raise ValueError('malformed stream event')
            if complete is not None:
                raise ValueError('event after terminal completion')
            if event.get('type') == 'error':
                raise ValueError('provider error event')
            if event.get('type') == 'complete':
                # The real refusal producer has no strip-count field. Only that omission is zero.
                stripped = event.get('misplaced_fact_markers', 0 if event.get('kind') == 'not_disclosed' else None)
                if (not isinstance(event.get('answer'), str) or not event['answer'].strip()
                        or event.get('kind') not in {'answer', 'not_disclosed'}
                        or not isinstance(event.get('citations'), list)
                        or any(not isinstance(c, dict) for c in event['citations'])
                        or type(stripped) is not int or stripped < 0):
                    raise ValueError('malformed terminal completion')
                complete = {**event, 'misplaced_fact_markers': stripped}
    if complete is None:
        raise ValueError('stream ended without terminal completion')
    return complete['answer'], complete['citations'], complete['kind'], complete['misplaced_fact_markers']


def _source_text(snap) -> str:
    cache = getattr(snap, 'content_cache', None)
    return getattr(cache, 'critical_excerpt', None) or getattr(cache, 'markdown_content', None) or ''


async def run(*, runs: int = 3, cases: list[CopilotGoldenCase] | None = None) -> dict[str, Any]:
    from app.services.copilot_service import _build_messages, openai_service
    from app.config import settings
    from evals.copilot_scorers import score_copilot_answer
    cases = _load_cases(GOLDEN_PATH) if cases is None else cases
    plan = _plan(cases, runs)
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'runs': runs,
              'golden_sha256': hashlib.sha256(GOLDEN_PATH.read_bytes()).hexdigest(),
              'source_sha': os.environ.get('GITHUB_SHA'), 'planned_attempts': plan,
              'requested_model': openai_service.model, 'actual_model': None,
              'actual_model_note': 'Per-call actual identities are in sanitized provider telemetry; not inferred from requested model.',
              'requested_flags': {'USE_STATEMENT_FINANCIALS': settings.USE_STATEMENT_FINANCIALS, 'COPILOT_MAX_TOKENS': settings.COPILOT_MAX_TOKENS},
              'results': []}
    lookup = {(c.accession_number, q.question_id): (c, q) for c in cases for q in c.qa}
    for identity in plan:
        case, qa = lookup[(identity['accession_number'], identity['question_id'])]
        row = {**identity, 'question': qa.question, 'terminal_complete': False}
        started = time.monotonic()
        try:
            snap = _snapshot_for_case(case)
            if snap is None:
                raise ValueError('prepared filing unavailable')
            source = _source_text(snap)
            if not source.strip():
                raise ValueError('prepared filing text unavailable')
            row['inputs'] = {'initial_messages': _build_messages(snap, source, qa.question, None),
                             'source_text': source, 'xbrl_data': snap.xbrl_data,
                             'period_of_report': str(snap.period_of_report),
                             'accession_number': snap.accession_number}
            row['tool_trace'] = {}
            answer, cites, kind, stripped = await _answer(snap, qa.question, trace=row['tool_trace'])
            row.update(answer=answer, citations=cites, kind=kind, terminal_complete=True,
                       stripped_misplaced_markers=stripped)
            row['score'] = score_copilot_answer(qa, answer=answer, citations=cites, kind=kind,
                filing_text=source, accession_number=case.accession_number,
                period_of_report=case.period_of_report, reporting_currency=case.reporting_currency).to_dict()
        except Exception as exc:
            row['error'] = {'type': type(exc).__name__, 'stage': 'answer_or_score'}
        row['elapsed_ms'] = round((time.monotonic() - started) * 1000, 2)
        report['results'].append(row)
    rows = report['results']
    scored = [r for r in rows if 'score' in r]
    report['summary'] = {'expected': len(plan), 'completed': len(rows), 'scored': len(scored),
        'errors': sum('error' in r for r in rows), 'passed': sum(r['score']['passed'] for r in scored),
        'pass_rate': sum(r['score']['passed'] for r in scored) / len(plan)}
    report['failures'] = validate_report(report, expected_plan=plan)
    report['accepted'] = not report['failures']
    return report


def _write_report(report: dict, output: Path = REPORTS_DIR) -> Path:
    """Keep full machine evidence and a readable status/count/row view, including preflight red."""
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'copilot-eval.json'
    path.write_text(json.dumps(report, indent=2, allow_nan=False, default=str) + '\n')
    summary = report.get('summary', {})
    def cell(value):
        return str(value).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('|','\\|').replace('\n',' ')
    lines = ['# Copilot filing fidelity', '', '**' + ('PASS' if report.get('accepted') else 'FAIL / incomplete') + '**', '',
        'Expected: ' + str(summary.get('expected', 'unavailable')) +
        '; completed: ' + str(summary.get('completed', 'unavailable')) +
        '; scored: ' + str(summary.get('scored', 'unavailable')) +
        '; execution errors: ' + str(summary.get('errors', 'unavailable')) + '.', '',
        'Requested model: ' + cell(report.get('requested_model', 'unavailable')) +
        '. Actual per-call model: see sanitized provider telemetry; not inferred here.', '',
        'Figure coverage is advisory. Missing cost measurement does not mean free. This is not the weekly strong-judge readout.', '',
        'Failures: ' + cell('; '.join(report.get('failures', [])) or 'none') + '.', '',
        '| Issuer | Accession | Question | Draw | Terminal | Verdict / error |',
        '| --- | --- | --- | --- | --- | --- |']
    for row in report.get('results', []):
        score = row.get('score', {})
        verdict = row.get('error') or ('PASS' if score.get('passed') else '; '.join(score.get('gate_failures', [])) or 'unscored')
        lines.append('| ' + ' | '.join(cell(v) for v in (
            row.get('ticker'),row.get('accession_number'),row.get('question_id'),row.get('run_index'),
            row.get('terminal_complete'),verdict)) + ' |')
    lines += ['', 'The accompanying JSON retains full answers, citations, initial messages, semantic tool results, source evidence and hashes.']
    (output / 'copilot-eval.md').write_text('\n'.join(lines) + '\n')
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=REPORTS_DIR)
    parser.add_argument('--runs', type=int, default=3)
    args = parser.parse_args()
    report = {'accepted': False, 'results': []}
    try:
        if not re.fullmatch(r'[0-9a-f]{40}', os.environ.get('GITHUB_SHA', '')):
            raise ValueError('authoritative CI source revision unavailable')
        cases = _load_cases(GOLDEN_PATH)
        _plan(cases, args.runs)
        prep = validate_preparation(args.preparation, cases)
        os.environ['DATABASE_URL'] = 'sqlite:///' + prep['database_path']
        from app.config import settings
        if not settings.OPENAI_API_KEY:
            raise ValueError('generator credential unavailable')
        telemetry = logging.getLogger('app.services.ai_metrics')
        telemetry.setLevel(logging.INFO)
        telemetry.addHandler(logging.StreamHandler())
        report = asyncio.run(run(runs=args.runs, cases=cases))
        report['preparation'] = prep
    except Exception as exc:
        report['failures'] = ['preflight failed: ' + (str(exc)[:200] if type(exc) is ValueError else type(exc).__name__)]
    path = _write_report(report, args.output)
    print(json.dumps({'accepted': report['accepted'], 'summary': report.get('summary'), 'report': str(path)}))
    return 0 if report['accepted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
