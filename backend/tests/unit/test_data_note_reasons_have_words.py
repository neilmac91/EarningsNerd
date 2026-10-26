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
4. an `append`, `extend` or `insert` on such a target (`reasons.append("calculation_mismatch")`);
5. an argument bound to a parameter that flows into one of the above, at any call of a function or method of that
   name in `app/` (`_quarantine(state, "repair_rolled_back")`, whose `reason` becomes `"reasons": [reason]`), to a
   fixpoint. A method's arguments bind after the `self` an object supplies (`self._quarantine(state, code)`) and the
   `cls` an object or its class supplies; through its class's name a method takes `self` as its first argument
   (`Repair._quarantine(repair, state, code)`), and a static method binds from the first.

What a value can hold is read through:
- string literals; list, tuple and set displays and their starred items; `or`, `and`, a conditional's arms and `+`;
- `list()`, `sorted()`, `set()`, `tuple()`, `frozenset()` and `dict.fromkeys()` of an argument;
- a comprehension's element, each loop name read through its iterable;
- a name, through its every binding in the same function or at module level: an assignment (plain, annotated,
  augmented, a walrus, or one item of a tuple display unpacked into a tuple), or a `for` loop's target, which holds
  its iterable's items (a tuple target is paired item by item over a display of tuples, `enumerate()` or `zip()`);
- a name imported from another module under `app/` (`from app.x import CODE`, `from .x import CODE as OTHER`) or a
  module's attribute (`from app import x` or `import app.x as x`, then `x.CODE`), through that module's bindings;
- an item of a dict display such a name holds (`fallback[kind]` reads every value of `fallback`).
A string read by a call (`provenance.get("reasons", [])`) is a key, not a value, and is not collected.

Out of reach, review-checked: a reason built at run time (an f-string, a `.format`, a join); one that crosses into a
`reasons` list through what the reader does not follow (an attribute of an object, a dict built by a comprehension, a
function's return, a loop over anything but a display, a name or one of the three calls above); a method call on a
receiver other than a `reasons` target (`provenance.setdefault("reasons", []).append(...)`); a method called through
anything but an object or its class's own name (`type(self)._quarantine(self, state, code)`); and a parameter bound
through `*args` or `**kwargs`. Each is planted in `test_the_reader_finds_each_form_and_names_its_gaps` below, which asserts the
reader does not find it, so a change that reaches one fails there until this list is updated.

Some modules keep lists named `reasons` that never reach a fact's provenance or a data note: the summary quality
tier's reasons and the Copilot's quotation checks. EXEMPT names each such site by file and function; an exempt site
must still write a reason (one find), so an exemption cannot outlive its code.
"""
from __future__ import annotations

import ast
from pathlib import Path

from app.services.trend_analysis.data_notes import REASONS

APP = Path(__file__).resolve().parents[2] / "app"
WRAPPERS = frozenset({"list", "sorted", "set", "tuple", "frozenset"})
LIST_METHODS = frozenset({"append", "extend", "insert"})
# (file under backend/, function) -> why its `reasons` never reach a data note.
EXEMPT = {
    ("app/services/summary_generation_service.py", "assess_quality"):
        "a summary's quality tier: prose reasons for the partial tier, stored on the summary, never on a fact",
    ("app/services/copilot/quotations.py", "_displayed_quotation_reasons"):
        "the Copilot's quotation checks: why a quotation was refused, never a fact's provenance",
}
# Reasons the gate must find, so a reader that went blind fails: each emitter the data notes depend on.
KNOWN = frozenset({
    "not_in_dataset", "legacy_unknown", "source_check_needed",  # data_notes._issue's fallbacks
    "legacy_calculation", "unsupported_eps_calculation",  # fact_provenance
    "missing_calculation_inputs", "calculation_mismatch",  # facts/lineage.annotate_filing_calculations
    "zero_where_prior_nonzero", "magnitude_vs_prior", "eps_sign_vs_net_income", "diluted_gt_basic",
    "period_mismatch",  # facts/reconcile, recorded by lineage.local_reconciliation
    "legacy_calculation_not_supported", "repair_rolled_back",  # quarterly_fact_repair._quarantine
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
                 module: _Scope | None = None):
        self.path, self.name, self.imports, self.registry = path, name, imports, registry
        self.module_scope = module or self
        self.params: list[str] = []
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = function.args
            # *args and **kwargs shadow a module name too, though a call binds neither (out of reach).
            self.params = [arg.arg for arg in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs,
                                                *filter(None, (arguments.vararg, arguments.kwarg))]]
        self.local = _assigned(body)
        self.classes = {node.name for node in body if isinstance(node, ast.ClassDef)}


def _module_of(expr: ast.AST, scope: _Scope) -> str | None:
    """The module under `app/` an expression names: an imported module, or a dotted attribute of one."""
    if isinstance(expr, ast.Name):
        if expr.id in scope.params or (scope is not scope.module_scope and expr.id in scope.local):
            return None
        module, attribute = scope.imports.get(expr.id, (None, None))
        return module if module is not None and attribute is None else None
    if isinstance(expr, ast.Attribute):
        parent = _module_of(expr.value, scope)
        if parent is not None and f"{parent}.{expr.attr}" in scope.registry:
            return f"{parent}.{expr.attr}"
        return f"{parent}.{expr.attr}" if parent is not None and any(
            name.startswith(f"{parent}.{expr.attr}.") for name in scope.registry) else None
    return None


Binding = tuple[ast.expr, _Scope, object, dict]


def _resolve(name: str, scope: _Scope, flows: set[str], seen: frozenset, bound: dict) -> list[Binding]:
    """What a name may hold: each expression with the scope and loop names to read it in, and its cycle key."""
    if name in bound:
        key = ("loop", id(bound[name]))
        return [] if key in seen else [(held, scope, key, bound) for held in bound[name]]
    key = (scope.path, scope.name, name)
    if key in seen:
        return []
    if name in scope.local:
        return [(held, scope, key, {}) for held in scope.local[name]]
    if name in scope.params:
        flows.add(name)
        return []
    module = scope.module_scope
    if module is not scope:
        return _resolve(name, module, flows, seen, {})
    source, attribute = scope.imports.get(name, (None, None))
    if attribute is not None and source in scope.registry:
        return _resolve(attribute, scope.registry[source], flows, seen | {key}, {})
    return []


def _values(expr: ast.AST | None, scope: _Scope, flows: set[str], seen: frozenset = frozenset(),
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
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
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
    """Each node with the scope it is read in: its innermost function, or the module."""
    stack: list[tuple[ast.AST, _Scope]] = [(tree, module)]
    while stack:
        node, scope = stack.pop()
        for child in ast.iter_child_nodes(node):
            inner = scope
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = _Scope(module.path, child.name, child, child.body, module.imports, module.registry, module)
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
    if _module_of(func.value, scope) is not None:
        return "module"
    value = func.value
    if (isinstance(value, ast.Name) and value.id not in scope.params
            and not (scope is not scope.module_scope and value.id in scope.local)):
        source, attribute = scope.imports.get(value.id, (None, None))
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
    # A function's or method's name -> (its positional parameters, "function" or the method's kind).
    definitions: dict[str, list[tuple[list[str], str]]] = {}
    for node, _scope in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = node.args
            definitions.setdefault(node.name, []).append(
                ([arg.arg for arg in [*arguments.posonlyargs, *arguments.args]], kinds.get(id(node), "function")))
    found: dict[tuple[str, str], set[str]] = {}
    flowing: set[tuple[str, str]] = set()  # (function name, parameter) that reach a reasons list

    def collect(expr: ast.AST, scope: _Scope) -> None:
        flows: set[str] = set()
        codes = _values(expr, scope, flows)
        if codes:
            found.setdefault((scope.path, scope.name), set()).update(codes)
        flowing.update((scope.name, param) for param in flows)

    for node, scope in nodes:
        for expr in _sites(node):
            collect(expr, scope)
    calls = [(node, scope) for node, scope in nodes if isinstance(node, ast.Call)]
    while True:
        before = len(flowing)
        for node, scope in calls:
            receiver = _receiver(node.func, scope)
            callee = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else None)
            for params, kind in definitions.get(callee, []):
                if (kind, receiver) not in SKIPPED:
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


# A package of three modules: the forms the reader follows, each code named for its form, and every documented gap,
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
        )

LOOP_SOURCE = {"review": "planted_gap_loop_over_a_call"}

def gaps(provenance, kind, record):
    provenance.setdefault("reasons", []).append("planted_gap_receiver")
    provenance["reasons"] = [f"planted_gap_{kind}"]
    provenance["reasons"] = ["planted_gap_format_{}".format(kind), "_".join(("planted_gap", "join"))]
    provenance["reasons"] = [record.code]
    by_kind = {name: "planted_gap_dict_comprehension" for name in ("review",)}
    provenance["reasons"] = [by_kind[kind]]
    for code in LOOP_SOURCE.values():
        provenance["reasons"].append(code)
    return {"reasons": built()}

def built():
    return ["planted_gap_return"]

def starred(state, *codes, **named):
    return {**state, "reasons": [*codes, *named.values()]}

def starred_caller(state, repair):
    return (
        starred(state, "planted_gap_args", reason="planted_gap_kwargs"),
        type(repair)._quarantine(repair, state, "planted_gap_method_through_type"),
    )
''',
}


def test_the_reader_finds_each_form_and_names_its_gaps():
    found = written_reasons(PLANTED)
    codes = {code for site_codes in found.values() for code in site_codes}
    assert {code for code in codes if not code.startswith("planted_gap")} == {
        "planted_dict", "planted_keyword", "planted_append", "planted_augmented", "planted_extend", "planted_walrus",
        "planted_argument", "planted_keyword_argument", "planted_relay", "planted_module_dict",
        "planted_imported_constant", "planted_imported_alias", "planted_relative_import", "planted_module_attribute",
        "planted_loop_over_module_attribute", "planted_loop", "planted_loop_pair", "planted_enumerate", "planted_zip",
        "planted_comprehension_iterable", "planted_tuple_unpacked", "planted_unpacked_name",
        "planted_method_positional", "planted_method_keyword", "planted_static_method", "planted_static_through_class",
        "planted_class_method", "planted_method_through_its_class",
    }
    forms = "app/planted/forms.py"
    assert found[(forms, "caller")] == {"planted_argument", "planted_keyword_argument"}
    assert found[(forms, "run")] == {
        "planted_method_positional", "planted_method_keyword", "planted_static_method",
        "planted_static_through_class", "planted_class_method", "planted_method_through_its_class",
    }
    # The documented gaps, each planted above: a key a call reads, a receiver other than a reasons target, a string
    # built at run time (an f-string, a .format, a join), an object's attribute, a dict built by a comprehension, a
    # loop over a call, a function's return, *args and **kwargs, and a method called through type(self).
    assert not codes & {
        "planted_key_read", "planted_gap_receiver", "planted_gap_format_{}", "planted_gap", "join",
        "planted_gap_dict_comprehension", "planted_gap_loop_over_a_call", "planted_gap_return", "planted_gap_args",
        "planted_gap_kwargs", "planted_gap_method_through_type",
    }
    assert {code for code in codes if code.startswith("planted_gap")} == set()
