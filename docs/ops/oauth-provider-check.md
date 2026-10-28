# OAuth provider check: what a person sees before signing in with Google or Apple (F38)

A checklist for the founder, who alone has the Google Cloud and Apple Developer consoles. It covers the identity a
person sees on each provider's consent screen (the app name, logo, support contact and policy links) and the sign-in
buttons on our pages against each provider's current rules. Source inspection cannot pass this check. The code below
says what we send and draw. The consoles and the live consent screens are the record, and the checker writes down
what they show, on the day, in the results table at the end.

Scope: a check, not a change. It changes no redirect URI, OAuth credential, login route or consent scope. A
mismatch it finds is recorded and triaged, never fixed in a console field it does not name (see
[What a mismatch leads to](#what-a-mismatch-leads-to)). Setup itself is in
[`docs/auth/03_implementation_plan.md`](../auth/03_implementation_plan.md) and, for Apple,
[`docs/auth/05_apple_signin_runbook.md`](../auth/05_apple_signin_runbook.md).

## What never goes in this file

- No client secret, private key, key ID, team ID, client ID or Services ID value.
- No account email: the support contact is recorded as "set, a role mailbox" or "set, a personal address", never
  as the address.
- No OAuth code or token, and no screenshot of a console page or a signed-in screen. A screenshot of the consent
  screen itself is kept outside the repository if at all.

## What our code sends and draws (for comparison, not as evidence)

- **The starts**: `GET /api/auth/google` and `/api/auth/apple` redirect to the provider; the POST starts return the
  same URL to a page carrying an invite or signup assent (`frontend/features/auth/components/OAuthStartControl.tsx`).
  - Google: scopes `openid email profile`, `prompt=select_account`.
  - Apple: scopes `name email`, `response_mode=form_post` (both in the starts' helpers in
    `backend/app/routers/auth.py`).
- **The buttons** (`frontend/features/auth/components/GoogleSignInButton.tsx`, `AppleSignInButton.tsx`):
  - **Google**: label "Continue with Google"; a white surface with the light border hairline; label ink
    `text-slate-700`, `font-medium`, `text-sm`; the four-colour "G" at 18px; hover `bg-slate-50`.
  - **Apple**: label "Continue with Apple"; black surface and white text in the light theme, white and black in the
    dark; `font-semibold`, `text-sm`; the Apple glyph at 18px in the text's colour.
  - **Both**: the full width of the form, the same corner radius and padding, and the brand focus ring. That ring is
    the one change `frontend/DESIGN_SYSTEM.md` §9 allows to a provider's mandated look.
- **The logo to upload**: the founder's full-resolution app tile, as supplied, never a smaller copy
  (`lessons/brand-hand-a-console-the-source-resolution-logo.md`). The tracked vector is
  `frontend/public/assets/earningsnerd-appicon.svg`.

## Google

In the Google Cloud console, open the project the production `GOOGLE_CLIENT_ID` belongs to. Its consent-screen
settings sit under Google Auth Platform → Branding, or APIs & Services → OAuth consent screen on older consoles.
Record each field as the console names it on the day.

1. **App name**: as entered, and whether it reads "EarningsNerd".
2. **User support email**: set or not, and whether it is a role mailbox.
3. **App logo**: uploaded or not. If it is uploaded, check it is the founder's full-resolution tile: open it at
   the size the console shows and on a phone. Google shows a new name or logo only once the app is verified.
4. **App domain**: the home page, privacy policy and terms links. Record whether each opens the live earningsnerd.io
   page meant for it.
5. **Authorized domains**: whether earningsnerd.io is listed.
6. **Publishing and verification status**: as the console states it.
7. **The live consent screen**: in a private window, use "Continue with Google" on the production login page and
   stop at Google's screen without choosing an account. Record the name, the logo or its placeholder, and the
   support and policy links it shows. Then close the window.
8. **The button against Google's branding guideline**
   (<https://developers.google.com/identity/branding-guidelines>, read on the day): the surface, border, label
   font and colour, the "G" and its size, and the allowed labels.
   - Record any difference as a value pair: ours, then the guideline's.
   - `frontend/DESIGN_SYSTEM.md` §9 asks for these values to be recorded there. That file is the design owner's to
     edit, so the values go to them as a request.

## Apple

In Apple Developer → Certificates, Identifiers & Profiles, open the Services ID the production `APPLE_CLIENT_ID`
names. Open nothing that shows the key.

1. **The name the sign-in sheet shows**: record it from the live sheet (step 4), and which console field it
   matches (the Services ID's description, or the primary App ID's name).
2. **Domains and return URLs**: record only whether earningsnerd.io and the production callback are listed. Change
   nothing.
3. **The App ID's Sign in with Apple capability**: enabled or not, and whether the Services ID is grouped with it.
4. **The live sign-in sheet**: in a private window, use "Continue with Apple" on the production login page and stop
   at Apple's sheet. Record the name and icon it shows and whether it offers to hide the email. Then close it.
5. **The button against Apple's Human Interface Guidelines for Sign in with Apple** (read on the day): the allowed
   titles ("Continue with Apple" among them or not), the black and white styles, the logo's size and placement,
   and the minimum height and corner radius. Record differences as value pairs, as for Google.

## Results

Copy one row per provider per check. A provider whose console the checker could not open is recorded as
**Unverified**, never as passed.

| Provider | Checked on (UTC date) | By | App name shown | Logo shown | Support contact | Policy links | Status in console | Button vs guideline | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Google | | | | | | | | | Unverified |
| Apple | | | | | | | | | Unverified |

Result is **Pass** (the consent screen shows EarningsNerd's identity, and the button meets the provider's current
rules), **Mismatch** (name the field), or **Unverified**.

## What a mismatch leads to

- **A console field** (a name, a logo, a support contact, a link): the founder corrects it in the console.
  Uploading a logo follows the lesson above, and no field the check did not name changes.
- **A button value**: a separate, authorized source change. It needs its own PR with
  `npm run test -- --run tests/unit/oauthStartWithInvite.spec.ts tests/unit/authPagesCopy.spec.tsx` (from
  `frontend/`) and `python -m pytest tests/unit/test_oauth_invite_gate.py` (from `backend/`). Any change to
  `frontend/DESIGN_SYSTEM.md` §9 goes to its owner as a request.
- **Anything functional** (a redirect URI, a scope, a sign-in that fails): out of scope here. Report it to the CTO
  for triage, and do not change it during the check.
