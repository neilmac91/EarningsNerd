"""The invited cohort's label stays private (CLAUDE.md rule 12; EN-BETA PB-01: never publish the cohort value).

The label is an opaque value that links invitations to a notice delivered privately (docs/LEGAL_READINESS.md,
"Invited-cohort registration"). It reaches code along one path, and no response carries it:

- the setting ``LEGAL_INVITED_COHORT`` is read in ``legal_readiness_service._configured_cohort`` alone;
- ``invited_cohort()``, which returns the label, is called only inside that service;
- ``require_account_admission()``, which hands the label on, is called only by the two account services:
  ``create_password_account`` passes it to ``invite_service.redeem_invite`` as a condition of its guarded UPDATE, and
  ``oauth_new_account_gate`` returns it to its one caller, ``oauth_create_account``, which passes it there too.

A new reader of the setting, by attribute or by its name as a string (``getattr(settings, "...")``), or a new caller of
any of those functions or of the gate helper fails here, so no route or service starts returning the label without this
list changing in review. Out
of reach: a read of every setting at once (``settings.model_dump()``, ``vars(settings)``), which no app code makes for a
response. The responses that exist are asserted free of the label in ``test_invited_cohort_registration.py`` and
``test_registration_config.py``.
"""
from __future__ import annotations

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"
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
'''


def _trees() -> dict[str, ast.AST]:
    return {
        path.relative_to(APP_DIR).as_posix(): ast.parse(path.read_text(encoding="utf-8"))
        for path in sorted(APP_DIR.rglob("*.py"))
    }


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
    assert _mentions("_configured_cohort") == {SERVICE: ["invited_cohort_readiness", "invited_cohort"]}
    assert _mentions("invited_cohort") == {
        SERVICE: ["is_invited_cohort_available", "admits_invite", "require_account_admission"],
    }
    assert _mentions("require_account_admission") == {
        "services/auth_account_service.py": ["<module>", "create_password_account"],
        "services/oauth_account_service.py": ["<module>", "oauth_new_account_gate"],
    }
    # The gate helper returns the label with its verdict, so its callers are held as well.
    assert _mentions("oauth_new_account_gate") == {"services/oauth_account_service.py": ["oauth_create_account"]}


def test_the_walk_sees_each_form():
    # The gate's reach, scored on planted forms: an attribute and a string read of the setting, an imported alias and
    # a call from a nested function in a method. A docstring that names the setting is no read.
    planted = {"routers/leak.py": ast.parse(PLANTED)}
    assert _mentions(SETTING, strings=True, trees=planted) == {"routers/leak.py": ["leak", "leak"]}
    assert _mentions(SETTING, trees=planted) == {"routers/leak.py": ["leak"]}
    assert _mentions("invited_cohort", trees=planted) == {"routers/leak.py": ["<module>", "get.inner"]}
    assert _mentions("oauth_new_account_gate", trees=planted) == {"routers/leak.py": ["handler"]}
