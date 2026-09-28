# Non-ORM dependency split — September 28, 2026

This maintenance tranche separates eight updates from [held #1000](https://github.com/neilmac91/EarningsNerd/pull/1000), whose source head is `284795e06330aa17177efc09907841adc8758ad3`. Its SQLAlchemy 2.1 update changes the default driver selected by bare `postgresql://` URLs and failed the PostgreSQL schema-seeding gate with `ModuleNotFoundError: No module named 'psycopg'`. The [SQLAlchemy migration guide](https://docs.sqlalchemy.org/en/21/changelog/migration_21.html#default-postgresql-driver-changed-to-psycopg-psycopg-3) documents that default-driver change.

Base: current main `4088743ca6ad3604a1dc4cb6b897e8864d506bd7`. The backend tree is byte-identical to previously tested `0776bb941eadb45402abc94dcff0b85d2bb02e0f` (`65ec685758a090b3d26a148531eb062454dfbc1b`). The four-manifest compiled patch has SHA-256 `3cc17ac95aaef5aac86967976b5c214e43131565398f605da660d516479fb932`.

| Dependency | Previous | Candidate |
| --- | --- | --- |
| json-repair | 0.63.4 | 0.63.5 |
| openai | 3.16.2 | 3.19.2 |
| posthog | 7.58.0 | 7.60.0 |
| PyJWT | 2.14.0 | 2.15.0 |
| sentry-sdk | 2.69.2 | 2.70.0 |
| uvicorn | 0.53.0 | 0.54.0 |
| ruff (development) | 0.16.8 | 0.16.9 |
| anthropic (optional evaluation) | 1.7.0 | 1.8.0 |

The runtime lock retains 99 packages with six version changes, no additions/removals and no unrelated transitive version drift. SQLAlchemy remains 2.0.54 with source range `>=2.0.54,<2.1`; psycopg2-binary 2.9.13 and greenlet 3.5.6 remain unchanged. pip-tools 7.5.3 on Python 3.11.16 generated the candidate with targeted upgrades and reproduced it byte-for-byte without upgrade flags. Its sole non-version lock delta removes SQLAlchemy from greenlet's generated provenance comment on macOS arm64; the explicit greenlet pin remains. No lock bytes were manually edited.

SQLAlchemy is excluded only from the backend Dependabot `minor-updates` version-update group. This keeps a future driver migration separate from routine updates and does not add a global ignore or change the security-update group.

The retained preparation installed runtime, development and optional evaluation dependencies with clean `pip check` results and unchanged runtime pins. A socket-blocked Anthropic MockTransport probe covered request/response shape, five HTTP errors, connection errors and timeouts without provider credentials or calls. Fresh implementation-gate evidence follows here before push. No application code, tests, migrations, model configuration, baseline pins or production settings change in this tranche.

Release boundaries: the replacement remains draft. Original #1000 remains open. Exact-head hosted checks and independent review are still required; ready-for-review opts into the paid Copilot workflow and is left to the coordinating release owner. Dependency maintenance is parallel to unresolved semantic-quality and beta work; it does not activate held pricing #1009 or establish product acceptance.
