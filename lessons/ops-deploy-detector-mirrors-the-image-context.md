# Make the deploy change detector exclude exactly what `.dockerignore` excludes, and gate it with a test

**Date:** 2026-10-06 · **Area:** ops / CI / deploy

## Context

PR #1098's only `backend/` file was `backend/tests/unit/test_capacity_readout.py` (its other changes were
under `ops/` and `tasks/`). `deploy-backend` decided to deploy with
`git diff --name-only HEAD^ HEAD | grep -qE '^backend/'`, so it built and pushed an image whose application
content was unchanged (`backend/.dockerignore` excludes `tests/`), received a new digest because image
builds are not reproducible, and rolled Cloud Run revision 00444 — a production change nobody intended,
noticed only when the merge's deploy job was verified afterwards (CODE RED decision record 09). The deploy
trigger was wider than the image's build inputs. The correction (PR #1101) was authored by the founder's
Astra agent and integrated after an independent review.

## Rule

1. The deploy change detector excludes exactly the paths `backend/.dockerignore` excludes from the image
   (today `backend/tests/`), and runs `git diff --name-only --no-renames` so both sides of a rename are
   listed — a runtime file moved under an excluded path still deploys (the image loses it).
2. Every step after the detector is gated on its output (`if: steps.changes.outputs.backend == 'true'`).
   The gate `backend/tests/unit/test_backend_deploy_scope.py` executes the detector's actual shell on every
   tracked `backend/tests/` path, future nested paths, near-prefix boundaries (`backend/tests_support/`),
   runtime, migration, container and mixed changes, and on a real-git rename; it also asserts the gating,
   that `backend-tests` stays unconditional, and that the step keeps GitHub's default shell (the pipeline's
   exit status relies on `bash -e` without `pipefail`).
3. When `.dockerignore` gains or loses an entry, change the detector, the gate and the three docs
   (`AGENTS.md` §6, `CLAUDE.md` Deploy, `docs/DEPLOYMENT.md`) in the same PR. Say "`backend/` outside
   `backend/tests/`", never "any backend change" or "test-only" (the exclusion is a path prefix, not a
   category: `backend/pytest.ini` and `backend/requirements-dev.txt` are inside the build context and deploy).
4. After a merge whose only `backend/` paths are excluded, the deploy job's steps are expected to skip and its
   log carries no `apply_migrations: applied=` line; a merge that touches deployable backend files is still
   verified by its deploy job's conclusion.

## Evidence

- `.github/workflows/ci.yml` — `deploy-backend` → "Detect backend changes" and the nine gated steps after it.
- `backend/tests/unit/test_backend_deploy_scope.py` — the gate (path cases and the scratch-repo rename case).
- `backend/.dockerignore` — `tests/`.
- PR #1098 (deploy of unchanged application code; Cloud Run revision 00444); PR #1101 (the correction).
