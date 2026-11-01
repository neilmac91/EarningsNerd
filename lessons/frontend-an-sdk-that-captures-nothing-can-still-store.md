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
- A session can end while no page is open: a refresh token lapses, or "Log out of all devices" or a deletion runs on
  another device. The app's session marker still read as a session at the next load, so PostHog started under the old
  id and that page's flags request and first `$pageview` carried it before the app's read of the session found no
  account.
- posthog-js switches an identified person to another id without a fresh identity, so a second account on the same
  browser was tied to the first one's device.

**Rule.**

- Tie an account to the SDK only through one consent facade (`frontend/lib/analytics.ts`), which identifies only while
  analytics is allowed. App code never calls `identify`, `alias` or `setIdentity` on a client, nor sets the person by
  key (`bootstrap.distinctID`, `identity_distinct_id`, `register({ distinct_id })`). Before it identifies an account,
  the facade resets an identity the client holds for another one.
- Forget the account at the one place that sees every way it goes away, not at each control that ends a session.
  `frontend/hooks/usePostHogUserIdentification.ts` calls `analytics.forgetAccount()` for every known guest and when the
  current-user query leaves the cache. Forgetting resets a held identity with a new device id.
- Trust a kept identity only while the browser holds a session and the server has confirmed it. A client-side session
  marker cannot tell a live session from one that ended elsewhere, so for a browser with one, the provider
  (`frontend/app/posthog-provider.tsx`) starts the SDK only after the app's read of the session has settled
  (`frontend/lib/posthogIdentity.ts`). In `loaded`, which posthog-js runs before its remote configuration and flags, it
  resets a kept identity unless the latest read confirms it. A read the cache drops (an account deletion, "Log out of
  all devices") is reported as no account, so it cannot be trusted later on the page. A browser without a marker
  starts at once and resets any identity kept.
- A client that cannot forget an account fails closed rather than capture under it.
- Check what an SDK writes, not only what it sends.

**Gate.** Partly gated, for posthog-js.

- `frontend/tests/unit/posthogShippedMembers.spec.ts` fails app code (outside `tests/`) that ties an account anywhere
  but `lib/analytics.ts`: an identity member read off a receiver not bound to that module's import (called, passed or
  bound), or destructured in a declaration or an assignment; a key that sets the person, in an object (a getter or
  method too), as a class field, or written by an assignment, a destructuring pattern, a loop head or an increment;
  either kind by a bare string; another declaration of a name bound to the facade; and any of these in code held in a
  string.
- `frontend/tests/unit/posthogConsentGuard.spec.tsx`, on real clients:
  - an account is identified only while analytics is allowed;
  - `forgetAccount` resets a held identity with a new device id, clears Sentry's user, keeps the visitor's choice
    (an allow and a refusal alike, the refusal stored again for every tab), never throws, turns off a client whose
    reset throws, and leaves an anonymous identity alone;
  - an anonymous visitor is identified in place, so the events before the login join the account;
  - a browser without a session that loads PostHog again starts on a fresh identity, and none of its requests carries
    the old one;
  - so does a browser whose session ended while no page was open, and one now holding another account's session;
  - for a browser with a session, PostHog starts only after the app's read of it, even when the allow was stored before
    the page; a refusal while the read is pending keeps it off, and a page that unmounts while it is pending never
    starts;
  - a read the page ended before PostHog started (a deletion's cleared cache) and a read made before the session marker
    went are not trusted;
  - an identity the read confirms is kept, an anonymous identity is kept across a load, and forgetting while PostHog is
    not loaded stores nothing;
  - another account starts on a fresh identity and is identified afresh.
- `frontend/tests/unit/posthog-user-identification.spec.tsx` pins that the hook asks to forget for every guest, again
  once PostHog is ready, and when the cache is cleared; that it reports each settled read of the session on the same
  page (an account, no account after a logout, no account after a failed refetch or a cache clear, nothing while
  pending); and that it identifies the same account again after a logout and a login, or a cache clear, though another
  reader re-reads the account first.

Review-checked:

- an `identify` reached through a name assembled at run time, or held more than two strings deep (planted as gaps in
  the scan);
- a file that handles a PostHog client without naming posthog-js;
- a session that ends without the account query reading no account or leaving the cache. Every logout control and a
  lost session write that null today; an account deletion and "Log out of all devices" clear the cache;
- a browser whose storage blocks the session marker. It keeps no consent choice either, so PostHog starts only on an
  allow made on the page, and an allow made before the app's read of the session answers resets a kept identity (a new
  anonymous id and device id), which costs statistics and keeps nothing of an account;
- a session read that never settles (a refresh that never answers, or offline): PostHog stays off for that page.

What PostHog keeps in storage while analytics is refused is the founder's decision (`tasks/todo.md` F70 item 4).

**Evidence.** Pull request #1881's third, fifth, sixth and seventh review rounds (2026-11-01) found each gap, by probes
on the real SDK and on the production bundle. Its body records the mutation proofs: the guard spec fails with the
provider's reset, its wait for the session read, the reset before a second account or the identify gate removed, and
the hook spec fails with the hook's forgetting, its cache subscription or its read report removed.
