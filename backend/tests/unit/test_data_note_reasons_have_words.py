"""Every reason the backend writes has words (CLAUDE.md rule 12; data notes version 2).

A data note's message is its reasons' sentences from `data_notes.REASONS`. A reason with no entry falls back to one
generic sentence ("The source or calculation basis needs review. Check the original filing."), so a new reason would
reach the page, the PDF, the workbook and the chart PNG with no words of its own and nothing would fail. This gate
reads every module under `app/` and fails on a reason code the backend can write that `REASONS` does not hold. The
frontend's copy (`provenance.ts` REASONS) is held equal to `REASONS` by the shared notes fixture
(`tests/fixtures/analysis_data_notes.json`: case `all_known_reason_messages_and_supplements_after_z` holds one note
for every reason, read by `test_analysis_data_notes.py` and `frontend/tests/unit/data-notes.spec.ts`), so a code with
words here has the same words there.

A reason is written where a string can become an element of a `reasons` list:
1. the value of a `"reasons"` key in a dict display (`{"reasons": ["source_check_needed"]}`);
2. a `reasons=` keyword (`provenance.update(reasons=[...])`, `calculated_provenance(..., reasons=reasons)`);
3. an assignment to a name `reasons`, an attribute `.reasons` or a `["reasons"]` item: plain, annotated, augmented,
   a walrus, or one item of a tuple unpacked from a tuple display (`reasons, other = ["code"], 1`);
4. an `append`, `extend`, `insert`, `add` or `update` on such a target (`reasons.append("calculation_mismatch")`);
5. an argument bound to a parameter that flows into one of the above, to a fixpoint, at a call of a function or method
   of that name in `app/` (`_quarantine(state, "repair_rolled_back")`, whose `reason` becomes `"reasons": [reason]`),
   and a parameter's default (`def withdraw(state, reason="code")`). A call through an import (`from app.x import f
   as g`) or a module (`x.f(...)`) binds only to that module's function when it defines one, and a call into a module
   outside `app/` binds to none. A method's arguments bind after the `self` an object supplies
   (`self._quarantine(state, code)`) and the `cls` an object or its class supplies; through its class
   (`Repair._quarantine(repair, state, code)`, `type(self)._quarantine(self, ...)`, `self.__class__`, `module.Class`)
   a method takes `self` as its first argument, and a static method binds from the first.

What a value can hold is read through:
- string literals; list, tuple and set displays and their starred items; `or`, `and`, a conditional's arms, `+` and `|`;
- `list()`, `sorted()`, `set()`, `tuple()`, `frozenset()` and `dict.fromkeys()` of an argument;
- a comprehension's element, each loop name read through its iterable;
- a name, through its every binding in its function, the functions that enclose it and the module: an assignment
  (plain, annotated, augmented, a walrus, or one item of a tuple display unpacked into a tuple), what an `append`,
  `extend`, `insert`, `add` or `update` puts into it, a `for` loop's target (its iterable's items; a tuple target is
  paired item by item over a display of tuples, `enumerate()` or `zip()`), and a parameter's default; a parameter its
  function rebinds (`codes = list(codes)`) still flows;
- a name imported from another module under `app/` (`from app.x import CODE`, `from .x import CODE as OTHER`) or a
  module's attribute (`from app import x` or `import app.x as x`, then `x.CODE`), through that module's bindings;
- an item of a dict display such a name holds (`fallback[kind]` reads every value of `fallback`).
A string read by a call (`provenance.get("reasons", [])`) is a key, not a value, and is not collected.

Out of reach, review-checked, and each planted in `test_the_reader_finds_each_form_and_names_its_gaps` with a literal
the reader would collect if it reached the form, so a change that reaches one fails there until this list is updated:
- a reason built at run time: an f-string, a `.format`, a join;
- a value read through an attribute of an object or a class (`record.code`, `Record.CODE`), a dict built by a
  comprehension, a container's `.get()`, or a function's return;
- a loop over anything but a display, a name, `enumerate()` or `zip()` (a dict's `.values()`, a dict display's keys);
- a tuple unpacked from anything but a tuple display (`code, other = PAIR`), and a starred target;
- a write through a receiver that is neither a name nor a `reasons` target
  (`provenance.setdefault("reasons", []).append(...)`);
- a call through a name assigned a function (`quarantine = _quarantine`), a lambda, or a callee looked up at run time
  (`getattr(self, name)(...)`), and a parameter bound through `*args` or `**kwargs`.
That list is what the reader is known to miss, not all it may miss: a form on neither list is unknown. So
`test_the_emitters_write_only_reasons_the_reader_finds` also drives the emitters it can run without a database, and
fails on a code they write that has no words or that the reader does not find, and on a code the reader finds in them
that no driver reaches.

Some modules keep lists named `reasons` that never reach a fact's provenance or a data note: the summary quality
tier's reasons and the Copilot's quotation checks. EXEMPT names each such site by file and function; an exempt site
must still write a reason (one find), so an exemption cannot outlive its code.
"""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.services.trend_analysis.data_notes import REASONS

APP = Path(__file__).resolve().parents[2] / "app"
WRAPPERS = frozenset({"list", "sorted", "set", "tuple", "frozenset"})
# The calls that put a value into a list or a set: on a `reasons` target a write (form 4), on any name a binding.
LIST_METHODS = frozenset({"append", "extend", "insert", "add", "update"})
# (file under backend/, function) -> why its `reasons` never reach a data note.
EXEMPT = {
    ("app/services/summary_generation_service.py", "assess_quality"):
        "a summary's quality tier: prose reasons for the partial tier, stored on the summary, never on a fact",
    ("app/services/copilot/quotations.py", "_displayed_quotation_reasons"):
        "the Copilot's quotation checks: why a quotation was refused, never a fact's provenance",
}
# The emitters the drivers below cannot run without a database: quarterly_fact_repair's _quarantine call sites. The
# reader must find their codes, so a reader that went blind to them fails; the driven emitters are held by the drivers.
KNOWN = frozenset({
    "legacy_calculation_not_supported", "repair_rolled_back", "legacy_period_label_mismatch",
    "rolling_duration_not_fiscal_year", "calculation_parent_period_corrected",
})
# The modules whose emitters the drivers run (_emitted_reasons).
DRIVEN = frozenset({
    "app/services/facts/reconcile.py", "app/services/facts/lineage.py", "app/services/fact_provenance.py",
    "app/services/trend_analysis/data_notes.py",
})


def _is_reasons_target(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "reasons"
    if isinstance(node, ast.Attribute):
        return node.attr == "reasons"
    return (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
            and node.slice.value == "reasons")


def _starred(items: list[ast.expr]) -> bool:
    return any(isinstance(item, ast.Starred) for item in items)


def _pairs(target: ast.expr, value: ast.expr) -> list[tuple[ast.expr, ast.expr]]:
    """Each target an assignment binds with the value it takes; a tuple display unpacks item by item."""
    if not isinstance(target, (ast.Tuple, ast.List)):
        return [(target, value)]
    if (isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(target.elts)
            and not _starred(target.elts) and not _starred(value.elts)):
        return [pair for item, held in zip(target.elts, value.elts) for pair in _pairs(item, held)]
    return []


def _loop_pairs(target: ast.expr, iterable: ast.expr) -> list[tuple[ast.expr, ast.expr]]:
    """Each target a loop binds with an expression that holds every item it takes."""
    if not isinstance(target, (ast.Tuple, ast.List)):
        return [(target, iterable)]
    if _starred(target.elts):
        return []
    if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name) and iterable.args:
        if iterable.func.id == "enumerate" and len(target.elts) == 2:
            return _loop_pairs(target.elts[1], iterable.args[0])
        if iterable.func.id == "zip" and len(iterable.args) == len(target.elts) and not _starred(iterable.args):
            return [pair for item, held in zip(target.elts, iterable.args) for pair in _loop_pairs(item, held)]
    if isinstance(iterable, (ast.List, ast.Tuple, ast.Set)) and iterable.elts and all(
        isinstance(row, (ast.Tuple, ast.List)) and len(row.elts) == len(target.elts) and not _starred(row.elts)
        for row in iterable.elts
    ):
        columns = [ast.Tuple(elts=[row.elts[index] for row in iterable.elts], ctx=ast.Load())
                   for index in range(len(target.elts))]
        return [pair for item, column in zip(target.elts, columns) for pair in _loop_pairs(item, column)]
    return []


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
            # checks.append(code), checks.extend(codes), checks.insert(0, code): the name holds what is put in it.
            bind([(node.func.value, node.args[-1] if node.func.attr == "insert" else node.args[0])])
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


def _resolve(name: str, scope: _Scope, flows: set[tuple[str, str]], seen: frozenset, bound: dict) -> list[Binding]:
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
        flows.add((scope.name, name))
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


def _values(expr: ast.AST | None, scope: _Scope, flows: set[tuple[str, str]], seen: frozenset = frozenset(),
            bound: dict | None = None) -> set[str]:
    """The string literals `expr` may hold as a reason; a parameter it reads joins `flows`."""
    bound = {} if bound is None else bound

    def read(item: ast.AST | None) -> set[str]:
        return _values(item, scope, flows, seen, bound)

    def held(bindings: list[Binding]) -> set[str]:
        return set().union(*(_values(value, where, flows, seen | {key}, inner)
                             for value, where, key, inner in bindings))

    if expr is None:
        return set()
    if isinstance(expr, ast.Constant):
        return {expr.value} if isinstance(expr.value, str) else set()
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
    if isinstance(expr, ast.Call) and expr.args and (
        (isinstance(expr.func, ast.Name) and expr.func.id in WRAPPERS)
        or (isinstance(expr.func, ast.Attribute) and expr.func.attr == "fromkeys")
    ):
        return read(expr.args[0])
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
    if isinstance(expr, ast.Subscript) and isinstance(expr.value, ast.Name):
        bindings = _resolve(expr.value.id, scope, flows, seen, bound)
        return held([(item, where, key, inner) for display, where, key, inner in bindings
                     if isinstance(display, ast.Dict) for item in display.values])
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
    ("function", "name"): 0, ("function", "module"): 0, ("function", "class"): 0, ("function", "object"): 0,
    ("static", "class"): 0, ("static", "object"): 0,
    ("class", "class"): 1, ("class", "object"): 1,
    ("instance", "class"): 0, ("instance", "object"): 1,
}


def _callee(func: ast.expr, receiver: str, scope: _Scope, defines: dict[str, set[str]]) -> tuple[str, str | None] | None:
    """The name a call reaches and the file it must be defined in (None: any file), or None for a call that reaches no
    function under `app/`: one into an outside module, or a callee the reader cannot name."""
    home = None
    if isinstance(func, ast.Name):
        name = func.id
        source, attribute = scope.module_scope.imports.get(name, (None, None))
        if attribute is not None and not _shadowed(name, scope):
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


def written_reasons(sources: dict[str, str]) -> dict[tuple[str, str], set[str]]:
    """Every string each (file, function) can write into a reasons list, forms 1 to 5."""
    trees = {path: ast.parse(source) for path, source in sources.items()}
    modules = {_module_name(path) for path in trees}
    registry: dict[str, _Scope] = {}
    for path, tree in trees.items():
        registry[_module_name(path)] = _Scope(path, "<module>", None, tree.body, _imports(tree, path, modules), registry)
    nodes = [(node, scope) for path, tree in trees.items()
             for node, scope in _walk_scopes(tree, registry[_module_name(path)])]
    kinds = {key: kind for tree in trees.values() for key, kind in _method_kinds(tree).items()}
    # A function's or method's name -> (its positional parameters, "function" or the method's kind, its file).
    definitions: dict[str, list[tuple[list[str], str, str]]] = {}
    defines: dict[str, set[str]] = {}
    for node, scope in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = node.args
            definitions.setdefault(node.name, []).append(
                ([arg.arg for arg in [*arguments.posonlyargs, *arguments.args]], kinds.get(id(node), "function"),
                 scope.path))
            defines.setdefault(scope.path, set()).add(node.name)
    found: dict[tuple[str, str], set[str]] = {}
    flowing: set[tuple[str, str]] = set()  # (function name, parameter) that reach a reasons list

    def collect(expr: ast.AST, scope: _Scope) -> None:
        flows: set[tuple[str, str]] = set()
        codes = _values(expr, scope, flows)
        if codes:
            found.setdefault((scope.path, scope.name), set()).update(codes)
        flowing.update(flows)

    for node, scope in nodes:
        for expr in _sites(node):
            collect(expr, scope)
    calls = [(node, scope) for node, scope in nodes if isinstance(node, ast.Call)]
    while True:
        before = len(flowing)
        for node, scope in calls:
            receiver = _receiver(node.func, scope)
            reached = _callee(node.func, receiver, scope, defines)
            if reached is None:
                continue
            callee, home = reached
            for params, kind, path in definitions.get(callee, []):
                if (kind, receiver) not in SKIPPED or (home is not None and path != home):
                    continue
                positional = params[SKIPPED[kind, receiver]:]
                for index, argument in enumerate(node.args):
                    if index < len(positional) and (callee, positional[index]) in flowing:
                        collect(argument, scope)
                for keyword in node.keywords:
                    if (callee, keyword.arg) in flowing:
                        collect(keyword.value, scope)
        if len(flowing) == before:
            break
    return found


def _app_sources() -> dict[str, str]:
    return {f"app/{path.relative_to(APP).as_posix()}": path.read_text(encoding="utf-8") for path in APP.rglob("*.py")}


def test_every_reason_the_backend_writes_has_words():
    found = written_reasons(_app_sources())
    exempt = {site for site in found if site in EXEMPT}
    assert exempt == set(EXEMPT), f"an exemption no longer writes a reason: {sorted(set(EXEMPT) - exempt)}"
    written = {code for site, codes in found.items() if site not in EXEMPT for code in codes}
    assert KNOWN <= written, f"the reader no longer sees {sorted(KNOWN - written)}: it went blind"
    missing = sorted((code, site) for site, codes in found.items() if site not in EXEMPT
                     for code in codes if code not in REASONS)
    assert missing == [], (
        "a reason the backend writes has no words in data_notes.REASONS (and provenance.ts REASONS, which the shared "
        f"notes fixture holds equal), so it would read the generic fallback: {missing}"
    )


def _emitted_reasons() -> set[str]:
    """What the DRIVEN emitters write, run through every branch that writes a reason: facts/reconcile's five soft checks
    and facts/lineage's two calculation checks over one filing's batch, fact_provenance's legacy projections, and
    data_notes' fallbacks for a review, an unknown and a missing value."""
    from app.services.fact_provenance import provenance_for_fact, reported_provenance
    from app.services.facts.reconcile import reconcile_facts
    from app.services.trend_analysis.data_notes import data_notes

    def fact(concept: str, value: float, raw_tag: str | None = "us-gaap:Probe", unit: str = "USD") -> dict:
        return {"company_id": 1, "concept": concept, "value": value, "unit": unit, "period_start": None,
                "period_end": date(2024, 12, 31), "fiscal_year": 2024, "fiscal_period": "FY",
                "accession": "0000000001-25-000001", "raw_tag": raw_tag, "source": "companyfacts"}

    batch = [
        fact("revenue", 0.0),  # zero where the prior period had a value
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
    codes = {code for item in accepted for code in item["provenance"]["reasons"]}
    legacy = [
        SimpleNamespace(concept="revenue", raw_tag="us-gaap:Revenues", source="companyfacts", reconciled=False),
        SimpleNamespace(concept="net_margin", raw_tag=None, source="derived", reconciled=True),
        SimpleNamespace(concept="eps_basic", raw_tag=None, source="derived", reconciled=True),
    ]
    codes |= {code for row in legacy for code in provenance_for_fact(row)["reasons"]}
    codes |= set(reported_provenance({"reconciled": False})["reasons"])
    dataset = {"mode": "annual", "period_key": "FY2024", "periods": [{"key": "FY2024"}], "series": [
        {"concept": "revenue", "label": "Revenue",
         "points": [{"period": "FY2024", "value": 1.0, "provenance": {"validation": "needs_review", "reasons": []}}]},
        {"concept": "net_income", "label": "Net income", "points": [{"period": "FY2024", "value": 1.0}]},
        {"concept": "free_cash_flow", "label": "Free cash flow", "points": [{"period": "FY2024", "value": None}]},
    ]}
    return codes | {code for note in data_notes(dataset)["notes"] for code in note["reasons"]}


def test_the_emitters_write_only_reasons_the_reader_finds():
    """The runtime half of this gate: what the emitters write when run, whatever form their code takes."""
    emitted = _emitted_reasons()
    assert sorted(emitted - set(REASONS)) == [], "an emitter writes a reason with no words in data_notes.REASONS"
    found = written_reasons(_app_sources())
    static = {code for (path, _function), codes in found.items() if path in DRIVEN for code in codes}
    assert sorted(emitted - static) == [], (
        "an emitter writes a reason the reader does not find in its module: the reader went blind to the form it "
        "takes there; follow that form, or name and plant it as out of reach"
    )
    assert sorted(static - emitted) == [], (
        "the reader finds a reason in a driven module that no driver reaches: run the branch that writes it in "
        "_emitted_reasons"
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
''',
    "app/planted/forms.py": '''
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

class Record:
    CODE = "planted_gap_class_attribute"

LOOP_SOURCE = {"review": "planted_gap_loop_over_a_call"}
CODES = {"review": "planted_gap_get"}
PAIR = ("planted_gap_unpacked_from_a_name", "Words, never a reason.")

def gaps(provenance, kind):
    provenance.setdefault("reasons", []).append("planted_gap_receiver")
    provenance["reasons"] = [f"planted_gap_{kind}"]
    provenance["reasons"] = ["planted_gap_format_{}".format(kind), "_".join(("planted_gap", "join"))]
    provenance["reasons"] = [Record.CODE, Record().CODE]
    by_kind = {name: "planted_gap_dict_comprehension" for name in ("review",)}
    provenance["reasons"] = [by_kind[kind], CODES.get(kind)]
    for code in LOOP_SOURCE.values():
        provenance["reasons"].append(code)
    for code in {"planted_gap_loop_over_dict_keys": 1}:
        provenance["reasons"].append(code)
    code, words = PAIR
    provenance["reasons"].append(code)
    head, *rest = ["planted_gap_head_beside_a_starred_target", "planted_gap_starred_target"]
    provenance["reasons"].extend([head, *rest])
    quarantine = fourth
    flag = lambda state, reason: {**state, "reasons": [reason]}
    getattr(Repair(), "_quarantine")(provenance, "planted_gap_getattr")
    return quarantine(provenance, "planted_gap_name_alias"), flag(provenance, "planted_gap_lambda"), {"reasons": built()}

def built():
    return ["planted_gap_return"]

def starred(state, *codes, **named):
    return {**state, "reasons": [*codes, *named.values()]}

def starred_caller(state):
    return starred(state, "planted_gap_args", reason="planted_gap_kwargs")
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
    found = written_reasons(PLANTED)
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
        "planted_call_through_module", "planted_method_through_module_class",
    }
    forms = "app/planted/forms.py"
    assert found[(forms, "caller")] == {"planted_argument", "planted_keyword_argument"}
    assert found[(forms, "run")] == {
        "planted_method_positional", "planted_method_keyword", "planted_static_method",
        "planted_static_through_class", "planted_class_method", "planted_method_through_its_class",
        "planted_method_through_type", "planted_method_through_dunder_class",
    }
    # The documented gaps, each planted above with a literal the reader would collect if it reached the form: a key a
    # call reads, a receiver other than a name or a reasons target, a string built at run time (an f-string, a .format,
    # a join), a class's attribute, a dict comprehension, a .get(), a loop over a call and over a dict's keys, a tuple
    # unpacked from a name, a starred target, a name alias, a lambda, a getattr callee, a function's return, and *args
    # and **kwargs.
    assert not codes & {"planted_key_read", "planted_gap", "join"}
    assert {code for code in codes if code.startswith("planted_gap")} == set()
