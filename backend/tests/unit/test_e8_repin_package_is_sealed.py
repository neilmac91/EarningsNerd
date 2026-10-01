"""The E8 re-pin package is sealed by bytes, not by prose (CLAUDE.md rule 12).

``tasks/fable-e8-repin-2026-09-22/`` may change only through a founder-approved rebuild
(``build_repin.py``, README "What changed, and only that"). Its own manifests cannot prove that:
``e8_resume.py::verify_addon`` compares each file with ``code-sha256.json`` but never checks the
manifest itself, so an edited file plus a regenerated manifest would pass every runtime check and
the test-homes exemption. This gate pins the manifests' own hashes, so any such edit fails CI
until a rebuild PR updates ``SEALED`` on purpose. It also keeps the values the launch session
must agree on in one place: the regenerated supplement manifest hash that ``e8_resume.py`` pins,
``build-summary.json`` records and the attestation names, and the attestation shape that the
unsealed ``export_e8_state.py`` mirrors. The sealed code is read with ``ast``, never imported.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE = REPO_ROOT / "tasks" / "fable-e8-repin-2026-09-22"
# Change only in a founder-approved rebuild PR, together with build-summary.json.
SEALED = {
    "code-sha256.json": "a20b874561f61d5f0b548cbec0992cde20efdf446245570f514cfe358383a9ce",
    "supplement-sha256.json": "1ef772b3157106bcf9bee52675f89bdf0cf643f0457eb405b6ce28e5fe950f6f",
    "build-summary.json": "4b83cac2280973dc7b1bb2ac99fc094f336aa0222bc16325df8b363a53ed3dc4",
    "repin.diff": "eee95906a0e23b6d1b795600bc5a45fc1a8c97fb6244f62cbaaee38a207a6d19",
}
# Deliberately unsealed operator tools: they are in neither manifest and may be fixed in place.
UNSEALED = {"build_repin.py", "restore_e8_session.py", "export_e8_state.py"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(name: str) -> dict:
    return json.loads((PACKAGE / name).read_text())


def sealed_constants() -> dict:
    """Module-level string/int constants of the sealed tools/e8_resume.py, read without importing it."""
    tree = ast.parse((PACKAGE / "tools" / "e8_resume.py").read_text())
    return {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }


def sealed_attestation_keys() -> set[str]:
    """The key set ``attest()`` requires, read from its ``expected_keys`` literal."""
    tree = ast.parse((PACKAGE / "tools" / "e8_resume.py").read_text())
    attest = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "attest")
    for node in ast.walk(attest):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "expected_keys":
            return {element.value for element in node.value.elts}
    raise AssertionError("attest() no longer declares expected_keys")


def test_manifests_diff_and_build_summary_are_the_reviewed_bytes() -> None:
    changed = {name: _sha(PACKAGE / name) for name, digest in SEALED.items() if _sha(PACKAGE / name) != digest}
    assert changed == {}, f"sealed re-pin files changed outside a founder-approved rebuild: {changed}"


def test_every_manifest_entry_matches_its_file() -> None:
    for manifest in ("code-sha256.json", "supplement-sha256.json"):
        wrong = [rel for rel, digest in _json(manifest).items() if _sha(PACKAGE / rel) != digest]
        assert wrong == [], f"{manifest} entries differ from the files: {wrong}"


def test_build_summary_describes_the_manifests_on_disk() -> None:
    summary = _json("build-summary.json")
    assert summary["repin_code_manifest"] == _json("code-sha256.json")
    assert summary["repin_supplement_tools"] == _json("supplement-sha256.json")
    assert summary["repin_supplement_manifest_sha256"] == _sha(PACKAGE / "supplement-sha256.json")


def test_e8_resume_pins_the_regenerated_supplement_manifest() -> None:
    assert sealed_constants()["E3_SUPPLEMENT_MANIFEST_SHA256"] == _sha(PACKAGE / "supplement-sha256.json")


def test_the_package_holds_exactly_the_sealed_and_operator_files() -> None:
    """An added file would pass every hash check yet run: the sealed tools put tools/ first on sys.path."""
    tracked = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "--", str(PACKAGE.relative_to(REPO_ROOT))],
                             capture_output=True, text=True, check=True).stdout.split()
    expected = set(_json("code-sha256.json")) | set(_json("supplement-sha256.json")) | set(SEALED) | UNSEALED
    assert {str(Path(p).relative_to(PACKAGE.relative_to(REPO_ROOT))) for p in tracked} == expected
    on_disk = {str(p.relative_to(PACKAGE)) for p in PACKAGE.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    assert on_disk == expected, f"files in the package outside the seal: {sorted(on_disk - expected)}"


def test_operator_tools_stay_outside_the_seal() -> None:
    sealed_files = set(_json("code-sha256.json")) | set(_json("supplement-sha256.json"))
    assert not {name for name in sealed_files if Path(name).name in UNSEALED}
    assert all((PACKAGE / name).is_file() for name in UNSEALED)


def test_export_tool_mirrors_the_sealed_attestation_contract() -> None:
    spec = importlib.util.spec_from_file_location("export_e8_state", PACKAGE / "export_e8_state.py")
    export = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export)
    constants = sealed_constants()
    assert export.ATTESTATION_KEYS == sealed_attestation_keys()
    assert export.PRIOR_COUNT == constants["MIN_PRIOR"]
    assert export.CEILING == constants["CEILING"]
    assert set(export.STOP_FILES) == {"STOP.json", constants["STOP"]}
    assert export.SEALED_HASHES == {
        "prior_evidence_sha256": constants["PRIOR_EVIDENCE_SHA256"],
        "founder_statement_sha256": constants["FOUNDER_STATEMENT_SHA256"],
        "original_manifest_sha256": constants["ORIGINAL_MANIFEST_SHA256"],
        "e3_supplement_manifest_sha256": constants["E3_SUPPLEMENT_MANIFEST_SHA256"],
    }
    assert constants["FOUNDER_STATEMENT_SHA256"] == _json("code-sha256.json")["founder-history-attestation.md"]
