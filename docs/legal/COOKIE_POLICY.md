# EarningsNerd — Cookie Policy

**Last updated: [DATE] · Version 1.0**

> ⚠️ **Template — not legal advice.** Drafted from the application's actual cookie/storage usage.
> Review with a qualified lawyer and complete the `[bracketed]` placeholders before publishing.
> Re-verify the cookie tables if the analytics or auth setup changes.

This Cookie Policy explains how **EarningsNerd** uses cookies and similar technologies (local
storage) on our website and web app. It supplements our **[Privacy Policy](./PRIVACY_POLICY.md)**.

## 1. What are cookies?

Cookies are small files stored on your device; "local storage" is a similar browser mechanism. They
can be **strictly necessary** (needed to run the site) or **optional** (e.g., analytics), and
**first-party** (set by us) or **third-party** (set by a provider).

## 2. Your choices

When you first visit, our **consent banner** lets you **Accept all**, **Reject all**, or
**Customize** your choice. **Non-essential (analytics) technologies do not load until you consent**,
and we honour your browser's **"Do Not Track"** signal (treating it as essential-only). You can
change your choice at any time via the cookie settings link, and **session recording is strictly
opt-in**. Strictly necessary cookies cannot be switched off, as the site will not work without them.

## 3. Strictly necessary cookies

Required for login, security, and core functionality. Set by us (first-party), `HttpOnly`, `Secure`
(in production), `SameSite=Lax`:

| Name | Purpose | Duration |
|---|---|---|
| `earningsnerd_access_token` | Keeps you signed in (short-lived access token) | ~30 minutes |
| `earningsnerd_refresh_token` | Renews your session securely (scoped to `/api/auth`) | ~30 days |
| `en_session` | Indicates an active session | ~30 days |
| `oauth_state` | Protects social sign-in against CSRF | A few minutes (during sign-in) |

We also use **local storage** for strictly functional purposes:

| Key | Purpose |
|---|---|
| `cookie_consent` | Remembers your cookie choices |
| `en_session_active` | Advisory flag that a session is active (not a credential) |

## 4. Analytics cookies (optional — consent required)

Loaded **only if you accept analytics**. They help us understand product usage and improve the
Service:

| Provider | Purpose | Type | Notes |
|---|---|---|---|
| **PostHog** | Product analytics (page/feature usage); optional session recording | First/third-party cookies + local storage | Loads only after consent; session recording is separately opt-in and masks all input fields and passwords |
| **Vercel Analytics** | Aggregate, privacy-friendly traffic measurement | **Cookieless** | Does not use cookies to identify you |
| **Sentry** | Error/performance diagnostics | No cookies | Used to keep the Service reliable |

We do **not** use advertising or cross-site tracking cookies, and we do not sell your data.

## 5. Managing cookies

Besides our banner, you can control cookies through your **browser settings** (block or delete
cookies). Doing so may affect how the Service works. Mobile apps generally use secure device storage
rather than browser cookies for sign-in.

## 6. Changes & contact

We may update this policy; material changes will be posted with a new date. Questions:
**privacy@earningsnerd.io**.

---

### Open items
1. Complete the effective date.
2. Re-verify the exact cookie names/durations against production before publishing, and keep this in
   sync with the consent banner.
3. Confirm PostHog cookie names/durations from your PostHog configuration if you want them itemised.
