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
