"""AST per-symbol proof that a refactor PR only MOVES code (``lessons/test-pure-move-ast-proof.md``).

A "pure move" claim is a proof, not an assertion: parse the old file and every new file, normalise
each symbol with ``ast.unparse`` (formatting and comments stop mattering; every token of code and
every docstring still counts), and diff per symbol name. Run it from ``backend/`` on COMMITTED state
(``lessons/test-proofs-run-on-committed-state.md``), with paths relative to ``backend/``::

    python -m tests.support.ast_move_proof --base origin/main \\
        --old app/services/facts_service.py \\
        --new app/services/facts_service.py app/services/facts/concepts.py app/services/facts/transport.py

The old file is read from ``--base`` (a git ref) and the new files from ``--head`` (default ``HEAD``),
or from the working tree with ``--worktree``. A symbol is a module-level function, class (its header:
decorators, bases, keywords and docstring, which Python takes as ``__doc__`` only from the first statement
of the body, so a member or an import placed above it changes the header), class member (method or class
attribute, keyed ``Class.member``), assignment (keyed by its target names; one that sets an attribute or
item, such as ``settings.FLAG = False``, keys as ``effect:<target>``) or other module-level expression
statement (``expr:<text>``). Statements inside module-level ``if``/``try``/``with``/``for``/``while`` blocks are
read as module-level, and each such block is a symbol of its own as well, whatever its body holds (its
header runs at import: ``if register(): import plugin`` calls, and ``while True: pass`` never finishes):
keyed by the condition it runs under (``guard:<test, iterable, context or handled exceptions>``, or
``Class.guard:…`` in a class body), its text is the whole block with its imports dropped, so changing a
condition or an exception type, or moving a statement into or out of the block, is MISSING or CHANGED.
The one exemption is an ``if TYPE_CHECKING:`` that holds only imports and has no ``else``: its body never
runs. A name bound more than once in one file (a ``try``/``except`` fallback, an ``if``/``else`` pair, a
property and its setter) keeps every definition in source order, so a change to any one of them is
CHANGED. Import statements and module docstrings are not symbols: a move rewrites them by design (code
that reads the docstring is RELOCATED when it differs). A block around imports still is one, so a split that
copies an import fallback into two files discloses a DUPLICATE.

Verdicts: MISSING (defined before, nowhere after), CHANGED (the normalised text differs), DUPLICATE
(defined in more than one new file, e.g. a ``logger`` per sub-module, whose logger NAME changes with the
module), SIDE EFFECT (a NEW symbol that runs code at import, which a move never adds; default deny, at the
statement and the expression level: only a docstring or literal, an assignment of a literal, a name, or a
display of those to plain names, and a def or class whose decorators, defaults and annotations are inert,
is inert. Defaults must be such values; annotations must be bare names or literals unless the module has
``from __future__ import annotations``; class bases must be plain names; a tuple or list of names takes
only a display of as many values, pair by pair, because unpacking anything else iterates it; in a class
body no name may take a bare name, because creating the class calls that value's ``__set_name__``; a def's
or lambda's body runs later and is not read. ``property``, ``staticmethod``, ``classmethod``,
``dataclass`` and the like are inert decorators, and so are ``.setter``, ``.getter`` and ``.deleter`` on a
name that an inert property def above them in the same class body binds, with no statement that runs code
in between; a class keyword such as ``metaclass=`` is not; a call, subscript, attribute read, operator or
unpacking in a value is not), SHADOWS (a NEW symbol that binds a name the OLD symbols of its own new file
use, a dunder that Python reads itself where they live, or a new member of a moved class, which attribute
lookups read; the next two paragraphs), REORDERED (an old
binding that now sits above one it followed in the same new file, every binding of a rebound name
counted: module-level code runs top to bottom, so ``B = A`` above ``A = 1`` raises at import, and
``A = 1; A = 2; B = A`` binds ``B`` to 2 where ``A = 1; B = A; A = 2`` bound it to 1), RELOCATED (an old
symbol that reads what its module gets from where it lives, which its new module changes; the third
paragraph below) and ADDED (other new symbols, which no moved code uses, such as the helpers a split introduces,
or a façade's ``__all__``).

SHADOWS: the old file had no symbol of that key, so the moved code took the name from an import, a builtin
or another binding, and after the move it gets the new one, although the new symbol is inert by itself
(``make = registry`` beside an old ``X = make()``). Names are resolved per namespace, the way the compiler
scopes them. A new module-level symbol shadows a name that old symbols of the same file load from the
module: at module level, in a class body (the lookup falls through to the module until the class has
bound the name) and in the body of a def, lambda or comprehension, which resolves the name when it runs,
unless a parameter or local of that def or of an enclosing one holds it. A new ``Class.member`` shadows a
name that old members of the same class load in the class body itself (a value, a decorator, a default, an
annotation, a block header, a comprehension's first iterable); the body of a method, or of anything else
nested there, never sees the class namespace. Either one also shadows a name that an old symbol of the
same namespace binds, since it rebinds that name for every importer; an old block binds every name
bound in it, its header's targets and its imports included, and a bare annotation (``size: int``) binds
its name here, as it does for the compiler. Order is not read: a def may run after any binding, so a new
binding below the last read at import is reported as well. The old symbol must use the name both before
the move and after it, so a disclosed change that starts calling a new helper is not a shadow, and each
new file is its own namespace: the same binding in a file that holds no user of the name is ADDED, as a
façade's ``__all__`` and a split's helpers are. A new block is not reported here: it is a SIDE EFFECT
already, each statement in it is a symbol of its own, and its key shows what its header binds. The proof
does not know what a new file held before the move, so a symbol the target file already had is new to it,
and one the moved code reads is reported: a same-named helper of the target module is what a move into an
existing module risks. One case is settled from the old file's own imports: when it took the name with a
single plain module-level ``from M import name``, the new file is M itself, and M binds the name nowhere that
no symbol's place shows (by an import, a star import or a new symbol's ``global``: ``_unsettled``, which
moved code below M's def could read first), the moved code keeps the binding it always had, and nothing is
reported unless moved code reads the name at import above that binding (in a statement, a class body, a
decorator, an annotation Python evaluates, which is not one its module postpones, or a comprehension, which
runs where it stands; a generator expression counts too, though it may run later, and so does a lambda
handed to a call, ``sorted(rows, key=lambda row: ...)``, which may call it there): the import ran before the
read, and now the binding runs after it, so the read raises NameError or takes an earlier binding of the
name, or the builtin of that name, ``read above it at import``.
A def's or lambda's body reads it when it runs, so its place alone does not matter, but code that runs at
import above the binding and reaches such a body runs it there: one that loads a name which may hold code
reading it (a def, a lambda, a class whose member does and that member's own name, which the class body may
call where it stands, and so for a name a statement binds in a member class's body or a ``match`` case's class,
from a load or the code it creates, a def whose decorator, default or annotation names one, since what reads its
``__annotations__`` may call it, a name bound from one, through any chain; a reference counts as a call, since
what is done with it is not followed, and so does every name of an annotation Python evaluates that is no lone
name or literal, whose evaluation may run code (a call, a subscript's ``__class_getitem__``, an attribute's
descriptor), but a lone name an annotation evaluates (``-> Report``), which Python stores and never calls,
does not, nor does a property's own accessor, which copies the property), or a def or class created there by
a decorator that is not inert (nor is one whose name the class body around binds, or the module otherwise
than by its standard import) or, for a class, with keywords or a base that is not a builtin class (a name
bound around the class statement, in its class body or the module, or through ``global``, is none), whose
class-creation code may run its methods, and so may a value its body binds, whose ``__set_name__`` creating the
class calls with the class (``_hands_class``: a literal, a lambda, or a def or class whose creation runs no code
is no such value; a bare name, a call's result, or a def or class whose decorator or class keywords or bases
may run code may be, and the member that binds it is reported); a member class's body runs there too,
and so is read for what it creates in turn, as are a ``match`` statement's cases, which are no symbols of their
own (``_definitions``). A dunder there is read by Python itself as well, wherever an old symbol stands above the
binding (the next paragraph). The settlement covers reads only: moved code that rebinds the name, at module
level or through ``global``, rebound the old file's copy and now rebinds the target's, for every importer,
and is reported. A class body is one namespace for ``global``, which the proof reads member by member: the
member that stores or deletes a name its class body declares ``global`` binds the module's name, wherever in
the body the declaration stands, and a declaration alone neither binds nor reads it, but the compiler's own
stores before the body runs, of ``__module__``, ``__qualname__`` and a documented class's docstring as
``__doc__``, bind the module's name where the body declares it ``global`` (``_class_stores``); a method's own
``global`` of its name leaves the method a member of the class.

Python itself reads a dunder name (``__x__``) of a namespace, with no load of it in the code there: a def
or class body created below a module's ``__builtins__`` resolves every builtin through it, a relative
import inside a def goes through ``__package__``, an attribute missing from the module through
``__getattr__``, and creating, comparing or hashing an instance through its class's ``__slots__``,
``__init__``, ``__eq__`` or ``__hash__``. So a new symbol that binds a dunder where moved code lives
shadows it, ``read by Python itself``: at module level when its file holds an old symbol, and in a class
body when the class is an old symbol. Every dunder counts, the ones libraries read included (pydantic's
``__get_validators__``, SQLAlchemy's ``__tablename__``), with one exemption: a module's ``__all__``, which
every façade declares and Python reads only for ``from module import *``. A dunder the old file imported
from the target file itself is settled only below the target's binding: Python reads ``__name__`` (as a
def's or class's ``__module__``) and ``__builtins__`` where it creates code, so an old symbol above the
binding gets the target's value there, ``read above it at import by Python itself``. Any other new member
of a class that is an old symbol is SHADOWS as well, ``read by attribute lookups on`` the class: the proof
does not follow an attribute read, so a new member may override what the class inherited (``self.close()``),
be a hook a library reads (an Enum's ``_missing_``) or a new field of a dataclass or a pydantic model, and a
pure move never adds one. An import in a class body is not a symbol, so a member it binds is outside this
rule (``from os.path import basename as close``); read the import diff. A new class's own members, its dunders included, are ADDED: moved code reaches
them only through the class's name, which SHADOWS reports when the moved code reads it, or a disclosed
change shows when it starts to (a new base on a moved class).

RELOCATED: a moved symbol keeps its text, but not its module, and the import system gives every module names
derived from where it lives. An OLD symbol with one home fails when it reads one of them, before the move and
after it, and its new module changes the value: ``__name__`` (and a class body's ``__module__``, until a
``del`` directly in the body) when the dotted name differs, ``logging.getLogger(__name__)`` among them, or
when ``__name__`` names a module that became or stopped being a package (``x.py`` and ``x/__init__.py``, an
anchor for a relative ``import_module``); ``__package__`` when the package differs; ``__file__``,
``__spec__``, ``__loader__``, ``__cached__`` or a package's ``__path__`` when the file differs, in the same
directory too (fail closed: ``Path(__file__).parent`` stays, ``.stem`` does not); ``__doc__`` when the module
docstring differs, on the same path too, since a façade rewrites it (a documented class, a nested one too,
binds its own before its body runs, until its body deletes it; a nested one that deletes it anywhere binds
none). So does a relative import in its code (a def's body, the class body for a class, a block's own body for
a block) that resolves to another module, against ``__package__``: a module that pins it, with a string bound
outright above the import and never undone (no class's: Python reads the module's own; None, a ``del`` or a
reset through ``global`` derive it from the path again), is settled as below; a call of the builtin
``globals()``, or of ``eval`` or ``exec`` with no globals of their own (none, or ``None``), which now reads
another module's namespace, or another file's (``x.py`` and ``x/__init__.py`` differ in ``__file__`` and
``__path__``; a builtin is a name the module binds nothing under for certain above the calling symbol, an
import included, nor, for a call in a class body itself, its class: a binding in a block or a ``match`` case,
by a bare annotation or ``:=``, or deleted before the call (by a ``del``, in a block or a ``match`` case too,
by an ``except ... as`` handler, by one in a loop from the loop's first line, or through ``global`` in a def
or class at any time; and for a def's body, or a generator expression's past its first iterable, which run
once import is done, by one anywhere below) and not made again, may leave the builtin, as does an import of
another builtin under its name (``len as eval``); and a name bound to a builtin, by an import from
``builtins`` under any name or a binding (an assignment, a display unpacked pairwise, ``:=`` or a parameter's
default) from a name that is the builtin where that binding stands, is that builtin where the binding is seen
(the module's where the code reads the module's name, a class body's in that body, a method's defaults
included, a def's in its own code), as is an attribute of the ``builtins`` module, and a call through ``:=``
calls what it binds; code whose text the move keeps calls what either module's bindings make of its names, so
a builtin found on one side counts, an alias the other side imports included, and a changed symbol what both
do); annotations postponed by ``from __future__ import annotations`` in one module and evaluated in the other
(a def's parameters and return, and an annotated assignment at module level or in a class body, not one in a
def's body, which Python never evaluates; reported once, on the class, for a class's members), and the code it
compiles with the builtin ``eval``, ``exec`` or ``compile``, which inherits the ``from __future__`` imports of
its module that change how Python 3 compiles (``annotations`` and ``barry_as_FLUFL``; the others are no-ops),
whatever globals it runs in, unless ``compile`` is told ``dont_inherit``, when those differ (``eval`` too:
what it compiles holds no annotation, but passes ``annotations`` on to the code it compiles and the lambdas it
makes; fail closed: a code object compiled elsewhere, an AST, inherits nothing); and a module dunder it binds,
at module level or through ``global``, which Python reads from the new module (a moved ``__getattr__`` no
longer serves the façade). A block reads its header here, a ``globals()`` there too, and its own relative
imports; its statements are symbols of their own. A namespace read that stays on its path is reported too when
its module binds other names, imports included (a name moved out without a re-export, a dropped import). A
name that both modules set outright above the reading symbol, at each of its definitions that reads it, and
not deleted since (outside a block or a ``match`` case, not by a bare annotation or ``:=``, from a value that
does not read the name as ``__doc__ +=`` does; a def above the binding may be called at import before it), or
that an earlier member of its class sets so for a read in the class body itself (not a class defined twice,
whose bodies each run in a namespace of their own), is compared as those symbols; one that only one module
sets outright, or binds at all, is reported; otherwise the values the import system derives are compared.
Names are derived from the path relative to ``backend/`` (the CLI normalises how ``--old`` and ``--new`` are
spelled), every directory a package, and without the old path (``compare()``'s ``old_path``, which the CLI
always passes) every read but the docstring's, the annotations' and the ``__future__`` imports compiled code
inherits (all three read from the source) is reported, as ``the old path is unknown`` or
``was an unknown module``. A RELOCATED symbol still counts as identical, as a REORDERED one does, and
``--allow`` takes its key.

Limits. Code that a new class runs through a BASE (an inherited metaclass, or the base's
``__init_subclass__``) is not visible in the AST, so a new class with bases is ADDED; read every ADDED class's
bases. Names are followed only as written. Statements are ordered by the line they start on, so two on one
line (``x = v; del x``, or a body on its header's line) are outside the proof; ruff's E702 and E701, which
``backend/ruff.toml`` selects for every file (a self-test pins it), reject both. A new symbol that loads an
unbound name raises NameError at import, which every test that imports the module, and the app's own startup,
fails on loudly. A name reached through an attribute is not followed, which is why every new member of a
moved class is reported. Code that the target-file settlement finds running at import is followed by name,
so a def reached through a string, a container's item, a hook another module calls (``atexit``, a registry
outside the file) or a module that imports this one while it is still importing is not. Its reach errs toward
a report (fail closed): names are matched across namespaces, a block joins every name it binds when one of
its statements reaches the name (a ``try`` that binds both ``dumps`` and ``BACKEND``), a def whose annotation
names a reaching class holds it though nothing may read its ``__annotations__`` (``HANDLERS = [build]``), a
class member that reads the name its own class body bound above it is taken to read the module's
(``class C: normalize = ...; out = normalize(x)``), an evaluated annotation that is no lone name is taken to
run what it names (``Optional[Report]`` does not), and a decorator that is not inert, or a class base that
is not a builtin class, is taken to run what it is handed (a FastAPI route's decorator does not), and a
class-body binding of a bare name or a call's result is taken to hold a descriptor whose ``__set_name__`` calls
the class (``VALUE = other()`` need not), and so is a def or class there whose creation may run code, and a
class-body statement whose code that runs there names ``locals``, ``vars``, ``exec`` or ``eval`` or a frame
(``len(locals())`` need not).
``--allow`` takes the target's binding, which allows every report on it: list each user in the PR body. Nor
is a name reached through a string (a quoted annotation,
``globals()['name']``, a deletion by ``locals().pop('name')``), a class body's namespace that a function it
calls writes through the caller's frame (class advice through ``sys._getframe(1)``), or that the body reaches
under another spelling than ``_touches_namespace`` reads (an import alias such as ``from builtins import
locals as namespace``, ``builtins.locals()``, an assignment such as ``namespace = locals``, ``getattr``), whose
descriptor's ``__set_name__`` creating the class still calls, a class body's namespace that a metaclass's
``__prepare__`` makes keep other values than the body binds, code Python 3.12 evaluates lazily (a ``type``
alias's value, a type parameter's bound, constraints or default: read where it stands, but evaluated when
first used; Python 3.11, which the backend runs, cannot parse them), a class-private ``__name`` (compared as
written, not mangled), or an import: imports are not symbols, so one that binds a name the moved code reads,
or a dunder, to something else, a new symbol of another new file included, is outside the proof (the one
exception: postponed annotations make annotated moved code RELOCATED); read the import diff. Every moved def
and class takes its new module's name as ``__module__``, and so does every class, ``NewType`` or ``TypeVar``
that a moved call creates (``namedtuple``, ``Enum('Form', ...)``, pydantic's ``create_model``: each reads its
caller's module name), and what is derived from it: its repr, pickling by reference, a dataclass's generated
``__doc__`` when it has none and a field's annotation names a class, a log record's module and path, a
warnings filter keyed by module. A move changes those by design, and a façade's re-export keeps the old path
importing. REORDERED compares the order within each new file only: moved code that runs at import in another
file runs when that file is first imported, which for a façade's sub-module is before the façade's own
statements it followed (a logging level or a warnings filter set above it no longer applies), so read the old
file's import-time statements that a split separates. A moved symbol that reads a name its old module bound
and its new module does not raises NameError, unless the name is also a builtin (``open``, ``eval``), which it
then reaches silently, or it reads the name only in an annotation its module postpones, which fails only where
hints are resolved (pydantic, FastAPI, ``typing.get_type_hints``); read the names a moved symbol takes from
its old module, and every ``TYPE_CHECKING`` import a new file adds for moved code. A globals argument that is
a name or another expression, rather than ``None``, is taken as a namespace of its own, though it may be
``None`` when the code runs. RELOCATED reads old symbols only, so code a PR decomposes into NEW functions is
ADDED and not examined for these reads, and ``vars()``, ``dir()`` or ``locals()`` without arguments at module
level is not followed, nor is a builtin reached any other way (``getattr(builtins, ...)``, ``__builtins__``, a
container, an argument passed in, a binding through ``global`` or as a ``for`` or ``with`` target, or a second
name assigned from the first), and a name bound to a builtin is taken for it wherever the code calls it,
though a later binding in a def may replace it first (fail closed). Provenance is decided per symbol, not per
scope, so a call is taken for the builtin though a nested class's own body binds its name above it, or another
scope of the symbol takes the name as a parameter or a comprehension target or reads it in a class body; and a
``compile`` whose result cannot carry ``annotations`` (``ast.PyCF_ONLY_AST``, an ``'eval'`` compile handed
straight to ``eval``) is reported when only that import differs (both fail closed). A read below a
module-level ``del`` of one of the names a module gets from where it lives falls through to ``builtins``, the
same in every module, yet is reported (fail closed). A new annotated assignment writes its namespace's
``__annotations__`` without binding that name, so moved code that reads the dict, at module level too, sees
one more key. And the names these rules trust (``property``, ``dataclass``, ``TYPE_CHECKING`` and the like)
are taken at their word by SIDE EFFECT and the exemptions, so a move that rebinds one where no moved symbol
reads it, such as an ADDED ``TYPE_CHECKING = True`` above an exempt block, is outside the proof; the
settlement trusts a decorator's name only as the standard library binds it (``_rebound_decorators``).

The exit status is 0 only when nothing is MISSING, CHANGED, DUPLICATE, SIDE EFFECT, SHADOWS, REORDERED or
RELOCATED beyond the symbols passed with ``--allow`` (for SHADOWS, the new symbol's key). A path that is no
file (missing, or a directory, at a ref or in the working tree), bytes that are no source text in the file's
encoding (its coding declaration, or UTF-8) and a file that does not parse stop the CLI with a message naming
it, exit status 1. Each allowed symbol
is a disclosed delta the PR body must list, and what changed is printed with it: its diff (its homes, for a
DUPLICATE), the names it shadows and, for an old symbol with one home, what its new module changes.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import copy
import difflib
import importlib.util
import subprocess
import sys
from collections.abc import Callable, Iterable, Set
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

_COMPOUND = (ast.If, ast.Try, ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While)
if hasattr(ast, "TryStar"):  # Python 3.11+
    _COMPOUND = (*_COMPOUND, ast.TryStar)


def _flatten(body: list[ast.stmt]) -> list[ast.stmt]:
    """Statements at module level, reading through module-level compound blocks."""
    out: list[ast.stmt] = []
    for node in body:
        if isinstance(node, _COMPOUND):
            for name in ("body", "orelse", "finalbody"):
                out.extend(_flatten(getattr(node, name, []) or []))
            for handler in getattr(node, "handlers", []) or []:
                out.extend(_flatten(handler.body))
        else:
            out.append(node)
    return out


def _target_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [n for elt in target.elts for n in _target_names(elt)]
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    return [ast.unparse(target)]


def _deletions(body: list[ast.stmt]) -> dict[str, list[int]]:
    """Where a body (a module's, or a class's) deletes each name as it runs, through blocks and ``match``
    cases, not into a def, a lambda or a class: a ``del``, and an ``except ... as`` handler, which deletes its
    name when it ends. One in a loop counts from the loop's first line, since the loop runs again what stands
    above it."""
    found: dict[str, list[int]] = {}

    def visit(node: ast.AST, loop: int | None) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return
        at = loop if loop is not None else getattr(node, "lineno", 0)
        if isinstance(node, ast.Delete):
            for target in node.targets:
                for name in _target_names(target):
                    found.setdefault(name, []).append(at)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            found.setdefault(node.name, []).append(at)
        if loop is None and isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            loop = node.lineno
        for child in ast.iter_child_nodes(node):
            visit(child, loop)

    for node in body:
        visit(node, None)
    return found


def _certain_bindings(body: list[ast.stmt]) -> dict[str, list[tuple[int, int | None]]]:
    """The names a body (a module's, or a class's) binds for certain as it runs, each with the lines every
    such binding holds between: from each one not in a block or a ``match`` (it may not run), not by a bare
    annotation or ``:=``, to the first deletion of the name after it (``_deletions``; None: never deleted). An
    import from ``builtins`` binds the builtin itself, which shadows only a name it is not (``len as eval``)."""
    deletions = _deletions(body)
    starts: dict[str, list[int]] = {}
    for statement in body:
        if isinstance(statement, (*_COMPOUND, ast.Match, ast.Delete)) or (isinstance(statement, ast.AnnAssign)
                                                                          and statement.value is None):
            continue
        if isinstance(statement, ast.ImportFrom) and statement.module == "builtins" and not statement.level:
            bound = {alias.asname for alias in statement.names if alias.asname not in (None, alias.name)}
        else:
            walrus = {each.target.id for each in ast.walk(statement) if isinstance(each, ast.NamedExpr)}
            bound = _Scope().read(statement).bound - walrus
        for name in bound:
            starts.setdefault(name, []).append(statement.lineno)
    return {name: [(line, min((at for at in deletions.get(name, ()) if at > line), default=None)) for line in lines]
            for name, lines in starts.items()}


def _bound_at(spans: dict[str, list[tuple[int, int | None]]], name: str, line: int) -> bool:
    """Whether a certain binding of ``name`` (``_certain_bindings``) holds at ``line``: one made above it, and
    not deleted since."""
    return any(start < line and (end is None or line < end) for start, end in spans.get(name, ()))


def _scope_nodes(body: list[ast.stmt]) -> list[ast.AST]:
    """Every node a module or class body evaluates in its own namespace: its statements, through blocks,
    handlers and ``match`` cases, and their expressions (a comprehension's ``:=`` binds there too), not into
    a def, a lambda or a class."""
    out: list[ast.AST] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return
        out.append(node)
        for child in ast.iter_child_nodes(node):
            visit(child)

    for node in body:
        visit(node)
    return out


def _is_docstring(node: ast.stmt) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _assignment_key(targets: list[ast.expr]) -> str:
    """Key an assignment by its target names; one that sets an attribute or an item is a side effect."""
    names = [n for t in targets for n in _target_names(t)]
    key = ",".join(names)
    return key if all(n.isidentifier() for n in names) else "effect:" + key


# Decorators that only wrap the function in a descriptor or generate methods: applying one has no effect
# outside the class or module, so a new method or class may carry them. A property's own ``.setter``,
# ``.getter`` and ``.deleter`` are inert too, but only on a property of the same class (``_class_body``).
_INERT_DECORATORS = frozenset({"property", "staticmethod", "classmethod", "cached_property", "abstractmethod",
                               "functools.cached_property", "abc.abstractmethod", "dataclass",
                               "dataclasses.dataclass"})
# The first names those decorators are spelled with, and the module each standard import of one takes it from: a
# builtin's (``property``) is bound by nothing (``_rebound_decorators``).
_TRUSTED_NAMES = frozenset(spelled.split(".")[0] for spelled in _INERT_DECORATORS)
_STANDARD_DECORATORS = {"cached_property": "functools", "abstractmethod": "abc", "dataclass": "dataclasses"}
_ACCESSORS = frozenset({"setter", "getter", "deleter"})
_NAMESPACE_BUILTINS = frozenset({"locals", "vars", "exec", "eval"})
_FRAME_ATTRIBUTES = frozenset({"f_locals", "_getframe", "currentframe"})
_BUILTIN_CLASSES = frozenset(name for name, value in vars(builtins).items() if isinstance(value, type))


def _inert_value(node: ast.expr | None) -> bool:
    """A value whose evaluation runs no code of its own: a literal, a name, a signed number, a tuple or list
    of those, a set or dict keyed by literals, or a lambda (its body runs later) with inert defaults. A
    call, subscript, attribute read, operator, comprehension, f-string or unpacking can run a
    user-defined method (``__getitem__``, ``__iter__``, ``__add__``, ``__getattr__``) at import."""
    if node is None or isinstance(node, (ast.Constant, ast.Name)):
        return True
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, (ast.USub, ast.UAdd)) and isinstance(node.operand, ast.Constant)
    if isinstance(node, (ast.Tuple, ast.List)):
        return all(_inert_value(elt) for elt in node.elts)
    if isinstance(node, ast.Set):
        return all(isinstance(elt, ast.Constant) for elt in node.elts)
    if isinstance(node, ast.Dict):  # a None key is a ** unpacking
        return all(isinstance(key, ast.Constant) for key in node.keys) and all(map(_inert_value, node.values))
    if isinstance(node, ast.Lambda):
        return _inert_arguments(node.args)
    return False


def _annotation(node: ast.expr | None, postponed: bool) -> bool:
    """An annotation runs nothing when the module postpones annotations (``from __future__ import
    annotations``), or when it is a bare name or a literal. Otherwise a subscript runs ``__class_getitem__``,
    an attribute read a module's ``__getattr__`` and a ``|`` union ``__or__``, at import."""
    return postponed or node is None or isinstance(node, (ast.Constant, ast.Name))


def _inert_arguments(args: ast.arguments, postponed: bool = True) -> bool:
    """A def's or lambda's defaults (evaluated at definition) are inert values, and its annotations inert."""
    params = [*args.posonlyargs, *args.args, *args.kwonlyargs, *(a for a in (args.vararg, args.kwarg) if a)]
    defaults = [*args.defaults, *(d for d in args.kw_defaults if d is not None)]
    return all(map(_inert_value, defaults)) and all(_annotation(p.annotation, postponed) for p in params)


def _accessor_receiver(decorator: ast.expr) -> str | None:
    """``name`` for a ``@name.setter``, ``@name.getter`` or ``@name.deleter`` decorator, else None."""
    if isinstance(decorator, ast.Attribute) and decorator.attr in _ACCESSORS and isinstance(decorator.value, ast.Name):
        return decorator.value.id
    return None


def _inert_decorator(decorator: ast.expr, properties: frozenset[str] | None = None) -> bool:
    """Applying a decorator calls it at import; only the descriptor-making ones, with inert arguments, are
    inert, and a property's own accessor, which copies the property: ``@name.setter`` on a name in
    ``properties`` (``_class_body``). ``@registry.setter`` calls whatever ``registry`` is."""
    receiver = _accessor_receiver(decorator)
    if receiver is not None:
        return receiver in (properties or ())
    call = decorator if isinstance(decorator, ast.Call) else None
    if ast.unparse(call.func if call else decorator) not in _INERT_DECORATORS:
        return False
    return call is None or all(_inert_value(arg) for arg in (*call.args, *(kw.value for kw in call.keywords)))


def _class_body(body: list[ast.stmt], postponed: bool) -> list[tuple[ast.stmt, bool, frozenset[str]]]:
    """Each statement of a class body, whether it is ``_inert`` where it stands, and the names bound to a
    property above it, which an accessor needs. A def binds its name to one when its outermost decorator is
    ``property`` or such an accessor and every decorator is inert (``property.setter`` reads the getter's
    ``__doc__`` again). Any other inert statement unbinds the names it binds, and one that runs code may
    rebind any name (``locals()``, ``exec``, a frame), so it unbinds them all."""
    judged: list[tuple[ast.stmt, bool, frozenset[str]]] = []
    properties: frozenset[str] = frozenset()
    for stmt in body:
        inert = _inert(stmt, postponed, properties)
        judged.append((stmt, inert, properties))
        decorators = stmt.decorator_list if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) else []
        makes_property = bool(decorators) and (
            (ast.unparse(decorators[0]) == "property" or _accessor_receiver(decorators[0]) is not None)
            and all(_inert_decorator(decorator, properties) for decorator in decorators))
        properties = properties - _bound_names(stmt) if inert else frozenset()
        if makes_property:
            properties |= {stmt.name}
    return judged


def _bound_names(stmt: ast.stmt) -> frozenset[str]:
    """The names an inert statement binds: a def's or class's name, or an assignment's targets (a bare
    annotation such as ``size: int`` assigns nothing)."""
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return frozenset({stmt.name})
    if isinstance(stmt, ast.Assign):
        return frozenset(name for target in stmt.targets for name in _target_names(target))
    if isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        return frozenset(_target_names(stmt.target))
    return frozenset()


def _inert_binding(target: ast.expr, value: ast.expr | None, in_class: bool) -> bool:
    """Whether binding ``value`` to ``target`` runs no code. A plain name takes any inert value, except, in
    a class body, a bare name: creating the class calls that value's ``__set_name__``. A tuple or list of
    targets takes a tuple or list display of as many values, pair by pair; unpacking anything else
    iterates it (``a, b = pair`` runs ``pair.__iter__``). An attribute or item target is a side effect."""
    if isinstance(target, ast.Name):
        return _inert_value(value) and not (in_class and isinstance(value, ast.Name))
    if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)):
        return len(target.elts) == len(value.elts) and all(
            _inert_binding(elt, item, in_class) for elt, item in zip(target.elts, value.elts))
    return False


def _inert(stmt: ast.stmt, postponed: bool, properties: frozenset[str] | None = None) -> bool:
    """Whether a NEW statement runs no code at import beyond binding names (default deny). Inert: ``pass``,
    a docstring or bare literal, an assignment of an inert value to plain names, and a def or class whose
    decorators, defaults and annotations are inert (a def's body runs later). A class's bases must be plain
    names (they are always evaluated), its body inert too, and a class keyword such as ``metaclass=``
    runs class-creation code. ``postponed``: the module has ``from __future__ import annotations``.
    ``properties``: in a class body, the names bound to a property above ``stmt``; None at module level."""
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr):
        return isinstance(stmt.value, ast.Constant)
    if isinstance(stmt, ast.Assign):
        return all(_inert_binding(target, stmt.value, properties is not None) for target in stmt.targets)
    if isinstance(stmt, ast.AnnAssign):
        return (_annotation(stmt.annotation, postponed)
                and _inert_binding(stmt.target, stmt.value, properties is not None))
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return (all(_inert_decorator(decorator, properties) for decorator in stmt.decorator_list)
                and _inert_arguments(stmt.args, postponed) and _annotation(stmt.returns, postponed))
    if isinstance(stmt, ast.ClassDef):
        return (not stmt.keywords and all(_inert_decorator(decorator, properties) for decorator in stmt.decorator_list)
                and all(isinstance(base, ast.Name) for base in stmt.bases)
                and all(inert for _, inert, _ in _class_body(stmt.body, postponed)))
    return False


def _hands_class(body: list[ast.stmt]) -> bool:
    """Whether a class body may leave a value in its namespace whose ``__set_name__``, which creating the class
    calls with the class itself, may call the class's code: anything an assignment binds that an inert binding
    does not make (``_inert_binding``: a literal, a lambda, a display of them; a bare name is not), and whatever a
    block, an import or ``:=`` binds, and any statement whose code that runs in the class body may change the
    namespace without binding a name (``_touches_namespace``). A def or a class is such a value only where what
    creates it may run code (``_runs_on_creation``), which needs the names around it: a module-level class's
    member is judged by the caller, and a nested class's by ``_creates_code``. ``pass``, any other expression
    statement, ``global`` and ``del`` bind nothing."""
    for stmt in body:
        if _touches_namespace(stmt):
            return True
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Pass, ast.Global, ast.Nonlocal,
                             ast.Delete)):
            continue
        if isinstance(stmt, ast.Expr) and not any(isinstance(each, ast.NamedExpr) for each in ast.walk(stmt)):
            continue
        if isinstance(stmt, ast.Assign) and all(_inert_binding(target, stmt.value, True) for target in stmt.targets):
            continue
        if isinstance(stmt, ast.AnnAssign) and (stmt.value is None or _inert_binding(stmt.target, stmt.value, True)):
            continue
        return True
    return False


def _runs_here(node: ast.AST) -> list[ast.AST]:
    """The nodes of a statement whose code runs in the namespace where it stands: a def's and a lambda's
    decorators, defaults and annotations, and a class's decorators, bases and keywords, but not a def's or a
    lambda's body, which runs later in a namespace of its own, nor a class's body, which runs in its own."""
    found: list[ast.AST] = []
    stack = [node]
    while stack:
        each = stack.pop()
        found.append(each)
        if isinstance(each, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack += [*each.decorator_list, each.args, *([each.returns] if each.returns else [])]
        elif isinstance(each, ast.Lambda):
            stack.append(each.args)
        elif isinstance(each, ast.ClassDef):
            stack += [*each.decorator_list, *each.bases, *each.keywords]
        else:
            stack += ast.iter_child_nodes(each)
    return found


def _touches_namespace(node: ast.AST) -> bool:
    """Whether code that runs where it stands (``_runs_here``) may change that namespace without binding a name:
    through ``locals()`` or ``vars()``, ``exec`` or ``eval``, or a frame (``f_locals``, ``sys._getframe``,
    ``inspect.currentframe``), whether it does so at once (``locals().update(field=Descriptor())``) or keeps the
    namespace for a later call (``def install(ns=locals())``). A def's or a lambda's own ``locals()`` is its
    own. These spellings are all it reads: an alias is not resolved (``from builtins import locals as namespace``,
    ``builtins.locals()``, ``namespace = locals``, ``getattr``), nor is a function that reaches its caller's
    frame by itself (class advice through ``sys._getframe(1)``)."""
    return any(isinstance(each, ast.Name) and each.id in _NAMESPACE_BUILTINS
               or isinstance(each, ast.Attribute) and each.attr in _FRAME_ATTRIBUTES for each in _runs_here(node))


def _class_stores(node: ast.ClassDef) -> set[str]:
    """The names the compiler stores for a class before its body runs: ``__module__``, ``__qualname__`` and, for a
    documented class, its docstring as ``__doc__``. Where the body declares one ``global``, the store binds the
    module's name (``STORE_GLOBAL``), as a member's store of it does."""
    return {"__module__", "__qualname__"} | ({"__doc__"} if _is_docstring(node.body[0]) else set())


def _bound_in(body: list[ast.stmt]) -> set[str]:
    """Every name a module's or a class's body may bind in its own namespace, wherever in it and in whatever
    order: its statements, through blocks, and a ``:=`` in a comprehension or a def's header there; and any name
    a scope inside it binds through ``global``. A def's or lambda's own names and a comprehension's targets are
    not. A star import is not followed: an old file that has one settles no name (``_imported_from``)."""
    scope = _Scope().read(*body)
    return scope.bound | scope.declared()


def _first_name(node: ast.expr) -> str | None:
    """The name an expression starts from: ``dataclasses`` for ``dataclasses.dataclass(frozen=True)``."""
    while isinstance(node, (ast.Call, ast.Attribute)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def _rebound_decorators(body: list[ast.stmt]) -> frozenset[str]:
    """The first names of ``_INERT_DECORATORS`` that a module's body binds otherwise than the standard library
    does at its top (``from dataclasses import dataclass``, ``import functools``): by a def, a class, an
    assignment, another import or one in a block, or ``global``. A builtin's (``property``) is bound by nothing.
    A decorator by such a name is whatever its binding makes it, so it is not inert. A star import is not
    followed: an old file or a target that has one settles no name (``_imported_from``, ``_unsettled``)."""
    rebound = _bound_in([stmt for stmt in body if not isinstance(stmt, (ast.Import, ast.ImportFrom))])
    for stmt in body:
        if not isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        origin = stmt.module if isinstance(stmt, ast.ImportFrom) and not stmt.level else None
        for alias in stmt.names:
            standard = alias.asname in (None, alias.name) and (
                origin is not None and _STANDARD_DECORATORS.get(alias.name) == origin
                if isinstance(stmt, ast.ImportFrom) else alias.name in _STANDARD_DECORATORS.values())
            if not standard:
                rebound.add((alias.asname or alias.name).split(".")[0])
    return frozenset(rebound & _TRUSTED_NAMES)


def _runs_on_creation(node: ast.stmt, properties: frozenset[str] | None, module_names: Set[str], around: Set[str],
                      rebound: Set[str]) -> bool:
    """Whether creating a def or class where it stands may call the module's code by itself: a decorator that is
    not inert (a property's own accessor is, on a name in ``properties``), or a class's keywords or a base that is
    not a builtin class, which run class-creation code (``__init_subclass__``, a metaclass). A base is looked up in
    the namespace around the class statement (``around``, a class body's) and then the module's, so a name either
    binds (``_bound_in``) is not the builtin, and so is a decorator's: one of the names the inert ones are spelled
    with is no longer inert when the class body around binds it, or the module binds it otherwise than the
    standard library does (``rebound``: ``_rebound_decorators``). Only such a def or class can leave a class body a
    value with a ``__set_name__`` (``_hands_class``): a decorator's result, or a class whose metaclass may not be
    ``type``."""
    untrusted = set(rebound) | (set(around) & _TRUSTED_NAMES)
    if not all(_inert_decorator(decorator, properties) and _first_name(decorator) not in untrusted
               for decorator in node.decorator_list):
        return True
    if not isinstance(node, ast.ClassDef):
        return False
    builtin = _BUILTIN_CLASSES - module_names - around
    if node.keywords or not all(isinstance(base, ast.Name) and base.id in builtin for base in node.bases):
        return True
    return False


def _creates_code(node: ast.stmt, properties: frozenset[str] | None, module_names: Set[str], around: Set[str],
                  nested: bool, postponed: bool, rebound: Set[str]) -> bool:
    """Whether creating a def or class where it stands may call the module's code: by itself
    (``_runs_on_creation``), or, for a ``nested`` class, one whose body the proof does not split into symbols (a
    member class, and each class inside one), by what its body creates where it runs, its own bases and
    decorators looked up around it."""
    if _runs_on_creation(node, properties, module_names, around, rebound):
        return True
    if not isinstance(node, ast.ClassDef):
        return False
    if not nested:
        # A module-level class's members are symbols of their own, each handing the class to what it binds
        # (``_Names.hands``), but an import in its body is in no member.
        return any(isinstance(stmt, (ast.Import, ast.ImportFrom)) for stmt in node.body)
    if _hands_class(node.body):
        return True
    inside = _bound_in(node.body)
    judged = {id(stmt): accessors for stmt, _, accessors in _class_body(node.body, postponed)}
    return any(_creates_code(stmt, judged.get(id(stmt), frozenset()), module_names, inside, True, postponed, rebound)
               for stmt in _definitions(node.body))


def _definitions(body: list[ast.stmt]) -> list[ast.stmt]:
    """The defs and classes a body creates where it runs: its statements, read through blocks and ``match``
    cases (which ``_flatten`` keeps whole), not into a def or a class."""
    found: list[ast.stmt] = []
    for stmt in body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.append(stmt)
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                found += _definitions(case.body)
        elif isinstance(stmt, _COMPOUND):
            for name in ("body", "orelse", "finalbody"):
                found += _definitions(getattr(stmt, name, None) or [])
            for handler in getattr(stmt, "handlers", None) or []:
                found += _definitions(handler.body)
    return found


def _postpones_annotations(tree: ast.Module) -> bool:
    """Whether the module has ``from __future__ import annotations``, so no annotation is evaluated."""
    return any(isinstance(node, ast.ImportFrom) and node.module == "__future__"
               and any(alias.name == "annotations" for alias in node.names) for node in tree.body)


def _guards(body: list[ast.stmt]) -> list[ast.stmt]:
    """Every compound block at this level and inside one (never inside a def or class)."""
    out: list[ast.stmt] = []
    for node in body:
        if isinstance(node, _COMPOUND):
            out.append(node)
            for name in ("body", "orelse", "finalbody"):
                out.extend(_guards(getattr(node, name, []) or []))
            for handler in getattr(node, "handlers", []) or []:
                out.extend(_guards(handler.body))
    return out


def _type_checking_imports(node: ast.stmt) -> bool:
    """``if TYPE_CHECKING:`` holding only imports, with no ``else``: the one block that is not a symbol, as its
    body never runs. Any other block's header runs at import, whatever its body holds."""
    return (isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"
            and not node.orelse and all(isinstance(stmt, (ast.Import, ast.ImportFrom)) for stmt in node.body))


def _guard_header(node: ast.stmt) -> str:
    """The condition a block runs under: its test, iterable, context or handled exceptions."""
    if isinstance(node, (ast.If, ast.While)):
        return f"{'if' if isinstance(node, ast.If) else 'while'} {ast.unparse(node.test)}"
    if isinstance(node, (ast.For, ast.AsyncFor)):
        word = "async for" if isinstance(node, ast.AsyncFor) else "for"
        return f"{word} {ast.unparse(node.target)} in {ast.unparse(node.iter)}"
    if isinstance(node, (ast.With, ast.AsyncWith)):
        word = "async with" if isinstance(node, ast.AsyncWith) else "with"
        return f"{word} {', '.join(ast.unparse(item) for item in node.items)}"
    handled = ", ".join((ast.unparse(h.type) if h.type is not None else "everything")
                        + (f" as {h.name}" if h.name else "") for h in node.handlers)
    word = "try" if isinstance(node, ast.Try) else "try*"
    return f"{word} except {handled}" + (" else" if node.orelse else "") + (" finally" if node.finalbody else "")


def _guard_header_nodes(node: ast.stmt) -> list[ast.AST]:
    """The expressions a block's header evaluates: its test, iterable and target, contexts, or handled
    exceptions. Its body's statements are symbols of their own."""
    if isinstance(node, (ast.If, ast.While)):
        return [node.test]
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return [node.target, node.iter]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return list(node.items)
    return [handler.type for handler in node.handlers if handler.type is not None]


def _without_imports(node: ast.stmt) -> ast.stmt:
    """A copy of the block with its import statements dropped: a move rewrites imports by design."""
    node = copy.deepcopy(node)
    for inner in ast.walk(node):
        for name in ("body", "orelse", "finalbody"):
            stmts = getattr(inner, name, None)
            if isinstance(stmts, list) and stmts and isinstance(stmts[0], ast.stmt):
                kept = [stmt for stmt in stmts if not isinstance(stmt, (ast.Import, ast.ImportFrom))]
                setattr(inner, name, kept or ([ast.Pass()] if name == "body" else []))
    return node


_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)

# The names a module gets from where it lives (RELOCATED): its dotted name, which a class body also binds as
# ``__module__`` before it runs (anywhere else that name is no module's); its package; its file, which its spec, loader, cached bytecode and a package's search path
# follow; and its docstring.
_FROM_NAME = frozenset({"__name__", "__module__"})
_FROM_FILE = frozenset({"__file__", "__spec__", "__loader__", "__cached__", "__path__"})
_MODULE_IDENTITY = _FROM_NAME | _FROM_FILE | {"__package__", "__doc__"}
# Builtins that read the namespace of the module whose code calls them (``eval`` and ``exec`` without one),
# and the ones that compile code under its ``from __future__`` imports.
_NAMESPACE_CALLS = frozenset({"globals", "eval", "exec"})
_COMPILE_CALLS = frozenset({"eval", "exec", "compile"})
# The ``from __future__`` imports that change how code compiles on Python 3, and so pass to the code a
# module compiles; the rest are no-ops there.
_INHERITED_FUTURES = frozenset({"annotations", "barry_as_FLUFL"})


def _parameters(args: ast.arguments) -> list[ast.arg]:
    return [*args.posonlyargs, *args.args, *args.kwonlyargs, *filter(None, (args.vararg, args.kwarg))]


def _pairs(target: ast.AST, value: ast.expr) -> list[tuple[ast.AST, ast.expr]]:
    """The targets an assignment binds, each with its value: a display unpacked into as many targets pairs
    them one by one (``e, g = eval, globals``)."""
    if (isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List))
            and len(target.elts) == len(value.elts)
            and not any(isinstance(each, ast.Starred) for each in (*target.elts, *value.elts))):
        return [pair for inner, item in zip(target.elts, value.elts) for pair in _pairs(inner, item)]
    return [(target, value)]


def _runs_later(node: ast.AST) -> list[ast.AST]:
    """The parts of a node that run only after it is evaluated: a def's or lambda's body, when it is called,
    and all of a generator expression but its first iterable, when it is consumed."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return list(node.body)
    if isinstance(node, ast.Lambda):
        return [node.body]
    if isinstance(node, ast.GeneratorExp):
        first, *rest = node.generators
        return [node.elt, first.target, *first.ifs, *rest]
    return []


def _builtin_names(nodes: Iterable[ast.AST], builtin_at: Callable[[str, ast.AST], bool],
                   modules: Set[str] = frozenset()) -> tuple[dict[str, set[str]], set[str]]:
    """The names these nodes bind to a builtin, each with the builtins it may be: an import from ``builtins``
    under any name, and a binding (an assignment, a display unpacked pairwise, ``:=`` or a parameter's
    default) from a name that is the builtin where that binding stands (``builtin_at``) or from an attribute
    of the ``builtins`` module (a name in ``modules``, or one imported here); and the names bound to that
    module, ``modules`` among them."""
    nodes = list(nodes)
    modules = set(modules) | {alias.asname or alias.name for each in nodes if isinstance(each, ast.Import)
                              for alias in each.names if alias.name == "builtins"}
    aliases: dict[str, set[str]] = {}
    for each in nodes:
        if isinstance(each, ast.ImportFrom) and each.module == "builtins" and not each.level:
            for alias in each.names:
                aliases.setdefault(alias.asname or alias.name, set()).add(alias.name)
            continue
        if isinstance(each, ast.Assign):
            pairs = [pair for target in each.targets for pair in _pairs(target, each.value)]
        elif isinstance(each, (ast.AnnAssign, ast.NamedExpr)) and each.value is not None:
            pairs = _pairs(each.target, each.value)
        elif isinstance(each, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):  # its parameters' defaults
            positional = [*each.args.posonlyargs, *each.args.args]
            pairs = [*zip(positional[len(positional) - len(each.args.defaults):], each.args.defaults),
                     *((arg, default) for arg, default in zip(each.args.kwonlyargs, each.args.kw_defaults) if default)]
        else:
            continue
        for target, value in pairs:
            if isinstance(value, ast.Name) and value.id in _NAMESPACE_CALLS | _COMPILE_CALLS:
                builtin = value.id if builtin_at(value.id, each) else None
            elif isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name):
                builtin = value.attr if value.value.id in modules else None
            else:
                builtin = None
            if builtin:
                for name in [target.arg] if isinstance(target, ast.arg) else _target_names(target):
                    aliases.setdefault(name, set()).add(builtin)
    return aliases, modules


def _reads_namespace(builtin: str, call: ast.Call) -> bool:
    """Whether a call of that builtin reads the namespace of the module whose code runs it: ``globals()``, and
    ``eval`` or ``exec`` given no globals of their own (none, or ``None``, which CPython takes as the caller's).
    An unpacked positional argument may hold anything, so it counts."""
    if builtin not in _NAMESPACE_CALLS:
        return False
    if builtin == "globals" or any(isinstance(arg, ast.Starred) for arg in call.args):
        return True
    given = call.args[1] if len(call.args) > 1 else next(
        (keyword.value for keyword in call.keywords if keyword.arg == "globals"), None)
    return given is None or (isinstance(given, ast.Constant) and given.value is None)


def _inherits_future(builtin: str, call: ast.Call) -> bool:
    """Whether a call of that builtin compiles code under its caller's ``from __future__`` imports, whatever
    namespace it runs the code in: ``eval`` and ``exec``, and ``compile`` unless its ``dont_inherit`` (the
    fifth argument) is a true constant."""
    if builtin in {"eval", "exec"}:
        return True
    if builtin != "compile":
        return False
    flag = call.args[4] if len(call.args) > 4 else next(
        (keyword.value for keyword in call.keywords if keyword.arg == "dont_inherit"), None)
    return not (isinstance(flag, ast.Constant) and flag.value)


def _annotates(node: ast.AST, in_def: bool = False) -> bool:
    """Whether code holds an annotation that ``from __future__ import annotations`` changes: a def's
    parameters and return, evaluated when the def statement runs, and an annotated assignment at module level
    or in a class body, a class in a def included. One in a def's body (``in_def``) is never evaluated."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.returns or any(param.annotation for param in _parameters(node.args)):
            return True
        return any(_annotates(stmt, in_def=True) for stmt in node.body)
    if isinstance(node, ast.AnnAssign):
        return not in_def
    in_def = in_def and not isinstance(node, ast.ClassDef)  # a class body runs where it stands
    return any(_annotates(child, in_def) for child in ast.iter_child_nodes(node))


class _Scope:
    """One scope of a symbol's code, read the way the compiler scopes names: the names it binds, loads and
    declares ``global``, and the scopes nested in it. A def's decorators, defaults and annotations, a
    class's bases and keywords and a comprehension's first iterable are evaluated in the scope around
    them, and ``:=`` inside a comprehension binds in the scope around it. (``nonlocal`` needs no rule: the
    name belongs to an enclosing def whether or not this scope rebinds it.) A load in an annotation is also
    ``typed`` (any other, ``untyped``), and ``active`` as well in one that is no lone name or literal
    (``_annotation``), whose evaluation may run code; a lambda in a call's callee or arguments is a body that runs
    where the call does, not ``deferred``."""

    def __init__(self, in_class: bool = False, walrus: _Scope | None = None, deferred: bool = False) -> None:
        self.in_class = in_class
        self.deferred = deferred  # a def's or lambda's body, which runs when it is called
        self.bound: set[str] = set()
        self.loaded: set[str] = set()
        self.typed: set[str] = set()  # loaded in an annotation
        self.active: set[str] = set()  # of those, loaded in one that may run code where it is evaluated
        # Loaded anywhere else, but as a def's ``@name.setter``-shaped decorator: a property's own accessor copies
        # the property and calls none of its code, and any other such decorator makes the def ``decorated``.
        self.untyped: set[str] = set()
        self.calling = 0  # inside a call's callee or arguments, which may call a lambda there
        self.annotating = 0  # inside an annotation
        self.acting = 0  # inside one that is no lone name or literal
        self.module: set[str] = set()  # declared ``global``
        self.first: set[str] = set()  # bound before a class body runs: a documented class's ``__doc__``
        self.nested: list[_Scope] = []
        self.walrus = walrus or self
        self.statements: list[ast.stmt] = []  # a class body's own, read one by one for ``held``
        self.annotated = False  # opened inside an annotation (a lambda, a comprehension), which postponing skips

    def _open(self, in_class: bool = False, walrus: _Scope | None = None, deferred: bool = False) -> _Scope:
        self.nested.append(_Scope(in_class, walrus, deferred))
        self.nested[-1].annotated = self.annotating > 0  # ``taken_now`` skips what is nested in it too
        return self.nested[-1]

    def read(self, *nodes: ast.AST | None) -> _Scope:
        for node in nodes:
            if isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    self.loaded.add(node.id)
                    (self.typed if self.annotating else self.untyped).add(node.id)
                    if self.acting:
                        self.active.add(node.id)
                else:
                    self.bound.add(node.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                args = node.args
                params = _parameters(args)
                self.read(*args.defaults, *args.kw_defaults)
                self.annotate(*(param.annotation for param in params))
                # A lambda in a call's callee or arguments may be called there, where the call runs.
                body = self._open(deferred=not (isinstance(node, ast.Lambda) and self.calling))
                body.bound.update(param.arg for param in params)
                if isinstance(node, ast.Lambda):
                    body.read(node.body)
                else:
                    self.bound.add(node.name)
                    for decorator in node.decorator_list:
                        receiver = _accessor_receiver(decorator)
                        if receiver is None:
                            self.read(decorator)
                        else:
                            self.loaded.add(receiver)
                    self.read(*getattr(node, "type_params", ()))
                    self.annotate(node.returns)
                    body.read(*node.body)
            elif isinstance(node, ast.Call):
                self.calling += 1
                self.read(node.func, *node.args, *node.keywords)
                self.calling -= 1
            elif isinstance(node, ast.ClassDef):
                self.bound.add(node.name)
                self.read(*node.decorator_list, *node.bases, *(keyword.value for keyword in node.keywords),
                          *getattr(node, "type_params", ()))
                body = self._open(in_class=True)
                body.statements = node.body
                if _is_docstring(node.body[0]) and "__doc__" not in _deletions(node.body):  # fail closed
                    body.first.add("__doc__")
                body.read(*node.body)
                body.bound |= _class_stores(node) & body.module  # the module's, where the body declares them
            elif isinstance(node, _COMPREHENSIONS):
                first, *rest = node.generators
                self.read(first.iter)
                results = (getattr(node, part, None) for part in ("elt", "key", "value"))
                self._open(walrus=self.walrus).read(first.target, *first.ifs, *rest, *results)
            elif isinstance(node, ast.NamedExpr):
                self.walrus.bound.add(node.target.id)
                self.read(node.value)
            elif isinstance(node, ast.Global):
                self.module.update(node.names)
            elif (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and not node.simple
                  and node.value is None):
                self.annotate(node.annotation)  # ``(x): int`` neither binds x nor reads it
            elif isinstance(node, ast.AnnAssign):
                self.annotate(node.annotation)
                self.read(node.target, node.value)
            elif node is not None:
                if isinstance(node, ast.alias):
                    self.bound.add((node.asname or node.name).split(".")[0])
                elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name:
                    self.bound.add(node.name)
                elif isinstance(node, ast.MatchMapping) and node.rest:
                    self.bound.add(node.rest)
                elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                    self.loaded.add(node.target.id)  # ``x += 1`` reads x before it binds it, and calls its ``__iadd__``
                    self.untyped.add(node.target.id)
                self.read(*ast.iter_child_nodes(node))
        return self

    def annotate(self, *nodes: ast.AST | None) -> _Scope:
        """Read annotations: their loads are ``typed``, which Python evaluates where the code stands unless the
        module postpones annotations. A lone name is then stored, never called; the loads of any other
        annotation are ``active`` too, since evaluating it may run code and hand it those names (a call, a
        subscript's ``__class_getitem__``, an attribute's descriptor: ``_annotation``)."""
        for node in nodes:
            acting = not _annotation(node, postponed=False)
            self.annotating += 1
            self.acting += acting
            self.read(node)
            self.acting -= acting
            self.annotating -= 1
        return self

    def taken(self, enclosing: frozenset[str] = frozenset()) -> set[str]:
        """The names this scope and the scopes nested in it take from the module. A def, lambda or
        comprehension takes each name it loads that neither it nor an enclosing def binds, and each name it
        declares ``global``. A class body also takes the loaded names it binds itself: the lookup falls
        through to the module until the class has bound the name (a documented class binds ``__doc__`` before
        its body runs), and never stops at an enclosing def."""
        if self.in_class:
            taken = {name for name in self.loaded - self.first if name in self.bound or name not in enclosing}
        else:
            taken = self.loaded - self.bound - enclosing
            enclosing = enclosing | self.bound
        return taken.union(self.module, *(scope.taken(enclosing) for scope in self.nested))

    def taken_now(self, postponed: bool, calls: bool = False, enclosing: frozenset[str] = frozenset()) -> set[str]:
        """Of what ``taken`` gives, the names read where they stand, at import, by this scope and the scopes
        nested in it that run there (a comprehension's or a class's body, not a def's), each read as
        ``_Names.evaluated`` reads a symbol's own: no ``global`` declaration, no ``@name.setter``-shaped
        decorator's receiver, and no annotation when the module postpones them, nor a lambda or comprehension in
        one (``annotated``), with what is nested in it. ``calls``: only the names whose code may run there, as
        ``_Names.calls`` reads them, so no lone name an annotation evaluates either."""
        if self.deferred or (postponed and self.annotated):
            return set()
        loads = self.untyped | (set() if postponed else self.active if calls else self.typed)
        if self.in_class:
            taken = {name for name in loads - self.first if name in self.bound or name not in enclosing}
        else:
            taken = loads - self.bound - enclosing
            enclosing = enclosing | self.bound
        return taken.union(*(scope.taken_now(postponed, calls, enclosing) for scope in self.nested))

    def held(self) -> dict[str, set[str]]:
        """The names that the statements of a class body nested in this scope bind, through class bodies only (a
        member class's own body, and the class bodies in it), each with the names its statement takes from the
        module, where it stands or in the code it creates (a def, a lambda, a class), as a symbol's ``here`` and
        ``later`` do. No symbol of the proof's holds them, and the class body may call one where it runs."""
        found: dict[str, set[str]] = {}
        for scope in self.nested:
            if not scope.in_class:
                continue
            for statement in scope.statements:
                each = _Scope().read(statement)
                takes = each.loaded | each.module | set().union(*(inner.taken() for inner in each.nested))
                for name in each.bound:
                    found.setdefault(name, set()).update(takes)
            for name, takes in scope.held().items():
                found.setdefault(name, set()).update(takes)
        return found

    def class_loads(self) -> set[str]:
        """The names the class bodies nested in this scope load where they stand."""
        return set().union(*((scope.loaded if scope.in_class else set()) | scope.class_loads() for scope in self.nested))

    def declared(self) -> set[str]:
        """The module's names this scope and the scopes nested in it bind through ``global``: declared and
        bound (stored or deleted) in the same scope. A ``global`` that is only read binds nothing."""
        return (self.module & self.bound).union(*(scope.declared() for scope in self.nested))


@dataclass
class _Names:
    """What one symbol does with names. ``owner`` is the class whose body holds it (None at module level);
    ``binds`` and ``here`` are the names it binds and loads in that scope; ``later`` are the names its nested
    scopes (the body of a def, lambda, comprehension or nested class) take from the module, ``soon`` the ones
    of those that a comprehension or class body reads where it stands, at import, and ``soon_calls`` the ones
    whose code it may run there, each read as the symbol's own (``_Scope.taken_now``); ``declared`` the
    module's names it or a nested scope binds through ``global``. A ``block`` (a guard) binds whatever is
    bound in it: its header's targets, its imports and its statements' names. ``lines``: where each of its
    definitions starts. For RELOCATED: ``identity``, the names it reads that its module gets from where it
    lives (a block, in its header only, as for ``namespace``; a class member not the ``__doc__`` its
    documented class binds), and ``read_at`` the lines of the definitions that read each (a relative import
    reads ``__package__``); ``relative``, its relative imports as ``(level, module, name)`` (a block's, from
    its header and its own statements, not its nested blocks'); ``namespace``,
    the builtins it calls that read its module's namespace; ``annotated``, whether it holds an annotation
    that ``from __future__ import annotations`` changes (a class's header holds its members'); ``compiles``,
    the builtins it calls that compile code under its module's ``from __future__`` imports; ``tentative``,
    the names it binds only possibly (a bare annotation binds nothing at run time, and ``:=`` may not run);
    ``deletes``, the names it is a ``del`` of; ``decorated``, whether creating it may call its own code: a
    decorator that is not inert is handed the def or class, and a class's keywords or a base that is not a
    builtin class run class-creation code (``__init_subclass__``, a metaclass); for a member class, what its body
    creates counts too (``_creates_code``). For the target-file settlement:
    ``plain`` and ``typed``, the names it loads where it stands outside annotations and in them (a ``global``
    declaration loads nothing), and ``active``, those of ``typed`` in an annotation that may run code where it is
    evaluated; ``postponed``, whether its module postpones annotations; ``class_global``, the names it binds that
    its class body declares ``global``, which are the module's; ``holders``, the names that the statements of
    the class bodies nested in it bind (``_Scope.held``), each with the names its statement takes from the
    module; ``hands``, for a class member that may bind a value with a ``__set_name__`` (``_hands_class``, or a
    def or class that ``_runs_on_creation``), its class, which creating the class hands to that code."""
    owner: str | None
    block: bool = False
    binds: set[str] = field(default_factory=set)
    here: set[str] = field(default_factory=set)
    later: set[str] = field(default_factory=set)
    soon: set[str] = field(default_factory=set)
    soon_calls: set[str] = field(default_factory=set)
    declared: set[str] = field(default_factory=set)
    lines: list[int] = field(default_factory=list)
    identity: set[str] = field(default_factory=set)
    read_at: dict[str, list[int]] = field(default_factory=dict)
    relative: set[tuple[int, str, str]] = field(default_factory=set)
    namespace: set[str] = field(default_factory=set)
    annotated: bool = False
    compiles: set[str] = field(default_factory=set)
    tentative: set[str] = field(default_factory=set)
    deletes: set[str] = field(default_factory=set)
    decorated: bool = False
    plain: set[str] = field(default_factory=set)
    typed: set[str] = field(default_factory=set)
    active: set[str] = field(default_factory=set)
    postponed: bool = False
    class_global: set[str] = field(default_factory=set)
    holders: dict[str, set[str]] = field(default_factory=dict)
    hands: set[str] = field(default_factory=set)

    def reads(self, owner: str | None) -> set[str]:
        """The names of one namespace (a class body, or the module for None) that this symbol reads. What
        a class member loads in its class body is looked up there and then in the module (it falls
        through until the class has bound it); its nested scopes never see the class namespace."""
        if owner is None:
            return self.here | self.later
        return self.here if owner == self.owner else set()

    def bound(self, owner: str | None) -> set[str]:
        """The names of that namespace this symbol binds."""
        return self.binds if owner == self.owner else set()

    def evaluated(self) -> set[str]:
        """The names it reads from the module while the module runs, where it stands or in a nested scope that
        runs there, not later from a def's body: no ``global`` declaration, which reads nothing, no annotation of
        a module that postpones them, which is never evaluated, and no ``@name.setter``-shaped decorator's
        receiver (a property's own accessor reads its class's property; any other makes the def ``decorated``)."""
        return self.plain | (set() if self.postponed else self.typed) | self.soon

    def calls(self) -> set[str]:
        """Of those, the names whose code it may run there: not a lone name an annotation evaluates, which Python
        stores and never calls (code that reads one through ``__annotations__`` reads this symbol's own name
        first), but every name of an annotation that may run code, unless the module postpones annotations, and
        the class it ``hands`` to a value's ``__set_name__``."""
        return self.plain | self.soon_calls | (set() if self.postponed else self.active) | self.hands

    def rebinds(self) -> set[str]:
        """The module's names it binds: at module level, or anywhere through ``global``."""
        return (self.binds if self.owner is None else set()) | self.declared


def symbols(source: str) -> dict[str, str]:
    """Map every symbol the source defines to its normalised (``ast.unparse``) text."""
    return _collect(source)[0]


def _collect(source: str) -> tuple[dict[str, str], list[str], set[str], dict[str, _Names]]:
    """Every symbol's normalised text, every binding occurrence's key in source order (its
    initialisation order: a name bound twice appears twice), the symbols that run code at import (every
    guard, and any symbol with a definition that is not ``_inert`` where it stands: a class member is
    judged in its class body, where a property accessor finds its property), and what each symbol does
    with names (``_Names``)."""
    tree = ast.parse(source)
    postponed = _postpones_annotations(tree)
    found: dict[str, str] = {}
    occurrences: list[tuple[int, int, int, str]] = []
    runs: set[str] = set()
    names: dict[str, _Names] = {}
    # A call by name reaches a builtin unless the module binds that name for certain (an import included) above
    # the symbol that calls it: code that runs at import above the binding still reaches the builtin. A name
    # the module itself binds to a builtin, or an attribute of the ``builtins`` module, is one too.
    # A def or class that deletes a module name through ``global`` (``_deletions``: a ``del``, an ``except ... as``)
    # may run before any call: no binding of it is certain.
    undone = {name for each in ast.walk(tree) if isinstance(each, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
              for name in {name for inner in ast.walk(each) if isinstance(inner, ast.Global) for name in inner.names}
              & set(_deletions(each.body))}
    shadowing = {name: spans for name, spans in _certain_bindings(tree.body).items() if name not in undone}
    module_names = _bound_in(tree.body)
    rebound = _rebound_decorators(tree.body)
    aliases, modules = _builtin_names(_scope_nodes(tree.body),
                                      lambda name, at: not _bound_at(shadowing, name, at.lineno))

    def put(key: str, text: str, node: ast.AST, inert: bool, owner: str | None = None,
            code: ast.AST | None = None, implicit: Set[str] = frozenset(),
            local: dict[str, list[tuple[int, int | None]]] | None = None,
            in_body: tuple[dict[str, set[str]], set[str]] = ({}, set()),
            class_globals: Set[str] = frozenset(), properties: frozenset[str] | None = None,
            around: Set[str] = frozenset()) -> None:
        found[key] = f"{found[key]}\n{text}" if key in found else text  # every definition, in source order
        occurrences.append((node.lineno, node.col_offset, len(occurrences), key))
        if not inert:
            runs.add(key)
        scope = _Scope().read(code or node)
        used = names.setdefault(key, _Names(owner, block=isinstance(node, _COMPOUND)))
        used.binds |= scope.bound
        # ``global x`` in a class body makes x the module's there, so the statement counts as a user of x.
        used.here |= scope.loaded | scope.module
        used.plain |= scope.untyped
        used.typed |= scope.typed
        used.active |= scope.active
        used.postponed = postponed
        used.later |= set().union(*(nested.taken() for nested in scope.nested))
        used.soon |= set().union(*(nested.taken_now(postponed) for nested in scope.nested))
        used.soon_calls |= set().union(*(nested.taken_now(postponed, calls=True) for nested in scope.nested))
        # A ``global`` in a class body holds for the whole body, which the compiler scopes as one namespace and
        # the proof reads member by member: the member that stores or deletes a name the body declares global
        # binds the module's, and a declaration that is only read binds nothing (``class_globals``).
        used.declared |= scope.declared() | (scope.bound & class_globals)
        used.class_global |= scope.bound & class_globals
        for held, takes in scope.held().items():
            used.holders.setdefault(held, set()).update(takes)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # A builtin class base (``Exception``) runs no class-creation code of the module's: its metaclass is
            # ``type`` and its ``__init_subclass__`` object's. A property's accessor on a property above it copies it.
            # A member class's body is no symbol of its own, so what it creates is judged with it.
            used.decorated |= _creates_code(node, properties, module_names, around, owner is not None, postponed,
                                            rebound)
        elif isinstance(node, ast.Match):  # one symbol, whole: what its cases create is judged with it
            used.decorated |= any(_creates_code(stmt, frozenset(), module_names, around, True, postponed, rebound)
                                  for stmt in _definitions([node]))
        used.lines.append(node.lineno)
        # What it reads that its module gets from where it lives. A block reads its header; its body's
        # statements are symbols of their own, and its text drops its imports. In a class body, the names the
        # class still binds itself (``implicit``) are its own.
        head = _Scope().read(*_guard_header_nodes(node)) if used.block else scope
        reads = ((head.loaded | head.module) - (implicit & {"__doc__"})).union(
            *(nested.taken() for nested in head.nested))
        in_class = (head.loaded & implicit if owner else set()) | head.class_loads()  # where ``__module__`` is bound
        identity = reads & _MODULE_IDENTITY - ({"__module__"} - in_class)
        used.identity |= identity
        for name in identity:
            used.read_at.setdefault(name, []).append(node.lineno)
        parts = _guard_header_nodes(node) if used.block else [code or node]
        code_nodes = [each for part in parts for each in ast.walk(part)]
        # A block's own imports are in no symbol's text (its nested blocks are guards of their own); the block
        # reads them. A relative import resolves against ``__package__``.
        own_statements = [each for name in ("body", "orelse", "finalbody") for each in getattr(node, name, None) or []]
        own_statements += [each for handler in getattr(node, "handlers", None) or [] for each in handler.body]
        relative = {(each.level, each.module or "", alias.name)
                    for each in [*code_nodes, *(own_statements if used.block else [])]
                    if isinstance(each, ast.ImportFrom) and each.level for alias in each.names}
        used.relative |= relative
        if relative:
            used.read_at.setdefault("__package__", []).append(node.lineno)
        # A class body looks a name up in the class first: a member bound above, unless a nested scope reads it.
        nested = set().union(*(scope.taken() for scope in head.nested))
        class_bound = {name for name in local or {} if _bound_at(local, name, node.lineno) and name not in nested}
        # A name bound to a builtin is that builtin where the binding is seen: the module's where the code reads
        # the module's name, its class body's (``in_body``) in that body itself, and its own code's when the
        # builtin it assigns is one there (a parameter or a local of that name is not).
        direct = head.loaded if owner else set()
        class_aliases, class_modules = in_body
        # Deferred code (``_runs_later``) runs after import, past any ``del`` below it.
        later = {id(inner) for part in parts for each in ast.walk(part) for root in _runs_later(each)
                 for inner in ast.walk(root)}

        def shadowed(name: str, at: ast.AST) -> bool:  # the module binds the name for certain where ``at`` runs
            if id(at) in later:
                return any(start < node.lineno and end is None for start, end in shadowing.get(name, ()))
            return _bound_at(shadowing, name, node.lineno)

        # A binding the class body itself evaluates (a method's default, ``run=eval``) from a name the class binds
        # to a builtin takes that builtin, as a call there does.
        own, own_modules = _builtin_names(
            code_nodes, lambda name, at: (name in direct and name in class_aliases.get(name, set()))
            or (name in reads - class_bound and not shadowed(name, at)),
            (modules & reads) | (class_modules & direct))

        def reached(call: ast.Call) -> set[str]:  # the builtins a call may be
            func = call.func
            while isinstance(func, ast.NamedExpr):  # ``(run := eval)(src)`` calls what it binds
                func = func.value
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                return {func.attr} if func.value.id in own_modules else set()
            if not isinstance(func, ast.Name):
                return set()
            found = set(own.get(func.id, ()))
            if func.id in direct:
                found |= class_aliases.get(func.id, set())
            if func.id in reads - class_bound:
                found |= aliases.get(func.id, set())
                if not shadowed(func.id, call):
                    found.add(func.id)
            return found

        calls = [(name, each) for each in code_nodes if isinstance(each, ast.Call) for name in reached(each)]
        used.namespace |= {name for name, call in calls if _reads_namespace(name, call)}
        used.compiles |= {name for name, call in calls if _inherits_future(name, call)}
        if isinstance(node, ast.Delete):
            used.deletes |= {name for target in node.targets for name in _target_names(target)}
        conditional = isinstance(node, ast.Match) or (isinstance(node, ast.AnnAssign) and node.value is None)
        used.tentative |= (scope.bound if conditional else set()) | {
            each.target.id for each in ast.walk(code or node) if isinstance(each, ast.NamedExpr)}
        annotated = any(_annotates(part) for part in parts)
        if owner is None:
            used.annotated |= annotated
        else:  # a class's members are compiled with its module: report it once, on the class
            names.setdefault(owner, _Names(None)).annotated |= annotated

    body = list(tree.body)
    if body and _is_docstring(body[0]):
        body = body[1:]  # the module docstring is rewritten by a move by design
    for guard in _guards(body):
        if not _type_checking_imports(guard):
            put("guard:" + _guard_header(guard), ast.unparse(_without_imports(guard)), guard, inert=False)
    for node in _flatten(body):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            put(node.name, ast.unparse(node), node, _inert(node, postponed))
        elif isinstance(node, ast.ClassDef):
            members = [m for m in _flatten(node.body) if not isinstance(m, (ast.Import, ast.ImportFrom))]
            # Python takes a class's ``__doc__`` from the first statement of its body only, so the header
            # carries it: a docstring that anything now precedes is gone from the header, as from ``__doc__``.
            header = ast.ClassDef(
                name=node.name, bases=node.bases, keywords=node.keywords,
                body=node.body[:1] if _is_docstring(node.body[0]) else [ast.Pass()],
                decorator_list=node.decorator_list,
                **({"type_params": node.type_params} if hasattr(node, "type_params") else {}),
            )
            put(node.name, ast.unparse(ast.fix_missing_locations(header)), node, _inert(header, postponed),
                code=header)
            # An import directly in the class body is in no member's text; the class reads it (a block, its own).
            imports = {(each.level, each.module or "", alias.name) for each in node.body
                       if isinstance(each, ast.ImportFrom) and each.level for alias in each.names}
            names[node.name].relative |= imports
            if imports:
                names[node.name].read_at.setdefault("__package__", []).append(node.lineno)
            # A class body binds ``__module__``, and a documented one its docstring as ``__doc__``, before it runs;
            # below a deletion the body reads the module's. Fail closed both ways: ``__doc__`` ends at any deletion
            # that may run, ``__module__`` (unbound at module level) only at a ``del`` directly in the body.
            deletions = _deletions(node.body)
            ends = {"__doc__": deletions.get("__doc__", []), "__module__": [
                each.lineno for each in node.body if isinstance(each, ast.Delete)
                and "__module__" in {name for target in each.targets for name in _target_names(target)}]}
            given = {"__module__"} | ({"__doc__"} if _is_docstring(node.body[0]) else set())

            def implicit(at: ast.stmt) -> set[str]:
                return {name for name in given if all(at.lineno < line for line in ends[name])}
            local = _certain_bindings(node.body)
            # What the class body binds to a builtin: a name it assigns one from is the class's above, else the module's.
            in_body = _builtin_names(_scope_nodes(node.body), lambda name, at: not _bound_at(local, name, at.lineno)
                                     and not _bound_at(shadowing, name, node.lineno), modules)
            class_globals = frozenset(name for each in _scope_nodes(node.body) if isinstance(each, ast.Global)
                                      for name in each.names)
            # The class statement's own stores (``_class_stores``) and its body's imports, which are in no member, bind
            # the module's name where the body declares it ``global``.
            imported = {(alias.asname or alias.name).split(".")[0] for each in _flatten(node.body)
                        if isinstance(each, (ast.Import, ast.ImportFrom)) for alias in each.names}
            names[node.name].declared |= class_globals & (_class_stores(node) | imported)
            class_names = _bound_in(node.body)  # where a member class looks up its bases first
            for guard in _guards(node.body):
                if not _type_checking_imports(guard):
                    put(f"{node.name}.guard:{_guard_header(guard)}", ast.unparse(_without_imports(guard)), guard,
                        inert=False, owner=node.name, implicit=implicit(guard), local=local, in_body=in_body,
                        class_globals=class_globals)
                    names[f"{node.name}.guard:{_guard_header(guard)}"].hands.add(node.name)  # binds anything
            # Each member is judged where it stands in the class body; inside a block, no property above it counts.
            judged = {id(stmt): (inert, properties) for stmt, inert, properties in _class_body(node.body, postponed)}
            for member in members:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    key = member.name
                elif isinstance(member, ast.Assign):
                    key = ",".join(n for t in member.targets for n in _target_names(t))
                elif isinstance(member, (ast.AnnAssign, ast.AugAssign)):
                    key = ",".join(_target_names(member.target))
                elif isinstance(member, ast.Pass):
                    continue
                else:
                    key = "expr:" + ast.unparse(member)
                inert, properties = judged.get(id(member), (None, frozenset()))
                if inert is None:
                    inert = _inert(member, postponed, frozenset())
                put(f"{node.name}.{key}", ast.unparse(member), member, inert, owner=node.name,
                    implicit=implicit(member), local=local, in_body=in_body, class_globals=class_globals,
                    properties=properties, around=class_names)
                # Creating the class hands it to what the member binds: a value an assignment may leave, or a def or
                # class whose creation may run code, so that its decorator's result or its metaclass may be a descriptor.
                if _hands_class([member]) or (
                        isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                        and _runs_on_creation(member, properties, module_names, class_names, rebound)):
                    names[f"{node.name}.{key}"].hands.add(node.name)
        elif isinstance(node, ast.Assign):
            put(_assignment_key(node.targets), ast.unparse(node), node, _inert(node, postponed))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            put(_assignment_key([node.target]), ast.unparse(node), node, _inert(node, postponed))
        elif isinstance(node, ast.Pass):
            continue
        else:
            text = ast.unparse(node)
            put("expr:" + text, text, node, _inert(node, postponed))
    return found, [key for *_, key in sorted(occurrences)], runs, names


@dataclass
class Report:
    moved: int = 0
    missing: list[str] = field(default_factory=list)
    changed: dict[str, str] = field(default_factory=dict)  # symbol -> unified diff
    duplicate: dict[str, list[str]] = field(default_factory=dict)  # symbol -> new files
    side_effects: dict[str, str] = field(default_factory=dict)  # new import-time statement -> new file
    shadows: dict[str, str] = field(default_factory=dict)  # new symbol -> the old names it rebinds, and their users
    added: dict[str, str] = field(default_factory=dict)  # symbol -> new file
    allowed: dict[str, str] = field(default_factory=dict)  # disclosed symbol -> what changed
    reordered: dict[str, str] = field(default_factory=dict)  # symbol -> where it now sits out of order
    relocated: dict[str, str] = field(default_factory=dict)  # old symbol -> what its new module changes for it

    @property
    def ok(self) -> bool:
        return not (self.missing or self.changed or self.duplicate or self.side_effects or self.shadows
                    or self.reordered or self.relocated)


def _delta(name: str, text: str | None, homes: list[str], new_by_file: dict[str, dict[str, str]]) -> str:
    """What happened to one symbol, for a disclosed (allowed) delta."""
    if text is None:
        return f"added in {', '.join(homes)}"
    if not homes:
        return "missing"
    if len(homes) > 1:
        return f"defined in {', '.join(homes)}"
    new_text = new_by_file[homes[0]][name]
    if new_text == text:
        return "unchanged"
    return "\n".join(difflib.unified_diff(text.splitlines(), new_text.splitlines(), "old", homes[0], lineterm="", n=1))


def _origin(node: ast.ImportFrom, path: str) -> frozenset[str]:
    """The files that a ``from M import ...`` in the file at ``path`` (relative to backend/) may import: ``M.py``
    or ``M/__init__.py``, or none when its dots climb past the top-level package (ImportError)."""
    # A relative import's dots count up from here: one is the package. The last parent, ".", is the directory
    # holding the top-level package, no package itself, so as many dots as parents climb past it (ImportError).
    packages = PurePosixPath(path).parents
    if node.level >= len(packages):
        return frozenset()
    base = packages[node.level - 1] if node.level else PurePosixPath()
    module = base.joinpath(*(node.module or "").split("."))
    return frozenset({f"{module}.py", f"{module}/__init__.py"})


def _imported_from(old_source: str, old_path: str) -> dict[str, frozenset[str]]:
    """The names the old file took with one plain module-level ``from M import name``, each with the files M
    may be (``M.py`` or ``M/__init__.py``, relative to backend/ like ``old_path``). When moved code lands in
    that very file, the symbol of that name there is the binding it always had. A name imported more than
    once, under an alias or inside a block is left out, and so is every name once the file has a star
    import: where such a name came from is not known."""
    tree = ast.parse(old_source)
    plain = {id(node) for node in tree.body if isinstance(node, ast.ImportFrom)}
    origins: dict[str, frozenset[str]] = {}
    imported: list[str] = []
    for node in _flatten(tree.body):
        for alias in node.names if isinstance(node, (ast.Import, ast.ImportFrom)) else ():
            imported.append((alias.asname or alias.name).split(".")[0])
            if id(node) in plain and alias.asname is None and (files := _origin(node, old_path)):
                origins[alias.name] = files
    if "*" in imported:
        return {}
    return {name: files for name, files in origins.items() if imported.count(name) == 1}


def _unsettled(path: str, source: str, names: dict[str, _Names], old_names: dict[str, _Names]) -> set[str] | None:
    """The module's names that the new file at ``path`` also binds where no symbol's place shows it, so that moved
    code there may read another binding at import than the one the old file imported (``_shadows``): by an
    import, through blocks and ``match`` cases (a star import may bind any name: None), or through a new
    symbol's ``global``. A def or an assignment in a block is a symbol of its own, whose place shows, and the
    file's import of a name from itself binds that name to itself, or raises ImportError at import."""
    found: set[str] = set()
    for node in _scope_nodes(ast.parse(source).body):
        itself = isinstance(node, ast.ImportFrom) and path in _origin(node, path)
        for alias in node.names if isinstance(node, (ast.Import, ast.ImportFrom)) else ():
            if itself and alias.asname in (None, alias.name):
                continue
            if alias.name == "*":
                return None
            found.add((alias.asname or alias.name).split(".")[0])
    return found.union(*(used.declared for key, used in names.items() if key not in old_names))


def _dunder(name: str) -> bool:
    """``__name__``: a name between two pairs of underscores, which Python looks up itself. A name of
    underscores alone, such as ``__``, is a throwaway name, as ``_`` is."""
    return name.startswith("__") and name.endswith("__") and bool(name.strip("_"))


# Every façade declares ``__all__`` (``tasks/refactor-plan-2026-10.md``), which Python reads only for a
# star import of the module, so a module's new ``__all__`` is ADDED.
_DECLARED_DUNDERS = frozenset({"__all__"})


def _reaching(name: str, names: dict[str, _Names]) -> set[str]:
    """The names that may hold code which reads ``name`` when it runs, ``name`` among them: a def, lambda or
    class whose code (a body, a method, any nested scope) or header (a decorator, a default, an annotation,
    since what reads ``__annotations__`` may call it) loads one of them, a class one of whose members does, and
    that member's own name, which its class body may call where it stands, and so for a name that a statement
    of a class body nested in a symbol binds (``_Names.holders``: a member class's own body); and a name bound at
    import from one of them (``HANDLERS = [describe]``) or through ``global``, closed under those steps. What
    code does with a name is not followed: a reference counts as much as a call. Names are matched across
    namespaces (a member's name also stands for a module name it equals), which errs toward reporting."""
    reach = {name}
    while True:
        grown = reach.union(*(used.binds | ({used.owner} if used.owner else set()) | used.declared
                              for used in names.values() if (used.here | used.later) & reach),
                            {held for used in names.values() for held, takes in used.holders.items() if takes & reach})
        if grown == reach:
            return reach
        reach = grown


def _shadows(key: str, names: dict[str, _Names], old_names: dict[str, _Names],
             own: frozenset[str] = frozenset()) -> str:
    """The names the NEW symbol ``key`` binds that OLD symbols of its file read or bind in the same
    namespace, before the move and after it, as ``binds make, read by X, build``. A dunder of a namespace
    that holds moved code (a module with an old symbol, or a class that is one) is read by Python itself,
    named in the moved code or not, except a module's ``__all__``; any other new member of a class that is
    an old symbol is read by attribute lookups on it, which the proof cannot follow (a name the class body
    declares ``global`` is the module's, not a member). Empty when there are none, and for a new block: it is
    a SIDE EFFECT already, and each statement in it is a symbol of its own.
    ``own``: the module-level names the old file imported from this very file (``_imported_from``). Such a
    binding is the one the moved code always had, so it shadows only the moved code that reads it at import
    above it (``read above it at import by X``): there the import ran first, and now the read does. That is
    code that evaluates it at import (``_Names.evaluated``), or may call a name that may hold code reading it
    (``_reaching``: a def called there, a reference to it; ``_Names.calls``: a lone name an annotation evaluates
    not, one that may run code yes), or is created
    there by a decorator, a class keyword or a base that is not a builtin class, which may run that code; and
    for a dunder, Python itself wherever an old symbol stands above it. Code that rebinds the name, at module
    level or through ``global``, rebound the old file's copy and now rebinds this file's, for every importer,
    so it is ``bound by`` as for any other name."""
    new, found = names[key], []
    for name in sorted(() if new.block else new.binds):
        owner = None if name in new.class_global else new.owner  # a class body's ``global`` binds the module's
        moved_here = owner in old_names if owner else any(other in old_names for other in names)
        uses = []
        if owner is None and name in own:
            reach = _reaching(name, names)
            above = [other for other in sorted(names) if other in old_names
                     and min(names[other].lines) < max(new.lines)]
            early = [other for other in above if name in names[other].evaluated() & old_names[other].evaluated()
                     or reach & names[other].calls() & old_names[other].calls()
                     or (names[other].decorated and old_names[other].decorated
                         and reach & (names[other].later | names[other].binds))]
            rebinding = [other for other in sorted(names) if other in old_names
                         and name in names[other].rebinds() & old_names[other].rebinds()]
            python = ["Python itself"] if _dunder(name) and name not in _DECLARED_DUNDERS and above else []
            for verb, users, lead in (("read above it at import", early, python), ("bound", rebinding, [])):
                if lead or users:
                    more = f" and {len(users) - 3} more" if len(users) > 3 else ""
                    uses.append(f"{verb} by {', '.join(lead + users[:3])}{more}")
        else:
            itself = moved_here and _dunder(name) and not (owner is None and name in _DECLARED_DUNDERS)
            attributes = owner is not None and moved_here and not _dunder(name)
            for verb, used in (("read", _Names.reads), ("bound", _Names.bound)):
                users = [other for other in sorted(names) if other in old_names
                         and name in used(names[other], owner) & used(old_names[other], owner)]
                lead = ([] if verb != "read" else ["Python itself"] if itself
                        else [f"attribute lookups on {owner}"] if attributes else [])
                if lead or users:
                    more = f" and {len(users) - 3} more" if len(users) > 3 else ""
                    uses.append(f"{verb} by {', '.join(lead + users[:3])}{more}")
        if uses:
            found.append(f"binds {name}, {' and '.join(uses)}")
    return "; ".join(found)


@dataclass(frozen=True)
class _Module:
    """Where a file lives, as the import system derives it from its path (relative to backend/, every
    directory a package), and what its code compiles under. ``path`` is None when it is not known. ``binds``:
    the module's names its symbols bind (``_Names.rebinds``); ``outright``: per namespace (a class, or the
    module for None), each name that every binding there sets outright (outside a block or a ``match``, not
    tentatively, from a value that does not read the name; none for a class defined twice), with the lines each
    binding holds between, as ``_certain_bindings`` gives them: to the first ``del`` of the name after it."""
    path: PurePosixPath | None
    docstring: str | None
    postponed: bool
    futures: frozenset[str]  # its ``from __future__`` imports that code it compiles inherits
    binds: frozenset[str]
    pins_package: bool  # every binding of its ``__package__`` sets a string, never deleted nor bound through global
    bound: frozenset[str]  # every name its namespace binds, imports included (a star import as its source)
    outright: dict[str | None, dict[str, list[tuple[int, int | None]]]] = field(hash=False)

    def settles(self, name: str, used: _Names) -> bool:
        """Whether a binding of its own is the value ``used`` reads of ``name`` wherever it stands, at each of its
        definitions that reads it: in a class body, one an earlier member of the class sets outright (a nested
        scope there reads the module's); else one the module sets outright above it. A def's body may run at
        import too, but only once the def statement has."""
        lines = used.read_at.get(name, used.lines)
        member = self.outright.get(used.owner, {}) if used.owner else {}
        if all(_bound_at(member, name, line) for line in lines) and name not in used.later:
            return True
        return all(_bound_at(self.outright.get(None, {}), name, line) for line in lines)

    def pins(self, used: _Names) -> bool:
        """Whether ``used``'s relative imports resolve against a ``__package__`` the module pins: a string it sets
        outright above each definition that imports, and never undoes. Python reads the module's own (a class's
        is no package), and derives one from the path again when it is None or gone."""
        lines = used.read_at.get("__package__", used.lines)
        return self.pins_package and all(_bound_at(self.outright.get(None, {}), "__package__", line) for line in lines)

    @property
    def is_package(self) -> bool:
        return self.path is not None and self.path.name == "__init__.py"

    @property
    def name(self) -> str:
        if self.path is None:
            return "an unknown module"
        parts = self.path.with_suffix("").parts
        return ".".join(parts[:-1] if self.is_package else parts)

    @property
    def package(self) -> str:
        return self.name if self.is_package else self.name.rpartition(".")[0]


def _module(path: str | None, source: str, names: dict[str, _Names]) -> _Module:
    tree = ast.parse(source)
    # A binding in a block, a tentative one, or one from the name itself (``__doc__ +=``) may keep the value
    # the import system derived. One through ``global`` sets it outright when it runs, and its def is compared
    # as a symbol.
    kept = {(used.owner, name) for used in names.values() for name in used.binds
            if used.block or name in used.identity or name in used.tentative}
    # A ``del`` ends the binding above it until the next. A class defined more than once runs each body in a
    # namespace of its own, so no member of either settles a read in it.
    twice = {key for key, used in names.items() if used.owner is None and len(used.lines) > 1}
    starts: dict[str | None, dict[str, list[int]]] = {}
    deleted: dict[str | None, dict[str, list[int]]] = {}
    for used in names.values():
        for name in used.deletes:
            deleted.setdefault(used.owner, {}).setdefault(name, []).extend(used.lines)
        for name in used.binds - used.deletes:
            if (used.owner, name) not in kept and used.owner not in twice:
                starts.setdefault(used.owner, {}).setdefault(name, []).extend(used.lines)
    outright = {owner: {name: [(line, min((at for at in deleted.get(owner, {}).get(name, ()) if at > line),
                                          default=None)) for line in lines] for name, lines in by_name.items()}
                for owner, by_name in starts.items()}
    # Every binding of ``__package__`` in the module's own namespace assigns a string constant; an
    # import, which no symbol holds, binds it to a value the proof cannot see. (One in a block, a ``match`` or a
    # handler keeps the derived value: no binding of it is outright.)
    module_nodes = _scope_nodes(tree.body)
    stores = [each for each in module_nodes if isinstance(each, ast.Name) and each.id == "__package__"
              and not isinstance(each.ctx, ast.Load)]
    strings = {id(target) for each in module_nodes if isinstance(each, ast.Assign)
               and isinstance(each.value, ast.Constant) and isinstance(each.value.value, str) for target in each.targets}
    imported = any((alias.asname or alias.name.partition(".")[0]) == "__package__"
                   for each in module_nodes if isinstance(each, (ast.Import, ast.ImportFrom)) for alias in each.names)
    pins_package = (bool(stores) and all(id(store) in strings for store in stores) and not imported
                    and not any("__package__" in used.declared for used in names.values()))
    return _Module(PurePosixPath(path) if path else None, ast.get_docstring(tree, clean=False),
                   _postpones_annotations(tree),
                   frozenset(alias.name for node in tree.body if isinstance(node, ast.ImportFrom)
                             and node.module == "__future__" for alias in node.names) & _INHERITED_FUTURES,
                   frozenset(name for used in names.values() for name in used.rebinds()),
                   pins_package,
                   frozenset(_Scope().read(*tree.body).bound - {"*"}
                             | {name for used in names.values() for name in used.declared}
                             | {f"* from {'.' * each.level}{each.module or ''}" for each in module_nodes
                                if isinstance(each, ast.ImportFrom) and any(alias.name == "*" for alias in each.names)}),
                   outright)


def _resolve(level: int, module: str, package: str) -> str:
    """The module a relative import names from ``package``, as ``importlib.util.resolve_name`` resolves it."""
    parts = package.split(".") if package else []
    if level > len(parts):
        return "an ImportError"  # beyond the top-level package, or no package at all
    return ".".join(parts[:len(parts) - level + 1] + ([module] if module else []))


def _identity_change(name: str, before: _Module, after: _Module) -> str:
    """How the value of one name that a module gets from where it lives differs between the old module and
    the new one, or "" when it does not."""
    if name == "__doc__":
        return "" if before.docstring == after.docstring else "the module docstring differs"
    if before.path is None:
        return "the old path is unknown"
    if name in _FROM_NAME:
        if before.name != after.name:
            return f"{after.name}, was {before.name}"
        if name == "__name__" and before.is_package != after.is_package:  # a relative anchor, as in import_module
            return f"{after.name}, {'now' if after.is_package else 'no longer'} a package"
        return ""
    if name == "__package__":
        return "" if before.package == after.package else f"{after.package!r}, was {before.package!r}"
    if before.path == after.path or (name == "__path__" and not (before.is_package or after.is_package)):
        return ""
    return "another file" + (" in the same directory" if before.path.parent == after.path.parent else "")


def _relocated(old: _Names, new: _Names, before: _Module, after: _Module, same: bool = False) -> str:
    """What the new module changes for one OLD symbol that reads where its module lives, read both before
    the move and after it: the names its module gets from its path (not one that both modules set outright
    above the read, which the proof compares as symbols), the targets of its relative imports (settled so by a
    ``__package__`` the modules pin), its module's namespace, whether its annotations are postponed, the
    ``__future__`` imports the code it compiles inherits, and, for a module dunder it binds, the module Python
    reads it from. ``same``: its text is unchanged, so a builtin either module's bindings make of a name counts,
    not only one both do. "" when nothing changes."""
    reasons = []
    for name in sorted(old.identity & new.identity):
        settled = before.settles(name, old), after.settles(name, new)
        bound = name in before.binds, name in after.binds
        if all(settled):
            continue  # each module sets the value it reads: their symbols are compared as such
        if any(settled) or bound[0] != bound[1]:  # one module's own binding; the other's may be derived
            why = "the old module bound it" if settled[0] or (bound[0] and not bound[1]) else "the new module binds it"
        else:
            why = _identity_change(name, before, after)
        if why:
            reasons.append(f"reads {name} ({why})")
    imports = old.relative & new.relative
    if imports:  # a relative import resolves against ``__package__``, which a module may pin itself
        settled = before.pins(old), after.pins(new)
        bound = "__package__" in before.binds, "__package__" in after.binds
        if any(settled) or bound[0] != bound[1]:
            why = ("the old module bound __package__" if settled[0] or (bound[0] and not bound[1])
                   else "the new module binds __package__")
            reasons.extend(f"imports {alias} from {'.' * level}{module} ({why})"
                           for level, module, alias in sorted(imports) if not all(settled))
            imports = set()
    for level, module, alias in sorted(imports):
        now = _resolve(level, module, after.package)
        was = _resolve(level, module, before.package) if before.path else before.name
        if now != was:
            reasons.append(f"imports {alias} from {'.' * level}{module} ({now}, was {was})")
    moved = before.path is None or before.name != after.name
    # Unchanged text reads what either module's bindings make of it; a changed symbol fails anyway.
    calls, compilers = ((old.namespace | new.namespace, old.compiles | new.compiles) if same
                        else (old.namespace & new.namespace, old.compiles & new.compiles))
    # Another file holds another namespace (x/__init__.py has __path__); the same file, one that binds other names.
    if calls and (before.path != after.path or before.bound != after.bound):
        called = ", ".join(f"{call}()" for call in sorted(calls))
        if before.path != after.path:
            where = f"was {before.name}" if moved else ("now" if after.is_package else "no longer") + " a package"
        else:
            where = "which binds other names: " + "; ".join(
                f"{', '.join(sorted(names))} {change}" for names, change in
                ((before.bound - after.bound, "gone"), (after.bound - before.bound, "new")) if names)
        reasons.append(f"reads its module's namespace through {called} ({after.name}, {where})")
    if old.annotated and new.annotated and before.postponed != after.postponed:
        reasons.append("its annotations are " + ("postponed now (from __future__ import annotations), evaluated"
                                                 if after.postponed else "evaluated now, postponed") + " before")
    if compilers:
        now, was = after.futures, before.futures
        if now != was:
            called = ", ".join(f"{name}()" for name in sorted(compilers))
            now, was = (", ".join(sorted(futures)) or "nothing" for futures in (now, was))
            reasons.append(f"the code it compiles with {called} inherits from __future__ {now} now, {was} before")
    if not old.block and moved:  # a block's statements are symbols of their own
        for name in sorted(name for name in old.rebinds() & new.rebinds() if _dunder(name)):
            reasons.append(f"binds {name}, which Python reads from {after.name}, was {before.name}")
    return "; ".join(reasons)


def compare(old_source: str, new_sources: dict[str, str], allow: frozenset[str] = frozenset(),
            old_path: str | None = None) -> Report:
    """Diff the old file's symbols against the union of the new files' symbols, check that no new symbol
    rebinds a name the old symbols of its file use, and check that the old symbols each new file holds
    keep their old relative order (module-level code runs top to bottom, so ``B = A`` above ``A = 1``
    raises at import). ``old_path`` (relative to backend/, like the new files' paths) lets the old file's
    own imports show which symbols of a target file the moved code already used."""
    old, old_order, _, old_names = _collect(old_source)
    origins = _imported_from(old_source, old_path) if old_path else {}
    collected = {path: _collect(src) for path, src in new_sources.items()}
    unsettled = {path: _unsettled(PurePosixPath(path).as_posix(), src, collected[path][3], old_names)
                 for path, src in new_sources.items()}
    before = _module(old_path, old_source, old_names)
    modules = {path: _module(path, src, collected[path][3]) for path, src in new_sources.items()}
    new_by_file = {path: texts for path, (texts, *_) in collected.items()}
    runs_by_file = {path: runs for path, (_, _, runs, _) in collected.items()}
    where: dict[str, list[str]] = {}
    for path, syms in new_by_file.items():
        for name in syms:
            where.setdefault(name, []).append(path)
    report = Report()
    for name, text in old.items():
        homes = where.get(name, [])
        relocated = _relocated(old_names[name], collected[homes[0]][3][name], before, modules[homes[0]],
                               same=new_by_file[homes[0]].get(name) == text) if len(homes) == 1 else ""
        if name in allow:
            delta = _delta(name, text, homes, new_by_file)
            report.allowed[name] = f"{delta}\nrelocated: {relocated}" if relocated else delta
            continue
        if relocated:
            report.relocated[name] = f"{homes[0]}, was {old_path or 'an unknown path'}: {relocated}"
        if not homes:
            report.missing.append(name)
            continue
        if len(homes) > 1:
            report.duplicate[name] = homes
            continue
        new_text = new_by_file[homes[0]][name]
        if new_text != text:
            diff = difflib.unified_diff(text.splitlines(), new_text.splitlines(), "old", homes[0], lineterm="", n=1)
            report.changed[name] = "\n".join(diff)
            continue
        report.moved += 1
    for name, homes in where.items():
        if name in old:
            continue
        shadowed = "; ".join(
            f"{path}: {what}" for path in homes
            if (what := _shadows(name, collected[path][3], old_names, frozenset(
                known for known, files in origins.items() if PurePosixPath(path).as_posix() in files
                and unsettled[path] is not None and known not in unsettled[path]))))
        if name in allow:
            delta = _delta(name, None, homes, new_by_file)
            report.allowed[name] = f"{delta}\nshadows {shadowed}" if shadowed else delta
            continue
        if shadowed:
            report.shadows[name] = shadowed
        if len(homes) > 1:
            report.duplicate[name] = homes
        elif name in runs_by_file[homes[0]]:
            report.side_effects[name] = homes[0]
        elif not shadowed:
            report.added[name] = homes[0]
    old_rank = _occurrence_ranks(old_order)
    for path, (_, order, *_) in collected.items():
        latest: tuple[str, int] | None = None  # the held occurrence that came latest in the old file, so far
        for occurrence in _occurrence_ranks(order):
            name = occurrence[0]
            if occurrence not in old_rank or name in allow or where[name] != [path]:
                continue
            if latest is not None and old_rank[occurrence] < old_rank[latest]:
                report.reordered.setdefault(name, f"{path}: now after {latest[0]}, which it preceded")
            else:
                latest = occurrence
    return report


def _occurrence_ranks(order: list[str]) -> dict[tuple[str, int], int]:
    """(key, its n-th binding) -> position, so a rebound name keeps every binding's place in the order."""
    seen: dict[str, int] = {}
    ranks: dict[tuple[str, int], int] = {}
    for position, key in enumerate(order):
        ranks[(key, seen.get(key, 0))] = position
        seen[key] = seen.get(key, 0) + 1
    return ranks


def _git_show(ref: str, rel_path: str) -> str:
    """The file at ``ref``; a path that is no file there (missing, or a directory, which ``git show`` would
    list) stops the CLI with a message, as any input it cannot read does: never a traceback, never an OK."""
    repo_path = (BACKEND_DIR / rel_path).resolve().relative_to(REPO_ROOT).as_posix()
    kind = subprocess.run(  # nosec B603 B607 - fixed git argv, read-only, developer tool
        ["git", "-C", str(REPO_ROOT), "cat-file", "-t", f"{ref}:{repo_path}"],
        capture_output=True, text=True, check=False,
    )
    if kind.returncode == 0 and kind.stdout.strip() != "blob":
        raise SystemExit(f"cannot read {repo_path} at {ref}: a {kind.stdout.strip()}, not a file")
    result = subprocess.run(  # nosec B603 B607 - fixed git argv, read-only, developer tool
        ["git", "-C", str(REPO_ROOT), "show", f"{ref}:{repo_path}"],
        capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"cannot read {repo_path} at {ref}: {result.stderr.decode(errors='replace').strip()}")
    return _source(result.stdout, f"{repo_path} at {ref}")


def _worktree(rel_path: str) -> str:
    """The file in the working tree; a missing path or a directory stops the CLI with a message."""
    path = BACKEND_DIR / rel_path
    if not path.is_file():
        raise SystemExit(f"cannot read {rel_path} in the working tree: not a file")
    return _source(path.read_bytes(), f"{rel_path} in the working tree")


def _source(data: bytes, where: str) -> str:
    """The text Python reads from a source file's bytes (its coding declaration or UTF-8, with universal
    newlines); bytes it cannot decode stop the CLI with a message."""
    try:
        return importlib.util.decode_source(data)
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise SystemExit(f"cannot read {where}: not Python source text ({exc})") from None


def _canonical(path: str) -> str:
    """``path`` relative to backend/, however it is spelled (``./``, ``..``, absolute): a module's identity is
    derived from it."""
    resolved = (BACKEND_DIR / path).resolve()
    if not resolved.is_relative_to(BACKEND_DIR):
        raise SystemExit(f"{path} is not under backend/")
    return resolved.relative_to(BACKEND_DIR).as_posix()


def render(report: Report) -> str:
    lines = []
    for name in sorted(report.missing):
        lines.append(f"MISSING    {name}")
    for name, diff in sorted(report.changed.items()):
        lines.append(f"CHANGED    {name}\n{diff}")
    for name, homes in sorted(report.duplicate.items()):
        lines.append(f"DUPLICATE  {name}: {', '.join(homes)}")
    for name, home in sorted(report.side_effects.items()):
        lines.append(f"SIDE EFFECT {name} ({home}): runs at import; a move never adds one")
    for name, where in sorted(report.shadows.items()):
        lines.append(f"SHADOWS    {name} ({where}): the moved code now gets the new binding")
    for name, where in sorted(report.reordered.items()):
        lines.append(f"REORDERED  {name} ({where}): module-level code runs in order")
    for name, where in sorted(report.relocated.items()):
        home, why = where.split(": ", 1)
        lines.append(f"RELOCATED  {name} ({home}): {why}")
    for name, home in sorted(report.added.items()):
        lines.append(f"ADDED      {name} ({home})")
    for name, delta in sorted(report.allowed.items()):
        lines.append(f"ALLOWED    {name} (disclosed delta)\n{delta}")
    verdict = "OK" if report.ok else "FAILED"
    lines.append(
        f"pure move: {verdict} ({report.moved} symbols identical, {len(report.missing)} missing, "
        f"{len(report.changed)} changed, {len(report.duplicate)} duplicated, "
        f"{len(report.side_effects)} side effects, {len(report.shadows)} shadowing, {len(report.reordered)} reordered, "
        f"{len(report.relocated)} relocated, "
        f"{len(report.added)} added, {len(report.allowed)} allowed)"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", required=True, help="git ref holding the file before the move")
    parser.add_argument("--old", required=True, help="the file before the move, relative to backend/")
    parser.add_argument("--new", required=True, nargs="+", help="every file the code lives in after the move")
    parser.add_argument("--head", default="HEAD", help="git ref holding the new files (default HEAD)")
    parser.add_argument("--worktree", action="store_true", help="read the new files from the working tree instead")
    parser.add_argument("--allow", action="append", default=[], help="a disclosed delta (repeatable)")
    args = parser.parse_args(argv)
    old_path = _canonical(args.old)
    old_source = _git_show(args.base, old_path)
    new_sources = {
        path: _worktree(path) if args.worktree else _git_show(args.head, path)
        for path in map(_canonical, args.new)
    }
    for path, source in ((old_path, old_source), *new_sources.items()):
        try:
            ast.parse(source, filename=path)
        except (SyntaxError, ValueError) as exc:  # a NUL byte is a ValueError before Python 3.11.4, with no line
            line = f" (line {exc.lineno})" if getattr(exc, "lineno", None) else ""
            raise SystemExit(f"cannot parse {path}: {getattr(exc, 'msg', exc)}{line}") from None
    report = compare(old_source, new_sources, frozenset(args.allow), old_path)
    print(render(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
