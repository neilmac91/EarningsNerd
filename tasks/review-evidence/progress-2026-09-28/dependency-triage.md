# Dependency triage: PRs #998, #999, and #1000

Base: current `main` at `67b9be8e9e5b6f9d533d2ed9fbdf20671f795ce7` (#997). The current-main manifests still contain the dependency versions from which all three PRs were raised; #997 has no dependency release overlap.

## Recommended order

1. Observe the #997 deployment, then clear the review gate and take **#998** first. Its functional CI is green and it includes the critical Next.js patch.
2. **#1000** should be split or regenerated without SQLAlchemy 2.1; handle that migration separately.
3. **#999** needs an explicit Sentry 10-to-11 migration and should be rebased or recreated after #998.

## #998 — frontend patch group

Updates: `@tanstack/react-query` 5.103.1→5.103.2; `next` 16.3.5→16.3.6; `posthog-js` 1.434.0→1.434.13; `@types/node` 26.6.1→26.6.2; `eslint-config-next` 16.3.5→16.3.6; `jsdom` 30.1.0→30.1.1.

All functional checks passed: backend, PostgreSQL migrations, frontend, Lighthouse, eval baseline, E2E, and Vercel. Only `review-gate` failed, after timing out for a Codex review summary; this is procedural rather than a dependency failure.

This PR has direct security value. Next 16.3.6 fixes [GHSA-vcvr-r3jv-pc5j / CVE-2026-94545](https://github.com/vercel/next.js/security/advisories/GHSA-vcvr-r3jv-pc5j), a critical CVSS 9.5 RCE affecting Node `next/og` `ImageResponse` in versions 16.2.0 through 16.3.5 when attacker-controlled values reach SVG content, attributes, or styles. Current-default-branch code search found no `ImageResponse`, `next/og`, or `opengraph-image` use, so repository reachability is not evidenced; that does not remove the reason to patch.

Minimal action: after #997 is observed stable, obtain the required review result for head `24e6ec9d75c312c7a5dbb14c3505aa547d2ff8a1`, then merge or rebase if main has moved.

## #999 — Sentry 11 major migration

Update: `@sentry/nextjs` 10.75.0→11.0.0.

Backend, PostgreSQL migration, and eval-baseline checks passed. Frontend, Lighthouse, and E2E fail at build/typecheck because `enableLogs` is no longer a valid init option at `frontend/instrumentation-client.ts:9` and `frontend/instrumentation.ts:11`; Vercel also fails. The review gate separately timed out.

The [Sentry 10-to-11 migration guide](https://github.com/getsentry/sentry-javascript/blob/develop/MIGRATION.md#upgrading-from-10x-to-11x) confirms that `enableLogs` was removed: the existing `consoleLoggingIntegration()` opts into logs without that field. The runtime floors are already met (Node 22.23.2, TypeScript 6.0.3, Next 16.3.5, React 18.2.0). The migration also changes data collection to more permissive defaults, so this requires an explicit `dataCollection` and scrubbing review; it is not presented as a security-advisory update.

Minimal action: hold the PR, land #998, then rebase/recreate #999. Remove both `enableLogs` fields, decide the intended `dataCollection` baseline, and rerun build/typecheck plus frontend, Lighthouse, E2E, and Vercel checks.

## #1000 — backend group with SQLAlchemy migration boundary

Updates: `ruff` 0.16.8→0.16.9; `anthropic` 1.7.0→1.8.0; `json-repair` 0.63.4→0.63.5; `openai` 3.16.2→3.19.2; `posthog` 7.58.0→7.60.0; `PyJWT` 2.14.0→2.15.0; `sentry-sdk` 2.69.2→2.70.0; `SQLAlchemy` 2.0.54→2.1.0; `uvicorn` 0.53.0→0.54.0.

Backend, frontend, Lighthouse, eval baseline, E2E, and Vercel passed. `migrations-postgres` failed with `ModuleNotFoundError: No module named 'psycopg'`. This directly follows [SQLAlchemy 2.1’s PostgreSQL driver change](https://docs.sqlalchemy.org/en/21/changelog/migration_21.html#default-postgresql-driver-changed-to-psycopg-psycopg-3): a bare `postgresql://` URL now selects psycopg 3. The repository and CI use bare URLs but install `psycopg2-binary==2.9.13`. Python 3.11 satisfies SQLAlchemy 2.1’s new floor.

`copilot-eval` also failed, but its log showed an empty `OPENAI_API_KEY`, `accepted=false`, and no summary. That run is non-diagnostic for the OpenAI SDK update. The review gate separately timed out. No specific security advisory was identified in the PR material.

Minimal action: split or regenerate the group with SQLAlchemy constrained below 2.1 so the other eight updates can be assessed separately. Put SQLAlchemy 2.1 in a dedicated migration PR and choose either explicit `postgresql+psycopg2://` URLs or a tested psycopg 3 installation/migration. Resolve the credential-gated Copilot check independently.

## Overlap

#998 and #999 both modify `frontend/package.json` and `frontend/package-lock.json`, although their direct packages differ. Landing #998 first avoids delaying the security patch; #999 then needs a rebase or recreation. #1000 changes only backend requirements and has no file or direct-package overlap with either frontend PR.

This was a read-only triage. No dependencies were installed, and no repository, PR, workflow, or GitHub state was changed.
