# E125: the mails keep rspamd's odd-count point, and their buttons paint a ground SpamAssassin reads (2026-10-19)

E110 sent each mail's words as its own text part, and with that rspamd's `URI_COUNT_ODD` (1 point) fired on
31 of the 40 production-shaped mails: the header's tile image is the one URL only the page carries. E125
asked which remedy to take, and the founder asked for each to be scored and the path decided. Each was
scored offline, in rspamd 4.2.2 and SpamAssassin 4.0.0, on the mails the code builds, and none is worth
taking: the mails keep the point. The same scan found that SpamAssassin read the five buttons' white words
as hidden text (`HTML_FONT_LOW_CONTRAST`, on 18 of the 40), because it reads no `background` shorthand; the
buttons now state `background-color`, and a gate holds every page to SpamAssassin's reading. No mail was
sent and no paid run was made.

## The mails and the two filters

The 40 mails are rendered from the backend with production-shaped inputs: `FRONTEND_URL`
`https://www.earningsnerd.io`, a 43-character token, and three names (none, a short one, a long one) for
each of 13 kinds, with the data-quality report as its job sends it
([`render_mails.py.txt`](render_mails.py.txt), E110's renderer). Each remedy is the MIME message Resend
would be handed ([`score_options.py.txt`](score_options.py.txt)):

| Option | What changes | Top-level type |
|---|---|---|
| current | nothing: what main sends | multipart/alternative |
| inline_nested | the tile as an image part (`src="cid:…"`), as nodemailer nests it: alternative [text, related [html, image]] | multipart/alternative |
| inline_related_top | the same image part, under a related top: related [alternative, image] | multipart/related |
| inline_mixed_top | the same, under a mixed top | multipart/mixed |
| text_tile_url | the tile's URL written into each text part | multipart/alternative |
| header_home_link | the header's tile wrapped in a link to the site | multipart/alternative |
| text_site_line | each text part ending with the site's address | multipart/alternative |

rspamd 4.2.2 scored each message through a bounded local daemon's `/checkv2`
([`with_rspamd.sh.txt`](with_rspamd.sh.txt)), handed a documentation address (`203.0.113.7`) and the
HELO `mail.earningsnerd.io`, with one 0-point measurement symbol added to its local configuration,
`X_URLS`, which lists the URLs `URI_COUNT_ODD` counts ([`x_urls.lua.txt`](x_urls.lua.txt)). The
container reaches no DNS, so every blocklist, SPF, DKIM and DMARC rule reads as a failed lookup at 0
points. SpamAssassin 4.0.0 (Ubuntu's 4.0.0-8ubuntu5, the rules it ships) scored each message with local
tests only, in test mode, each test's points read off its report ([`write_mime.py.txt`](write_mime.py.txt),
[`sa_score.py.txt`](sa_score.py.txt), [`compare_sa.py.txt`](compare_sa.py.txt)). Each message carries a
placeholder `DKIM-Signature` header, since Resend signs every mail it sends and SpamAssassin's local rules
read only that a signature exists; without one, `TO_NO_BRKTS_HTML_IMG` (1.0) fires on every mail that
carries an image part ([`sa-options-main-unsigned.txt`](sa-options-main-unsigned.txt),
[`sa-options-main-unsigned.json`](sa-options-main-unsigned.json)).

## rspamd: where URI_COUNT_ODD fires

The same on main and on this branch ([`options-rspamd-main.txt`](options-rspamd-main.txt),
[`options-rspamd-head.txt`](options-rspamd-head.txt); the points of every symbol that scores, mail by
mail: [`options-rspamd-main.json`](options-rspamd-main.json), [`options-rspamd-head.json`](options-rspamd-head.json)):

| Option | Fires on | Which mails |
|---|---|---|
| current | 31 of 40 | all but the verification, invite and reset mails |
| inline_nested | 9 of 40 | the verification, invite and reset mails |
| inline_related_top | 0 of 40 | none |
| inline_mixed_top | 0 of 40 | none |
| text_tile_url | 9 of 40 | the verification, invite and reset mails |
| header_home_link | 9 of 40 | the verification, invite and reset mails |
| text_site_line | 9 of 40 | the verification, invite and reset mails |

The rule (`rules/misc.lua`) reads a multipart/alternative top alone, counts each URL it keeps as often as
it occurs, and fires on an odd total. Main's counts: 4 on the verification, invite and reset mails,
whose page carries their link twice; 1 on the OAuth-linked mail and the data-quality report; 5 on the
referral, account-exists, alert and one-filing digest and earnings-day mails; 7 on the welcome mail and the
alert that reports changed wording; 9 on the three-filing digest and the three-company earnings-day mail.

Every mail's other points: `HFILTER_HOSTNAME_UNKNOWN` (2.5), `RDNS_NONE` (2) and `ONCE_RECEIVED` (0.1)
come from the scan's own path, a documentation address with no reverse DNS; `MANY_INVISIBLE_PARTS`
(0.05, one hidden block: the preheader) and `MIME_GOOD` (-0.1) are the mail's. So a mail's content
scores -0.05, or 0.95 with `URI_COUNT_ODD`. rspamd's default actions greylist at 4, add a header at 6
and reject at 15 (`actions.conf`). A mail that passes SPF, DKIM and DMARC takes -0.2, -0.1 and -0.5 more
by rspamd's default weights (`scores.d/policies_group.conf`; inferred for Resend's mail, since this
domain's records were not looked up here).

## SpamAssassin: every option the same

By the score SpamAssassin's report prints, to a tenth, the 40 mails score 16.6 in all on main, 0.1 to 0.8
each, under every option, and 4.0 on this branch, 0.1 each ([`sa-options-main.txt`](sa-options-main.txt),
[`sa-options-head.txt`](sa-options-head.txt); every test, mail by mail:
[`sa-options-main.json`](sa-options-main.json), [`sa-options-head.json`](sa-options-head.json)). By its exact
scores the mails as they are score 16.794 on main, 0.812 on each of the 18 and 0.099 on each of the others,
and 3.96 on this branch ([`contrast-main.txt`](contrast-main.txt), [`contrast-head.txt`](contrast-head.txt)).
Every mail scores `INVESTMENT_ADVICE` (0.1), which the footer line's "Not investment advice" trips.
`header_home_link` adds `T_REMOTE_IMAGE` on 37 of the 40, the invite mails aside: 0.01, the score
SpamAssassin gives a rule in testing, which its report prints as 0.0. Nothing else differs between the
options.

## The decision: keep the point

1. None of the four remedies that keep a mail multipart/alternative evens every count. Each adds or takes
   away one URL on every mail, so it flips every count's parity: the 31 odd mails go even, and the
   verification, invite and reset mails, which counted 4, go odd. A remedy fitted to each mail's count (one
   URL more on the mails that count odd alone) was not scored: it would hold each mail's links to the
   rule's arithmetic, and the next link a mail gains would undo it.
2. The two layouts that clear all 40 do not even the count: they take the mail out of the rule's reach,
   since it reads a multipart/alternative top alone. Whether Resend would send either is unknown. It builds
   the MIME message from the request: its reference for sending a mail
   (`resend.com/docs/api-reference/emails/send-email`, read 2026-10-19) takes an inline image as an
   attachment with a `content_id` and names no parameter that sets a mail's MIME layout, and the layout it
   builds around such an attachment was not observed, since no mail was sent (`inline_nested` is the one
   nodemailer builds). So the inline image would leave the rule firing on 9 of the 40 or on none, and the
   decision rests on points 3 and 4, which hold either way.
3. Each remedy costs what the point does not. An image part adds 5,135 bytes to every mail (the tile's
   3,495 bytes, base64-encoded, with its part's headers; 12,798 to 17,933 on main's verification mail)
   and changes the layout every client reads, which no inbox has been checked against. The tile's URL or
   the site's address in a text part is words the text part says and its page does not, which E110's rule
   (a text part says what its page says) and its gate (`text_part_problems`) refuse. Linking the header's
   tile changes every page.
4. The point is small: the mails' content scores -0.05 in rspamd without it and 0.95 with it, against a
   greylist threshold of 4.

So the mails keep the point (`lessons/arch-mail-sends-its-words-as-a-text-part.md`).

## What else the scan found: SpamAssassin read the buttons' white on cream

SpamAssassin scored `HTML_FONT_LOW_CONTRAST` on 18 of main's 40 mails under every option: the
verification, invite, reset, account-exists and both alert mails, each on its button's words (0.713
where a receiver runs neither network tests nor Bayes, 0.786 with Bayes alone, 0.001 wherever it runs
network tests, `50_scores.cf`). Two of its published metas build on the rule, `LONGLN_LOW_CONTRAST` and
`NORDNS_LOW_CONTRAST`, each with a scoring limit of 2.5 (`72_active.cf`; the live scores come from the
rules channel and were not read here).

Its HTML parser (`Mail::SpamAssassin::HTML`) reads a text's ground from a style's `background-color` alone,
on a table, a row, a cell, a div, a p, a span or a link (`text_style`). It reads no `background` shorthand,
no style on a body or on any other element, and no `bgcolor` attribute: it takes one in on a table, a row, a
cell and a body, then sets nothing with it. Each case was measured one mail at a time
([`probe-grounds.txt`](probe-grounds.txt), [`probe-grounds.json`](probe-grounds.json), from
[`probe_grounds.py.txt`](probe_grounds.py.txt) and [`sa_contrast.pl.txt`](sa_contrast.pl.txt), which prints
the first text the parser reads as low contrast). The buttons painted their sage in the shorthand
(`background:#4F7A63`), so SpamAssassin read their white words (#ffffff) on the cream of the page's outer
table (#f4f3ee), 8.98 apart by its measure, under its floor of 12 ([`contrast-main.txt`](contrast-main.txt),
from [`contrast_mails.sh.txt`](contrast_mails.sh.txt)).

Each button now writes `background-color:#4F7A63`. No mail scores the rule on this branch, and each
scores 0.099, where the 18 scored 0.812 ([`contrast-head.txt`](contrast-head.txt)). The 18 pages differ
from main's by that one declaration and nothing else, and every text part is the same. Chromium 141
paints each of them, at 600 px and at 320 px, pixel for pixel as it paints main's (36 of 36), and a
control whose button is another sage paints otherwise at both widths
([`paint-compare.txt`](paint-compare.txt), [`paint-compare.json`](paint-compare.json), from
[`paint_compare.mjs.txt`](paint_compare.mjs.txt)).

## The gate

`spamassassin_contrast_problems` (`backend/tests/support/mail_styles.py`) reads each page as
SpamAssassin's HTML parser reads a text's colours when it reads a mail: a port of `text_style`,
`close_table_tag`, `close_tag`, `html_text` and `html_font_invisible`, on the tags the standard
library's parser reads. `test_mail_rendered_addresses.py` holds every page the mail module sends to it
(`test_spamassassin_reads_no_text_on_a_page_sent_as_too_like_its_ground`).

Every comparison with SpamAssassin's parser below runs it as SpamAssassin runs it on a mail's HTML part
([`sa_html.pl.txt`](sa_html.pl.txt)): `Message::Node::rendered`, under `normalize_charset`'s default,
decodes the part to characters and builds the parser with `new(1, 1)`. In that mode a no-break space
written by its number, or as itself, is a character, so white text made of one alone scores; a review of
this record's first harness, which fed the parser UTF-8 bytes (`new(0, 0)`), found it. The harness
reports every text the parser reads, with its ink and its ground.

- **The edges of its reading**, measured before they were ported or refused ([`probe-edges.txt`](probe-edges.txt),
  [`probe-edges.json`](probe-edges.json), from [`probe_edges.py.txt`](probe_edges.py.txt)).
- **Its planted pages** (`CONTRASTS`: 44 broken, 37 refused, 29 kept): SpamAssassin's own parser reads
  each broken and kept page as the reader does, 73 of 73 ([`plants.txt`](plants.txt), page by page in
  [`plants.json`](plants.json), from [`score_plants.py.txt`](score_plants.py.txt)).
- **Pages built to make the two part**, 162 of them, by the two reviews of the reader and by this
  record: the reader refuses 102, reads the other 60 as SpamAssassin's parser reads them, and none
  otherwise ([`probe-divergences.txt`](probe-divergences.txt), the pages in
  [`probe_divergences.py.txt`](probe_divergences.py.txt), from [`cmp_sets.py.txt`](cmp_sets.py.txt)). The
  refused include a comment closed by `-- >`, where HTML::Parser ends it and the standard library does
  not; a style holding a no-break space or a Kelvin sign, which SpamAssassin matches in Unicode; a
  no-break space before the `/` that closes a tag, which SpamAssassin reads as a space, so it holds the tag
  open, where the standard library reads the space into the tag's name (the second review found it); and
  a basefont's size written as `&Tab;3`, which the standard library decodes and HTML::Parser does not. The
  60 include a marquee left open in a cell, whose tags SpamAssassin reads none of, so a cell after it
  closes the cell before it. Four of the first review's pages, each with a space past ASCII between a
  tag's name and its attribute, the reader read as SpamAssassin does and now refuses. A decimal reference
  of more than 4,300 digits stops the gate with an error, at Python's limit on reading a number (in the
  browser tokenizer it reads a page with, and in the standard library's decoding where the reference
  stands in an attribute), so the gate fails on such a page rather than passing it; a hexadecimal one of
  any length it refuses.
- **The 40 production-shaped pages** of main and of this branch: the reader finds the inks, the grounds
  and the words SpamAssassin's parser finds, 80 of 80, the 18 buttons on main and nothing on this branch
  ([`pages-main.txt`](pages-main.txt), [`pages-head.txt`](pages-head.txt), page by page in
  [`pages-main.json`](pages-main.json) and [`pages-head.json`](pages-head.json), from
  [`score_pages.py.txt`](score_pages.py.txt)).
- On main's `email_service.py` the gate fails on the five buttons, in the seven renders that carry them
  ([`gate-on-main.txt`](gate-on-main.txt)). The mutation proof is in the PR body.

The scripts are kept as `.txt`, so nothing in the repository runs them, and they name each other and
their paths as they ran: `render_mails.py.txt` ran as `render_prod.py`, E110's renderer, and
`score_pages.py.txt` reads its output. [`summarize_rspamd.py.txt`](summarize_rspamd.py.txt) and
[`trim_rspamd.py.txt`](trim_rspamd.py.txt) made the rspamd tables and trimmed its results.
