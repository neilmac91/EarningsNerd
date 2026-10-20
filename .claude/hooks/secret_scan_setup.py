"""SessionStart hook: provision the gitleaks binary that secret_scan_guard.py runs before a push (E126).

.claude/settings.json runs this at the start of every session, so the guard never fetches anything at push time. It
reads GITLEAKS_VERSION and GITLEAKS_SHA256 from .github/workflows/ci.yml, the env of the `secret-scan` job and the one
place they are pinned (each must appear there exactly once, or nothing is provisioned). On a linux x64 machine, the one
platform the pin names an archive for, it downloads that release archive from GitHub once, by the job's URL, checks it
against the SHA-256 before it opens it, extracts only the `gitleaks` member into
~/.cache/earningsnerd/gitleaks/<version>-<archive SHA-256>/, and records the binary's own SHA-256 beside it in
`gitleaks.sha256`. A binary already there that matches its record means nothing is downloaded. The download goes
through HTTPS_PROXY when it is set, and TLS trusts the CA bundle SSL_CERT_FILE names.

It never blocks a session: it exits 0 whatever happens. On a failure, another platform included, it prints one line on
stdout, which a SessionStart hook hands to Claude, saying that the guard refuses every push and repository write it
would scan until this succeeds, and how to run it by hand; on success it prints one line on stderr, which a session
does not see. The registered command (`python3 -I -S`) uses the standard library only.
Tests: backend/tests/unit/test_secret_scan_guard.py.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import time
from pathlib import Path

CI = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
SETUP = Path(__file__).resolve()
PIN = {
    "GITLEAKS_VERSION": re.compile(r"^[ \t]+GITLEAKS_VERSION:[ \t]*['\"]?([0-9]+\.[0-9]+\.[0-9]+)['\"]?[ \t]*$", re.MULTILINE),
    "GITLEAKS_SHA256": re.compile(r"^[ \t]+GITLEAKS_SHA256:[ \t]*['\"]?([0-9a-f]{64})['\"]?[ \t]*$", re.MULTILINE),
}
# The archive the `secret-scan` job downloads, by the same URL.
ARCHIVE = "https://github.com/gitleaks/gitleaks/releases/download/v{version}/gitleaks_{version}_linux_x64.tar.gz"
MAX_ARCHIVE_BYTES = 64 << 20
MAX_BINARY_BYTES = 128 << 20
DOWNLOAD_SECONDS = 45  # inside the 60 the registration gives the hook


class SetupError(Exception):
    """Why the binary could not be provisioned."""


def pin(ci: Path = CI) -> tuple[str, str]:
    """GITLEAKS_VERSION and GITLEAKS_SHA256 as ci.yml pins them."""
    try:
        text = ci.read_text(encoding="utf-8")
    except OSError as error:
        raise SetupError(f"cannot read {ci}: {error.strerror or error}") from None
    values = []
    for name, pattern in PIN.items():
        found = pattern.findall(text)
        if len(found) != 1:
            raise SetupError(f"{ci} pins {name} {len(found)} times, not once")
        values.append(found[0])
    return values[0], values[1]


def directory(version: str, sha256: str) -> Path:
    """Where the binary extracted from the archive with this SHA-256 lives."""
    return Path.home() / ".cache" / "earningsnerd" / "gitleaks" / f"{version}-{sha256}"


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def verified(folder: Path) -> Path | None:
    """The binary in `folder` when it matches the SHA-256 recorded beside it, else None."""
    binary = folder / "gitleaks"
    try:
        recorded = (folder / "gitleaks.sha256").read_text(encoding="utf-8").split()
        return binary if recorded and recorded[0] == digest(binary) else None
    except OSError:
        return None


def _download(url: str) -> bytes:
    import urllib.request  # here, not at the top: the guard imports this module before every Bash command

    machine = os.uname().machine.lower()
    if sys.platform != "linux" or machine not in ("x86_64", "amd64"):
        raise SetupError(f"ci.yml pins the linux x64 archive only, and this machine is {sys.platform} {machine}")
    deadline, data = time.monotonic() + DOWNLOAD_SECONDS, bytearray()
    with urllib.request.urlopen(url, timeout=20) as response:
        while block := response.read(1 << 16):
            data += block
            if len(data) > MAX_ARCHIVE_BYTES:
                raise SetupError(f"the archive is larger than {MAX_ARCHIVE_BYTES >> 20} MiB")
            if time.monotonic() > deadline:
                raise SetupError(f"the download took longer than {DOWNLOAD_SECONDS} seconds")
    return bytes(data)


def _write(folder: Path, name: str, data: bytes, mode: int) -> None:
    """Write `folder/name` whole or not at all."""
    import tempfile

    handle = tempfile.NamedTemporaryFile(dir=folder, prefix=f".{name}.", delete=False)
    try:
        with handle:
            handle.write(data)
        os.chmod(handle.name, mode)
        os.replace(handle.name, folder / name)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def provision(version: str, sha256: str, download=_download) -> tuple[Path, bool]:
    """The verified binary, and whether this call downloaded it."""
    import io
    import tarfile

    folder = directory(version, sha256)
    if (binary := verified(folder)) is not None:
        return binary, False
    archive = download(ARCHIVE.format(version=version))
    if hashlib.sha256(archive).hexdigest() != sha256:
        raise SetupError(f"the downloaded archive does not match GITLEAKS_SHA256 in {CI.name}")
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            member = bundle.getmember("gitleaks")
            if not member.isfile() or member.size > MAX_BINARY_BYTES:
                raise SetupError("the archive's gitleaks member is not a regular file of a sane size")
            extracted = bundle.extractfile(member)
            content = extracted.read() if extracted is not None else b""
    except (tarfile.TarError, KeyError) as error:
        raise SetupError(f"cannot extract gitleaks from the archive: {error}") from None
    folder.mkdir(parents=True, exist_ok=True)
    _write(folder, "gitleaks", content, 0o755)
    _write(folder, "gitleaks.sha256", f"{hashlib.sha256(content).hexdigest()}  gitleaks\n".encode(), 0o644)
    if (binary := verified(folder)) is None:
        raise SetupError(f"the binary written to {folder} does not match its record")
    return binary, True


def main() -> int:
    try:
        version, sha256 = pin()
        binary, downloaded = provision(version, sha256)
    except Exception as error:  # a session start is never blocked; the guard fails closed instead
        detail = str(error) or type(error).__name__
        print(
            f"secret_scan_setup: the pinned gitleaks is not provisioned ({detail}). Until it is, "
            ".claude/hooks/secret_scan_guard.py refuses every push and repository write it would scan; "
            f"run it by hand with: python3 {SETUP}"
        )
        return 0
    state = "downloaded and verified" if downloaded else "verified"
    print(f"secret_scan_setup: gitleaks {version} {state} at {binary}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
