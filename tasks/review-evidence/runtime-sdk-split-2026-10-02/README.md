# Runtime SDK successor to #1050 — 2 October 2026

This change separates OpenAI 3.19.2 → 3.20.0, PyJWT 2.15.0 → 2.15.1 and Sentry
2.70.0 → 2.71.0 from the aggregate [Dependabot #1050](https://github.com/neilmac91/EarningsNerd/pull/1050)
(head `938c586110d8eec3f200d3bedb9adefb61560d14`). Edgartools remains **5.58.0**;
[issue #1063](https://github.com/neilmac91/EarningsNerd/issues/1063) carries the blocked 5.59.1
update and its missing filing characters. Anthropic is handled separately.

Original base: `5525a91db3de9ce554b6015ed51d6817666c7bc3`; current main
`153cfc4612b790713e1aebbec9174479c373468f` was subsequently merged, followed by
`efdc33f42bbf95a70ceb78d0c6615d59788800df` (#1065), before the final full gate. Dependency source commit:
`92aab7ae2109f2f31669fdc7c68e577842e8b58e`. Evidence-only additions follow that commit.
No application, workflow, contract test, prompt, model, baseline or production flag changed.

## Lock and environment provenance

Python 3.11.16, pip-tools 7.6.1 and pip 26.2.1 in a disposable compiler environment.
The existing lock was the resolver seed; the only selected upgrades were
`--upgrade-package openai==3.20.0 --upgrade-package PyJWT==2.15.1 --upgrade-package sentry-sdk==2.71.0`.
The index was explicitly `https://pypi.org/simple`. The compile command was
`pip-compile --output-file=requirements.txt --strip-extras --no-emit-index-url --no-emit-trusted-host requirements.in`
with the selections above, and `CUSTOM_COMPILE_COMMAND` preserved the existing portable header.
A second compile without upgrade selections reproduced the lock byte for byte.
[Lock changes](lock-changes.json) contains exactly the three intended version changes.
The only other lock diff is the generated greenlet provenance comment: macOS arm64 omits
SQLAlchemy's platform-marker edge, while the explicit `greenlet==3.5.6` input preserves the
Linux/CI package pin. No hand-edited compiled lock or unrelated package update was used.

A fresh runtime-only environment installed the exact 99 resolved pins.
[Runtime freeze](runtime-freeze.txt) matches the lock exactly; Anthropic is absent.
[Installed artifacts](installed-artifacts.json) records public source URLs and archive hashes.
[Runtime pip check](runtime-pip-check.txt) and the
[runtime + pinned dev-tool check](runtime-dev-pip-check.txt) report no broken requirements.
[Gate environment](runtime-dev-freeze.txt) records the complete runtime/dev set.
[Wheel receipts](wheel-receipts.json) retain the exact old/new public wheel SHA-256 values
checked against PyPI's version metadata; all three Requires-Dist sets were unchanged.
The manifest is archive provenance, not a claim of publisher attestation.

## Compatibility assessment

- OpenAI's application-used chat-completion files are unchanged. `_base_client.py` preserves
  query strings when appending a base-URL slash; `_httpx2.py` adds SSL/end-of-stream faults to
  request exception classification. The configured default base is `https://api.deepseek.com/v1`.
  Primary and fallback application clients still explicitly use `max_retries=0`.
  Existing real-SDK mock-transport tests (`test_provider_resilience.py`,
  `test_attribution_verify.py`, `test_recovery_context.py`, `test_eval_measurement.py`) remain
  unchanged and are included in the full gate. New Responses/WebSocket features are unused.
- PyJWT changes valid trailing Base64URL padding handling. The
  [old/new synthetic HMAC controls](pyjwt-offline-controls.json) accept valid signatures and
  reject junk, wrong signatures, embedded padding and excessive padding; only the new version
  accepts the correctly signed padded payload. The unchanged full suite includes locked auth
  flow and OAuth token validation coverage.
- Sentry's FastAPI and SQLAlchemy integration modules are unchanged; app configuration uses fixed
  sampling and no custom sampler/before-send callback. The new version changes callback-error
  accounting and adds an unused TypeSafe integration. The
  [offline smoke](sentry-shapes.txt), driven by [this script](sentry_shapes.py.txt), initializes
  the application's FastAPI/SQLAlchemy integrations, confirms `send_default_pii=False`, and
  captures a synthetic exception through a recorder transport. Real socket access raises.

Primary release sources: [OpenAI 3.20.0](https://github.com/openai/openai-python/releases/tag/v3.20.0),
[PyJWT 2.15.1](https://github.com/jpadilla/pyjwt/blob/2.15.1/CHANGELOG.rst),
[Sentry 2.71.0](https://github.com/getsentry/sentry-python/releases/tag/2.71.0).

## Verification

[Initial full gate](initial-evidence-packaging-failure.txt): 5585 passed, 1 evidence-link failure,
2 deselected, 0 skipped.
The guard correctly rejected new, not-yet-tracked evidence files; no application assertion failed.
After committing those files and integrating main, the [final full gate](final-full-gate.txt) on
`f009a602d28487fe2f9234e9fc17294cf5da5e1e` passed: **ruff clean; bandit no medium/high issues; 5604 passed, 2 deselected, 0 skipped**.
[Machine-readable status](final-full-gate-status.json) records all three successful commands.
[Independent environment check](final-environment-review.json) confirms the runtime lock,
independent optional base, combined package set and retained Edgartools 5.58.0.
Only these verification receipts and this documentation were added after the tested commit;
the evidence-link gate is checked again on the committed receipt update.

[Migration proof](migrations-triple-pass.txt) reproduces CI's disposable PostgreSQL15 database:
40 files apply, all 40 skip on pass two, then all 40 safely reapply after resetting the ledger.
The decoy `schema_migrations` table is included. PostgreSQL databases and bytecode caches are
isolated by lane/worktree. Credentials are synthetic and no inherited service credentials
are passed to the gate. [Dependency audit](pip-audit.txt) reports no known vulnerabilities.
No new gate or contract was introduced, so no test or mutation proof was added.

## Review and release boundary

Manual source review found no concrete compatibility blocker in these three upgrades.
The separate Edgartools hold survives both refutations: its fixture directly invokes the parser
before app extraction, and a prior same-source version swap reproduces the loss with only
Edgartools changed. A spacing-only assertion change cannot restore missing `%)` characters.
[Hold and receipts](edgartools-hold.md) preserves that disposition.

Independent review of the final successor head and hosted required checks remain release
requirements. This evidence is offline compatibility, not live model quality or paid fidelity.
No provider call, workflow dispatch, production operation or production flag change occurred
while preparing this local successor. Every backend merge still requires the next deployment's
migration receipt and health verification before another backend merge.

## Resumed local-runner correction

The [resumed gate on main 153cfc46](resumption-host-library-failure.txt) had **5595 passed,
2 failed, 2 deselected, 0 skipped**: the sanitized runner omitted the existing Homebrew native
library directory, so WeasyPrint could not load libgobject. Restoring
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` fixed [both exact PDF tests](pdf-host-library-restored.txt):
**2 passed**. This probe used the runtime successor after integrating #1065; the same native
libraries serve both isolated environments. No dependency, application or test change was used
to bypass the failure. The complete gates passed with the restored path on the new base; see the final receipt above.
