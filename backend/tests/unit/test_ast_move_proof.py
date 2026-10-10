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
in the class body for a new class member) or a dunder that Python reads itself where moved code lives (a
module's ``__all__`` aside), a symbol of the target file that moved code reads at import above it or
rebinds, a class docstring that no longer opens its body, a reordered symbol, and a moved symbol that reads
what its new module changes (its name, package, file or docstring, a relative import's target, its
namespace, whether its annotations are postponed, or a module dunder it binds) each fail; a disclosed delta
passes with its diff shown.
"""
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
    files = {"app/x.py": FACADE + "\nimport logging\n\nlogger = logging.getLogger(__name__)\n",
             "app/x/helpers.py": HELPERS, "app/x/service.py": SERVICE}
    files.update(overrides)
    return files


def _facade(new: dict[str, str], allow: frozenset[str] = frozenset()) -> Report:
    """``compare`` for OLD, which lived where the façade now does: its ``logger`` stays in ``app/x.py``, so
    the logger keeps its name, and a moved symbol that read where its module lives would be RELOCATED."""
    return compare(OLD, new, allow, old_path="app/x.py")


def test_an_honest_move_passes_and_ignores_formatting_comments_and_imports():
    report = _facade(_move())
    assert report.ok, render(report)
    # logger, LIMIT, clip, Service (its header), and its docstring, retries and run members
    assert report.moved == 7
    assert report.added == {"__all__": "app/x.py"}


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
    assert report.duplicate == {"logger": ["app/x.py", "app/x/service.py"]}
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
    assert report.shadows == {"Box.make": "app/x.py: binds make, read by Box.x"}
    module = compare(old, {"app/x.py": "make = Base = registry\n\n" + old})
    assert module.shadows == {"make,Base": "app/x.py: binds Base, read by Box; binds make, read by Box.run, Box.x"}


def test_an_honest_split_adds_names_without_shadowing_any():
    """The control. A new name shadows only what the OLD symbols of its own file take from its own
    namespace: a parameter, a local or a comprehension variable is not the module's name, an attribute is
    not a name, a method body does not see a class member, and another file has its own namespace. New
    code may read new names, and a disclosed change that starts calling a new helper never read it before."""
    box = "class Box:\n    def run(self):\n        return self.make() + rows\n"
    scoped = ("def local(make):\n    return make()\n\n\n"
              "def bound():\n    make = rows[0]\n    return [make for make in rows]\n\n\n")
    reader = "X = make()\n"
    added = ("\nmake = registry\n"
             "\ndef _trim(value):\n    return value.strip()\n"
             "\ndef _clean(value):\n    return _trim(value)\n")
    report = compare("from helpers import make, rows\n\n\n" + scoped + box + reader,
                     {"app/x/a.py": "from helpers import rows\n\n\n" + scoped + box + "    rows = ()\n" + added,
                      "app/x/b.py": "from helpers import make\n\n" + reader})
    assert report.ok, render(report)
    assert report.added == dict.fromkeys(("make", "_trim", "_clean", "Box.rows"), "app/x/a.py")
    helpers = HELPERS.replace("return text[:LIMIT]", "return _trim(text)[:LIMIT]") + "\ndef _trim(value):\n    return value\n"
    calling = _facade(_move(**{"app/x/helpers.py": helpers}), frozenset({"clip"}))
    assert calling.ok, render(calling)  # clip's printed diff is the disclosure
    assert calling.added == {"__all__": "app/x.py", "_trim": "app/x/helpers.py"}


def _added_at_module_level(old: str) -> str:
    """What the proof says of ``make = registry`` added above ``old``: its SHADOWS reason, or "" when ADDED."""
    report = compare(old, {"app/x.py": "make = registry\n\n" + old})
    assert report.ok == (report.added == {"make": "app/x.py"}), render(report)
    return report.shadows.get("make", "").removeprefix("app/x.py: binds make, ")


def _added_to_box(old: str, *names: str) -> str:
    """What the proof says of a new first member of ``class Box`` that binds ``names``: its SHADOWS reason."""
    assert old.startswith("class Box:\n")
    member = " = ".join(names) + " = 0"
    report = compare(old, {"app/x.py": old.replace("class Box:\n", f"class Box:\n    {member}\n", 1)})
    return report.shadows.get("Box." + ",".join(names), "").removeprefix("app/x.py: ")


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
    body."""
    target = "cache = {}\n"
    for reader, key in (("def reset():\n    global cache\n    cache = {}\n", "reset"),
                        ("for cache in ROWS:\n    pass\n", "guard:for cache in ROWS"),
                        ("class Box:\n    def reset(self):\n        global cache\n        cache = {}\n", "Box.reset"),
                        # A class body's ``global`` and its store are two members: the declaration counts.
                        ("class Box:\n    global cache\n    cache = {}\n", "Box.expr:global cache")):
        old = "from app.b import cache\n\n" + reader
        report = compare(old, {"app/a.py": "", "app/b.py": target + "\n\n" + reader}, old_path="app/a.py")
        assert report.shadows == {"cache": f"app/b.py: binds cache, bound by {key}"}, reader
    # A read below the binding stays exempt, a ``global`` that is only read included: it binds nothing.
    for reads in ("def size():\n    return len(cache)\n", "def size():\n    global cache\n    return len(cache)\n"):
        report = compare("from app.b import cache\n\n" + reads, {"app/a.py": "", "app/b.py": target + "\n\n" + reads},
                         old_path="app/a.py")
        assert report.ok, render(report)

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


def test_a_new_dunder_member_of_a_moved_class_is_read_by_python_itself():
    """No moved code loads ``__slots__``, yet creating the class reads it: the moved class's instances lose
    their ``__dict__``. It runs nothing at import, and it printed ``pure move: OK`` before the rule."""
    moved = "class Moved:\n    x = 1\n"
    slots = compare(moved, {"app/x.py": moved.replace("    x = 1", "    __slots__ = ()\n    x = 1")})
    assert not slots.ok
    assert slots.shadows == {"Moved.__slots__": "app/x.py: binds __slots__, read by Python itself"}


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
    assert report.moved == 2 and report.added == {"Moved.y": "app/x.py"}  # the docstring and x, unchanged
    for above in ("    import os\n", "    x = 1\n"):
        displaced = old.replace("    x = 1\n", "").replace('    """Doc."""', above + '    """Doc."""')
        assert "Moved" in compare(old, {"app/x.py": displaced}).changed, above
    assert "Moved" in compare(old, {"app/x.py": old.replace('    """Doc."""', '    if FLAG:\n        """Doc."""')}).changed
    only = 'class NotFound(Exception):\n    """Raised."""\n'
    assert list(compare(only, {"app/x.py": only.replace("    ", "    status = 404\n    ", 1)}).changed) == ["NotFound"]
    ellipsis = "class Proto:\n    ...\n    x = 1\n"
    assert compare(ellipsis, {"app/x.py": ellipsis.replace("    ...", "    y = 0\n    ...")}).ok
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
    assert report.added == {"__all__": "app/x.py", **dict.fromkeys(members, "app/x/helpers.py")}


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
    lazy = compare(size, {"app/x.py": size, "app/x/lazy.py": "def __getattr__(name):\n    return name\n"})
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


def test_a_name_a_module_binds_itself_is_compared_as_that_binding():
    """A name that a symbol of each module binds is compared as those symbols, so ``NAME`` moved with its
    ``__name__`` binding reads what it read; with the binding left behind it reads the new module's
    derived name. Each copy of a DUPLICATE away from the old path is DUPLICATE only."""
    old = "__name__ = 'legacy'\nNAME = __name__\n"
    both = compare(old, {"app/x.py": "", "app/y.py": old}, old_path="app/x.py")
    assert both.relocated == {"__name__": "app/y.py, was app/x.py: binds __name__, which Python reads from app.y, was app.x"}
    left = compare(old, {"app/x.py": "__name__ = 'legacy'\n", "app/y.py": "NAME = __name__\n"}, old_path="app/x.py")
    assert left.relocated == {"NAME": "app/y.py, was app/x.py: reads __name__ (the old module bound it)"}
    twice = compare("NAME = __name__\n", {"app/x.py": "", "app/y.py": "NAME = __name__\n", "app/z.py": "NAME = __name__\n"},
                    old_path="app/x.py")
    assert twice.duplicate == {"NAME": ["app/y.py", "app/z.py"]} and twice.relocated == {}


def test_a_binding_settles_a_name_only_when_it_sets_it_outright_above_the_read():
    """``__doc__ +=`` and ``__doc__.format()`` keep the docstring they read, the ``__package__`` shim binds
    only when the package is empty, a bare annotation binds nothing and a walrus in an empty comprehension never
    runs, and code above ``__doc__ = ...`` may read the docstring: a statement at import, or a def called
    there before the binding runs, a symbol's first definition included. Each still reads what the new module
    derives. Below the first binding the binding is the value, and a ``global`` store sets it outright too (its
    def is compared as a symbol)."""
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
    for binding in ("__doc__: str", '[(__doc__ := "x") for _ in ()]'):
        tentative = f'"""Old."""\n{binding}\nTEXT = __doc__\n'
        assert _relocated(tentative, "app/x.py", "app/x.py", tentative.replace("Old.", "New.")) == {
            "TEXT": "reads __doc__ (the module docstring differs)"}, binding


def test_a_class_body_read_is_settled_by_an_earlier_member_that_sets_the_name_outright():
    """A class body looks a name up in the class first, so a member that reads ``__module__`` or ``__doc__``
    after a member set it outright reads that value wherever the class moves. A read above it, a binding in
    a block, one derived from the module's value, and a lambda's read (a nested scope reads the module's) still
    take what the new module derives."""
    old = ('"""Old."""\n\n\nclass C:\n    __module__ = "stable"\n    origin = __module__\n\n\n'
           'class D:\n    origin = __module__\n    __module__ = "stable"\n\n\n'
           'class E:\n    if READY:\n        __module__ = "stable"\n    origin = __module__\n\n\n'
           'class F:\n    __doc__ = "Fixed."\n    usage = __doc__\n    both = (__doc__, (lambda: __doc__)())\n\n\n'
           'class K:\n    __doc__ = __doc__ + "!"\n    usage = __doc__\n')
    assert _relocated(old, "app/y.py", "app/x.py", old.replace("Old.", "New.")) == {
        "D.origin": "reads __module__ (app.y, was app.x)", "E.origin": "reads __module__ (app.y, was app.x)",
        "F.both": "reads __doc__ (the module docstring differs)", "K.__doc__": "reads __doc__ (the module docstring differs)",
        "K.usage": "reads __doc__ (the module docstring differs)"}


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
    block in its body; an undocumented class body falls through to the module's, past any enclosing class."""
    old = ('"""Old."""\n\n\nclass Plain:\n    usage = __doc__\n\n\nclass Cli:\n    """Cli."""\n    if __doc__:\n        usage = 1\n\n\n'
           'class Job:\n    class Options:\n        """Scan."""\n        help = __doc__\n\n\n'
           'def build():\n    class Command:\n        """Backfill."""\n        help = __doc__\n    return Command\n\n\n'
           "class Outer:\n    class Inner:\n        help = __doc__\n")
    assert _relocated(old, "app/x.py", "app/x.py", old.replace("Old.", "New.")) == {
        "Plain.usage": "reads __doc__ (the module docstring differs)",
        "Outer.Inner": "reads __doc__ (the module docstring differs)"}


def test_a_block_reads_its_header_and_a_class_its_body_imports():
    """A block reads where its module lives through its header only (a ``__main__`` guard moved away no longer
    runs under ``python -m``), whichever header it is (a test, a context, an iterable or target, a handled
    exception) and a namespace call there too; its statements are symbols of their own, a def in it included.
    A relative import directly in a class body is in no member's text, so the class reports it."""
    old = ("if __name__ == '__main__':\n    main()\n\nif READY:\n    PATH = __file__\n\n    def load():\n"
           "        from . import h\n        return h\n\n\nclass Loader:\n    from . import h\n")
    assert _relocated(old, "app/services/sub/y.py") == {
        "guard:if __name__ == '__main__'": "reads __name__ (app.services.sub.y, was app.services.x)",
        "PATH": "reads __file__ (another file)",
        "load": "imports h from . (app.services.sub, was app.services)",
        "Loader": "imports h from . (app.services.sub, was app.services)"}
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
    its module keeps all three. ``x.py`` to ``x/__init__.py`` keeps the name a module dunder is read under, but
    not the namespace, which gains ``__path__`` and another ``__file__``, either way."""
    old = ("def lookup(name):\n    return globals()[name]\n\n\ndef run(src):\n    return eval(src)\n\n\n"
           "def scoped(src, ns):\n    return eval(src, ns)\n\n\ndef total(rows: list) -> int:\n    return len(rows)\n\n\n"
           "def plain(rows):\n    return rows\n\n\nclass Row:\n    key: str\n\n    def size(self) -> int:\n        return 0\n\n\n"
           "def __getattr__(name):\n    return name\n")
    moved = _relocated(old, "app/x/impl.py", "app/x.py", "from __future__ import annotations\n\n" + old)
    assert moved == {
        "lookup": "reads its module's namespace through globals() (app.x.impl, was app.x)",
        "run": "reads its module's namespace through eval() (app.x.impl, was app.x)",
        "total": "its annotations are postponed now (from __future__ import annotations), evaluated before",
        "Row": "its annotations are postponed now (from __future__ import annotations), evaluated before",
        "__getattr__": "binds __getattr__, which Python reads from app.x.impl, was app.x"}
    assert _relocated(old, "app/x.py", "app/x.py") == {}
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
    namespace once moved; below the first binding, the call is the module's ``eval``. A binding that may not
    happen (in a block or a ``match``, a bare annotation, a walrus, or one deleted later) leaves the builtin. A
    class body looks the name up in the class first, a block in it too: an ``eval`` its class bound above for
    certain is the class's, but a method's body, or a call above that binding, reaches the builtin."""
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
                    "eval: object", "[(eval := fake) for _ in ()]", "match FLAG:\n    case True:\n        eval = fake"):
        uncertain = f'def fake(src):\n    return "fake"\n\n\n{binding}\nRESULT = eval("__name__")\n'
        moved = compare(uncertain, {"app/x.py": uncertain.replace('RESULT = eval("__name__")\n', ""),
                                    "app/y.py": 'RESULT = eval("__name__")\n'}, old_path="app/x.py")
        assert moved.relocated == {"RESULT": f"app/y.py, was app/x.py: {namespace}"}, binding


def test_module_is_a_class_bodys_only():
    """A class body binds ``__module__`` before it runs, a nested one in a def too; anywhere else the name is
    unbound before the move and after it (NameError), a method's body included."""
    old = ("def where():\n    return __module__\n\n\nclass Box:\n    origin = __module__\n\n    def own(self):\n"
           "        return __module__\n\n\ndef build():\n    class Inner:\n        origin = __module__\n    return Inner\n")
    assert _relocated(old, "app/y.py", "app/x.py") == {
        "Box.origin": "reads __module__ (app.y, was app.x)", "build": "reads __module__ (app.y, was app.x)"}


def test_only_annotations_python_evaluates_and_code_compiled_under_the_future_import_count():
    """Each form alone, moved into a module that postpones annotations: a parameter (``*args`` and ``**kwargs``
    too), a return, an async def's, a class field, a class built in a def and a nested def's parameter. Code
    handed to the builtin ``exec`` or ``compile`` inherits the caller's ``from __future__`` imports unless told
    ``dont_inherit``, with a reason of its own, both ways; an imported ``compile`` is not the builtin. An
    annotation in a def's body, ``self.calls: list[str] = []`` included, is never evaluated."""
    old = ("def param(rows: list):\n    return rows\n\n\ndef ret(rows) -> list:\n    return rows\n\n\n"
           "class Field:\n    key: str\n\n\ndef local(rows):\n    count: Undefined = len(rows)\n    return count\n\n\n"
           "class Fake:\n    def __init__(self):\n        self.calls: list[str] = []\n\n\n"
           "def factory():\n    class Row:\n        key: Later\n    return Row\n\n\n"
           "def nested():\n    def inner(x: Later):\n        return x\n    return inner\n\n\n"
           "def make(src, ns):\n    exec(src, {}, ns)\n\n\ndef build(src):\n    return compile(src, '<generated>', 'exec')\n\n\n"
           "def isolated(src):\n    return compile(src, '<generated>', 'exec', dont_inherit=True)\n\n\n"
           "def apart(src):\n    return compile(src, '<generated>', 'exec', 0, True)\n\n\n"
           "async def fetch(row: Row) -> Row:\n    return row\n\n\ndef merge(*rows: Row):\n    return rows\n\n\n"
           "def extra(**rows: Row):\n    return rows\n")
    future = "from __future__ import annotations\n\n"
    postponed = "its annotations are postponed now (from __future__ import annotations), evaluated before"
    compiled = "the code it compiles (exec, compile) inherits from __future__ import annotations now, not before"
    assert _relocated(old, "app/x/impl.py", "app/x.py", future + old) == {
        **dict.fromkeys(("param", "ret", "Field", "factory", "nested", "fetch", "merge", "extra"), postponed),
        **dict.fromkeys(("make", "build"), compiled)}
    back = _relocated(future + old, "app/x/impl.py", "app/x.py", old)
    assert back["param"] == "its annotations are evaluated now, postponed before"
    assert back["make"] == "the code it compiles (exec, compile) no longer inherits from __future__ import annotations"
    imported = 'from re import compile\n\n\ndef pattern():\n    return compile(r"\\d+")\n'
    assert _relocated(imported, "app/x/impl.py", "app/x.py", future + imported) == {}


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
