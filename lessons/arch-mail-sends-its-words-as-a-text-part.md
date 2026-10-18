# Send a mail's words as its text part, never as a copy hidden in its page

**Date:** 2026-10-18 · **Area:** backend mail (`backend/app/services/email_service.py`, the delivery queue)

## Context

Every mail `email_service.py` built appended its plain-text copy to the page as a
`<pre style="display:none">` and sent no text part. A spam filter reads hidden text as a signal:
rspamd's `HIDDEN_TEXT` (`rules/html.lua`) scores 200 or more hidden characters, at up to 5 points.
The invite's copy was past that on main (205 characters). #1334's preheaders, which are hidden text
too, took the password reset, verification, OAuth-linked and account-exists mails past it as well
(212 to 254). The copies had also drifted from their pages: reworded sentences, missing links, and
the page's escaped greeting ("&amp;") printed as text. Given no text part, Resend builds one from
the page, its hidden preheader and header among it.

## Rule

1. Hand each mail's words to the transport as its text part, `send_email(..., text=)`, built by
   `_wrap_text`: the page's words, each link written out beside its words, then the footer and the
   footer line. A render or build function returns it after its page. A queued batch freezes it
   beside its page (`body_text`), and the batch's digest covers it.
2. A page hides one text, its preheader, and nothing else by any means a browser or a spam filter
   reads as hiding.
3. A text part says what its page says. Change both in the same edit.
4. Plain text is never escaped: the reader's name goes in as typed, on one line (`_greeting_text`).

## Evidence

- E110: `email_service.py`'s `_wrap_text` and `_greeting_text`; `notification_delivery_service.py`'s
  `payload_digest`, which leaves a NULL text out, so a batch frozen before `body_text` keeps its digest
  (`backend/migrations/20261018_earningsnerd_delivery_body_text.sql`).
- Gates: `backend/tests/unit/test_mail_rendered_addresses.py` (every send's text part,
  `text_part_problems`; the hidden text, `tests/support/mail_styles.py`'s `hidden_text_problems`),
  `test_email_name_interpolation_allowlist.py`, `test_email_name_escaping.py`,
  `test_notification_delivery.py`.
