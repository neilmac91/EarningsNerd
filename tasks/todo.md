# Task: Free Copilot "taste" — 3 lifetime questions (roadmap item 2.2)

Let Free users sample the Pro "Ask this Filing" Copilot a few times before the upsell, so the
grounded-citation magic drives conversion. Unblocked by 2.1 (cost telemetry), and cost-guarded:
each free-taste answer is tagged in the cost event so free-taste spend is isolatable.

## Decisions (per roadmap "3 lifetime questions" + simplicity)
- **3 lifetime free questions, GLOBAL pool** (not locked to one filing). Simplest + cleanest UX.
  (Roadmap says "on first filing"; chose global over per-filing scoping — flagged in the PR as a
  one-column follow-up if a deeper single-filing taste is preferred.)
- **Lifetime counter lives on `User`** (`copilot_free_taste_used`), NOT `user_usage` (which is
  monthly — wrong home for a lifetime value; the recon's suggestion corrected here).
- **Entitlements SSoT extension:** `Entitlements.copilot_free_taste` (3 Free / 0 Pro) +
  `can_use_copilot(user)`.

## Backend
- [x] `User.copilot_free_taste_used` column (`server_default "0"`, NOT NULL) + manual migration
      `20260629_user_copilot_free_taste.sql` (create_all won't ALTER existing `users`).
- [x] `entitlements.py`: `copilot_free_taste` field (Free=3, Pro=0) + `can_use_copilot()` helper.
- [x] `dependencies.py`: `require_copilot_or_taste` — Pro OR Free-with-taste; else 403 → upsell.
- [x] `summaries.py` ask-stream: swap the dep; the monthly 429 cap is now Pro-only; meter on
      completion → Free decrements the lifetime counter, Pro increments monthly `qa_count`.
- [x] `subscription_service.py`: `increment_user_copilot_free_taste(user_id, db)`.
- [x] Cost guard: `_emit_copilot_cost_best_effort` + `capture_copilot_inference` now tag
      `is_free_taste` so free-taste $ is isolatable in PostHog (the "guard cost" of 2.2).
- [x] `subscriptions.py` `UsageResponse`: `copilot_free_taste_used` + `copilot_free_taste_total`.

## Frontend
- [x] `Usage` type + the usage endpoint already gain the two taste fields.
- [x] `AskCopilotRail`: fetch usage for any authed user; a Free user with taste gets the composer +
      "N of 3 free questions left" pill; on exhaustion the composer disables and an inline upsell
      shows (the conversation stays — not yanked for the teaser). Anonymous / already-exhausted-with-
      no-conversation users still get the teaser. Conservative until usage loads (teaser is the safe
      default), so the composer is never shown to someone out of questions.

## Tests
- [x] backend `test_entitlements.py`: free taste allowance + `can_use_copilot` (0/2 allow, 3/4 deny;
      Pro always). `test_copilot.py`: free-with-taste streams, taste-exhausted 403, a free answer
      decrements the lifetime counter (and leaves monthly `qa_count` at 0).
- [x] frontend `AskCopilotRail.test.tsx`: free-with-taste shows composer + count; exhausted shows
      teaser. Existing "teaser for non-Pro" stays green (default usage carries no taste → teaser).

## Verify
- [x] Backend `py_compile` clean (pytest unavailable locally → the new cases run on CI backend-tests).
- [x] Frontend `npm run typecheck` + `lint --max-warnings 0` clean; vitest 50 files / 230 tests (+2).
- [ ] CI green on the pushed branch; open as a draft PR.

## Founder actions (not code)
- **Apply the migration to prod** (`20260629_user_copilot_free_taste.sql`) before/with deploy.
- Watch the funnel: `copilot_inference_cost{is_free_taste=true}` for spend, and the question→answer
  events for Free users converting after the taste.

## Review
- Surgical + reuse-first: leans on the existing Copilot pipeline, usage endpoint, teaser, and cost
  telemetry — the new logic is one gate, one lifetime counter, one metering branch, one cost tag,
  and the rail's free-user rendering. No change to the Copilot service/tools/prompts; no eval surface.
- Scope flag: global-pool taste chosen over first-filing scoping (stated in the PR for redirect).
