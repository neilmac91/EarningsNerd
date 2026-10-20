"""SessionStart hook: provision the gitleaks binary that secret_scan_guard.py runs before a push (E126).

.claude/settings.json runs this at the start of every session, so the guard never fetches anything at push time. It
reads GITLEAKS_VERSION and GITLEAKS_SHA256 from .github/workflows/ci.yml, the env of the `secret-scan` job and the one
place they are pinned (each must appear there exactly once, or nothing is provisioned). That SHA-256 is the linux x64
archive's, the one the job runs; CHECKSUMS below pins the same release's darwin arm64, darwin x64 and linux arm64
archives as the release's checksums file lists them, with its linux x64 line too, and test_secret_scan_guard.py fails
when ci.yml's version moves and they do not, or when that line and ci.yml's SHA-256 differ. On a platform PLATFORMS
maps (platform.system() and platform.machine()), it downloads that platform's archive from GitHub once, by the job's
URL, checks it against its SHA-256 before it opens it, extracts only the `gitleaks` member into
~/.cache/earningsnerd/gitleaks/<version>-<archive SHA-256>/, and records the binary's own SHA-256 beside it in
`gitleaks.sha256`. A binary already there that matches its record means nothing is downloaded.
The download goes through HTTPS_PROXY when it is set, and TLS trusts the CA bundle SSL_CERT_FILE names. On any other
platform it provisions nothing, and its line names the platform and how to add a pin.

It never blocks a session: it exits 0 whatever happens. On a failure it prints one line on stdout, which a SessionStart
hook hands to Claude, saying that the guard refuses every push and repository write it would scan until this succeeds,
and how to run it by hand; on success it prints one line on stderr, which a session does not see. The registered
command (`python3 -I -S`) uses the standard library only.
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
# The release's archives, at the URL the `secret-scan` job downloads its own from.
RELEASE = "https://github.com/gitleaks/gitleaks/releases/download/v{version}/{archive}"
ARCHIVE = "gitleaks_{version}_{platform}.tar.gz"
CI_PLATFORM = "linux_x64"  # the archive the job runs, whose SHA-256 ci.yml pins
# platform.system() and platform.machine() to the release's name for the platform; any other provisions nothing.
PLATFORMS = {
    ("Linux", "x86_64"): "linux_x64",
    ("Linux", "aarch64"): "linux_arm64",
    ("Linux", "arm64"): "linux_arm64",
    ("Darwin", "arm64"): "darwin_arm64",
    ("Darwin", "x86_64"): "darwin_x64",
}
# ci.yml's release's archives, as its checksums file (gitleaks_<version>_checksums.txt) lists them. ci.yml's own
# GITLEAKS_SHA256 stays what linux_x64 is checked against; its line here is the gate's tie between this copied block and
# the value CI checks on every run. To add a platform, map it in PLATFORMS and copy its line from that file here; to
# move to another release, move every line with ci.yml.
CHECKSUMS = {
    "gitleaks_8.24.3_darwin_arm64.tar.gz": "b90f13bb8c90ab72083d9b0c842e39dafb82c0e5c3f872f407366b7a58909013",
    "gitleaks_8.24.3_darwin_x64.tar.gz": "41c44ae8ad1d6eef57d4526ad0fd67d8129eee9a856f55c2b3b9395fd3d9ec0f",
    "gitleaks_8.24.3_linux_arm64.tar.gz": "5f2edbe1f49f7b920f9e06e90759947d3c5dfc16f752fb93aaafc17e9d14cf07",
    "gitleaks_8.24.3_linux_x64.tar.gz": "9991e0b2903da4c8f6122b5c3186448b927a5da4deef1fe45271c3793f4ee29c",
}
MAX_ARCHIVE_BYTES = 64 << 20
MAX_BINARY_BYTES = 128 << 20
DOWNLOAD_SECONDS = 45  # inside the 60 the registration gives the hook


class SetupError(Exception):
    """Why the binary could not be provisioned."""


def ci_pin(ci: Path = CI) -> tuple[str, str]:
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


def pin(ci: Path = CI) -> tuple[str, str, str]:
    """ci.yml's gitleaks version, this machine's archive of that release, and the archive's pinned SHA-256."""
    import platform  # here, not at the top: the guard imports this module before every Bash command

    version, ci_sha256 = ci_pin(ci)
    system, machine = platform.system(), platform.machine()
    name = PLATFORMS.get((system, machine))
    if name is None:
        raise SetupError(
            f"no gitleaks archive is pinned for this platform ({system} {machine}); to add one, map it in PLATFORMS and "
            f"copy its line from the release's gitleaks_{version}_checksums.txt into CHECKSUMS, both in {SETUP}")
    archive = ARCHIVE.format(version=version, platform=name)
    sha256 = ci_sha256 if name == CI_PLATFORM else CHECKSUMS.get(archive)
    if sha256 is None:
        raise SetupError(
            f"no SHA-256 is pinned for {archive}, this platform's ({system} {machine}) archive of the version ci.yml "
            f"pins; copy its line from the release's gitleaks_{version}_checksums.txt into CHECKSUMS in {SETUP}")
    return version, archive, sha256


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


def provision(version: str, archive: str, sha256: str, download=_download) -> tuple[Path, bool]:
    """The verified binary, and whether this call downloaded it."""
    import io
    import tarfile

    folder = directory(version, sha256)
    if (binary := verified(folder)) is not None:
        return binary, False
    data = download(RELEASE.format(version=version, archive=archive))
    if hashlib.sha256(data).hexdigest() != sha256:
        raise SetupError(f"the downloaded {archive} does not match its pinned SHA-256")
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as bundle:
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
        version, archive, sha256 = pin()
        binary, downloaded = provision(version, archive, sha256)
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
