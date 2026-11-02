# Take an HTMLParser reader's verdict where every Python release starts the construct, never in a handler one release skips; CI runs one release, so a test hands the construct on each way

Date: 2026-11-01   Area: test

**Context**: `spamassassin_contrast_problems` (`backend/tests/support/mail_styles.py`) refuses a marked section
(`<![...>`), and it refused one in `unknown_decl`. A Python release hands a marked section on to `unknown_decl` or to
`handle_comment` on terms of its own. As measured, 3.11.17 and Ubuntu's 3.12.3, whose html.parser carries 2025's
fixes, hand one to the first where "]" closes it right before its ">" and to the second where not; 3.13.16 hands one to
the second unless it is a CDATA section. So on 3.13.16 the planted Outlook section (`<![if !mso]>...<![endif]>`) read
as two comments and its case failed, while CI, on 3.11, passed it. #1915's pre-merge check found it when it ran main's
records tests on this container's 3.13.16.

**Rule**:
- A reader built on `html.parser.HTMLParser` takes its verdict on a construct where every release starts to read it
  (for a `<!` that opens no comment, `parse_html_declaration(self, i)`), then reads on as the release does; never in a
  handler one release reaches and another skips.
- Trace a construct's route on each release before relying on it. The container carries 3.11, 3.12 and 3.13
  (`/usr/bin/python3.1x`), and `uv venv --python /usr/bin/python3.11` with the backend's requirements runs the suite on
  one of them.
- CI runs one release, so a test hands the construct on each way a release does or may, through the standard library's
  own readers of each, and holds every planted page to the running release's verdict (gated for marked sections by
  `test_the_contrast_check_scores_a_planted_marked_section_alike_however_a_release_hands_it_on` in
  `backend/tests/unit/test_mail_rendered_addresses.py`; other constructs and the other readers are review-checked).

**Evidence**: The fix and its gate (`test(mail): the contrast reader refuses a marked section the same on every Python
release`). The reader's verdicts on the 110 planted pages and three more are byte-identical on 3.11.17, 3.12.3 and
3.13.16, and the old reader, run on 3.11 or 3.12, fails the new test alone.
