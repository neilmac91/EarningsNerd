# Send a mail's words as its text part, never as a copy hidden in its page

**Date:** 2026-10-18 · **Area:** backend mail (`backend/app/services/email_service.py`, the delivery queue)

## Context

Every mail `email_service.py` built appended its plain-text copy to the page as a
`<pre style="display:none">` and sent no text part. A spam filter reads hidden text as a signal:
rspamd's `HIDDEN_TEXT` (`rules/html.lua`) scores 200 or more hidden characters, at up to 5 points.
Measured with rspamd 4.2.2 on production-shaped mails, it fired on 31 of main's 40 (2.1 to 5 points):
the invite's copy alone was past it, and #1334's preheaders, hidden text too, took the password reset
(217), verification (214), OAuth-linked (212) and account-exists (254) mails past it as well. The copies
had also drifted from their pages: reworded sentences, missing links, and the page's escaped greeting
("&amp;") printed as text. Given no text part, Resend builds one from the page, its hidden preheader and
header among it. A text part of the mail's own has one cost: rspamd's `URI_COUNT_ODD` (1 point) fires
where a multipart/alternative mail's URLs total odd, as they do where the header's tile image is the one
URL only the page carries (E125).

## Rule

1. Hand each mail's words to the transport as its text part, `send_email(..., text=)`, built by
   `_wrap_text`: the page's words, each link written out beside its words, then the footer and the
   footer line. A render or build function returns it after its page. A queued batch freezes it
   beside its page (`body_text`), and the batch's digest covers it.
2. A page hides one text, its preheader, and nothing else by any means a browser or a spam filter
   reads as hiding. The gate's reader reads a page both ways, a browser's and rspamd's, which differ
   (rspamd hides text under 4 px with em at 16 px, an opacity under 0.1, a box under a hidden one
   whatever it sets), and fails closed: it refuses a property, a value or an element it has not been
   taught (`_READS`, `_TEXT_ELEMENTS` in `tests/support/mail_styles.py`). Teach it with the reason it
   hides no text, or a model of how it does; plant the form, and score it against rspamd and Chromium.
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
