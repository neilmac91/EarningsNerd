# Decision record 15 — the rule-12 runtime-records gate merged (PR #1110) after 14 paid runs, each settled — 13 reserved before they fired, one recorded after the founder's ready action triggered it; Codex reviews again from 2026-10-07 (no override used; its 18 findings over 14 reviews verified, 17 fixed and one declined with reasons); an adversarial sweep and six verification rounds; the eval's non-acceptances disclosed; one ledger slip corrected; PR #1109 review record closed; sixth and seventh deploy-skip proofs; ledger events 7–34; closure 165 (chief, 2026-10-08)

Recorded 2026-10-08T03:51:14Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`). From this record on, model
identifiers are not written into these public records (a harness rule for record content, PR text and commit messages; only a
commit's required co-author trailer names one); contexts are identified by their context id and launch time, and a model change
of the chief session is recorded as an event without naming the models. One such event so far: the founder changed the chief
session's model on 2026-10-07 between 10:38:52Z and 12:46:55Z (the commits `a154b316` and `e1ab73e4` of PR #1110); the session
and its link are unchanged, and the checkpoint header no longer names a model. Context: record 14 merged to main as `f26debcb43f8c49eeca34e76cef6bc0e394a920e` (PR #1109, squash of
`4b814581` + `f0f3dc53`, merged 2026-10-07T07:12:27Z); the runtime-records gate merged to main as `e144ef3d2dedcb15603cd3267ab719478d925360`
(PR #1110, squash of 29 commits from `e9911039` to `471a253c`, merged 2026-10-08T03:35:55Z; main also carries other work merged meanwhile — PRs #1111, #1102, #1107,
#1116, #1117, #1119, #1122, #1125, #1081, #1127 and #1112, none touching these records); this branch was restarted from `e144ef3d`. This record is
records only: no code, workflow, migration, cloud, IAM or production change; no provider call by this record; no reservation written
by this record (every paid run of the gate PR was settled, and all but run 10 reserved before it fired, by ledger events 7–34, all
written before this record); no
source material opened.

## What this record closes

1. The rule-12 gate for these records is in CI (PR #1110): every record PR from now on fails `backend-tests` when the records tree
   is missing or holds a symbolic link or a record that is not plain UTF-8 text with a plain name, the checkpoint's structure is not
   what a reader sees (raw HTML, a section title rendered twice or by a setext heading, more than one deliverables table), a
   deliverables row is malformed or its digest wrong, a runtime file is untabled, the closure chain is broken or its committed tail
   removed, a stamp is earlier than the newest closure or not strictly UTC, a decisions entry is malformed or out of sequence, a
   JSON file does not parse strictly, or a private address, home path or upload-area path appears in any reading of any record —
   before any reviewer sees it. This record is the first the gate checks.
2. The gate PR's 14 paid `copilot-eval` runs were each settled at actual cost; 13 were reserved before they fired, and run 10, which
   the founder's marking the PR ready triggered while the chief held it in draft, was recorded after it had run (event 25 at
   22:20:03Z: 2 min 19 s after the ready action at 22:17:44Z, 1 s after the run's job completed). Paid dispatch is
   HELD again. Six runs were not accepted by the eval's own citation check; disclosed below, not caused by this PR.
3. Codex reviews pull requests again from 2026-10-07; its 18 findings on the gate (over 14 reviews) were each verified, and 17 were
   fixed and one declined with reasons; the founder's review-override exception rests while Codex reviews.
4. One ledger slip (event 11's active-reservation entry carried the wrong event number) is corrected and disclosed (chief defect 5).
5. PR #1109's review record; the sixth and seventh live proofs that merges confined to `backend/tests/` and `tasks/` skip the deploy.

## The runtime-records gate (PR #1110)

**What landed** (29 commits, three files; nothing under `backend/app/`, `.github/` or `tasks/`):

- `backend/tests/unit/test_code_red_runtime_records.py` — nine tests over `tasks/code-red-20261004/runtime/`: the tree, its
  `control/` directory, `CHECKPOINT.md` and `APPOINTMENTS.json` exist (absence fails, never skips) and the tree holds no symbolic
  link; every record is UTF-8 text without NUL bytes, named in plain text (no invisible, control or separator character, no
  whitespace at either end of a name segment); `CHECKPOINT.md` is read with the CommonMark parser the backend already pins
  (`markdown-it-py`, GFM tables), nesting well inside the depth the parser reads in full: it holds no raw HTML, it opens with the
  heading `# <title> (updated <stamp>)`, each of its deliverables and decisions titles is rendered by exactly one heading (the `## `
  line itself), every top-level heading of level one or two is an ATX heading with visible text, the deliverables section renders
  exactly one table whose every row parses as `| path | digest |` with a 64-lowercase-hex digest equal to the file's, named by its
  plain relative path (no detour, absolute path or symbolic link) inside the runtime tree or the permitted
  `tasks/readiness-2026-09-21/beta/` tree, and no other table, nor that table's header, nor a row's cells after its digest, shows a digest as rendered; every file under the runtime tree has a row and the
  four off-tree rows tabled at that commit stay tabled; every entry named like a closure is a canonical closure file directly
  under `control/`, and the closures chain append-only, anchored to the committed tail (closures 136–164 present, closure 164 pinned
  by digest; each `prior_record` hash equals the previous file, each `recorded_at` is later than its predecessor's, counts are
  integers equal to the lists, the previous ids are a prefix, nothing is duplicated, the declared new entries are exactly the
  appended ids and the `new_context_roles` keys, resolved labels were registered before); the checkpoint header and
  `APPOINTMENTS.json` are stamped no earlier than the newest closure at the closure's fractional precision, every stamp in the one
  form `YYYY-MM-DDTHH:MM:SS[.ffffff]` + `Z` or `+00:00`; every non-blank line of the decisions section is a numbered entry and the
  numbers run contiguously from 1; every JSON and JSON-lines file parses strictly (no duplicate member names, no `NaN`); and the
  records carry no claude.ai address other than the session link with its id or a written placeholder (so no private artifact link
  and no gallery link by any route),
  no home-directory path, and under `control/` and in the checkpoint no session upload-area path — every file scanned whatever its
  suffix, as written and with markup removed, each line folded the way a browser, a JSON consumer, a Markdown renderer or a terminal reads it
  (percent-encoding, HTML references, JSON and Markdown escapes, terminal control strings and colour codes, compatibility forms,
  invisible characters, case), plus a reading with the JSON escapes decoded once. It runs on every PR (CI runs the backend gate on every PR) and never triggers `deploy-backend` (the detector ignores
  `backend/tests/`). Its docstring names what it does not cover: it guards against leaks and structural slips, not a hostile
  writer (look-alike letters, an address split by whitespace, a volume name with a space are outside it).
- `lessons/test-absence-claims-come-from-git-grep.md` and its index line in `lessons/README.md` — the rule from record 12's
  reviewer blocker (chief defect 4): an absence claim is made only from `git grep` over every tracked file; a test asserting absence
  scans every file in its tree, never a suffix allow-list.

**Mutation proofs** (each in a detached worktree, restored afterwards; one failure each, clean run passing at every head): hash-row
tamper, untabled file, early stamp, numbering gap, closure count tamper, previous-closure tamper, private URL, broken JSON
(`e9911039`); a `.jsonl` file containing a home path with a matching row, the second artifact-link form in a control and in a
handback file, an escaping `../../` row (`502f115a`); a demoted `###` heading, a stray `__pycache__/x.pyc` (`d74f2c44`); a permitted
off-tree row with a 63-character digest, a nested `control/archive/` file carrying the upload-area path (`8fb59df1`); a row whose
path cell lacks backticks, a stray pipe-prefixed note in the table (`8d1cf886`); the separator line deleted, the header line deleted
(`abdaae24`); the checkpoint stamp at the newest closure's own second (one second later passes), a `52) …` entry, a stray bullet
(`66d5521d`); the tree renamed (the parent skipped), a row without its leading pipe, closure 164 deleted with its row, closure 164
altered with its row re-hashed (`817f68d9`); a symbolic link to a directory, a dangling link, a link to a regular file (`5060ab09`); the upload-area path spelled with a backslash-escaped solidus and with a code-point-escaped dot in a tabled control JSON file, a JSON-lines line carrying an escaped macOS home path, a JSON-lines line that does not parse (`6a7a3f27`); a pinned off-tree row deleted, a closure 166 chained to 164 with 165 absent, a well-formed closure 165 still passing (`defe0281`); an upper-case artifact host in the checkpoint, an upper-case home path in a control JSON file, a closure 165 dated before 164 and one carrying 164's exact stamp, one 27 ms later still passing (`84fded68`); the product route `/api/users/me` cited in a control JSON file passing where the parent failed, raw, upper-case, file-URL, backticked and escaped-solidus home paths failing (`e692da12`); a closure with a timezone-less stamp, one with a non-UTC offset and an appointments stamp without its `Z`, valid `Z` and `+00:00` stamps still passing (`e0f00861`); an artifact link with an explicit port, a trailing-dot host, doubled slashes, a percent-encoded letter or slash, and userinfo with an upper-case host, the session link form still passing (`a9b94c75`); doubly and triply percent-encoded spellings, a literal percent sign in prose still passing (`1e987b0b`); percent-encoded upper-case letters in the link, the home path and the upload-area path (`a154b316`); numeric and named HTML references, a full-width link, a zero-width space, a soft hyphen, backslash separators, an ideographic full stop, a variation selector, a Windows home path and a backslash upload-area path, legitimate prose with `&`, `/api/users/` and a percent sign still passing (`e1ab73e4`); then, from `74a53f07` to `471a253c`, an adversarial sweep at `e1ab73e4` and six verification rounds — 164 read-only agents in seven workflows (`wf_b6d89b8e-cd6`, `wf_f997c473-a57`, `wf_fa8c5b37-371`, `wf_efc1a716-981`, `wf_f10e6641-4f5`, `wf_7aa1f81c-d0c`, `wf_a845ce3b-8f4`), each in an isolated worktree, every finding reproduced by a separate verifier — whose verified findings moved the checkpoint reading to the CommonMark parser, the address check to an allow-list of the session link and the scan to several decoded readings per line; on the final head 213 string probes and 100 file-level mutations behave as intended; of four further cases, three are renderer limits the docstring names and one no longer mutates. Locally the test ran with `--noconftest`; CI ran it under the real `conftest.py` on every head (`backend-tests` success each time; final head
job 113133832463).

**Review** (code-bearing PR → the lean three-lens workflow plus one delta reviewer, pre-registered in closure 164 under
`runtime-records-gate-review-01`; all read-only; identities in closure 165):

- Three lenses (anchors, code, policy) on `e9911039`, refuters only for blocker and should-fix findings (workflow `wf_1cf4ba90-7d3`,
  3 lens contexts + 5 refuter contexts, 07:14–07:41Z; five findings went to refuters: three held — the suffix allow-list, raised by
  two lenses, and the second link form — one was refuted as a should-fix and applied as a nit, and one was refuted and not
  applied): **no blocker**; two should-fix findings — the forbidden-strings test scanned
  only `.md`, `.json` and `.sh` files and so skipped the tree's tracked `.jsonl` (the very defect the lesson records, reproduced in
  the gate's own code), and the second artifact-link form (the `/code/` path variant) was not a needle; nits — hash rows read from
  the deliverables section only, an escaping-row guard, null-safe closure fields, the stamp message naming its convention, the
  lesson's quotation made verbatim with the squash-merge reference and a single rule, a shorter index line. One finding refuted and
  not applied: widening the needles to container home paths (`/home/`, `/root/`), which are by-convention identifiers in these
  records. All accepted findings applied in `502f115a` (pushed 07:46:59Z).
- The single delta reviewer (launched 07:47Z; one context) ran 22 checks, each bound to the head named (check 19 covering every head
  from `74a53f07` to `37c3ce12` at once): `502f115a` ACCEPT WITH NITS (four nits, applied in `d74f2c44`);
  `d74f2c44` (the four nits applied) ACCEPT; `8fb59df1` (Codex round 1 applied) ACCEPT WITH NITS (one P3 nit, applied in `8d1cf886`); `8d1cf886` (its P3 nit
  applied) ACCEPT WITH NITS (one optional nit, applied in `abdaae24`); `abdaae24` (its optional nit applied) ACCEPT; `66d5521d` (Codex round 2 applied) ACCEPT WITH NITS (one docstring nit, applied in `351191d7`);
  `351191d7` (docstring only) ACCEPT; `817f68d9` (Codex round 3 applied) ACCEPT;
  `5060ab09` (Codex round 4 applied) ACCEPT;
  `6a7a3f27` (Codex round 5: one finding applied, one declined) ACCEPT (the decline judged sound);
  `defe0281` (Codex round 6 applied) ACCEPT;
  `84fded68` (Codex round 7 applied) ACCEPT WITH NITS (the lower-cased home-path pattern collided with the product's `/api/users/…` routes; applied in `e692da12`);
  `e692da12` (the nit applied: the home path matched as a leading path segment) ACCEPT;
  `e0f00861` (Codex round 8 applied) ACCEPT;
  `a9b94c75` (Codex round 9 applied) ACCEPT (one optional note, applied in `1e987b0b`);
  `1e987b0b` (the optional note applied: percent-decoding to a fixed point) ACCEPT WITH NITS (one nit, applied in `a154b316`);
  `a154b316` (the nit applied: the case fold re-applied after each decoding step) ACCEPT (re-requested once after a provider rate limit stopped the first run without a verdict);
  `e1ab73e4` (the chief's root-cause hardening: each text read as a renderer reads it before matching) ACCEPT WITH NITS (one should-fix false positive, raw `\/api\/users\/me` in JSON text read as a home path, applied in `74a53f07` with the adversarial sweep's fixes);
  `37c3ce12` (check 19: the whole change since `e1ab73e4` — the sweep's and six verification rounds' fixes, the CommonMark reading
  of the checkpoint, Codex round 10 — with 70 proofs of its own) ACCEPT WITH NITS (three nits: the session-link form, digests in
  status cells, type hints; applied in `839113b1`);
  `839113b1` ACCEPT;
  `03b5cefc` (Codex round 12 applied) ACCEPT WITH NITS (two nits: a home path written right after a session-id placeholder, empty
  placeholders; applied in `471a253c`);
  `471a253c`, the final head: ACCEPT.
- Codex reviewed each head that left draft and, on request, each head pushed while the PR was ready: `d74f2c44` (review 5439411208, 08:08:33Z) — two P2 findings: a malformed digest silently
  dropped a deliverables row (an off-tree row then went unchecked); the control-only needles covered only direct children of
  `control/` — fixed in `8fb59df1`; `abdaae24` (5439735601, 08:37:17Z) — two P2: stamps compared after truncation to whole seconds;
  a malformed trailing decisions entry vanished instead of failing — fixed in `66d5521d`; `351191d7` (5439925612, 08:54:54Z) — three
  P2: a module-level skip let a deleted or renamed records tree stay green; rows prefiltered by a leading pipe; no committed-tail
  anchor on the chain — fixed in `817f68d9`; `817f68d9` (5440104376, 09:09:31Z) — one P2: a tracked symbolic link to a
  directory or an absent target is not a file, so the completeness and forbidden-string scans skipped it while its target path sat in
  Git — fixed in `5060ab09` (no symbolic links permitted anywhere in the tree); `5060ab09` (5440300189, 09:26:40Z) — two P2: a forbidden
  string spelled with JSON escapes evaded the raw-text scan — fixed in `6a7a3f27` (every JSON document decoded and its strings
  scanned; JSON-lines files parse line by line); and a proposal to require the newest closure to equal the pinned tail — verified as
  described and **declined** on its thread (it relocates the coordinated edit rather than removing it, and it would put every
  records-only PR under `backend/**`, firing the paid eval and the code-bearing review workflow on each record; the tail constant is
  advanced whenever the gate file is next edited — the operating rule below); `6a7a3f27` (5440500639, 09:44:50Z) — two P2: the four
  off-tree deliverable rows could be deleted from the checkpoint unnoticed; a closure numbered 166 chained to 164 passed with 165
  absent — fixed in `defe0281` (the off-tree rows tabled at this commit are pinned; closure numbers must run 136 through the newest
  without gaps); `defe0281` (5440616900, 09:56:12Z) — two P2: an artifact URL with its host in another case evaded the case-sensitive
  scan; a correctly chained closure dated earlier than its predecessor passed — fixed in `84fded68` (raw and decoded text lower-cased
  before matching, needles lower-case; each closure's `recorded_at` strictly later than its predecessor's); `e692da12` (5440829027, 10:14:30Z) — one P2: a stamp
  without a UTC offset was read as UTC — fixed in `e0f00861` (an explicit zero offset is required; a naive or non-UTC stamp fails by
  name); `e0f00861` (5440995190, 10:30:18Z) — one P2: an artifact link with an explicit port evaded the substring match — fixed in
  `a9b94c75` (haystacks case-folded and percent-decoded; the link matched by a pattern tolerating a port, a trailing dot and repeated
  slashes in either form; the session link form still allowed); `37327581` (5449103836, 22:20:52Z, the review the founder's ready action triggered) — one P2: a blank line between deliverables rows ended the rendered table while the rows after it still passed — fixed in `7128fa73` (the section must render exactly one table), pushed with the head `37c3ce12`; `37c3ce12` (comment 6050959961, 2026-10-08T02:31:03Z, on request) — no findings; `839113b1` (5450842952, 02:58:00Z, on request) — one P2: the bare session route and an empty session id passed the allow-list — fixed in `03b5cefc` (a written placeholder is read as an id before markup is removed, so the allow-list requires an id or a placeholder in every reading); `03b5cefc` (comment 6051427239, 03:14:56Z, on request) — no findings; `471a253c`, the final head (comment 6051589810, 03:30:42Z, on request) — no findings. Every finding was verified by the chief before the fix or the decline, and every
  thread answered (with the fixing commit, or the reasons) and resolved. Through review 9 the PR went back to draft before each fix was
  pushed, so no paid run fired on a push; after the founder marked it ready (2026-10-07T22:17:44Z; run 10 started 22:17:46Z) the chief left it ready and wrote a
  reservation before each push instead. No `Review override:` line was used at any point; `review-gate` passed on the Codex Completed
  row at every head that left draft or was pushed while ready (from run 37591507559 on the first to run 37722713664 on the final
  head).

**Operating rule (gate anchors).** The gate pins the closure chain to its committed tail (`COMMITTED_CLOSURES` = 136–164,
`COMMITTED_TAIL` = closure 164 by digest) and pins the four off-tree deliverable rows tabled at this commit
(`COMMITTED_OFF_TREE_ROWS`); later closures chain to the tail without gaps and are checked by each record PR's independent reviewer
(chain step N-1 → N, newest closure). Whenever the gate file is next edited for any reason, both anchors are advanced in the same
commit — the tail to the then-newest closure and its digest, the pinned rows to the off-tree rows then tabled. The anchor is not advanced by records-only PRs, because an edit under
`backend/**` fires the paid `copilot-eval` run and the code-bearing review workflow on every record (Codex's declined finding).

**Merge:** squash-merged as `e144ef3d` at 2026-10-08T03:35:55Z on the final head `471a253c`, every check on that head
green (`copilot-eval` run 14 included; `deploy-backend` skipped on the PR run). Main CI run 37723488706 green
(03:35:57–03:42:23Z); its `deploy-backend` job 113137811799 ran only the change detector, logged `No deployable backend
changes - skipping deploy.` and **skipped all twelve deploy steps** — the seventh live proof of the PR #1101 correction (tests only;
no service revision, no job image, no migration). The earlier proofs counted nine: PR #1117 added the registry-authentication and
Docker Buildx steps and PR #1122 the private task-worker update, each gated on the detector like the rest (merged to main
meanwhile, outside these records).

## The paid runs — each reserved before it fired and settled after, except run 10, which the founder triggered (ledger events 7–34)

| Run (head) | Reserved (event, written) | Fired (run start; trigger) | Run / job | Outcome | Telemetry (calls; USD; tokens) | Settled (event, written; released) |
|---|---|---|---|---|---|---|
| 1 (`d74f2c44`) | 7, 07:14:49Z — two seconds before the PR was opened as a draft; named head `e9911039` | 08:05:52Z; ready | 37591507299 / 112693841701 | failure — eval not accepted: 18 / 18 / 15 scored / 15 passed / 3 errors, all three draws of BABA `viewed-native-revenue-2025` withheld by the service's citation check | 34; 0.012581; 977,466 prompt (971,264 cache hits) / 4,080 completion | 8, 08:14:03Z; 0.047419 |
| 2 (`abdaae24`) | 9, 08:14:47Z; named head `8fb59df1` | 08:32:48Z; ready | 37594477790 / 112703624394 | success — accepted 18 / 18 / 18 / 18 / 0 | 33; 0.011949; 945,208 / 3,743 | 10, 08:40:58Z; 0.048051 |
| 3 (`351191d7`) | 11, 08:40:58Z; named head `66d5521d` (its entry carried event number 9 in error — corrected by event 12) | 08:51:19Z; ready | 37596562861 / 112710533489 | failure — not accepted: 17 scored / 17 passed / 1 error, draw 2 of the same question withheld | 33; 0.011918; 945,194 / 3,723 | 12, 08:56:44Z; 0.048082 |
| 4 (`817f68d9`) | 13, 09:01:12Z | 09:06:05Z; ready | 37598266061 / 112716068781 | success — accepted 18 / 18 / 18 / 18 / 0 | 33; 0.011884; 945,196 / 3,723 | 14, 09:14:11Z; 0.048116 |
| 5 (`5060ab09`) | 15, 09:15:26Z | 09:23:22Z; ready | 37600263407 / 112722636014 | success — accepted 18 / 18 / 18 / 18 / 0 | 33; 0.011904; 945,194 / 3,742 | 16, 09:31:33Z; 0.048096 |
| 6 (`6a7a3f27`) | 17, 09:39:08Z | 09:41:37Z; ready | 37602360863 / 112729551175 | failure — not accepted: 16 scored / 16 passed / 2 errors, two draws withheld at the citation publication boundary (one unverified or ambiguous referenced citation, one unsupported prose quotation) | 34; 0.012428; 977,465 / 3,980 | 18, 09:44:46Z; 0.047572 |
| 7 (`defe0281`) | 19, 09:50:31Z | 09:52:28Z; ready | 37603580135 / 112733565805 | success — accepted 18 / 18 / 18 / 18 / 0 | 34; 0.012222; 977,469 / 3,808 | 20, 10:00:00Z; 0.047778 |
| 8 (`e692da12`) | 21, 10:05:36Z | 10:11:35Z; ready | 37605751354 / 112740678346 | failure — not accepted: 17 scored / 17 passed / 1 error, one draw withheld at the citation publication boundary (unverified or ambiguous referenced citation) | 33; 0.005937; 945,184 / 3,714 | 22, 10:14:51Z; 0.054063 |
| 9 (`e0f00861`) | 23, 10:21:03Z | 10:26:02Z; ready | 37607362138 / 112746008321 | success — accepted 18 / 18 / 18 / 18 / 0 | 33; 0.005913; 945,194 / 3,675 | 24, 10:33:59Z; 0.054087 |
| 10 (`37327581`) | 25, 22:20:03Z — recorded after the trigger: the founder marked the PR ready at 22:17:44Z, while the chief held it in draft for further verification; written after the run's job completed (22:20:02Z) | 22:17:46Z; ready (founder) | 37695253262 / 113045269828 | success — accepted 18 / 18 / 18 / 18 / 0 | 34; 0.006290; 996,356 (990,583 cache hits) / 4,086 | 26, 22:47:36Z; 0.053710 |
| 11 (`37c3ce12`) | 27, 2026-10-08T02:27:31Z | 02:28:02Z; push while ready | 37718004123 / 113118877598 | failure — not accepted: 17 scored / 17 passed / 1 error, one draw withheld at the citation publication boundary | 38; 0.014386; 1,113,252 (1,106,807 cache hits) / 4,843 | 28, 02:31:05Z; 0.045614 |
| 12 (`839113b1`) | 29, 02:53:01Z | 02:53:26Z; push | 37720074791 / 113125466027 | success — accepted 18 / 18 / 18 / 18 / 0 | 34; 0.012848; 996,381 (990,711) / 4,339 | 30, 02:58:22Z; 0.047152 |
| 13 (`03b5cefc`) | 31, 03:10:25Z | 03:10:48Z; push | 37721483659 / 113129895701 | failure — not accepted: 17 scored / 17 passed / 1 error, one draw withheld at the citation publication boundary | 36; 0.013696; 1,062,930 (1,056,887) / 4,618 | 32, 03:13:31Z; 0.046304 |
| 14 (`471a253c`) | 33, 03:25:54Z | 03:26:17Z; push | 37722715889 / 113133832352 | success — accepted 18 / 18 / 18 / 18 / 0 | 37; 0.014129; 1,088,089 (1,081,847) / 4,802 | 34, 03:29:44Z; 0.045871 |

Every ceiling was USD 0.060000 (dearest measured comparable run 0.025568 × 2, rounded up; the record-09 rule); no run exceeded it.
Retained holds 1.881713 unchanged throughout. Recorded use against the USD 25 authority 0.590487 → 0.748572 (calls 393 →
872); conditional unreserved 22.527800 → **22.369715**; active reservations 0; paid dispatch HELD again. Each
publish was preceded by a readback of the published file and followed by a readback with the new hash (document after the last
event: `66471d09305626f3655ee372e06a4156f8a15df412f85d03118b196d41c0c548`, 106,288 bytes, artifact version 35). Measured `copilot-eval` runs on
comparable code now read 0.005575 / 0.025568 / 0.011828 / 0.012581 / 0.011949 / 0.011918 / 0.011884 / 0.011904 / 0.012428 / 0.012222 / 0.005937 / 0.005913 / 0.006290 / 0.014386 / 0.012848 / 0.013696 / 0.014129; the next reservation stays
at the dearest measured run × 2 unless a dearer run is measured. The event-4 excess of USD 0.015568 stays visible. All events are
appended to `control/LEDGER-ACCESS.md` by this record. Telemetry estimates, not invoices.

**The non-acceptances, disclosed.** The eval's acceptance requires every draw to be scored; a draw the service withholds under its
citation check counts as an execution error. Runs 1, 3, 8, 11 and 13 lost draws to that check (run 1 all three draws of one question
on one filing), and run 6 lost two draws (one unverified or ambiguous referenced citation, one unsupported prose quotation); runs 2,
4, 5, 7, 9, 10, 12 and 14 on the identical eval code were accepted in full. Nothing in this PR touches the answer path, the citation check, the prompts or the eval
harness, so the outcomes are the eval's own nondeterminism on live model output, recorded as observed; `copilot-eval` is not a
required check. No paid re-run was triggered for a non-acceptance: every later run followed from a fix push under its own
reservation (or, run 10, from the founder's ready action). Three standing-down comments on the PR (6034525467, 6050967656 and
6051413678) record the failures of runs 3, 11 and 13.

**Chief defect 5 (ledger).** The script that wrote event 11 carried the previous reservation's event number (9) into the new
active-reservation entry; the ceiling, purpose, head and headroom arithmetic were correct and event 11's own sequence number, chain
hash and statement are right. Found by the chief when writing event 12, which records the correction (`correction` field, balances
unaffected) while settling the reservation; the event-13 script asserts the entry's event number. Recorded in
`control/APPOINTMENTS.json` (`chief_defects`).

## Codex reviews again — the override exception rests

From 2026-10-07 the Codex connector posts real review summaries: PR #1109's summary comment 6032808809 shows the Code Review for
`f0f3dc5` **Completed** at 07:07:50Z (no findings); PR #1110's summary comment 6033721005, updated in place, showed Completed after
each of its fourteen reviews (the last on `471a253`, 03:30:43Z). `review-gate` passed on the Completed row each time. Consequences recorded here:

- The founder's Codex-credit exception (the standing authorization recorded at takeover, `TAKEOVER.md`: `Review override:
  <reason>` in the PR body with an independent current-head review recorded) applies **only while Codex's quota is exhausted**.
  It was used on every earlier PR from this branch (#1086–#1106); it was **not** used on #1109 or #1110 and is not used again unless the connector's usage-limit comment
  returns. Records stop describing the quota as exhausted.
- The independent read-only review of every PR continues unchanged (records-only rule: one reviewer context plus the same context's
  delta check; code-bearing: the lean three-lens workflow plus one delta reviewer). Codex's review is additional, never a
  substitute, and is never claimed where it did not happen. Its non-optional findings are verified, then fixed or declined with reasons on their thread. On a backend/**-touching
  PR every un-draft, and every push while the PR is ready, fires one paid run, so each needs a reservation first — fourteen runs here,
  USD 0.158085 in all.
- Observed only, not acted on: the founder's product-owner PRs #1107 (EN-02), merged to main as `aa17bcb8`, and #1108 (EN-03),
  open and out of draft at this record, each driven in its own session. Outside these records; the chief changes nothing there.

## PR #1109 review record closed (decision record 14)

- Head `4b814581` reviewed by the single pre-registered reviewer (closure 164, `record-14-reviewer-01`, launched 06:55Z): **NO
  BLOCKER**; 96 hash rows / 0 mismatched / 0 missing; closure chain 163 → 164 verified; every locally checkable anchor verified;
  semantics confirmed; policy greps clean over 563 added lines; 0 should-fix; 5 nits (a merge-count phrase; the ticked founder item
  silent on (a)/(b); field 6's charging default; the relay date stated in three places; one PR-body phrase), all applied in
  `f0f3dc53`.
- Delta `4b814581..f0f3dc53` by the same reviewer: **NO BLOCKER bound to `f0f3dc539e7d36344ad2f29f625842a5d0af759c`**; 0 remaining.
  Codex reviewed the PR itself (above); no override.
- Merged `f26debcb` at 07:12:27Z onto `be43b490`. Main CI run 37585922558 green at 07:20:43Z; its `deploy-backend` job 112678454242 ran
  only the change detector and **skipped all nine deploy steps** — the sixth live proof of the PR #1101 correction.

## R1 — unchanged by this record

| Item | State | Evidence / rule |
|---|---|---|
| Complete original input-manifest comparison | BLOCKED — the component manifests enumerate none of the 69 inputs (0 / 69); the two-part custody clarification of record 14 is with the founder; no answer relayed yet | Record 14 |
| Allowance | 180 / 10 / 20 / 12 / 2 / 44 charged / 136 remaining; nothing reset | Record 14 |
| Release | **NOT_RELEASED**; `handbacks/cto/R1-STATUS.md` unchanged | Record 05 gate |

## Registration (closure 165)

`control/source-context-exclusion-165.json` (313 → 488): resolves closure 164's `record-14-reviewer-01` to
`launched-2026-10-07T0655Z`; resolves `runtime-records-gate-review-01` to its 173 launch-time identities — the three lens
contexts and five refuter contexts of workflow `wf_1cf4ba90-7d3` (registered per the lens-label convention; the agent id is the
identity), the delta reviewer `launched-2026-10-07T0747Z:pr-1110-delta-reviewer-01` (one context across its 22 delta
checks) and the 164 agents of the adversarial sweep and the six verification workflows (registered as
`claude-code-workflow:<workflow>:<agent>:<label>`; read-only against the records in isolated worktrees; results returned to the
chief only); pre-registers this record's single PR reviewer (`record-15-reviewer-01`). Closure 164's label named the three-lens
workflow and its delta reviewer; the 164 sweep and verification agents were launched under it without being named there. That is
stated here, not hidden: they are registered now as actual contexts, with no eligibility. The Codex connector is GitHub's own app, not a
registered context. No context gains source A/B, reconciliation or blind financial judging eligibility; all earlier identities and
adverse histories retained.

## Spend

Since record 14: **479 DeepSeek calls; USD 0.158085** (the 14 `copilot-eval` runs on PR #1110);
28 ledger events (7–34: 13 reservations written before their run, one recorded after the founder's trigger,
14 settlements, one of them carrying a correction);
0 active reservations; conditional unreserved 22.527800 → 22.369715; holds unchanged; paid dispatch HELD. External mutations
by the chief: PR #1109 body edited, marked ready, squash-merged `f26debcb`; PR #1110 opened (draft), body edited, marked ready
9 times by the chief (once by the founder) and converted back to draft 9 times, 4 pushes while ready (each under a
reservation), two force-pushes of its own branch while in draft (`c4b065bf` → `6a7a3f27` at 09:35:21Z and `23c10170` →
`e1ab73e4` at 12:47:14Z; no run fired on either replaced head), 4 `@codex review` requests, 18 Codex threads answered and resolved, three standing-down comments,
squash-merged `e144ef3d`; the private ledger artifact republished 28 times (versions 8
to 35); branch restarts and pushes; this record's PR.

## Founder actions this record needs

1. **Custody clarification (unchanged from record 14):** relay the two-part question and its six return fields.
2. **D3 numbers:** unchanged, held (record 08 patch `21322a05…`).

Nothing in this record releases input, dispatches the planner, runs an export or operator leg, admits capacity, invites anyone,
changes a flag, adds load, implements E09, redefines record 05's gate or changes the accepted reporting contract.
