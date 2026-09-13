# An npm override's meaning is set by the package it constrains — re-check every override on a major bump

Date: 2026-09-13   Area: frontend

**Context**: PR #852 took three frontend test-stack majors at once (vitest 5, jsdom 30,
jest-dom 7). The repo carried an override pinning `undici` under `jsdom`:

```json
"overrides": { "jsdom": { "undici": "^7.28.0" } }
```

jsdom 29 declared `undici ^7.25.0`, so that line raised a floor — it pulled undici forward
past what jsdom asked for, which is what an override is normally for. jsdom 30 declares
`undici ^8.9.0`. The override line did not change, was not part of the diff, and was not
mentioned in any Dependabot PR — and it silently inverted into a ceiling, holding undici at
7.29.1, a full major below what the newly installed jsdom actually wanted.

Nothing failed. The install succeeded, the whole suite passed, and the build was clean,
because nothing in these tests exercises the paths where jsdom reaches for undici. It would
have merged invisibly. Codex caught it in review.

The fix was to delete the override, not bump it: the reason it existed (raising a floor
under jsdom 29) no longer applied at all under jsdom 30. undici now resolves to 8.10.2.

**Rule**: An override constrains a package this repo does not depend on directly, so its
meaning is set by the packages that DO depend on it — and those move without the override
line changing. On any major bump, list every override target that the bumped package
depends on, transitively, and re-derive whether the override still does what it was written
to do. When the reason is gone, delete the override; do not bump it to whatever makes the
install quiet.

The machine-checkable half is directional, and the direction is the whole point:

- Pushing a package **forward**, past a floor a dependent declares, is the deliberate case.
  This repo has six of them — the `@lhci/cli` security bumps, and `postcss`, which `next`
  pins to an exact older patch. A gate that flagged every unsatisfied range would flag all
  six and be worthless.
- Holding a package **back**, below a dependent's declared floor, is never intentional.
  That is this bug, and it is the only case worth failing on.

`frontend/tests/unit/overrideDirectionGate.spec.ts` walks the committed lockfile with real
node resolution (walking up the nesting chain, so a nested copy is judged against its own
dependent rather than the hoisted one) and fails on any backward override. It carries a
control assertion that at least one forward override is still found, because otherwise an
emptied overrides block or a rename would make the whole scan pass vacuously.

**Evidence**: `frontend/tests/unit/overrideDirectionGate.spec.ts`;
`frontend/package.json` overrides block; PR #852, and the review comment recorded on #751.
Measured on the committed tree: 7 declared-range violations, 6 forward and deliberate, 0
backward. The historical state (`jsdom@30.0.1` declaring `undici ^8.9.0`, resolved 7.29.1)
is pinned as a fixture in that spec so the detector is proven to fire.
