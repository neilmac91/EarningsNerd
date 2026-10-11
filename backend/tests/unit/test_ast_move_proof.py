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
iterates it), a new symbol that binds a name the moved code of its file reads or binds (at module level, or
in the class body for a new class member), a dunder that Python reads itself where moved code lives (a
module's ``__all__`` aside) or any new member of a moved class, a symbol of the target file that moved code
reads at import above it (directly, through code it reaches there, or through Python's own read of a dunder)
or rebinds (a class body's ``global`` read as one scope), a class docstring that no longer opens its body, a
reordered symbol, and a moved symbol that reads what its new module changes (its name, package, file or
docstring, a relative import's target, its namespace, whether its annotations are postponed, or a module
dunder it binds) each fail; a disclosed delta passes with its diff shown, and an input the CLI cannot read
stops it with a message.
"""
import tomllib
from pathlib import Path

import pytest

from tests.support import ast_move_proof
from tests.support.ast_move_proof import Report, compare, render

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
    files = {"app/x/__init__.py": FACADE + "\nimport logging\n\nlogger = logging.getLogger(__name__)\n",
             "app/x/helpers.py": HELPERS, "app/x/service.py": SERVICE}
    files.update(overrides)
    return files


def _facade(new: dict[str, str], allow: frozenset[str] = frozenset()) -> Report:
    """``compare`` for OLD, the package ``app/x/__init__.py`` split into the sub-modules beside it (the layout
    Python imports: ``from .helpers import`` there names ``app.x.helpers``). Its ``logger`` stays in the façade,
    so the logger keeps its name, and a moved symbol that read where its module lives would be RELOCATED."""
    return compare(OLD, new, allow, old_path="app/x/__init__.py")


def test_an_honest_move_passes_and_ignores_formatting_comments_and_imports():
    report = _facade(_move())
    assert report.ok, render(report)
    # logger, LIMIT, clip, Service (its header), and its docstring, retries and run members
    assert report.moved == 7
    assert report.added == {"__all__": "app/x/__init__.py"}


def test_one_changed_token_fails_as_changed():
    report = _facade(_move(**{"app/x/helpers.py": HELPERS.replace("text[:LIMIT]", "text[:LIMIT - 1]")}))
    assert not report.ok
    assert list(report.changed) == ["clip"]
    assert "text[:LIMIT - 1]" in report.changed["clip"]


def test_a_dropped_symbol_fails_as_missing():
    report = _facade(_move(**{"app/x/helpers.py": "LIMIT = 8_000\n"}))
    assert not report.ok
    assert report.missing == ["clip"]


def test_a_symbol_defined_twice_fails_until_disclosed():
    files = _move(**{"app/x/service.py": SERVICE + "\nimport logging\nlogger = logging.getLogger(__name__)\n"})
    report = _facade(files)
    assert not report.ok
    assert report.duplicate == {"logger": ["app/x/__init__.py", "app/x/service.py"]}
    assert _facade(files, frozenset({"logger"})).ok


def test_a_changed_class_member_is_named_by_its_qualified_key():
    report = _facade(_move(**{"app/x/service.py": SERVICE.replace("retries = 3", "retries = 4")}))
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
    report = _facade(_move(**{"app/x/helpers.py": HELPERS + added}))
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
    report = _facade(files)
    assert report.side_effects == {"REGISTERED": "app/x/helpers.py"}
    assert report.added == {"__all__": "app/x/__init__.py", "KEY": "app/x/helpers.py"}  # a lambda's call runs later



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
    report = _facade(_move(**{"app/x/helpers.py": HELPERS + added}))
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
    report = _facade(_move(**{"app/x/helpers.py": HELPERS + added}))
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
    report = _facade(_move(**{"app/x/helpers.py": HELPERS + added}))
    assert set(report.side_effects) == {"Box.hook", "Box.label", "Box.left,right"}
    assert {"Box", "Box.LIMIT", "Box.low,high", "ALIAS"} <= set(report.added)


def test_unpacking_anything_but_a_display_of_as_many_values_runs_at_import():
    """``LEFT, RIGHT = PAIR`` iterates ``PAIR``, whose ``__iter__`` runs at import. A display of as many
    values is paired with the names, nested displays included, and iterates nothing."""
    added = "\nLEFT, RIGHT = PAIR\n\n(FIRST, SECOND), THIRD = (1, 2), clip\n"
    report = _facade(_move(**{"app/x/helpers.py": HELPERS + added}))
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
    report = _facade(_move(**{"app/x/helpers.py": HELPERS + added}))
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
    report = _facade(_move(**{"app/x/helpers.py": HELPERS + added}))
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

def test_a_new_symbol_that_binds_a_name_the_moved_code_reads_shadows_it():
    """``make = registry`` is inert, yet the old ``X = make()`` beside it now calls ``registry()``: the old
    file had no ``make`` symbol, so the moved code took the name from an import or a builtin. A def's body
    resolves the module's names when it is called, so it counts as much as a line that runs at import."""
    old = "from helpers import make\n\nX = make()\n\n\ndef build():\n    return make()\n"
    new = old.replace("\nX = ", "\nmake = registry\n\nX = ")
    report = compare(old, {"app/x.py": new})
    assert not report.ok
    assert report.shadows == {"make": "app/x.py: binds make, read by X, build"}
    assert report.added == {}
    assert "SHADOWS    make (app/x.py: binds make, read by X, build)" in render(report)
    disclosed = compare(old, {"app/x.py": new}, frozenset({"make"}))
    assert disclosed.ok
    assert disclosed.allowed == {"make": "added in app/x.py\nshadows app/x.py: binds make, read by X, build"}
    # A new symbol that rebinds a name an old symbol BINDS changes it for every importer, read here or not.
    twice = "def make():\n    return 1\n"
    rebound = compare(twice, {"app/x.py": twice + "\nmake, spare = registry, 0\n"})
    assert rebound.shadows == {"make,spare": "app/x.py: binds make, bound by make"}


def test_a_new_class_member_shadows_a_name_its_class_body_reads():
    """A class body looks a name up in the class first: a new ``Box.make`` above the old ``x = make()`` makes
    creating the class run ``register()``. A method's body never sees the class namespace, so ``Box.run``
    is no reader of it; a new module-level ``make`` reaches both, and the class header's base as well."""
    old = "class Box(Base):\n    x = make()\n\n    def run(self):\n        return make()\n"
    member = old.replace("    x = ", "    def make():\n        return register()\n\n    x = ")
    report = compare(old, {"app/x.py": member})
    assert not report.ok
    assert report.shadows == {"Box.make": "app/x.py: binds make, read by attribute lookups on Box, Box.x"}
    module = compare(old, {"app/x.py": "make = Base = registry\n\n" + old})
    assert module.shadows == {"make,Base": "app/x.py: binds Base, read by Box; binds make, read by Box.run, Box.x"}


def test_an_honest_split_adds_names_without_shadowing_any():
    """The control. A new name shadows only what the OLD symbols of its own file take from its own
    namespace: a parameter, a local or a comprehension variable is not the module's name, an attribute is
    not a name, and another file has its own namespace. New code may read new names, and a disclosed change
    that starts calling a new helper never read it before."""
    box = "class Box:\n    def run(self):\n        return self.make() + rows\n"
    scoped = ("def local(make):\n    return make()\n\n\n"
              "def bound():\n    make = rows[0]\n    return [make for make in rows]\n\n\n")
    reader = "X = make()\n"
    added = ("\nmake = registry\n"
             "\ndef _trim(value):\n    return value.strip()\n"
             "\ndef _clean(value):\n    return _trim(value)\n")
    report = compare("from helpers import make, rows\n\n\n" + scoped + box + reader,
                     {"app/x/a.py": "from helpers import rows\n\n\n" + scoped + box + added,
                      "app/x/b.py": "from helpers import make\n\n" + reader})
    assert report.ok, render(report)
    assert report.added == dict.fromkeys(("make", "_trim", "_clean"), "app/x/a.py")
    helpers = HELPERS.replace("return text[:LIMIT]", "return _trim(text)[:LIMIT]") + "\ndef _trim(value):\n    return value\n"
    calling = _facade(_move(**{"app/x/helpers.py": helpers}), frozenset({"clip"}))
    assert calling.ok, render(calling)  # clip's printed diff is the disclosure
    assert calling.added == {"__all__": "app/x/__init__.py", "_trim": "app/x/helpers.py"}


def _added_at_module_level(old: str) -> str:
    """What the proof says of ``make = registry`` added above ``old``: its SHADOWS reason, or "" when ADDED."""
    report = compare(old, {"app/x.py": "make = registry\n\n" + old})
    assert report.ok == (report.added == {"make": "app/x.py"}), render(report)
    return report.shadows.get("make", "").removeprefix("app/x.py: binds make, ")


def _added_to_box(old: str, *names: str) -> str:
    """What the proof says of a new first member of ``class Box`` that binds ``names``: its SHADOWS reason,
    without the attribute lookups that read every new member of a moved class (pinned on their own in
    ``test_a_new_member_of_a_moved_class_is_read_through_its_attributes``), "" when nothing else reads it."""
    assert old.startswith("class Box:\n")
    member = " = ".join(names) + " = 0"
    report = compare(old, {"app/x.py": old.replace("class Box:\n", f"class Box:\n    {member}\n", 1)})
    reasons = []
    for reason in filter(None, report.shadows.get("Box." + ",".join(names), "").removeprefix("app/x.py: ").split("; ")):
        binds, _, uses = reason.partition(", ")
        uses = uses.replace("read by attribute lookups on Box, ", "read by ").replace("read by attribute lookups on Box", "")
        uses = uses.removeprefix(" and ")
        if uses:
            reasons.append(f"{binds}, {uses}")
    return "; ".join(reasons)


def test_every_place_the_moved_code_takes_a_module_name_from_is_a_reader():
    """One case per scoping rule that makes a name the module's: a load in a class body falls through to the
    module even when the class binds the name (inside a def too), ``global`` sends a def's name there, an
    augmented assignment reads before it binds, a parenthesised annotation binds nothing, and a block reads
    through its header and binds its header's targets and its imports."""
    assert _added_at_module_level("def build():\n    class K:\n        x = make\n        make = 0\n    return K\n") == "read by build"
    assert _added_at_module_level("def init():\n    global make\n    make = build()\n") == "read by init"
    assert _added_at_module_level("class Box:\n    make += 1\n") == "read by Box.make"
    assert _added_at_module_level("def build():\n    (make): int\n    return make()\n") == "read by build"
    assert _added_at_module_level("if make():\n    pass\n") == "read by guard:if make()"
    assert _added_at_module_level("for make in ROWS:\n    pass\n") == "bound by guard:for make in ROWS"
    fallback = "try:\n    from fast import make\nexcept ImportError:\n    pass\n"
    assert _added_at_module_level(fallback) == "bound by guard:try except ImportError"
    # A NEW block is a SIDE EFFECT; it is not reported again for the old names bound in it.
    widened = compare(FALLBACK, {"app/x.py": FALLBACK.replace("except ImportError:", "except Exception:")})
    assert set(widened.side_effects) == {"guard:try except Exception"} and widened.shadows == {}


def test_a_name_bound_in_a_nearer_scope_is_not_the_modules():
    """One case per scoping rule that keeps a name out of the module: a parameter, a def's local, an
    enclosing def's local, a comprehension's target, ``:=`` inside a comprehension (it binds in the def
    around it), a lambda's parameter, and the names an import, an ``except ... as`` and a ``match`` bind."""
    for old in ("def local(make):\n    return make()\n",
                "def build():\n    make = 1\n    return make\n",
                "def outer():\n    make = 1\n\n    def inner():\n        return make\n    return inner\n",
                "ROWS = [make for make in rows]\n",
                "def find(rows):\n    found = [(make := row) for row in rows]\n    return make, found\n",
                "KEY = lambda make: make\n",
                "def load():\n    import make\n    return make\n",
                "def load():\n    try:\n        return 1\n    except OSError as make:\n        return make\n",
                "def load(value):\n    match value:\n        case [make, *rest]:\n            return make, rest\n"):
        assert _added_at_module_level(old) == "", old


def test_a_class_member_is_read_only_by_what_runs_in_the_class_body():
    """A def's decorator, default and annotations, a nested class's bases, a block's header and a
    comprehension's first iterable run in the class body and see a new member; the comprehension's own
    element and a nested class's body do not. A class body that declares a name ``global`` binds the
    module's name, so a new member of that name is reported too."""
    method = "class Box:\n    @deco\n    def run(self, limit=LIMIT) -> Out:\n        return limit\n"
    assert _added_to_box(method, "deco", "LIMIT", "Out") == (
        "binds LIMIT, read by Box.run; binds Out, read by Box.run; binds deco, read by Box.run")
    assert _added_to_box("class Box:\n    class Inner(Base):\n        pass\n", "Base") == "binds Base, read by Box.Inner"
    assert _added_to_box("class Box:\n    if make:\n        x = 1\n", "make") == "binds make, read by Box.guard:if make"
    assert _added_to_box("class Box:\n    xs = [r for r in rows]\n", "rows") == "binds rows, read by Box.xs"
    assert _added_to_box("class Box:\n    xs = [make(r) for r in ()]\n", "make") == ""
    assert _added_to_box("class Box:\n    class Inner:\n        y = make\n", "make") == ""
    assert _added_to_box("class Box:\n    global make\n    x = 1\n", "make") == "binds make, read by Box.expr:global make"


def test_a_symbol_of_the_target_file_is_no_shadow_when_the_old_file_imported_it_from_there():
    """``run`` moves into the module it imported ``normalize`` from: it keeps the binding it always had. The
    same move when the old file took ``normalize`` from anywhere else is the shadow a move into an existing
    module risks, and so is any import the proof cannot place: an alias, or no path for the old file."""
    old = "from app.b import normalize\n\n\ndef run(value):\n    return normalize(value)\n"
    files = {"app/a.py": "from app.b import run\n\n__all__ = ['run']\n",
             "app/b.py": "def normalize(value):\n    return value.strip()\n\n\ndef run(value):\n    return normalize(value)\n"}
    for source in (old, old.replace("from app.b import", "from .b import")):
        report = compare(source, files, old_path="app/a.py")
        assert report.ok, render(report)
        assert report.added == {"__all__": "app/a.py", "normalize": "app/b.py"}
    shadowed = {"normalize": "app/b.py: binds normalize, read by run"}
    for unplaced in (old.replace("app.b", "app.c"),  # another module
                     old.replace("import normalize", "import clean as normalize"),  # an alias
                     old + "\ntry:\n    from fast import normalize\nexcept ImportError:\n    pass\n",  # rebound in a block
                     "if FAST:\n    " + old):  # imported only when FAST
        assert compare(unplaced, files, old_path="app/a.py").shadows == shadowed, unplaced
    assert compare(old, files).shadows == shadowed  # no path for the old file



def test_a_symbol_of_the_target_file_shadows_moved_code_that_reads_it_at_import_above_it():
    """The old file's import ran before ``X = normalize``; in the target file the binding must still run
    first. Placed above it, a read at import raises NameError, or takes an earlier binding of the name, so it
    is reported: in a statement, a class body, a decorator or a comprehension, which runs where it stands. A
    def's or lambda's body reads the name when it runs, so its place does not matter."""
    target = "def normalize(value):\n    return value.strip()\n"

    def placed(reader: str, above: bool, head: str = "") -> dict[str, str]:
        body = reader + "\n\n" + target if above else target + "\n\n" + reader
        return {"app/a.py": "", "app/b.py": head + body}

    for reader, key in (("X = normalize\n", "X"),
                        ("XS = [normalize(row) for row in ROWS]\n", "XS"),
                        ("class Box:\n    clean = normalize\n", "Box.clean"),
                        ("@normalize\ndef run(value):\n    return value\n", "run")):
        old = "from app.b import normalize\n\n" + reader
        report = compare(old, placed(reader, above=True), old_path="app/a.py")
        assert report.shadows == {"normalize": f"app/b.py: binds normalize, read above it at import by {key}"}, reader
        assert compare(old, placed(reader, above=False), old_path="app/a.py").ok, reader
    for reader in ("def run(value):\n    return normalize(value)\n", "RUN = lambda value: normalize(value)\n"):
        old = "from app.b import normalize\n\n" + reader
        report = compare(old, placed(reader, above=True), old_path="app/a.py")
        assert report.ok, render(report)
    # An earlier binding of the name above the reader is not the one the old file imported.
    early = compare("from app.b import normalize\n\nX = normalize\n",
                    placed("X = normalize\n", above=True, head="normalize = None\n\n"), old_path="app/a.py")
    assert early.shadows == {"normalize": "app/b.py: binds normalize, read above it at import by X"}


def test_moved_code_that_rebinds_a_name_imported_from_the_target_file_shadows_it():
    """The exemption covers reads only. Before the move ``reset`` rebound the old file's own copy of
    ``cache``; in the target file it rebinds the target's binding, for every importer. A module-level loop
    or ``except ... as`` target rebinds it as well, and so does a ``global`` declared in a method or a class
    body. A class body is one namespace for the compiler, though the proof reads its members one by one: the
    member that stores or deletes the name rebinds the module's, wherever in the body the declaration stands."""
    target = "cache = {}\n"
    for reader, key in (("def reset():\n    global cache\n    cache = {}\n", "reset"),
                        ("for cache in ROWS:\n    pass\n", "guard:for cache in ROWS"),
                        ("class Box:\n    def reset(self):\n        global cache\n        cache = {}\n", "Box.reset"),
                        ("class Box:\n    global cache\n    cache = {}\n", "Box.cache"),
                        ("class Box:\n    if FLAG:\n        global cache\n    cache = {}\n", "Box.cache"),
                        ("class Box:\n    global cache\n    del cache\n", "Box.expr:del cache"),
                        ("class Box:\n    global cache\n    for cache in ({'k': 2},):\n        pass\n",
                         "Box.guard:for cache in ({'k': 2},)")):
        old = "from app.b import cache\n\n" + reader
        report = compare(old, {"app/a.py": "", "app/b.py": target + "\n\n" + reader}, old_path="app/a.py")
        assert report.shadows == {"cache": f"app/b.py: binds cache, bound by {key}"}, reader
    # A read below the binding stays exempt, a ``global`` that is only read included: it binds nothing.
    for reads in ("def size():\n    return len(cache)\n", "def size():\n    global cache\n    return len(cache)\n",
                  "class Box:\n    global cache\n    size = len(cache)\n"):
        report = compare("from app.b import cache\n\n" + reads, {"app/a.py": "", "app/b.py": target + "\n\n" + reads},
                         old_path="app/a.py")
        assert report.ok, render(report)


def test_code_that_runs_at_import_above_the_target_binding_and_reaches_a_body_that_reads_it_reads_it_there():
    """A def's or lambda's body reads the name when it runs, so its place alone does not matter. Code that runs
    at import above the target's binding and reaches such a body runs it before the binding exists, where the
    old file's import had run first: a call, a reference (what is done with it is not followed), through any
    chain of defs or a class's methods, a lambda handed to a call (``sorted(key=...)``, ``map``, one called where
    it stands, in a default or a class body), a member its class body calls, a decorator that is handed the def
    (an ``async def`` too), a class whose bases or keywords may call its methods when it is created, a
    method's decorator in the class body, and what a member class's body creates when it runs: a nested class on
    a base that may call it, a nested def under a calling decorator, and what it calls: a def or class it binds
    itself. An augmented assignment reads its target before it binds it. An annotation that is no lone name or
    literal runs code where Python evaluates it (a call, a subscript's ``__class_getitem__``), and a def whose
    annotation names a reaching class holds it: what reads its ``__annotations__`` may call it. Below the binding
    each is settled, and so is a reaching def or class that nothing above the binding names or calls: a lambda
    that no call is handed, one that an inert decorator or a property's own accessor wraps (in a nested class
    too), a class whose only base is a builtin class (one no binding its lookup sees replaces: a def's local, a
    comprehension's target or another class's body does not), and a lone name an annotation evaluates, which
    Python stores and never calls (a postponed annotation is not even evaluated), a ``global`` declaration,
    which reads nothing, and a class's own property's accessor, in a nested class body as in the moved code."""
    target = "def normalize(value):\n    return value.strip()\n"
    report_init = "class Report:\n    def __init__(self):\n        normalize(' x ')\n\n\n"
    report_class = "class Report:\n    def render(self):\n        return normalize(' x ')\n\n\n"
    error = "class FooError(Exception):\n    def __str__(self):\n        return normalize(' boom ')\n"
    nested = "def hook():\n    return normalize(' x ')\n\n\nclass Outer:\n    class Inner:\n"
    box = "class Box:\n    @classmethod\n    def hook(cls):\n        return normalize(' x ')\n"
    calling = "def dataclass(cls):\n    cls.hook()\n    return cls\n\n\n"
    for reader, key in (
            ("def describe():\n    return normalize(' x ')\n\n\nDESCRIPTION = describe()\n", "DESCRIPTION"),
            ("RUN = lambda: normalize(' x ')\nDESCRIPTION = RUN()\n", "DESCRIPTION"),
            ("def inner():\n    return normalize(' x ')\n\n\ndef outer():\n    return inner()\n\n\nDESCRIPTION = outer()\n",
             "DESCRIPTION"),
            ("def describe():\n    return normalize(' x ')\n\n\nHANDLERS = [describe]\n", "HANDLERS"),
            ("def describe():\n    return normalize(' x ')\n\n\nALIAS = describe\nDESCRIPTION = ALIAS()\n", "ALIAS, DESCRIPTION"),
            ("def describe():\n    return normalize(' x ')\n\n\ndef setup():\n    global HOOK\n    HOOK = describe\n\n\n"
             "setup()\nVALUE = HOOK()\n", "VALUE, expr:setup()"),
            ("class Box:\n    def clean(self):\n        return normalize(' x ')\n\n\nCLEAN = Box().clean()\n", "CLEAN"),
            ("@register\ndef hook():\n    return normalize(' x ')\n", "hook"),
            ("class Box(Base):\n    def clean(self):\n        return normalize(' x ')\n", "Box"),
            ("class Box:\n    @register\n    def clean(self):\n        return normalize(' x ')\n", "Box.clean"),
            ("@register\nasync def hook():\n    return normalize(' x ')\n", "hook"),
            ("class Meta(type):\n    def __init__(cls, *args):\n        super().__init__(*args)\n        cls.label = cls.clean()\n"
             "\n\nclass Box(metaclass=Meta):\n    @classmethod\n    def clean(cls):\n        return normalize(' x ')\n", "Box"),
            ("ROWS = [' b ', ' a ']\nVALUE = sorted(ROWS, key=lambda row: normalize(row))\n", "VALUE"),
            ("VALUE = (lambda: normalize(' x '))()\n", "VALUE"),
            ("ROWS = [' a ']\nVALUE = list(map(lambda row: normalize(row), ROWS))\n", "VALUE"),
            ("def run(value=(lambda: normalize(' x '))()):\n    return value\n", "run"),
            ("class Box:\n    ORDER = sorted([' b ', ' a '], key=lambda row: normalize(row))\n", "Box.ORDER"),
            ("class Box:\n    def clean(value):\n        return normalize(value)\n\n    CLEANED = clean(' x ')\n", "Box.CLEANED"),
            ("class Box:\n    @staticmethod\n    def clean(value):\n        return normalize(value)\n\n"
             "    CLEANED = clean(' x ')\n", "Box.CLEANED"),
            ("class Box:\n    def _wrap(fn):\n        normalize(' x ')\n        return fn\n\n    @_wrap\n    def clean(self):\n"
             "        return 1\n", "Box.clean"),
            ("def build(value) -> normalize:\n    return value\n", "build"),
            ("Exception = Base\n\n\n" + error, "FooError"),
            ("def setup():\n    global Exception\n    Exception = Base\n\n\n" + error, "FooError"),
            ("FOUND = [(Exception := Base) for _ in (1,)]\n\n\n" + error, "FooError"),
            ("class Box:\n    Exception = Base\n\n    class FooError(Exception):\n        def __str__(self):\n"
             "            return normalize(' boom ')\n", "Box.FooError"),
            ("class Base:\n    def __init_subclass__(cls, **kwargs):\n        super().__init_subclass__(**kwargs)\n"
             "        cls.hook()\n\n\nclass Outer:\n    class Inner:\n        class Deep(Base):\n            @classmethod\n"
             "            def hook(cls):\n                return normalize(' x ')\n", "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        @register\n        def hook():\n            return normalize(' x ')\n",
             "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        if True:\n            @register\n            def hook():\n"
             "                return normalize(' x ')\n", "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        def hook():\n            return normalize(' x ')\n\n"
             "        VALUE = hook()\n", "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        class Deep:\n            def __init__(self):\n"
             "                normalize(' x ')\n\n        VALUE = Deep()\n", "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        class Deeper:\n            def hook():\n"
             "                return normalize(' x ')\n\n            VALUE = hook()\n", "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        class Deep(metaclass=Base):\n            def clean(self):\n"
             "                return normalize(' x ')\n", "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        Exception = Base\n\n        class Deep(Exception):\n"
             "            def __str__(self):\n                return normalize(' boom ')\n", "Outer.Inner"),
            (nested + "        value: hook()\n", "Outer.Inner"),
            (calling + "@dataclass\n" + box, "Box"),
            ("from app.c import dataclass\n\n\n@dataclass\n" + box, "Box"),
            ("import types\n\n\n" + calling.replace("dataclass", "calling")
             + "dataclasses = types.SimpleNamespace(dataclass=calling)\n\n\n@dataclasses.dataclass\n" + box, "Box"),
            ("class Outer:\n    def dataclass(cls):\n        cls.hook()\n        return cls\n\n    @dataclass\n"
             "    class Inner:\n        @classmethod\n        def hook(cls):\n            return normalize(' x ')\n",
             "Outer.Inner"),
            ("def property(fn):\n    fn(None)\n    return fn\n\n\nclass Box:\n    @property\n    def value(self):\n"
             "        return normalize(' x ')\n", "Box.value"),
            ("class Outer:\n    class Inner:\n        hook = lambda: normalize(' x ')\n        VALUE = hook()\n",
             "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        hook: object = lambda: normalize(' x ')\n"
             "        VALUE = hook()\n", "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        for hook in (lambda: normalize(' x '),):\n            pass\n\n"
             "        VALUE = hook()\n", "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        FIRST = (hook := lambda: normalize(' x '))\n"
             "        VALUE = hook()\n", "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        RULES = {'name': lambda value: normalize(value)}\n"
             "        VALUE = RULES['name'](' x ')\n", "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        def run(value, clean=lambda value: normalize(value)):\n"
             "            return clean(value)\n\n        VALUE = run(' x ')\n", "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        class Report:\n            def __init__(self):\n"
             "                normalize(' x ')\n\n        def build(value: Report):\n            return value\n\n"
             "        CHECK = build.__annotations__['value']()\n", "Outer.Inner"),
            ("class Outer:\n    class Inner:\n        value: normalize\n", "Outer.Inner"),
            (report_init + "def build(value: Report()):\n    return value\n", "build"),
            (report_init + "def build() -> Report():\n    return 1\n", "build"),
            ("class Report:\n    def __class_getitem__(cls, item):\n        return normalize(' x ')\n\n\n"
             "def build(value: Report[int]):\n    return value\n", "build"),
            (report_init + "VALUE: Report() = 1\n", "VALUE"),
            ("from typing import Optional\n\n\n" + report_init
             + "def build(value: Optional[Report]):\n    return value\n", "build"),
            (report_init + "def build(value: Report):\n    return value\n\n\n"
             "CHECK = build.__annotations__['value']()\n", "CHECK"),
            ("def route(fn):\n    for hint in fn.__annotations__.values():\n        hint()\n    return fn\n\n\n"
             + report_init + "@route\ndef build(value: Report):\n    return value\n", "build"),
            (report_class + "def build(value: Report):\n    return value\n\n\nHANDLERS = [build]\n", "HANDLERS")):
        old = "from app.b import normalize\n\n\n" + reader
        above = compare(old, {"app/a.py": "", "app/b.py": reader + "\n\n" + target}, old_path="app/a.py")
        assert above.shadows == {"normalize": f"app/b.py: binds normalize, read above it at import by {key}"}, reader
        assert compare(old, {"app/a.py": "", "app/b.py": target + "\n\n" + reader}, old_path="app/a.py").ok, reader
    for reader in ("def describe():\n    return normalize(' x ')\n\n\nVALUE = other()\n",
                   "class Box(Base):\n    LIMIT = 3\n",
                   "class Box:\n    @property\n    def clean(self):\n        return normalize(' x ')\n",
                   "VALUE = [lambda row: normalize(row)]\n",
                   "class Box:\n    @property\n    def value(self):\n        return self._v\n\n    @value.setter\n"
                   "    def value(self, raw):\n        self._v = normalize(raw)\n",
                   error,
                   "def helper():\n    Exception = object\n    return Exception\n\n\n" + error,
                   "PICK = lambda Exception: Exception\nNAMES = [Exception for Exception in ()]\n\n\n" + error,
                   "class Other:\n    Exception = object\n\n\n" + error,
                   "class Outer:\n    class Inner:\n        def other():\n            return 1\n\n        def hook():\n"
                   "            return normalize(' x ')\n\n        VALUE = other()\n",
                   "class Outer:\n    class Inner:\n        class Deep(Exception):\n            def __str__(self):\n"
                   "                return normalize(' boom ')\n",
                   "class Outer:\n    class Inner:\n        @staticmethod\n        def hook():\n"
                   "            return normalize(' x ')\n\n        @property\n        def value(self):\n"
                   "            return self._v\n\n        @value.setter\n        def value(self, raw):\n"
                   "            self._v = normalize(raw)\n",
                   nested + "        value: hook\n",
                   nested + "        global hook\n",
                   "from dataclasses import dataclass\n\n\n@dataclass\n" + box,
                   "import dataclasses\n\n\n@dataclasses.dataclass\n" + box,
                   "from dataclasses import dataclass as dataclass\n\n\n@dataclass\n" + box,
                   "class Outer:\n    class Inner:\n        hook = lambda: normalize(' x ')\n        VALUE = 1\n",
                   "class Outer:\n    class Inner:\n        hook = lambda: 1\n"
                   "        other = lambda: normalize(' x ')\n        VALUE = hook()\n",
                   "def hook():\n    return 1\n\n\nclass Outer:\n    class Inner:\n        def make():\n"
                   "            class Made:\n                hook = lambda: normalize(' x ')\n\n"
                   "            return Made\n\n        VALUE = hook()\n",
                   "def hook():\n    return 1\n\n\nclass Outer:\n    class Inner:\n        def make():\n"
                   "            def hook():\n                return normalize(' x ')\n\n            return hook\n\n"
                   "        VALUE = hook()\n",
                   "class Outer:\n    class Inner:\n        @property\n        def normalize(self):\n"
                   "            return 1\n\n        @normalize.setter\n        def normalize(self, raw):\n"
                   "            pass\n",
                   report_class + "def build(text: str) -> Report:\n    return Report()\n",
                   report_class + "def build(report: Report):\n    return report\n",
                   report_class + "@dataclass\nclass Batch:\n    first: Report\n",
                   "class Box:\n    global normalize\n\n    def clean(self):\n        return normalize(' x ')\n"):
        old = "from app.b import normalize\n\n\n" + reader
        report = compare(old, {"app/a.py": "", "app/b.py": reader + "\n\n" + target}, old_path="app/a.py")
        assert report.ok, render(report)
    # A ``match`` case creates its defs and classes where the match runs, at import: in a member class's body,
    # at module level, or in a module-level class's body. An undecorated def there is settled.
    hooking = ("class Base:\n    def __init_subclass__(cls, **kwargs):\n        super().__init_subclass__(**kwargs)\n"
               "        cls.hook()\n\n\n")
    for reader in ("class Outer:\n    class Inner:\n        match 1:\n            case _:\n                @register\n"
                   "                def hook():\n                    return normalize(' x ')\n",
                   "match 1:\n    case _:\n        @register\n        def hook():\n            return normalize(' x ')\n",
                   "class Box:\n    match 1:\n        case _:\n            @register\n            def hook():\n"
                   "                return normalize(' x ')\n",
                   hooking + "match 1:\n    case _:\n        class Deep(Base):\n            @classmethod\n"
                   "            def hook(cls):\n                return normalize(' x ')\n",
                   "match 1:\n    case _:\n        class Box:\n            def hook():\n                return normalize(' x ')\n\n"
                   "            VALUE = hook()\n",
                   "match 1:\n    case _:\n        class Box:\n            clean = lambda value: normalize(value)\n"
                   "            VALUE = clean(' x ')\n"):
        old = "from app.b import normalize\n\n\n" + reader
        above = compare(old, {"app/a.py": "", "app/b.py": reader + "\n\n" + target}, old_path="app/a.py")
        assert above.shadows.get("normalize", "").startswith(
            "app/b.py: binds normalize, read above it at import by "), reader
        assert compare(old, {"app/a.py": "", "app/b.py": target + "\n\n" + reader}, old_path="app/a.py").ok, reader
    reader = "match 1:\n    case _:\n        def hook():\n            return normalize(' x ')\n"
    old = "from app.b import normalize\n\n\n" + reader
    assert compare(old, {"app/a.py": "", "app/b.py": reader + "\n\n" + target}, old_path="app/a.py").ok
    # A postponed annotation is not evaluated: neither one that names the binding nor one that reaches it, nor
    # one that would call or subscript a reaching class.
    future = "from __future__ import annotations\n"
    for reader in ("def build(value) -> normalize:\n    return value\n",
                   report_class + "def build(text: str) -> Report:\n    return Report()\n",
                   report_init + "def build(value: Report()):\n    return value\n",
                   report_init + "VALUE: Report() = 1\n",
                   "class Report:\n    def __class_getitem__(cls, item):\n        return normalize(' x ')\n\n\n"
                   "def build(value: Report[int]):\n    return value\n",
                   nested + "        value: hook()\n",
                   "class Outer:\n    class Inner:\n        value: normalize\n"):
        old = future + "from app.b import normalize\n\n\n" + reader
        report = compare(old, {"app/a.py": "", "app/b.py": future + reader + "\n\n" + target}, old_path="app/a.py")
        assert report.ok, render(report)
    # No NameError when the name is also a builtin: above the binding the call takes the builtin, silently.
    negate = "def format(value):\n    return -value\n"
    reader = "ROWS = [3, 1]\nVALUE = sorted(ROWS, key=lambda row: format(row))\n"
    report = compare("from app.b import format\n\n\n" + reader, {"app/a.py": "", "app/b.py": reader + "\n\n" + negate},
                     old_path="app/a.py")
    assert report.shadows == {"format": "app/b.py: binds format, read above it at import by VALUE"}
    # An augmented assignment reads its target before it binds it, and a class body's lookup falls through to the
    # module until the class has bound the name.
    count = "COUNT = 0\n"
    for reader, key in (("class Box:\n    COUNT += 1\n", "Box.COUNT"),
                        ("class Outer:\n    class Inner:\n        COUNT += 1\n", "Outer.Inner")):
        old = "from app.b import COUNT\n\n\n" + reader
        above = compare(old, {"app/a.py": "", "app/b.py": reader + "\n\n" + count}, old_path="app/a.py")
        assert above.shadows == {"COUNT": f"app/b.py: binds COUNT, read above it at import by {key}"}, reader
        assert compare(old, {"app/a.py": "", "app/b.py": count + "\n\n" + reader}, old_path="app/a.py").ok, reader
    # The settlement rests on the target's binding being the one the old file imported, the target's last. An
    # import, a star import or a new symbol's ``global`` binds the name where no symbol's place shows it, so
    # moved code below the def may read it before that binding: it is not settled. A def in a new block is a
    # symbol of its own, whose place shows.
    fast = "def normalize(value):\n    return value.strip()\n\n\n"
    reader = "X = normalize(' a ')\n"
    old = "from app.b import normalize\n\n\n" + reader
    for rebinding in ("try:\n    from fastnorm import normalize\nexcept ImportError:\n    pass\n",
                      "from fastnorm import normalize\n",
                      "from fastnorm import *\n",
                      "def install():\n    global normalize\n    normalize = str.upper\n\n\ninstall()\n"):
        report = compare(old, {"app/a.py": "", "app/b.py": fast + reader + "\n\n" + rebinding}, old_path="app/a.py")
        assert report.shadows == {"normalize": "app/b.py: binds normalize, read by X"}, rebinding
    blocked = compare(old, {"app/a.py": "", "app/b.py": fast + reader + "\n\nif FAST:\n    def normalize(value):\n"
                                                         "        return value\n"}, old_path="app/a.py")
    assert blocked.shadows == {"normalize": "app/b.py: binds normalize, read above it at import by X"}
    settled = compare(old, {"app/a.py": "", "app/b.py": fast + reader + "\n\nfrom fastnorm import other\n"},
                      old_path="app/a.py")
    assert settled.ok, render(settled)
    # A file's import of a name from itself (moved code that kept its own import) binds the name to itself, or
    # raises ImportError at import: it settles as the def does. Under another name it binds another value.
    for itself in ("from app.b import normalize\n", "from .b import normalize\n"):
        report = compare(old, {"app/a.py": "", "app/b.py": fast + itself + reader}, old_path="app/a.py")
        assert report.ok, render(report)
    aliased = compare(old, {"app/a.py": "", "app/b.py": fast + reader + "\n\nfrom app.b import X as normalize\n"},
                      old_path="app/a.py")
    assert aliased.shadows == {"normalize": "app/b.py: binds normalize, read by X"}


def test_python_reads_a_dunder_the_old_file_imported_from_the_target_where_moved_code_stands():
    """A dunder the old file imported from the target file is settled for moved code below the target's
    binding only. Python reads a module's ``__name__`` (as a class's or def's ``__module__``) and its
    ``__builtins__`` (a def's builtins) itself, where it creates moved code, with no load of either in the code,
    so moved code above the binding gets the target's value there: ``'app.b'``, or the real builtins. Every
    dunder counts, as everywhere else, but a module's ``__all__``; a read of it above the binding is listed
    after Python's own."""
    for name, binding, moved in (("__name__", "__name__ = 'custom'\n", "class Moved:\n    pass\n"),
                                 ("__builtins__", "__builtins__ = {'len': max}\n", "def size(rows):\n    return len(rows)\n")):
        old = f"from app.b import {name}\n\n\n{moved}"
        report = compare(old, {"app/a.py": "", "app/b.py": f"{moved}\n\n{binding}"}, old_path="app/a.py")
        assert report.shadows == {name: f"app/b.py: binds {name}, read above it at import by Python itself"}, name
        assert compare(old, {"app/a.py": "", "app/b.py": f"{binding}\n\n{moved}"}, old_path="app/a.py").ok, name
    named = compare("from app.b import __version__\n\nVERSION = __version__\n",
                    {"app/a.py": "", "app/b.py": "VERSION = __version__\n__version__ = '1.0'\n"}, old_path="app/a.py")
    assert named.shadows == {
        "__version__": "app/b.py: binds __version__, read above it at import by Python itself, VERSION"}
    listed = compare("from app.b import __all__\n\n\ndef names():\n    return 1\n",
                     {"app/a.py": "", "app/b.py": "def names():\n    return 1\n\n\n__all__ = ['names']\n"},
                     old_path="app/a.py")
    assert listed.ok, render(listed)


def test_the_target_file_settlement_weighs_old_module_level_code_by_what_it_did_before_and_after_the_move():
    """The settlement rests on the old file's own module-level imports, so it holds for a module-level binding
    only: a new member of a moved class binds in the class namespace, which no import placed. It weighs OLD
    symbols only, each by what it did both before the move and after it: a disclosed change that starts or
    stops reading or rebinding the name above the binding is CHANGED, its diff the disclosure, and a new symbol
    that reads it there is ADDED (NameError at import fails loudly)."""
    target = "def normalize(value):\n    return value.strip()\n"
    old = "from app.b import normalize\n\n\nclass Box:\n    clean = normalize\n"
    member = compare(old, {"app/a.py": "", "app/b.py": target + "\n\nclass Box:\n    normalize = None\n    clean = normalize\n"},
                     old_path="app/a.py")
    assert member.shadows == {"Box.normalize": "app/b.py: binds normalize, read by attribute lookups on Box, Box.clean"}
    for before, after in (("X = 1\n", "X = normalize\n"), ("X = normalize\n", "X = 1\n")):
        report = compare("from app.b import normalize\n\n" + before, {"app/a.py": "", "app/b.py": after + "\n\n" + target},
                         old_path="app/a.py")
        assert list(report.changed) == ["X"] and report.shadows == {}, before
    hook = "def hook():\n    return normalize(' x ')\n"
    report = compare("from app.b import normalize\n\n" + hook, {"app/a.py": "", "app/b.py": "@register\n" + hook + "\n\n" + target},
                     old_path="app/a.py")
    assert list(report.changed) == ["hook"] and report.shadows == {}  # a decorator added by a disclosed change
    reset = "def reset():\n    global normalize\n    normalize = None\n"
    for before, after in (("def reset():\n    pass\n", reset), (reset, "def reset():\n    pass\n")):
        report = compare("from app.b import normalize\n\n" + before, {"app/a.py": "", "app/b.py": target + "\n\n" + after},
                         old_path="app/a.py")
        assert list(report.changed) == ["reset"] and report.shadows == {}, before
    added = compare("from app.b import normalize\n\nX = 1\n",
                    {"app/a.py": "", "app/b.py": "ALIAS = normalize\nX = 1\n\n\n" + target}, old_path="app/a.py")
    assert added.added == dict.fromkeys(("ALIAS", "normalize"), "app/b.py") and added.shadows == {}


def test_a_relative_import_beyond_the_top_level_package_places_no_name():
    """``from ..app import normalize`` in ``app/a.py`` climbs past the top-level package, so the old file cannot
    import at all and the name has no origin to settle; ``from . import`` there names the package ``app``."""
    old = "from ..app import normalize\n\n\ndef run(value):\n    return normalize(value)\n"
    files = {"app/a.py": "", "app/__init__.py": "def normalize(value):\n    return value\n\n\ndef run(value):\n    return normalize(value)\n"}
    assert compare(old, files, old_path="app/a.py").shadows == {"normalize": "app/__init__.py: binds normalize, read by run"}
    assert compare(old.replace("from ..app import", "from . import"), files, old_path="app/a.py").ok

def test_a_new_module_dunder_beside_moved_code_is_read_by_python_itself():
    """No moved code loads ``__builtins__``, yet ``size`` below it resolves ``len`` through it. It runs
    nothing at import, and it printed ``pure move: OK`` before the rule."""
    size = "def size(rows):\n    return len(rows)\n"
    builtins = {"app/x.py": "__builtins__ = {'len': 0}\n\n" + size}
    report = compare(size, builtins)
    assert not report.ok
    assert report.shadows == {"__builtins__": "app/x.py: binds __builtins__, read by Python itself"}
    assert report.added == {}
    assert "SHADOWS    __builtins__ (app/x.py: binds __builtins__, read by Python itself)" in render(report)
    disclosed = compare(size, builtins, frozenset({"__builtins__"}))
    assert disclosed.ok
    assert disclosed.allowed == {
        "__builtins__": "added in app/x.py\nshadows app/x.py: binds __builtins__, read by Python itself"}
    # A NEW class whose body declares ``global __getattr__`` binds the module's beside the moved ``size``.
    helper = "class Helper:\n    global __getattr__\n\n    def __getattr__(name):\n        return 'lazy'\n"
    installed = compare(size, {"app/x.py": size + "\n\n" + helper})
    assert installed.shadows == {"Helper.__getattr__": "app/x.py: binds __getattr__, read by Python itself"}


def test_a_new_dunder_member_of_a_moved_class_is_read_by_python_itself():
    """No moved code loads ``__slots__``, yet creating the class reads it: the moved class's instances lose
    their ``__dict__``. It runs nothing at import, and it printed ``pure move: OK`` before the rule."""
    moved = "class Moved:\n    x = 1\n"
    slots = compare(moved, {"app/x.py": moved.replace("    x = 1", "    __slots__ = ()\n    x = 1")})
    assert not slots.ok
    assert slots.shadows == {"Moved.__slots__": "app/x.py: binds __slots__, read by Python itself"}


def test_a_new_member_of_a_moved_class_is_read_through_its_attributes():
    """A pure move never adds a member to a moved class, and the proof cannot follow an attribute read, so every
    new member of an OLD class is SHADOWS, read by attribute lookups on the class: one that overrides what the
    class inherited (``Moved().close()``), a non-dunder hook a library reads (an Enum's ``_missing_``), a new
    field of a dataclass (its ``__init__`` takes one more argument), and a constant. A method body never reads
    the class namespace, so ``Box.run`` is not named. A dunder keeps Python's own read as its reason; a new
    class's members stay ADDED, and a name the class body declares ``global`` binds the module's, not a member."""
    for old, member, cls, name in (
            ("class Moved(Base):\n    x = 1\n", "    def close(self):\n        return 'new'\n", "Moved", "close"),
            ("class Form(Enum):\n    A = 'a'\n", "    @classmethod\n    def _missing_(cls, value):\n        return cls.A\n",
             "Form", "_missing_"),
            ("@dataclass\nclass Row:\n    key: str\n", "    extra: int = 0\n", "Row", "extra"),
            ("class Box:\n    def run(self):\n        return self.make() + rows\n", "    rows = ()\n", "Box", "rows")):
        report = compare(old, {"app/x.py": old + member})
        assert report.shadows == {f"{cls}.{name}": f"app/x.py: binds {name}, read by attribute lookups on {cls}"}, name
        assert report.added == {} and not report.ok, name
        allowed = compare(old, {"app/x.py": old + member}, frozenset({f"{cls}.{name}"}))
        assert allowed.ok and allowed.allowed[f"{cls}.{name}"].endswith(f"read by attribute lookups on {cls}"), name
    dunder = compare("class Moved:\n    x = 1\n", {"app/x.py": "class Moved:\n    x = 1\n    __slots__ = ()\n"})
    assert dunder.shadows == {"Moved.__slots__": "app/x.py: binds __slots__, read by Python itself"}
    new_class = compare("A = 1\n", {"app/x.py": "A = 1\n\n\nclass Helper:\n    LIMIT = 3\n"})
    assert new_class.ok and new_class.added == dict.fromkeys(("Helper", "Helper.LIMIT"), "app/x.py")
    module = compare("X = make\n\n\nclass Box:\n    global make\n",
                     {"app/x.py": "X = make\n\n\nclass Box:\n    global make\n    make = registry\n"})
    assert module.shadows == {"Box.make": "app/x.py: binds make, read by Box.expr:global make, X"}
    # Only the class body's own ``global`` makes a name the module's: a method that declares its own name
    # ``global`` still binds the method in the class, which attribute lookups read.
    own = "    def close(self):\n        global close\n        close = None\n        return 'new'\n"
    report = compare("class Moved(Base):\n    x = 1\n", {"app/x.py": "class Moved(Base):\n    x = 1\n" + own})
    assert report.shadows == {"Moved.close": "app/x.py: binds close, read by attribute lookups on Moved"}


def test_a_class_body_global_that_is_only_read_installs_no_module_dunder():
    """``global __doc__`` in a class body makes the body read the module's docstring and binds nothing, so the
    class moved elsewhere installs no module dunder there; a member that stores the name binds the module's."""
    doc = '"""Doc."""\n\n\nclass Box:\n    global __doc__\n    text = __doc__\n'
    assert _relocated(doc, "app/y.py", "app/x.py") == {}
    stored = doc.replace("    text = __doc__\n", "    __doc__ = 'Box.'\n")
    assert _relocated(stored, "app/y.py", "app/x.py") == {"Box.__doc__": "binds __doc__, which Python reads from app.y, was app.x"}


def test_a_class_docstring_counts_only_as_the_first_statement_of_its_body():
    """Python takes a class's ``__doc__`` from the first statement of its body only, and FastAPI and pydantic
    read it: a new member placed above an old class's docstring takes it out of ``__doc__``, with every
    member's text unchanged. The header carries the docstring, so whatever now precedes it (a new member, an
    import, an old member, a block around it) changes the header, in a class that holds nothing else too, and
    so does a docstring added to a class that had none. A first statement that is no string is no docstring."""
    old = 'class Moved:\n    """Doc."""\n    x = 1\n'
    report = compare(old, {"app/x.py": old.replace('    """Doc."""', '    y = 0\n    """Doc."""')})
    assert not report.ok
    assert list(report.changed) == ["Moved"]
    assert '-    """Doc."""\n+    pass' in report.changed["Moved"]
    assert report.moved == 2 and report.added == {}  # the docstring and x, unchanged; the new y is SHADOWS
    assert report.shadows == {"Moved.y": "app/x.py: binds y, read by attribute lookups on Moved"}
    for above in ("    import os\n", "    x = 1\n"):
        displaced = old.replace("    x = 1\n", "").replace('    """Doc."""', above + '    """Doc."""')
        assert "Moved" in compare(old, {"app/x.py": displaced}).changed, above
    assert "Moved" in compare(old, {"app/x.py": old.replace('    """Doc."""', '    if FLAG:\n        """Doc."""')}).changed
    only = 'class NotFound(Exception):\n    """Raised."""\n'
    assert list(compare(only, {"app/x.py": only.replace("    ", "    status = 404\n    ", 1)}).changed) == ["NotFound"]
    ellipsis = "class Proto:\n    ...\n    x = 1\n"
    displaced = compare(ellipsis, {"app/x.py": ellipsis.replace("    ...", "    y = 0\n    ...")})
    assert displaced.changed == {} and set(displaced.shadows) == {"Proto.y"}
    bare = "class Moved:\n    x = 1\n"
    documented = compare(bare, {"app/x.py": old})
    assert list(documented.changed) == ["Moved"]
    assert documented.added == {"Moved.expr:'Doc.'": "app/x.py"}


def test_a_facades_all_and_a_new_classs_own_dunders_and_docstring_are_added():
    """The control. A façade declares ``__all__`` beside the old ``logger`` it keeps, and a split adds a class
    of its own, with a docstring and dunders, beside moved code: no moved code reaches them except through
    the class's name, so every one is ADDED."""
    cache = ('\nclass _Cache:\n    """Docstring."""\n\n    __slots__ = ("rows",)\n\n'
             "    def __init__(self):\n        self.rows = {}\n\n"
             "    def __eq__(self, other):\n        return self is other\n")
    report = _facade(_move(**{"app/x/helpers.py": HELPERS + cache}))
    assert report.ok, render(report)
    members = ("_Cache", "_Cache.expr:'Docstring.'", "_Cache.__slots__", "_Cache.__init__", "_Cache.__eq__")
    assert report.added == {"__all__": "app/x/__init__.py", **dict.fromkeys(members, "app/x/helpers.py")}


def test_every_dunder_counts_where_moved_code_lives_and_only_there():
    """One case per rule. Every dunder counts, a def or one that a library reads, at module level and in an
    old class, ``__all__`` and ``__doc__`` included in a class, and in a class or a file whose only old
    symbol is its header or a block; a dunder the moved code also names lists both readers. A module's
    ``__all__`` is exempt from Python's read only, a file with no old symbol holds no moved code, and a
    class-private ``__name``, a name with underscores on one side only and the throwaway ``__`` are no
    dunders."""
    size = "def size(rows):\n    return len(rows)\n"
    for new, key in (("def __getattr__(name):\n    return name\n", "__getattr__"),
                     ("__package__ = 'app'\n", "__package__")):
        assert compare(size, {"app/x.py": size + new}).shadows == {
            key: f"app/x.py: binds {key}, read by Python itself"}, new
    fallback = "try:\n    import fast\nexcept ImportError:\n    pass\n"
    assert compare(fallback, {"app/x.py": fallback + "\n__package__ = 'app'\n"}).shadows == {
        "__package__": "app/x.py: binds __package__, read by Python itself"}
    moved = "class Moved:\n    x = 1\n"
    for new, name in (("def __init__(self):\n        pass", "__init__"), ("__tablename__ = 'rows'", "__tablename__"),
                      ("def __init_subclass__(cls):\n        pass", "__init_subclass__"), ("__all__ = ()", "__all__"),
                      ("def __eq__(self, other):\n        return True", "__eq__"), ("__doc__ = 'Other.'", "__doc__")):
        report = compare(moved, {"app/x.py": moved + f"\n    {new}\n"})
        assert report.shadows == {f"Moved.{name}": f"app/x.py: binds {name}, read by Python itself"}, new
    empty = "class NotFound(Exception):\n    pass\n"
    assert compare(empty, {"app/x.py": empty + "\n    def __str__(self):\n        return 'x'\n"}).shadows == {
        "NotFound.__str__": "app/x.py: binds __str__, read by Python itself"}
    readers = "A = __name__\nB = __name__\nC = __name__\nD = __name__\n"
    named = compare(readers, {"app/x.py": "__name__ = 'app'\n" + readers})
    assert named.shadows == {"__name__": "app/x.py: binds __name__, read by Python itself, A, B, C and 1 more"}
    assert compare(size, {"app/x.py": "__all__ = ['size']\n\n" + size}).added == {"__all__": "app/x.py"}
    listed = "def names():\n    return __all__\n"
    assert compare(listed, {"app/x.py": "__all__ = []\n\n" + listed}).shadows == {
        "__all__": "app/x.py: binds __all__, read by names"}
    lazy = compare(size, {"app/x/__init__.py": size, "app/x/lazy.py": "def __getattr__(name):\n    return name\n"})
    assert lazy.ok and lazy.added == {"__getattr__": "app/x/lazy.py"}
    plain = compare(size, {"app/x.py": size + "\n__cache = {}\ncache__ = {}\n_cache__ = {}\n__cache_ = {}\n__ = 0\n"})
    assert plain.ok and set(plain.added) == {"__cache", "cache__", "_cache__", "__cache_", "__"}


INDEX = ('import logging\nfrom pathlib import Path\n\nlogger = logging.getLogger(__name__)\n'
         'DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "index.json"\n\n\n'
         'def load_helper():\n    from . import helpers\n    return helpers.KIND\n')
INDEX_FACADE = ("from app.services.index.loader import DATA_PATH, load_helper, logger\n\n"
                "__all__ = ['DATA_PATH', 'load_helper', 'logger']\n")


def test_moved_code_that_reads_where_its_module_lives_is_relocated():
    """``index_service.py`` moved whole into ``index/loader.py`` behind a façade keeps every text, yet
    ``DATA_PATH`` now points one directory deeper, ``logger`` is renamed and ``load_helper`` imports another
    module. Each printed ``pure move: OK`` before the rule; on its own path the module stays OK."""
    files = {"app/services/index_service.py": INDEX_FACADE, "app/services/index/loader.py": INDEX}
    report = compare(INDEX, files, old_path="app/services/index_service.py")
    assert not report.ok
    where = "app/services/index/loader.py, was app/services/index_service.py"
    assert report.relocated == {
        "DATA_PATH": f"{where}: reads __file__ (another file)",
        "load_helper": f"{where}: imports helpers from . (app.services.index, was app.services)",
        "logger": f"{where}: reads __name__ (app.services.index.loader, was app.services.index_service)"}
    assert report.moved == 3 and report.added == {"__all__": "app/services/index_service.py"}
    rendered = render(report)
    assert f"RELOCATED  logger ({where}): reads __name__ (app.services.index.loader, " in rendered
    assert ", 0 reordered, 3 relocated, 1 added, " in rendered
    disclosed = compare(INDEX, files, frozenset({"DATA_PATH", "load_helper", "logger"}),
                        old_path="app/services/index_service.py")
    assert disclosed.ok
    assert disclosed.allowed["logger"] == (
        "unchanged\nrelocated: reads __name__ (app.services.index.loader, was app.services.index_service)")
    assert compare(INDEX, {"app/services/index_service.py": INDEX}, old_path="app/services/index_service.py").ok


def _relocated(old: str, new_path: str, old_path: str = "app/services/x.py", new: str | None = None) -> dict[str, str]:
    """What RELOCATED says of each old symbol of ``old`` moved whole to ``new_path``, without the location."""
    report = compare(old, {new_path: old if new is None else new}, old_path=old_path)
    return {key: where.split(": ", 1)[1] for key, where in report.relocated.items()}


def test_each_name_is_relocated_only_when_its_value_differs():
    """One case per name. A sibling file keeps the package, so ``__package__`` and a relative import keep
    their values while the name and the file change; ``x.py`` to ``x/__init__.py`` keeps the name but makes
    it a package, which moves the package, the file and the relative imports; a class body's ``__module__``
    is the module's name; ``__path__`` exists only in a package; and a relative import that went beyond the
    top-level package is its own target."""
    reads = ("A = __name__\nB = __package__\nC = __file__\nD = __spec__\nE = __path__\nF = __loader__\nG = __cached__\n\n\n"
             "def load():\n    from .h import x\n    return x\n\n\nclass Box:\n    origin = __module__\n")
    assert _relocated(reads, "app/services/y.py") == {
        "A": "reads __name__ (app.services.y, was app.services.x)",
        "C": "reads __file__ (another file in the same directory)",
        "D": "reads __spec__ (another file in the same directory)",
        "F": "reads __loader__ (another file in the same directory)",
        "G": "reads __cached__ (another file in the same directory)",
        "Box.origin": "reads __module__ (app.services.y, was app.services.x)"}
    assert _relocated(reads, "app/services/x/__init__.py") == {
        "A": "reads __name__ (app.services.x, now a package)",
        "B": "reads __package__ ('app.services.x', was 'app.services')",
        "C": "reads __file__ (another file)", "D": "reads __spec__ (another file)", "E": "reads __path__ (another file)",
        "F": "reads __loader__ (another file)", "G": "reads __cached__ (another file)",
        "load": "imports x from .h (app.services.x.h, was app.services.h)"}
    beyond = "def load():\n    from ... import x\n    return x\n"
    assert _relocated(beyond, "app/services/sub/y.py") == {"load": "imports x from ... (app, was an ImportError)"}
    assert _relocated(reads, "app/services/x.py") == {}


def test_a_module_moved_to_another_directory_under_the_same_file_name_is_relocated():
    """``app/services/x.py`` to ``app/services/sub/x.py`` or ``app/utils/x.py`` keeps the file's name, not the
    module's: its name, package, file and namespace all change, and so does the module its dunders serve."""
    old = ("import logging\n\nlogger = logging.getLogger(__name__)\nPKG = __package__\n\n\ndef lookup(name):\n"
           "    return globals()[name]\n\n\ndef where():\n    return __file__\n\n\ndef __getattr__(name):\n    return name\n")
    for new_path in ("app/services/sub/x.py", "app/utils/x.py"):
        module = new_path.removesuffix(".py").replace("/", ".")
        assert _relocated(old, new_path, "app/services/x.py") == {
            "logger": f"reads __name__ ({module}, was app.services.x)",
            "PKG": f"reads __package__ ({module.rpartition('.')[0]!r}, was 'app.services')",
            "lookup": f"reads its module's namespace through globals() ({module}, was app.services.x)",
            "where": "reads __file__ (another file)",
            "__getattr__": f"binds __getattr__, which Python reads from {module}, was app.services.x"}, new_path


def test_a_symbol_is_relocated_only_for_what_it_reads_before_the_move_and_after_it():
    """A CHANGED symbol that still reads ``__name__`` is RELOCATED too; a disclosed change that starts or stops
    reading it is CHANGED only, its diff the disclosure; a parameter named ``__file__`` is not the module's."""
    old = "LOG = getLogger(__name__ + '.x')\nNEW = getLogger('fixed')\nOLD = getLogger(__name__)\n\n\ndef f(__file__):\n    return __file__\n"
    new = old.replace("'.x'", "'.y'").replace("getLogger('fixed')", "getLogger(__name__)").replace(
        "OLD = getLogger(__name__)", "OLD = getLogger('fixed')")
    report = compare(old, {"app/y.py": new}, old_path="app/x.py")
    assert set(report.changed) == {"LOG", "NEW", "OLD"}
    assert report.relocated == {"LOG": "app/y.py, was app/x.py: reads __name__ (app.y, was app.x)"}
    # A relative import rewritten for its new package keeps its target: CHANGED, its diff the disclosure.
    load = "def load():\n    from .h import x\n    return x\n"
    rewritten = compare(load, {"app/services/sub/y.py": load.replace("from .h", "from ..h")}, old_path="app/services/x.py")
    assert list(rewritten.changed) == ["load"] and rewritten.relocated == {}
    # So is a change that starts calling a builtin that reads the module's namespace.
    started = compare("def run(src):\n    return src\n", {"app/y.py": "def run(src):\n    return eval(src)\n"},
                      old_path="app/x.py")
    assert list(started.changed) == ["run"] and started.relocated == {}


def test_unchanged_code_calls_the_builtin_that_either_module_binds_its_alias_to():
    """The same text calls whatever each module binds its names to, so a builtin found on one side is read
    there however the other side binds the alias: one the old module bound and the new one imports from a
    helper is still the builtin, though the proof follows no import."""
    aliases = "_ev = eval\n_g = globals\n_compile = compile\n"
    code = ("def run(src):\n    return _ev(src)\n\n\ndef lookup(name):\n    return _g()[name]\n\n\n"
            "def build(src):\n    return _compile(src, '<generated>', 'exec')\n")
    split = compare(f"from __future__ import annotations\n\n{aliases}\n\n{code}",
                    {"app/x.py": "from app.y import *\n", "app/h.py": aliases,
                     "app/y.py": f"from app.h import _compile, _ev, _g\n\n\n{code}"}, old_path="app/x.py")
    namespace = "app/y.py, was app/x.py: reads its module's namespace through {} (app.y, was app.x)"
    compiled = "the code it compiles with {} inherits from __future__ nothing now, annotations before"
    assert split.relocated == {
        "run": f"{namespace.format('eval()')}; {compiled.format('eval()')}",
        "lookup": namespace.format("globals()"),
        "build": f"app/y.py, was app/x.py: {compiled.format('compile()')}"}


def test_a_name_a_module_binds_itself_is_compared_as_that_binding():
    """A name that a symbol of each module binds is compared as those symbols, so ``NAME`` moved with its
    ``__name__`` binding reads what it read; with the binding left behind it reads the new module's
    derived name. A relative import resolves against ``__package__``, so one the module pins is the same:
    the binding left behind, or added, is reported, and kept on both sides the import resolves as it did. Only
    the module's own string pins it: Python reads no class's, and takes None, a ``del`` or a reset through
    ``global`` as no pin, deriving the package from the path again.
    Each copy of a DUPLICATE away from the old path is DUPLICATE only."""
    old = "__name__ = 'legacy'\nNAME = __name__\n"
    both = compare(old, {"app/x.py": "", "app/y.py": old}, old_path="app/x.py")
    assert both.relocated == {"__name__": "app/y.py, was app/x.py: binds __name__, which Python reads from app.y, was app.x"}
    left = compare(old, {"app/x.py": "__name__ = 'legacy'\n", "app/y.py": "NAME = __name__\n"}, old_path="app/x.py")
    assert left.relocated == {"NAME": "app/y.py, was app/x.py: reads __name__ (the old module bound it)"}
    twice = compare("NAME = __name__\n", {"app/x.py": "", "app/y.py": "NAME = __name__\n", "app/z.py": "NAME = __name__\n"},
                    old_path="app/x.py")
    assert twice.duplicate == {"NAME": ["app/y.py", "app/z.py"]} and twice.relocated == {}
    pinned = '__package__ = "app.sub"\n\n\ndef load():\n    from .mod import NAME\n    return NAME\n'
    load = pinned.split("\n\n\n", 1)[1]
    behind = compare(pinned, {"app/x.py": '__package__ = "app.sub"\n', "app/y.py": load}, old_path="app/x.py")
    assert behind.relocated == {"load": "app/y.py, was app/x.py: imports NAME from .mod (the old module bound __package__)"}
    added = compare(load, {"app/x.py": pinned}, old_path="app/x.py")
    assert added.relocated == {"load": "app/x.py, was app/x.py: imports NAME from .mod (the new module binds __package__)"}
    assert _relocated(pinned, "app/x/__init__.py", "app/x.py") == {}
    # Only the definition that imports reads it: one above the binding that does not is no read.
    late = "import os\n\n\ndef load():\n    return None\n\n\n" + pinned
    assert _relocated(late, "app/x/__init__.py", "app/x.py") == {}
    classes = ('class Loader:\n    __package__ = "app"\n\n    def load(self):\n        from .mod import NAME\n        return NAME\n\n\n'
               'class Plugins:\n    __package__ = "app"\n    if READY:\n        from .mod import NAME\n')
    assert _relocated(classes, "app/sub/x.py", "app/x.py") == {
        "Loader.load": "imports NAME from .mod (app.sub.mod, was app.mod)",
        "Plugins.guard:if READY": "imports NAME from .mod (app.sub.mod, was app.mod)"}
    for above, below in (("__package__ = None", ""), ("__package__, OTHER = None, 1", ""),
                         ('__package__ = "app"', "\n\ndel __package__\n"),
                         ('__package__ = "app"', "\n\ndef reset():\n    global __package__\n    __package__ = None\n"),
                         ('__package__ = "app"', "\n\nfrom app.settings import PACKAGE as __package__\n"),
                         ("", '\n\n__package__ = "app"\n')):
        undone = f"{above}\n\n\n{load}{below}"
        assert _relocated(undone, "app/x/__init__.py", "app/x.py")["load"] == "imports NAME from .mod (app.x.mod, was app.mod)", undone


def test_a_binding_settles_a_name_only_when_it_sets_it_outright_above_the_read():
    """``__doc__ +=`` and ``__doc__.format()`` keep the docstring they read, the ``__package__`` shim binds
    only when the package is empty, a bare annotation binds nothing and a walrus in an empty comprehension never
    runs, and code above ``__doc__ = ...`` may read the docstring: a statement at import, or a def called
    there before the binding runs, a symbol's first definition included. Each still reads what the new module
    derives. Below the first binding the binding is the value, and a ``global`` store sets it outright too (its
    def is compared as a symbol). A definition above it that reads nothing of the name is no read. A binding in a
    ``match`` case may not run."""
    cli = '"""Filing CLI."""\n__doc__ += "\\n\\nUsage: run"\n\n\ndef usage():\n    return __doc__\n'
    assert _relocated(cli, "app/cli.py", "app/cli.py", cli.replace("Filing CLI.", "Facade.")) == {
        "__doc__": "reads __doc__ (the module docstring differs)", "usage": "reads __doc__ (the module docstring differs)"}
    formatted = cli.replace('__doc__ += "\\n\\nUsage: run"', "__doc__ = __doc__.format()")
    assert set(_relocated(formatted, "app/cli.py", "app/cli.py", formatted.replace("Filing CLI.", "Facade."))) == {
        "__doc__", "usage"}
    shim = "if not __package__:\n    __package__ = 'app.tools'\n\n\ndef where():\n    return __package__\n"
    assert _relocated(shim, "app/tools/runner/__init__.py", "app/tools/runner.py") == {
        "guard:if not __package__": "reads __package__ ('app.tools.runner', was 'app.tools')",
        "where": "reads __package__ ('app.tools.runner', was 'app.tools')"}
    above = ('"""Old."""\nDESCRIPTION = __doc__\n\n\ndef early():\n    return __doc__\n\n\n__doc__ = "Fixed."\nTITLE = __doc__\n\n\n'
             "def reset():\n    global __doc__\n    __doc__ = None\n\n\ndef usage():\n    return __doc__\n")
    assert _relocated(above, "app/x.py", "app/x.py", above.replace("Old.", "New.")) == {
        "DESCRIPTION": "reads __doc__ (the module docstring differs)", "early": "reads __doc__ (the module docstring differs)"}
    called = "def where():\n    return __package__\n\n\nANCHOR = where()\n__package__ = 'app.tools'\n"
    assert _relocated(called, "app/tools/runner/__init__.py", "app/tools/runner.py") == {
        "where": "reads __package__ ('app.tools.runner', was 'app.tools')"}
    twice = '"""Old."""\n__doc__ = "A"\nTEXT = __doc__\n__doc__ = "B"\n'
    assert _relocated(twice, "app/x.py", "app/x.py", twice.replace("Old.", "New.")) == {}
    reread = '"""Old."""\nTEXT = __doc__\n__doc__ = "Fixed."\nTEXT = __doc__\n'
    assert _relocated(reread, "app/x.py", "app/x.py", reread.replace("Old.", "New.")) == {
        "TEXT": "reads __doc__ (the module docstring differs)"}
    drafted = '"""Old."""\nTEXT = "draft"\n__doc__ = "Fixed."\nTEXT = __doc__\n'
    assert _relocated(drafted, "app/x.py", "app/x.py", drafted.replace("Old.", "New.")) == {}
    for binding in ("__doc__: str", '[(__doc__ := "x") for _ in ()]', 'match MODE:\n    case "cli":\n        __doc__ = "CLI."'):
        tentative = f'"""Old."""\n{binding}\nTEXT = __doc__\n'
        assert _relocated(tentative, "app/x.py", "app/x.py", tentative.replace("Old.", "New.")) == {
            "TEXT": "reads __doc__ (the module docstring differs)"}, binding


def test_a_class_body_read_is_settled_by_an_earlier_member_that_sets_the_name_outright():
    """A class body looks a name up in the class first, so a member that reads ``__module__`` or ``__doc__``
    after a member set it outright reads that value wherever the class moves, until a ``del`` of it and again
    after the next. A read above it, a binding in a block, one derived from the module's value, a read after a
    ``del`` (by a member defined above it too), and a lambda's read (a nested scope reads the module's) still
    take what the new module derives, as do a binding in a ``match`` case and a read below a ``del`` in one. A
    member's definition that reads nothing of the name is no read. A class defined twice runs each body in a
    namespace of its own, so a member of one settles no read in the other."""
    old = ('"""Old."""\n\n\nclass C:\n    __module__ = "stable"\n    origin = __module__\n\n\n'
           'class D:\n    origin = __module__\n    __module__ = "stable"\n\n\n'
           'class E:\n    if READY:\n        __module__ = "stable"\n    origin = __module__\n\n\n'
           'class F:\n    __doc__ = "Fixed."\n    usage = __doc__\n    both = (__doc__, (lambda: __doc__)())\n\n\n'
           'class K:\n    __doc__ = __doc__ + "!"\n    usage = __doc__\n\n\n'
           'class G:\n    __doc__ = "Fixed."\n    del __doc__\n    usage = __doc__\n\n\n'
           'class H:\n    __doc__ = "Fixed."\n    del __doc__\n    __doc__ = "Again."\n    usage = __doc__\n\n\n'
           'class J:\n    __doc__ = "Fixed."\n    del __doc__\n    __doc__, spare = "Again.", 1\n    usage = __doc__\n\n\n'
           'class L:\n    __doc__ = "Fixed."\n    usage = 1\n    del __doc__\n    usage = __doc__\n\n\n'
           'class M:\n    origin = 1\n    __module__ = "stable"\n    origin = __module__\n\n\n'
           'class N:\n    match MODE:\n        case "legacy":\n            __module__ = "stable"\n    origin = __module__\n\n\n'
           'class P:\n    __doc__ = "Fixed."\n    match MODE:\n        case 1:\n            del __doc__\n    usage = __doc__\n\n\n'
           'class Q:\n    __doc__ = "Fixed."\n    usage = __doc__\n    del __doc__\n    usage = __doc__\n')
    assert _relocated(old, "app/y.py", "app/x.py", old.replace("Old.", "New.")) == {
        "D.origin": "reads __module__ (app.y, was app.x)", "E.origin": "reads __module__ (app.y, was app.x)",
        "F.both": "reads __doc__ (the module docstring differs)", "K.__doc__": "reads __doc__ (the module docstring differs)",
        "K.usage": "reads __doc__ (the module docstring differs)", "G.usage": "reads __doc__ (the module docstring differs)",
        "L.usage": "reads __doc__ (the module docstring differs)", "N.origin": "reads __module__ (app.y, was app.x)",
        "P.usage": "reads __doc__ (the module docstring differs)", "Q.usage": "reads __doc__ (the module docstring differs)"}
    twice = ('import sys\n\nif sys.version_info < (3, 0):\n    class A:\n        __module__ = "legacy"\nelse:\n'
             '    class A:\n        origin = __module__\n')
    assert _relocated(twice, "app/y.py", "app/x.py") == {"A.origin": "reads __module__ (app.y, was app.x)"}


def test_a_name_one_module_sets_outright_and_the_other_does_not_is_relocated():
    """One module's own binding against the other's derived value, whichever side holds it: a binding moved
    into a block may never run, and a def or a method that binds through ``global`` binds the module's name."""
    plain = '__doc__ = "Fixed."\nTEXT = __doc__\n'
    guarded = 'if READY:\n    __doc__ = "Fixed."\nTEXT = __doc__\n'
    assert _relocated(plain, "app/x.py", "app/x.py", guarded) == {"TEXT": "reads __doc__ (the old module bound it)"}
    assert _relocated(guarded, "app/x.py", "app/x.py", plain) == {"TEXT": "reads __doc__ (the new module binds it)"}
    setup = "def setup():\n    global __doc__\n    __doc__ = 'Ready.'\n\n\ndef usage():\n    return __doc__\n"
    split = compare(setup, {"app/x.py": setup.split("\n\n\n")[0] + "\n", "app/y.py": "def usage():\n    return __doc__\n"},
                    old_path="app/x.py")
    assert split.relocated == {"usage": "app/y.py, was app/x.py: reads __doc__ (the old module bound it)"}
    method = ("class Setup:\n    def run(self):\n        global __doc__\n        __doc__ = 'Ready.'\n\n\n"
              "def usage():\n    return __doc__\n")
    moved = compare(method, {"app/x.py": method.split("\n\n\n")[0] + "\n", "app/y.py": "def usage():\n    return __doc__\n"},
                    old_path="app/x.py")
    assert moved.relocated == {"usage": "app/y.py, was app/x.py: reads __doc__ (the old module bound it)"}


def test_moved_code_that_reads_the_module_docstring_is_relocated_when_it_differs():
    """A façade rewrites the module docstring on the old path, so code that stays there and reads ``__doc__``
    (``argparse``'s description) is RELOCATED; the same docstring is OK. In a class body a documented class
    reads its own ``__doc__``; a method reads the module's."""
    old = '"""Old."""\nDESCRIPTION = __doc__\n\n\nclass Cli:\n    """Cli."""\n    usage = __doc__\n\n    def help(self):\n        return __doc__\n'
    assert _relocated(old, "app/x.py", "app/x.py", old.replace("Old.", "New.")) == {
        "DESCRIPTION": "reads __doc__ (the module docstring differs)",
        "Cli.help": "reads __doc__ (the module docstring differs)"}
    assert _relocated(old, "app/x.py", "app/x.py") == {}
    member = '"""Old."""\nDESCRIPTION = __doc__\n\n\nclass Cli:\n    __doc__ = "Cli usage."\n'
    assert _relocated(member, "app/x.py", "app/x.py", member.replace("Old.", "New.")) == {
        "DESCRIPTION": "reads __doc__ (the module docstring differs)"}
    indented = '"""Title.\n\n    Body.\n"""\nDESCRIPTION = __doc__\n'
    assert _relocated(indented, "app/x.py", "app/x.py", indented.replace("    Body.", "        Body.")) == {
        "DESCRIPTION": "reads __doc__ (the module docstring differs)"}


def test_a_documented_class_binds_its_own_docstring_wherever_it_stands():
    """Nested in a class or built in a def, a documented class reads its own ``__doc__``, and so does a
    block in its body, until its body deletes the name (a ``del``, in a block too, an ``except ... as __doc__``,
    or a ``del`` in a loop, which runs again what stands above it); an undocumented class body, or one below that
    deletion, falls through to the module's, past any enclosing class. A nested class that deletes it anywhere
    reads the module's throughout (fail closed)."""
    old = ('"""Old."""\n\n\nclass Plain:\n    usage = __doc__\n\n\nclass Cli:\n    """Cli."""\n    if __doc__:\n        usage = 1\n\n\n'
           'class Job:\n    class Options:\n        """Scan."""\n        help = __doc__\n\n\n'
           'def build():\n    class Command:\n        """Backfill."""\n        help = __doc__\n    return Command\n\n\n'
           "class Outer:\n    class Inner:\n        help = __doc__\n\n\n"
           'class Erased:\n    """Gone."""\n    del __doc__\n    help = __doc__\n    if __doc__:\n        flag = 1\n\n\n'
           'class Maybe:\n    """Maybe."""\n    if FLAG:\n        del __doc__\n    help = __doc__\n\n\n'
           'class Kept:\n    """Kept."""\n    spare = 1\n    del spare\n    help = __doc__\n\n\n'
           'class Caught:\n    """Caught."""\n    try:\n        raise LookupError\n    except LookupError as __doc__:\n        pass\n'
           '    help = __doc__\n\n\n'
           'class Looped:\n    """Looped."""\n    seen = []\n    for _pass in range(2):\n        seen.append(__doc__)\n'
           '        if _pass == 0:\n            del __doc__\n\n\n'
           'class Waited:\n    """Waited."""\n    n = 0\n    while n < 2:\n        n += 1\n        last = __doc__\n'
           '        if n == 1:\n            del __doc__\n\n\n'
           'class Shell:\n    class Inner:\n        """Inner."""\n        del __doc__\n        help = __doc__\n\n\n'
           'def make():\n    class Command:\n        """Backfill."""\n        del __doc__\n        help = __doc__\n    return Command\n')
    assert _relocated(old, "app/x.py", "app/x.py", old.replace("Old.", "New.")) == {
        **dict.fromkeys(("Plain.usage", "Outer.Inner", "Erased.help", "Erased.guard:if __doc__", "Maybe.help", "Caught.help",
                         "Looped.expr:seen.append(__doc__)", "Waited.last", "Shell.Inner", "make"),
                        "reads __doc__ (the module docstring differs)")}


def test_a_block_reads_its_header_and_a_class_its_body_imports():
    """A block reads where its module lives through its header only (a ``__main__`` guard moved away no longer
    runs under ``python -m``), whichever header it is (a test, a context, an iterable or target, a handled
    exception) and a namespace call there too; its statements are symbols of their own, a def in it included.
    A relative import directly in a class body, or in a block (at module level too), is in no symbol's text, so
    the class or the block reports it."""
    old = ("if __name__ == '__main__':\n    main()\n\nif READY:\n    PATH = __file__\n\n    def load():\n"
           "        from . import h\n        return h\n\n\nclass Loader:\n    from . import h\n")
    assert _relocated(old, "app/services/sub/y.py") == {
        "guard:if __name__ == '__main__'": "reads __name__ (app.services.sub.y, was app.services.x)",
        "PATH": "reads __file__ (another file)",
        "load": "imports h from . (app.services.sub, was app.services)",
        "Loader": "imports h from . (app.services.sub, was app.services)"}
    fallback = ("try:\n    from .fast import impl\nexcept ImportError:\n    from .slow import impl\n\n\n"
                "class Plugins:\n    if READY:\n        KIND = None\n    else:\n        from .h import KIND\n")
    assert _relocated(fallback, "app/services/sub/y.py") == {
        "guard:try except ImportError": "imports impl from .fast (app.services.sub.fast, was app.services.fast); "
                                        "imports impl from .slow (app.services.sub.slow, was app.services.slow)",
        "Plugins.guard:if READY": "imports KIND from .h (app.services.sub.h, was app.services.h)"}
    headers = ("if 'LIMIT' in globals():\n    READY = True\n\nwith open(Path(__file__).with_name('a.txt')) as _fh:\n"
               "    DATA = _fh.read()\n\nfor _word in Path(__file__).read_text().split():\n    NAMES.append(_word)\n\n"
               "for SEEN[__name__] in ['v']:\n    pass\n\ntry:\n    import fast\n"
               "except getattr(sys.modules[__name__], 'Handled', ImportError):\n    fast = None\n\n\n"
               "class Config:\n    if eval('DEBUG'):\n        level = 10\n")
    namespace = "reads its module's namespace through {} (app.services.sub.y, was app.services.x)"
    assert _relocated(headers, "app/services/sub/y.py") == {
        "guard:if 'LIMIT' in globals()": namespace.format("globals()"),
        "guard:with open(Path(__file__).with_name('a.txt')) as _fh": "reads __file__ (another file)",
        "guard:for _word in Path(__file__).read_text().split()": "reads __file__ (another file)",
        "guard:for SEEN[__name__] in ['v']": "reads __name__ (app.services.sub.y, was app.services.x)",
        "guard:try except getattr(sys.modules[__name__], 'Handled', ImportError)":
            "reads __name__ (app.services.sub.y, was app.services.x)",
        "Config.guard:if eval('DEBUG')": namespace.format("eval()")}


def test_namespace_reads_postponed_annotations_and_moved_module_dunders_are_relocated():
    """``globals()``, and ``eval`` without a namespace, read another module's namespace from a new file;
    ``from __future__ import annotations`` in one module only changes how annotated code compiles (once on a
    class, for its members); and a module-level dunder, moved, is read from the new module. A file that keeps
    its module keeps all three, but its namespace only while it binds the same names: a split that moves one out
    without a re-export, or drops an import, changes what ``globals()`` holds there. ``x.py`` to ``x/__init__.py``
    keeps the name a module dunder is read under, but not the namespace, which gains ``__path__`` and another
    ``__file__``, either way."""
    old = ("def lookup(name):\n    return globals()[name]\n\n\ndef run(src):\n    return eval(src)\n\n\n"
           "def scoped(src, ns):\n    return eval(src, ns)\n\n\ndef total(rows: list) -> int:\n    return len(rows)\n\n\n"
           "def plain(rows):\n    return rows\n\n\nclass Row:\n    key: str\n\n    def size(self) -> int:\n        return 0\n\n\n"
           "def __getattr__(name):\n    return name\n")
    moved = _relocated(old, "app/x/impl.py", "app/x.py", "from __future__ import annotations\n\n" + old)
    compiled = "the code it compiles with eval() inherits from __future__ annotations now, nothing before"
    assert moved == {
        "lookup": "reads its module's namespace through globals() (app.x.impl, was app.x)",
        "run": f"reads its module's namespace through eval() (app.x.impl, was app.x); {compiled}",
        "scoped": compiled,
        "total": "its annotations are postponed now (from __future__ import annotations), evaluated before",
        "Row": "its annotations are postponed now (from __future__ import annotations), evaluated before",
        "__getattr__": "binds __getattr__, which Python reads from app.x.impl, was app.x"}
    assert _relocated(old, "app/x.py", "app/x.py") == {}
    split = "A = 1\n\n\ndef keys():\n    return sorted(globals())\n\n\ndef value():\n    return eval('A')\n"
    kept = split.split("\n\n\n", 1)[1]
    gone = "app/x.py, was app/x.py: reads its module's namespace through {} (app.x, which binds other names: A gone)"
    assert compare(split, {"app/x.py": kept, "app/a.py": "A = 1\n"}, old_path="app/x.py").relocated == {
        "keys": gone.format("globals()"), "value": gone.format("eval()")}
    assert compare(split, {"app/x.py": "from app.a import A\n\n\n" + kept, "app/a.py": "A = 1\n"},
                   old_path="app/x.py").relocated == {}
    # A def that binds through ``global`` binds in its module's namespace; a star import binds what its source holds.
    setup = "def setup():\n    global READY\n    READY = True\n\n\ndef keys():\n    return sorted(globals())\n"
    moved = compare(setup, {"app/x.py": "from app.a import setup\n\n\n" + setup.split("\n\n\n", 1)[1],
                            "app/a.py": setup.split("\n\n\n", 1)[0] + "\n"}, old_path="app/x.py")
    assert moved.relocated["keys"].endswith("(app.x, which binds other names: READY gone)")
    star = "from app.c import *\n\n\ndef keys():\n    return sorted(globals())\n"
    assert _relocated(star, "app/x.py", "app/x.py", star.replace("app.c", "app.d")) == {
        "keys": "reads its module's namespace through globals() (app.x, which binds other names: * from app.c gone; "
                "* from app.d new)"}
    package = "reads its module's namespace through {} (app.x, {} a package)"
    assert _relocated(old, "app/x/__init__.py", "app/x.py") == {
        "lookup": package.format("globals()", "now"), "run": package.format("eval()", "now")}
    assert _relocated(old, "app/x.py", "app/x/__init__.py") == {
        "lookup": package.format("globals()", "no longer"), "run": package.format("eval()", "no longer")}


def test_eval_and_exec_read_the_callers_namespace_unless_given_globals_of_their_own():
    """CPython runs ``eval`` and ``exec`` in the caller's globals when none are given or the given ones are
    ``None`` (by position or by keyword, with only ``locals=`` or ``closure=``, or unpacked from a sequence the
    proof cannot see into); a mapping of their own, or a parameter named ``eval``, reads nothing of the module."""
    old = ("def run(src):\n    exec(src)\n\n\ndef evaluate(expr, row):\n    return eval(expr, None, row)\n\n\n"
           "def closure(src):\n    exec(src, closure=None)\n\n\ndef unpacked(src, rest):\n    return eval(src, *rest)\n\n\n"
           "def keyword(src):\n    return eval(src, globals=None)\n\n\ndef only_locals(src, ns):\n    return eval(src, locals=ns)\n\n\n"
           "def scoped(src, ns):\n    return eval(src, {}, ns)\n\n\n"
           "def given(src):\n    return eval(src, globals={})\n\n\ndef local(expr, eval):\n    return eval(expr)\n")
    namespace = "reads its module's namespace through {} (app.y, was app.x)"
    assert _relocated(old, "app/y.py", "app/x.py") == {
        "run": namespace.format("exec()"), "evaluate": namespace.format("eval()"), "closure": namespace.format("exec()"),
        "unpacked": namespace.format("eval()"), "keyword": namespace.format("eval()"),
        "only_locals": namespace.format("eval()")}


def test_a_builtin_is_reached_by_a_call_above_any_module_binding_of_its_name():
    """Code that runs at import above ``eval = fake`` still calls the builtin, which reads the new module's
    namespace once moved; below a binding, the call is the module's ``eval`` until a ``del`` of it, and again
    after the next binding. A binding that may not happen (in a block or a ``match``, a bare annotation, a
    walrus) leaves the builtin, and so does a deletion that may happen: a ``del`` in a block or a ``match`` case,
    an ``except ... as eval`` (which deletes its name), a ``del`` in a loop (which runs again what stands above
    it), or either one through ``global`` in a def or a class body; ``from builtins import eval`` is the builtin, and a call in the
    statement that binds ``eval`` is still made to the builtin. A def's body runs when called, and a generator
    expression's past its first iterable when consumed, both after import, past any ``del`` below them. A class
    body looks the name up
    in the class first, a block in it too: an ``eval`` its class bound above for certain is the class's, but a
    method's body, or a call above that binding, reaches the builtin."""
    above = 'RESULT = eval("__name__")\n\n\ndef fake(src):\n    return "fake"\n\n\neval = fake\n'
    split = compare(above, {"app/x.py": above.replace('RESULT = eval("__name__")\n\n\n', ""),
                            "app/y.py": 'RESULT = eval("__name__")\n'}, old_path="app/x.py")
    assert split.relocated == {"RESULT": "app/y.py, was app/x.py: reads its module's namespace through eval() (app.y, was app.x)"}
    below = 'def fake(src):\n    return "fake"\n\n\neval = fake\nRESULT = eval("__name__")\neval = fake\n'
    assert _relocated(below, "app/y.py", "app/x.py") == {}
    classes = ('class C:\n    eval = staticmethod(lambda _: "stable")\n    result = eval("__name__")\n\n\n'
               'class D:\n    eval = staticmethod(lambda _: "stable")\n\n    def run(self, src):\n        return eval(src)\n\n\n'
               'class E:\n    result = eval("__name__")\n    eval = staticmethod(lambda _: "late")\n\n\n'
               'class F:\n    eval = staticmethod(lambda _: True)\n    if eval("__name__"):\n        flag = 1\n\n\n'
               'class G:\n    eval = staticmethod(lambda _: "first")\n    result = eval("__name__")\n    eval = staticmethod(lambda _: "next")\n\n\n'
               'class H:\n    if FLAG:\n        eval = staticmethod(lambda _: "maybe")\n    result = eval("__name__")\n')
    namespace = "reads its module's namespace through eval() (app.y, was app.x)"
    assert _relocated(classes, "app/y.py", "app/x.py") == {"D.run": namespace, "E.result": namespace, "H.result": namespace}
    for binding in ("if FLAG:\n    eval = fake", "eval = fake\ndel eval", "try:\n    from nowhere import eval\nexcept ImportError:\n    pass",
                    "eval: object", "[(eval := fake) for _ in ()]", "match FLAG:\n    case True:\n        eval = fake",
                    "from builtins import eval", "eval = fake\nif FLAG:\n    del eval",
                    "eval = fake\nmatch FLAG:\n    case True:\n        del eval",
                    "eval = fake\ntry:\n    raise LookupError\nexcept LookupError as eval:\n    pass",
                    "eval = fake\n\n\ndef reset():\n    global eval\n    del eval\n\n\nreset()",
                    "eval = fake\n\n\nclass Reset:\n    global eval\n    del eval\n",
                    "eval = fake\n\n\ndef caught():\n    global eval\n    try:\n        raise LookupError\n"
                    "    except LookupError as eval:\n        pass\n\n\ncaught()"):
        uncertain = f'def fake(src):\n    return "fake"\n\n\n{binding}\nRESULT = eval("__name__")\n'
        moved = compare(uncertain, {"app/x.py": uncertain.replace('RESULT = eval("__name__")\n', ""),
                                    "app/y.py": 'RESULT = eval("__name__")\n'}, old_path="app/x.py")
        assert moved.relocated == {"RESULT": f"app/y.py, was app/x.py: {namespace}"}, binding
        assert _relocated(uncertain, "app/y.py", "app/x.py") == {"RESULT": namespace}, binding  # the binding moved too
    deleted_after = 'def fake(src):\n    return "fake"\n\n\neval = fake\nRESULT = eval("__name__")\ndel eval\n'
    assert _relocated(deleted_after, "app/y.py", "app/x.py") == {}
    rebound = 'def fake(src):\n    return "fake"\n\n\neval = fake\ndel eval\neval = fake\nRESULT = eval("__name__")\n'
    assert _relocated(rebound, "app/y.py", "app/x.py") == {}
    unpacked = 'def fake(src):\n    return "fake"\n\n\nRESULT, eval = eval("__name__"), fake\n'
    assert _relocated(unpacked, "app/y.py", "app/x.py") == {"RESULT,eval": namespace}
    deferred = 'def fake(src):\n    return "fake"\n\n\neval = fake\n\n\ndef run(src):\n    return eval(src)\n\n\ndel eval\n'
    assert _relocated(deferred, "app/y.py", "app/x.py") == {"run": namespace}
    assert _relocated(deferred.replace("\n\n\ndel eval\n", "\n"), "app/y.py", "app/x.py") == {}
    pending = ('def fake(src):\n    return "fake"\n\n\neval = fake\nPENDING = (eval(src) for src in ["__name__"])\n'
               'FIRST = (src for src in eval("__name__"))\nRUN = lambda src: eval(src)\ndel eval\n')
    assert _relocated(pending, "app/y.py", "app/x.py") == {"PENDING": namespace, "RUN": namespace}
    # A def's own ``del`` of a local, with no ``global``, undoes nothing of the module's.
    local = 'def fake(src):\n    return "fake"\n\n\neval = fake\n\n\ndef local():\n    eval = 1\n    del eval\n\n\nRESULT = eval("__name__")\n'
    assert _relocated(local, "app/y.py", "app/x.py") == {}
    looped = ('def fake(src):\n    return "fake"\n\n\neval = fake\nRESULT = []\nfor _pass in range(2):\n'
              '    RESULT.append(eval("__name__"))\n    if _pass == 0:\n        del eval\n')
    assert _relocated(looped, "app/y.py", "app/x.py") == {"expr:RESULT.append(eval('__name__'))": namespace}


def test_a_builtin_is_followed_through_any_name_or_import_that_binds_it():
    """A builtin is the builtin whatever name holds it: imported from ``builtins`` under another name or its
    own, at module level (in a block too), in the def or in a class body; bound from it (an assignment, a display
    unpacked pairwise, ``:=``, in a comprehension too, or a parameter's default, a call through ``:=`` itself
    included) by a name that is the builtin where the binding stands (above ``eval = fake`` too; an import from
    ``builtins`` aside) or from the ``builtins`` module; and an attribute of that module, however imported. The
    reason names the builtin. Such a name is the builtin where its binding is seen: the module's where the code
    reads the module's name, a class body's in that body (a method's defaults included, not its body), a def's
    in its own code. A
    parameter that holds it is not, nor a parameter named like a module alias or ``builtins``, an alias or a
    default of an ``eval`` the module or the class binds, an attribute of another module, a name assigned from
    an import that shadows the builtin, or one builtin imported under another's name (``len as eval``)."""
    old = ("import builtins\nfrom builtins import eval as run, globals as scope, compile as build\n\nrebound = eval\n"
           "attribute: object = builtins.exec\n\n\ndef aliased(src):\n    return run(src)\n\n\n"
           "def lookup(name):\n    return scope()[name]\n\n\ndef local(src):\n    from builtins import eval as go\n"
           "    return go(src)\n\n\ndef own(src):\n    from builtins import eval\n    return eval(src)\n\n\n"
           "def dotted(src):\n    return builtins.eval(src)\n\n\ndef renamed(src):\n    import builtins as b\n"
           "    b.exec(src)\n\n\ndef assigned(src):\n    return rebound(src)\n\n\n"
           "def annotated(src):\n    attribute(src)\n\n\ndef compiled(src):\n    return build(src, '<generated>', 'exec')\n\n\n"
           "maker = compile\n\n\ndef made(src):\n    return maker(src, '<generated>', 'exec')\n\n\n"
           "def given(run, src):\n    return run(src)\n\n\ndef scoped(src, eval):\n    held = eval\n    return held(src)\n\n\n"
           "def mine(src):\n    held = eval\n    return held(src)\n\n\n"
           "class Holder:\n    run_here = eval\n    result = run_here('__name__')\n\n    def later(self, src):\n"
           "        return run_here(src)\n\n\ndef passed(builtins, src):\n    return builtins.eval(src)\n\n\n"
           "class Shadowed:\n    eval = staticmethod(len)\n    run_here = eval\n    result = run_here('__name__')\n\n\n"
           "try:\n    from builtins import exec as tried\nexcept ImportError:\n    tried = None\n\n\n"
           "def attempt(src):\n    tried(src)\n\n\nif (walrus := eval):\n    pass\n\n\ndef caught(src):\n    return walrus(src)\n\n\n"
           "[(listed := eval) for _ in range(1)]\n\n\ndef from_list(src):\n    return listed(src)\n\n\n"
           "def defaulted(src, chosen=eval):\n    return chosen(src)\n\n\ndef keyword(src, *, chosen=exec):\n    chosen(src)\n\n\n"
           "first, second = eval, globals\n\n\ndef pair(name):\n    return second()[name]\n\n\n"
           "def unpack(src):\n    run_it, look = eval, globals\n    return run_it(src)\n\n\n"
           "def called(src):\n    return (go := eval)(src)\n\n\nclass Inline:\n    result = (go := eval)('__name__')\n\n\n"
           "class Captured:\n    eval = eval\n\n    def run(self, src, chosen=eval):\n        return chosen(src)\n\n\n"
           "class Swapped:\n    eval = staticmethod(len)\n\n    def run(self, src, chosen=eval):\n        return chosen(src)\n")
    namespace = "reads its module's namespace through {} (app.y, was app.x)"
    assert _relocated(old, "app/y.py", "app/x.py") == {
        **dict.fromkeys(("aliased", "local", "own", "dotted", "assigned", "mine", "Holder.result", "caught", "from_list",
                         "defaulted", "unpack", "called", "Inline.result", "Captured.run"), namespace.format("eval()")),
        **dict.fromkeys(("renamed", "annotated", "attempt", "keyword"), namespace.format("exec()")),
        **dict.fromkeys(("lookup", "pair"), namespace.format("globals()"))}
    flufl = _relocated(old, "app/y.py", "app/x.py", "from __future__ import barry_as_FLUFL\n\n" + old)
    compiled = "the code it compiles with compile() inherits from __future__ barry_as_FLUFL now, nothing before"
    assert flufl["compiled"] == flufl["made"] == compiled
    imported = "from builtins import eval\n\nrun = eval\n\n\ndef call(src):\n    return run(src)\n"
    assert _relocated(imported, "app/y.py", "app/x.py") == {"call": namespace.format("eval()")}
    early = 'run = eval\n\n\ndef fake(src):\n    return src\n\n\neval = fake\n\n\ndef call(src):\n    return run(src)\n'
    assert _relocated(early, "app/y.py", "app/x.py") == {"call": namespace.format("eval()")}
    others = ("import json\nimport re\nfrom re import compile\n\npattern = compile\nsearch = re.compile\n\n\n"
              "def fake(src):\n    return src\n\n\neval = fake\nrun = eval\n\n\ndef parse(src):\n    return json.loads(src)\n\n\n"
              "def match(src):\n    return pattern(src)\n\n\ndef find(src):\n    return search(src)\n\n\n"
              "def call(src):\n    return run(src)\n\n\ndef method(engine, src):\n    return engine.eval(src)\n\n\n"
              "def kept(src):\n    held = eval\n    return held(src)\n\n\n"
              "class Kept:\n    run_here = eval\n    result = run_here('__name__')\n\n\n"
              "class Imports:\n    import builtins\n    result = builtins.eval('__name__')\n\n\n"
              "def fallback(src, chosen=eval):\n    return chosen(src)\n\n\n"
              "class Reimported:\n    from builtins import eval\n\n    def run(self, src, chosen=eval):\n        return chosen(src)\n\n"
              "    def body(self, src):\n        held = eval\n        return held(src)\n")
    assert _relocated(others, "app/y.py", "app/x.py", "from __future__ import barry_as_FLUFL\n\n" + others) == dict.fromkeys(
        ("Imports.result", "Reimported.run"), namespace.format("eval()") + "; " + compiled.replace("compile()", "eval()"))
    renaming = ("from builtins import len as eval\nRESULT = eval('abc')\n\n\n"
                "class Sized:\n    from builtins import len as exec\n    result = exec('abc')\n")
    assert _relocated(renaming, "app/y.py", "app/x.py") == {}


def test_module_is_a_class_bodys_only():
    """A class body binds ``__module__`` before it runs, a nested one in a def too, until a ``del`` directly in the
    body; anywhere else, and below that ``del``, the name is unbound before the move and after it (NameError), a
    method's body included. A ``del`` in a block may not run, so a read below it may still be the class's."""
    old = ("def where():\n    return __module__\n\n\nclass Box:\n    origin = __module__\n\n    def own(self):\n"
           "        return __module__\n\n\ndef build():\n    class Inner:\n        origin = __module__\n    return Inner\n\n\n"
           "class Erased:\n    origin = __module__\n    del __module__\n    late = __module__\n\n\n"
           "class Maybe:\n    if FLAG:\n        del __module__\n    late = __module__\n")
    assert _relocated(old, "app/y.py", "app/x.py") == dict.fromkeys(
        ("Box.origin", "build", "Erased.origin", "Maybe.late"), "reads __module__ (app.y, was app.x)")


def test_only_annotations_python_evaluates_and_code_compiled_under_the_future_import_count():
    """Each form alone, moved into a module that postpones annotations: a parameter (``*args`` and ``**kwargs``
    too), a return, an async def's, a class field, a class built in a def and a nested def's parameter. Code
    handed to the builtin ``eval``, ``exec`` or ``compile`` inherits every ``from __future__`` import of the
    caller (a ``barry_as_FLUFL`` too), whatever globals it runs in, unless ``compile`` is told
    ``dont_inherit``, with a reason of its own that names the builtins, both ways; an imported ``compile`` is
    not the builtin. What ``eval`` compiles holds no annotation, but its code carries the annotations import into
    what it compiles and the lambdas it makes, so ``eval`` counts as the others do. The other ``__future__``
    imports change nothing Python 3 compiles. An annotation in a def's body, ``self.calls: list[str] = []``
    included, is never evaluated."""
    old = ("def param(rows: list):\n    return rows\n\n\ndef ret(rows) -> list:\n    return rows\n\n\n"
           "class Field:\n    key: str\n\n\ndef local(rows):\n    count: Undefined = len(rows)\n    return count\n\n\n"
           "class Fake:\n    def __init__(self):\n        self.calls: list[str] = []\n\n\n"
           "def factory():\n    class Row:\n        key: Later\n    return Row\n\n\n"
           "def nested():\n    def inner(x: Later):\n        return x\n    return inner\n\n\n"
           "def make(src, ns):\n    exec(src, {}, ns)\n\n\ndef build(src):\n    return compile(src, '<generated>', 'exec')\n\n\n"
           "def isolated(src):\n    return compile(src, '<generated>', 'exec', dont_inherit=True)\n\n\n"
           "def apart(src):\n    return compile(src, '<generated>', 'exec', 0, True)\n\n\n"
           "def inherits(src):\n    return compile(src, '<generated>', 'exec', dont_inherit=False)\n\n\n"
           "def zero(src):\n    return compile(src, '<generated>', 'exec', 0, 0)\n\n\n"
           "async def fetch(row: Row) -> Row:\n    return row\n\n\ndef merge(*rows: Row):\n    return rows\n\n\n"
           "def extra(**rows: Row):\n    return rows\n\n\ndef value(src):\n    return eval(src, {})\n\n\n"
           "def both(src):\n    exec(src, {})\n    return eval(src, {})\n")
    future = "from __future__ import annotations\n\n"
    postponed = "its annotations are postponed now (from __future__ import annotations), evaluated before"
    compiled = "the code it compiles with {} inherits from __future__ {} now, {} before"
    assert _relocated(old, "app/x/impl.py", "app/x.py", future + old) == {
        **dict.fromkeys(("param", "ret", "Field", "factory", "nested", "fetch", "merge", "extra"), postponed),
        "make": compiled.format("exec()", "annotations", "nothing"),
        **dict.fromkeys(("build", "inherits", "zero"), compiled.format("compile()", "annotations", "nothing")),
        "value": compiled.format("eval()", "annotations", "nothing"),
        "both": compiled.format("eval(), exec()", "annotations", "nothing")}
    back = _relocated(future + old, "app/x/impl.py", "app/x.py", old)
    assert back["param"] == "its annotations are evaluated now, postponed before"
    assert back["make"] == compiled.format("exec()", "nothing", "annotations")
    flufl = _relocated(old, "app/x/impl.py", "app/x.py", "from __future__ import barry_as_FLUFL\n\n" + old)
    assert flufl == {"make": compiled.format("exec()", "barry_as_FLUFL", "nothing"),
                     **dict.fromkeys(("build", "inherits", "zero"), compiled.format("compile()", "barry_as_FLUFL", "nothing")),
                     "value": compiled.format("eval()", "barry_as_FLUFL", "nothing"),
                     "both": compiled.format("eval(), exec()", "barry_as_FLUFL", "nothing")}
    either = _relocated(future + old, "app/x/impl.py", "app/x.py",
                        "from __future__ import annotations, barry_as_FLUFL\n\n" + old)
    assert either["value"] == compiled.format("eval()", "annotations, barry_as_FLUFL", "annotations")
    assert either["make"] == compiled.format("exec()", "annotations, barry_as_FLUFL", "annotations")
    imported = 'from re import compile\n\n\ndef pattern():\n    return compile(r"\\d+")\n'
    assert _relocated(imported, "app/x/impl.py", "app/x.py", future + imported) == {}
    for noop in ("generator_stop", "division", "print_function", "unicode_literals"):
        assert _relocated(f"from __future__ import {noop}\n\n" + old, "app/x.py", "app/x.py", old) == {}, noop


def test_a_module_dunder_bound_through_global_is_relocated_and_a_class_dunder_or_private_name_is_not():
    """A def or a method that binds a module dunder through ``global`` installs it on the module it now lives
    in, and a moved ``__all__`` no longer lists the façade's exports; a block reports a dunder defined in it as
    that def. A class's ``__init__`` and ``__eq__`` move with their class, and ``__registry`` is a private
    name, not a dunder."""
    old = ("def enable():\n    global __getattr__\n\n    def __getattr__(name):\n        return name\n\n\n"
           "class Exports:\n    @staticmethod\n    def install():\n        global __dir__\n        __dir__ = lambda: ['x']\n\n\n"
           "class Box:\n    def __init__(self):\n        self.n = 1\n\n    def __eq__(self, other):\n        return True\n\n\n"
           "__registry = {}\n__all__ = ['enable']\n\nif LAZY:\n\n    def __dir__():\n        return []\n")
    assert _relocated(old, "app/x/install.py", "app/x.py") == {
        "__dir__": "binds __dir__, which Python reads from app.x.install, was app.x",
        "enable": "binds __getattr__, which Python reads from app.x.install, was app.x",
        "Exports.install": "binds __dir__, which Python reads from app.x.install, was app.x",
        "__all__": "binds __all__, which Python reads from app.x.install, was app.x"}


def test_without_the_old_path_every_read_but_the_docstrings_fails_closed():
    """``old_path`` places the old module; the CLI always passes ``--old``. Without it, a read of where the
    module lives cannot be cleared, so it is reported; the module docstring can still be compared."""
    source = ('"""Doc."""\n' + INDEX + "DESCRIPTION = __doc__\n\n\ndef lookup(name):\n    return globals()[name]\n\n\n"
              "def __getattr__(name):\n    return name\n")
    report = compare(source, {"app/services/index_service.py": source})
    assert {key: where.split(": ", 1)[1] for key, where in report.relocated.items()} == {
        "DATA_PATH": "reads __file__ (the old path is unknown)",
        "load_helper": "imports helpers from . (app.services, was an unknown module)",
        "logger": "reads __name__ (the old path is unknown)",
        "lookup": "reads its module's namespace through globals() (app.services.index_service, was an unknown module)",
        "__getattr__": "binds __getattr__, which Python reads from app.services.index_service, was an unknown module"}
    assert all(where.startswith("app/services/index_service.py, was an unknown path: ")
               for where in report.relocated.values())


def test_the_cli_derives_a_modules_identity_from_its_path_however_it_is_spelled(monkeypatch, capsys):
    """``./``, ``..`` and an absolute path name the same file, so a file compared with itself is one module,
    and the file read is the one named; a path outside ``backend/`` names no module of it."""
    read = []

    def show(ref: str, path: str) -> str:
        read.append(path)
        return INDEX

    monkeypatch.setattr(ast_move_proof, "_git_show", show)
    spelled = str(ast_move_proof.BACKEND_DIR / "app/services/index_service.py")
    assert ast_move_proof.main(["--base", "B", "--old", "app/services/../services/index_service.py", "--new", spelled]) == 0
    assert read == ["app/services/index_service.py", "app/services/index_service.py"]
    assert "pure move: OK (3 symbols identical" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="is not under backend/"):
        ast_move_proof.main(["--base", "B", "--old", "../frontend/x.py", "--new", "app/x.py"])


def test_the_cli_refuses_a_path_it_cannot_read_as_one_python_file(monkeypatch):
    """A missing or directory ``--new`` under ``--worktree``, a directory read from a ref and a file that does
    not parse each stop the CLI with a message naming the path (exit status 1), never a traceback or an OK."""
    monkeypatch.setattr(ast_move_proof, "_git_show", lambda ref, path: INDEX)
    for new in ("app/no_such_module.py", "app/services"):
        with pytest.raises(SystemExit, match=f"cannot read {new} in the working tree: not a file"):
            ast_move_proof.main(["--base", "B", "--old", "app/services/index_service.py", "--new", new, "--worktree"])
    monkeypatch.setattr(ast_move_proof, "_git_show", lambda ref, path: "def broken(:\n")
    with pytest.raises(SystemExit, match="cannot parse app/services/index_service.py: "):
        ast_move_proof.main(["--base", "B", "--old", "app/services/index_service.py", "--new", "app/services/index_service.py"])
    for broken, message in (("def broken(:\n", r"invalid syntax \(line 1\)$"),
                            ("x = 1\x00\n", "source code string cannot contain null bytes$")):
        monkeypatch.setattr(ast_move_proof, "_git_show",
                            lambda ref, path, broken=broken: INDEX if path == "app/services/index_service.py" else broken)
        with pytest.raises(SystemExit, match="cannot parse app/services/new_part.py: " + message):
            ast_move_proof.main(["--base", "B", "--old", "app/services/index_service.py", "--new", "app/services/new_part.py"])
    monkeypatch.undo()
    with pytest.raises(SystemExit, match="cannot read backend/app/services at HEAD: a tree, not a file"):
        ast_move_proof._git_show("HEAD", "app/services")
    with pytest.raises(SystemExit, match="cannot read backend/app/no_such_module.py at HEAD: fatal: "):
        ast_move_proof._git_show("HEAD", "app/no_such_module.py")


def test_the_cli_reads_a_source_as_python_decodes_it_and_refuses_bytes_it_cannot(monkeypatch, tmp_path):
    """A file is read as Python reads it, its coding declaration honoured; bytes that are no text in its
    encoding stop the CLI with a message naming the file, exit status 1, never a traceback."""
    monkeypatch.setattr(ast_move_proof, "BACKEND_DIR", tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "latin.py").write_bytes(b"# -*- coding: latin-1 -*-\nNAME = 'caf\xe9'\n")
    assert ast_move_proof._worktree("app/latin.py").endswith("NAME = 'caf\u00e9'\n")
    (tmp_path / "app" / "bad.py").write_bytes(b"NAME = 'caf\xe9'\n")
    with pytest.raises(SystemExit, match="cannot read app/bad.py in the working tree: not Python source text"):
        ast_move_proof._worktree("app/bad.py")


def test_an_honest_split_that_keeps_what_reads_its_module_in_place_is_not_relocated():
    """The control. The logger stays on the old path, the moved helpers read ordinary names and import a
    sibling relatively within the same package, and the moved module compiles as before: nothing changes."""
    old = ("from __future__ import annotations\nimport logging\n\nlogger = logging.getLogger(__name__)\n\n\n"
           "def clean(text: str) -> str:\n    from .text import strip\n    return strip(text)\n\n\n"
           "def run(text: str) -> str:\n    logger.info('run')\n    return clean(text)\n")
    facade = ("from __future__ import annotations\nimport logging\n\nfrom app.services.helpers import clean\n\n"
              "logger = logging.getLogger(__name__)\n\n\ndef run(text: str) -> str:\n    logger.info('run')\n"
              "    return clean(text)\n")
    helpers = "from __future__ import annotations\n\n\ndef clean(text: str) -> str:\n    from .text import strip\n    return strip(text)\n"
    report = compare(old, {"app/services/x.py": facade, "app/services/helpers.py": helpers}, old_path="app/services/x.py")
    assert report.ok, render(report)
    assert report.relocated == {} and report.moved == 3


def test_an_added_import_time_side_effect_fails_until_disclosed():
    files = _move(**{"app/x/helpers.py": HELPERS + "\nsettings.STRICT = False\nregister(clip)\n"})
    report = _facade(files)
    assert not report.ok
    assert report.side_effects == {"effect:settings.STRICT": "app/x/helpers.py",
                                   "expr:register(clip)": "app/x/helpers.py"}
    disclosed = _facade(files, frozenset({"effect:settings.STRICT", "expr:register(clip)"}))
    assert disclosed.ok
    assert disclosed.allowed == {"effect:settings.STRICT": "added in app/x/helpers.py",
                                 "expr:register(clip)": "added in app/x/helpers.py"}


def test_an_allowed_change_still_prints_its_diff():
    report = _facade(_move(**{"app/x/helpers.py": HELPERS.replace("LIMIT = 8_000", "LIMIT = 9_000")}),
                     frozenset({"LIMIT"}))
    assert report.ok
    rendered = render(report)
    assert "ALLOWED    LIMIT (disclosed delta)" in rendered
    assert "-LIMIT = 8000" in rendered and "+LIMIT = 9000" in rendered


def test_the_one_line_limit_rests_on_ruff_rejecting_two_statements_on_a_line():
    """The proof orders statements by the line they start on, so two on one line are outside it (Limits): a
    ``del`` beside a binding, or a read beside a ``del``, may come before it or after it. Ruff's E702 (``;``) and
    E701 (a body on its header's line), selected for every file under ``backend/`` and ignored for none, keep
    such lines out of the code the proof reads."""
    lint = tomllib.loads((Path(__file__).parents[2] / "ruff.toml").read_text())["lint"]

    def covers(rules: list[str], code: str) -> bool:
        return any(rule == "ALL" or code.startswith(rule) for rule in rules)

    selected = [*lint["select"], *lint.get("extend-select", [])]
    ignored = [*lint.get("ignore", []), *lint.get("extend-ignore", []),
               *(rule for key in ("per-file-ignores", "extend-per-file-ignores")
                 for rules in lint.get(key, {}).values() for rule in rules)]
    for code in ("E701", "E702"):
        assert covers(selected, code) and not covers(ignored, code), code
