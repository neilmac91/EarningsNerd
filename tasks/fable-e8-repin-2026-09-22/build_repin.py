"""Build the E8 re-pin package from the sealed E3 supplement and E8 add-on, changing one literal.

The founder chose to continue E8 on the Claude CLI now installed in the judging containers
(2.1.280) after the pinned 2.1.278 build disappeared with a container image change. The sealed
packages cannot be edited (their hashes are pinned by ``immutable-sha256.json``,
``supplement-sha256.json`` and ``code-sha256.json``), so this script derives a new sibling package:

  tools/binding.py, tools/readout.py       byte-identical copies of the E3 supplement's
  tools/guard_setup.py                     supplement copy with the version literal 2.1.278 -> 2.1.280
  tools/resume.py                          supplement copy with the version literal 2.1.278 -> 2.1.280
  supplement-sha256.json                   regenerated for the four tools above
  tools/e8_resume.py                       add-on copy with E3_SUPPLEMENT_MANIFEST_SHA256 pointing at
                                           the regenerated supplement manifest
  founder-history-attestation.md           byte-identical (its hash is pinned inside e8_resume.py)
  tests/test_e8_addon.py                   byte-identical
  README.md, verification.md               written by hand for this package
  code-sha256.json                         regenerated for the five add-on files
  repin.diff                               the exact unified diff against the sealed sources

Every substitution is asserted to match exactly once, so an unexpected source edit fails the
build rather than silently producing a different package. Run from the repository root:

  python3 tasks/fable-e8-repin-2026-09-22/build_repin.py \
      --supplement /home/user/fable-judging/fable-reconciliation-2026-09-22 \
      --addon /home/user/fable-judging/fable-e8-continuation-2026-09-22 \
      --out tasks/fable-e8-repin-2026-09-22
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import shutil
from pathlib import Path

OLD_VERSION = '2.1.278'
NEW_VERSION = '2.1.280'
SUPPLEMENT_MANIFEST_SHA256 = '8e43ac912126d5253f5a46b4e5cc88ffbaa5b4ab4e5d49bb37f3189d1b0c568c'
SUPPLEMENT_TOOL_HASHES = {
    'tools/binding.py': 'f4f1d409af97a747f5785a33e582396d1edb0dfe6de933e31e9079bc9e7706bc',
    'tools/guard_setup.py': '45f2b402720df8481ad404a8b63162e2cdb042f8e0ba3cae55a58a4eff4edd8c',
    'tools/readout.py': 'ccb07da61854769fd0489c684714a1f297a2d8de6a4a4a5e26ae777e9b353e37',
    'tools/resume.py': '9b8d9f3f76a68b7ad63b7bb1c652361388b641b8918fb6ea3391c688f9bdf54b',
}
ADDON_HASHES = {
    'tools/e8_resume.py': 'a2399735f16890ef582620bcbfd876da903724b7c12ff5597a5b9adacd4813c7',
    'founder-history-attestation.md': '67527fd115135ae78c7e339423f7c798d53e78bb878d820ac77262e45d36ec8c',
    'tests/test_e8_addon.py': 'd79de7571e66257a5d60b318f409af6ddfd93cc5ef4abbd82b1cf9cc3f7c7456',
}
# (file, exact old text, exact new text); each must occur exactly once in the sealed source.
SUBSTITUTIONS = [
    ('tools/guard_setup.py',
     "re.fullmatch(r'2\\.1\\.278(?: \\(Claude Code\\))?\\s*', proc.stdout)",
     "re.fullmatch(r'2\\.1\\.280(?: \\(Claude Code\\))?\\s*', proc.stdout)"),
    ('tools/guard_setup.py',
     "raise GuardError('Real CLI must report exactly 2.1.278 (Claude Code)')",
     "raise GuardError('Real CLI must report exactly 2.1.280 (Claude Code)')"),
    ('tools/resume.py',
     "re.match(r'^2\\.1\\.278(?:\\s|$)', result.stdout.strip())",
     "re.match(r'^2\\.1\\.280(?:\\s|$)', result.stdout.strip())"),
    ('tools/resume.py',
     "raise ValueError('Existing Claude CLI 2.1.278 required; no replacement or model probe performed')",
     "raise ValueError('Existing Claude CLI 2.1.280 required; no replacement or model probe performed')"),
]
HAND_WRITTEN = ('README.md', 'verification.md')


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def substitute(text: str, old: str, new: str, name: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f'REFUSE: expected exactly one occurrence in {name}: {old!r}')
    return text.replace(old, new)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--supplement', required=True, type=Path)
    parser.add_argument('--addon', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    supplement = args.supplement.resolve(strict=True)
    addon = args.addon.resolve(strict=True)
    out = args.out.resolve()
    if sha(supplement / 'supplement-sha256.json') != SUPPLEMENT_MANIFEST_SHA256:
        raise SystemExit('REFUSE: sealed supplement manifest hash differs')
    for rel, expected in {**SUPPLEMENT_TOOL_HASHES}.items():
        if sha(supplement / rel) != expected:
            raise SystemExit(f'REFUSE: sealed supplement file differs: {rel}')
    for rel, expected in ADDON_HASHES.items():
        if sha(addon / rel) != expected:
            raise SystemExit(f'REFUSE: sealed add-on file differs: {rel}')
    for name in HAND_WRITTEN:
        if not (out / name).exists():
            raise SystemExit(f'REFUSE: write {name} in {out} before building')
    (out / 'tools').mkdir(parents=True, exist_ok=True)
    (out / 'tests').mkdir(parents=True, exist_ok=True)
    diff_chunks: list[str] = []

    # Supplement tools: two byte-identical, two with the single literal changed.
    supplement_manifest: dict[str, str] = {}
    for rel in SUPPLEMENT_TOOL_HASHES:
        source = (supplement / rel).read_text()
        text = source
        for file, old, new in SUBSTITUTIONS:
            if file == rel:
                text = substitute(text, old, new, rel)
        (out / rel).write_text(text)
        supplement_manifest[rel] = sha_bytes(text.encode())
        if text != source:
            diff_chunks.extend(difflib.unified_diff(source.splitlines(keepends=True), text.splitlines(keepends=True),
                                                    fromfile=f'sealed/{rel}', tofile=f'repin/{rel}'))
    manifest_bytes = (json.dumps(supplement_manifest, indent=2) + '\n').encode()
    (out / 'supplement-sha256.json').write_bytes(manifest_bytes)
    new_manifest_sha = sha_bytes(manifest_bytes)

    # Add-on: adapter with the manifest constant re-pointed; attestation and tests byte-identical.
    source = (addon / 'tools/e8_resume.py').read_text()
    text = substitute(source, f"E3_SUPPLEMENT_MANIFEST_SHA256 = '{SUPPLEMENT_MANIFEST_SHA256}'",
                      f"E3_SUPPLEMENT_MANIFEST_SHA256 = '{new_manifest_sha}'", 'tools/e8_resume.py')
    (out / 'tools/e8_resume.py').write_text(text)
    diff_chunks.extend(difflib.unified_diff(source.splitlines(keepends=True), text.splitlines(keepends=True),
                                            fromfile='sealed/tools/e8_resume.py', tofile='repin/tools/e8_resume.py'))
    for rel in ('founder-history-attestation.md', 'tests/test_e8_addon.py'):
        shutil.copyfile(addon / rel, out / rel)
    code_manifest = {rel: sha(out / rel) for rel in
                     ('README.md', 'founder-history-attestation.md', 'tests/test_e8_addon.py', 'tools/e8_resume.py', 'verification.md')}
    (out / 'code-sha256.json').write_text(json.dumps(code_manifest, indent=2, sort_keys=True) + '\n')
    (out / 'repin.diff').write_text(''.join(diff_chunks))
    summary = {
        'old_version': OLD_VERSION, 'new_version': NEW_VERSION,
        'sealed_supplement_manifest_sha256': SUPPLEMENT_MANIFEST_SHA256,
        'repin_supplement_manifest_sha256': new_manifest_sha,
        'repin_supplement_tools': supplement_manifest,
        'repin_code_manifest': code_manifest,
        'byte_identical': ['tools/binding.py', 'tools/readout.py', 'founder-history-attestation.md', 'tests/test_e8_addon.py'],
        'changed': ['tools/guard_setup.py', 'tools/resume.py', 'tools/e8_resume.py'],
    }
    (out / 'build-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
