"""Self-test of ``tests/support/ast_move_proof.py``: a proof that cannot fail proves nothing.

The hot-module refactor (``tasks/refactor-plan-2026-10.md``) proves every "pure move" with this tool,
so each verdict it can return is pinned here on small synthetic modules: an honest move passes, and a
changed token, a dropped symbol, a duplicated definition, a changed class member, a changed arm of a
rebound name, a changed guard (one around imports alone included), a statement moved out of its guard and
an added import-time side effect (an assignment whose value calls; a call in a new class body, default,
decorator or lambda default; a class keyword such as ``metaclass=``; ``raise``, ``assert`` or ``del``; a
value that subscripts, unpacks, reads an attribute or applies an operator; an evaluated annotation; a block
whose body holds only imports or ``pass``, outside the ``if TYPE_CHECKING:`` exemption; a ``.setter`` on a
name that no inert property def above it in its class binds, or with code that runs in between; a class
attribute bound to a bare name, whose ``__set_name__`` runs; and an unpacking of anything but a display, which
iterates it) and a reordered symbol each fail; a disclosed delta passes with its diff shown.
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


def test_a_widened_handler_fails_when_its_body_only_imports():
    """``except Exception`` around an import alone also hides every error the imported module raises."""
    fallback = "try:\n    import plugin\nexcept ImportError:\n    pass\n"
    assert compare(fallback, {"app/x/a.py": fallback}).ok
    report = compare(fallback, {"app/x/a.py": fallback.replace("except ImportError:", "except Exception:")})
    assert report.missing == ["guard:try except ImportError"]
    assert report.side_effects == {"guard:try except Exception": "app/x/a.py"}


def test_a_statement_moved_out_of_its_guard_fails():
    old = "if FLAG:\n    A = 1\n    B = 2\n"
    report = compare(old, {"app/x/a.py": "if FLAG:\n    A = 1\nB = 2\n"})
    assert list(report.changed) == ["guard:if FLAG"]
    assert report.moved == 2  # A and B themselves are unchanged


def test_a_block_runs_at_import_whatever_its_body_holds():
    """A block's header runs at import even when its body holds only imports or ``pass``: ``if register()``
    calls, and ``while True`` never finishes importing. A class body runs at import too."""
    added = ("\nif register():\n    import plugin\n"
             "\nwhile True:\n    pass\n"
             "\nfor _ in hook():\n    import plugin\n"
             "\nwith patch_env():\n    import plugin\n"
             "\nclass Plugin:\n    if register():\n        import plugin\n")
    report = compare(OLD, _move(**{"app/x/helpers.py": HELPERS + added}))
    assert not report.ok
    assert set(report.side_effects) == {"guard:if register()", "guard:while True", "guard:for _ in hook()",
                                        "guard:with patch_env()", "Plugin.guard:if register()"}


def test_only_an_import_only_type_checking_block_is_not_a_symbol():
    """``if TYPE_CHECKING:`` with only imports and no ``else`` never runs its body, so it is exempt; an
    ``else`` or any other test makes it a block like any other."""
    old = "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from x import Y\n\nA = 1\n"
    report = compare(old, {"app/x/a.py": "A = 1\n"})
    assert report.ok, render(report)
    assert report.moved == 1
    added = ("\nif TYPE_CHECKING:\n    from x import Y\nelse:\n    import plugin\n"
             "\nif not TYPE_CHECKING:\n    import plugin\n"
             "\nif TYPE_CHECKING or register():\n    from x import Y\n")
    others = compare("A = 1\n", {"app/x/a.py": "A = 1\n" + added})
    assert set(others.side_effects) == {"guard:if TYPE_CHECKING", "guard:if not TYPE_CHECKING",
                                        "guard:if TYPE_CHECKING or register()"}


def test_a_new_assignment_that_calls_runs_at_import():
    files = _move(**{"app/x/helpers.py": HELPERS + "\nREGISTERED = register(clip)\nKEY = lambda row: row.get('k')\n"})
    report = compare(OLD, files)
    assert report.side_effects == {"REGISTERED": "app/x/helpers.py"}
    assert report.added == {"__all__": "app/x.py", "KEY": "app/x/helpers.py"}  # a lambda's call runs later



def test_definition_time_calls_in_new_classes_defs_and_lambdas_run_at_import():
    """A new class body, a def's defaults or decorator, and a lambda's defaults all run at import; a def's
    body, a lambda's body, a docstring and an inert decorator such as ``property`` do not."""
    added = (
        "\nclass Registry:\n    'Docstring.'\n    token = register()\n\n"
        "    @property\n    def size(self):\n        return len(self.token)\n"
        "\ndef helper(value=register()):\n    return value\n"
        "\n@atexit.register\ndef hook():\n    pass\n"
        "\nHANDLER = lambda value=register(): value\n"
        "\n@dataclass(frozen=True)\nclass Row:\n    key: str\n"
        "\ndef later():\n    return register()\n"
    )
    report = compare(OLD, _move(**{"app/x/helpers.py": HELPERS + added}))
    assert not report.ok
    assert report.side_effects == dict.fromkeys(("Registry.token", "helper", "hook", "HANDLER"), "app/x/helpers.py")
    assert {"Registry", "Registry.expr:'Docstring.'", "Registry.size", "Row", "Row.key", "later"} <= set(report.added)


def test_a_property_accessor_is_inert_only_on_a_property_bound_above_it_in_its_class():
    """``@size.setter`` calls ``size.setter`` at class creation, which copies the property when ``size`` is
    one of the class's own. ``@registry.setter`` calls whatever ``registry`` is, on a method or at module
    level, and ``@width.setter`` reads whatever ``width`` was rebound to between the property and it. A bare
    annotation (``size: int``) assigns nothing, so the property stands."""
    added = ("\nclass Box:\n"
             "    @property\n    def size(self):\n        return 1\n\n"
             "    def other(self):\n        return 2\n\n"
             "    size: int\n\n"
             "    @size.setter\n    def size(self, value):\n        pass\n\n"
             "    @size.deleter\n    def size(self):\n        pass\n\n"
             "    @registry.setter\n    def hook(self, value):\n        pass\n\n"
             "    @property\n    def width(self):\n        return 1\n\n"
             "    width = 0\n\n"
             "    @width.setter\n    def width(self, value):\n        pass\n"
             "\n@registry.setter\ndef handler(value):\n    pass\n")
    report = compare(OLD, _move(**{"app/x/helpers.py": HELPERS + added}))
    assert set(report.side_effects) == {"Box.hook", "Box.width", "handler"}
    assert {"Box", "Box.size", "Box.other"} <= set(report.added)  # an inert method or annotation between is fine


def test_a_property_accessor_needs_an_inert_getter_and_nothing_that_runs_code_in_between():
    """Old code that runs between a property and a new accessor can rebind the name (``locals()``,
    ``exec``, a frame), and ``property.setter`` reads the getter's ``__doc__`` again, which a getter
    wrapped by a decorator that is not inert can make run code."""
    rebound = ("class Rebound:\n    @property\n    def size(self):\n        return 1\n\n"
               "    locals().update(size=registry)\n")
    described = "\nclass Described:\n    @property\n    @describe\n    def size(self):\n        return 1\n"
    setter = "\n    @size.setter\n    def resize(self, value):\n        pass\n"
    report = compare(rebound + described, {"app/x/a.py": rebound + setter + described + setter})
    assert set(report.side_effects) == {"Rebound.resize", "Described.resize"}


def test_a_class_attribute_bound_to_a_name_runs_its_set_name_at_import():
    """Creating a class calls ``__set_name__`` on each attribute value whose type has one, so in a class body
    a bare name is not an inert value, paired through an unpacking included; a literal still is, and so is a
    bare name at module level."""
    added = ("\nclass Box:\n    LIMIT = 3\n    hook = registry\n    label: str = DEFAULT\n"
             "    left, right = registry, 1\n    low, high = 0, 9\n\nALIAS = registry\n")
    report = compare(OLD, _move(**{"app/x/helpers.py": HELPERS + added}))
    assert set(report.side_effects) == {"Box.hook", "Box.label", "Box.left,right"}
    assert {"Box", "Box.LIMIT", "Box.low,high", "ALIAS"} <= set(report.added)


def test_unpacking_anything_but_a_display_of_as_many_values_runs_at_import():
    """``LEFT, RIGHT = PAIR`` iterates ``PAIR``, whose ``__iter__`` runs at import. A display of as many
    values is paired with the names, nested displays included, and iterates nothing."""
    added = "\nLEFT, RIGHT = PAIR\n\n(FIRST, SECOND), THIRD = (1, 2), clip\n"
    report = compare(OLD, _move(**{"app/x/helpers.py": HELPERS + added}))
    assert set(report.side_effects) == {"LEFT,RIGHT"}
    assert "FIRST,SECOND,THIRD" in report.added


def test_only_inert_definitions_are_added_and_everything_else_runs_at_import():
    """Default deny: a new statement is ADDED only when it is a docstring or literal, or a def, class or
    plain-name assignment that makes no call at import. ``raise``, ``assert``, ``del`` and an augmented
    assignment run code without a call node, and a class keyword runs a metaclass or ``__init_subclass__``."""
    assert not compare("", {"app/x/a.py": "raise RuntimeError\n"}).ok
    added = ("\nassert READY\n\ndel REGISTRY['x']\n\nCOUNT += 1\n"
             "\nclass Plugin(metaclass=RegisteringMeta):\n    pass\n"
             "\nclass Configured(Base, flag=True):\n    pass\n"
             "\nclass Plain(Base):\n    'Docstring.'\n    LIMIT = 3\n")
    report = compare(OLD, _move(**{"app/x/helpers.py": HELPERS + added}))
    assert set(report.side_effects) == {"expr:assert READY", "expr:del REGISTRY['x']", "COUNT", "Plugin", "Configured"}
    # A base's own metaclass or __init_subclass__ is not visible in the AST: the stated limit.
    assert {"Plain", "Plain.LIMIT", "Plain.expr:'Docstring.'"} <= set(report.added)


def test_a_value_is_inert_only_when_it_is_a_literal_a_name_or_a_display_of_those():
    """A subscript, unpacking, operator or attribute read runs a user-defined method (``__getitem__``,
    ``__iter__``, ``__add__``, ``__getattr__``) with no call node."""
    added = ("\nTOKEN = REGISTRY['x']\nVALUES = [*REGISTRY]\nTOTAL = LEFT + RIGHT\nFLAG = settings.FLAG\n"
             "\nNAMES = ['a', 'b']\nALIAS = clip\nLIMITS: dict = {'a': 1, 'b': -2}\n"
             "\ndef shaped(value: int = None, *, key: str = 'k') -> tuple:\n"
             "    return value\n"
             "\ndef keyed(value=REGISTRY['x']):\n    return value\n")
    report = compare(OLD, _move(**{"app/x/helpers.py": HELPERS + added}))
    assert set(report.side_effects) == {"TOKEN", "VALUES", "TOTAL", "FLAG", "keyed"}
    assert {"NAMES", "ALIAS", "LIMITS", "shaped"} <= set(report.added)


def test_annotations_are_evaluated_unless_the_module_postpones_them():
    """Without ``from __future__ import annotations``, a subscripted, dotted or ``|`` annotation runs
    ``__class_getitem__``, a module's ``__getattr__`` or ``__or__`` at import; a class base always runs."""
    typed = ("def typed(value: Meta[int]) -> None:\n    return None\n"
             "\nLIMIT: typing.Final = 3\n\nWIDTH: int | None = None\n\nclass Pair(Generic[T]):\n    pass\n")
    evaluated = compare("", {"app/x/a.py": typed})
    assert set(evaluated.side_effects) == {"typed", "LIMIT", "WIDTH", "Pair"}
    postponed = compare("", {"app/x/a.py": "from __future__ import annotations\n\n" + typed})
    assert set(postponed.side_effects) == {"Pair"}  # bases are evaluated whatever the module postpones
    assert set(postponed.added) == {"typed", "LIMIT", "WIDTH"}


def test_the_old_symbols_in_each_new_file_keep_their_old_order():
    """Module-level code runs top to bottom: ``B = A`` above ``A = 1`` raises at import, with every symbol's
    text unchanged, and moving a rebinding changes a value silently. Order is checked per binding within
    each new file, so a split across files is free to regroup."""
    report = compare("A = 1\nB = A\n", {"app/x/a.py": "B = A\nA = 1\n"})
    assert not report.ok
    assert report.reordered == {"A": "app/x/a.py: now after B, which it preceded"}
    assert "REORDERED  A" in render(report)
    assert compare("A = 1\nB = A\n", {"app/x/a.py": "B = A\n", "app/x/b.py": "A = 1\n"}).ok
    members = compare("class C:\n    A = 1\n    B = A\n", {"app/x/a.py": "class C:\n    B = A\n    A = 1\n"})
    assert members.reordered == {"C.A": "app/x/a.py: now after C.B, which it preceded"}
    assert compare("A = 1\nB = A\n", {"app/x/a.py": "B = A\nA = 1\n"}, frozenset({"A"})).ok
    # Every binding of a rebound name keeps its place: B silently becomes 2, with every text unchanged.
    rebound = compare("A = 1\nB = A\nA = 2\n", {"app/x/a.py": "A = 1\nA = 2\nB = A\n"})
    assert rebound.reordered == {"B": "app/x/a.py: now after A, which it preceded"}
    assert compare("A = 1\nB = A\nA = 2\n", {"app/x/a.py": "A = 1\nB = A\nA = 2\n"}).ok

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
