# Send a mail's words as its text part, never as a copy hidden in its page

**Date:** 2026-10-18, updated 2026-10-19 (E125) · **Area:** backend mail (`backend/app/services/email_service.py`, the delivery queue)

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
URL only the page carries: on 31 of the 40.

E125 scored each remedy in rspamd 4.2.2 and SpamAssassin 4.0.0, and the mails keep the point. Each that
keeps the mail multipart/alternative (the tile as an inline image part, its URL in each text part, the
header's tile linked to the site, the site's address at the end of each text part) leaves 9 of the 40
odd: the verification, invite and reset mails, which counted even. The two that clear all 40 put the
image part under a multipart/related or a multipart/mixed top, which the rule does not read (it reads
a multipart/alternative top alone). Resend's API names no parameter that sets a mail's MIME layout (its
reference for sending a mail, read 2026-10-19), and the layout it builds around an inline image was not
observed. Whichever it builds, the image part costs every mail 5,135 bytes and a layout no inbox was
checked against, for a point on mails whose content otherwise scores -0.05 in rspamd (the scan's own
sending path aside), far under its greylist threshold of 4.

The same scan found SpamAssassin's `HTML_FONT_LOW_CONTRAST` (0.713 where a receiver runs neither network
tests nor Bayes) on 18 of the 40. SpamAssassin reads a text's ground only from a style's
`background-color` on a table, a row, a cell, a div, a p, a span or a link, never from the `background`
shorthand or a `bgcolor` attribute, so it read the five buttons' white words on the page's cream around
them.

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
   SpamAssassin reads no text as too like its ground either: paint a ground under light words as
   `background-color`, the colon right after the name, in the style of the table, row, cell, div, p,
   span or link that holds them. A `background` shorthand or a `bgcolor` alone paints a ground a browser
   shows and SpamAssassin does not read; it reads the ground around it, white at the page's edge. Its
   reader (`spamassassin_contrast_problems`) is a port of SpamAssassin's own reading of a mail, whose text
   it decodes to characters (so a no-break space by its number is a character), and fails closed too: plant
   a new form and score it with SpamAssassin's HTML parser in that mode (`new(1, 1)`, as
   `Message::Node::rendered` builds it).
3. A text part says what its page says. Change both in the same edit.
4. Plain text is never escaped: the reader's name goes in as typed, on one line (`_greeting_text`).

## Evidence

- E110: `email_service.py`'s `_wrap_text` and `_greeting_text`; `notification_delivery_service.py`'s
  `payload_digest`, which leaves a NULL text out, so a batch frozen before `body_text` keeps its digest
  (`backend/migrations/20261018_earningsnerd_delivery_body_text.sql`).
- E125: the five buttons' `background-color` in `email_service.py`; the scores, the options and the
  port's agreement with SpamAssassin, page by page and plant by plant:
  `tasks/review-evidence/e125-mail-spam-scores-2026-10-19/`.
- Gates: `backend/tests/unit/test_mail_rendered_addresses.py` (every send's text part,
  `text_part_problems`; the hidden text, `tests/support/mail_styles.py`'s `hidden_text_problems`; the
  colours SpamAssassin reads, `spamassassin_contrast_problems`),
  `test_email_name_interpolation_allowlist.py`, `test_email_name_escaping.py`,
  `test_notification_delivery.py`.
