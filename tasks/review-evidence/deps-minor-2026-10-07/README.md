# Dependabot #1096 successor without Edgartools — 7 October 2026

This change takes six of the seven updates in
[Dependabot #1096](https://github.com/neilmac91/EarningsNerd/pull/1096)
(head `a31f9094d17c98dcd37522794420e96f83071c06`) and leaves Edgartools on **5.58.0**. It follows
the [#1066 runtime split](../runtime-sdk-split-2026-10-02/README.md) and the
[#1067 optional Anthropic split](../optional-anthropic-split-2026-10-02/README.md).

Base: main `335ad94ba05d514074017a4676af8a7816dab416`. Requirements commit `798a462a`, Dependabot
policy commit `6ae59ea6`, then this evidence. No application code, test, prompt, model, flag,
workflow, migration or baseline changed.

| Package | From | To | File |
| --- | --- | --- | --- |
| fastapi | 0.141.1 | 0.142.2 | `requirements.in` + lock |
| openai | 3.20.0 | 3.23.0 | `requirements.in` + lock |
| posthog | 7.60.1 | 7.62.0 | `requirements.in` + lock |
| python-dotenv | 1.2.3 | 1.2.4 | `requirements.in` + lock |
| opentelemetry-api | — | 1.45.0 (new, `via fastapi`) | lock |
| ruff | 0.16.9 | 0.16.10 | `requirements-dev.txt` |
| anthropic | 1.9.0 | 1.11.0 | `requirements-eval.txt` (optional judge SDK) |
| edgartools | 5.58.0 | **5.58.0 (held)** | unchanged |

## Lock provenance

Python 3.11.17 (Linux x86_64), pip 26.2.1 and pip-tools 7.6.1 in a disposable compiler
environment. Index `https://pypi.org/simple`. The existing lock was the resolver seed.
The command, run from `backend/`, was:

```
CUSTOM_COMPILE_COMMAND="pip-compile --output-file=requirements.txt --strip-extras requirements.in" \
pip-compile --index-url https://pypi.org/simple \
  --output-file=requirements.txt --strip-extras --no-emit-index-url --no-emit-trusted-host \
  --upgrade-package fastapi==0.142.2 --upgrade-package openai==3.23.0 \
  --upgrade-package posthog==7.62.0 --upgrade-package python-dotenv==1.2.4 \
  --upgrade-package opentelemetry-api==1.45.0 requirements.in
```

The `opentelemetry-api` selection is the one deliberate addition. FastAPI 0.142 now requires
`opentelemetry-api>=1.44.0`. #1096 resolved it to 1.45.0 on 5 October. 1.45.1 was published on
6 October, so an unselected compile today picks 1.45.1. Selecting 1.45.0 keeps the version that
#1096's CI actually ran. The greenlet comment change is generated: on Linux, SQLAlchemy's
platform marker includes greenlet, which restores the `sqlalchemy` edge that #1066's macOS arm64
compile had dropped. #1096's lock has the same comment.

The exact lock diff:

```diff
@@ -55,7 +55,7 @@ email-validator==2.3.0
     # via -r requirements.in
 et-xmlfile==2.0.0
     # via openpyxl
-fastapi==0.141.1
+fastapi==0.142.2
     # via
     #   -r requirements.in
     #   sentry-sdk
@@ -64,7 +64,9 @@ filelock==3.29.4
 fonttools==4.63.0
     # via weasyprint
 greenlet==3.5.6
-    # via -r requirements.in
+    # via
+    #   -r requirements.in
+    #   sqlalchemy
 h11==0.16.0
     # via
     #   httpcore
@@ -120,10 +122,12 @@ numpy==2.4.6
     # via
     #   pandas
     #   rank-bm25
-openai==3.20.0
+openai==3.23.0
     # via -r requirements.in
 openpyxl==3.1.5
     # via -r requirements.in
+opentelemetry-api==1.45.0
+    # via fastapi
 orjson==3.11.9
     # via edgartools
 packaging==26.2
@@ -138,7 +142,7 @@ pillow==12.3.0
     # via weasyprint
 pluggy==1.6.0
     # via pytest
-posthog==7.60.1
+posthog==7.62.0
     # via -r requirements.in
 psycopg2-binary==2.9.13
     # via -r requirements.in
@@ -183,7 +187,7 @@ python-dateutil==2.9.0.post0
     # via
     #   -r requirements.in
     #   pandas
-python-dotenv==1.2.3
+python-dotenv==1.2.4
     # via
     #   -r requirements.in
     #   pydantic-settings
@@ -246,6 +250,7 @@ typing-extensions==4.15.0
     #   fastapi
     #   httpx2
     #   openai
+    #   opentelemetry-api
     #   posthog
     #   pydantic
     #   pydantic-core
```

**Comparison with #1096.** All 100 lock pins equal #1096's lock except `edgartools==5.58.0`.
Full-file diffs against `a31f9094` show one differing line in `requirements.in`
(`edgartools>=5.58.0`) and one in the lock (`edgartools==5.58.0`). The dev and eval files are
byte-identical to #1096's.

**Reproducibility.** A second compile without upgrade selections reproduced the lock byte for
byte. Both outputs have SHA-256 `4c17b3356bb725e5ee5e3142952b489670b7599d961c60c099521ddbd5ad2c95`.
No lock bytes were hand-edited.

## Why Edgartools is excluded

[Decision D](../../pr-disposition-2026-09-30.md) and
[issue #1063](https://github.com/neilmac91/EarningsNerd/issues/1063) hold Edgartools at 5.58.0
because 5.59.1 has two real Ford regressions: a missing break before tables, and lost `%)`
characters in the ROIC row. #1096's backend-tests job
([111664425766](https://github.com/neilmac91/EarningsNerd/actions/runs/37279635850/job/111664425766)) failed
on 5.59.1 with
`tests/unit/test_outlook_source_coverage.py::test_original_ford_complete_outlook_reaches_primary_and_forward_recovery_without_displacement`
(`1 failed, 5710 passed, 39 skipped, 2 deselected`). On 5.58.0 that file passes 8 of 8 in the
gate below. No test was weakened.

## Dependabot policy change

In the pip `minor-updates` group, `edgartools` now joins `sqlalchemy` in `exclude-patterns`. The
weekly group can no longer bundle the held version with unrelated updates, as it did in #1096.
Dependabot still proposes Edgartools in its own PR, where the Ford test gates it. This is not an
ignore rule, which decision D ruled out.

A new pip `ignore` entry covers `sqlalchemy` `version-update:semver-minor`. The
[#1010 split](../dependency-split-2026-09-28/README.md) capped SQLAlchemy at `<2.1` because 2.1
maps a bare `postgresql://` URL to psycopg 3, which is not installed. Dependabot #1095 proposed
2.1.2 anyway. SQLAlchemy 2.0.x patch updates still arrive. The rule limits version updates only.
For security-update jobs, dependabot-core's `IgnoreCondition#ignored_versions` keeps only an
entry's explicit `versions` and drops its `update-types`, and this entry has no `versions`. A
security fix shipped only in 2.1 can therefore still open a #1095-style PR. CI's
`migrations-postgres` job will stop it, as it stopped #1095
([111663839337](https://github.com/neilmac91/EarningsNerd/actions/runs/37279450106/job/111663839337):
`No module named 'psycopg'`; backend-tests passed there on SQLite). Such a PR must be closed or
migrated deliberately, which is the existing #1010 position. The YAML parses, and nothing else in
the file changed.

## Compatibility notes

- **FastAPI 0.142.** The only new dependency is `opentelemetry-api`, used by FastAPI's native
  telemetry bridge. That bridge exports only when an OTel SDK provider or an
  `OTEL_EXPORTER_OTLP_*` endpoint is configured. Neither exists here: no `OTEL_` setting appears
  in the repository, and the OTel SDK is not in the lock. If an endpoint were set, the missing SDK
  would make FastAPI log a warning and start normally. The
  [offline probe](fastapi_telemetry_probe.py.txt) imports the real `main.app` with sockets blocked.
  It shows the bridge disabled and the proxy providers in place, both without Sentry and with
  Sentry initialized from a synthetic DSN. See the [result](fastapi-telemetry.txt).
- **OpenAI 3.23.** `_base_client.py`, `_streaming.py`, `_exceptions.py` and
  `resources/chat/completions/completions.py` are byte-identical to 3.20.0. The core deltas are an
  auth error message, whitespace-tolerant boolean response parsing, and `NotRequired[Annotated]`
  unwrapping in parameter transforms. The suite's real-SDK mock-transport tests run in the gate.
- **PostHog 7.62.** The 23 September [offline shape check](../sdk-minor-refresh-2026-09-23/posthog_shapes.py.txt)
  gives identical output on [7.60.1](posthog-shapes-7.60.1.txt) and [7.62.0](posthog-shapes-7.62.0.txt)
  apart from the version.
- **Anthropic 1.11 (optional eval file).** The #1067
  [offline check](../optional-anthropic-split-2026-10-02/anthropic_shapes.py.txt) ran with `--app`
  against runtime + eval requirements, using `httpx2.MockTransport`, blocked sockets and synthetic
  keys. Its [result](anthropic-shapes-1.11.0.txt) is `ANTHROPIC_SHAPES_OK 1.11.0 app`. It matches the
  1.9.0 receipt apart from the version.
- python-dotenv and ruff are patch releases. `ruff check .` is clean below. python-dotenv 1.2.4 also
  fixes one parse: `KEY=   # comment` now gives an empty value instead of the comment text. That makes
  `APPLE_CLIENT_ID` from `backend/.env.example` correctly empty for a developer who copied the file,
  so Apple sign-in reads as unconfigured. Cloud Run has no `.env` file, so production is unaffected.
  (Added after merge from the exact-head review's nit.)

## Verification

A fresh Python 3.11.17 environment installed `requirements.txt` + `requirements-dev.txt`. All 100
installed runtime versions match the lock, and `pip check` reports no broken requirements.
`pip-audit -r requirements.txt` reports no known vulnerabilities. The gate ran from `backend/` on
`6ae59ea6` with a sanitized environment: no inherited provider keys, and only conftest's
synthetic values. As in CI's backend-tests job, no PostgreSQL service was present. The tails are
below, with the Ford file's progress line taken from the same pytest log:

```
$ ruff check .
All checks passed!
ruff exit=0
$ bandit -r app -ll
Run metrics:
	Total issues (by severity):
		Undefined: 0
		Low: 15
		Medium: 0
		High: 0
bandit exit=0
$ python -m pytest
tests/unit/test_outlook_source_coverage.py ........                      [ 68%]
=== 5759 passed, 39 skipped, 2 deselected, 40 warnings in 464.22s (0:07:44) ====
pytest exit=0
```

No new gate or contract is introduced, so no mutation proof applies.

## Release boundary

As written before the push: this is local, unpushed preparation. Independent exact-head review and the hosted required checks
remain release requirements. The change touches `backend/requirements*.txt`, so a merge triggers
`deploy-backend`, with the usual serialized migration receipt and health verification. No provider
call, workflow dispatch or production operation occurred.

## Release record (added after merge)

- **PR and merge:** #1119 at head `76d2ba6d`, squash-merged as `111e8ce4` at 2026-10-07T23:12Z. It
  supersedes Dependabot #1096, closed with comment 6048731593.
- **Paid validation on the exact head** (E1 precedent):
  - eval-baseline dispatch run 37695333206: 70/70 scored, errors 0, regression gate PASS. Two
    warnings:
    - untraceable dollar figures (advisory);
    - `mean_citation_fidelity` 0.8615 vs 0.9648. Every 7 October run that finished before 23:12Z
      reads 0.818–0.862, because the eval harness's section extraction fell back to regex for
      35/35 filings. A run that finished at 23:13Z read 0.871 (8 runs in all; see decision 3 of
      `tasks/pr-disposition-2026-10-07.md`). This is not caused by this diff and is queued as a
      follow-up.
  - copilot-eval run 37695352886: accepted, 18/18, 0 errors.
  - Cost: USD 0.181759 in total.
- **Reviews:** Codex completed on `76d2ba6` with no findings. The independent three-lens exact-head
  review found no blocker and no should-fix. Its two nits are corrected in this file.
- **Deploy:** main CI run 37700883978, deploy job 113066259541. It was the first deploy built with
  Buildx and the GHA cache (#1117).
  - Migrations: `apply_migrations: applied=0 skipped=41`.
  - Revision `earningsnerd-backend-00446-vhw` serves 100% of traffic.
  - "Verify health" reported healthy.
  - An independent `/health/detailed` read at 2026-10-07T23:24:50Z returned 200 healthy, with the
    database at 6.13 ms and the SEC circuit closed.
  - Release comment: #1119 comment 6048886899.
