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
3. an assignment, annotated or augmented, to a name `reasons`, an attribute `.reasons` or a `["reasons"]` item;
4. an `append`, `extend` or `insert` on such a target (`reasons.append("calculation_mismatch")`);
5. an argument bound to a parameter that flows into one of the above, at any call of a function of that name in
   `app/` (`_quarantine(state, "repair_rolled_back")`, whose `reason` becomes `"reasons": [reason]`), to a fixpoint.

What a value can hold is read through string literals, list, tuple and set displays and their starred items, `or`,
`and`, a conditional's arms, `+`, `list()`, `sorted()`, `set()`, `tuple()`, `frozenset()` and `dict.fromkeys()` of
an argument, a comprehension's element, a name assigned in the same function or at module level (followed through
its every assignment), and an item of a dict display such a name holds (`fallback[kind]` reads every value of
`fallback`). A string read by a call (`provenance.get("reasons", [])`) is a key, not a value, and is not collected.

Out of reach, review-checked: a reason built at run time (an f-string, a `.format`, a join); one that crosses into a
`reasons` list through a container read the reader does not follow (an attribute of an object, a dict built by a
comprehension, a function's return); a method call on a receiver other than a `reasons` target
(`provenance.setdefault("reasons", []).append(...)`); and a parameter bound through `*args` or `**kwargs`. Each is
planted in `test_the_reader_finds_each_form_and_names_its_gaps` below.

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


def _assigned(body: list[ast.stmt]) -> dict[str, list[ast.expr]]:
    """Every value a name is given in one scope, nested functions and classes left to their own scopes."""
    names: dict[str, list[ast.expr]] = {}
    stack = list(body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.setdefault(target.id, []).append(node.value)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name) and node.value:
            names.setdefault(node.target.id, []).append(node.value)
        elif isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
            names.setdefault(node.target.id, []).append(node.value)
        stack.extend(ast.iter_child_nodes(node))
    return names


class _Scope:
    def __init__(self, path: str, name: str, function: ast.AST | None, module: dict[str, list[ast.expr]]):
        self.path, self.name, self.module = path, name, module
        self.params: list[str] = []
        self.local: dict[str, list[ast.expr]] = {}
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = function.args
            self.params = [arg.arg for arg in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]]
            self.local = _assigned(function.body)


def _values(expr: ast.AST | None, scope: _Scope, flows: set[str], seen: frozenset = frozenset()) -> set[str]:
    """The string literals `expr` may hold as a reason; a parameter it reads joins `flows`."""
    if expr is None:
        return set()
    if isinstance(expr, ast.Constant):
        return {expr.value} if isinstance(expr.value, str) else set()
    if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        return set().union(*(_values(elt, scope, flows, seen) for elt in expr.elts))
    if isinstance(expr, ast.Starred):
        return _values(expr.value, scope, flows, seen)
    if isinstance(expr, ast.IfExp):
        return _values(expr.body, scope, flows, seen) | _values(expr.orelse, scope, flows, seen)
    if isinstance(expr, ast.BoolOp):
        return set().union(*(_values(value, scope, flows, seen) for value in expr.values))
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        return _values(expr.left, scope, flows, seen) | _values(expr.right, scope, flows, seen)
    if isinstance(expr, ast.Call) and expr.args and (
        (isinstance(expr.func, ast.Name) and expr.func.id in WRAPPERS)
        or (isinstance(expr.func, ast.Attribute) and expr.func.attr == "fromkeys")
    ):
        return _values(expr.args[0], scope, flows, seen)
    if isinstance(expr, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        bound = {target.id for generator in expr.generators for target in ast.walk(generator.target)
                 if isinstance(target, ast.Name)}
        return _values(expr.elt, scope, flows, seen | bound)
    if isinstance(expr, ast.Name):
        if expr.id in seen:
            return set()
        if expr.id in scope.params:
            flows.add(expr.id)
        held = scope.local.get(expr.id) or ([] if expr.id in scope.params else scope.module.get(expr.id, []))
        return set().union(*(_values(value, scope, flows, seen | {expr.id}) for value in held))
    if isinstance(expr, ast.Subscript) and isinstance(expr.value, ast.Name) and expr.value.id not in seen:
        held = scope.local.get(expr.value.id) or scope.module.get(expr.value.id, [])
        return set().union(*(_values(value, scope, flows, seen | {expr.value.id})
                             for display in held if isinstance(display, ast.Dict) for value in display.values))
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
    if isinstance(node, ast.Assign) and any(_is_reasons_target(target) for target in node.targets):
        return [node.value]
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)) and _is_reasons_target(node.target):
        return [node.value]
    return []


def _walk_scopes(tree: ast.Module, path: str):
    """Each node with the scope it is read in: its innermost function, or the module."""
    module = _assigned(tree.body)
    stack = [(tree, _Scope(path, "<module>", None, module))]
    while stack:
        node, scope = stack.pop()
        for child in ast.iter_child_nodes(node):
            inner = scope
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = _Scope(path, child.name, child, module)
            yield child, inner
            stack.append((child, inner))


def written_reasons(sources: dict[str, str]) -> dict[tuple[str, str], set[str]]:
    """Every string each (file, function) can write into a reasons list, forms 1 to 5."""
    trees = {path: ast.parse(source) for path, source in sources.items()}
    nodes = [(node, scope) for path, tree in trees.items() for node, scope in _walk_scopes(tree, path)]
    definitions: dict[str, list[list[str]]] = {}
    for node, scope in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = node.args
            definitions.setdefault(node.name, []).append([arg.arg for arg in [*arguments.posonlyargs, *arguments.args]])
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
            callee = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else None)
            for params in definitions.get(callee, []):
                for index, argument in enumerate(node.args):
                    if index < len(params) and (callee, params[index]) in flowing:
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


PLANTED = '''
def first(fact):
    fact["provenance"] = {"reasons": ["planted_dict"] if fact else []}

def second(provenance):
    provenance.update(validation="needs_review", reasons=["planted_keyword"])

def third():
    reasons: list[str] = []
    reasons.append("planted_append")
    reasons += ["planted_augmented"]
    reasons.extend(sorted({"planted_extend"}))
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

def gaps(provenance, kind):
    provenance.setdefault("reasons", []).append("planted_gap_receiver")
    provenance["reasons"] = [f"planted_gap_{kind}"]
    return {"reasons": built()}

def built():
    return ["planted_gap_return"]
'''


def test_the_reader_finds_each_form_and_names_its_gaps():
    found = written_reasons({"app/planted.py": PLANTED})
    codes = {code for site_codes in found.values() for code in site_codes}
    assert codes == {
        "planted_dict", "planted_keyword", "planted_append", "planted_augmented", "planted_extend",
        "planted_argument", "planted_keyword_argument", "planted_relay", "planted_module_dict",
    }
    assert found[("app/planted.py", "caller")] == {"planted_argument", "planted_keyword_argument"}
    # The documented gaps: a key a call reads, a receiver other than a reasons target, a string built at run time
    # and a function's return.
    assert not codes & {"planted_key_read", "planted_gap_receiver", "planted_gap_return"}
