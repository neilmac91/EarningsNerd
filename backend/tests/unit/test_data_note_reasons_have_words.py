"""Every reason the backend writes has words (CLAUDE.md rule 12; data notes version 2).

A data note's message is its reasons' sentences from `data_notes.REASONS`. A reason with no entry falls back to one
generic sentence ("The source or calculation basis needs review. Check the original filing."), so a new reason would
reach the page, the PDF, the workbook and the chart PNG with no words of its own and nothing would fail. This gate
reads every module under `app/` and fails on a reason code the backend can write that `REASONS` does not hold. The
frontend's copy (`provenance.ts` REASONS) is held equal to `REASONS` by the shared notes fixture
(`tests/fixtures/analysis_data_notes.json`: case `all_known_reason_messages_and_supplements_after_z` holds one note
for every reason, read by `test_analysis_data_notes.py` and `frontend/tests/unit/data-notes.spec.ts`), so a code with
words here has the same words there.

The gate has two halves. A static reader finds what can be written and where; a run of every emitter module checks
the reader against what the code writes, by line, and a guard holds every other mention of `reasons` in `app/`.

The reader. A reason is written where a string can become an element of a `reasons` list:
1. the value of a `"reasons"` key in a dict display (`{"reasons": ["source_check_needed"]}`);
2. a `reasons=` keyword (`provenance.update(reasons=[...])`, `calculated_provenance(..., reasons=reasons)`);
3. an assignment to a name `reasons`, an attribute `.reasons` or a `["reasons"]` item: plain, annotated, augmented,
   a walrus, or one item of an unpacked tuple (`reasons, other = ["code"], 1`);
4. an `append`, `extend`, `insert`, `add` or `update` on such a target (`reasons.append("calculation_mismatch")`);
5. an argument bound to a parameter that flows into one of the above, to a fixpoint, at a call of a function or method
   of that name in `app/` (`_quarantine(state, "repair_rolled_back")`, whose `reason` becomes `"reasons": [reason]`),
   and a parameter's default (`def withdraw(state, reason="code")`). A parameter flows for its own file's function
   alone. A bare name binds to its own module's function when the module defines one, as Python looks it up; a call
   through an import (`from app.x import f as g`) or a module (`x.f(...)`) binds only to that module's function when
   it defines one, and a call into a module outside `app/` binds to none. A method's arguments bind after the `self` an object supplies
   (`self._quarantine(state, code)`) and the `cls` an object or its class supplies; through its class
   (`Repair._quarantine(repair, state, code)`, `type(self)._quarantine(self, ...)`, `self.__class__`, `module.Class`)
   a method takes `self` as its first argument, and a static method binds from the first. A call on an object reaches
   a method only, never a module-level function of that name.

What a value can hold is read through:
- string literals; list, tuple and set displays and their starred items; `or`, `and`, a conditional's arms, `+` and `|`;
- `list()`, `sorted()`, `reversed()`, `set()`, `tuple()`, `frozenset()` and `dict.fromkeys()` of an argument, and a
  dict display's `keys()`, `values()` and `items()`, a `**` entry's own included (`{**BASE, ...}.values()`);
- a comprehension's element, its loop names bound as a `for` loop's are;
- a name, through its every binding in its function, the functions that enclose it and the module: an assignment
  (plain, annotated, augmented or a walrus), what an `extend` or `update` puts into it, a one-element display of what
  an `append`, `insert` or `add` puts into it (so `checks.append((code, limit))` is one row), a parameter's default,
  and a `for` loop's target. A loop name takes each item its iterable holds (a dict display's keys, a starred
  element's items, a `**` entry's keys); a tuple target takes its column of each row (`for code, limit in CHECKS`,
  nested targets and a table's starred rows too), over `enumerate()` and `zip()` item by item; a tuple unpacked from
  anything but a tuple display takes its element (`code, words = PAIR`). A parameter its function rebinds
  (`codes = list(codes)`) still flows;
- a name imported from another module under `app/` (`from app.x import CODE`, `from .x import CODE as OTHER`) or a
  module's attribute (`from app import x` or `import app.x as x`, then `x.CODE`), through that module's bindings;
- an item of a display such a name holds: every value of a dict (`fallback[kind]`, a `**` entry's values too), a
  list's or tuple's element at a constant index (`FIRST[0]`, `ROWS[0][0]`).
A string read by a call (`provenance.get("reasons", [])`) is a key, not a value, and is not collected.

Out of reach, review-checked, and each planted in `test_the_reader_finds_each_form_and_names_its_gaps` with a literal
the reader would collect if it reached the form, so a change that reaches one fails there until this list is updated:
- a reason built at run time: an f-string, a `.format`, a join;
- a value read through an attribute of an object or a class (`record.code`, `Record.CODE`), a dict built by a
  comprehension or by `dict()`, a container's `.get()`, or a function's return (a loop over one included);
- a starred target (`head, *rest = ...`), and an element at an index at or past a starred item (`(*HEAD, code)[1]`);
- a write through a receiver that is neither a name nor a `reasons` target
  (`provenance.setdefault("reasons", []).append(...)`), through a name bound to the list (`flags = reasons`,
  `bucket = provenance.setdefault("reasons", [])`) or through a helper's parameter (`_tag(provenance["reasons"], code)`);
- a key built at run time (`"rea" + "sons"`) or held in a module's constant (`KEY = "reasons"`);
- a call through a name assigned a function (`quarantine = _quarantine`), a lambda, a callee looked up at run time
  (`getattr(self, name)(...)`), or an object that holds a module (`module.f(...)` with `module` a parameter);
  arguments spread at a call (`f(*pair)`, `f(**{"reason": code})`) or gathered by `*args` and `**kwargs`; and a
  default named in a class body (`def _q(self, state, reason=DEFAULT)`, `DEFAULT` set in the class).
That list is what the reader is known to miss, not all it may miss: a form on neither list is unknown.

The run. An emitter module is one where the reader finds a reason, a site (forms 1 to 4) or a call that binds a reason
parameter. In each, every line that writes a reason (a site, a binding call, the line that runs each literal it
collects: its own, or the first line of a display of constants, which CPython folds into one constant loaded there) and
every line that mentions `reasons` must run: `reasons` as a name, an attribute, a keyword or a string, or a local name
tied to the list in its function, to a fixpoint, each way. Forward, a name the function assigns from an expression with
a mention in it (after `flags = reasons` or `bucket = provenance.setdefault("reasons", [])`, each line that uses `flags`
or `bucket`); back, a name held by a site's value or by what a tied name is assigned (after `"reasons": codes` or
`reasons.extend(extra)`, then `codes = sorted(pending)`, each line that uses `codes`, `extra` or `pending`). The
assignments read are =, an annotation, +=, :=, a for, with or comprehension target, and an append, extend, insert, add
or update on a name; a value holds a name as itself, a list, tuple or set display's element or starred item, an arm of
a conditional, `or` or `and`, a `+` or `|` operand, a wrapper's argument (`sorted(pending)`), a `fromkeys` call's first
argument (`dict.fromkeys(codes)`), the receiver of `keys()`, `values()` or `items()`, or a comprehension's element. A
name tied only by a read of `reasons` is tied both ways like any other, and a comprehension's names count across its
function (after `parents = [(row_id, after) for row_id, after in updates.items() if ... .get("reasons", [])]`, each
line that uses `parents`, `row_id` or `after`), so a line that cannot write a reason can be required: drive it, or
name it in UNDRIVEN. `_drive` runs those modules, traced with `sys.settrace`, and returns the codes in what it gathers
from them, and `test_the_drivers_reach_every_reason_writing_line_and_write_only_reasons_the_reader_finds` fails when
(a) a code `_drive` gathers has no words; (b) such a line runs in no driver, unless UNDRIVEN names it by function and
text with why none can (and an entry that names no unreached line, or more than one, fails); or (c) a code `_drive`
gathers is one the reader did not find in those modules, so a form the reader cannot follow fails wherever a driver
writes it where `_drive` gathers it. A module's own top level runs on import, before the trace, so its lines are read
but not required.

The guard. `test_every_function_that_mentions_reasons_is_driven_exempt_or_reads_only` holds every function under `app/`
that mentions `reasons` outside the emitter modules to EXEMPT or READS_ONLY. Some modules keep lists named `reasons`
that never reach a fact's provenance or a data note: the summary quality tier's reasons and the Copilot's quotation
checks. EXEMPT names each such site by file and function, and an exempt site must still write a reason (one find), so
an exemption cannot outlive its code. READS_ONLY names each function that reads, counts, prints or logs reasons and
writes none, held exact: each entry still mentions `reasons` and the reader finds no reason in it.

What escapes. The gate is not complete, and seven review rounds each found a form it missed. A code the reader misses
can pass only where no value `_drive` gathers holds it (a code the reader finds with no words fails the first test),
and only in one of these classes, each stated as the edge of what the gate reads, so a form not yet seen falls in one
(the first three planted among the reader's gaps and the fifth among the run's, the others by construction,
review-checked):
- a write the reader misses, on a line no driver runs that the run does not name (it names each site, binding call
  and collected literal's line, and each line that mentions `reasons` or a name tied to it, as above): a helper's
  parameter (`_tag(provenance["reasons"], code)`, the helper writing `codes.append(code)`), a function's
  return (`reasons.extend(_extra(kind))`), a closure's variable, an attribute (`holder.codes.append(code)`, then
  `provenance["reasons"] = holder.codes`);
- a key built at run time (`provenance["rea" + "sons"]`);
- what a module's top level or a class body writes, which the run reads but does not require
  (`TEMPLATE = {"reasons": [f"{SOURCE}_withheld"]}`), or holds as a key (`KEY = "reasons"`, so a function's
  `provenance[KEY] = codes` names no line);
- a function EXEMPT or READS_ONLY names whose stated reason is wrong, or any line UNDRIVEN names (each reason
  review-checked);
- a value no driver evaluates in a write a driver runs, or on a line one runs: an arm of a conditional, `or` or `and`
  (`reasons.append("period_mismatch" if late else f"period_{kind}")`), a comprehension's or generator's element over an
  iterable no driver fills (`reasons.extend(change.code for change in changes)`), or a write after a one-line `if`,
  since (b) holds lines, not the values in them; (a) and (c) catch it once a driver writes it where `_drive` gathers it;
- a value a driver writes where `_drive` does not gather it (it reads the reasons of the facts, rows and notes its
  docstring names and drops the rest, such as `_calendar_relabels`' inserts and `reconcile_facts`' rejected facts),
  since (a) and (c) read only what `_drive` returns.
Any of these whose value a driver writes where `_drive` gathers it still fails (a) or (c).
"""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.services.trend_analysis.data_notes import REASONS

APP = Path(__file__).resolve().parents[2] / "app"
WRAPPERS = frozenset({"list", "sorted", "reversed", "set", "tuple", "frozenset"})
# The calls that put a value into a list or a set: on a `reasons` target a write (form 4), on any name a binding.
LIST_METHODS = frozenset({"append", "extend", "insert", "add", "update"})
# (file under backend/, function) -> why its `reasons` never reach a data note.
EXEMPT = {
    ("app/services/summary_generation_service.py", "assess_quality"):
        "a summary's quality tier: prose reasons for the partial tier, stored on the summary, never on a fact",
    ("app/services/copilot/quotations.py", "_displayed_quotation_reasons"):
        "the Copilot's quotation checks: why a quotation was refused, never a fact's provenance",
}
# (file under backend/, function) -> why it mentions `reasons` but never writes a fact's reason. A function outside
# the emitter modules that mentions `reasons` (a name, an attribute, a keyword or a string) is here or in EXEMPT, and
# each entry still mentions it and writes no reason the reader finds: held exact, like EXEMPT.
READS_ONLY = {
    ("app/services/analysis_export_metadata.py", "fine_print_summary"):
        "prints a marked note's summary words (data_notes.note_summary) in the PDF's and the workbook's fine print",
    ("app/services/data_quality_service.py", "partial_reason_counts"):
        "counts the summary quality tier's stored reasons for the data quality report",
    ("app/services/data_quality_service.py", "summary_audit_counts"):
        "tallies the summary quality tier's reasons by SIC bucket for the audit report",
    ("app/services/excel_export_service.py", "_build_sources"):
        "prints a value's stored provenance reasons in the workbook's Sources sheet",
    ("app/services/summary_stages/finalize.py", "finalize"):
        "logs a summary's quality tier reasons",
}
# (file under backend/, function, the line's text, stripped) -> why no driver can run that reason-writing line; such a
# line is held by the reader alone. An entry must name a line the reader names and no driver runs. None today.
UNDRIVEN: dict[tuple[str, str, str], str] = {}


def _is_reasons_target(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "reasons"
    if isinstance(node, ast.Attribute):
        return node.attr == "reasons"
    return (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
            and node.slice.value == "reasons")


def _starred(items: list[ast.expr]) -> bool:
    return any(isinstance(item, ast.Starred) for item in items)


# Synthetic expressions the reader evaluates by its own rule (_values, _displays): what a loop or an unpacking binds.
ITEMS, COLUMN, ELEMENT = "__items__", "__column__", "__element__"


def _marker(name: str, *args: ast.expr) -> ast.Call:
    return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=list(args), keywords=[])


def _is_marker(expr: ast.AST, name: str) -> bool:
    return isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == name


def _pairs(target: ast.expr, value: ast.expr) -> list[tuple[ast.expr, ast.expr]]:
    """Each target an assignment binds with the value it takes. A tuple display unpacks item by item; anything else
    (a name, an attribute, a call) gives each target its element of what the value holds."""
    if not isinstance(target, (ast.Tuple, ast.List)):
        return [(target, value)]
    if _starred(target.elts):
        return []
    if isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(target.elts) and not _starred(value.elts):
        return [pair for item, held in zip(target.elts, value.elts) for pair in _pairs(item, held)]
    return [pair for index, item in enumerate(target.elts)
            for pair in _pairs(item, _marker(ELEMENT, value, ast.Constant(index)))]


def _loop_pairs(target: ast.expr, iterable: ast.expr) -> list[tuple[ast.expr, ast.expr]]:
    """Each target a loop binds with an expression that holds every item it takes: a name takes the iterable's items, a
    tuple target its columns (each row unpacked as an assignment would), over enumerate() and zip() item by item."""
    if not isinstance(target, (ast.Tuple, ast.List)):
        return [(target, _marker(ITEMS, iterable))]
    if _starred(target.elts):
        return []
    if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name) and iterable.args:
        if iterable.func.id == "enumerate" and len(target.elts) == 2:
            return _loop_pairs(target.elts[1], iterable.args[0])
        if iterable.func.id == "zip" and len(iterable.args) == len(target.elts) and not _starred(iterable.args):
            return [pair for item, held in zip(target.elts, iterable.args) for pair in _loop_pairs(item, held)]
    return [pair for index, item in enumerate(target.elts)
            for pair in _pairs(item, _marker(COLUMN, iterable, ast.Constant(index)))]


def _assigned(body: list[ast.stmt]) -> dict[str, list[ast.expr]]:
    """Every value a name is given in one scope, nested functions and classes left to their own scopes."""
    names: dict[str, list[ast.expr]] = {}

    def bind(pairs: list[tuple[ast.expr, ast.expr]]) -> None:
        for target, value in pairs:
            if isinstance(target, ast.Name):
                names.setdefault(target.id, []).append(value)

    stack = list(body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                bind(_pairs(target, node.value))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and node.value is not None:
            bind(_pairs(node.target, node.value))
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            bind(_loop_pairs(node.target, node.iter))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in LIST_METHODS
              and isinstance(node.func.value, ast.Name) and node.args):
            # checks.extend(codes), seen.update(codes): the name holds what the argument holds. checks.append(code),
            # checks.insert(0, code), seen.add(code): a one-element display of it, so a loop takes it as one row.
            if node.func.attr in {"extend", "update"}:
                bind([(node.func.value, node.args[0])])
            else:
                put = node.args[-1] if node.func.attr == "insert" else node.args[0]
                bind([(node.func.value, ast.List(elts=[put], ctx=ast.Load()))])
        stack.extend(ast.iter_child_nodes(node))
    return names


def _module_name(path: str) -> str:
    parts = path.removesuffix(".py").split("/")
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imports(tree: ast.Module, path: str, modules: set[str]) -> dict[str, tuple[str, str | None]]:
    """Each name a module imports: (module, attribute), the attribute None where the name is a module itself."""
    package = _module_name(path) if path.endswith("/__init__.py") else _module_name(path).rpartition(".")[0]
    found: dict[str, tuple[str, str | None]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = package.split(".")[:len(package.split(".")) - node.level + 1]
                base = ".".join([*anchor, *([node.module] if node.module else [])])
            for alias in node.names:
                full = f"{base}.{alias.name}"
                found[alias.asname or alias.name] = (full, None) if full in modules else (base, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    found[alias.asname] = (alias.name, None)
                else:
                    found[alias.name.split(".")[0]] = (alias.name.split(".")[0], None)
    return found


class _Scope:
    """A function's names, or a module's: what each name holds, and where to read a name it does not bind."""

    def __init__(self, path: str, name: str, function: ast.AST | None, body: list[ast.stmt],
                 imports: dict[str, tuple[str, str | None]], registry: dict[str, _Scope],
                 parent: _Scope | None = None):
        self.path, self.name, self.imports, self.registry = path, name, imports, registry
        # The enclosing function's scope, or the module's; a module has none.
        self.parent = parent
        self.module_scope: _Scope = parent.module_scope if parent is not None else self
        self.params: list[str] = []
        self.defaults: dict[str, ast.expr] = {}
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = function.args
            positional = [*arguments.posonlyargs, *arguments.args]
            # *args and **kwargs shadow an outer name too, though a call binds neither (out of reach).
            self.params = [arg.arg for arg in [*positional, *arguments.kwonlyargs,
                                                *filter(None, (arguments.vararg, arguments.kwarg))]]
            self.defaults = dict(zip([arg.arg for arg in positional[len(positional) - len(arguments.defaults):]],
                                     arguments.defaults))
            self.defaults.update((arg.arg, default) for arg, default in zip(arguments.kwonlyargs, arguments.kw_defaults)
                                 if default is not None)
        self.local = _assigned(body)
        self.classes = {node.name for node in body if isinstance(node, ast.ClassDef)}
        # A module's literals in displays of constants, by id, with the line that runs them (_folded).
        self.folded: dict[int, int] = {}


def _constant_display(node: ast.AST) -> bool:
    return isinstance(node, (ast.List, ast.Tuple, ast.Set)) and all(
        isinstance(elt, ast.Constant) or _constant_display(elt) for elt in node.elts)


def _folded(tree: ast.Module) -> dict[int, int]:
    """Each literal in a display of constants, by id, with the display's first line. CPython folds such a display into
    one constant loaded at that line, so a literal's own line never runs: a list of three codes over three lines runs
    on its first line alone."""
    lines: dict[int, int] = {}
    stack: list[ast.AST] = [tree]
    while stack:
        node = stack.pop()
        if _constant_display(node):
            lines.update((id(leaf), node.lineno) for leaf in ast.walk(node) if isinstance(leaf, ast.Constant))
        else:
            stack.extend(ast.iter_child_nodes(node))
    return lines


def _shadowed(name: str, scope: _Scope) -> bool:
    """Whether a function on the way out to the module binds the name, so it is not the module's own."""
    while scope.parent is not None:
        if name in scope.params or name in scope.local:
            return True
        scope = scope.parent
    return False


def _module_of(expr: ast.AST, scope: _Scope) -> str | None:
    """The module an expression names: an imported module, or a dotted attribute of one under `app/`."""
    if isinstance(expr, ast.Name):
        if _shadowed(expr.id, scope):
            return None
        module, attribute = scope.module_scope.imports.get(expr.id, (None, None))
        return module if module is not None and attribute is None else None
    if isinstance(expr, ast.Attribute):
        parent = _module_of(expr.value, scope)
        dotted = f"{parent}.{expr.attr}"
        if parent is not None and (dotted in scope.registry or any(
                name.startswith(f"{dotted}.") for name in scope.registry)):
            return dotted
    return None


Binding = tuple[ast.expr, _Scope, object, dict]


def _resolve(name: str, scope: _Scope, flows: set[tuple[str, str, str]], seen: frozenset, bound: dict) -> list[Binding]:
    """What a name may hold: each expression with the scope and loop names to read it in, and its cycle key."""
    if name in bound:
        key = ("loop", id(bound[name]))
        return [] if key in seen else [(held, scope, key, bound) for held in bound[name]]
    key = (id(scope), name)
    if key in seen:
        return []
    bindings: list[Binding] = []
    if name in scope.params:
        # A parameter flows even where its function rebinds it (codes = list(codes)); its default is read where the
        # function is defined.
        flows.add((scope.path, scope.name, name))
        if name in scope.defaults and scope.parent is not None:
            bindings.append((scope.defaults[name], scope.parent, key, {}))
    bindings += [(held, scope, key, {}) for held in scope.local.get(name, [])]
    if name in scope.params or name in scope.local:
        return bindings
    if scope.parent is not None:
        return _resolve(name, scope.parent, flows, seen, {})
    source, attribute = scope.imports.get(name, (None, None))
    if attribute is not None and source in scope.registry:
        return _resolve(attribute, scope.registry[source], flows, seen | {key}, {})
    return []


# A string the reader collects: the code, and where its literal is (file, function, line; no line at module level, which
# runs on import rather than in a driver).
Hit = tuple[str, str, str, int | None]
DICT_VIEWS = frozenset({"keys", "values", "items"})


def _displays(expr: ast.AST | None, scope: _Scope, flows: set[tuple[str, str, str]], seen: frozenset,
              bound: dict) -> list[tuple[ast.expr, _Scope, frozenset, dict]]:
    """The list, tuple, set and dict displays an expression may hold, each with the scope to read it in: through names,
    imports, conditions, `+`, the calls that keep a container (list(), sorted() ...), a dict's keys(), values() and
    items() (as a list display), and an element or a column of another display."""
    def again(item: ast.AST | None, where: _Scope = scope, s: frozenset = seen, b: dict = bound) -> list:
        return _displays(item, where, flows, s, b)

    if isinstance(expr, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return [(expr, scope, seen, bound)]
    if isinstance(expr, ast.Name):
        return [found for value, where, key, inner in _resolve(expr.id, scope, flows, seen, bound)
                for found in again(value, where, seen | {key}, inner)]
    if isinstance(expr, ast.Attribute):
        module = _module_of(expr.value, scope)
        if module not in scope.registry:
            return []
        return [found for value, where, key, inner in _resolve(expr.attr, scope.registry[module], flows, seen, {})
                for found in again(value, where, seen | {key}, inner)]
    if isinstance(expr, ast.IfExp):
        return again(expr.body) + again(expr.orelse)
    if isinstance(expr, ast.BoolOp):
        return [found for value in expr.values for found in again(value)]
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.Add, ast.BitOr)):
        return again(expr.left) + again(expr.right)
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id in WRAPPERS and expr.args:
        return again(expr.args[0])
    if (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr in DICT_VIEWS
            and not expr.args):
        views = []
        for display, where, s, b in again(expr.func.value):
            if isinstance(display, ast.Dict):
                pairs = [(key, value) for key, value in zip(display.keys, display.values) if key is not None]
                elts = [key if expr.func.attr == "keys" else value if expr.func.attr == "values"
                        else ast.Tuple(elts=[key, value], ctx=ast.Load()) for key, value in pairs]
                views.append((ast.List(elts=elts, ctx=ast.Load()), where, s, b))
                # {**BASE, ...}: BASE's own view, read where BASE is.
                views += [view for key, value in zip(display.keys, display.values) if key is None
                          for view in again(ast.Call(func=ast.Attribute(value=value, attr=expr.func.attr, ctx=ast.Load()),
                                                     args=[], keywords=[]), where, s, b)]
        return views
    if isinstance(expr, ast.Subscript):
        return [found for display, where, s, b in again(expr.value)
                for value in _subscripted(display, expr.slice) for found in again(value, where, s, b)]
    if _is_marker(expr, ELEMENT) or _is_marker(expr, COLUMN):
        return [found for part, where, s, b in _parts(expr, scope, flows, seen, bound)
                for found in again(part, where, s, b)]
    return []


def _items(expr: ast.AST | None, scope: _Scope, flows: set[tuple[str, str, str]], seen: frozenset,
           bound: dict) -> list[tuple[ast.expr, _Scope, frozenset, dict]]:
    """Each item iterating an expression yields: a list, tuple or set display's elements, a dict display's keys, and
    the items of a starred element (`(*HEAD_ROWS, row)`) or a `**` entry (`{**BASE, key: value}`)."""
    found: list[tuple[ast.expr, _Scope, frozenset, dict]] = []
    for display, where, s, b in _displays(expr, scope, flows, seen, bound):
        pairs = (zip(display.keys, display.values) if isinstance(display, ast.Dict)
                 else ((elt, elt.value if isinstance(elt, ast.Starred) else None) for elt in display.elts))
        for item, spread in pairs:
            if item is None or isinstance(item, ast.Starred):
                found += _items(spread, where, flows, s, b)
            else:
                found.append((item, where, s, b))
    return found


def _at(display: ast.List | ast.Tuple, index: object) -> ast.expr | None:
    """A list's or tuple's element at a constant index, or None: not an int, out of range, or at or past a starred
    item, whose length the reader does not know."""
    if not isinstance(index, int) or isinstance(index, bool) or not -len(display.elts) <= index < len(display.elts):
        return None
    span = display.elts[:index + 1] if index >= 0 else display.elts[index:]
    return None if _starred(span) else display.elts[index]


def _subscripted(display: ast.expr, index: ast.expr) -> list[ast.expr]:
    """What `display[index]` may be: every value of a dict display (and of a `**` entry's mapping), or a list's or
    tuple's element at a constant index."""
    if isinstance(display, ast.Dict):
        return [value if key is not None else ast.Subscript(value=value, slice=index, ctx=ast.Load())
                for key, value in zip(display.keys, display.values)]
    if isinstance(display, (ast.List, ast.Tuple)) and isinstance(index, ast.Constant):
        element = _at(display, index.value)
        return [element] if element is not None else []
    return []


def _parts(marker: ast.Call, scope: _Scope, flows: set[tuple[str, str, str]], seen: frozenset,
           bound: dict) -> list[tuple[ast.expr, _Scope, frozenset, dict]]:
    """An ELEMENT marker's element of each tuple or list its value holds, or a COLUMN marker's element of each row its
    iterable yields."""
    source, index = marker.args[0], marker.args[1].value
    rows = ([(source, scope, seen, bound)] if _is_marker(marker, ELEMENT)
            else _items(source, scope, flows, seen, bound))
    return [(row.elts[index], where, s, b) for item, at, rs, rb in rows
            for row, where, s, b in _displays(item, at, flows, rs, rb)
            if isinstance(row, (ast.Tuple, ast.List)) and index < len(row.elts)
            and not isinstance(row.elts[index], ast.Starred)]


def _values(expr: ast.AST | None, scope: _Scope, flows: set[tuple[str, str, str]], seen: frozenset = frozenset(),
            bound: dict | None = None) -> set[Hit]:
    """The string literals `expr` may hold as a reason, each with where it is written; a parameter it reads joins
    `flows`."""
    bound = {} if bound is None else bound

    def read(item: ast.AST | None) -> set[Hit]:
        return _values(item, scope, flows, seen, bound)

    def held(bindings: list) -> set[Hit]:
        return set().union(*(_values(value, where, flows, seen | {key}, inner)
                             for value, where, key, inner in bindings))

    if expr is None:
        return set()
    if isinstance(expr, ast.Constant):
        # The line that runs when the literal is read: its own, or the first line of the constant display that holds
        # it (_folded). None at module level, which runs on import rather than in a driver.
        line = scope.module_scope.folded.get(id(expr), expr.lineno) if scope.parent is not None else None
        return {(expr.value, scope.path, scope.name, line)} if isinstance(expr.value, str) else set()
    if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        return set().union(*(read(elt) for elt in expr.elts))
    if isinstance(expr, ast.Starred):
        return read(expr.value)
    if isinstance(expr, ast.IfExp):
        return read(expr.body) | read(expr.orelse)
    if isinstance(expr, ast.BoolOp):
        return set().union(*(read(value) for value in expr.values))
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.Add, ast.BitOr)):
        return read(expr.left) | read(expr.right)
    if _is_marker(expr, ITEMS):
        # A loop's name takes what the iterable holds: each item, a dict display's keys included.
        return read(expr.args[0]) | set().union(*(
            _values(item, where, flows, s | {("item", id(item))}, b)
            for item, where, s, b in _items(expr.args[0], scope, flows, seen, bound)))
    if _is_marker(expr, ELEMENT) or _is_marker(expr, COLUMN):
        return set().union(*(_values(part, where, flows, s, b)
                             for part, where, s, b in _parts(expr, scope, flows, seen, bound)))
    if isinstance(expr, ast.Call) and expr.args and (
        (isinstance(expr.func, ast.Name) and expr.func.id in WRAPPERS)
        or (isinstance(expr.func, ast.Attribute) and expr.func.attr == "fromkeys")
    ):
        return read(expr.args[0])
    if (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr in DICT_VIEWS
            and not expr.args):
        return set().union(*(_values(item, where, flows, s, b)
                             for item, where, s, b in _items(expr, scope, flows, seen, bound)))
    if isinstance(expr, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        inner = dict(bound)
        for generator in expr.generators:
            loop: dict[str, list[ast.expr]] = {
                node.id: [] for node in ast.walk(generator.target) if isinstance(node, ast.Name)}
            for target, value in _loop_pairs(generator.target, generator.iter):
                if isinstance(target, ast.Name):
                    loop[target.id].append(value)
            inner.update(loop)
        return _values(expr.elt, scope, flows, seen, inner)
    if isinstance(expr, ast.Name):
        return held(_resolve(expr.id, scope, flows, seen, bound))
    if isinstance(expr, ast.Attribute):
        module = _module_of(expr.value, scope)
        return held(_resolve(expr.attr, scope.registry[module], flows, seen, {})) if module in scope.registry else set()
    if isinstance(expr, ast.Subscript):
        # A dict display's every value (fallback[kind]); a list or tuple display's element at a constant index, through
        # nested subscripts too (ROWS[0][0]).
        return set().union(*(_values(value, where, flows, s, b)
                             for display, where, s, b in _displays(expr.value, scope, flows, seen, bound)
                             for value in _subscripted(display, expr.slice)))
    return set()


def _sites(node: ast.AST) -> list[ast.AST]:
    """The expressions written into a reasons list at this node (forms 1 to 4)."""
    if isinstance(node, ast.Dict):
        return [value for key, value in zip(node.keys, node.values)
                if isinstance(key, ast.Constant) and key.value == "reasons"]
    if isinstance(node, ast.Call):
        found = [keyword.value for keyword in node.keywords if keyword.arg == "reasons"]
        if (isinstance(node.func, ast.Attribute) and node.func.attr in LIST_METHODS
                and _is_reasons_target(node.func.value)):
            found += node.args
        return found
    if isinstance(node, ast.Assign):
        return [value for target in node.targets for item, value in _pairs(target, node.value)
                if _is_reasons_target(item)]
    if isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and node.value is not None:
        return [value for item, value in _pairs(node.target, node.value) if _is_reasons_target(item)]
    return []


def _walk_scopes(tree: ast.Module, module: _Scope):
    """Each node with the scope it is read in: its innermost function, or the module. A function's scope encloses the
    functions defined in it; a class body encloses nothing, as in Python."""
    stack: list[tuple[ast.AST, _Scope]] = [(tree, module)]
    while stack:
        node, scope = stack.pop()
        for child in ast.iter_child_nodes(node):
            inner = scope
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = _Scope(module.path, child.name, child, child.body, module.imports, module.registry, scope)
            yield child, inner
            stack.append((child, inner))


def _method_kinds(tree: ast.Module) -> dict[int, str]:
    """Each function in a class body: "static", "class" or "instance", by its decorator."""
    kinds: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    named = {decorator.id for decorator in item.decorator_list if isinstance(decorator, ast.Name)}
                    kinds[id(item)] = ("static" if "staticmethod" in named
                                       else "class" if "classmethod" in named else "instance")
    return kinds


def _receiver(func: ast.expr, scope: _Scope) -> str:
    """How a call names its callee: a bare "name", a "module"'s attribute, a "class"'s or any other "object"'s."""
    if not isinstance(func, ast.Attribute):
        return "name"
    value = func.value
    if _module_of(value, scope) is not None:
        return "module"
    if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "type"
            and len(value.args) == 1) or (isinstance(value, ast.Attribute) and value.attr == "__class__"):
        return "class"  # type(self)._quarantine(self, ...), self.__class__._quarantine(self, ...)
    if isinstance(value, ast.Attribute):
        owner = _module_of(value.value, scope)
        if owner in scope.registry and value.attr in scope.registry[owner].classes:
            return "class"  # module.Repair._quarantine(repair, ...)
    if isinstance(value, ast.Name) and not _shadowed(value.id, scope):
        source, attribute = scope.module_scope.imports.get(value.id, (None, None))
        if value.id in scope.module_scope.classes or (
                source in scope.registry and attribute in scope.registry[source].classes):
            return "class"
    return "object"


# The positional parameters a call skips, by what it calls and how it names it; absent where such a call cannot reach
# the definition. A method's `self` is bound by an object and passed through its class; `cls` is bound by both.
SKIPPED = {
    ("function", "name"): 0, ("function", "module"): 0,
    ("static", "class"): 0, ("static", "object"): 0,
    ("class", "class"): 1, ("class", "object"): 1,
    ("instance", "class"): 0, ("instance", "object"): 1,
}


def _callee(func: ast.expr, receiver: str, scope: _Scope, defines: dict[str, set[str]],
            free: dict[str, set[str]]) -> tuple[str, str | None] | None:
    """The name a call reaches and the file it must be defined in (None: any file), or None for a call that reaches no
    function under `app/`: one into an outside module, or a callee the reader cannot name. A bare name reaches its own
    module's function first, as Python's lookup does (`free`: each file's functions outside a class body)."""
    home = None
    if isinstance(func, ast.Name):
        name = func.id
        source, attribute = scope.module_scope.imports.get(name, (None, None))
        if name in free.get(scope.path, set()):
            home = scope.path  # job_run_service's _finish(...) is its own, never data_notes._finish
        elif attribute is not None and not _shadowed(name, scope):
            if source not in scope.registry:
                return None
            name, home = attribute, scope.registry[source].path  # from app.x import f as g; g(...)
    elif isinstance(func, ast.Attribute):
        name = func.attr
        if receiver == "module":
            module = _module_of(func.value, scope)
            if module not in scope.registry:
                return None  # json.dumps(...): never an app function of that name
            home = scope.registry[module].path
    else:
        return None
    # A module that only re-exports the name defines nothing of it: any file's definition may be the one.
    return name, home if home is not None and name in defines.get(home, set()) else None


def read_reasons(sources: dict[str, str]) -> tuple[dict[tuple[str, str], set[str]], dict[tuple[str, str], set[int]]]:
    """Every string each (file, function) can write into a reasons list (forms 1 to 5), and each function's
    reason-writing lines: a site (forms 1 to 4), a call that binds a parameter that flows, and a literal collected."""
    trees = {path: ast.parse(source) for path, source in sources.items()}
    modules = {_module_name(path) for path in trees}
    registry: dict[str, _Scope] = {}
    for path, tree in trees.items():
        registry[_module_name(path)] = _Scope(path, "<module>", None, tree.body, _imports(tree, path, modules), registry)
        registry[_module_name(path)].folded = _folded(tree)
    nodes = [(node, scope) for path, tree in trees.items()
             for node, scope in _walk_scopes(tree, registry[_module_name(path)])]
    kinds = {key: kind for tree in trees.values() for key, kind in _method_kinds(tree).items()}
    # A function's or method's name -> (its positional parameters, "function" or the method's kind, its file).
    definitions: dict[str, list[tuple[list[str], str, str]]] = {}
    defines: dict[str, set[str]] = {}
    free: dict[str, set[str]] = {}
    for node, scope in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = node.args
            definitions.setdefault(node.name, []).append(
                ([arg.arg for arg in [*arguments.posonlyargs, *arguments.args]], kinds.get(id(node), "function"),
                 scope.path))
            defines.setdefault(scope.path, set()).add(node.name)
            if id(node) not in kinds:
                free.setdefault(scope.path, set()).add(node.name)
    found: dict[tuple[str, str], set[str]] = {}
    lines: dict[tuple[str, str], set[int]] = {}
    flowing: set[tuple[str, str, str]] = set()  # (file, function name, parameter) that reach a reasons list

    def collect(expr: ast.AST, scope: _Scope, line: int) -> None:
        flows: set[tuple[str, str, str]] = set()
        hits = _values(expr, scope, flows)
        if hits:
            found.setdefault((scope.path, scope.name), set()).update(code for code, *_where in hits)
        if scope.parent is not None:
            lines.setdefault((scope.path, scope.name), set()).add(line)
        for _code, path, function, at in hits:
            if at is not None:
                lines.setdefault((path, function), set()).add(at)
        flowing.update(flows)

    for node, scope in nodes:
        for expr in _sites(node):
            collect(expr, scope, node.lineno)
    calls = [(node, scope) for node, scope in nodes if isinstance(node, ast.Call)]
    while True:
        before = len(flowing)
        for node, scope in calls:
            receiver = _receiver(node.func, scope)
            reached = _callee(node.func, receiver, scope, defines, free)
            if reached is None:
                continue
            callee, home = reached
            for params, kind, path in definitions.get(callee, []):
                if (kind, receiver) not in SKIPPED or (home is not None and path != home):
                    continue
                positional = params[SKIPPED[kind, receiver]:]
                for index, argument in enumerate(node.args):
                    if index < len(positional) and (path, callee, positional[index]) in flowing:
                        collect(argument, scope, node.lineno)
                for keyword in node.keywords:
                    if (path, callee, keyword.arg) in flowing:
                        collect(keyword.value, scope, node.lineno)
        if len(flowing) == before:
            break
    return found, lines


def written_reasons(sources: dict[str, str]) -> dict[tuple[str, str], set[str]]:
    """Every string each (file, function) can write into a reasons list, forms 1 to 5."""
    return read_reasons(sources)[0]


def _app_sources() -> dict[str, str]:
    return {f"app/{path.relative_to(APP).as_posix()}": path.read_text(encoding="utf-8") for path in APP.rglob("*.py")}


def _mention(node: ast.AST, aliases: set[str]) -> bool:
    """Whether a node names the list: `reasons` as a name, an attribute, a keyword or a string, or a name tied to it."""
    return ((isinstance(node, ast.Name) and (node.id == "reasons" or node.id in aliases))
            or (isinstance(node, ast.Attribute) and node.attr == "reasons")
            or (isinstance(node, ast.Constant) and node.value == "reasons")
            or (isinstance(node, ast.keyword) and node.arg == "reasons"))


def _held(expr: ast.AST) -> set[str]:
    """The names a value holds: the value itself, a list, tuple or set display's element or starred item, an arm of a
    conditional, `or` or `and`, a `+` or `|` operand, a wrapper's argument, a `fromkeys` call's first argument
    (`dict.fromkeys(codes)`), the receiver of `keys()`, `values()` or `items()`, and a comprehension's element. Any
    other position holds none: a dict display, a subscript, an attribute, an f-string, another call's argument."""
    if isinstance(expr, ast.Name):
        return {expr.id}
    if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        return set().union(*(_held(elt) for elt in expr.elts))
    if isinstance(expr, ast.Starred):
        return _held(expr.value)
    if isinstance(expr, ast.IfExp):
        return _held(expr.body) | _held(expr.orelse)
    if isinstance(expr, ast.BoolOp):
        return set().union(*(_held(value) for value in expr.values))
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.Add, ast.BitOr)):
        return _held(expr.left) | _held(expr.right)
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id in WRAPPERS and expr.args:
        return _held(expr.args[0])
    if (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "fromkeys"
            and expr.args):
        return _held(expr.args[0])
    if (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr in DICT_VIEWS
            and not expr.args):
        return _held(expr.func.value)
    if isinstance(expr, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        return _held(expr.elt)
    return set()


def _assignments(node: ast.AST) -> list[tuple[set[str], ast.expr]]:
    """The names a node assigns, with the value they take: an assignment (plain, annotated, augmented or a walrus), a
    for, with or comprehension target, and an append, extend, insert, add or update on a name (its argument, as
    _assigned reads it). A target gives a name, or each name a tuple or list unpacks into; a subscript or attribute
    target (`updates[row_id] = state`) gives none."""
    def names(target: ast.expr) -> set[str]:
        if isinstance(target, ast.Name):
            return {target.id}
        if isinstance(target, (ast.Tuple, ast.List, ast.Starred)):
            return {name.id for name in ast.walk(target)
                    if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Store)}
        return set()

    if isinstance(node, ast.Assign):
        return [(names(target), node.value) for target in node.targets]
    if isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and node.value is not None:
        return [(names(node.target), node.value)]
    if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
        return [(names(node.target), node.iter)]
    if isinstance(node, ast.withitem) and node.optional_vars is not None:
        return [(names(node.optional_vars), node.context_expr)]
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in LIST_METHODS
            and isinstance(node.func.value, ast.Name) and node.args):
        return [({node.func.value.id}, node.args[-1] if node.func.attr == "insert" else node.args[0])]
    return []


def _mentions(sources: dict[str, str]) -> dict[tuple[str, str], set[int | None]]:
    """Each (file, function) whose body mentions `reasons` ("<module>" for a module or class body) and the lines that run
    each mention (_folded; None at module level). A mention is `reasons` as a name, an attribute, a keyword or a string,
    or a local name tied to the list in the same function, to a fixpoint, each way: a name assigned from an expression
    with a mention in it (after `flags = reasons` or `bucket = provenance.setdefault("reasons", [])`, each line that
    uses `flags` or `bucket` is one), and a name held (_held) by a site's value or by what a tied name is assigned
    (after `"reasons": codes` or `reasons.extend(extra)`, each line that uses `codes` or `extra`), the assignments read
    by _assignments. A line that names neither `reasons` nor a tied name has none: a write through an attribute of an
    untied name (`holder.codes.append(code)`), or through a name its function neither assigns from such an expression
    nor stores into one (a helper's parameter, a function's return, a closure's variable), or through a key built at
    run time or held in a module's constant."""
    found: dict[tuple[str, str], set[int | None]] = {}
    for path, source in sources.items():
        tree = ast.parse(source)
        folded = _folded(tree)
        # Each node with its innermost function (None for the module and class bodies).
        owned: dict[ast.AST | None, list[ast.AST]] = {}
        stack: list[tuple[ast.AST, ast.AST | None]] = [(tree, None)]
        while stack:
            node, function = stack.pop()
            for child in ast.iter_child_nodes(node):
                owned.setdefault(function, []).append(child)
                stack.append((child, child if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else function))
        for function, nodes in owned.items():
            aliases: set[str] = set()
            if function is not None:
                bindings = [binding for node in nodes for binding in _assignments(node)]
                # What a site writes into the list: `codes` in `"reasons": codes`, `extra` in `reasons.extend(extra)`.
                aliases = set().union(*(_held(value) for node in nodes for value in _sites(node)))
                while True:
                    # Forward, a name assigned from a mention holds the list; back, what a tied name is assigned goes
                    # into it.
                    tied = {name for names, value in bindings
                            if any(_mention(item, aliases) for item in ast.walk(value)) for name in names}
                    tied |= {name for names, value in bindings if names & aliases for name in _held(value)}
                    if tied <= aliases:
                        break
                    aliases |= tied
            name = function.name if function is not None else "<module>"
            for node in nodes:
                if _mention(node, aliases):
                    line = folded.get(id(node), node.lineno) if function is not None else None
                    found.setdefault((path, name), set()).add(line)
    return found


def _emitter_modules(found: dict, lines: dict) -> set[str]:
    """The modules where the reader finds a reason, a reason site or a call that binds one, outside EXEMPT and
    READS_ONLY: the modules the runtime half drives."""
    return {path for path, function in {*found, *lines} if (path, function) not in EXEMPT.keys() | READS_ONLY.keys()}


def test_every_reason_the_backend_writes_has_words():
    found = written_reasons(_app_sources())
    exempt = {site for site in found if site in EXEMPT}
    assert exempt == set(EXEMPT), f"an exemption no longer writes a reason: {sorted(set(EXEMPT) - exempt)}"
    missing = sorted((code, site) for site, codes in found.items() if site not in EXEMPT
                     for code in codes if code not in REASONS)
    assert missing == [], (
        "a reason the backend writes has no words in data_notes.REASONS (and provenance.ts REASONS, which the shared "
        f"notes fixture holds equal), so it would read the generic fallback: {missing}"
    )


def test_every_function_that_mentions_reasons_is_driven_exempt_or_reads_only():
    """A write in a form the reader misses usually still names the list somewhere in its function. So every function
    under app/ that mentions `reasons` is in an emitter module, whose every mention line the runtime half must run, or
    in EXEMPT, or in READS_ONLY, which is held exact and finds no reason. A write that names the list nowhere in its
    function (the header's escapes) is outside this guard."""
    sources = _app_sources()
    found, lines = read_reasons(sources)
    emitters = _emitter_modules(found, lines)
    outside = {site for site in _mentions(sources) if site[0] not in emitters and site not in EXEMPT}
    assert sorted(outside ^ READS_ONLY.keys()) == [], (
        "a function outside the emitter modules mentions reasons (drive its module in _drive, or name it in READS_ONLY "
        "with why it writes no fact's reason), or a READS_ONLY entry no longer does"
    )
    assert sorted((site, codes) for site, codes in found.items() if site in READS_ONLY and codes) == [], (
        "a READS_ONLY function writes a reason the reader finds: give it words, or name it in EXEMPT"
    )


def _drive(monkeypatch) -> set[str]:
    """Run every emitter module the reader names through each line that writes or reads a reason, and return the codes
    in what it gathers, not all they write (`_calendar_relabels`' inserts and `reconcile_facts`' rejected facts are
    dropped, for two): facts/reconcile's soft checks and companyfacts cross-check and facts/lineage's calculation
    checks over one filing's batch (with and without initialize_reported), fact_provenance's legacy projections,
    data_notes' fallbacks, summary words and a citation supplement, quarterly_fact_repair's calendar relabels (pure)
    and its repair, reported EPS and rollback, and filing_lineage_repair's backfill of each outcome, all on in-memory
    SQLite databases."""
    from collections.abc import Iterator
    from contextlib import contextmanager
    from decimal import Decimal

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.database import Base
    from app.models import Company, FinancialFact
    from app.services import quarterly_fact_repair as repair
    from app.services.fact_provenance import provenance_for_fact, reported_provenance
    from app.services.facts.lineage import annotate_filing_calculations
    from app.services import filing_lineage_repair as lineage_repair
    from app.services.facts.reconcile import cross_check_facts, reconcile_facts
    from app.services.trend_analysis.data_notes import citation_data_notes, data_notes, note_summary
    from tests.unit.test_filing_lineage_repair import HOLDS, _company, _margin, _seed_hold
    from tests.unit.test_quarterly_fact_repair import candidate, fact as repair_fact, normalizer, payload

    def reasons(provenance: dict | None) -> set[str]:
        return set((provenance or {}).get("reasons", []))

    def fact(concept: str, value: float, raw_tag: str | None = "us-gaap:Probe", unit: str = "USD") -> dict:
        return {"company_id": 1, "concept": concept, "value": value, "unit": unit, "period_start": None,
                "period_end": date(2024, 12, 31), "fiscal_year": 2024, "fiscal_period": "FY",
                "accession": "0000000001-25-000001", "raw_tag": raw_tag, "source": "companyfacts"}

    batch = [
        fact("revenue", 0.0),  # zero where the prior period was not zero
        fact("net_income", 5000.0),  # 500 times the prior period's
        fact("earnings_per_share", -1.0, unit="USD/shares"),  # opposite sign to net income
        fact("eps_diluted", 2.0, unit="USD/shares"),  # above basic EPS
        fact("current_assets", 300.0), fact("current_liabilities", 100.0),
        fact("working_capital", 999.0, raw_tag=None),  # not current assets less current liabilities
        fact("net_margin", 5.0, raw_tag=None),  # a flow with no period start: its inputs cannot be matched
    ]
    # The period ends a day after the filing's report date, so every figure in it also has a period mismatch.
    accepted, _ = reconcile_facts(batch, prior_values={"revenue": 100.0, "net_income": 10.0},
                                  period_of_report=date(2024, 12, 30))
    codes = set().union(*(reasons(item["provenance"]) for item in accepted))
    codes |= set().union(*(reasons(item["provenance"])
                           for item in annotate_filing_calculations(batch, initialize_reported=True)))
    # companyfacts replaces the revenue: the source check's audit keeps the reasons it resolved.
    codes |= set().union(*(reasons(item["provenance"])
                           for item in cross_check_facts(accepted, {("revenue", date(2024, 12, 31)): 1.0})))
    legacy = [
        SimpleNamespace(concept="revenue", raw_tag="us-gaap:Revenues", source="companyfacts", reconciled=False),
        SimpleNamespace(concept="net_margin", raw_tag=None, source="derived", reconciled=True),
        SimpleNamespace(concept="eps_basic", raw_tag=None, source="derived", reconciled=True),
    ]
    codes |= set().union(*(reasons(provenance_for_fact(row)) for row in legacy))
    # With a CIK, a reported value's record gains its filing's links.
    codes |= reasons(provenance_for_fact(SimpleNamespace(
        concept="revenue", raw_tag="us-gaap:Revenues", source="companyfacts", reconciled=True,
        accession="0000000001-25-000001"), cik="1"))
    codes |= reasons(reported_provenance({"reconciled": False}))
    dataset = {"mode": "annual", "period_key": "FY2024", "periods": [{"key": "FY2024"}], "series": [
        {"concept": "revenue", "label": "Revenue",
         "points": [{"period": "FY2024", "value": 1.0, "provenance": {"validation": "needs_review", "reasons": []}}]},
        {"concept": "net_income", "label": "Net income", "points": [{"period": "FY2024", "value": 1.0}]},
        {"concept": "free_cash_flow", "label": "Free cash flow", "points": [{"period": "FY2024", "value": None}]},
    ]}
    report = data_notes(dataset)
    combined = citation_data_notes([{"value": 1.0, "provenance": {"validation": "needs_review", "reasons": []}},
                                    {"value": 1.0, "provenance": None}], report)
    codes |= {code for note in combined["notes"] for code in note["reasons"]}
    assert note_summary(["legacy_calculation", "source_check_needed"])

    # The calendar relabels: a rolling twelve months filed as a fiscal year, a quarter filed under another quarter's
    # label, and a calculation in the old scope of that quarter's input.
    rolling = {"company_id": 1, "filing_id": None, "concept": "operating_cash_flow", "raw_tag": "us-gaap:X",
               "unit": "USD", "period_start": "2024-04-01", "period_end": "2025-03-31", "fiscal_year": 2025,
               "fiscal_period": "FY", "value": 80.0, "form": "10-K", "accession": "A", "source": "companyfacts",
               "reconciled": True, "is_latest": True, "provenance": None}
    relabelled = {**rolling, "concept": "revenue", "raw_tag": "us-gaap:Rev", "period_start": "2025-01-01",
                  "fiscal_period": "Q4", "value": 10.0}
    child = {**relabelled, "concept": "net_margin", "raw_tag": None, "source": "derived"}
    # The quarter's corrected label is already stored, so the relabel admits that row as its replacement.
    stored = {**relabelled, "fiscal_period": "Q1", "is_latest": False}
    exclusion = {key: rolling[key] for key in ("concept", "raw_tag", "period_start", "period_end", "accession", "unit")}
    updates, _inserts = repair._calendar_relabels(
        {1: rolling, 2: relabelled, 3: child, 4: stored}, [{**relabelled, "fiscal_period": "Q1"}],
        {"calendar_exclusions": [{**exclusion, "reason": "rolling_duration_not_fiscal_year"}]})
    codes |= set().union(*(reasons(state.get("provenance")) for state in updates.values()))

    # The repair quarantines a calculation whose inputs a filing proves incompatible, and a rollback leaves what the
    # repair inserted unavailable (tests/unit/test_quarterly_fact_repair.py's scenarios, on their helpers).
    @contextmanager
    def database() -> Iterator[Session]:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        try:
            with Session(engine, expire_on_commit=False) as session:
                session.add(Company(id=1, ticker="META", cik="1326801", name="Meta"))
                session.commit()
                yield session
        finally:
            engine.dispose()

    with database() as db:
        db.add(FinancialFact(**repair_fact(concept="operating_margin", unit="pure"), is_latest=True))
        db.commit()
        normalizer(monkeypatch, [candidate(concept="revenue")], meta={"quarterly_exclusions": [{
            "concept": "operating_income", "fiscal_year": 2024, "fiscal_period": "Q4",
            "reason": "incompatible_vintages", "inputs": [{"accession": "old"}, {"accession": "new"}],
        }]})
        repair.repair_company(db, 1, payload(), dry_run=False)
        db.commit()
        codes |= set().union(*(reasons(row.provenance) for row in db.query(FinancialFact)))
    with database() as db:
        db.add(FinancialFact(**repair_fact(value=Decimal("20")), is_latest=True))
        db.commit()
        normalizer(monkeypatch, [candidate(), candidate(concept="free_cash_flow")])
        repair.repair_company(db, 1, payload(), dry_run=False, run_id="apply-1")
        db.commit()
        repair.rollback_company(db, 1, "apply-1", dry_run=False)
        db.commit()
        codes |= set().union(*(reasons(row.provenance) for row in db.query(FinancialFact)))
    with database() as db:
        # A reported quarterly EPS whose identity is already stored (tests/unit/test_quarterly_fact_repair.py's
        # promotion scenario).
        db.add(FinancialFact(**repair_fact(concept="eps_diluted", value=Decimal("7.95"), unit="USD/shares"),
                             is_latest=True))
        reported = repair_fact(concept="eps_diluted", value=Decimal("8.02"), unit="USD/shares", source="reported_eps",
                               accession="0001326801-25-000014")
        db.add(FinancialFact(**reported, is_latest=False))
        db.commit()
        normalizer(monkeypatch)
        repair.repair_company(db, 1, payload(), dry_run=False, reported_eps=[reported])
        db.commit()
        codes |= set().union(*(reasons(row.provenance) for row in db.query(FinancialFact)))

    # The lineage backfill writes lineage's verdict onto filing-owned legacy calculations: a pass, a mismatch and each
    # hold (tests/unit/test_filing_lineage_repair.py's helpers), one company each.
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        for index, case in enumerate(["passed", "mismatch", *sorted(HOLDS)]):
            company, filing = _company(db, ticker=f"L{index}", cik=f"{index + 1:010d}")
            if case in HOLDS:
                _seed_hold(db, company, filing, case)
            else:
                _margin(db, company, filing, margin=25.0 if case == "passed" else 26.0)
            db.commit()
            result = lineage_repair.backfill_company(db, company.id, apply=True, run_id=f"lineage-{index}")
            db.commit()
            codes |= set(result["reasons"]) | {code for row in result["rows"] for code in row["reasons"]}
        codes |= set().union(*(reasons(row.provenance) for row in db.query(FinancialFact)))
    engine.dispose()
    return codes


def _executed(run, paths: set[str]) -> tuple[object, set[tuple[str, int]]]:
    """What `run` returns, and the lines it executes in the files under backend/ named in `paths` (sys.settrace,
    which Python 3.11 to 3.13 all have; a tracer already set, such as coverage's, is restored after)."""
    import os
    import sys

    backend = APP.parent
    named = {os.path.realpath(backend / path): path for path in paths}
    cached: dict[str, str | None] = {}
    executed: set[tuple[str, int]] = set()

    def in_line(frame, event, _arg):
        if event == "line":
            executed.add((cached[frame.f_code.co_filename], frame.f_lineno))
        return in_line

    def on_call(frame, _event, _arg):
        filename = frame.f_code.co_filename
        if filename not in cached:
            cached[filename] = named.get(os.path.realpath(filename))
        return in_line if cached[filename] is not None else None

    previous = sys.gettrace()
    sys.settrace(on_call)
    try:
        result = run()
    finally:
        sys.settrace(previous)
    return result, executed


def test_the_drivers_reach_every_reason_writing_line_and_write_only_reasons_the_reader_finds(monkeypatch):
    """The runtime half of this gate, held by line rather than by code. In each emitter module the reader names every
    reason-writing line (a site, a call that binds a reason parameter, a literal's running line) and every line that
    mentions `reasons`; _drive runs them, traced. The test fails when (a) a code _drive gathers has no words, (b) a named
    line runs in no driver and UNDRIVEN does not say why, so a line that names the list is never left undriven without a
    stated reason, or (c) a code _drive gathers is one the reader did not find in those modules, a form the reader
    cannot follow caught wherever a driver writes it where _drive gathers it. A value no driver evaluates in a write a
    driver runs, or on a line one runs (an arm of a conditional, `or` or `and`, a comprehension's or generator's element
    over an iterable no driver fills, a write after a one-line `if`), is outside (b), which holds lines, not the values
    in them; a value _drive does not gather is outside (a) and (c)."""
    sources = _app_sources()
    found, lines = read_reasons(sources)
    emitters = _emitter_modules(found, lines)
    skipped = EXEMPT.keys() | READS_ONLY.keys()
    named = {(path, function, line) for (path, function), numbers in [*lines.items(), *_mentions(sources).items()]
             if path in emitters and (path, function) not in skipped for line in numbers if line is not None}
    # Each module where the reader finds a reason, a site or a binding call in a function has lines it names there
    # (sites, binding calls, literals), so a reader that stopped naming them fails here, not only in the planted test. A
    # module whose only site is at its top level, read but not required, has none.
    assert {path for (path, function), numbers in lines.items() if numbers and (path, function) not in skipped} == {
        path for path, function in {*found, *lines} if function != "<module>" and (path, function) not in skipped}
    emitted, executed = _executed(lambda: _drive(monkeypatch), emitters)
    assert sorted(emitted - set(REASONS)) == [], "an emitter writes a reason with no words in data_notes.REASONS"
    unreached: dict[tuple[str, str, str], list[int]] = {}
    for path, function, line in sorted(named):
        if (path, line) not in executed:
            unreached.setdefault((path, function, sources[path].splitlines()[line - 1].strip()), []).append(line)
    assert sorted(UNDRIVEN.keys() - unreached.keys()) == [], "an UNDRIVEN entry names no unreached line: drop it"
    assert sorted((key, unreached[key]) for key in UNDRIVEN if len(unreached[key]) > 1) == [], (
        "an UNDRIVEN entry's text names more than one unreached line: each line needs its own reason"
    )
    assert sorted((path, line, text) for (path, function, text), numbers in unreached.items()
                  if (path, function, text) not in UNDRIVEN for line in numbers) == [], (
        "a reason-writing line (a site, a call that binds a reason, a literal, or any mention of `reasons`) in an "
        "emitter module that no driver executes: run its branch in _drive, or name it in UNDRIVEN with why it cannot"
    )
    static = {code for (path, function), codes in found.items()
              if path in emitters and (path, function) not in skipped for code in codes}
    assert sorted(emitted - static) == [], (
        "a driver writes a reason the reader does not find in the emitter modules: the reader went blind to the form "
        "it takes there; follow that form, or name and plant it as out of reach"
    )


# A package of four modules: the forms the reader follows, each code named for its form, and every documented gap,
# each code named planted_gap_*. Words that are never a reason sit beside some codes, so a reader that read too much
# fails too.
PLANTED = {
    "app/planted/__init__.py": "",
    "app/planted/codes.py": '''
IMPORTED = "planted_imported_constant"
ALIASED = "planted_imported_alias"
RELATIVE = "planted_relative_import"
VIA_MODULE = "planted_module_attribute"
FLAGS = ("planted_loop_over_module_attribute",)
TABLE = (("planted_tuple_loop_over_module_attribute", "Words, never a reason."),)
''',
    "app/planted/forms.py": '''
from contextlib import nullcontext

import app.planted.codes as aliased_module
from app.planted import codes
from app.planted.codes import ALIASED as RENAMED, IMPORTED
from .codes import RELATIVE

def first(fact):
    fact["provenance"] = {"reasons": ["planted_dict"] if fact else []}

def second(provenance):
    provenance.update(validation="needs_review", reasons=["planted_keyword"])

def third():
    reasons: list[str] = []
    reasons.append("planted_append")
    reasons += ["planted_augmented"]
    reasons.extend(sorted({"planted_extend"}))
    reasons.add("planted_reasons_add")
    if (reasons := ["planted_walrus"]):
        return reasons

def fourth(state, reason):
    return {**state, "reasons": [reason]}

def caller(state):
    return fourth(state, "planted_argument"), fourth(state, reason="planted_keyword_argument")

def relay(fact, codes):
    return fourth(fact, codes)

def relayed(fact):
    return relay(fact, "planted_relay")

def withhold(state, codes):
    codes = list(codes)
    return {**state, "reasons": codes}

def normalise(state, reason):
    reason = reason or "planted_default_by_or"
    return {**state, "reasons": [reason]}

def withdraw(state, reason="planted_positional_default", *, extra="planted_keyword_only_default"):
    return {**state, "reasons": [reason, extra]}

def rebound(state):
    return withhold(state, ["planted_rebound_parameter"]), normalise(state, "planted_normalised_argument"), withdraw(state)

def collected(state, prior):
    checks = []
    checks.append("planted_list_append")
    checks.extend(["planted_list_extend"])
    checks.insert(0, "planted_list_insert")
    seen = set()
    seen.add("planted_set_add")
    seen.update({"planted_set_update"})
    return fourth(state, checks), fourth(state, sorted(seen)), fourth(state, sorted(set(prior) | {"planted_set_union"}))

def outer(state):
    code = "planted_closure"
    def inner():
        return {**state, "reasons": [code]}
    return inner()

FALLBACKS = {"review": "planted_module_dict"}

def fifth(kind, supplied):
    chosen = supplied or [FALLBACKS[kind]]
    reasons = list(dict.fromkeys([*chosen]))
    return {"reasons": [code for code in reasons]}

def keys_are_not_values(provenance):
    reasons = list(provenance.get("planted_key_read", {}).get("reasons", []))
    return reasons

def imported():
    reasons = [IMPORTED, RENAMED, RELATIVE, codes.VIA_MODULE]
    for code in aliased_module.FLAGS:
        reasons.append(code)
    return reasons

def looped():
    reasons = []
    for code in ("planted_loop",):
        reasons.append(code)
    for code, words in (("planted_loop_pair", "Words, never a reason."),):
        reasons.append(code)
    for index, code in enumerate(["planted_enumerate"]):
        reasons.append(code)
    for code, words in zip(("planted_zip",), ("Other words, never a reason.",)):
        reasons.append(code)
    return {"reasons": [code for code, words in (("planted_comprehension_iterable", "Words again."),)]}

def unpacked():
    reasons, other = ["planted_tuple_unpacked"], "planted_neighbour_never_a_reason"
    first, second = "planted_unpacked_name", "planted_neighbour_never_a_reason"
    reasons.append(first)
    return reasons, other, second

class Repair:
    def _quarantine(self, state, reason):
        return {**state, "reasons": [reason]}

    @staticmethod
    def _withdraw(state, reason):
        return {**state, "reasons": [reason]}

    @classmethod
    def _flag(cls, state, reason):
        return {**state, "reasons": [reason]}

    def run(self, state):
        return (
            self._quarantine("planted_state_never_a_reason", "planted_method_positional"),
            self._quarantine(state, reason="planted_method_keyword"),
            self._withdraw(state, "planted_static_method"),
            Repair._withdraw(state, "planted_static_through_class"),
            self._flag(state, "planted_class_method"),
            Repair._quarantine(self, state, "planted_method_through_its_class"),
            type(self)._quarantine(self, "planted_state_never_a_reason", "planted_method_through_type"),
            self.__class__._quarantine(self, state, "planted_method_through_dunder_class"),
        )

CHECKS = (("planted_tuple_loop_over_a_name", 10), ("planted_tuple_loop_second_row", 20))
NESTED = ((("planted_nested_tuple_target", "Words, never a reason."), 1),)
WITHHELD = {"planted_dict_key_never_a_reason": "planted_dict_items_value"}
LOOP_SOURCE = {"review": "planted_loop_over_dict_values"}
PAIR = ("planted_unpacked_from_a_name", "Words, never a reason.")
FIRST = ("planted_tuple_index", "Words, never a reason.")

def tables(state):
    reasons = []
    for code, limit in CHECKS:
        reasons.append(code)
    for code, words in codes.TABLE:
        reasons.append(code)
    for key, code in WITHHELD.items():
        reasons.append(code)
    for (code, words), count in NESTED:
        reasons.append(code)
    for code in LOOP_SOURCE.values():
        reasons.append(code)
    for code in {"planted_loop_over_dict_keys": 1}:
        reasons.append(code)
    code, words = PAIR
    reasons.append(code)
    reasons.append(FIRST[0])
    return {**state, "reasons": [code for code, limit in CHECKS]}, reasons

def replace(state, reason):
    return {**state, "reasons": [reason]}

def appended(state):
    checks = []
    checks.append(("planted_append_tuple_row", 1))
    checks.insert(0, ("planted_insert_tuple_row", 2))
    pairs = set()
    pairs.add(("planted_add_tuple_row", "Words, never a reason."))
    listed = [code for code, limit in checks]
    return {**state, "reasons": [*listed, *[code for code, words in pairs]]}

MODULE_ROWS = []
MODULE_ROWS.append(("planted_module_append_tuple_row", "Words, never a reason."))
HEAD_ROWS = (("planted_starred_row_head", 1),)
ALL_ROWS = (*HEAD_ROWS, ("planted_starred_row_tail", 2))
SHIFTED = (*HEAD_ROWS, "planted_gap_index_past_a_starred_item")
ROWS = (("planted_nested_index", "Words, never a reason."),)
BASE = {"review": "planted_spread_dict_value"}
MERGED = {**BASE, "unknown": "planted_merged_dict_value"}
VIEWED = {"review": "planted_spread_view_value"}
KEYED = {"planted_spread_key": "Words, never a reason."}

def more_tables(state, kind):
    reasons = []
    for code, words in MODULE_ROWS:
        reasons.append(code)
    for code, limit in ALL_ROWS:
        reasons.append(code)
    reasons.append(ROWS[0][0])
    for code in reversed(("planted_reversed",)):
        reasons.append(code)
    reasons.append(MERGED[kind])
    for code in {**VIEWED}.values():
        reasons.append(code)
    for code in {**KEYED}:
        reasons.append(code)
    reasons.append(SHIFTED[1])
    return {**state, "reasons": reasons, "tables": 2}

def _finish(state, status):
    return {**state, "reasons": [status]}

def finished(state):
    return _finish(state, "planted_own_module_call")

def folded(state):
    reasons = [
        "planted_folded_first",
        "planted_folded_second",
        "planted_folded_third",
    ]
    return {**state, "reasons": reasons, "folded": True}

def not_a_method(text):
    return text.replace("planted_object_first_never_a_reason", "planted_object_second_never_a_reason")

class Record:
    CODE = "planted_gap_class_attribute"

class Defaults:
    DEFAULT = "planted_gap_class_body_default"

    def _q(self, state, reason=DEFAULT):
        return {**state, "reasons": [reason]}

CODES = {"review": "planted_gap_get"}

def from_a_call(kind):
    return {"reasons": [code for code, words in table_for(kind)]}

def table_for(kind):
    return (("planted_gap_loop_over_a_call", kind),)

def gaps(provenance, kind):
    provenance.setdefault("reasons", []).append("planted_gap_receiver")
    provenance["reasons"] = [f"planted_gap_{kind}"]
    provenance["reasons"] = ["planted_gap_format_{}".format(kind), "_".join(("planted_gap", "join"))]
    provenance["reasons"] = [Record.CODE, Record().CODE]
    by_kind = {name: "planted_gap_dict_comprehension" for name in ("review",)}
    provenance["reasons"] = [by_kind[kind], CODES.get(kind), dict(review="planted_gap_dict_call")[kind]]
    head, *rest = ["planted_gap_head_beside_a_starred_target", "planted_gap_starred_target"]
    provenance["reasons"].extend([head, *rest])
    quarantine = fourth
    flag = lambda state, reason: {**state, "reasons": [reason]}
    getattr(Repair(), "_quarantine")(provenance, "planted_gap_getattr")
    fourth(*(provenance, "planted_gap_call_site_star"))
    fourth(provenance, **{"reason": "planted_gap_call_site_double_star"})
    return quarantine(provenance, "planted_gap_name_alias"), flag(provenance, "planted_gap_lambda"), {"reasons": built()}

def built():
    return ["planted_gap_return"]

KEY = "reasons"

def _tag(codes, code):
    codes.append(code)

def escapes(provenance, kind):
    flags = provenance["reasons"]
    flags.append("planted_gap_list_alias")
    bucket = provenance.setdefault("reasons", [])
    bucket.append("planted_gap_setdefault_alias")
    _tag(provenance["reasons"], "planted_gap_helper_parameter")
    provenance["rea" + "sons"] = ["planted_gap_runtime_key"]
    provenance[KEY] = ["planted_gap_constant_key"]
    return provenance

def untied(provenance, holder):
    codes = provenance["reasons"]
    def closed():
        codes.append("planted_gap_closure_variable")
    holder.codes.append("planted_gap_attribute_receiver")
    provenance["reasons"] = holder.codes
    return closed

def tied(provenance, kind):
    codes = []
    codes.append(f"planted_tied_site_value_{kind}")
    extra = []
    extra.append(f"planted_tied_folded_in_{kind}")
    reasons = list(provenance.get("reasons", []))
    reasons.extend(extra)
    pending = []
    pending.append(f"planted_tied_assigned_into_{kind}")
    chained = sorted(pending)
    more = []
    more.append(f"planted_tied_extended_into_{kind}")
    listed = []
    listed.extend(more)
    kept = []
    kept.append(f"planted_tied_comprehension_element_{kind}")
    keyed = []
    keyed.append(f"planted_tied_fromkeys_argument_{kind}")
    viewed = {}
    viewed[kind] = f"planted_tied_view_receiver_{kind}"
    for looped in (reasons,):
        looped.append(f"planted_tied_for_target_{kind}")
    with nullcontext(reasons) as entered:
        entered.append(f"planted_tied_with_target_{kind}")
    [gathered.append(f"planted_tied_comprehension_target_{kind}") for gathered in (reasons,)]
    shown = [*codes, *(chained if kind else listed)] + (listed or [code for code in kept])
    shown += list(dict.fromkeys(keyed)) + list(viewed.values())
    return {**provenance, "reasons": shown}, reasons

def per_item(provenance, changes):
    reasons = provenance["reasons"]
    reasons.extend(
        f"planted_gap_generator_element_{change}"
        for change in changes)
    return reasons

def starred(state, *codes, **named):
    return {**state, "reasons": [*codes, named["reason"]]}

def via(module, state):
    return module.fourth(state, "planted_gap_module_in_a_variable")

def starred_caller(state):
    return starred(state, "planted_gap_args", reason="planted_gap_kwargs")
''',
    "app/planted/jobs.py": '''
def _finish(run_id, status):
    return {"run": run_id, "status": status}

def track(run_id):
    return _finish(run_id, "planted_own_definition_never_a_reason")
''',
    "app/planted/calls.py": '''
import json
from app.planted import forms
from app.planted.forms import fourth as quarantine

def through_imports(state, repair):
    return (
        quarantine(state, "planted_call_through_import_alias"),
        forms.fourth(state, "planted_call_through_module"),
        forms.Repair._quarantine(repair, state, "planted_method_through_module_class"),
        json.fourth("planted_outside_first_never_a_reason", "planted_outside_second_never_a_reason"),
    )
''',
}


def test_the_reader_finds_each_form_and_names_its_gaps():
    found, lines = read_reasons(PLANTED)
    codes = {code for site_codes in found.values() for code in site_codes}
    assert {code for code in codes if not code.startswith("planted_gap")} == {
        "planted_dict", "planted_keyword", "planted_append", "planted_augmented", "planted_extend",
        "planted_reasons_add", "planted_walrus", "planted_argument", "planted_keyword_argument", "planted_relay",
        "planted_rebound_parameter", "planted_default_by_or", "planted_normalised_argument",
        "planted_positional_default", "planted_keyword_only_default", "planted_list_append", "planted_list_extend",
        "planted_list_insert", "planted_set_add", "planted_set_update", "planted_set_union", "planted_closure",
        "planted_module_dict", "planted_imported_constant", "planted_imported_alias", "planted_relative_import",
        "planted_module_attribute", "planted_loop_over_module_attribute", "planted_loop", "planted_loop_pair",
        "planted_enumerate", "planted_zip", "planted_comprehension_iterable", "planted_tuple_unpacked",
        "planted_unpacked_name", "planted_method_positional", "planted_method_keyword", "planted_static_method",
        "planted_static_through_class", "planted_class_method", "planted_method_through_its_class",
        "planted_method_through_type", "planted_method_through_dunder_class", "planted_call_through_import_alias",
        "planted_call_through_module", "planted_method_through_module_class", "planted_tuple_loop_over_a_name",
        "planted_tuple_loop_second_row", "planted_tuple_loop_over_module_attribute", "planted_dict_items_value",
        "planted_nested_tuple_target", "planted_loop_over_dict_values", "planted_loop_over_dict_keys",
        "planted_unpacked_from_a_name", "planted_tuple_index", "planted_append_tuple_row", "planted_insert_tuple_row",
        "planted_add_tuple_row", "planted_module_append_tuple_row", "planted_starred_row_head",
        "planted_starred_row_tail", "planted_nested_index", "planted_reversed", "planted_spread_dict_value",
        "planted_merged_dict_value", "planted_spread_view_value", "planted_spread_key", "planted_own_module_call",
        "planted_folded_first", "planted_folded_second", "planted_folded_third",
    }
    forms = "app/planted/forms.py"
    # A bare name's call reaches its own module's function: jobs.track's _finish is jobs', never forms'.
    assert ("app/planted/jobs.py", "track") not in found and ("app/planted/jobs.py", "track") not in lines
    assert found[(forms, "caller")] == {"planted_argument", "planted_keyword_argument"}
    assert found[(forms, "run")] == {
        "planted_method_positional", "planted_method_keyword", "planted_static_method",
        "planted_static_through_class", "planted_class_method", "planted_method_through_its_class",
        "planted_method_through_type", "planted_method_through_dunder_class",
    }
    assert found[(forms, "tables")] == {
        "planted_tuple_loop_over_a_name", "planted_tuple_loop_second_row", "planted_tuple_loop_over_module_attribute",
        "planted_dict_items_value", "planted_nested_tuple_target", "planted_loop_over_dict_values",
        "planted_loop_over_dict_keys", "planted_unpacked_from_a_name", "planted_tuple_index",
    }
    # The lines the runtime half must run: each site (third's six), a call that binds a reason (caller's), a literal on a
    # line apart from its site (outer's code, written by inner), and a display of constants on its first line alone,
    # since CPython folds it into one constant loaded there.
    source = PLANTED[forms].splitlines()

    def at(text: str) -> int:
        [number] = [index + 1 for index, line in enumerate(source) if line.strip() == text]
        return number

    assert lines[(forms, "third")] == {
        at("reasons: list[str] = []"), at('reasons.append("planted_append")'), at('reasons += ["planted_augmented"]'),
        at('reasons.extend(sorted({"planted_extend"}))'), at('reasons.add("planted_reasons_add")'),
        at('if (reasons := ["planted_walrus"]):'),
    }
    assert lines[(forms, "caller")] == {
        at('return fourth(state, "planted_argument"), fourth(state, reason="planted_keyword_argument")')}
    assert lines[(forms, "outer")] == {at('code = "planted_closure"')}
    assert lines[(forms, "inner")] == {at('return {**state, "reasons": [code]}')}
    assert lines[(forms, "folded")] == {at("reasons = ["), at('return {**state, "reasons": reasons, "folded": True}')}
    # The runtime half's mentions: a name tied to the list makes each line that uses it one, so a write through it is a
    # line a driver must run. Forward, a name assigned from a mention (an assignment, a for, with or comprehension
    # target); back, a name a site's value holds, or what a tied name is assigned holds (by an assignment, an extend,
    # in each position a value holds a name in: a display's starred item, an arm, an operand, a wrapper's argument, a
    # `fromkeys` call's argument, a dict view's receiver, a comprehension's element). A helper's parameter, a closure's
    # variable and an attribute are not (the header's first escape), nor is a generator's element on a line of its own
    # (the fifth: the line that writes it is named, the element's is not, so over an empty iterable nothing the run
    # holds tells it apart).
    mentioned = _mentions(PLANTED)
    assert {at('flags.append("planted_gap_list_alias")'), at('bucket.append("planted_gap_setdefault_alias")')} <= (
        mentioned[(forms, "escapes")])
    assert {at(f'{name}.append(f"planted_tied_{form}_{{kind}}")') for name, form in (
        ("codes", "site_value"), ("extra", "folded_in"), ("pending", "assigned_into"), ("more", "extended_into"),
        ("kept", "comprehension_element"), ("looped", "for_target"), ("entered", "with_target"),
        ("keyed", "fromkeys_argument"),
    )} | {at('[gathered.append(f"planted_tied_comprehension_target_{kind}") for gathered in (reasons,)]'),
          at('viewed[kind] = f"planted_tied_view_receiver_{kind}"')} <= mentioned[(forms, "tied")]
    assert (forms, "_tag") not in mentioned and (forms, "closed") not in mentioned
    assert at('holder.codes.append("planted_gap_attribute_receiver")') not in mentioned[(forms, "untied")]
    assert at("reasons.extend(") in mentioned[(forms, "per_item")] & lines[(forms, "per_item")]
    assert at('f"planted_gap_generator_element_{change}"') not in (
        mentioned[(forms, "per_item")] | lines[(forms, "per_item")])
    # The documented gaps, each planted above with a literal the reader would collect if it reached the form: a key a
    # call reads, a receiver other than a name or a reasons target, a string built at run time (an f-string, a .format,
    # a join), a class's attribute, a dict built by a comprehension or by dict(), a .get(), a loop over a function's
    # return, a starred target, a name alias, a lambda, a getattr callee, a module function through an object,
    # arguments spread at a call, a class-body default, a function's return, *args and **kwargs, an element at an
    # index past a starred item, a name bound to the list, a setdefault's result, a helper's parameter, a closure's
    # variable, an attribute receiver, a key built at run time, a key held in a module's constant and a generator's
    # element.
    assert not codes & {"planted_key_read", "planted_gap", "join"}
    assert {code for code in codes if code.startswith("planted_gap")} == set()
