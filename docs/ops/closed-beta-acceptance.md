# Closed beta: acceptance, staged admission and rollback

How a closed beta of invited testers with complimentary Pro access is accepted, admitted in stages and rolled
back. The code is the source: where this page and the code differ, the code is right and this page is wrong; fix
it in the same change. Each check names the test that pins it, or the operational evidence that stands in where no
test can; three rollback levers in section 7 name neither yet.

This page holds no tester, recipient, operator or provider identifier and no figures read from production. The
roster and the cohort tracker live in the founder's private store ([section 9](#9-private-cohort-tracker)).
Status, current evidence and open blockers belong in the pull request that records an acceptance, not here.

Who decides what, in this programme's governance: the founder approves every live action named below (each mutation,
each production flag, each protected Ops `-apply`, each invitation sent) and is the release approver. The chief
engineer accepts engineering evidence for an exact source head. Nothing on this page authorizes an action by itself.

## 1. Identities to record before every acceptance step

An acceptance holds only for the identities it was taken on. A change to any row below resets the checks that
depend on it.

| Identity | How to read it | Notes |
| --- | --- | --- |
| Source | `main`'s commit, and each open pull request's head | Record full SHAs. |
| Backend release | The `deploy-backend` job log of the newest commit that deployed: `apply_migrations: applied=N skipped=M`, `revision [earningsnerd-backend-…] … serving 100 percent`, the task worker's revision, `Deployed <sha> and verified healthy` | A job that finds no deployable backend change, or skips as superseded, concludes success and deployed nothing ([deploy discipline](../../AGENTS.md#6-deploy-discipline)). |
| Backend runtime | Ops `describe-service` (read-only; [F51](../OPERATIONS.md#agent-production-readbacks-f51)): serving revision, image digest, `SENTRY_RELEASE`, `REGISTRATION_MODE`, sizing lines, worker invoker verdict | It prints only the names of the `LEGAL_*` and `FEEDBACK_MEDIA_*` settings, when set, and withholds `REVERSE_TRIAL_ENABLED`, `PRO_TRIAL_DAYS` and `STRIPE_BETA_PROMO_CODE_ID`. The founder reads those values on the service; the live answers below show only their effect. |
| Frontend release | The GitHub deployment named `Production` for the commit, and the `www` alias it serves where the Vercel dashboard shows it | Record `NEXT_PUBLIC_ENABLE_CALENDAR` and `NEXT_PUBLIC_ENABLE_ANALYSIS` too: the earnings-day alert bells and Multi-Period Analysis exist only while they are on. |
| Live answers | `GET /health/detailed`; `GET /api/legal/readiness` (collection, checkout and marketing availability, the two agreement versions, the operator notice); `GET /api/auth/registration` (`invite_only`, `beta_promo_enabled`) | Public reads; no account needed. |
| Screenshots | `GET /api/feedback/capabilities` signed in: `attachments_enabled` is true only while `FEEDBACK_MEDIA_ENABLED` is on and a bucket is set; no Ops read prints either value. The newest `feedback-media-inspect` and `feedback-media-verify-*` receipts | Enabling needs `feedback-media-provision-apply`, `-verify-apply` and `-enable-apply`. At the enable, the provision's storage probe, the latest scheduled cleanup and the verify receipt must each be at most two hours old, and the cleanup heartbeat must have been seen in the last two hours. Both bind the serving backend image, and the receipt also binds `main`'s `frontend/` tree and the verification sources. So land every `frontend/` and `ops/feedback_media/` change the window needs first; then, from the provision dispatch until the enable completes, merge nothing that deploys the backend or changes `frontend/` or `ops/feedback_media/`. |
| Agreement versions | `TERMS_VERSION` and `ELIGIBILITY_VERSION` in `backend/app/services/legal_readiness_service.py`, as `/api/legal/readiness` serves them | A version change asks every new tester for fresh assent. |
| Model | `AI_DEFAULT_MODEL` and `OPENAI_BASE_URL` from `describe-service` | A change re-opens the summary, Copilot and analysis checks. |

## 2. Synthetic acceptance (CI)

[`backend/tests/integration/test_closed_beta_journey.py`](../../backend/tests/integration/test_closed_beta_journey.py)
runs the beta journey through the real API on every pull request, under the production-shaped holds (collection
ready, `invite_only`, invitation mail held, checkout closed). It uses SQLite. It fakes SEC, the model, Google, Stripe,
object storage and image processing at the seams their own suites fake, captures account mail where `email_service`
sends it, and runs with PostHog, Sentry, Resend, the breached-password check and Turnstile switched off. So it proves
the API composes for a beta account. It proves nothing about production
delivery, configuration or capacity; sections 3 to 5 carry those.

| Test | What it pins |
| --- | --- |
| `test_an_invited_tester_registers_verifies_and_signs_in` | Manual-link invitation, registration with the tester's own assent, the beta tag, the agreement row, verification, sign-in, the spent link |
| `test_every_unusable_invitation_is_refused_and_creates_nothing` | Missing, unknown, other-address, revoked and expired links are refused and create nothing; the revoked and expired links are tried from the address they name |
| `test_an_invited_tester_signs_up_with_google_and_signs_back_in` | Invited Google sign-up, its agreement row, a returning sign-in that needs no invitation, no reset mail for a social-only account |
| `test_pro_capabilities_answer_a_pro_tester_and_stay_shut_for_free` | Every Pro capability the pricing pages sell except priority support, through its route (Multi-Period Analysis and the Excel export only to the plan gate), for three ways an account can hold Pro (the mirror alone, an active row, a future trial row, each with the mirror set), against a Free control; checkout stays closed |
| `test_every_pro_entitlement_has_a_beta_acceptance_answer` | Gate: every entitlement in which Pro differs from Free has an answer in `CAPABILITY_MATRIX` |
| `test_a_grant_and_its_revocation_reach_only_the_account_they_name` | Grant and revoke move one account; the others' plan inputs and flags are unchanged |
| `test_billing_events_for_other_accounts_never_reach_a_complimentary_tester` | Stripe events for another account leave a complimentary tester as they were |
| `test_feedback_reaches_triage_and_the_testers_data_leaves_with_them` | Text and screenshot feedback, admin triage, private screenshot reads, export, deletion, screenshot cleanup |
| `test_a_tester_signs_out_resets_their_password_and_signs_back_in` | Sign-out of one browser, reset mail, no other browser can refresh its session (an access token already issued lives out its 30 minutes), the new password, a single-use link |
| `test_one_testers_session_never_reaches_anothers_records` | Watchlist, saved summaries, feedback receipts and export stay with their owner |
| `test_pausing_invitations_keeps_existing_testers_signed_in_and_their_rights` | Revoking a cohort's pending invitations leaves admitted testers' sessions, Pro and export |
| `test_switching_screenshots_off_keeps_text_feedback_and_cleanup` | Screenshots off: uploads answer 503 with a message that the draft has been kept; text feedback, reading an existing screenshot and cleanup still work. The open form then holds the draft unsendable until a reload, which discards its note and screenshot (section 7) |
| `test_closing_collection_stops_new_accounts_and_keeps_admitted_testers` | Collection closed: minting, re-sending and registering answer 503, the waiting invitation is neither spent nor revoked, admitted testers keep sign-in, Pro and export |
| `test_pausing_new_summaries_keeps_stored_ones_and_the_rest_of_the_account` | New summaries paused: a fresh one is refused with no model call, a stored one still serves, feedback and sign-in work |
| `test_account_work_answers_while_summaries_generate_on_a_production_sized_pool` | With the most generations a process admits held at the model call, on a four-connection pool with no overflow, sign-in, usage, feedback and a reset request all answer and a connection stays free |

[`backend/tests/unit/test_beta_operator_switches_survive_deploys.py`](../../backend/tests/unit/test_beta_operator_switches_survive_deploys.py)
keeps every `LEGAL_*` and `FEEDBACK_MEDIA_*` setting out of every workflow file. With
`backend/tests/unit/test_summary_rollout_preservation.py`, which holds each CI deploy command to one additive
environment map, no CI deploy resets the founder's switches. A console edit and the manual bootstrap
`gcloud run deploy` in `docs/DEPLOYMENT.md`, which uses `--set-env-vars`, are outside both gates.

`_grant_pro` and `_revoke_pro` are the only places the tests grant or revoke a tester's complimentary Pro (the pool
check seeds its generating accounts as Pro, and the Stripe test's paying account becomes Pro through its own
checkout event). When the complimentary-access operation lands, its grant and revoke replace the `mirror` holder's
body and `_revoke_pro`'s, run as the operator runs them: the dry run, then the apply of the digest that dry run
reported. The two row holders stand for a subscriber's Pro, which a grant never writes, so they keep their rows.
Every test must then pass unchanged. That is its integration acceptance.

## 3. Live acceptance checklist

Run in order at the founder rehearsal ([section 6](#6-staged-admission)), on a phone and on a desktop browser,
with two founder-controlled tester accounts (one password, one Google), a third disposable one for step 23 and the
administrator account. Step 22 also needs a used, a revoked and an expired link: mint the expired one 48 hours ahead
(the admin page's shortest expiry) or through the API with a shorter one. A step passes only on what the tester's
own screen and inbox show; a badge, a provider's acceptance or a mocked response is not a pass.

| # | Step | Passes when | Synthetic proof |
| --- | --- | --- | --- |
| 1 | Mint the invitation | `/admin/invites` with "Email invites" cleared returns a link, bound to the tester's address | onboarding test |
| 2 | Deliver it | The link reaches the tester through the founder's own channel and opens `/register` with the invitation | — |
| 3 | Link scanners | Opening the link with a plain `GET` (`curl`) and again in a browser leaves the invitation `pending` in `/admin/invites` | `frontend/tests/e2e/legal-readiness.spec.ts` (no write request before submit); `backend/tests/unit/test_read_only_get_endpoints.py` (GET routes write nothing, except allowlisted ones such as the Google callback, which needs the state the tester's own browser started) |
| 4 | Register | Both agreement boxes start unchecked; registration answers with the check-your-email notice | onboarding test; `frontend/tests/e2e/legal-readiness.spec.ts` (both boxes start unchecked) |
| 5 | Verification mail | The mail arrives in the tester's inbox within the founder's mail window and its link verifies the account. A mail scanner that runs scripts can open the link first: the page then reports a failure although the account is verified; record it | onboarding test (capture only) |
| 6 | Sign in | Password and Google sign-in return to the home page signed in, and the account menu shows the tester's own address | onboarding and Google tests |
| 7 | Complimentary Pro | The account shows Pro on the dashboard, in Settings and in usage, and Settings offers no upgrade or checkout | matrix and grant tests (the plan through `/api/auth/me` and usage; nothing tests Settings' billing control) |
| 8 | Search and filing | A covered company's filing page loads | — |
| 9 | Cached summary | A filing with a stored summary renders it at once | matrix test (cached read) |
| 10 | Fresh summary | A filing without one generates to completion | matrix test |
| 11 | Ask this Filing | A fourth question answers with cited passages (Free's three are for the account's lifetime) | matrix test (gate only) |
| 12 | Multi-Period Analysis | Ten annual periods and twelve quarters render, and the narrative completes | matrix test (dataset gate only) |
| 13 | Exports | The summary PDF and CSV and the analysis Excel workbook download and open | matrix test (Excel: gate only) |
| 14 | Watchlist and alerts | A company is added; hourly filing and 8-K alerts can be switched on; more than three earnings-day alerts are allowed (the bells on `/calendar`, which needs `NEXT_PUBLIC_ENABLE_CALENDAR`; pick four companies it lists) | matrix test |
| 15 | An alert arrives | One filing or 8-K alert reaches the tester's inbox | — (sends real mail; needs approval) |
| 16 | Text feedback | It appears in `/admin/feedback` with the tester's address | feedback test |
| 17 | Screenshot feedback | Only once screenshots are enabled: the report and its image appear in `/admin/feedback` | feedback test |
| 18 | Triage | The administrator marks it triaged | feedback test |
| 19 | Sign out, reset, sign in | The reset mail arrives; the old password fails; the new one works | reset test |
| 20 | Export | Settings → export downloads the tester's data with their agreement and feedback | feedback test |
| 21 | Cross-account | Signed in as one tester, the other's saved summaries, watchlist and screenshots cannot be reached | cross-account and feedback tests |
| 22 | Unusable invitations | A used, revoked and expired link each show a page the tester can act on | onboarding test (used) and invalid-invitation test (revoked, expired); refusal only |
| 23 | Deletion | A disposable tester account deletes itself and its session ends. With screenshots enabled, its screenshot cannot be opened at once and its object is gone after the next hourly cleanup run | feedback test |

Steps 7 and 22 cannot pass with today's code: Settings offers Upgrade to Pro to an account with no Stripe customer,
and every unusable link answers one refusal with no way forward. They pass only after the complimentary-access
work's Billing fix and the invitation work's per-case refusals, which makes both preconditions of the rehearsal.

A tab must never change the credentials of an account other than the one it shows (E29 (6) in `tasks/todo.md`).
Before any tester is admitted, that auth repair is merged and deployed with its own two-account tests (one
target with a password, one social-only), and the founder rehearsal repeats the manual check its pull request
describes. Neither account may change. E29 (5), an OAuth sign-in that another tab's refresh can undo, is fixed or
dispositioned in writing before the rehearsal.

## 4. Pro capabilities: pass and fail

The beta grants what the pricing pages sell as Pro: the `/pricing` cards (`frontend/app/pricing/page.tsx`) and the
landing's table (`frontend/features/marketing/components/PricingSection.tsx`), both reading
`frontend/lib/planLimits.ts`. Each row passes only when every part of its pass column holds for a complimentary
tester. `CAPABILITY_MATRIX` in the journey test gives every entitlement in which Pro differs from Free
(`backend/app/services/entitlements.py`) a test or a written reason; it does not read the pricing pages.

| Capability | Passes when | Fails when |
| --- | --- | --- |
| Unlimited summaries (fair-use ceiling 300 a month) | A sixth fresh summary in the month generates | Any upgrade prompt or Free allowance message |
| Ask this Filing | Questions past the Free three answer, with cited passages | The free-question limit or an upgrade prompt |
| Multi-Period Analysis | Dataset, charts and narrative for ten annual periods and for twelve quarters | A plan refusal, or an empty dataset for a covered company |
| PDF, CSV and Excel exports | Each file downloads and opens: the summary PDF and CSV with the filing's figures, the Excel workbook with the analysis's periods | A plan refusal or an empty file |
| Hourly filing alerts and 8-K alerts | Both switches stay on after saving, and an alert arrives | A switch reverting to off, or no alert after a matching filing |
| Earnings-day alerts beyond three (not on the pricing pages; Pro's cap is never shown) | A fourth company's alert switches on | The Free limit message |
| Watchlist | Unlimited on both plans | — |
| Priority support | The support inbox answers a tester within the window the founder sets | No answer; nothing machine-checks this row |

Dormant flags stay off for the beta unless they pass their own acceptance: `ENABLE_SECTION_CHANGES` (the landing's
pricing table lists the Change Report for both plans), `REVERSE_TRIAL_ENABLED` (global, not targeted, and with no
revoke before its end), and the forward-looking entitlements `history_retention_days` and `priority_model`, which
nothing enforces. The serving API and worker set `REVERSE_TRIAL_ENABLED`, and `describe-service` withholds its
value, so the founder confirms it is false before the rehearsal. If it is true, `/verify-email` gives each tester
who signed up with a password a seven-day trial row and sets `is_pro` (Google and Apple sign-ups never call it). A
subscription row outranks the `is_pro` mirror, so once the trial lapses that tester is enforced Free while
`/api/auth/me` still reads Pro, and a complimentary grant cannot restore Pro over the row.

## 5. Operational acceptance

Read before admission, after the founder rehearsal, and at each observation point of section 6.

| Signal | Source | Concern for the beta |
| --- | --- | --- |
| Serving shape | `describe-service` sizing lines | Configured inputs only (instances, concurrency, CPU, memory, pool); not measured load |
| API latency and errors, queue depth and task attempts, SQL connections, job executions | Ops `capacity-readout` (read-only, bounded) | Observed aggregates; a partial read is a floor, never zero |
| Pool reserve | `database.checked_out` from `GET /metrics` (administrator); [thresholds](../OPERATIONS.md#monitoring-alerts-suggested-thresholds) | The deployed pool has no overflow. A reading covers one instance and counts its own connection, so 1 means nothing else is checked out |
| SEC throttling | The SEC breaker in `/health/detailed`; `sec_rate_limiter` and `circuit_breaker` in `GET /metrics` (administrator), each for the instance that answered | An open breaker stops fresh summaries that must fetch their filing from SEC on that instance; Multi-Period Analysis does not use it |
| Model cost and timeouts | The DeepSeek balance readout; `ai_call` log lines ([telemetry](../OPERATIONS.md#ai-call-telemetry-ai_call--ai_summary-log-lines)) | Spend against the founder's daily limit |
| Account mail | Inbox arrival time at steps 5 and 19. For step 5, the API's logs and Sentry; for reset and resend mail, the worker's `email NOT sent` and `(nothing sent)` lines ([account mail](../OPERATIONS.md#account-mail-f60)) | The API sends registration's mail itself; reset and resend mail wait behind the single task worker's current task and anything queued before it |
| Job freshness | `capacity-readout`'s job executions and job ledger; the weekly data-quality report (`describe-jobs` reads configuration only) | Filing and 8-K alerts depend on the hourly filing scan; earnings-day alerts depend on their own daily job |
| Errors | Sentry, filtered to the serving `SENTRY_RELEASE`; `logs-probe` start lines per API revision | Every API revision reports under its own release. The task worker and the pregenerate job bind no `SENTRY_DSN`, so their failures reach Cloud Logging only |
| Funnel | PostHog: the browser's events, sent only after a tester's cookie consent, and the API's account events (sign-up, invitation redeemed, feedback), sent whatever the choice (D-051) | A step missing from the browser's events is not proof it failed; read the API's events or the database |
| Backups | The newest monthly SQL export run; managed backup and point-in-time settings read by the founder | The tolerated loss window must be set before testers create data, and a restore proof must cover every applied migration |
| Alerts | The alert policies and Sentry alert rules that exist, and a test notification someone received | Without one, the daily smoke issue is the only automated availability signal, so an outage can go unseen for a day |

Fresh summaries are generated inside the API request on the serving architecture; durable summary generation is
not active. Whether that path carries the beta's load is unmeasured, and the first wave's capacity readout is the
first evidence. Fresh summaries share the API's CPU, its four-connection pool and its event loop with sign-in,
feedback and registration mail, while reset and resend mail wait behind the single task worker's current task and
anything queued before it. Six first-time generations of large filings at once leave most of them a
lower-quality excerpt that is stored for good (E77 in `tasks/todo.md`), so the first wave's observation reads the
capacity readout around its busiest hour. Nothing in code caps
daily model spend: the provider balance is prepaid and read by hand, and running it out stops fresh summaries, Ask
this Filing answers and new Multi-Period Analysis narratives for every tester. Stored summaries, the analysis
dataset, its charts and its workbook still serve. A rehearsal of the durable path, or a load run against an
isolated environment, needs its own approved budget.

## 6. Staged admission

1. **Founder rehearsal.** The founder runs section 3 end to end with founder-controlled accounts only, on the
   identities of section 1. Any failed step stops the programme until it is fixed and re-run.
2. **First wave: three testers.** Mint three address-bound invitations under one cohort label; deliver them;
   observe for 24 to 48 hours, reading section 5 at least twice a day and the feedback inbox daily.
3. **Second wave: the remaining testers,** only once the first wave meets every exit condition below, under a new
   cohort label.

Each wave exits when no stop condition has occurred, every tester in that wave has signed in and holds Pro, and
the feedback and support inboxes are answered. Stop admitting, and use section 7, on any of these:

- a tester cannot sign in or reach their account;
- a tester without Pro, or a Pro surface refusing a complimentary tester;
- any access to another account's data;
- known wrong data shown without its qualification. Before the rehearsal, each such item open in `tasks/todo.md`
  is repaired, shown with its qualification, or accepted by the founder in writing, and the rehearsal opens the
  periods each one names on the analysis page;
- lost feedback or screenshots;
- stalled mail, alerts or queues;
- an error rate, cost or capacity reading beyond the limits the founder set before the wave.

Land every deploy or repair that moves stored financial figures before the rehearsal. During a wave, a saved
analysis over a period that moved refuses its export, telling the tester to run it again, and an acceptance holds
only for the identities it was taken on.

## 7. Rollback levers

Each lever stops one thing. Apart from the one account a revoke or a suspension names, each keeps sign-in, granted
rights, data export, deletion and cleanup. Every lever is a live action, and the founder approves each one. Only
the Ops `-apply` operations enforce that, through the `ops-apply` approval; `rollback-traffic` has no approval step,
so an incident rollback does not wait.

| Lever | How | Stops | Keeps | Proof |
| --- | --- | --- | --- | --- |
| Pause a wave's invitations | `/admin/invites`: revoke each pending invitation of the cohort | New registrations with those links | Admitted testers, their sessions, Pro and data | `test_pausing_invitations_keeps_existing_testers_signed_in_and_their_rights` |
| Close all new accounts | `LEGAL_COLLECTION_ENABLED=false` on the API service | Every mint, re-send and registration answers 503, and so do the contact form and waitlist joins | Existing accounts, sessions, sign-in, linking, Pro, export and deletion; waiting invitations stay usable for a reopening until they expire (seven days after minting by default) | `test_closing_collection_stops_new_accounts_and_keeps_admitted_testers`; `tests/unit/test_account_agreement.py` (closed collection keeps password and social sign-in) |
| Pause new summaries | `SUMMARY_NEW_JOBS_PAUSED=true` on the API service, the task worker and the pregenerate job | New summary generation | Stored summaries, sign-in, feedback. It does not stop Ask this Filing or Multi-Period Analysis: `COPILOT_MONTHLY_QUESTION_CAP=0` on the API service refuses every Pro question as a fair-use refusal, and `NEXT_PUBLIC_ENABLE_ANALYSIS=false` on Vercel, then a redeploy, hides the analysis page while its API still answers | `test_pausing_new_summaries_keeps_stored_ones_and_the_rest_of_the_account` |
| Revoke one tester's Pro | The complimentary-access revoke (its dry run, then its apply), once that code is deployed and its Ops operations exist; until then only a direct database write revokes Pro | That account's Pro surfaces | The account, its session, its beta tag and its data | `test_a_grant_and_its_revocation_reach_only_the_account_they_name` |
| Switch screenshots off | Ops `feedback-media-disable-apply`, approved for that run. It is refused while a `main` push run is in progress or queued, and it waits in the shared `ops` queue, where a later pending dispatch replaces it, so dispatch nothing else until it runs | New screenshot uploads | Text feedback, reading and cleaning up existing screenshots | `test_switching_screenshots_off_keeps_text_feedback_and_cleanup` |
| Hide the feedback launcher | `NEXT_PUBLIC_ENABLE_FEEDBACK_WIDGET=false` on Vercel, then a redeploy | The whole launcher, text feedback included | Everything else | — |
| Suspend one tester | No route exists; a direct database write of `users.is_active=false` | That account's sign-in | Its data | — |
| Roll back the API | Ops `rollback-traffic`, then a revert, after the account-mail queue drains ([account mail](../OPERATIONS.md#account-mail-f60)) | The current revision | The database | — |

Switching screenshots off while a tester has a screenshot draft open leaves that draft unable to send: the form
keeps re-sending the screenshot, cannot remove it, and a reload discards both the note and the screenshot. Until
the feedback form recovers on its own, tell first-wave testers to copy their note before reloading and to send it
again as text.

A traffic rollback moves only the API service, and an environment switch belongs to a revision: moving traffic to
an older revision restores that revision's own `LEGAL_*`, `FEEDBACK_MEDIA_*` and `SUMMARY_NEW_JOBS_PAUSED` values,
and a switch changed while traffic is pinned lands on a revision that serves nothing (a screenshot disable then
fails by design). Re-read the live answers of section 1 after any rollback.

A code rollback never crosses a compatibility floor. Read [the rollback section of
DEPLOYMENT.md](../DEPLOYMENT.md#rollback-when-a-bad-revision-is-live) first: never roll the password reader back
before E97, whose Argon2id hashes an older reader cannot verify, and never move traffic past
`earningsnerd-backend-00661-zr9`; a rollback past E110 parks pending alert batches unsent. Applied migrations stay
applied, so the older revision must still run against the newer schema.

## 8. Operator inputs

Before the founder rehearsal the founder supplies, outside this repository where private:

- the public operator notice (`LEGAL_OPERATOR_*`) and the decision to publish it and open collection;
- what testers are told and agree to: the beta's duration, that feedback text (and its hashed network address) is
  kept without the account after deletion while screenshots are deleted, screenshot retention (180 days at most),
  and the support channel;
- the roster and the two cohort labels;
- the beta's end and review dates, and what complimentary access becomes at the end;
- the daily model spend limit, the error and capacity limits of section 6, the mail arrival window of section 3, the
  support answer window and the tolerated loss window of section 5;
- whether `REVERSE_TRIAL_ENABLED` is false on the service (section 4).

## 9. Private cohort tracker

Keep this table only in the founder's private store, keyed by a tester code (`T01`, `T02` and so on) with the
mapping to people held separately. Never commit a filled copy, a name or an address.

| Code | Wave | Invitation minted | Delivered | Registered | Verified | Pro granted | First feedback | Issues | Pro revoked | Closed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | 1 | | | | | | | | | |
