"""The phase proof must reject behavioral and ordering changes hidden by an allowed method diff."""
import pytest

from tests.support.summary_finalize_move_proof import compare

OLD = '''
class OpenAIService:
    async def summarize_filing(self, value):
        first = value + 1
        second = first * 2
        return second
'''
NEW = '''
class OpenAIService:
    async def summarize_filing(self, value):
        run = summary_finalize.SummaryRun(value=value)
        summary_finalize.first_phase(run)
        summary_finalize.second_phase(run)
        return run.second
'''
PHASES = '''
from dataclasses import dataclass, field
@dataclass
class SummaryRun:
    value: int
    first: int = field(init=False, repr=False)
    second: int = field(init=False, repr=False)
def first_phase(run):
    run.first = run.value + 1
def second_phase(run):
    run.second = run.first * 2
'''


def test_phase_reassembly_preserves_the_method():
    assert compare(OLD, NEW, PHASES) == ""


@pytest.mark.parametrize("mutation", ["body", "order", "await", "constructor", "default"])
def test_phase_reassembly_rejects_changes(mutation):
    facade, phases = NEW, PHASES
    if mutation == "body":
        phases = phases.replace("* 2", "* 3")
    elif mutation == "order":
        facade = facade.replace("first_phase(run)", "PLACEHOLDER(run)").replace(
            "second_phase(run)", "first_phase(run)").replace("PLACEHOLDER(run)", "second_phase(run)")
    elif mutation == "await":
        facade = facade.replace("summary_finalize.first_phase(run)", "await summary_finalize.first_phase(run)")
    elif mutation == "constructor":
        facade = facade.replace("value=value", "value=value + 1")
    else:
        phases = phases.replace("field(init=False, repr=False)", "field(default_factory=register)", 1)
    try:
        diff = compare(OLD, facade, phases)
    except AssertionError:
        return
    assert diff, f"{mutation} incorrectly passed as a pure move"
