# An SDK that captures nothing can still store: identify only through the consent facade, and forget the account wherever the reader has none

Date: 2026-11-01 · Area: frontend / telemetry

**Context.** #1881 restarted browser PostHog after #1552's consent guard had kept it off. The guard and the consent
choice stop what posthog-js captures and sends, but its reviews found what it still stores:

- `posthog.identify()` writes the account id to PostHog's cookie and local storage even while capturing is off. The
  dashboard and login pages identified the reader whatever the choice, so a refusal in the same tab still left the
  account id there.
- posthog-js keeps an identified reader's id across page loads until `reset()`. Only the dashboard's Log out called
  it. The account menu's and the mobile menu's Log out, "Log out of all devices", an account deletion and a lost
  session left the reader identified. With analytics allowed, the signed-out browser's events, and the next reader's on
  a shared device, were captured under the account id. After a deletion, the browser kept capturing under the id the
  backend had just deleted. The consent clause ties statistics to an account id while the reader is logged in
  (`frontend/lib/consentCopy.ts`).
- A browser that logged out while PostHog was not loaded kept the id, and PostHog resumed under it on the next allow.

**Rule.**

- Tie an account to the SDK only through one consent facade (`frontend/lib/analytics.ts`), which identifies only while
  analytics is allowed. App code never calls `identify` or `alias` on a client, nor sets the person by key
  (`bootstrap.distinctID`, `register({ distinct_id })`).
- Forget the account at the one place that sees every way it goes away, not at each control that ends a session.
  `frontend/hooks/usePostHogUserIdentification.ts` calls `analytics.forgetAccount()` for every known guest, and that
  resets an identity the SDK still holds.
- Reset an identity kept from an earlier visit before the SDK's first request, when the browser has no session. The
  provider (`frontend/app/posthog-provider.tsx`) does it in `loaded`, which posthog-js runs before its remote
  configuration and flags.
- Check what an SDK writes, not only what it sends.

**Gate.** Partly gated, for posthog-js.

- `frontend/tests/unit/posthogShippedMembers.spec.ts` fails app code (outside `tests/`) that ties an account anywhere
  but `lib/analytics.ts`: an `identify` or `alias` read off a receiver not bound to that module's import (called,
  passed or bound), one destructured, or a key that sets the person.
- `frontend/tests/unit/posthogConsentGuard.spec.tsx`, on real clients:
  - an account is identified only while analytics is allowed;
  - `forgetAccount` resets a held identity and leaves an anonymous one alone;
  - a browser without a session that loads PostHog again starts on a fresh identity, and none of its requests carries
    the old one;
  - a browser whose session goes on keeps its identity.
- `frontend/tests/unit/posthog-user-identification.spec.tsx` pins that the hook asks to forget for every guest, again
  once PostHog is ready, and that it identifies the same account again after a logout and a login.

Review-checked:

- an `identify` reached through a name assembled at run time (planted as a gap in the scan);
- a file that handles a PostHog client without naming posthog-js;
- a session that ends without the account query reading no account. Every logout control and a lost session write
  that null today.

What PostHog keeps in storage while analytics is refused is the founder's decision (`tasks/todo.md` F70 item 4).

**Evidence.** Pull request #1881's third and fifth review rounds (2026-11-01) found each gap, by probes on the real
SDK. Its body records the mutation proofs: the guard spec fails with the provider's reset or the identify gate removed,
and the hook spec fails with the hook's forgetting removed.
