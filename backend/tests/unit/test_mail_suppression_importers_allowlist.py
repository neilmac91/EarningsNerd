"""Who may read the invitation suppression list (EN-BETA PB-01; review of #1965).

The list (``mail_suppression_service``, the ``MailRecipient`` model) holds the pseudonymous hash of every address an
invitation was emailed to and of every address that unsubscribed, bounced or complained. Invitation email reads it,
through ``invite_delivery_service``; requested account mail (verification, password reset, the sign-in notices) never
does, since a reader who opted out of invitations still needs those. ``email_service``'s own senders are held by
``test_email_name_interpolation_allowlist.py``; this gate holds every other module in ``app/``: a router, a durable
mail task or another service that imported the list could start refusing account mail to a suppressed address, and no
behavioural test would cover every sender. A new reader joins the allowlist here with its reason, in the same diff.
"""
import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"

# Modules that may import the list's service, each with its reason.
SERVICE_IMPORTERS = {
    "app/services/invite_delivery_service.py": "invitation email: refuses a suppressed address, records opt-outs and feedback",
}
# Modules that may import the list's model, each with its reason.
MODEL_IMPORTERS = {
    "app/services/mail_suppression_service.py": "the list's own service",
    "app/models/__init__.py": "the models package's exports (create_all, the deletion checks)",
}


def _imports(tree: ast.AST) -> tuple[bool, bool]:
    """Whether the module imports the list's service, and whether it imports its model."""
    service = model = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                service |= alias.name == "app.services.mail_suppression_service"
                model |= alias.name == "app.models.invite_mail"
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = {alias.name for alias in node.names}
            service |= node.module == "app.services.mail_suppression_service" or (
                node.module == "app.services" and "mail_suppression_service" in names
            )
            model |= (node.module in ("app.models", "app.models.invite_mail") and "MailRecipient" in names) or (
                node.module == "app.models" and "invite_mail" in names
            )
    return service, model


def _readers() -> tuple[set[str], set[str]]:
    service, model = set(), set()
    for path in sorted(APP.rglob("*.py")):
        rel = path.relative_to(APP.parent).as_posix()
        imports_service, imports_model = _imports(ast.parse(path.read_text(encoding="utf-8")))
        if imports_service:
            service.add(rel)
        if imports_model:
            model.add(rel)
    return service, model


def test_only_invitation_email_reads_the_suppression_list():
    service, model = _readers()
    assert service == set(SERVICE_IMPORTERS), (
        "only invitation email may import mail_suppression_service; requested account mail never reads the list. "
        f"Unexpected: {sorted(service - set(SERVICE_IMPORTERS))}; gone: {sorted(set(SERVICE_IMPORTERS) - service)}"
    )
    assert model == set(MODEL_IMPORTERS), (
        "only the list's service may import MailRecipient. "
        f"Unexpected: {sorted(model - set(MODEL_IMPORTERS))}; gone: {sorted(set(MODEL_IMPORTERS) - model)}"
    )


def test_the_walk_sees_each_way_to_import_the_list():
    planted = {
        "from app.services import mail_suppression_service": (True, False),
        "from app.services.mail_suppression_service import suppression_for": (True, False),
        "import app.services.mail_suppression_service": (True, False),
        "from app.models import MailRecipient": (False, True),
        "from app.models.invite_mail import MailRecipient": (False, True),
        "from app.models import invite_mail": (False, True),
        "from app.services import email_service": (False, False),
        "from app.models import InviteDelivery": (False, False),
    }
    for source, expected in planted.items():
        assert _imports(ast.parse(source)) == expected, source
