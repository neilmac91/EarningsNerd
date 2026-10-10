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
CHANGED. Import statements and module docstrings are not symbols: a move rewrites them by design. A block
around imports still is one, so a split that copies an import fallback into two files discloses a DUPLICATE.

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
use, or a dunder that Python reads itself where they live; the next two paragraphs), REORDERED (an old
binding that now sits above one it followed in the same new file, every binding of a rebound name
counted: module-level code runs top to bottom, so ``B = A`` above ``A = 1`` raises at import, and
``A = 1; A = 2; B = A`` binds ``B`` to 2 where ``A = 1; B = A; A = 2`` bound it to 1) and ADDED (other
new symbols, which no moved code uses, such as the helpers a split introduces, or a façade's ``__all__``).

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
single plain module-level ``from M import name`` and the new file is M itself, the moved code keeps the
binding it always had, and nothing is reported unless moved code reads the name at import above that
binding (in a statement, a class body, a decorator or a comprehension, which runs where it stands; a
generator expression counts too, though it may run later): the import ran before the read, and now the
binding runs after it, so the read raises NameError or takes an earlier binding of the name, ``read above
it at import``. A def's or lambda's body reads it when it runs. The settlement covers reads only: moved
code that rebinds the name, at module level or through ``global``, rebound the old file's copy and now
rebinds the target's, for every importer, and is reported.

Python itself reads a dunder name (``__x__``) of a namespace, with no load of it in the code there: a def
or class body created below a module's ``__builtins__`` resolves every builtin through it, a relative
import inside a def goes through ``__package__``, an attribute missing from the module through
``__getattr__``, and creating, comparing or hashing an instance through its class's ``__slots__``,
``__init__``, ``__eq__`` or ``__hash__``. So a new symbol that binds a dunder where moved code lives
shadows it, ``read by Python itself``: at module level when its file holds an old symbol, and in a class
body when the class is an old symbol. Every dunder counts, the ones libraries read included (pydantic's
``__get_validators__``, SQLAlchemy's ``__tablename__``), with one exemption: a module's ``__all__``, which
every façade declares and Python reads only for ``from module import *``. (A name the old file imported
from the target file itself is settled as above, a dunder too.) A new class's own dunders are ADDED: moved
code reaches them only through the class's name, which SHADOWS reports when the moved code reads it, or a
disclosed change shows when it starts to (a new base on a moved class).

Limits. Code that a new class runs through a BASE (an inherited metaclass, or the base's
``__init_subclass__``) is not visible in the AST, so a new class with bases is ADDED; read every ADDED
class's bases. Names are followed only as written. A new symbol that loads an unbound name raises
NameError at import, which every test that imports the module, and the app's own startup, fails on loudly.
A name reached through an attribute is not followed: an ADDED ``Class.member`` of a moved class overrides
whatever the class inherited under that name for ``self.name`` and for the non-dunder names a class's
machinery reads (an Enum's ``_missing_``), and an annotated one is a new field of a dataclass or a
pydantic model, so read every one. Neither is a name reached through a string (a quoted annotation,
``globals()['name']``), a class-private ``__name`` (compared as written, not mangled), or an import:
imports are not symbols, so one that binds a name the moved code reads, or a dunder, to something else, a
new symbol of another new file included, is outside the proof, and so is a new ``from __future__``
import, which changes how the moved code compiles; read the import diff. A new annotated assignment
writes its namespace's ``__annotations__`` without binding that name, so moved code that reads the dict,
at module level too, sees one more key. And the names these rules trust (``property``, ``dataclass``,
``TYPE_CHECKING`` and the like) are taken at their word, so a move that rebinds one where no moved symbol
reads it, such as an ADDED ``TYPE_CHECKING = True`` above an exempt block, is outside the proof.

The exit status is 0 only when nothing is MISSING, CHANGED, DUPLICATE, SIDE EFFECT, SHADOWS or REORDERED
beyond the symbols passed with ``--allow`` (for SHADOWS, the new symbol's key); each allowed symbol is a
disclosed delta the PR body must list, and its diff is printed with it, with the names it shadows.
"""
from __future__ import annotations

import argparse
import ast
import copy
import difflib
import subprocess
import sys
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
_ACCESSORS = frozenset({"setter", "getter", "deleter"})


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


def _class_body(body: list[ast.stmt], postponed: bool) -> list[tuple[ast.stmt, bool]]:
    """Each statement of a class body, and whether it is ``_inert`` where it stands, which an accessor needs:
    the names bound to a property above it. A def binds its name to one when its outermost decorator is
    ``property`` or such an accessor and every decorator is inert (``property.setter`` reads the getter's
    ``__doc__`` again). Any other inert statement unbinds the names it binds, and one that runs code may
    rebind any name (``locals()``, ``exec``, a frame), so it unbinds them all."""
    judged: list[tuple[ast.stmt, bool]] = []
    properties: frozenset[str] = frozenset()
    for stmt in body:
        inert = _inert(stmt, postponed, properties)
        judged.append((stmt, inert))
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
                and all(inert for _, inert in _class_body(stmt.body, postponed)))
    return False


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


class _Scope:
    """One scope of a symbol's code, read the way the compiler scopes names: the names it binds, loads and
    declares ``global``, and the scopes nested in it. A def's decorators, defaults and annotations, a
    class's bases and keywords and a comprehension's first iterable are evaluated in the scope around
    them, and ``:=`` inside a comprehension binds in the scope around it. (``nonlocal`` needs no rule: the
    name belongs to an enclosing def whether or not this scope rebinds it.)"""

    def __init__(self, in_class: bool = False, walrus: _Scope | None = None, deferred: bool = False) -> None:
        self.in_class = in_class
        self.deferred = deferred  # a def's or lambda's body, which runs when it is called
        self.bound: set[str] = set()
        self.loaded: set[str] = set()
        self.module: set[str] = set()  # declared ``global``
        self.nested: list[_Scope] = []
        self.walrus = walrus or self

    def _open(self, in_class: bool = False, walrus: _Scope | None = None, deferred: bool = False) -> _Scope:
        self.nested.append(_Scope(in_class, walrus, deferred))
        return self.nested[-1]

    def read(self, *nodes: ast.AST | None) -> _Scope:
        for node in nodes:
            if isinstance(node, ast.Name):
                (self.loaded if isinstance(node.ctx, ast.Load) else self.bound).add(node.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                args = node.args
                params = [*args.posonlyargs, *args.args, *args.kwonlyargs, *filter(None, (args.vararg, args.kwarg))]
                self.read(*args.defaults, *args.kw_defaults, *(param.annotation for param in params))
                body = self._open(deferred=True)
                body.bound.update(param.arg for param in params)
                if isinstance(node, ast.Lambda):
                    body.read(node.body)
                else:
                    self.bound.add(node.name)
                    self.read(*node.decorator_list, node.returns, *getattr(node, "type_params", ()))
                    body.read(*node.body)
            elif isinstance(node, ast.ClassDef):
                self.bound.add(node.name)
                self.read(*node.decorator_list, *node.bases, *(keyword.value for keyword in node.keywords),
                          *getattr(node, "type_params", ()))
                self._open(in_class=True).read(*node.body)
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
                self.read(node.annotation)  # ``(x): int`` neither binds x nor reads it
            elif node is not None:
                if isinstance(node, ast.alias):
                    self.bound.add((node.asname or node.name).split(".")[0])
                elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name:
                    self.bound.add(node.name)
                elif isinstance(node, ast.MatchMapping) and node.rest:
                    self.bound.add(node.rest)
                elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                    self.loaded.add(node.target.id)  # ``x += 1`` reads x before it binds it
                self.read(*ast.iter_child_nodes(node))
        return self

    def taken(self, enclosing: frozenset[str] = frozenset(), now: bool = False) -> set[str]:
        """The names this scope and the scopes nested in it take from the module. A def, lambda or
        comprehension takes each name it loads that neither it nor an enclosing def binds, and each name it
        declares ``global``. A class body also takes the loaded names it binds itself: the lookup falls
        through to the module until the class has bound the name, and never stops at an enclosing def.
        ``now``: only the scopes that run where they stand, a comprehension's or a class's body, not a def's."""
        if now and self.deferred:
            return set()
        if self.in_class:
            taken = {name for name in self.loaded if name in self.bound or name not in enclosing}
        else:
            taken = self.loaded - self.bound - enclosing
            enclosing = enclosing | self.bound
        return taken.union(self.module, *(scope.taken(enclosing, now) for scope in self.nested))

    def declared(self) -> set[str]:
        """The module's names this scope and the scopes nested in it bind through ``global``: declared and
        bound (stored or deleted) in the same scope. A ``global`` that is only read binds nothing."""
        return (self.module & self.bound).union(*(scope.declared() for scope in self.nested))


@dataclass
class _Names:
    """What one symbol does with names. ``owner`` is the class whose body holds it (None at module level);
    ``binds`` and ``here`` are the names it binds and loads in that scope; ``later`` are the names its nested
    scopes (the body of a def, lambda, comprehension or nested class) take from the module, and ``soon`` the
    ones of those that a comprehension or class body takes where it stands, at import; ``declared`` the
    module's names it or a nested scope binds through ``global``. A ``block`` (a guard) binds whatever is
    bound in it: its header's targets, its imports and its statements' names. ``lines``: where each of its
    definitions starts."""
    owner: str | None
    block: bool = False
    binds: set[str] = field(default_factory=set)
    here: set[str] = field(default_factory=set)
    later: set[str] = field(default_factory=set)
    soon: set[str] = field(default_factory=set)
    declared: set[str] = field(default_factory=set)
    lines: list[int] = field(default_factory=list)

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

    def at_import(self) -> set[str]:
        """The names it reads from the module while the module runs, not later from a def's body."""
        return self.here | self.soon

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

    def put(key: str, text: str, node: ast.AST, inert: bool, owner: str | None = None,
            code: ast.AST | None = None) -> None:
        found[key] = f"{found[key]}\n{text}" if key in found else text  # every definition, in source order
        occurrences.append((node.lineno, node.col_offset, len(occurrences), key))
        if not inert:
            runs.add(key)
        scope = _Scope().read(code or node)
        used = names.setdefault(key, _Names(owner, block=isinstance(node, _COMPOUND)))
        used.binds |= scope.bound
        # ``global x`` in a class body makes x the module's there, so the statement counts as a user of x.
        used.here |= scope.loaded | scope.module
        used.later |= set().union(*(nested.taken() for nested in scope.nested))
        used.soon |= set().union(*(nested.taken(now=True) for nested in scope.nested))
        # A ``global`` directly in a class body holds for the whole body, but each member is read on its
        # own, so the store is another member's: there the declaration alone counts.
        used.declared |= scope.declared() | (scope.module if owner else set())
        used.lines.append(node.lineno)

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
            for guard in _guards(node.body):
                if not _type_checking_imports(guard):
                    put(f"{node.name}.guard:{_guard_header(guard)}", ast.unparse(_without_imports(guard)), guard,
                        inert=False, owner=node.name)
            # Each member is judged where it stands in the class body; inside a block, no property above it counts.
            judged = {id(stmt): inert for stmt, inert in _class_body(node.body, postponed)}
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
                inert = judged[id(member)] if id(member) in judged else _inert(member, postponed, frozenset())
                put(f"{node.name}.{key}", ast.unparse(member), member, inert, owner=node.name)
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

    @property
    def ok(self) -> bool:
        return not (self.missing or self.changed or self.duplicate or self.side_effects or self.shadows
                    or self.reordered)


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


def _imported_from(old_source: str, old_path: str) -> dict[str, frozenset[str]]:
    """The names the old file took with one plain module-level ``from M import name``, each with the files M
    may be (``M.py`` or ``M/__init__.py``, relative to backend/ like ``old_path``). When moved code lands in
    that very file, the symbol of that name there is the binding it always had. A name imported more than
    once, under an alias or inside a block is left out, and so is every name once the file has a star
    import: where such a name came from is not known."""
    tree = ast.parse(old_source)
    packages = PurePosixPath(old_path).parents  # a relative import's dots count up from here: one is the package
    plain = {id(node) for node in tree.body if isinstance(node, ast.ImportFrom)}
    origins: dict[str, frozenset[str]] = {}
    imported: list[str] = []
    for node in _flatten(tree.body):
        for alias in node.names if isinstance(node, (ast.Import, ast.ImportFrom)) else ():
            imported.append((alias.asname or alias.name).split(".")[0])
            if id(node) in plain and alias.asname is None and node.level <= len(packages):
                base = packages[node.level - 1] if node.level else PurePosixPath()
                module = base.joinpath(*(node.module or "").split("."))
                origins[alias.name] = frozenset({f"{module}.py", f"{module}/__init__.py"})
    if "*" in imported:
        return {}
    return {name: files for name, files in origins.items() if imported.count(name) == 1}


def _dunder(name: str) -> bool:
    """``__name__``: a name between two pairs of underscores, which Python looks up itself. A name of
    underscores alone, such as ``__``, is a throwaway name, as ``_`` is."""
    return name.startswith("__") and name.endswith("__") and bool(name.strip("_"))


# Every façade declares ``__all__`` (``tasks/refactor-plan-2026-10.md``), which Python reads only for a
# star import of the module, so a module's new ``__all__`` is ADDED.
_DECLARED_DUNDERS = frozenset({"__all__"})


def _shadows(key: str, names: dict[str, _Names], old_names: dict[str, _Names],
             own: frozenset[str] = frozenset()) -> str:
    """The names the NEW symbol ``key`` binds that OLD symbols of its file read or bind in the same
    namespace, before the move and after it, as ``binds make, read by X, build``. A dunder of a namespace
    that holds moved code (a module with an old symbol, or a class that is one) is read by Python itself,
    named in the moved code or not, except a module's ``__all__``. Empty when there are none, and for a new
    block: it is a SIDE EFFECT already, and each statement in it is a symbol of its own.
    ``own``: the module-level names the old file imported from this very file (``_imported_from``). Such a
    binding is the one the moved code always had, so it shadows only the moved code that reads it at import
    above it (``read above it at import by X``): there the import ran first, and now the read does. Code that
    rebinds the name, at module level or through ``global``, rebound the old file's copy and now rebinds this
    file's, for every importer, so it is ``bound by`` as for any other name."""
    new, found = names[key], []
    moved_here = new.owner in old_names if new.owner else any(other in old_names for other in names)
    for name in sorted(() if new.block else new.binds):
        uses = []
        if new.owner is None and name in own:
            early = [other for other in sorted(names) if other in old_names
                     and name in names[other].at_import() & old_names[other].at_import()
                     and min(names[other].lines) < max(new.lines)]
            rebinding = [other for other in sorted(names) if other in old_names
                         and name in names[other].rebinds() & old_names[other].rebinds()]
            for verb, users in (("read above it at import", early), ("bound", rebinding)):
                if users:
                    more = f" and {len(users) - 3} more" if len(users) > 3 else ""
                    uses.append(f"{verb} by {', '.join(users[:3])}{more}")
        else:
            itself = moved_here and _dunder(name) and not (new.owner is None and name in _DECLARED_DUNDERS)
            for verb, used in (("read", _Names.reads), ("bound", _Names.bound)):
                users = [other for other in sorted(names) if other in old_names
                         and name in used(names[other], new.owner) & used(old_names[other], new.owner)]
                python = ["Python itself"] if verb == "read" and itself else []
                if python or users:
                    more = f" and {len(users) - 3} more" if len(users) > 3 else ""
                    uses.append(f"{verb} by {', '.join(python + users[:3])}{more}")
        if uses:
            found.append(f"binds {name}, {' and '.join(uses)}")
    return "; ".join(found)


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
    new_by_file = {path: texts for path, (texts, *_) in collected.items()}
    runs_by_file = {path: runs for path, (_, _, runs, _) in collected.items()}
    where: dict[str, list[str]] = {}
    for path, syms in new_by_file.items():
        for name in syms:
            where.setdefault(name, []).append(path)
    report = Report()
    for name, text in old.items():
        homes = where.get(name, [])
        if name in allow:
            report.allowed[name] = _delta(name, text, homes, new_by_file)
            continue
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
                known for known, files in origins.items() if PurePosixPath(path).as_posix() in files))))
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
    repo_path = (BACKEND_DIR / rel_path).resolve().relative_to(REPO_ROOT).as_posix()
    result = subprocess.run(  # nosec B603 B607 - fixed git argv, read-only, developer tool
        ["git", "-C", str(REPO_ROOT), "show", f"{ref}:{repo_path}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"cannot read {repo_path} at {ref}: {result.stderr.strip()}")
    return result.stdout


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
    for name, home in sorted(report.added.items()):
        lines.append(f"ADDED      {name} ({home})")
    for name, delta in sorted(report.allowed.items()):
        lines.append(f"ALLOWED    {name} (disclosed delta)\n{delta}")
    verdict = "OK" if report.ok else "FAILED"
    lines.append(
        f"pure move: {verdict} ({report.moved} symbols identical, {len(report.missing)} missing, "
        f"{len(report.changed)} changed, {len(report.duplicate)} duplicated, "
        f"{len(report.side_effects)} side effects, {len(report.shadows)} shadowing, {len(report.reordered)} reordered, "
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
    old_source = _git_show(args.base, args.old)
    new_sources = {
        path: (BACKEND_DIR / path).read_text() if args.worktree else _git_show(args.head, path)
        for path in args.new
    }
    report = compare(old_source, new_sources, frozenset(args.allow), args.old)
    print(render(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
