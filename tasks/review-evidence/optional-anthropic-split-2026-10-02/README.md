# Optional Anthropic successor to #1050 — 2 October 2026

This change updates only `backend/requirements-eval.txt`: Anthropic **1.8.0 → 1.9.0**.
It separates the optional API-credit judge SDK from aggregate
[Dependabot #1050](https://github.com/neilmac91/EarningsNerd/pull/1050)
(head `938c586110d8eec3f200d3bedb9adefb61560d14`). The weekly readout and runtime image do not
install this file. Its `-c requirements.txt` constraint and docstring-parser 0.18.0 remain intact.
Runtime SDK upgrades have a separate successor; Edgartools 5.59.1 remains held in
[issue #1063](https://github.com/neilmac91/EarningsNerd/issues/1063).

Original base: `5525a91db3de9ce554b6015ed51d6817666c7bc3`; current main
`153cfc4612b790713e1aebbec9174479c373468f` was subsequently merged, followed by
`efdc33f42bbf95a70ceb78d0c6615d59788800df` (#1065), before the final full gate. Dependency source commit:
`73b218e3ef24c2edad834601b7ecc18e0a4bed10`. Evidence-only additions follow that commit.
Application, prompts, model choices, contracts, workflows, budgets and baseline files are unchanged.

## Explicit optional installation and offline compatibility

A separate disposable Python3.11.16 environment resolves runtime + pinned dev + optional eval
requirements. To avoid downloading the same 99-package runtime twice, it began as a copy of the
fresh runtime installation, restored OpenAI3.19.2/PyJWT2.15.0/Sentry2.70.0 from the verified old
wheels, then ran pip install against **all three actual requirements files**. This validates
this branch's independent base; it does not claim that the three new runtime SDKs were present.
[Installed version list](optional-freeze.txt), produced by `pip list --format=freeze --exclude pip --exclude setuptools`, records the complete installed set and
[pip check](optional-pip-check.txt) reports no broken requirements. Runtime pins match this
branch's lock and the optional additions are exactly Anthropic1.9.0 and docstring-parser0.18.0.
[Installed artifacts](installed-artifacts.json) records new resolved artifacts, and
[wheel receipts](wheel-receipts.json) records the old/new Anthropic wheel SHA-256 values and
unchanged Requires-Dist compared against PyPI metadata.

The [offline script](anthropic_shapes.py.txt), adapted from the existing 23 September SDK
receipt, runs real `evals.judge._judge_via_anthropic`, `evals.models._call_anthropic` and
`evals.runner._is_transient` against the installed SDK through `httpx2.MockTransport`.
It verifies the actual system/messages/model/max_tokens request shape, JSON-schema output
configuration, parsed PASS verdict, usage tokens and status/connection/timeout error classes.
Socket connect/create_connection are blocked, and keys are synthetic placeholders.
[Results](anthropic-shapes.txt): `ANTHROPIC_SHAPES_OK 1.9.0 app`.

Source comparison found unchanged standard base-client/streaming paths. `messages.create`
adds an optional omitted `diagnostics` argument; generated beta/type additions are outside
these exercised call shapes. [Primary release](https://github.com/anthropics/anthropic-sdk-python/releases/tag/v1.9.0).
Normal runtime CI alone does not cover this optional install; the explicit check above does.

A third disposable environment combines the new runtime versions (OpenAI3.20.0, PyJWT2.15.1,
Sentry2.71.0) with Anthropic1.9.0 and docstring-parser0.18.0. Its
[pip check](combined-pip-check.txt), [installed versions](combined-freeze.txt), and repeated
[offline application SDK check](combined-offline-sdk.txt) also pass. This is combined package
compatibility evidence; the full source-tree gate below belongs to this branch's stated base.
The [optional package vulnerability audit](pip-audit.txt) reports no known vulnerabilities.

## Verification and release boundary

[Initial full gate](initial-evidence-packaging-failure.txt): 5585 passed, 1 evidence-link failure,
2 deselected, 0 skipped. The guard correctly rejected new, not-yet-tracked receipts.
All evidence files are now tracked. The full gate is rerun after integrating current main;
its completed result follows in the next evidence update. No application assertion failed.

The full gate uses synthetic credentials, fresh bytecode cache and four separate disposable
PostgreSQL15 concurrency-lane databases. No new assertion, contract or gate is introduced;
no redundant version-pin test or mutation proof was added.

Independent exact-head review and hosted required checks remain release requirements. If the
runtime successor lands first, rerun required integration checks after updating this branch's base; the
combined package environment is already checked above. This is offline compatibility evidence, not live Anthropic quality/fidelity acceptance.
No provider call, workflow dispatch or production action occurred in this preparation.
Although this dependency is excluded from the runtime image, this backend-file merge still
triggers deployment and requires the usual serialized migration and health verification.

## Resumed local-runner correction

The [resumed gate on main 153cfc46](resumption-host-library-failure.txt) had **5595 passed,
2 failed, 2 deselected, 0 skipped**: the sanitized runner omitted the existing Homebrew native
library directory, so WeasyPrint could not load libgobject. Restoring
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` fixed [both exact PDF tests](pdf-host-library-restored.txt):
**2 passed**. This probe used the runtime successor after integrating #1065; the same native
libraries serve both isolated environments. No dependency, application or test change was used
to bypass the failure. The complete gates are repeated with the restored path on the new base.
