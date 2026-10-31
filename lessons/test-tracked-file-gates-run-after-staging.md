# Run a `git ls-files` gate after staging its own module, and select targets by name pattern

**Date:** 2026-10-02  
**Area:** Testing & verification / rule-12 gates

**Context:** The example-env placeholder gate selected tracked files whose basename contained
both "env" and "example". Run locally before `git add`, the new module was untracked, so
`git ls-files` never returned it and the gate passed. Committed, the module matched its own
selector and CI failed on the test's string constants (the sole red job on the push).

**Rule:** A gate that enumerates repository files through `git ls-files` runs only after
every file it adds is staged, because an untracked module is invisible to the selector.
Select targets with a name pattern that describes the real artefacts (`^\.env(\..+)*\.example$`),
never with substrings that a test module's own name can satisfy, and keep one test that
asserts the gate's module is not among its own targets.

**Evidence:** [`test_example_env_files_are_placeholders.py`](../backend/tests/unit/test_example_env_files_are_placeholders.py)
(`_is_example_env_name`, `test_selector_picks_dotenv_example_files_only`); corrective
commit `6ac68991` on PR #1069, whose mutation proof restores the substring match and
reproduces the CI failure.

Recurred 2026-10-24 on `claude/trend-analysis-depth-eval`. A full backend run with the new
`backend/evals/trend_depth/` package untracked passed. Once the package was committed,
`test_copilot_eval_paths.py::test_every_file_under_backend_is_classified` failed: it reads
`git ls-files` and needs every new subdirectory of `evals/` classified. The branch had been pushed
between the two runs. Run the full suite once more after the first commit of a new package, before
its push.
