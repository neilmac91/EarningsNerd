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
module's ``__all__`` aside), a class docstring that no longer opens its body, and a reordered symbol each
fail; a disclosed delta passes with its diff shown.
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
    calling = compare(OLD, _move(**{"app/x/helpers.py": helpers}), frozenset({"clip"}))
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
    read it: a new member placed above an old class's docstring makes it None, with every member's text
    unchanged. The header carries the docstring, so whatever now precedes it (a new member, an import, an
    old member) changes the header, and so does a docstring added to a class that had none."""
    old = 'class Moved:\n    """Doc."""\n    x = 1\n'
    report = compare(old, {"app/x.py": old.replace('    """Doc."""', '    y = 0\n    """Doc."""')})
    assert not report.ok
    assert list(report.changed) == ["Moved"]
    assert '-    """Doc."""\n+    pass' in report.changed["Moved"]
    assert report.moved == 2 and report.added == {"Moved.y": "app/x.py"}  # the docstring and x, unchanged
    for above in ("    import os\n", "    x = 1\n"):
        displaced = old.replace("    x = 1\n", "").replace('    """Doc."""', above + '    """Doc."""')
        assert "Moved" in compare(old, {"app/x.py": displaced}).changed, above
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
    report = compare(OLD, _move(**{"app/x/helpers.py": HELPERS + cache}))
    assert report.ok, render(report)
    members = ("_Cache", "_Cache.expr:'Docstring.'", "_Cache.__slots__", "_Cache.__init__", "_Cache.__eq__")
    assert report.added == {"__all__": "app/x.py", **dict.fromkeys(members, "app/x/helpers.py")}


def test_every_dunder_counts_where_moved_code_lives_and_only_there():
    """One case per rule. Every dunder counts, a def or one that a library reads, at module level and in an
    old class, ``__all__`` included in a class; a dunder the moved code also names lists both readers. A
    module's ``__all__`` is exempt from Python's read only, a file with no old symbol holds no moved code,
    and a class-private ``__name``, a ``name__`` and the throwaway ``__`` are no dunders."""
    size = "def size(rows):\n    return len(rows)\n"
    for new, key in (("def __getattr__(name):\n    return name\n", "__getattr__"),
                     ("__package__ = 'app'\n", "__package__")):
        assert compare(size, {"app/x.py": size + new}).shadows == {
            key: f"app/x.py: binds {key}, read by Python itself"}, new
    moved = "class Moved:\n    x = 1\n"
    for new, name in (("def __init__(self):\n        pass", "__init__"), ("__tablename__ = 'rows'", "__tablename__"),
                      ("def __init_subclass__(cls):\n        pass", "__init_subclass__"), ("__all__ = ()", "__all__")):
        report = compare(moved, {"app/x.py": moved + f"\n    {new}\n"})
        assert report.shadows == {f"Moved.{name}": f"app/x.py: binds {name}, read by Python itself"}, new
    named = compare("NAME = __name__\n", {"app/x.py": "__name__ = 'app'\nNAME = __name__\n"})
    assert named.shadows == {"__name__": "app/x.py: binds __name__, read by Python itself, NAME"}
    assert compare(size, {"app/x.py": "__all__ = ['size']\n\n" + size}).added == {"__all__": "app/x.py"}
    listed = "def names():\n    return __all__\n"
    assert compare(listed, {"app/x.py": "__all__ = []\n\n" + listed}).shadows == {
        "__all__": "app/x.py: binds __all__, read by names"}
    lazy = compare(size, {"app/x.py": size, "app/x/lazy.py": "def __getattr__(name):\n    return name\n"})
    assert lazy.ok and lazy.added == {"__getattr__": "app/x/lazy.py"}
    plain = compare(size, {"app/x.py": size + "\n__cache = {}\ncache__ = {}\n__ = 0\n"})
    assert plain.ok and set(plain.added) == {"__cache", "cache__", "__"}


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
