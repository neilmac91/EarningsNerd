# Guard submit handlers with an early return when the button uses loading, not disabled

Date: 2026-07-04   Area: frontend

**Context**: Recomposing the waitlist forms, replaced `<Button disabled={isSubmitting}>` + a manual spinner with `<Button loading={isSubmitting}>`. The DS Button uses `aria-disabled` + an onClick guard by design — NOT the native `disabled` attribute. But a form's implicit submit (Enter in a field) bypasses the button's onClick and fires `onSubmit` directly, so the swap silently reopened concurrent/duplicate submits. Gemini caught it.

**Rule**: Any form whose submit button relies on `loading` (not native `disabled`) MUST guard its submit handler with an early return (`if (isSubmitting) return` / `if (loading) return`) right after `preventDefault()`. Don't rely on the button's disabled look to prevent re-entry. Also: `className` on `<Input>` lands on the outer shell, and `text-sm` is already in the field defaults — don't re-pass it.

**Evidence**: `<Button loading={isSubmitting}>` sets `aria-disabled` + onClick guard, not native `disabled`; implicit submit (Enter in a field) bypasses onClick and fires `onSubmit` directly.
