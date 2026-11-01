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
- An account deletion and "Log out of all devices" clear React Query's cache, and a cleared cache tells no observer,
  so a hook that waited for a guest never saw those accounts go.
- `reset()` works only on a loaded client. A browser that logged out while PostHog was not loaded kept the id, and
  PostHog resumed under it on the next allow, even when another account had signed in there by then.
- posthog-js switches an identified person to another id without a fresh identity, so a second account on the same
  browser was tied to the first one's device.

**Rule.**

- Tie an account to the SDK only through one consent facade (`frontend/lib/analytics.ts`), which identifies only while
  analytics is allowed. App code never calls `identify`, `alias` or `setIdentity` on a client, nor sets the person by
  key (`bootstrap.distinctID`, `identity_distinct_id`, `register({ distinct_id })`). Before it identifies an account,
  the facade resets an identity the client holds for another one.
- Forget the account at the one place that sees every way it goes away, not at each control that ends a session.
  `frontend/hooks/usePostHogUserIdentification.ts` calls `analytics.forgetAccount()` for every known guest and when the
  current-user query leaves the cache. Forgetting resets a held identity with a new device id. Where the SDK has not
  loaded, it leaves a flag that names no account (`frontend/lib/posthogIdentity.ts`), and only where the SDK has
  stored something, so a browser that never allowed analytics stores nothing for it.
- Reset an identity kept from an earlier visit before the SDK's first request, when that flag is set (whoever's session
  it is now) or the browser has no session. The provider (`frontend/app/posthog-provider.tsx`) does it in `loaded`,
  which posthog-js runs before its remote configuration and flags.
- Check what an SDK writes, not only what it sends.

**Gate.** Partly gated, for posthog-js.

- `frontend/tests/unit/posthogShippedMembers.spec.ts` fails app code (outside `tests/`) that ties an account anywhere
  but `lib/analytics.ts`: an identity member read off a receiver not bound to that module's import (called, passed or
  bound), or destructured; a key that sets the person, in an object or written by assignment; either kind by a bare
  string; another declaration of a name bound to the facade; and any of these in code held in a string.
- `frontend/tests/unit/posthogConsentGuard.spec.tsx`, on real clients:
  - an account is identified only while analytics is allowed;
  - `forgetAccount` resets a held identity with a new device id, clears Sentry's user, keeps the visitor's choice, and
    leaves an anonymous identity alone;
  - a browser without a session that loads PostHog again starts on a fresh identity, and none of its requests carries
    the old one;
  - so does a browser whose account went while PostHog was off, though another account's session is active by then;
    the flag is left only where PostHog has stored something;
  - an anonymous identity is kept across a load, and one kept while the browser's session goes on stays;
  - another account starts on a fresh identity and is identified afresh.
- `frontend/tests/unit/posthog-user-identification.spec.tsx` pins that the hook asks to forget for every guest, again
  once PostHog is ready, and when the cache is cleared, and that it identifies the same account again after a logout
  and a login.

Review-checked:

- an `identify` reached through a name assembled at run time, or held more than two strings deep (planted as gaps in
  the scan);
- a file that handles a PostHog client without naming posthog-js;
- a session that ends without the account query reading no account or leaving the cache. Every logout control and a
  lost session write that null today; an account deletion and "Log out of all devices" clear the cache;
- local storage that reads but cannot be written (a full quota), which loses the flag: the provider then resets only
  for a browser without a session, and the facade resets before the next account is identified.

What PostHog keeps in storage while analytics is refused is the founder's decision (`tasks/todo.md` F70 item 4).

**Evidence.** Pull request #1881's third, fifth and sixth review rounds (2026-11-01) found each gap, by probes on the
real SDK. Its body records the mutation proofs: the guard spec fails with the provider's reset, the flag, the reset
before a second account or the identify gate removed, and the hook spec fails with the hook's forgetting or its cache
subscription removed.
