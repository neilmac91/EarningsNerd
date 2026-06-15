# Frontend Auth Design Plan — for approval

**Status: PROPOSAL (awaiting sign-off before implementation).**

## Locked decisions (from product owner)
- **Architecture:** split-screen immersive pages (dedicated routes, branded value pane)
- **Visual ambition:** refined minimal + tasteful motion (Stripe/Linear grade)
- **Scope:** 6 auth pages · header auth state + user menu · email-verification nudge UX · Apple/Google button compliance
- **Social login:** social-first (Apple + Google prominent; email behind progressive disclosure)

## Design language (inherited, unchanged)
Mint `#10B981` accent on a dark-first theme · Inter · `rounded-2xl` cards / `rounded-lg`
controls · mint glow shadows · existing `fade-up` (0.6s) + `float` keyframes · React Query
(`getCurrentUserSafe`) for auth state. **No new animation/UI dependency** — extend
`globals.css` + Tailwind keyframes only.

---

## A. The split-screen shell — `components/auth/AuthShell.tsx`
A shared wrapper (not a route-group move — keeps existing routes deep-linkable, low impact).

```
grid lg:grid-cols-2  min-h-screen
├─ LEFT  (form pane)   bg-background, form centered, max-w-[400px]
└─ RIGHT (brand pane)  hidden lg:flex · bg-hero-gradient + mint radial glow
                       • product-value showcase (filing → structured summary visual)
                       • trust signals: "SEC EDGAR · XBRL-verified"
                       • slow `float` on the showcase card, `fade-up` on load
```
Mobile: brand pane collapses; a compact logo + one-line value prop sits above the form.
Each of the 6 pages renders its content into the left pane; the right pane is constant.

## B. Social-first form composition (login + register)
1. Logo + heading ("Welcome back" / "Create your account")
2. **Continue with Apple** — full width, HIG-compliant
3. **Continue with Google** — full width, brand-compliant
4. Divider: "or continue with email"
5. **Collapsed email disclosure** — a "Use email instead" button expands (max-height + opacity
   transition) into email/password fields. Honors the social-first decision; trivially tunable
   back to always-visible if conversion data says so.

Polish: password **show/hide** toggle · `active:scale-[0.98]` press feedback · existing focus
rings · `Loader2` spinners · `autocomplete` (`email`, `current-password`, `new-password`) ·
errors/success via `StateCard` (**new `success` variant** added) with `aria-live`.

## C. Button compliance (Apple review-safe)
- `components/auth/AppleSignInButton.tsx` — Apple logo, "Continue with Apple", black-on-white
  (light) / white-on-black (dark), HIG min-height & radius, never smaller than sibling buttons.
- `components/auth/GoogleSignInButton.tsx` — official multicolor "G", neutral surface, correct
  padding, equal prominence (satisfies Google's guidance).

## D. Header auth state + user menu — `components/UserMenu.tsx`
- **Logged out:** keep "Log In" + "Get Started" (mint).
- **Logged in:** avatar button (initials in a mint-tinted circle) → dropdown: name/email header ·
  Dashboard · Watchlist · Settings · divider · Log out.
- **Unverified:** amber dot on the avatar + "Verify email" pinned at the top of the menu.
- Accessible custom dropdown (click-outside, Escape, `aria-*`, focus return) — no new dependency.

## E. Email-verification nudge UX (because `email_verified` gates AI gen + checkout)
- **Thin global banner** (logged-in + unverified): "Verify your email to generate summaries —
  Resend link." Session-dismissible; amber accent; calls `resendVerification`.
- **Graceful 403 intercept:** when an unverified user hits Generate / Subscribe, the backend 403
  ("Please verify your email…") renders a friendly prompt — "We sent a link to {email}.
  [Resend] [I've verified — refresh]" — instead of a raw error.
- **Post-verify polish:** verify-email success gets a tasteful checkmark pop, then auto-redirect.

## F. The 6 pages, redesigned (all in the shell)
- **login / register:** social-first as in §B.
- **check-email:** animated mail icon (subtle float) · **resend cooldown timer** ("Resend in 30s").
- **verify-email:** loading → success (checkmark pop) → error (with resend).
- **forgot-password:** email → success confirmation (anti-enumeration copy preserved verbatim).
- **reset-password:** lightweight **password-strength meter** (length/entropy heuristic, no heavy
  lib) · show/hide · confirm-match.

## G. Motion (tasteful, reduced-motion-safe)
Entrance via existing `fade-up` with stagger · button press `active:scale-[0.98]` · disclosure
expand (max-height + opacity) · brand-pane `float` + mint glow · new checkmark-pop keyframe ·
all gated behind `prefers-reduced-motion`.

## H. Accessibility / quality bar
Full keyboard nav + visible focus · `aria-live` form feedback · AA contrast on text · correct
`autocomplete`/`inputmode` · Enter-to-submit · double-submit lockout. Validated against the
existing Vitest + Playwright suites; no regressions to current 30 frontend tests.

---

## Build increments (after approval; Apple button wires up in Increment 4)
1. **Shell + primitives:** `AuthShell`, brand pane, `AppleSignInButton`/`GoogleSignInButton`,
   `StateCard` success variant, password show/hide; refactor login + register.
2. **Remaining 4 pages** into the shell (cooldown, checkmark pop, strength meter).
3. **Header `UserMenu`** + logged-in state + verify-dot.
4. **Verification nudge system:** banner + 403-intercept prompts + post-verify polish.

Each increment ships independently, committed + pushed, with tests green.
