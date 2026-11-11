# A tag publishes the commit it names: never archive an unscanned branch as a tag, scan tags like branches, and answer a leaked key by revoking it

Date: 2026-11-11   Area: ops (security)

**Context**: On 2026-01-18 the closed pull request #17 (head branch `2025-11-18-qpw4-40e1b`, commit
`222424317`) added `backend/env.example.txt` and `frontend/env.example.txt` holding the real values of
an OpenRouter API key, a Supabase secret key, the Supabase project URL and its anon key. Cursor Bugbot
flagged them on the pull request the same day. On 2026-01-22 `scripts/cleanup-branches.sh` archived
the branch as the annotated tag `archive/2025-11-18-supabase-rag`, pushed the tag and deleted the
branch. From then on the commit was reachable on GitHub only through that tag and `refs/pull/17/head`.
CI's `secret-scan` (added by #1069 on 2026-10-04) checked out every tag (`fetch-depth: 0`) but walked
`--log-opts="--branches --remotes"`, by a comment that called tags "curated by hand", so it read
3,184 commits as clean on every run and never that one. GitHub's secret scanning raised alerts 1
(OpenRouter) and 2 (Supabase) on 2026-01-18 with the label "Public leak". On 2026-11-11 the audit
fetched every ref (11,861 commits) and found no other real credential. Alerts 3 (a sequential
`whsec_1234567890…` placeholder in a deleted doc) and 4 (Svix's published example secret, a test
vector at `backend/tests/unit/test_resend_webhook_signature.py:24`) are not credentials. gitleaks
8.24.3 has no rule for either `whsec_` shape, nor for OpenRouter, Supabase, DeepSeek, Resend or Google
OAuth keys, so a bare key of those shapes passed the scan.

**Rule**:
1. A tag, a pull request's head ref and a fork publish the commit they name exactly as a branch does.
   Never archive a branch as a tag, or keep any ref to it, before a scan of its commits is clean.
   Keep an unscanned branch's work as an offline `git bundle`.
2. CI's secret scan walks every branch and every tag. The repository's `.gitleaks.toml` adds a rule
   for each key shape this stack holds or held that the built-in set misses. When the stack takes a
   new provider, add its rule and a vector to `backend/tests/unit/test_gitleaks_repo_rules.py`.
3. A credential that reached a public ref is compromised whatever happens to the ref afterwards.
   Revoke or rotate it at the provider first, and review the provider's usage from the day it
   leaked. Deleting the ref only shortens the exposure. GitHub keeps `refs/pull/<n>/head` read-only
   and serves cached commit views, so only GitHub Support can purge those, and a history rewrite of
   `main` would not reach them either. Never pin a real credential in `.gitleaksignore` to turn CI
   green.
4. Close a secret-scanning alert only for what it is: "Revoked" after the provider confirms it, "False
   positive" for a placeholder, "Used in tests" for a published test vector. Alerts do not close
   when the line or the ref goes away.

**Gate**: `backend/tests/unit/test_ci_secret_scan_scope.py` (the scan walks
`--branches --remotes --tags` or `--all`, over a full checkout, reading `.gitleaks.toml` from the
checkout), `backend/tests/unit/test_gitleaks_repo_rules.py` (each repository rule finds its shape,
named or bare, and passes over placeholders) and the widened selector of
`backend/tests/unit/test_example_env_files_are_placeholders.py` (it now reads `env.example.txt`).
Clause 3's rotation, the provider usage review and the alert dispositions are the founder's
(`tasks/todo.md` F73), and review-checked.

**Evidence**: `git for-each-ref --contains 222424317` lists only `refs/tags/archive/2025-11-18-supabase-rag`
(tag object `ee2eff971`) and `refs/pull/17/head`. Main's CI run 42986073465 (job 130407432442) logged
`* [new tag] archive/2025-11-18-supabase-rag` at checkout and then `no leaks found` over
`--branches --remotes`. The pinned gitleaks 8.24.3 with the new rules finds nothing over `--branches --remotes`. Over
`--branches --remotes --tags` it finds four findings, all in `222424317`, and nothing else: the two keys
(`backend/env.example.txt` 20, `openrouter-api-key`, and 16, `supabase-secret-key`) and the anon JWT
under the built-in `jwt` rule (`backend/env.example.txt` 15, `frontend/env.example.txt` 9). So CI's scan
is red until the tag is deleted. The values never reached `main`. The current AI provider
is DeepSeek (`.github/ai-model.env`), and no code on `main` reads a Supabase or OpenRouter setting, so
revoking both keys cannot break production.
