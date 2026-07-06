# <Button loading> sets aria-disabled, not native disabled — guard the form submit handler with an early return

**Area:** frontend-build · **Date:** 2026-07-04

Recomposing the waitlist forms, I replaced `<Button disabled={isSubmitting}>` + a manual spinner with
`<Button loading={isSubmitting}>`. The DS Button keeps its resting fill while loading and uses
`aria-disabled` + an onClick guard — it does NOT set the native `disabled` attribute (by design). But
a form's implicit submit (Enter in a field) bypasses the button's onClick and fires `onSubmit`
directly, and a non-native-disabled submit button no longer blocks implicit submission. Net: swapping
`disabled` → `loading` silently reopened concurrent/duplicate submits (Gemini caught it).

**Rule:** any form whose submit button relies on `loading` (not native `disabled`) MUST guard its
submit handler with an early return (`if (isSubmitting) return` / `if (loading) return`) right after
`preventDefault()`. Don't rely on the button's disabled look to prevent re-entry. (Also: `className`
on `<Input>` lands on the outer shell, and `text-sm` is already in the field defaults — don't re-pass
it.)
