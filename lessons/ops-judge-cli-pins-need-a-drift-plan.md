# Pin the judge CLI by version, but decide in advance what happens when the image drifts

**Date:** 2026-09-22 · **Area:** ops / evals

## Context

The Fable E8 variability panel sealed its tooling around the exact Claude CLI build `2.1.278`
(regex fullmatch in `guard_setup.py::_real_cli` and `resume.py::verified_cli`, both hash-pinned).
The Claude Code web container image was replaced between the 22 September E3 session and the
next session; the same path now reports `2.1.280` and no `2.1.278` binary exists anywhere in the
container. Every dispatch path fail-closed, correctly, and the run could not start. The handoff
rules forbade installing a replacement, so the only ways forward were a new reviewed package
re-pinned to the current build (with a documented version confound) or closing the panel.

## Rule

When an evaluation pins an external executable by exact version, the same package must state,
before the first run, which of these applies if that exact build is no longer available:
(a) the study closes with real denominators, or (b) a new reviewed sibling package re-pins to the
current build and every readout carries the version confound. Never edit the sealed pin in place,
never wrap or spoof the version string, and never let a session discover the choice mid-restore.
Record the observed CLI version in every per-slot execution record so a confound is visible in
the data, not only in prose.

## Evidence

- `tasks/fable-e8-repin-2026-09-22/README.md` (the re-pin package and its confound statement)
- `tasks/handover-astra-2026-09-22-e8-repin.md` (restore receipt summary, option table)
- `backend/evals/judge.py` resolves bare `claude` from PATH and does no version check; the pin
  lives only in the judging tools.
