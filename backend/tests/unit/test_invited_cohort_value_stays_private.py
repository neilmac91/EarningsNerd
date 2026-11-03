"""The invited cohort's label stays private (CLAUDE.md rule 12; EN-BETA PB-01: never publish the cohort value).

The label is an opaque value that links invitations to a notice delivered privately (docs/LEGAL_READINESS.md,
"Invited-cohort registration"). It reaches code along one path, and no public response carries it (the admin's own
invite answers echo each invitation's stored cohort, as they did before the exception):

- the setting ``LEGAL_INVITED_COHORT`` is read in ``legal_readiness_service._configured_cohort`` alone;
- ``invited_cohort()``, which returns the label, is called only inside that service;
- ``require_account_admission()``, which hands the label on, is called only by the two account services:
  ``create_password_account`` passes it to ``invite_service.redeem_invite`` as a condition of its guarded UPDATE, and
  ``oauth_new_account_gate`` returns it to its one caller, ``oauth_create_account``, which passes it there too.

A new reader of the setting, or a new caller of any of those functions or of the gate helper, by attribute, by name or
by a string that names it (``getattr(settings, "...")``, ``getattr(service, "invited_cohort")()``), anywhere in
``backend/app`` or the top-level modules (``main.py``, ``task_worker_main.py``), fails here, so no route or service
starts returning the label without this list changing in review. Out of reach: a read of every setting at once
(``settings.model_dump()``, ``vars(settings)``), which no app code makes for a response, and a name built at run time.
The responses that exist are asserted free of the label in ``test_invited_cohort_registration.py`` and
``test_registration_config.py``.
"""
from __future__ import annotations

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"
SERVICE = "services/legal_readiness_service.py"
SETTING = "LEGAL_INVITED_COHORT"

PLANTED = '''
from app.services.legal_readiness_service import invited_cohort as label


def leak(settings):
    """Returns LEGAL_INVITED_COHORT."""
    return settings.LEGAL_INVITED_COHORT, getattr(settings, "LEGAL_INVITED_COHORT")


class Route:
    def get(self):
        def inner():
            return invited_cohort()
        return inner()


def handler(db, email):
    _error, _invite, cohort = oauth_new_account_gate(db, email=email, email_verified=True, invite_code_hash="x")
    return {"cohort": cohort}


def by_name(service):
    return getattr(service, "invited_cohort")()
'''


def _trees() -> dict[str, ast.AST]:
    """Every module under ``backend/app`` (by its path there) and every top-level module (``main.py`` and its
    siblings, as ``../<name>``, so the top level's ``__init__.py`` never takes the app package's key), parsed."""
    paths = {path.relative_to(APP_DIR).as_posix(): path for path in sorted(APP_DIR.rglob("*.py"))}
    paths.update({f"../{path.name}": path for path in sorted(BACKEND_DIR.glob("*.py"))})
    return {rel: ast.parse(path.read_text(encoding="utf-8")) for rel, path in paths.items()}


def _mentions(name: str, *, strings: bool = False, trees: dict[str, ast.AST] | None = None) -> dict[str, list[str]]:
    """Each mention of ``name`` in app/ (a name, an attribute, an imported alias and, with ``strings``, a string equal
    to it), by file and the dotted path of the functions around it. A definition of ``name`` is not a mention."""
    found: dict[str, list[str]] = {}
    for rel, tree in (_trees() if trees is None else trees).items():
        stack: list[str] = []
        hits: list[str] = []

        class Walk(ast.NodeVisitor):
            def visit_FunctionDef(self, node) -> None:
                stack.append(node.name)
                self.generic_visit(node)
                stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def generic_visit(self, node: ast.AST) -> None:
                named = (
                    node.id if isinstance(node, ast.Name) else
                    node.attr if isinstance(node, ast.Attribute) else
                    node.name if isinstance(node, ast.alias) else
                    node.value if strings and isinstance(node, ast.Constant) and isinstance(node.value, str) else None
                )
                if named == name:
                    hits.append(".".join(stack) or "<module>")
                super().generic_visit(node)

        Walk().visit(tree)
        if hits:
            found[rel] = hits
    return found


def test_the_cohort_setting_is_read_by_the_readiness_service_alone():
    # config.py declares it (an annotated name in the class body), the one other place it may appear.
    assert _mentions(SETTING, strings=True) == {"config.py": ["<module>"], SERVICE: ["_configured_cohort"]}


def test_the_label_leaves_the_service_only_for_the_redemptions_guard():
    assert _mentions("_configured_cohort", strings=True) == {SERVICE: ["invited_cohort_readiness", "invited_cohort"]}
    assert _mentions("invited_cohort", strings=True) == {
        SERVICE: ["is_invited_cohort_available", "admits_invite", "require_account_admission"],
        # The admin readiness answer's key, which holds the exception's conditions (invited_cohort_readiness), not the
        # label.
        "routers/admin.py": ["invite_readiness"],
    }
    assert _mentions("require_account_admission", strings=True) == {
        "services/auth_account_service.py": ["<module>", "create_password_account"],
        "services/oauth_account_service.py": ["<module>", "oauth_new_account_gate"],
    }
    # The gate helper returns the label with its verdict, so its callers are held as well.
    assert _mentions("oauth_new_account_gate", strings=True) == {
        "services/oauth_account_service.py": ["oauth_create_account"],
    }


def test_the_walk_sees_each_form():
    # The gate's reach, scored on planted forms: an attribute and a string read of the setting, an imported alias and
    # a call from a nested function in a method. A docstring that names the setting is no read.
    planted = {"routers/leak.py": ast.parse(PLANTED)}
    assert _mentions(SETTING, strings=True, trees=planted) == {"routers/leak.py": ["leak", "leak"]}
    assert _mentions(SETTING, trees=planted) == {"routers/leak.py": ["leak"]}
    assert _mentions("invited_cohort", trees=planted) == {"routers/leak.py": ["<module>", "get.inner"]}
    assert _mentions("invited_cohort", strings=True, trees=planted) == {
        "routers/leak.py": ["<module>", "get.inner", "by_name"],
    }
    assert _mentions("oauth_new_account_gate", trees=planted) == {"routers/leak.py": ["handler"]}


def test_the_walk_reads_every_module_once():
    # main.py defines public routes of its own (/, /health/detailed): the walk reads it and its siblings beside every
    # module of the app package, the package's own __init__.py among them, none taking another's place.
    trees = _trees()
    assert {"../main.py", "../task_worker_main.py", "../__init__.py", "__init__.py"} <= set(trees)
    assert len(trees) == len(list(APP_DIR.rglob("*.py"))) + len(list(BACKEND_DIR.glob("*.py")))
