"""Keep retired JWT libraries out; ASN.1 is allowed only through Google ADC (W3-6)."""
import ast
from pathlib import Path
import re

BACKEND = Path(__file__).resolve().parents[2]
RETIRED_DISTRIBUTIONS = {"python-jose", "ecdsa", "rsa", "pyasn1", "pyasn1-modules"}


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
            if any(module.split(".")[0] in {"jose", "ecdsa", "rsa", "pyasn1", "pyasn1_modules"}
                   for module in modules):
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
        if filename == "requirements.txt" and "pyasn1" in retired:
            # google-auth uses ASN.1 to read certificates for Application Default Credentials.
            # Keep it transitive-only: no direct requirement/import or retired JWT implementation.
            lock = "\n".join(requirements)
            assert re.search(r"(?m)^pyasn1==[^\n]+\n    # via pyasn1-modules$", lock)
            assert re.search(r"(?m)^pyasn1-modules==[^\n]+\n    # via google-auth$", lock)
            assert "google-cloud-storage" in names and "google-auth" in names
            retired.difference_update({"pyasn1", "pyasn1-modules"})
        assert not retired, f"Retired JWT dependencies in {filename}: {sorted(retired)}"
