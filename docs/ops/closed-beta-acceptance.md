# Closed beta: acceptance, staged admission and rollback

How a closed beta of invited testers with complimentary Pro access is accepted, admitted in stages and rolled
back. The code is the source: where this page and the code differ, the code is right and this page is wrong; fix
it in the same change. Each check names the test that pins it, or the operational evidence that has to stand in
for a test where none can.

This page holds no tester, recipient, operator or provider identifier and no figures read from production. The
roster and the cohort tracker live in the founder's private store ([section 9](#9-private-cohort-tracker)).
Status, current evidence and open blockers belong in the pull request that records an acceptance, not here.

Who decides what: the founder approves every live action named below (each mutation, each production flag, each
protected Ops `-apply`, each invitation sent) and is the release approver. The chief engineer accepts
engineering evidence for an exact source head. Nothing on this page authorizes an action by itself.

## 1. Identities to record before every acceptance step

An acceptance holds only for the identities it was taken on. A change to any row below resets the checks that
depend on it.

| Identity | How to read it | Notes |
| --- | --- | --- |
| Source | `main`'s commit, and each open pull request's head | Record full SHAs. |
| Backend release | The commit's `deploy-backend` job log: `apply_migrations: applied=N skipped=M`, `revision [earningsnerd-backend-…] … serving 100 percent`, the task worker's revision, `Deployed <sha> and verified healthy` | A job that skips as superseded deployed nothing ([deploy discipline](../../AGENTS.md#6-deploy-discipline)). |
| Backend runtime | Ops `describe-service` (read-only; [F51](../OPERATIONS.md#agent-production-readbacks-f51)): serving revision, image digest, `SENTRY_RELEASE`, `REGISTRATION_MODE`, sizing lines, worker invoker verdict | It does not print the `LEGAL_*` or `FEEDBACK_MEDIA_*` values; read those from the live answers below. |
| Frontend release | The GitHub deployment named `Production` for the commit, and the `www` alias it serves | |
| Live answers | `GET /health/detailed`; `GET /api/legal/readiness` (collection, checkout and marketing availability, the two agreement versions, the operator notice); `GET /api/auth/registration` (`invite_only`, `beta_promo_enabled`) | Public reads; no account needed. |
| Screenshots | `GET /api/feedback/capabilities` signed in (`attachments_enabled`), the only read of the serving value; the newest `feedback-media-inspect` and `feedback-media-verify-*` receipts | Enabling needs `feedback-media-provision-apply`, `-verify-apply` and `-enable-apply` within about two hours, with no backend deploy between the receipt and the enable: the receipt binds the serving image. |
| Agreement versions | `TERMS_VERSION` and `ELIGIBILITY_VERSION` in `backend/app/services/legal_readiness_service.py`, as `/api/legal/readiness` serves them | A version change asks every new tester for fresh assent. |
| Model | `AI_DEFAULT_MODEL` and `OPENAI_BASE_URL` from `describe-service` | A change re-opens the summary, Copilot and analysis checks. |

## 2. Synthetic acceptance (CI)

[`backend/tests/integration/test_closed_beta_journey.py`](../../backend/tests/integration/test_closed_beta_journey.py)
runs the beta journey through the real API on every pull request, under the production-shaped holds (collection
ready, `invite_only`, invitation mail held, checkout closed). It uses SQLite and fakes every provider at the seam
its own suite fakes, so it proves the API composes for a beta account. It proves nothing about production
delivery, configuration or capacity; sections 3 to 5 carry those.

| Test | What it pins |
| --- | --- |
| `test_an_invited_tester_registers_verifies_and_signs_in` | Manual-link invitation, registration with the tester's own assent, the beta tag, the agreement row, verification, sign-in, the spent link |
| `test_every_unusable_invitation_gets_one_answer_and_creates_nothing` | Missing, unknown, other-address, revoked and expired links get one 403 and create nothing |
| `test_an_invited_tester_signs_up_with_google_and_signs_back_in` | Invited Google sign-up, its agreement row, a returning sign-in that needs no invitation, no reset mail for a social-only account |
| `test_pro_capabilities_answer_a_pro_tester_and_stay_shut_for_free` | Every Pro capability on the pricing page, through its route, for each way an account can hold Pro, against a Free control; checkout stays closed |
| `test_every_pro_entitlement_has_a_beta_acceptance_answer` | Gate: every entitlement in which Pro differs from Free has an answer in `CAPABILITY_MATRIX` |
| `test_a_grant_and_its_revocation_reach_only_the_account_they_name` | Grant and revoke move one account; the others' plan inputs and flags are unchanged |
| `test_billing_events_for_other_accounts_never_reach_a_complimentary_tester` | Stripe events for another account leave a complimentary tester as they were |
| `test_feedback_reaches_triage_and_the_testers_data_leaves_with_them` | Text and screenshot feedback, admin triage, private screenshot reads, export, deletion, screenshot cleanup |
| `test_a_tester_signs_out_resets_their_password_and_signs_back_in` | Sign-out of one browser, reset mail, every session ended, the new password, a single-use link |
| `test_one_testers_session_never_reaches_anothers_records` | Watchlist, saved summaries, feedback receipts and export stay with their owner |
| `test_pausing_invitations_keeps_existing_testers_signed_in_and_their_rights` | Revoking a cohort's pending invitations leaves admitted testers' sessions, Pro and export |
| `test_switching_screenshots_off_keeps_text_feedback_and_cleanup` | Screenshots off: uploads refused with the draft kept, text feedback and cleanup still work |
| `test_closing_collection_stops_new_accounts_and_keeps_admitted_testers` | Collection closed: minting, re-sending and registering answer 503, the waiting invitation stays usable, admitted testers keep sign-in, Pro and export |
| `test_pausing_new_summaries_keeps_stored_ones_and_the_rest_of_the_account` | New summaries paused: a fresh one is refused with no model call, a stored one still serves, feedback and sign-in work |
| `test_account_work_answers_while_summaries_generate_on_a_production_sized_pool` | With the most generations a process admits held at the model call, on a four-connection pool with no overflow, sign-in, usage, feedback and a reset request all answer and a connection stays free |

[`backend/tests/unit/test_beta_operator_switches_survive_deploys.py`](../../backend/tests/unit/test_beta_operator_switches_survive_deploys.py)
keeps every `LEGAL_*` and `FEEDBACK_MEDIA_*` setting out of every workflow, so no deploy resets the founder's switches.

`_grant_pro` and `_revoke_pro` are the only places the tests make an account Pro. The complimentary-access
operation replaces their bodies when it lands; every test must then pass unchanged. That is its integration
acceptance.

## 3. Live acceptance checklist

Run in order at the founder rehearsal ([section 6](#6-staged-admission)), on a phone and on a desktop browser,
with two founder-controlled tester accounts (one password, one Google) and the administrator account. A step
passes only on what the tester's own screen and inbox show; a badge, a provider's acceptance or a mocked
response is not a pass.

| # | Step | Passes when | Synthetic proof |
| --- | --- | --- | --- |
| 1 | Mint the invitation | `/admin/invites` with "Email invites" cleared returns a link, bound to the tester's address | onboarding test |
| 2 | Deliver it | The link reaches the tester through the founder's own channel and opens `/register` with the invitation | — |
| 3 | Link scanners | Opening the link with a plain `GET` (`curl`) and again in a browser leaves the invitation `pending` in `/admin/invites` | `frontend/tests/e2e/legal-readiness.spec.ts` (no request before submit); `tests/unit/test_read_only_get_endpoints.py` |
| 4 | Register | Both agreement boxes start unchecked; registration answers with the check-your-email notice | onboarding test |
| 5 | Verification mail | The mail arrives in the tester's inbox within the founder's mail window and its link verifies the account. A mail scanner that runs scripts can open the link first: the page then reports a failure although the account is verified; record it | onboarding test (capture only) |
| 6 | Sign in | Password and Google sign-in land on the dashboard showing the tester's own address | onboarding and Google tests |
| 7 | Complimentary Pro | The account shows Pro on the dashboard, in Settings and in usage; Settings offers no checkout and no failing billing button | matrix and grant tests |
| 8 | Search and filing | A covered company's filing page loads | — |
| 9 | Cached summary | A filing with a stored summary renders it at once | matrix test (cached read) |
| 10 | Fresh summary | A filing without one generates to completion | matrix test |
| 11 | Ask this Filing | A fourth question in the month answers with cited passages | matrix test |
| 12 | Multi-Period Analysis | Ten annual periods render and the narrative completes | matrix test (gate only) |
| 13 | Exports | The summary PDF and CSV and the analysis Excel workbook download and open | matrix test (Excel: gate only) |
| 14 | Watchlist and alerts | A company is added; hourly filing and 8-K alerts can be switched on; more than three earnings-day alerts are allowed | matrix test |
| 15 | An alert arrives | One filing or 8-K alert reaches the tester's inbox | — (sends real mail; needs approval) |
| 16 | Text feedback | It appears in `/admin/feedback` with the tester's address | feedback test |
| 17 | Screenshot feedback | Only once screenshots are enabled: the report and its image appear in `/admin/feedback` | feedback test |
| 18 | Triage | The administrator marks it triaged | feedback test |
| 19 | Sign out, reset, sign in | The reset mail arrives; the old password fails; the new one works | reset test |
| 20 | Export | Settings → export downloads the tester's data with their agreement and feedback | feedback test |
| 21 | Cross-account | Signed in as one tester, the other's saved summaries, watchlist and screenshots cannot be reached | cross-account test |
| 22 | Unusable invitations | A used, revoked and expired link each show a page the tester can act on | invalid-invitation test (status only) |
| 23 | Deletion | A disposable tester account deletes itself; its session ends; its screenshot cannot be opened at once and its object is gone after the next hourly cleanup run | feedback test |

A stale tab must never change the credentials of an account other than the one it shows. Before any tester is
admitted, the auth repair for that case carries its own two-account tests (one target with a password, one
social-only), and the founder rehearsal repeats it by hand: sign in as one account, sign in as the other in a new
tab, then submit the first tab's password form. The server refuses, and neither account changes.

## 4. Pro capabilities: pass and fail

The beta grants what the pricing page sells as Pro (`frontend/features/marketing/components/PricingSection.tsx`,
`frontend/lib/planLimits.ts`). Each row passes only when every part of its pass column holds for a complimentary
tester. `CAPABILITY_MATRIX` in the journey test holds the same list to `backend/app/services/entitlements.py`.

| Capability | Passes when | Fails when |
| --- | --- | --- |
| Unlimited summaries (fair-use ceiling 300 a month) | A sixth fresh summary in the month generates | Any upgrade prompt or Free allowance message |
| Ask this Filing | Questions past the Free three answer, with cited passages | The free-question limit or an upgrade prompt |
| Multi-Period Analysis | Dataset, charts and narrative for ten annual periods | A plan refusal, or an empty dataset for a covered company |
| PDF, CSV and Excel exports | Each file downloads and opens with the filing's figures | A plan refusal or an empty file |
| Hourly filing alerts and 8-K alerts | Both switches stay on after saving, and an alert arrives | A switch reverting to off, or no alert after a matching filing |
| Earnings-day alerts beyond three | A fourth company's alert switches on | The Free limit message |
| Watchlist | Unlimited on both plans | — |
| Priority support | The support inbox answers a tester within the window the founder sets | No answer; nothing machine-checks this row |

Dormant flags stay off for the beta unless they pass their own acceptance: `ENABLE_SECTION_CHANGES` (the pricing
page lists the Change Report for both plans), `REVERSE_TRIAL_ENABLED` (global, not targeted, and with no revoke
before its end), and the forward-looking entitlements `history_retention_days` and `priority_model`, which
nothing enforces.

## 5. Operational acceptance

Read before admission, after the founder rehearsal, and at each observation point of section 6.

| Signal | Source | Concern for the beta |
| --- | --- | --- |
| Serving shape | `describe-service` sizing lines | Configured inputs only (instances, concurrency, CPU, memory, pool); not measured load |
| API latency and errors, queue age, SQL connections | Ops `capacity-readout` (read-only, bounded) | Observed aggregates; a partial read is a floor, never zero |
| Pool reserve | `database.checked_out` from `GET /metrics` (administrator); [thresholds](../OPERATIONS.md#monitoring-alerts-suggested-thresholds) | The deployed pool has no overflow |
| SEC throttling | The SEC breaker in `/health/detailed`; `logs-probe` | An open breaker stops fresh summaries and analyses |
| Model cost and timeouts | The DeepSeek balance readout; `ai_call` log lines ([telemetry](../OPERATIONS.md#ai-call-telemetry-ai_call--ai_summary-log-lines)) | Spend against the founder's daily limit |
| Account mail | Inbox arrival time at each step 5 and 19; worker logs `email NOT sent` and `(nothing sent)` ([account mail](../OPERATIONS.md#account-mail-f60)) | Account mail waits behind the single task worker's current task |
| Job freshness | Ops `describe-jobs`; scheduled job outcomes | Alerts depend on the hourly filing scan |
| Errors | Sentry, filtered to the serving `SENTRY_RELEASE`; `logs-probe` start lines per revision | Every revision reports under its own release |
| Funnel | PostHog closed-beta events from consenting testers | Headless and unconsented sessions are absent by design |
| Backups | The newest monthly SQL export run; managed backup and point-in-time settings read by the founder | The tolerated loss window must be set before testers create data; the last restore proof predates 17 of the applied migrations |
| Alerts | The alert policies and Sentry alert rules that exist, and a test notification someone received | Without one, the daily smoke issue is the only automated signal, so an outage can go unseen for a day |

Fresh summaries are generated inside the API request on the serving architecture; durable summary generation is
not active, and the beta does not need it activated to meet its load. They share the API's CPU, its four-connection
pool and its event loop with sign-in, feedback and registration mail, while reset and resend mail wait behind the
single task worker's current task. Six first-time generations of large filings at once leave most of them a
lower-quality excerpt that is stored for good (E77 in `tasks/todo.md`), so the first wave's observation reads the
capacity readout around its busiest hour. Nothing in code caps
daily model spend: the provider balance is prepaid and read by hand, and running it out stops summaries, Ask this
Filing and Multi-Period Analysis for every tester. A rehearsal of the durable path, or a load run against an
isolated environment, needs its own approved budget.

## 6. Staged admission

1. **Founder rehearsal.** The founder runs section 3 end to end with founder-controlled accounts only, on the
   identities of section 1. Any failed step stops the programme until it is fixed and re-run.
2. **First wave: three testers.** Mint three address-bound invitations under one cohort label; deliver them;
   observe for 24 to 48 hours, reading section 5 at least twice a day and the feedback inbox daily.
3. **Second wave: the remaining testers,** only once the first wave meets every exit condition below, under a new
   cohort label.

Each wave exits when no stop condition has occurred, every first-wave tester has signed in and holds Pro, and the
feedback and support inboxes are answered. Stop admitting, and use section 7, on any of these:

- a tester cannot sign in or reach their account;
- a tester without Pro, or a Pro surface refusing a complimentary tester;
- any access to another account's data;
- known wrong data shown without its qualification;
- lost feedback or screenshots;
- stalled mail, alerts or queues;
- an error rate, cost or capacity reading beyond the limits the founder set before the wave.

## 7. Rollback levers

Each lever stops one thing and keeps sign-in, granted rights, data export, deletion and cleanup. Every lever is
a live action that needs the founder's approval.

| Lever | How | Stops | Keeps | Proof |
| --- | --- | --- | --- | --- |
| Pause a wave's invitations | `/admin/invites`: revoke each pending invitation of the cohort | New registrations with those links | Admitted testers, their sessions, Pro and data | `test_pausing_invitations_keeps_existing_testers_signed_in_and_their_rights` |
| Close all new accounts | `LEGAL_COLLECTION_ENABLED=false` on the API service | Every mint, re-send and registration answers 503 | Existing accounts, sessions, sign-in, linking, Pro, export and deletion; waiting invitations stay usable for a reopening | `test_closing_collection_stops_new_accounts_and_keeps_admitted_testers`; `tests/unit/test_account_agreement.py` (closed collection keeps password and social sign-in) |
| Pause new summaries | `SUMMARY_NEW_JOBS_PAUSED=true` on the API service and the pregenerate job | New summary generation | Stored summaries, sign-in, feedback; it does not stop Ask this Filing or Multi-Period Analysis, which have no server-side switch | `test_pausing_new_summaries_keeps_stored_ones_and_the_rest_of_the_account` |
| Revoke one tester's Pro | The complimentary-access operation's revoke | That account's Pro surfaces | The account, its session, its beta tag and its data | `test_a_grant_and_its_revocation_reach_only_the_account_they_name` |
| Switch screenshots off | Ops `feedback-media-disable-apply`, approved for that run; it is refused while a `main` push run is in progress or queued | New screenshot uploads (the draft is kept) | Text feedback, reading and cleaning up existing screenshots | `test_switching_screenshots_off_keeps_text_feedback_and_cleanup` |
| Hide the feedback launcher | `NEXT_PUBLIC_ENABLE_FEEDBACK_WIDGET=false` on Vercel, then a redeploy | The whole launcher, text feedback included | Everything else | — |
| Suspend one tester | No route exists; a direct database write of `users.is_active=false` | That account's sign-in | Its data | — |
| Roll back the API | Ops `rollback-traffic`, then a revert, after the account-mail queue drains ([account mail](../OPERATIONS.md#account-mail-f60)) | The current revision | The database | — |

Switching screenshots off while a tester has a screenshot draft open can leave that draft unable to send until
the page is reloaded; tell first-wave testers to reload if sending fails, until the feedback form recovers on its
own.

A traffic rollback moves only the API service, and an environment switch belongs to a revision: moving traffic to
an older revision restores that revision's own `LEGAL_*`, `FEEDBACK_MEDIA_*` and `SUMMARY_NEW_JOBS_PAUSED` values,
and a switch changed while traffic is pinned lands on a revision that serves nothing. Re-read the live answers of
section 1 after any rollback.

A code rollback never crosses a migration blindly: additive migrations stay applied, so the older revision must
still run against the newer schema. Read the migration line of every release since the target before moving
traffic.

## 8. Operator inputs

Before the founder rehearsal the founder supplies, outside this repository where private:

- the public operator notice (`LEGAL_OPERATOR_*`) and the decision to publish it and open collection;
- what testers are told and agree to: the beta's duration, that feedback text (and its hashed network address) is
  kept without the account after deletion while screenshots are deleted, screenshot retention (180 days at most),
  and the support channel;
- the roster and the two cohort labels;
- the beta's end and review dates, and what complimentary access becomes at the end;
- the daily model spend limit, the error and capacity limits of section 6, the mail arrival window of section 3 and the
  support answer window.

## 9. Private cohort tracker

Keep this table only in the founder's private store, keyed by a tester code (`T01` to `T20`) with the mapping to
people held separately. Never commit a filled copy, a name or an address.

| Code | Wave | Invitation minted | Delivered | Registered | Verified | Pro granted | First feedback | Issues | Pro revoked | Closed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | 1 | | | | | | | | | |
