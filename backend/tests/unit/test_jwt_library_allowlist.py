"""Keep retired JWT imports and their dependency chain out of the backend (W3-6)."""
import ast
from pathlib import Path
import re

BACKEND = Path(__file__).resolve().parents[2]
RETIRED_DISTRIBUTIONS = {"python-jose", "ecdsa", "rsa", "pyasn1"}


def test_jwt_library_and_lock_exclude_retired_jose_chain():
    roots = [BACKEND / directory for directory in ("app", "scripts", "tests")]
    assert all(root.is_dir() for root in roots), "JWT import scan roots must exist"
    main = BACKEND / "main.py"
    assert main.is_file(), "JWT import scan must include the application entry point"
    paths = [main, *(path for root in roots for path in root.rglob("*.py"))]
    imports = []
    for path in sorted(paths):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                modules = [node.module or ""]
            if any(module == "jose" or module.startswith("jose.") for module in modules):
                imports.append(f"{path.relative_to(BACKEND)}:{node.lineno}")
    assert not imports, f"Retired jose imports must use PyJWT: {imports}"

    for filename in ("requirements.in", "requirements.txt"):
        requirements = (BACKEND / filename).read_text(encoding="utf-8").splitlines()
        names = {
            re.sub(r"[-_.]+", "-", match.group(1)).lower()
            for line in requirements
            if (match := re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]*)", line))
        }
        retired = names & RETIRED_DISTRIBUTIONS
        assert not retired, f"Retired JWT dependencies in {filename}: {sorted(retired)}"
