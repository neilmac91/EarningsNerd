"""Every vendored font is the file its provenance record names (backend/app/assets/fonts/SOURCES.txt).

SOURCES.txt says where each font in the directory comes from and how the symbols face was cut, with each file's
sha256 on a line "sha256 <hex>  <file name>". A font replaced without its record (a re-cut that forgot the line,
a file swapped for another build) would leave the record describing bytes the PDFs no longer embed. So every
font file in the directory has exactly one hash line, and its hash is the file's; a line naming a file the
directory lacks is only the cut's source, which is not vendored (NOT_VENDORED).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

FONTS = Path(__file__).resolve().parents[2] / "app" / "assets" / "fonts"
HASH_LINE = re.compile(r"^\s*sha256 ([0-9a-f]{64})  (\S+)", re.MULTILINE)
FONT_SUFFIXES = (".woff2", ".woff", ".ttf", ".otf")
NOT_VENDORED = frozenset({"Inter[opsz,wght].ttf"})  # the symbols face's source, pinned by URL and blob


def recorded_hashes(record: str) -> dict[str, list[str]]:
    """Each file name the record gives a hash line, with every hash it gives that name."""
    found: dict[str, list[str]] = {}
    for digest, name in HASH_LINE.findall(record):
        found.setdefault(name, []).append(digest)
    return found


def hash_problems(record: str, directory: Path) -> list[str]:
    fonts = sorted(path.name for path in directory.iterdir() if path.suffix in FONT_SUFFIXES)
    recorded = recorded_hashes(record)
    found = [f"{name} has no hash line" for name in fonts if name not in recorded]
    found += [f"{name} has {len(digests)} hash lines" for name, digests in recorded.items() if len(digests) > 1]
    found += [f"{name} is recorded but not in the directory" for name in recorded
              if name not in fonts and name not in NOT_VENDORED]
    for name in fonts:
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if name in recorded and recorded[name][0] != actual:
            found.append(f"{name} is {actual}, not the recorded {recorded[name][0]}")
    return found


def test_every_vendored_font_is_the_file_its_record_names():
    record = (FONTS / "SOURCES.txt").read_text(encoding="utf-8")
    assert hash_problems(record, FONTS) == []
    # The reader found a line for each of the four faces the PDFs declare.
    assert {"Inter-Variable-latin.woff2", "Inter-Variable-Italic-latin.woff2", "Inter-Variable-symbols.woff2",
            "GeistMono-latin.woff2"} <= set(recorded_hashes(record))


def test_the_reader_flags_each_way_a_record_drifts(tmp_path):
    """Planted: a wrong hash, a font with no line, a font with two and a line for a file that is gone."""
    (tmp_path / "A.woff2").write_bytes(b"a")
    (tmp_path / "B.woff2").write_bytes(b"b")
    (tmp_path / "C.woff2").write_bytes(b"c")
    a, c = hashlib.sha256(b"a").hexdigest(), hashlib.sha256(b"c").hexdigest()
    record = (f"  sha256 {'0' * 64}  A.woff2\n  sha256 {c}  C.woff2\n  sha256 {c}  C.woff2\n"
              f"  sha256 {a}  Gone.woff2\n  sha256 {a}  Inter[opsz,wght].ttf (the source, not vendored)\n")
    assert hash_problems(record, tmp_path) == [
        "B.woff2 has no hash line",
        "C.woff2 has 2 hash lines",
        "Gone.woff2 is recorded but not in the directory",
        f"A.woff2 is {a}, not the recorded {'0' * 64}",
    ]
    record = f"  sha256 {a}  A.woff2\n  sha256 {hashlib.sha256(b'b').hexdigest()}  B.woff2\n  sha256 {c}  C.woff2\n"
    assert hash_problems(record, tmp_path) == []
