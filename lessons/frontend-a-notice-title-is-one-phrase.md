# Give a Notice or GuidanceCard title one phrase; the second clause goes in the description

Date: 2026-10-14 · Area: frontend / design system

**Context.** After Stripe's checkout, the dashboard's notice read "Checkout finished; your plan
updates in a moment": two sentences joined into the title of a component that already gives a
title and a description. The founder's chief designer review of `b8754f1e` on PR #1291 marked it
P3. The title became "Checkout finished", with "Your plan updates in a moment. Reload this page if
it still shows Free." as the description.

**Rule.** A `Notice` or `GuidanceCard` title is one phrase, never two clauses joined by a
semicolon. Put the second clause in the description. An HTML entity in JSX (`&apos;`, `&amp;`) is
one character, not a semicolon. The gate is `frontend/tests/unit/noticeTitlesAreOnePhrase.spec.ts`.
It reads every string, template piece and JSX text in a `title` given to either component, under
any import alias, in `app`, `components` and `features`, with both arms of a conditional and with
JSX entities decoded. Review checks what it cannot read: a title passed in as a variable, and two
sentences joined in a title some other way.

**Evidence.** Founder review 5510831467 on PR #1291 (inline comment 4264748883 on
`frontend/app/dashboard/page.tsx`); the split notice in `5c3fc816`, asserted title and description
apart in `frontend/tests/unit/dashboardCheckoutReturn.spec.tsx`; D-033 in
`docs/brand/decisions-log.md`; the Inline notice entry in `frontend/DESIGN_SYSTEM.md` §4.
