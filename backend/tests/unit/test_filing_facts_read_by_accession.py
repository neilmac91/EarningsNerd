"""Structural gate: no code selects a filing's facts by ``FinancialFact.filing_id``.

``filing_id`` says which writer stored a fact row, never which filing reported it. The fact identity
(company, concept, period end, fiscal period, unit, accession) holds the accession and both writers
skip a stored identity, so a companyfacts row stored first at a filing's identity holds that filing's
cell with no filing owner, and a read keyed by ``filing_id`` misses it: the newest annual report's
whole chart, an older one's oldest year and balance. A filing's figures are the rows at its company and
accession (``facts/filing_scope.annual_filing_rows``; ``lessons/arch-read-a-filings-facts-by-its-accession.md``).

This test walks every Python file that can query the table (``backend/app``, ``backend/scripts``,
``backend/evals`` and the top-level modules, ``backend/main.py`` and ``backend/task_worker_main.py``
among them) and counts each mention of the column through the model as (path, enclosing function or
class, kind), holding the counts equal to ``ALLOWED``. A mention is:

* ``column``: the attribute ``filing_id`` on the model, however the model is reached: its name or an
  import alias (``from app.models import FinancialFact as F``), a module attribute
  (``models.FinancialFact``), a name the module binds to either or to ``aliased(...)`` of one (an alias
  of an alias too), and the table's column collections (``FinancialFact.__table__.c.filing_id``,
  ``.columns``);
* ``ownership``: that attribute tested against ``None`` (``.is_(None)``, ``.isnot(None)``,
  ``.is_not(None)``, ``== None``, ``!= None``): which writer stored the rows, whatever their filing. A
  kind of its own, so turning a listed ownership test into a key comparison fails;
* ``by_name``: the column named by a string where SQLAlchemy resolves it against the model:
  ``getattr(<model>, "filing_id")``, ``<model>.__table__.c["filing_id"]`` and ``.c.get("filing_id")``,
  and, in a module that names the model, a ``filing_id`` keyword to ``filter_by`` (spelled out or in a
  ``**{...}`` literal) and ``filing_id`` in a string handed to ``text``, ``column`` or ``literal_column``;
* ``implicit_join``: in a module that names the model, a join with no onclause (none given, or
  ``None``) among whose tables is the model or ``Filing``, each reached as above, through
  ``aliased(...)`` or as its ``__table__``: the methods ``join``/``outerjoin`` (one table, by position or
  as ``target``) and ``join_from``/``outerjoin_from`` (two); the functions ``join``/``outerjoin`` of
  ``sqlalchemy`` or ``sqlalchemy.orm`` (two, by position or as ``left``/``right``), called by a bare
  name or through an imported module; and a table's own ``.join``
  (``FinancialFact.__table__.join(Filing.__table__)``). Without an onclause SQLAlchemy infers one from
  the foreign keys, and ``filing_id`` is the model's one key to ``filings``: ``query(FinancialFact)
  .join(Filing)`` reads ``ON filings.id = financial_fact.filing_id`` with the column never named. A join
  that would infer another key is counted too; naming its onclause keeps it out;
* ``relationship``: a ``relationship(...)`` declared on the model, or one whose target is the model
  (by name or reference): an attribute that loads rows over the same inferred key.

Each listed mention says why it selects no filing's figures, and any new mention, a second one in a
listed scope included, fails until it is reviewed and listed.

Named gaps, review-checked: a comparison of a loaded row's attribute (``row.filing_id == x`` over rows
read another way) or of a copied state's key (``state["filing_id"]``, the audited repairs' snapshots); a
name built at run time (``getattr(FinancialFact, name)``, a ``**`` mapping that is not a literal); the
model reached through a call (``type(row)``, ``inspect(FinancialFact)``, a ``relationship`` target given
as a callable) or a name bound by anything but a plain assignment; a join's tables or onclause passed
by unpacking (``join(*tables)``), or a table reached through a name bound to it
(``t = FinancialFact.__table__``) or a call (``table("financial_fact")``); and SQL outside Python
(``ops/detection`` tests ownership only). ``test_the_scan_scores_every_planted_form`` scores the scan on
planted forms and look-alikes.
"""
from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOTS = ("app", "scripts", "evals")
MODEL = "FinancialFact"
PARENT = "Filing"
COLUMN = "filing_id"
_SQL_CALLS = frozenset({"text", "column", "literal_column"})
_NONE_TESTS = frozenset({"is_", "isnot", "is_not"})
# call -> the tables its method form names before the onclause. The function form (``sqlalchemy.join``,
# ``sqlalchemy.orm.outerjoin``) names one more first, the left table; a table's own ``.join`` is called on it.
_JOINS = {"join": 1, "outerjoin": 1, "join_from": 2, "outerjoin_from": 2}
_JOIN_TABLE_KEYWORDS = frozenset({"target", "left", "right", "from_"})
_COLUMN_WORD = re.compile(rf"\b{COLUMN}\b")

# (path from backend/, enclosing scope, kind) -> how many times. Each says why it selects no filing.
ALLOWED: dict[tuple[str, str, str], int] = {
    # Selected beside the other columns so ``evidence_kind`` keeps every filing-owned row out of the
    # companyfacts year evidence: an ownership test in Python, over a company's rows at period ends.
    ("app/services/facts/fiscal_evidence.py", "trusted_fiscal_years", "column"): 1,
    # ``.isnot(None)``: the companies that hold any per-filing row, the cohort each repair walks.
    ("scripts/relabel_filing_fy_facts.py", "run", "ownership"): 1,
    ("scripts/repair_filing_lineage.py", "run", "ownership"): 1,
}


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None


def _unaliased(node: ast.AST) -> ast.AST:
    """``aliased(<x>, ...)`` reads as ``<x>``."""
    return node.args[0] if isinstance(node, ast.Call) and _call_name(node) == "aliased" and node.args else node


def _table(node: ast.AST) -> ast.AST:
    """A join's table as the model it names: ``aliased(<x>, ...)`` and ``<x>.__table__`` read as ``<x>``."""
    node = _unaliased(node)
    return node.value if isinstance(node, ast.Attribute) and node.attr == "__table__" else node


def _imported_names(tree: ast.AST) -> set[str]:
    """The names a module binds by import: ``sa`` for ``import sqlalchemy as sa``, ``orm``, ``join``."""
    return {(alias.asname or alias.name).split(".")[0] for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}


def _model_names(tree: ast.AST, model: str = MODEL) -> set[str]:
    """The names this module binds to a model: the model's own, import aliases, and names assigned
    from a reference to it or from ``aliased(<reference>, ...)``, to a fixed point."""
    names = {model}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names |= {alias.asname or alias.name for alias in node.names if alias.name == model}
    assigns = [node for node in ast.walk(tree) if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value]
    while True:
        found = set(names)
        for node in assigns:
            if _is_model(_unaliased(node.value), names, model):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                found |= {target.id for target in targets if isinstance(target, ast.Name)}
        if found == names:
            return names
        names = found


def _is_model(node: ast.AST, names: set[str], model: str = MODEL) -> bool:
    return (isinstance(node, ast.Name) and node.id in names) or (isinstance(node, ast.Attribute) and node.attr == model)


def _is_column_collection(node: ast.AST, names: set[str]) -> bool:
    """``<model>.__table__.c`` or ``<model>.__table__.columns``."""
    return (isinstance(node, ast.Attribute) and node.attr in {"c", "columns"}
            and isinstance(node.value, ast.Attribute) and node.value.attr == "__table__"
            and _is_model(node.value.value, names))


def _names_column(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == COLUMN


def _is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


class _Finder(ast.NodeVisitor):
    def __init__(self, tree: ast.AST) -> None:
        self.names = _model_names(tree)
        self.parents = _model_names(tree, PARENT)
        self.modules = _imported_names(tree) - self.names - self.parents
        self.names_model = any(_is_model(node, self.names) for node in ast.walk(tree)
                               if isinstance(node, (ast.Name, ast.Attribute))) or any(
            isinstance(node, ast.ImportFrom) and any(alias.name == MODEL for alias in node.names)
            for node in ast.walk(tree))
        self.mentions: Counter[tuple[str, str]] = Counter()
        self._stack: list[str] = []
        self._owned: set[int] = set()  # column nodes already counted as an ownership test

    def _is_column(self, node: ast.AST) -> bool:
        return isinstance(node, ast.Attribute) and node.attr == COLUMN and (
            _is_model(node.value, self.names) or _is_column_collection(node.value, self.names))

    def _implicit_join(self, node: ast.Call, name: str) -> bool:
        """A join that names no onclause (none, or ``None``) with the model or ``Filing`` among its
        tables: the positional ones before the onclause, those passed by keyword, and a table receiver."""
        receiver = node.func.value if isinstance(node.func, ast.Attribute) else None
        root = receiver
        while isinstance(root, ast.Attribute):
            root = root.value
        function_form = receiver is None or isinstance(root, ast.Name) and root.id in self.modules
        before_onclause = _JOINS[name] + int(function_form and name in {"join", "outerjoin"})
        tables = [*node.args[:before_onclause], *(kw.value for kw in node.keywords if kw.arg in _JOIN_TABLE_KEYWORDS)]
        if receiver is not None and not function_form:
            tables.append(receiver)  # a table's own ``.join``; a query or select is no table
        onclauses = [*node.args[before_onclause:before_onclause + 1],
                     *(kw.value for kw in node.keywords if kw.arg == "onclause")]
        return all(_is_none(onclause) for onclause in onclauses) and any(
            _is_model(_table(table), self.names) or _is_model(_table(table), self.parents, PARENT) for table in tables)

    def _ownership(self, column: ast.AST) -> None:
        self._owned.add(id(column))
        self._count("ownership")

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
        if self._is_column(node) and id(node) not in self._owned:
            self._count("column")
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        sides = [node.left, *node.comparators]
        if (len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq))
                and any(_is_none(side) for side in sides)):
            for side in sides:
                if self._is_column(side):
                    self._ownership(side)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if _is_column_collection(node.value, self.names) and _names_column(node.slice):
            self._count("by_name")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node)
        func = node.func
        if (name in _NONE_TESTS and isinstance(func, ast.Attribute) and self._is_column(func.value)
                and len(node.args) == 1 and _is_none(node.args[0])):
            self._ownership(func.value)
        elif name == "getattr" and len(node.args) >= 2 and _is_model(node.args[0], self.names) and _names_column(node.args[1]):
            self._count("by_name")
        elif (name == "get" and isinstance(func, ast.Attribute) and _is_column_collection(func.value, self.names)
              and node.args and _names_column(node.args[0])):
            self._count("by_name")
        elif self.names_model and name == "filter_by" and any(
                kw.arg == COLUMN or kw.arg is None and isinstance(kw.value, ast.Dict)
                and any(key is not None and _names_column(key) for key in kw.value.keys)
                for kw in node.keywords):
            self._count("by_name")
        elif self.names_model and name in _SQL_CALLS and any(
                isinstance(arg, ast.Constant) and isinstance(arg.value, str) and _COLUMN_WORD.search(arg.value)
                for arg in node.args):
            self._count("by_name")
        elif self.names_model and name in _JOINS and self._implicit_join(node, name):
            self._count("implicit_join")
        elif name == "relationship" and (self._stack[-1:] == [MODEL] or node.args and (
                _is_model(node.args[0], self.names)
                or isinstance(node.args[0], ast.Constant) and node.args[0].value == MODEL)):
            self._count("relationship")
        self.generic_visit(node)


def mentions(source: str) -> Counter[tuple[str, str]]:
    tree = ast.parse(source)
    finder = _Finder(tree)
    finder.visit(tree)
    return finder.mentions


def _python_files():
    yield from sorted(BACKEND_DIR.glob("*.py"))
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
        "company and accession (facts/filing_scope.annual_filing_rows), and name a join's onclause; list "
        "an ownership test or a selected column here with why it selects no filing's figures."
    )


def test_the_scan_reads_every_top_level_module():
    """A process entry point beside ``main.py`` (the task worker's) can query the table too."""
    scanned = set(_python_files())
    assert {BACKEND_DIR / "main.py", BACKEND_DIR / "task_worker_main.py"} <= scanned
    assert set(BACKEND_DIR.glob("*.py")) <= scanned


def test_the_scan_scores_every_planted_form():
    planted = mentions(
        '"""FinancialFact.filing_id in a docstring is prose."""\n'
        "from app.models import Company, Filing, FinancialFact, Summary\n"
        "from app.models import FinancialFact as Fact, Filing as Report\n"
        "from app import models\n"
        "import os, sqlalchemy as sa\n"
        "from sqlalchemy import join, orm\n"
        "from sqlalchemy.orm import aliased\n"
        "Alias = Fact\n"
        "Parent = aliased(Report)\n"
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
        "def more_by_name(db, fid):\n"
        "    db.query(FinancialFact).filter_by(**{'filing_id': fid})\n"
        "    return FinancialFact.__table__.c.get('filing_id') == fid\n"
        "class Reader:\n"
        "    def owned(self, db):\n"
        "        return db.query(FinancialFact).filter(FinancialFact.filing_id.isnot(None))\n"
        "def ownership(db):\n"
        "    db.query(FinancialFact).filter(FinancialFact.filing_id.is_(None), Fact.filing_id.is_not(None))\n"
        "    return db.query(FinancialFact).filter(FinancialFact.filing_id == None, None != Twice.filing_id)\n"
        "def keyed_like_an_ownership_test(db, fid):\n"
        "    return db.query(FinancialFact).filter(FinancialFact.filing_id.is_(fid), FinancialFact.filing_id != fid)\n"
        "def implicit_joins(db, fid):\n"
        "    db.query(FinancialFact).join(Filing).filter(Filing.id == fid)\n"
        "    db.query(Filing).join(Fact, isouter=True)\n"
        "    db.query(FinancialFact).outerjoin(aliased(models.Filing))\n"
        "    db.query(FinancialFact).join(Report), db.query(Fact).join(Parent)\n"
        "    select(FinancialFact).select_from(join(FinancialFact, Filing))\n"
        "    select(Fact).select_from(sa.outerjoin(Filing, Fact)), orm.join(FinancialFact, Filing, None)\n"
        "    select(Fact).select_from(sa.join(left=Fact, right=Filing))\n"
        "    db.query(FinancialFact).join(Filing.__table__), FinancialFact.__table__.join(Filing.__table__)\n"
        "    Fact.__table__.join(Company.__table__)\n"
        "    db.query(FinancialFact).join(target=Filing), db.query(FinancialFact).join(Filing, None)\n"
        "    return select(FinancialFact).join_from(FinancialFact, Filing)\n"
        "def look_alikes(db, row, state, fid, name, mapping):\n"
        "    db.query(Summary).filter(Summary.filing_id == fid)\n"
        "    getattr(FinancialFact, name)\n"
        "    db.query(FinancialFact).join(Filing, FinancialFact.accession == Filing.accession_number)\n"
        "    db.query(Filing).join(FinancialFact, onclause=FinancialFact.accession == Filing.accession_number)\n"
        "    join(FinancialFact, Filing, FinancialFact.accession == Filing.accession_number)\n"
        "    FinancialFact.__table__.join(Filing.__table__, FinancialFact.accession == Filing.accession_number)\n"
        "    os.path.join(name, 'Filing'), sa.join(Summary, Company)\n"
        "    db.query(Summary).join(Company), ', '.join(name), db.query(FinancialFact).filter_by(**mapping)\n"
        "    return row.filing_id == fid, state['filing_id'], {'filing_id': fid}, 'filing_id'\n"
    )
    assert planted == Counter({
        ("direct", "column"): 1, ("through_aliases", "column"): 3, ("module_attribute", "column"): 1,
        ("table_columns", "column"): 2, ("table_columns", "by_name"): 1, ("by_name", "by_name"): 4,
        ("more_by_name", "by_name"): 2, ("owned", "ownership"): 1, ("ownership", "ownership"): 4,
        ("keyed_like_an_ownership_test", "column"): 2, ("implicit_joins", "implicit_join"): 15,
    })
    # A relationship on the model, or one to it, loads rows over the same inferred key.
    assert mentions(
        "from app.models import FinancialFact as Fact\n"
        "class FinancialFact(Base):\n"
        "    filing = relationship('Filing')\n"
        "class Filing(Base):\n"
        "    facts = relationship('FinancialFact', back_populates='filing')\n"
        "    also = relationship(Fact)\n"
        "    company = relationship('Company')\n"
    ) == Counter({("FinancialFact", "relationship"): 1, ("Filing", "relationship"): 2})
    # filter_by, SQL strings and joins resolve against whatever the query reads: only a module that
    # names the model is in scope for them.
    assert mentions("def f(db, fid):\n    return db.query(Summary).join(Filing).filter_by(filing_id=fid)\n") == Counter()
