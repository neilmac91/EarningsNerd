"""Self-test of ``tests/support/ast_move_proof.py``: a proof that cannot fail proves nothing.

The hot-module refactor (``tasks/refactor-plan-2026-10.md``) proves every "pure move" with this tool,
so each verdict it can return is pinned here on small synthetic modules: an honest move passes, and a
changed token, a dropped symbol, a duplicated definition, a changed class member, a changed arm of a
rebound name, a changed guard, a statement moved out of its guard and an added import-time side effect
(including an assignment whose value calls) each fail; a disclosed delta passes with its diff shown.
"""
from tests.support.ast_move_proof import compare, render

OLD = '''"""Old module docstring."""
import logging

logger = logging.getLogger(__name__)
LIMIT = 8_000


def clip(text: str) -> str:
    # a comment that the move may reflow
    return text[:LIMIT]


class Service:
    """Service docstring."""

    retries = 3

    def run(self, value: int) -> int:
        return value + self.retries
'''

FACADE = '''"""New façade docstring: rewritten by the move, which is allowed."""
from .helpers import LIMIT, clip
from .service import Service

__all__ = ["LIMIT", "Service", "clip"]
'''

HELPERS = '''import logging

LIMIT = 8_000

def clip(text: str) -> str:
    return text[:LIMIT]   # the same code, reformatted
'''

SERVICE = '''class Service:
    """Service docstring."""

    retries = 3

    def run(self, value: int) -> int:
        return value + self.retries
'''


def _move(**overrides: str) -> dict[str, str]:
    files = {"app/x.py": FACADE + "\nimport logging\n\nlogger = logging.getLogger(__name__)\n",
             "app/x/helpers.py": HELPERS, "app/x/service.py": SERVICE}
    files.update(overrides)
    return files


def test_an_honest_move_passes_and_ignores_formatting_comments_and_imports():
    report = compare(OLD, _move())
    assert report.ok, render(report)
    # logger, LIMIT, clip, Service (its header), and its docstring, retries and run members
    assert report.moved == 7
    assert report.added == {"__all__": "app/x.py"}


def test_one_changed_token_fails_as_changed():
    report = compare(OLD, _move(**{"app/x/helpers.py": HELPERS.replace("text[:LIMIT]", "text[:LIMIT - 1]")}))
    assert not report.ok
    assert list(report.changed) == ["clip"]
    assert "text[:LIMIT - 1]" in report.changed["clip"]


def test_a_dropped_symbol_fails_as_missing():
    report = compare(OLD, _move(**{"app/x/helpers.py": "LIMIT = 8_000\n"}))
    assert not report.ok
    assert report.missing == ["clip"]


def test_a_symbol_defined_twice_fails_until_disclosed():
    files = _move(**{"app/x/service.py": SERVICE + "\nimport logging\nlogger = logging.getLogger(__name__)\n"})
    report = compare(OLD, files)
    assert not report.ok
    assert report.duplicate == {"logger": ["app/x.py", "app/x/service.py"]}
    assert compare(OLD, files, frozenset({"logger"})).ok


def test_a_changed_class_member_is_named_by_its_qualified_key():
    report = compare(OLD, _move(**{"app/x/service.py": SERVICE.replace("retries = 3", "retries = 4")}))
    assert list(report.changed) == ["Service.retries"]


FALLBACK = '''try:
    from json_repair import repair_json
    _HAS_JSON_REPAIR = True
except ImportError:
    _HAS_JSON_REPAIR = False
'''


def test_every_definition_of_a_rebound_name_is_compared():
    """The copilot_service.py:57-62 shape: flipping the try arm alone must not pass as a pure move."""
    assert compare(FALLBACK, {"app/x/repair.py": FALLBACK}).ok
    flipped = FALLBACK.replace("_HAS_JSON_REPAIR = True", "_HAS_JSON_REPAIR = False")
    report = compare(FALLBACK, {"app/x/repair.py": flipped})
    assert set(report.changed) == {"_HAS_JSON_REPAIR", "guard:try except ImportError"}
    assert "+_HAS_JSON_REPAIR = False" in report.changed["_HAS_JSON_REPAIR"]


def test_a_changed_guard_fails_even_when_its_body_is_identical():
    """Widening ``except ImportError`` to ``except Exception`` keeps every assignment byte-identical."""
    widened = FALLBACK.replace("except ImportError:", "except Exception:")
    report = compare(FALLBACK, {"app/x/repair.py": widened})
    assert not report.ok
    assert report.missing == ["guard:try except ImportError"]
    assert report.side_effects == {"guard:try except Exception": "app/x/repair.py"}
    negated = "if FLAG:\n    A = 1\n"
    assert compare(negated, {"app/x/a.py": negated}).ok
    assert compare(negated, {"app/x/a.py": negated.replace("if FLAG:", "if not FLAG:")}).missing == ["guard:if FLAG"]


def test_a_statement_moved_out_of_its_guard_fails():
    old = "if FLAG:\n    A = 1\n    B = 2\n"
    report = compare(old, {"app/x/a.py": "if FLAG:\n    A = 1\nB = 2\n"})
    assert list(report.changed) == ["guard:if FLAG"]
    assert report.moved == 2  # A and B themselves are unchanged


def test_an_import_only_block_is_not_a_symbol():
    old = "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from x import Y\n\nA = 1\n"
    report = compare(old, {"app/x/a.py": "A = 1\n"})
    assert report.ok, render(report)
    assert report.moved == 1


def test_a_new_assignment_that_calls_runs_at_import():
    files = _move(**{"app/x/helpers.py": HELPERS + "\nREGISTERED = register(clip)\nKEY = lambda row: row.get('k')\n"})
    report = compare(OLD, files)
    assert report.side_effects == {"REGISTERED": "app/x/helpers.py"}
    assert report.added == {"__all__": "app/x.py", "KEY": "app/x/helpers.py"}  # a lambda's call runs later


def test_an_added_import_time_side_effect_fails_until_disclosed():
    files = _move(**{"app/x/helpers.py": HELPERS + "\nsettings.STRICT = False\nregister(clip)\n"})
    report = compare(OLD, files)
    assert not report.ok
    assert report.side_effects == {"effect:settings.STRICT": "app/x/helpers.py",
                                   "expr:register(clip)": "app/x/helpers.py"}
    disclosed = compare(OLD, files, frozenset({"effect:settings.STRICT", "expr:register(clip)"}))
    assert disclosed.ok
    assert disclosed.allowed == {"effect:settings.STRICT": "added in app/x/helpers.py",
                                 "expr:register(clip)": "added in app/x/helpers.py"}


def test_an_allowed_change_still_prints_its_diff():
    report = compare(OLD, _move(**{"app/x/helpers.py": HELPERS.replace("LIMIT = 8_000", "LIMIT = 9_000")}),
                     frozenset({"LIMIT"}))
    assert report.ok
    rendered = render(report)
    assert "ALLOWED    LIMIT (disclosed delta)" in rendered
    assert "-LIMIT = 8000" in rendered and "+LIMIT = 9000" in rendered
