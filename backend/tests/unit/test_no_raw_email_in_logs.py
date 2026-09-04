"""Structural gate: no logger call in app/ carries a raw e-mail address.

Audit 2026-09 finding C8 (`docs/audit-2026-09/05-security-ops.md`): plaintext addresses reached
Cloud Logging from `routers/auth.py`, and the follow-up sweep found the same in the Resend webhook
handlers, the admin invite flow and the waitlist signup path. Logs are retained and readable by
anyone with project log access, so the rule is: log an id (`user.id`, `invite.id`, Resend's
`email_id`) or `app.utils.pii.mask_email(...)` — never the address.

Encoded structurally (CLAUDE.md rule 12), the same move as `test_naive_utcnow_allowlist.py`: an
AST walk over every `logger.<level>(...)` call in app/ records the (file, enclosing function) of
any call whose arguments — positional, keyword, or f-string pieces — reference an address-bearing
expression (`<x>.email`, or a bare name such as `email` / `to` / `to_email` / `user_email`),
unless that expression is wrapped in one of the `app.utils.pii` sanitizers. The result must equal
the allow-list below EXACTLY: a new raw-address log line fails with a pointer to the fix, and a
sanctioned site that gets fixed must be dropped from the list in the same PR, so the list only
ever shrinks. It matches on (file, function), not line numbers, and ignores docstrings/comments.
"""
import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# The ONLY logger calls in app/ allowed to carry an address, as (file, function) pairs.
ALLOWED_RAW_EMAIL_LOG_SITES = {
    # GDPR-erasure audit line, written deliberately BEFORE the user row (and with it the only
    # id -> address mapping) is deleted. Whether that trail should carry the address or a hash is a
    # founder decision; until it is made the site stays sanctioned rather than silently changed.
    ("routers/users.py", "delete_user_account"),
    # Confirms which founder-configured DATA_QUALITY_REPORT_EMAIL the weekly report went to — an
    # operator setting from Settings, not user data.
    ("services/data_quality_service.py", "run_and_email"),
}

LOG_RECEIVERS = {"logger", "log", "_logger", "logging"}
LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
# `<anything>.email` in a log argument is an address; so is a bare name from this set.
EMAIL_ATTRS = {"email"}
EMAIL_NAMES = {"email", "to", "to_email", "to_addr", "user_email", "recipient", "recipient_email"}
# Calls whose result is log-safe by construction: their arguments are not inspected.
SANITIZERS = {"mask_email", "mask_recipients"}


def _callee_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_log_call(node: ast.Call) -> bool:
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr in LOG_METHODS):
        return False
    receiver = func.value
    if isinstance(receiver, ast.Name):
        return receiver.id in LOG_RECEIVERS
    # logging.getLogger("uvicorn.error").warning(...)
    return isinstance(receiver, ast.Call) and _callee_name(receiver) == "getLogger"


def _address_expressions(node: ast.AST) -> list[str]:
    """Source of every address-bearing sub-expression of a log argument, skipping sanitizer calls."""
    found: list[str] = []
    stack: list[ast.AST] = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, ast.Call) and _callee_name(current) in SANITIZERS:
            continue
        if isinstance(current, ast.Attribute) and current.attr in EMAIL_ATTRS:
            found.append(ast.unparse(current))
        elif isinstance(current, ast.Name) and current.id in EMAIL_NAMES:
            found.append(current.id)
        stack.extend(ast.iter_child_nodes(current))
    return found


class _RawEmailLogFinder(ast.NodeVisitor):
    """Collect (enclosing function, offending expressions) for every log call carrying an address."""

    def __init__(self) -> None:
        self.hits: list[tuple[str, list[str]]] = []
        self._stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Call(self, node: ast.Call) -> None:
        if _is_log_call(node):
            arguments = list(node.args) + [keyword.value for keyword in node.keywords]
            offending = [expr for argument in arguments for expr in _address_expressions(argument)]
            if offending:
                self.hits.append((self._stack[-1] if self._stack else "<module>", offending))
        self.generic_visit(node)


def _raw_email_log_sites(source: str) -> list[tuple[str, list[str]]]:
    finder = _RawEmailLogFinder()
    finder.visit(ast.parse(source))
    return finder.hits


# A gate that cannot fail proves nothing: pin what the finder catches and what it lets through.
_FINDER_PROBE = '''
import logging
from app.utils.pii import mask_email, mask_recipients
logger = logging.getLogger(__name__)

def fstring_attribute(user):
    logger.error(f"Verification email NOT sent to {user.email}")

def percent_bare_name(to):
    logger.info("Email delivered: %s to %s", "em_1", to)

def structured_extra(email):
    logger.warning("login failed", extra={"email": email})

async def async_handler(data):
    to = data.get("to")
    logger.warning(f"delayed for {to}")

def module_logger_call(payload):
    logging.getLogger("uvicorn.error").warning("bad %s", payload.email)

def masked_attribute_is_fine(user):
    logger.info("Email sent to %s", mask_email(user.email))

def masked_list_is_fine(data):
    logger.info(f"Email sent to {mask_recipients(data.get('to'))}")

def id_is_fine(user):
    logger.info("Reset email NOT sent to user id=%s", user.id)

def other_attribute_is_fine(user):
    logger.info("verified=%s email_id=%s", user.email_verified, user.email_id)

def not_a_logger(client, email):
    client.info(email)
'''


def test_finder_catches_every_shape_and_ignores_safe_ones():
    hits = _raw_email_log_sites(_FINDER_PROBE)
    assert hits == [
        ("fstring_attribute", ["user.email"]),
        ("percent_bare_name", ["to"]),
        ("structured_extra", ["email"]),
        ("async_handler", ["to"]),
        ("module_logger_call", ["payload.email"]),
    ]


def test_raw_email_log_sites_match_the_allowlist():
    found: dict[tuple[str, str], list[str]] = {}
    for py in sorted(APP_DIR.rglob("*.py")):
        rel = py.relative_to(APP_DIR).as_posix()
        for function, offending in _raw_email_log_sites(py.read_text(encoding="utf-8")):
            found.setdefault((rel, function), []).extend(offending)

    unexpected = {site: exprs for site, exprs in found.items() if site not in ALLOWED_RAW_EMAIL_LOG_SITES}
    assert not unexpected, (
        "Logger calls in app/ carry a raw e-mail address (audit C8: addresses must not reach logs):\n"
        + "\n".join(f"  {file}::{function}() logs {exprs}" for (file, function), exprs in sorted(unexpected.items()))
        + "\nLog an id instead (user.id, invite.id, Resend email_id), or wrap the address in "
        "app.utils.pii.mask_email(...) / mask_recipients(...). Extending ALLOWED_RAW_EMAIL_LOG_SITES "
        "needs a written reason next to the entry."
    )
    stale = ALLOWED_RAW_EMAIL_LOG_SITES - set(found)
    assert not stale, (
        "These sanctioned sites no longer log an address — delete them from "
        f"ALLOWED_RAW_EMAIL_LOG_SITES so the allow-list only ever shrinks: {sorted(stale)}"
    )
