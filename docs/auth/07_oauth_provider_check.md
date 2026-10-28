# OAuth provider check: what a person sees before signing in with Google or Apple (F38)

A checklist for the founder, who alone has the Google Cloud and Apple Developer consoles. It covers the identity a
person sees before an OAuth sign-in (the app name, logo, support contact and policy links) and our sign-in buttons
against each provider's current rules. Source inspection cannot pass this check. The code below says what we send
and draw. The consoles and the live screens are the record, and the checker writes down what they show, on the day,
in the results table at the end.

Scope: a check, not a change. It changes no redirect URI, OAuth credential, login route or consent scope. A
mismatch it finds is recorded and routed, never fixed in a field this page does not hand to the founder (see
[What a mismatch leads to](#what-a-mismatch-leads-to)). Setup is in
[`03_implementation_plan.md`](03_implementation_plan.md) and, for Apple,
[`05_apple_signin_runbook.md`](05_apple_signin_runbook.md).

## What never goes in this file

- No client secret, private key, key ID, team ID, client ID, bundle ID or Services ID value.
- No account email. The support contact is recorded as "set, a role mailbox" or "set, a personal address", never as
  the address.
- No OAuth code or token, and no screenshot of a console page or a signed-in screen. A screenshot of a consent screen
  itself, if one is kept at all, stays outside the repository.

## Which providers to check

A provider is configured when production sets its client ID and the login page renders its button.
- **Google's button** always renders.
- **Apple's button** renders only when the frontend build sets `NEXT_PUBLIC_ENABLE_APPLE_SIGNIN=true`
  (`frontend/lib/featureFlags.ts`, `SocialAuthButtons.tsx`).

If the production login page shows no Apple button, record Apple's live-page and button fields as "not rendered in
this build". Its row stays **Unverified**, whatever the console shows.

## What our code sends and draws (for comparison, not as evidence)

- **The starts**: `GET /api/auth/google` and `/api/auth/apple` redirect to the provider. The POST starts return the
  same URL to a page carrying an invite or signup assent (`frontend/features/auth/components/OAuthStartControl.tsx`;
  the scopes are set in the starts' helpers in `backend/app/routers/auth.py`).
  - Google: scopes `openid email profile`, `prompt=select_account`, so Google shows its account chooser first.
  - Apple: scopes `name email`, `response_mode=form_post`.
- **Google's button** (`GoogleSignInButton.tsx`):
  - label "Continue with Google";
  - a white `#FFFFFF` surface with a 1px `#E5E7EB` border;
  - label ink `#334155` at 14px on a 20px line, weight 500, in the body face: SF Pro on Apple systems, Inter
    elsewhere (the stack puts `-apple-system` first, `frontend/DESIGN_SYSTEM.md` §3), so the face a checker sees
    depends on their device;
  - the four-colour "G" at 18px, 12px from the label;
  - a 12px corner radius and 12px × 16px padding, 46px tall with its border;
  - hover `#F8FAFC`;
  - the same in both themes: it stays white with its light hairline in the dark theme too.
- **Apple's button** (`AppleSignInButton.tsx`):
  - label "Continue with Apple";
  - a black `#000000` surface with white text in the light theme, white with black text in the dark;
  - 14px on a 20px line, weight 600, in the same face as Google's label;
  - the Apple glyph at 18px in the text's colour;
  - the same radius, padding and gap as Google's, 44px tall (it has no border).
- **Both buttons**: the full width of the form, with the brand focus ring. The ring is the one change
  `frontend/DESIGN_SYSTEM.md` §9 allows to a provider's mandated look.
- **The logo to upload** is the founder's own full-resolution app tile, as supplied
  ([the lesson](../../lessons/brand-hand-a-console-the-source-resolution-logo.md)). Upload neither tracked file:
  - `frontend/public/assets/earningsnerd-appicon.png` is a 128 × 128 copy;
  - `earningsnerd-appicon.svg` is a different, rounded tile on a transparent ground, in a format Google's logo
    field does not take.

## Google

In the Google Cloud console, open the project the production `GOOGLE_CLIENT_ID` belongs to. Its consent-screen
settings sit under Google Auth Platform → Branding, or APIs & Services → OAuth consent screen on older consoles.
Record each field as the console names it on the day.

1. **App name**: as entered, and whether it reads "EarningsNerd".
2. **User support email**: set or not, and whether it is a role mailbox.
3. **App logo**: uploaded or not. If it is, check it is the founder's full-resolution tile: view it at the size the
   console shows, and on a phone.
4. **App domain**: the home page, privacy policy and terms links. Record whether each opens the live earningsnerd.io
   page meant for it.
5. **Authorized domains**: record which domains are listed. Change nothing here, since these fields gate the
   redirect URIs.
6. **Publishing and verification status**: as the console states it. Google shows a new name or logo only once the
   app is verified, so an unverified app's screen can show a placeholder even when the console is right.
7. **The live screens**: in a private window, use "Continue with Google" on the production login page.
   - **The account chooser** comes first (`prompt=select_account`). Record the app name it shows.
   - **The consent screen**, which carries the logo, support and policy links, appears only after an account is
     chosen. Choose an account that has never signed in to EarningsNerd, since Google can skip the screen for one
     that has. Read the screen, then press **Cancel**: our callback answers Cancel as a declined sign-in and writes
     nothing.
   - A field the screens did not show is recorded as "not shown at this step", not as a mismatch.
8. **The button against Google's branding guideline**
   (<https://developers.google.com/identity/branding-guidelines>, read on the day): the surface, border, label font,
   size, weight and colour, the "G" and its size, the corner radius, the height and the allowed labels, in both
   themes. Record each difference as a value pair, ours then the guideline's.

## Apple

Only if Apple is configured (above). In Apple Developer → Certificates, Identifiers & Profiles, open the Services
ID the production `APPLE_CLIENT_ID` names. Open nothing that shows the key.

The runbook set these values:
- the App ID's description "EarningsNerd" and the Services ID's "EarningsNerd Web";
- the Services ID's Primary App ID, the App ID "EarningsNerd";
- the domain `api.earningsnerd.io`;
- the return URL `https://api.earningsnerd.io/api/auth/apple/callback`.

Compare against those.

1. **Domains and return URLs**: record whether the production domain and return URL above are listed. Change
   nothing.
2. **Sign in with Apple** on the App ID: enabled or not. Record whether the Services ID's Primary App ID is that
   App ID.
3. **The live page**: in a private window, use "Continue with Apple" on the production login page and stop at
   Apple's page. Record the name and icon it shows, and which description it matches: "EarningsNerd" or
   "EarningsNerd Web". The choice to hide the email appears only after signing in to Apple, so record it as "not
   shown at this step" unless the checker signs in with an Apple ID that has never used EarningsNerd and cancels
   before continuing.
4. **The button against Apple's Human Interface Guidelines for Sign in with Apple**
   (<https://developer.apple.com/design/human-interface-guidelines/sign-in-with-apple>, read on the day): the
   allowed titles ("Continue with Apple" among them or not), the black and white styles, the logo's size and
   placement, and the minimum height and corner radius. Record differences as value pairs, as for Google.

## Results

One row per provider per check. The checker sends the filled rows to A, who records them here in a PR. Results are
sanitized as above.

| Provider | Checked on (UTC date) | By | App name shown | Logo shown | Support contact | Policy links | Console status | Button vs guideline | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Google | | | | | | | | | Unverified |
| Apple | | | | | | | | | Unverified |

Each Result is one of:
- **Pass**: the screens show EarningsNerd's identity, and the button meets the provider's current rules.
- **Pending verification**: the console is right, but the screen shows a placeholder until Google verifies the app.
- **Mismatch**: name the field.
- **Unverified**: the console could not be opened, or the provider is not configured. Say which.

F38 closes when each configured provider's row is Pass, or Unverified or Pending verification with its reason, and
any button value pairs have gone to the design owner. A cleanup in a provider console keeps its own later founder
checkpoint.

## What a mismatch leads to

- **A console identity field** (the app name, logo, support contact or policy links): the founder corrects it in the
  console. A logo is uploaded as the lesson above says.
- **An authorized domain, an Apple domain or a return URL**: report it to the CTO for triage. These fields gate the
  sign-in redirects, so they are not edited during the check.
- **A button value**: the value pairs in the results row are the request to the design owner, who owns
  `frontend/DESIGN_SYSTEM.md` §9, where those values are recorded. A source change to a button is a separate,
  authorized PR. It runs the full frontend gate in `CLAUDE.md` and checks both themes (rule 11). The gates that pin
  the buttons today:
  - `tests/unit/themePairs.spec.ts` (the Google border);
  - `tests/unit/designRules.spec.ts` (the Google exemption);
  - `tests/unit/inlineSvgAllowlist.spec.ts` (both marks);
  - `tests/unit/RegisterForm.spec.tsx`;
  - the exemptions in `eslint.config.mjs`.
- **Anything functional** (a scope, a sign-in that fails): out of scope here. Report it to the CTO for triage.
