"""The T4 proof rejects changes concealed by helper/state/delegation scaffolding."""
import pytest

from tests.support.trend_phase_move_proof import STATE, compare

OLD = '''
from __future__ import annotations

def build_dataset(value):
    first = value + 1
    if value:
        second = first * 2
    else:
        second = first
    result = []
    result.append(second)
    return result
'''
NEW = '''
from __future__ import annotations

def build_dataset(value):
    first = _first(value)
    second = _second(value, first)
    result = []
    _append(result, second)
    return result

def _first(value):
    first = value + 1
    return first

def _second(value, first):
    if value:
        second = first * 2
    else:
        second = first
    return second

def _append(result, second):
    result.append(second)
'''
IMPORTS = '''
from __future__ import annotations
'''
SIGNATURE = '''async def stream_trend_narrative(
    *, company_id: int, mode: str, start_period: str, end_period: str,
    force: bool = False, user_id: Optional[int] = None,
):
    from app.database import SessionLocal
    from app.services.openai_service import STREAM_ERROR_SENTINEL, openai_service
    from app.services.prompt_loader import get_named_prompt
'''
ASSEMBLY = '''    db = SessionLocal()
    try:
        if company_id == 0:
            yield {"type": "error"}
            return
        ticker = "TEST"
    finally:
        db.close()
'''
PUBLICATION = '''    narrative = ticker
    yield {"type": "token", "text": narrative}
    yield {"type": "complete"}
'''
NARRATIVE_OLD = IMPORTS + SIGNATURE + '    yield {"type": "progress"}\n' + ASSEMBLY + PUBLICATION
NARRATIVE_NEW = (IMPORTS + 'from contextlib import closing\n'
                 + STATE + '\n' + SIGNATURE + '''    run = _NarrativeRun(company_id, mode, start_period, end_period, force, user_id)
    yield {"type": "progress"}
    with closing(_assemble(run, SessionLocal)) as events:
        for event in events:
            yield event
    if not run.assembled:
        return
    with closing(_publish(run)) as events:
        for event in events:
            yield event


def _assemble(run, SessionLocal):
''' + ASSEMBLY.replace('company_id', 'run.company_id').replace('ticker', 'run.ticker')
                 + '    run.assembled = True\n\ndef _publish(run):\n'
                 + PUBLICATION.replace('ticker', 'run.ticker'))


def test_same_name_helpers_reassemble_exactly():
    assert compare(OLD, NEW, 'dataset') == ''


def test_narrative_state_and_closing_bridges_reassemble_exactly():
    assert compare(NARRATIVE_OLD, NARRATIVE_NEW, 'narrative') == ''


@pytest.mark.parametrize(('before', 'after'), [
    ('value + 1', 'value + 2'),
    ('_first(value)', '_first(value + 1)'),
    ('_second(value, first)', '_second(first, value)'),
    ('return first', 'return value'),
    ('def _first(value):', 'def _first(value=register()):'),
    ('def _first(value):', '@register\ndef _first(value):'),
    ('def _append(result, second):', 'def _append(result):'),
    ('_append(result, second)', '_append(result)'),
    ('result.append(second)', 'result.append(second)\n    register()'),
    ('first = _first(value)\n    second = _second(value, first)',
     'second = _second(value, first)\n    first = _first(value)'),
])
def test_helper_proof_rejects_behavior_and_binding_changes(before, after):
    candidate = NEW.replace(before, after, 1)
    assert candidate != NEW
    try:
        diff = compare(OLD, candidate, 'dataset')
    except AssertionError:
        return
    assert diff, 'changed helper incorrectly accepted'


@pytest.mark.parametrize(('before', 'after'), [
    ('closing(_assemble(run, SessionLocal))', '_assemble(run, SessionLocal)'),
    ('yield event', 'yield {"type": "complete"}'),
    ('self.assembled = False', 'self.assembled = True'),
    ('run.assembled = True', 'run.assembled = False'),
    ('if not run.assembled:', 'if run.assembled:'),
    ('_NarrativeRun(company_id, mode,', '_NarrativeRun(company_id + 1, mode,'),
    ('db.close()', 'db.rollback()'),
    ('ticker = "TEST"', 'ticker = "CHANGED"'),
    ('run.ticker = "TEST"', 'run.ticker = "TEST"\n        extra = [run.key for run.key in (1, 2)]'),
    ('    if not run.assembled:\n        return\n', ''),
])
def test_narrative_proof_rejects_cleanup_state_and_event_changes(before, after):
    candidate = NARRATIVE_NEW.replace(before, after, 1)
    assert candidate != NARRATIVE_NEW
    try:
        diff = compare(NARRATIVE_OLD, candidate, 'narrative')
    except AssertionError:
        return
    assert diff, 'changed narrative incorrectly accepted'


def test_helper_return_must_not_be_mistaken_for_a_parent_return():
    old = """def build_dataset(value):
    first = value + 1
    if value:
        return first
    return []
"""
    new = """def build_dataset(value):
    _maybe_return(value)
    return []
def _maybe_return(value):
    first = value + 1
    if value:
        return first
"""
    with pytest.raises(AssertionError, match="control flow"):
        compare(old, new, 'dataset')
