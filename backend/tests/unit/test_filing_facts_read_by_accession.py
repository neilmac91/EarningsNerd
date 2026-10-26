"""Structural gate: no code selects a filing's facts by ``FinancialFact.filing_id``.

``filing_id`` says which writer stored a fact row, never which filing reported it. The fact identity
(company, concept, period end, fiscal period, unit, accession) holds the accession and both writers
skip a stored identity, so a companyfacts row stored first at a filing's identity holds that filing's
cell with no filing owner, and a read keyed by ``filing_id`` misses it: the newest annual report's
whole chart, an older one's oldest year and balance. A filing's figures are the rows at its company and
accession (``facts/filing_scope.annual_filing_rows``; ``lessons/arch-read-a-filings-facts-by-its-accession.md``).

This test walks every Python file that can query the table (``backend/app``, ``backend/scripts``,
``backend/evals`` and ``backend/main.py``) and counts each mention of the column through the model as
(path, enclosing function or class, kind), holding the counts equal to ``ALLOWED``. A mention is:

* ``column``: the attribute ``filing_id`` on the model, however the model is reached: its name or an
  import alias (``from app.models import FinancialFact as F``), a module attribute
  (``models.FinancialFact``), a name the module binds to either or to ``aliased(...)`` of one (an alias
  of an alias too), and the table's column collections (``FinancialFact.__table__.c.filing_id``,
  ``.columns``);
* ``by_name``: the column named by a string where SQLAlchemy resolves it against the model:
  ``getattr(<model>, "filing_id")`` and ``<model>.__table__.c["filing_id"]``, and, in a module that names
  the model, a ``filing_id=`` keyword to ``filter_by`` and ``filing_id`` in a string handed to ``text``,
  ``column`` or ``literal_column``.

An ownership test (``.isnot(None)``: the rows the per-filing writer stored, whatever their filing) or a
selected column is a mention too: each listed one says why it selects no filing's figures, and any new
mention, a second one in a listed scope included, fails until it is reviewed and listed.

Named gaps, review-checked: a comparison of a loaded row's attribute (``row.filing_id == x`` over rows
read another way) or of a copied state's key (``state["filing_id"]``, the audited repairs' snapshots); a
name built at run time (``getattr(FinancialFact, name)``); the model reached through a call
(``type(row)``, ``inspect(FinancialFact)``) or a name bound by anything but a plain assignment; and SQL
outside Python (``ops/detection`` tests ownership only). ``test_the_scan_scores_every_planted_form``
scores the scan on planted forms and look-alikes.
"""
from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOTS = ("app", "scripts", "evals")
MODEL = "FinancialFact"
COLUMN = "filing_id"
_SQL_CALLS = frozenset({"text", "column", "literal_column"})
_COLUMN_WORD = re.compile(rf"\b{COLUMN}\b")

# (path from backend/, enclosing scope, kind) -> how many times. Each says why it selects no filing.
ALLOWED: dict[tuple[str, str, str], int] = {
    # Selected beside the other columns so ``evidence_kind`` keeps every filing-owned row out of the
    # companyfacts year evidence: an ownership test in Python, over a company's rows at period ends.
    ("app/services/facts/fiscal_evidence.py", "trusted_fiscal_years", "column"): 1,
    # ``.isnot(None)``: the companies that hold any per-filing row, the cohort each repair walks.
    ("scripts/relabel_filing_fy_facts.py", "run", "column"): 1,
    ("scripts/repair_filing_lineage.py", "run", "column"): 1,
}


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None


def _model_names(tree: ast.AST) -> set[str]:
    """The names this module binds to the model: the model's own, import aliases, and names assigned
    from a model reference or from ``aliased(<model reference>, ...)``, to a fixed point."""
    names = {MODEL}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names |= {alias.asname or alias.name for alias in node.names if alias.name == MODEL}
    assigns = [node for node in ast.walk(tree) if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value]
    while True:
        found = set(names)
        for node in assigns:
            value = node.value
            if isinstance(value, ast.Call) and _call_name(value) == "aliased" and value.args:
                value = value.args[0]
            if _is_model(value, names):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                found |= {target.id for target in targets if isinstance(target, ast.Name)}
        if found == names:
            return names
        names = found


def _is_model(node: ast.AST, names: set[str]) -> bool:
    return (isinstance(node, ast.Name) and node.id in names) or (isinstance(node, ast.Attribute) and node.attr == MODEL)


def _is_column_collection(node: ast.AST, names: set[str]) -> bool:
    """``<model>.__table__.c`` or ``<model>.__table__.columns``."""
    return (isinstance(node, ast.Attribute) and node.attr in {"c", "columns"}
            and isinstance(node.value, ast.Attribute) and node.value.attr == "__table__"
            and _is_model(node.value.value, names))


def _names_column(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == COLUMN


class _Finder(ast.NodeVisitor):
    def __init__(self, tree: ast.AST) -> None:
        self.names = _model_names(tree)
        self.names_model = any(_is_model(node, self.names) for node in ast.walk(tree)
                               if isinstance(node, (ast.Name, ast.Attribute))) or any(
            isinstance(node, ast.ImportFrom) and any(alias.name == MODEL for alias in node.names)
            for node in ast.walk(tree))
        self.mentions: Counter[tuple[str, str]] = Counter()
        self._stack: list[str] = []

    def _scoped(self, node, name: str) -> None:
        self._stack.append(name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scoped(node, node.name)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scoped(node, node.name)

    def _count(self, kind: str) -> None:
        self.mentions[(self._stack[-1] if self._stack else "<module>", kind)] += 1

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == COLUMN and (_is_model(node.value, self.names) or _is_column_collection(node.value, self.names)):
            self._count("column")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if _is_column_collection(node.value, self.names) and _names_column(node.slice):
            self._count("by_name")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node)
        if name == "getattr" and len(node.args) >= 2 and _is_model(node.args[0], self.names) and _names_column(node.args[1]):
            self._count("by_name")
        elif self.names_model and name == "filter_by" and any(kw.arg == COLUMN for kw in node.keywords):
            self._count("by_name")
        elif self.names_model and name in _SQL_CALLS and any(
                isinstance(arg, ast.Constant) and isinstance(arg.value, str) and _COLUMN_WORD.search(arg.value)
                for arg in node.args):
            self._count("by_name")
        self.generic_visit(node)


def mentions(source: str) -> Counter[tuple[str, str]]:
    tree = ast.parse(source)
    finder = _Finder(tree)
    finder.visit(tree)
    return finder.mentions


def _python_files():
    yield BACKEND_DIR / "main.py"
    for root in ROOTS:
        yield from sorted((BACKEND_DIR / root).rglob("*.py"))


def test_no_code_selects_a_filings_facts_by_filing_id():
    found: Counter[tuple[str, str, str]] = Counter()
    for path in _python_files():
        rel = path.relative_to(BACKEND_DIR).as_posix()
        for (scope, kind), count in mentions(path.read_text(encoding="utf-8")).items():
            found[(rel, scope, kind)] += count
    unexpected = {key: count for key, count in found.items() if ALLOWED.get(key) != count}
    stale = sorted(key for key in ALLOWED if key not in found)
    assert not unexpected and not stale, (
        "Mentions of FinancialFact.filing_id drifted from the reviewed list.\n"
        f"  new or recounted: {unexpected}\n  stale (prune them): {stale}\n"
        "filing_id says which writer stored a row, not which filing reported it: a companyfacts row "
        "stored first at a filing's identity holds its cell with no owner. Read a filing's facts at its "
        "company and accession (facts/filing_scope.annual_filing_rows); list an ownership test or a "
        "selected column here with why it selects no filing's figures."
    )


def test_the_scan_scores_every_planted_form():
    planted = mentions(
        '"""FinancialFact.filing_id in a docstring is prose."""\n'
        "from app.models import FinancialFact, Summary\n"
        "from app.models import FinancialFact as Fact\n"
        "from app import models\n"
        "from sqlalchemy.orm import aliased\n"
        "Alias = Fact\n"
        "Twice = Alias\n"
        "Other: type = aliased(FinancialFact, name='f2')\n"
        "def direct(db, fid):\n"
        "    return db.query(FinancialFact).filter(FinancialFact.filing_id == fid)\n"
        "def through_aliases(db, fid):\n"
        "    db.query(Fact).filter(Fact.filing_id.in_([fid]))\n"
        "    db.query(Twice).filter(fid == Twice.filing_id)\n"
        "    return db.query(Other).filter(Other.filing_id == fid)\n"
        "def module_attribute(db, fid):\n"
        "    return db.query(models.FinancialFact).filter(models.FinancialFact.filing_id == fid)\n"
        "def table_columns(fid):\n"
        "    return [FinancialFact.__table__.c.filing_id == fid, FinancialFact.__table__.columns.filing_id,\n"
        "            FinancialFact.__table__.c['filing_id']]\n"
        "def by_name(db, fid):\n"
        "    db.query(FinancialFact).filter(getattr(FinancialFact, 'filing_id') == fid)\n"
        "    db.query(FinancialFact).filter_by(filing_id=fid)\n"
        "    db.query(FinancialFact).filter(text('filing_id = :f'), column('filing_id'))\n"
        "class Reader:\n"
        "    def owned(self, db):\n"
        "        return db.query(FinancialFact).filter(FinancialFact.filing_id.isnot(None))\n"
        "def look_alikes(db, row, state, fid, name):\n"
        "    db.query(Summary).filter(Summary.filing_id == fid)\n"
        "    getattr(FinancialFact, name)\n"
        "    return row.filing_id == fid, state['filing_id'], {'filing_id': fid}, 'filing_id'\n"
    )
    assert planted == Counter({
        ("direct", "column"): 1, ("through_aliases", "column"): 3, ("module_attribute", "column"): 1,
        ("table_columns", "column"): 2, ("table_columns", "by_name"): 1, ("by_name", "by_name"): 4,
        ("owned", "column"): 1,
    })
    # filter_by and SQL strings resolve against whatever the query reads: only a module that names the
    # model is in scope for them.
    assert mentions("def f(db, fid):\n    return db.query(Summary).filter_by(filing_id=fid)\n") == Counter()
