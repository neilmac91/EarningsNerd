# WeasyPrint 70 security update — local candidate

Prepared on `codex/wave3-weasyprint70-upgrade` from `5c050cc3d7efabe9360927abf5aecb214f9bc34c`. Feature commit `0313a609ed42c29c52255774a8c72723d8c2628e` changes only the direct and compiled WeasyPrint pins from 69.0 to 70.0. Compiling with isolated pip-tools 7.5.3/pip 25.3 preserved every transitive pin. The shared SDK environment was not modified.

The [official 70.0 release](https://github.com/Kozea/WeasyPrint/releases/tag/v70.0) identifies CVE-2026-55073 as fixed. Authenticated read-only GitHub confirms [Dependabot alert #284](https://github.com/neilmac91/EarningsNerd/security/dependabot/284) is open and lists 70.0 as patched. The upstream advisory page's patched-version field still says none; the release and package alert provide newer remediation evidence. Neither export call passes the vulnerable `stylesheets` or `xmp_metadata` options, so the specific reported bypass is not currently reachable through those inspected call sites. This does not justify dismissing the package alert.

Committed-state full gate at `0313a609ed42c29c52255774a8c72723d8c2628e`, isolated PostgreSQL 15.15 databases with all four CI-named lane variables and performance included, exited 0:

```text
All checks passed!
Bandit: No issues identified. Medium: 0 / High: 0
3129 passed, 29 warnings in 100.10s (0:01:40)
```

Native PDF/export controls separately completed without skips:

```text
28 passed, 2 warnings in 20.35s
```

The pinned dependency audit exited 0, checking 99 dependencies including WeasyPrint 70.0:

```text
No known vulnerabilities found
```

The full log has a post-pytest atexit logging error from `_close_yahoo_client_sync` writing to a closed pytest capture stream. It did not change exit status. The same stack appears in the retained earlier paired-claims gate at `1a7bbc90820238408135561ba3c78fb70faa9b97` after `3116 passed, 29 warnings`; that function is byte-unchanged in this candidate. This is existing teardown noise, not a failed PDF control or an omitted gate.

Rendered existing summary/analysis fixtures using 69.0 and isolated 70.0. Both versions retain the three portrait summary pages and portrait-plus-landscape analysis pages. Three of five rasterized pages are pixel-identical at 900px maximum dimension. The only first-page difference is a small wordmark text-spacing shift within its original area; visual inspection found no clipping or body/table pagination change. This is bounded macOS/native evidence. Linux CI/container rendering and serial deployment remain required before production clearance.

All eleven locked anchors are unchanged because the feature diff consists solely of the two dependency pins. No new application invariant or test was introduced; a synthetic mutation proof is not appropriate for this bounded dependency update. Independent correctness/rules/tests review found no code-scope blocker. No model call or assessment occurred. Existing CI's AI-relevant path filter excludes this requirements-only change; verify the final diff before publication.

Evidence retained in the local task workspace: `outputs/weasyprint70-full-gate.log`, `outputs/weasyprint70-native-tests.log`, `outputs/weasyprint70-audit.json`, `outputs/weasyprint70-layout-review.md`, `outputs/weasyprint70-layout/`, `outputs/weasyprint70-independent-review.md`, and `outputs/weasyprint-advisory-triage.md`. These are local artifacts, not files claimed to be committed in this repository.

No push, PR, merge, alert dismissal, provider call or production action has occurred. Founder approval to merge this specific major upgrade remains required after a reviewable PR exists; root owns publication and serial deployment. Protected alert #270 and frontend dependency PRs #749–#751 are unchanged.
