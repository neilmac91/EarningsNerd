# Decision record 26 — record 25 merged (twenty-first deploy-skip proof); Codex clears #1281's `3c52519`; E19 built as #1297 and redesigned at a relayed request, no blocker found but its second review four refuters short, its release with #1281 held for the founder's go; main moves under #1281 (another writer's #1306), a todo conflict prepared, not pushed; two other writers' deploys read back; ledger events 63–64; closure 177

Recorded 2026-10-13, by the successor chief (`https://claude.ai/code/session_011jZyZqfNWZRqiFNWfTc3u8`).
Context: record 25 merged to main as `dc2d2d4b` (PR #1294, 2026-10-13T09:08:16Z), and the records branch `claude/stoic-wright-6jeujo`
was reset to it before this record's first commit (closure 177, `45aed08`, pushed 09:12:53Z). Record 25's counts ran to 06:59:31Z;
this record's run from there to 18:31Z (this record's commit), with its push and the `@codex review` request after it. PR #1281 (the
secret-output follow-ups) is not merged at this record, and E19, the value-level Sentry scrubber (PR #1297, stacked on #1281's
branch), is not folded into it: both wait for the founder's go (Plan, item 1). This PR changes only files under `tasks/`: closure
177's exclusion record (its first commit), this record, the checkpoint, the appointments file, the archive ledger's record-26 entry,
and `tasks/todo.md`'s handover block and F22. No application code, workflow, migration, cloud, IAM or production change, and nothing
under `backend/`, so its merge deploys nothing. This record's dispatches: one `deepseek-balance` dispatch (07:54:38Z; its reading at
07:54:43Z, before event 63) and one read-only `describe-service` (17:51:36Z).

## Record 25 merged (PR #1294): review record closed; twenty-first deploy-skip proof

After record 25's cutoff, Codex reviewed `889c256` (07:03:50Z; one P2: the open-PR snapshot's list missed #1295, which opened between
the chief's two queries; fixed in `db55984`, committed 07:04:35Z) and `db55984` (07:08:30Z; no major issues). `record-25-reviewer-01`
(closure 175; agent `a917032fd909fbe4a`, launched 07:00:46Z; one context for the review and its deltas) bound **no blocker** to every
head it checked: `889c256` (07:31:59Z; two should-fixes and nine nits, applied in `db55984` and `bc5a470`), `132dd3b` (four
should-fixes and seven nits, applied in `4724763`), `c065a87` (one should-fix and five nits, applied in `8ecdf02`) and `8ecdf02`, the
merged head (no should-fix; one optional nit not taken, as the counts it names are dated elsewhere in the record). Codex reviewed
`bc5a470` (two P2s: the handover block after #1281's push, and other writers' rows still calling merged PRs in flight; fixed in
`132dd3b`), `132dd3b` (one P2: the checkpoint said no reservation was active while event 63 was; fixed in `4724763`) and `4724763`
(one P2: E16's line still read PREPARE although #1281 implements it). That last one the chief answered in `c065a87` without editing
E16's line, which #1281 replaces when it merges: editing it would have made the second of the two PRs to merge conflict, and a
conflict on #1281 would have cost a re-run of its paid checks; the handover block names #1281 as E16's implementation instead. Codex
found nothing on `c065a87` and `8ecdf02`. The records gate passed before each commit, and gitleaks over the PR's eight commits found
nothing. The chief marked the PR ready at 08:43:24Z (no paid run fired: the PR touched only `tasks/`). Codex's ready-triggered review
of `8ecdf02` found nothing (08:47:32Z), `review-gate` passed at 08:47:46Z and the e2e job at 08:53:48Z. The chief squash-merged it at
09:08:16Z as `dc2d2d4b` with an explicit title and message, pinned to `8ecdf02`, with main idle at `3da1c520` (disclosure 1(a): about
fifteen minutes later than it could have been). Main CI run 38374165690 passed; its `deploy-backend` job (115226387956) skipped every
deploy step, 6 to 17, after its detector (step 5) succeeded: the twenty-first deploy-skip proof (09:28:53Z). Both merge trains were
told at about 09:10Z; each replied that none of the drafts reusing the record's todo IDs is theirs (#1286 is on
`claude/project-thread-k8wfz3`; #1288, #1289 and #1291 on `claude/brave-bohr-hai5vi-*` branches), so those drafts' owners renumber
theirs, and the chief renumbers its own lines if an ID is taken when they merge.

## #1281 at `3c52519`: the second review's fixes checked, CI green, Codex's hosted review clean

The chief pushed `3c52519` (the second review's fixes; committed 07:39:08Z) at 07:55:26Z, after ledger event 63 reserved its two paid
runs (spend, below). Requested at 07:55:34Z, Codex answered with its usage-limit reply (07:55:42Z). CI run 38365809146 passed on the
head: the `eval-baseline` run's regression gate passed with the two advisory warnings the PR's earlier runs showed (mean untraceable
dollar figures 1.171; mean citation fidelity 0.8454 against the pinned 0.9648), on a head that changes no prompt, model or summary
code; the Copilot fidelity run (38365809062) passed; and the backend, frontend, migrations, secret-scan, lighthouse and e2e
(08:18:17Z) jobs passed.

The second, independent review's same-context delta check (`secret-output-followups-second-review-01`) bound **no blocker** to
`3c52519` at about 08:12Z: both should-fixes and nits 1–6 applied correctly, its ten earlier mutations and six new ones on the new
code each caught, the gate file's 296 tests passed, and the full suite's only failures were the 33 acceptance-tooling tests whose
fixtures sit under an excluded directory. It raised no should-fix, six nits (D-1 to D-3 and D-5 to D-7) and one merge-readiness item
(D-4: without an override line the review gate would fail, as Codex could not review the head). The chief edited the body at
08:14:08Z: a `Review override:` line naming that review and its delta check as the substitute for Codex's review, and the two body
nits (D-2: the migration step's reach and the scrubber's blind spots stated exactly; D-3: nits 1–6 applied, nit 7 declined). The
review gate passed at 08:14:34Z. The documentation nits D-1 (the lesson's `compare_digest` advice leads to code the gate rejects), D-5
(the `DATABASE_URL` row's IAM example: the deploy's migration step and `ops.yml` split the URL without percent-decoding) and D-6 (the
gate module's docstring) were carried to E19, the next change to those files; D-7 (a possible duplicate E19 line in #1294) did not
apply. The same context then checked the body (about 08:21Z): accurate, carrying the three nits acceptable as each fails safe, and one
wording slip of its own, fixed in the body at 08:21:56Z together with the merge order (record 25 first, so #1281's todo pointer to it
resolves).

Codex reviewed again from 11:35Z (#1297's first head, below). At 11:36Z the chief requested its review of `3c52519` (comment
6144652583), and Codex found no major issues (11:39:16Z): the hosted review the relayed comment (next section) distinguishes from
substitute evidence. The chief answered Codex's open P2 thread on the value-level scrubber at 11:39:37Z, naming #1297 as its fix and a
release dependency (the thread stays open until #1297 lands), and edited the body at 11:40:12Z: the `Review override:` line withdrawn,
Codex's hosted review recorded, #1297 named. #1281 stayed open, ready and green at `3c52519`, with nothing posted on it after
11:40:12Z; it was mergeable (`clean`) until main moved at 18:01:35Z (#1306, below), and since then it conflicts with main in
`tasks/todo.md` alone.

## The second relayed comment: E19 becomes a release dependency

At 09:06:49Z a comment appeared on #1281 under the founder's login, posted through the Codex GitHub app as "AI-assisted release
coordination": "the remaining value-level Sentry redaction finding must be resolved before I recommend releasing the merge hold.
Passing current-head CI and Copilot does not resolve that review finding. A focused companion PR is acceptable for review clarity, but
please track it as a release dependency rather than describing after-merge deferral as an adopted decision. Preserve the distinction
between substitute-review evidence on 3c52519 and hosted Codex clearance. Neil’s general hold pending another agent’s review remains
in effect; nothing in this comment authorizes merging or additional security scope." As with the first relayed comment, the chief
cannot verify a relay, and holding costs only time; E19's placement was the open founder choice, so the chief follows the comment. It
acknowledged on the PR at 09:09:07Z (the hold stays; E19 is a release dependency of #1281, built as a focused companion PR stacked on
#1281's branch; the override line is substitute-review evidence, not Codex clearance, Codex having last reviewed this PR on `54c954c`)
and edited the body to say so at 09:09:28Z. After the chief's status report, the founder wrote in the chat at about 09:47Z: "Ok.
Continue when ready". The chief read it as approval to build E19 first, and to ask for the merge confirmation once E19 was ready.

## E19: the value-level Sentry scrubber (`sentry-value-scrubber-pr-01`)

**Design.** The workflow `wf_90ae5e9c-de0` (09:15:42Z to 11:22:54Z; three agents) produced two independent designs, each implemented
and proven in its own exclusion-safe copy of `3c52519`, then a verified synthesis. The minimal design read the values once at startup
and moved the secret-field rule into `app/config.py`. The defense-in-depth design re-read them per item, kept the rule in `main.py`
and the gate as separate copies, matched eight escaped forms, hooked logs and metrics too and named the setting in its placeholder.
The synthesis kept one value scrubber, built once at startup, on every hook that carries text: `before_send` (errors and check-ins),
`before_send_transaction`, `before_send_log` and `before_send_metric`. It withholds each secret setting's value, stripped, and each
connection URL's password as written and percent-decoded (in a URL missing its `@host`, the text a parser reads as the port: Codex's
case), at 8 characters or more, longest first, as the SDK's plain `[Filtered]`; a hook that raises drops its item, so a failure sends
nothing. It found that the SDK's own logger and metrics API sends past `before_send` and the event scrubber whatever `enable_logs`
says, which is why the log and metric hooks are wired. It keeps the rule in `main.py`, with the gate's own copy as the independent
oracle its tests iterate, so `app/config.py` does not change and no paid evaluation run fires. The chief chose the plain placeholder
and the rule's copy, and added one pin: the gate's fixture refuses `enable_logs`, because with Sentry logs on a log record's `extra`
value that is not text, a mapping or a list reaches Sentry as its repr, built after the hook. The chief tracks two of the synthesis's
open questions elsewhere: `app/database.py`'s refusal message still advises percent-encoding, which the deploy's split does not decode
(todo E23 in #1297; E24 once main is merged in, as main's E23 is now another writer's); and the startup log's quote of a host-missing
URL's digits, accepted since #1281.

**Implementation and gates.** The chief applied the synthesis in the worktree of the branch
`claude/stoic-wright-6jeujo-sentry-value-scrubber`, stacked on #1281's head, after checking each file against the checksum the
synthesis reported, reviewing the diff and confirming that the pinned `sentry-sdk==2.71.0` has every hook it sets and sends each
hook's returned item. Gate file: 314 passed (296 on `3c52519`). Full backend gate (the records-gate wrapper, `backend` scope): ruff
and bandit clean; pytest 33 failed, 7,315 passed, 39 skipped, the 33 failures the acceptance-tooling tests whose fixtures sit under an
excluded directory (the same 33 fail on `3c52519`). Commit `d71c081`; gitleaks clean. Pushed at 11:31Z as draft PR #1297 against
#1281's branch; no head of #1297 fired a paid run (its `eval-baseline` job skipped every paid step, and no Copilot fidelity run fired:
no file under `backend/app/`, `backend/evals/` or `backend/prompts/` changes), so no reservation was needed. Codex reviewed `d71c081`
at 11:35:58Z: no major issues.

**The first high-tier review.** The workflow `wf_c08be321-99a` (11:32:10Z to 13:02:36Z over `d71c081`; thirteen agents: three lenses
and two refuters per blocker or should-fix, on the models AGENTS.md section 5 names for the high tier; this machine's four processors
let two agents run at a time) found **no blocker** in any lens. Correctness: one should-fix (C-1: the gate's `enable_logs` pin missed
the logging integration's second switch, `capture_sentry_logs`, and a log record's `extra` value that is neither text, a mapping nor a
list passed the hook unchanged, its repr built by the SDK after the hook) and two nits (C-2: an SDK log whose body is not text, sent
as its `str` after the hook; C-3: the gate's transport dropped envelope and item headers, and no carrier named a transaction with the
secret). Rules-and-brief: three should-fixes (RB-1: the body did not say how the stack lands; RB-2: the body's evidence sections were
placeholders in the snapshot it read; RB-3: `app/database.py`'s refusal message advises a percent-encoding the deploy's split does not
decode, and nothing tracked it) and two nits (RB-4: two summaries overclaimed; RB-5: no `_PASSWORD` suffix in either copy of the
rule). Tests-and-gates: one should-fix (TG-1, the same as C-3) and three nits (TG-2: "read once" was not pinned; TG-3: the fragment
check read URL scaffolding; TG-4: the fail-closed case sent no check-in); its mutations confirmed every other gate. The refuters: C-1
and RB-3 stand (two of two each); RB-1 and TG-1 stand by one and fall to nits by the other; RB-2 falls to a nit (two of two: the body
was filled at 11:48:07Z, after the lens's snapshot).

**The fixes** (eight commits, each gated before its push, none firing a paid run). `85f6019` (pushed 12:12:00Z): the walk is total
(None, booleans and numbers kept; mappings and lists walked; any other value turned into its repr with the SDK's `safe_repr` and
scrubbed there), which closes C-1 and C-2 at the root, so the `enable_logs` pin went (its reason gone); `_PASSWORD` joined both copies
of the rule; the transport keeps envelope and item headers and the span carrier names its transaction with the secret; "whole value"
in the two summaries; todo E23 for the refusal message. `06a463e` (12:21:43Z): the read-once, check-in and URL-scaffolding nits.
`ceae996` (12:41:22Z): Codex's P2 on `06a463e`. `37211fa` (13:18:43Z): the delta reviewer's first nits. `9e987c4` and `d4c7290`
(13:37:58Z): Codex's P2 on `37211fa` and the delta reviewer's next nits. `3804b09` (13:44:19Z): Codex's P2 on `d4c7290`. `942d99b`
(14:08Z): the delta reviewer's fourth round. Gate file 296 → 342 tests on `942d99b`; full backend gate there: ruff and bandit clean,
pytest 33 failed, 7,343 passed, 39 skipped, the 33 the acceptance-tooling tests. Mutation proofs, each on committed state: 40 runs on
`d71c081`, 43 on `06a463e`, 46 on `ceae996`, 57 on `d4c7290` and 61 on `942d99b`, each as intended (runs on `85f6019` and `37211fa`
stopped early once a newer head superseded them, every finished run as intended).

**Codex on the first design.** `d71c081` and `85f6019`: no major issues (11:35:58Z, 12:15:08Z). `06a463e`: one P2 (12:27:13Z): a weak
secret equal to a protocol word, `IP_HASH_SALT=event_id` in Codex's example, renamed the event's own `event_id`, which the SDK reads
after the hook, so the capture raised. The chief confirmed it in the SDK's source and found it wider: after the hooks the SDK reads an
item's own keys (an event's `event_id`, a log's `attributes`, a metric's `name`), compares an event's `type` (`check_in`,
`transaction`) and reads a profile's `contexts.trace.trace_id`. `ceae996` kept those three positions as they were and scrubbed
everything else, with a gate case setting nine secret settings to protocol words; three mutations each fail only that case (disclosure
1(c)). `ceae996`: one P2 (12:47:53Z): keep nested protocol fields too (a child span's `trace_id` and timestamps collapse into one
`[Filtered]` key under such a secret). The chief declined it on its thread (12:57:18Z): nothing could crash or leak, the path needs a
misconfigured, word-like secret, and the fix seemed to need a hand-kept map of Sentry's event schema; it put the call to the founder
in the chat at about 13:00Z. The third relayed comment reopened it (below). `37211fa`: one P2 (13:23:05Z): a weak secret overlapping
the placeholder (`IP_HASH_SALT=Filtered`) rode inside every `[Filtered]`. The chief found it wider (a secret starting with `Filtered]`
forms from the placeholder and the text beside it) and fixed it in `9e987c4`: the placeholder is the first of six that no secret
overlaps (inside, around or across either edge), checked once at startup; if every one is overlapped, the options fail and Sentry
stays off. `d4c7290`: one P2 (13:43:22Z): E23 belonged first under Engineering, as the open items run newest first; fixed in
`3804b09`, where Codex found nothing (13:49:32Z). `942d99b`: one P2 (14:14:05Z): an event processor registered through an assignment
alias escaped the kept-fields scan; the second design removed the scan's reason (below). Each P2 was answered on its thread; every
thread is resolved.

**The delta reviewer** (`ae31331869c7cec1a`, 12:18:08Z to 17:00:45Z, one context over every round, bound first to `06a463e` and then,
by message, to each later head) bound **no blocker** to `ceae996` (13:07Z), with every finding above closed but RB-1 and RB-2 on the
live PR bodies (its D2-6, a should-fix, met when the bodies were republished), and nits D2-1 (the trace header's contents unchecked),
D2-2 (a per-item re-read that bypasses `_secret_values` survived the read-once pin), D2-3 (a check-in's loss reason unchecked), D2-4
(two wordings), D2-5 (the limits of a weak secret equal to a protocol word understated) and D2-7 (optional: a scan for hand-built
Sentry events and trace contexts, so the kept fields' premise is gated), all applied in `37211fa`, where the three survivors it named
fail as `M47`–`M49`. Its check of `37211fa` (13:31Z): **no blocker**; two nits, applied in `d4c7290`: the kept-fields scan widened to
a scope or a client held in a name, a trace context set by keyword and an event processor (D3-1; planted calls fail as `M55`–`M57`),
and two lesson sentences (D3-2). Its check of `d4c7290` (about 13:55Z): **no blocker**; one should-fix (D4-1: the overlap cases with a
placeholder inside a secret and across the left edge were unpinned), nits D4-2 (an event processor registered by decorator or alias),
D4-3 (the startup `try` that turns Sentry off when the options fail was ungated) and D4-5 (documentation), and one optional item,
declined (D4-4: caching per node, measured at about 0.27 µs a node); `942d99b` applied the rest, and four mutations (`M58`–`M61`) each
fail the case meant for them. Its check of `942d99b` (about 14:15Z): **no blocker**, one optional nit (D5-1: a dotted decorator
unpinned), carried and then moot once the second design removed the scan.

**The third relayed comment.** At 14:05:00Z a comment appeared on #1297 under the founder's login, posted through the Codex GitHub app
as "AI-assisted coordination": "the current-head review and marker-collision fix are useful progress. Before recommending release,
please explicitly reconcile the retained child-span/check-in protocol-key tradeoff with the request for schema-aware regression
coverage. A clean later review does not by itself settle a previously declined finding, and I have no verified founder acceptance of
that telemetry-loss tradeoff. Prefer preserving required structural keys and scrubbing values/user-controlled payload keys, or provide
a concrete safety argument and reproduction explaining why that alternative is unsuitable. Neil’s general merge hold remains in force,
including the proposed stacked merge into #1281. Preparation and local validation may continue; do not infer new merge or paid-run
authority from the proposed sequence." The chief cannot verify a relay; it asks for no step outside the hold, and the chief follows
it: the fold and every paid run wait for the founder's explicit go, and the declined finding is reconciled by its preferred option.

**The second design.** `2cc3780` (pushed 14:55:36Z) keeps nothing whole any more. Every value is scrubbed; a key stays as it is only
when it is exactly one of the protocol's own words (54 then, each at least 8 characters, read from the items the SDK builds under
main's options; a shorter key can hold no secret above the floor); an item's `type` stays only when it is one of its protocol types. A
child span's `trace_id` and timestamps now keep their names under such a secret, which settles the declined finding. Keeping nothing
whole also answers Codex's alias P2 on `942d99b` at its root: no processor, hand-built event or hand-set trace context can carry a
secret past the hooks, so the kept-fields scan and its seventeen self-tests went and a behaviour test replaced them. The gate derives
the structure from the SDK's own items on every channel, not from main's list, and fails on any lost key. The chief answered Codex's
two threads (15:00:43Z and 15:01:16Z, then resolved them) and the relayed comment (15:01:52Z): structural keys kept, values and
user-controlled keys scrubbed; the safety argument (a kept key is a public protocol word, which can hold a secret only when the secret
is that word, and a word missing from the list is scrubbed again: telemetry lost, nothing leaked); the residual (a weak secret equal
to a protocol value, such as a check-in's `in_progress`, still replaces that value, since values stay scrubbed); and the hold,
standing.

**The second design's checks.** The design checks (workflow `wf_13b2a427-187`, 14:30:21Z to 15:19:52Z; two contexts, each probing its
own export of `942d99b`) found the core sound. The vocabulary-completeness check found three protocol names missing (`fingerprint`,
`replay_id`, `user_segment`), asked for a reverse assertion (main's list may hold no word the capture lacks), and gave the
reproduction the comment asks for: a rule keeping keys by position alone sends a secret held as a key at `contexts.job.<secret>` or
`logentry.params.<secret>`, which the exact-word rule withholds. The adversarial check raised one major finding (F1: by name alone, an
app's own key spelled like a protocol word, `username` in `extra`, `tags` or a log's attributes, kept a weak secret equal to it,
`IP_HASH_SALT=username`) and seven more: a text subclass posing as a key (F2), `replay_id` and `user_segment` missing (F3), a gate
that passed with entries removed or dead (F4), the enum residual (F5, documented), the floor (F6), `_meta` unwalked (F7) and
documentation (F8). `2483213` (15:47:41Z) applied them: a protocol word is kept only when it is exactly text and sits outside user
data (below `data`, `tags`, `extra`, `attributes`, `headers`, `cookies`, `env`, `vars`, `params`, `measurements` or `modules`, or in
an app's own context: any but `trace`, `runtime` and `response`); 57 words; the reverse assertion, the SDK pinned at 2.71.0, the
contexts compared exactly and `_meta` walked; an end-to-end case with protocol words as user-data keys, eleven per-field cases and a
key-type case; and, after a probe found two survivors (`M63`, `M64`: a prefix and a substring match), a user key that holds the secret
without equalling it (`username.<token>`).

The second high-tier review (workflow `wf_0f0826ee-035`, from 15:02:49Z over `942d99b..2cc3780`: three lenses, security, SDK protocol
fidelity, and gate, tests and docs, then two refuters per finding, on the models AGENTS.md section 5 names for the high tier) found
**no blocker and no major finding** in any lens. Protocol: PF-1 (minor: `fingerprint` missing, so a weak secret equal to it renamed an
error's own key), PF-2 (nit: the replay fields a baggage header carries) and PF-3 (minor: the capture's reach and the claims about
it). Security: SEC-1 (minor: an attachment's bytes pass no hook, and nothing gated attachment writers once the scan went), SEC-2 (nit:
a `type` that is a list or a dict made the hook raise and drop the event) and SEC-3 (nit: `fingerprint`, as PF-1). Gate: F1 (minor: a
list's items shared one path, so a key lost in one span passed), F2 (nit: `distribution` unexercised), F3 (nit: the behaviour case
lacked positive assertions), F4 (nit: a comment overclaimed) and F5 (nit: the capture's reach). Refuters: PF-1, SEC-1 and SEC-3 stand
(two of two each), PF-3 stands as a nit (two of two), PF-2 and SEC-2 fall (two of two each); of the gate lens's, F1 stands (as a minor
finding by one refuter, a nit by the other), F2 and F3 stand as nits (two of two each), and at this record's cutoff F4's two refuters
were running and F5's had not started (record 27 and #1297's body take their verdicts). Every finding was fixed whatever its refuters
found: PF-1, PF-2, PF-3 and SEC-3 in `2483213`; SEC-1 (the hook drops a hint's attachments, which the SDK would send past every hook)
and SEC-2 (a `type` that is not text is walked like any value) in `2d0ce7f` (16:24:26Z); F1 to F5 in `6782126` (16:38:27Z): list items
compared by index, a distribution metric captured and taken as a weak secret, positive assertions, an outbound HTTP call in the
capture and its reach stated.

The delta reviewer's sixth round, over `942d99b..6782126` (16:55Z), bound **no blocker**: every disposition above checked as applied,
its own mutations at `2d0ce7f` and `6782126` with no survivor against the gate, and one should-fix (D6-1: a hand-built event whose
`type` was a text subclass posing as `transaction` sent its own text). `f5a601e` (16:57:40Z) fixed it as specified, keeping an item's
`type` only when it is exactly text, with a gate case that fails against `6782126`'s `main.py`; its check of `f5a601e` (about 17:00Z):
**no blocker**. Codex reviewed every head of the second design and found no major issues on any: `2cc3780` (15:00:26Z), `2483213`
(15:52:58Z), `2d0ce7f` (16:29:06Z), `6782126` (16:43:06Z) and `f5a601e` (17:02:32Z).

**Where E19 stands.** #1297's head is `f5a601e`, fourteen commits on #1281's `3c52519`, still a draft. Gate file: 342 passed (296 on
`3c52519`). Full backend gate: ruff and bandit clean; pytest 33 failed, 7,343 passed, 39 skipped, the same 33 acceptance-tooling
tests. Mutation proofs: 156 runs on committed `f5a601e`, each on a fresh `git archive` export without the two excluded directories:
152 killed and the four intended survivors (the control; a twin on `3c52519`, where the same option survives, so the new fixture pin
is what catches it; and two item types shorter than the 8-character floor, which no secret can alter). Each protocol word, user-data
field, SDK context and longer item type, removed one at a time, fails the gate, so no entry is dead. Earlier heads of the second
design: 119 runs on `2cc3780` and 144 on `2483213`, as intended, and 86 of 155 on `6782126` before `f5a601e` superseded it. gitleaks
over the fourteen commits: clean. CI on `f5a601e` passed (backend, frontend, e2e, lighthouse, migrations and secret-scan;
`eval-baseline` skipped every paid step). The chief republished the body with the evidence at 17:30:36Z and read it back equal. At
about 17:31Z it asked the founder in the chat for a go on the release sequence (Plan, item 1); there was no answer by this record's
cutoff. The second high-tier review is incomplete at the cutoff: the gate lens's F4 and F5 refuters had not reported, and missing
review output is never clearance (AGENTS.md section 5), so the release waits for them (Codex's P1 on this PR's first record head). The
rule as it stands: every value is scrubbed; a key stays as it is only when it is exactly text, one of 57 protocol words and outside
user data; an item's `type` stays only when it is exactly one of its five protocol types; a hint's attachments are dropped. The
documented residual is over-redaction only: a weak secret equal to a protocol value, such as `in_progress`, replaces that value.

**Main moves under #1281.** At 18:01:35Z another writer's records PR #1306 merged as `7933ee20` (its deploy skipped, below). It added
two Engineering lines at the top of `tasks/todo.md`, E23 (assigned to the chief: two other writers' Copilot draws to settle in the
private ledger; Spend, below) and E22, just where #1281 replaces E16 with E19, E18 and E17 and #1297 replaces E19 with its line on
`app/database.py`'s refusal message, which #1297 numbered E23. GitHub has reported #1281 as conflicting with main since then
(`dirty`); a trial merge of main into #1281's head and into #1297's conflicts in `tasks/todo.md` alone. Resolving it needs a push to
#1281's branch, which fires the paid runs the hold covers, so the chief prepared it locally and pushed nothing. In an exclusion-safe
scratch worktree, it squashed #1297 onto `3c52519` (the tree equal to `f5a601e`'s) and merged main into that commit: main's E23 and
E22 kept, E16 gone (#1281 implements it), #1297's line renumbered E24 (main's E23 is now another writer's, and the chief renumbers its
own lines when an ID is taken) and E18 and E17 kept. Main's #1302 and #1305 moved the backend's dependencies (among them fastapi,
pydantic, openai and stripe 16), so the chief built a fresh environment from main's requirements to run the full gate on that merge:
ruff and bandit clean; pytest 33 failed, 7,343 passed, 39 skipped, the failures the same 33 acceptance-tooling tests as on `f5a601e`.
The release order changes accordingly (Plan, item 1): fold first, while #1281 still conflicts, since GitHub runs no pull-request
workflow on a conflicting pull request; then push the merge of main once, so one paid round runs.

## Production after record 25: six main runs classified; two deploys read back

Main moved six times after record 25's base. Each run is classified from its `deploy-backend` job's step conclusions (read through the
platform's REST API, read-only: for each skipped run, steps 6 to 17 all `skipped` and the detector, step 5, `success`), and each
deploy from its log through the redacting filter (every Cloud Run default-domain host, signed query, address and token replaced; only
step markers, pins, migration counts, revision and health lines kept, and one line of the allow-listed env pairs per echoed
`--update-env-vars` or `--set-env-vars` line; the raw copy deleted):

| Merge | PR | Main CI run | `deploy-backend` job | Outcome |
|---|---|---|---|---|
| `dc2d2d4b` | #1294 (record 25) | 38374165690 | 115226387956 | every deploy step skipped (twenty-first proof) |
| `95ac0333` | #1304 (frontend minor-updates group; another writer's) | 38428711625 | 115414312381 | every deploy step skipped |
| `02411fbb` | #1300 (a dependency sweep record; another writer's) | 38428719575 | 115415951767 | every deploy step skipped |
| `6113751c` | #1302 (backend minor-updates group; another writer's) | 38429472853 | 115418160027 | **deployed** 16:41:19–16:45:14Z; service `earningsnerd-backend-00504-flk`, worker `earningsnerd-task-worker-00054-pjv` |
| `02fb99b1` | #1305 (stripe 16 and Checkout's payment-method field; another writer's) | 38436459638 | 115442211817 | **deployed** 17:32:57–17:36:30Z; service `earningsnerd-backend-00505-bt2`, worker `earningsnerd-task-worker-00055-j7r` |
| `7933ee20` | #1306 (the dependency sweep's release record; another writer's) | 38443416044 | 115457922943 | every deploy step skipped |

Both deploys read back as record 25's did: migrations `applied=0 skipped=43`; the worker, then the service, each serving 100% of
traffic; the scheduled jobs' images updated; the five allow-listed env-pair lines identical to record 25's (the worker
`DURABLE_TASKS_ENABLED=true`, `TASKS_WORKER_PROCESS=true`, pool 3 / overflow 0; the service pool 4 / overflow 0,
`TASKS_WORKER_PROCESS=false`, `ENABLE_INSIDER_ACTIVITY=false`; pregenerate 3 / 0; the job loop and backfill-facts 1 / 0; both SEC pins
at 1 everywhere); "Deployed 6113751 and verified healthy." at 16:45:05Z and "Deployed 02fb99b and verified healthy." at 17:36:23Z
(database healthy, Redis disabled as in production, the SEC EDGAR circuit closed). All six CI runs concluded success.
**Production now.** A read-only `describe-service` dispatch (ops run 38442055155 from 17:51:36Z, its job 115450853503
17:51:39–17:52:11Z, on main `02fb99b1`; log read through the redacting filter, raw copy deleted) returned `describe-service: PASS`:
the service `earningsnerd-backend-00505-bt2` and the worker `earningsnerd-task-worker-00055-j7r` each serve 100%, both on #1305's
image (release `02fb99b1`); both SEC pins at 1 on both; the service's `ENABLE_INSIDER_ACTIVITY` `false` (unset on the worker, where
the settings default, false, applies); the worker's invoker policy PRIVATE. So production runs #1305's deploy; neither #1281 nor #1297
has reached it. A revision serving no traffic would not show in this read.

## Spend (ledger events 63–64)

Each paid trigger of this record was reserved first, with a fresh `deepseek-balance` reading above the founder's USD 5 floor; each
settlement uses the runs' telemetry from the public job logs, read through the chief's field filter, the raw copies deleted.

| Event | Kind | USD | For |
|---|---|---|---|
| 63 | reservation | 0.790000 | the push of `3c52519` to #1281 (one `eval-baseline` run, 0.730000; one Copilot fidelity run, 0.060000); written 07:54:56Z with a reading of USD 10.38 at 07:54:43Z (`deepseek-balance` run 38365710161, job 115190220218) |
| 64 | settles 63 | 0.366538 (108 calls, all at peak pricing) | the `eval-baseline` run (38365809146, job 115190532850, 07:55:33–08:07:12Z; 70 calls, 0.352654) and the Copilot fidelity run (38365809062, job 115190532023, 07:55:33–07:58:05Z; 38 calls, 0.013884); 0.423462 released; written 08:07:48Z |

Spend this record: **USD 0.366538, 108 DeepSeek calls** (telemetry estimates, not invoices); recorded use against the authority
3.021542 → 3.388080 (1,766 → 1,874 calls); retained holds unchanged (1.881713); headroom 20.096745 → 19.730207; cumulative recorded
usage 6.805791 → 7.172329 (3,825 → 3,933 calls); **0 active reservations after event 64**. Each event was published to the private
ledger after the chief read the published document back and found it equal to the previous event's (event 63 at `51049bd6…`, event 64
at `2c856b48…`); each publication was read back equal (`2c856b48…` and `1fca2715…`). No paid trigger of the chief's followed event 64:
no head of #1297 fired one (above). Event 65, the reservation before the fold moves #1281's head (USD 1.580000: up to two rounds of
one `eval-baseline` run, 0.730000, and one Copilot fidelity run, 0.060000, in case GitHub runs CI on the fold's push as well as on the
merge's; one round is expected), is prepared and unwritten; it waits for the founder's go and a fresh reading above the floor. Other
writers' paid runs in this record's window, not reserved in this ledger and not read here: the Copilot fidelity runs on #1302's branch
(38428724525, 16:13:32–16:16:01Z, success) and on #1305's (38432391251, 16:40:12–16:42:39Z, failed at its question step), and the
`eval-baseline` job of #1305's branch (115417598365 in CI run 38432369552, 16:40:09–16:50:12Z, its baseline eval and regression gate
run); three Copilot fidelity runs on Dependabot branches failed at the same question step (38429840008, 38429940475 and 38436835915);
their calls, if any, were not read. F23, the founder row #1300 added, named a Copilot reservation (record 09's rule) as a step before
#1302's ready marking; no request reached the chief, and this ledger holds none. #1306 then added E23 on main, assigned to the chief:
settle the two Copilot draws in the private ledger (36 and 38 calls, USD 0.013691 together by that writer's reading of their
telemetry). The chief will record them, with #1305's `eval-baseline` job, which E23 does not list, after reading each run's telemetry
through its own field filter (Plan, item 3). No `deepseek-balance` dispatch in the window was another writer's.

## Disclosures

No classifier denial of the chief's this record. No chief defect is numbered: the misses below are process misses, each without
production effect.
1. **The chief's own misses** (no production effect; each corrected):
   (a) **Record 25's merge waited about fifteen minutes.** #1294 was mergeable from 08:53:48Z (its last check), but the chief waited
   for an event that GitHub does not send when a workflow run finishes, with no watcher armed for that wait, and found it ready at
   09:07:51Z. Nothing else waited on it.
   (b) **A lease push refused, harmlessly.** After the merge the chief reset the records branch and pushed with a lease naming the old
   head; GitHub had already deleted the merged branch, so the lease reported stale information and pushed nothing. A plain push
   recreated the branch (09:12:53Z).
   (c) **A result stated before its check ran.** The chief's answer to Codex's P2 on `06a463e` (12:41:31Z) said "Three mutations each
   fail the new case"; the probe that showed it ran after the answer was posted. The probe confirmed the statement (`M44`–`M46`, each
   killed by that case alone), and the head's full mutation run later agreed. Rule: state a check's result only after it has run.
   (d) **Two of the chief's own tools misfired before any test ran:** the first start of the mutation run on `ceae996` named a
   mistyped commit and stopped at its `git archive` (its empty directory removed); the first run on `2483213` stopped at two mutation
   anchors left stale by that commit (`M07`, `M48`). The runner was fixed, and from then on every anchor was dry-run checked against
   its export before each run.
   (e) **A formatter run outside CI's checks:** `ruff format` on `backend/main.py` reformatted code the change does not touch (CI runs
   `ruff check`, not `ruff format`, on that file). The chief rebuilt the file from the committed head with only the intended edits;
   nothing of the reformatting was committed.
   (f) **Reads beyond the chief's own runs:** the step conclusions of other writers' paid jobs (REST, read-only, to account for this
   window's spend); and, to confirm the absence of classifier denials and to recover the delta reviewer's side-effect lists for this
   section, the chief's own session log, matched lines only (the chief's log, not an agent's transcript).
2. **The relayed comments** (09:06:49Z on #1281; 14:05:00Z on #1297) are attributed to the founder's login through the Codex GitHub
   app; the chief did not post them and treats each as a relay it cannot verify (above).
3. **Record 25's fact-check workflow** (`wf_3acf8f6c-b19`): the production checker passed a stray `-f` on one GET (a query parameter;
   the harness saved that output to a tool-results file, unopened); the live checker read five other writers' balance lines (USD 12.86
   to 12.08) from their public job logs.
4. **The second review** (`a181b591c42bf15f5`): `git init`, `git add -A` and `git add -f` inside its own archive copies; one `git
   status --porcelain` in #1281's worktree, which refreshes that worktree's index stat cache; one `git rev-parse` there; one `rm -rf`
   with a variable path, stopped by the harness's safety check (it never ran); one `ls` of the runtime control directory in its
   archive copy; GitHub GETs only. It also saw a short-lived `.env` file at the scratchpad root at about 06:54Z (not opened; gone
   within seconds). Two agents saw one there later (the first review's correctness lens, at about 11:32–11:44Z, which therefore ran no
   test; and refuter TG-1:2, during its run (12:48–13:03Z), gone seconds later). Its origin is unknown, and no test writes a file of
   that name. A `.env` there would be loaded by `main.py`'s `load_dotenv()` in a test run from a copy below it, so every agent brief
   since 11:32Z requires a check for one on the path to `/` before each test run, and the chief ran a metadata-only watcher (names and
   sizes, never contents) from 13:03:31Z to 17:03:31Z and again from 17:41:43Z: it logged none.
5. **`record-25-reviewer-01`** (`a917032fd909fbe4a`): one `python3 -I` call without `env -i`, on its own JSON; pytest temp directories
   left under the system temp directory; nine other writers' eval job logs read through the field filter (first pass) and two more
   later, each raw copy deleted; one balance job's log (the balance line only, raw deleted); the todo patches of the open PRs read by
   GET; a pytest attempt with a tool-managed interpreter that left `__pycache__` directories in its archive copy; `git hash-object
   --no-filters` (no `-w`) on archive files; a three-way merge of copies of `tasks/todo.md` in its own directory; and, outside its
   GitHub-reads brief, one run of the shared scratchpad's `agent_times.py` (agent ids and timestamps only).
6. **E19's agents** (label `sentry-value-scrubber-pr-01`) wrote in their own directories and imported no application code outside
   pytest, except as disclosed:
   (a) the design workflow `wf_90ae5e9c-de0`: the minimal designer made a second archive, let library caches form under its own home
   directory and left output files under the harness's task directory; the defense designer built throwaway git indexes in its
   directory (removed), created and deleted a probe test and interrupted its own run; the synthesizer made two extra archives and
   throwaway git indexes (removed), created and deleted a probe test, ran about ten text-edit scripts with `-I` but not under `env
   -i`, stopped its own mutation run and removed its leftover temp directory, ran one two-second foreground sleep and left pytest temp
   sessions; logs of two of them name test ids under the excluded directories (the ids only, nothing opened);
   (b) the first review workflow `wf_c08be321-99a`: throwaway git indexes in four agents' copies; pytest's default temp directories
   under the system temp directory; read-only GETs of #1297 and #1281; refuter RB-3:2 left its own copy mutated and opened loopback
   sockets (127.0.0.1, libpq) to simulate the deploy's split, outside its brief's "no network beyond GitHub GETs"; refuter C-1:1's one
   GET for the SDK's changelog in another repository was refused (403); the app's console formatter printed the gate's fabricated
   values into two agents' tool output, no environment value;
   (c) the delta reviewer `ae31331869c7cec1a`: archive copies with throwaway git indexes, probe and planted calls in its copies
   (reverted); read-only git in the worktree (`rev-parse`, `log`, `show`, `diff`); GETs of #1297 and #1281; two GETs to another
   repository refused; one early broad grep and one verbose test run that printed the gate's fabricated tokens; one oversized output
   that the harness saved under the session's tool-results directory (unopened);
   (d) the design checks `wf_13b2a427-187`: HOME pointed at each export (library caches there); the adversarial check patched its
   export's `main.py` for one run and restored it; one `git ls-tree` (adversarial) and one `git status --porcelain` (completeness) in
   the worktree, read-only, the second able to refresh the index's stat cache;
   (e) the second review workflow `wf_0f0826ee-035` (the twenty-one contexts that had reported at the cutoff): the security lens first
   wrote three files one level above its directory, then moved them in; the gate lens ran `git status --short` and a working-tree `git
   diff` in the worktree and two Python calls outside the prescribed form (its own JSON; a package list); refuter SEC-1:1 ran one `git
   status --short` there and edited its probe with a standard-library-only heredoc outside the prescribed form; refuter SEC-2:1 ran
   `git status --porcelain` there; the protocol lens's one outbound attempt was a refused loopback Redis connection; refuter F1:1 read
   one hunk of a later commit; no GitHub calls.
   Several of the test conftest's per-process database directories under the system temp directory could not be attributed to one run;
   none was removed.
7. **Side effects of this record:** read-only GitHub requests; downloads through the platform's REST API, each raw copy deleted: two
   deploy job logs and the `describe-service` log (through the redacting filter), two eval job logs (#1281's runs on `3c52519`,
   through the field filter) and one balance log (the balance line only); one `deepseek-balance` dispatch and one `ops.yml` dispatch;
   on PR #1294 six pushes, its body edited seven times, six `@codex review` requests, five answers on Codex's threads (each resolved),
   the ready marking and the squash merge with an explicit message; on PR #1281 one push (`3c52519`), its body edited four times, two
   `@codex review` requests, an acknowledgement comment and two answers on Codex's thread (07:55:35Z, the correction record 25
   discloses, and 11:39:37Z); PR #1297 opened as a draft and thirteen pushes to the branch the chief created (no force-push), its body
   published four times, thirteen `@codex review` requests, six answers on five review threads (each thread resolved) and an answer to
   the relayed comment; this PR opened as a draft with closure 177; two ledger events published to the private ledger; cross-session
   messages to both merge trains at about 09:10Z; eight self check-ins armed; four workflows and two background agents launched
   (`record-25-reviewer-01` under closure 175, the rest under closure 177's `sentry-value-scrubber-pr-01`); the chief's local gates
   (in the worktree) and mutation runs (in exports of committed heads); a scratch worktree (exclusion-safe) holding two unpushed
   commits, the fold's and the merge's preparation, and a fresh virtual environment built from main's requirements; one read of the
   account's routine list, which returned other sessions' routines too (data only, not acted on); and, on the records branch, main
   merged in (`238eafc`) before this record's commit. These counts run to 18:31Z (this record's commit), with its push and the `@codex
   review` request after it; every later action is record 27's.

## Plan

1. **#1281's release with #1297 waits for the founder's go** (asked at about 17:31Z). On "go", once the second high-tier review's last
   refuters (the gate lens's F4 and F5) have reported and any finding they uphold is fixed and checked, since until then that review
   is incomplete, not clearance: (1) a fresh `deepseek-balance` reading above USD 5 and ledger event 65, published and read back,
   sized for two pushes (USD 1.580000), in case GitHub runs CI on the first; one round is expected; (2) the chief marks #1297 ready
   and squash-merges it into #1281's branch with the drafted title and message, pinned to #1297's head at that time (`f5a601e` at this
   record's cutoff), while #1281 still conflicts with main, so no workflow runs on it; (3) it merges main into #1281's branch with the
   prepared resolution (above), runs the full gate on that commit, pushes once and requests Codex; (4) once CI and Codex are green
   there, it asks once for the merge confirmation naming that head, then squash-merges #1281 with an explicit message once main is
   idle, verifies the deploy, settles event 65, tells the merge trains and reports. Merging deploys the backend. On "hold", nothing
   moves. Neither step starts on a relayed comment.
2. **This record's PR:** a fact-check workflow over the draft (`record-26-factcheck-01`, closure 177), then `record-26-reviewer-01`
   (closure 176; records-only rule: one reviewer context bound to the final head, with same-context delta checks); `@codex review`
   after each push; an explicit squash title and message; then the twenty-second deploy-skip proof. It touches neither the F9 and E16
   lines #1281 rewrites nor the E19 line #1297 removes, so the PRs merge cleanly in either order; the chief checks main's
   `tasks/todo.md` at each merge for IDs another writer took (F23 and E21 are now another writer's).
3. **E23, another writer's request to the chief:** record the two Copilot draws and #1305's `eval-baseline` job in the private ledger,
   after reading each run's telemetry through the field filter; one event after the release's events, or sooner if the founder holds.
4. **The second review's last refuters** (the gate lens's F4 and F5) had not reported by the cutoff; #1297's body and record 27 take
   their verdicts.
5. **Then the checkpoint's Next queue:** the COO's G3 first-customer-part review and the G4 gate; B32's qualifying retained window; R1
   waits on the founder's custody step-A answer.

## Registration (closure 177)

Closure 177 (759 → 769), pushed at 09:12:53Z before any launch it pre-registers, registers as actual this session's launches since
closure 176: the record-25 fact-check workflow `wf_3acf8f6c-b19` and its four agent contexts (convention `workflow_agent_labels`),
#1281's second, independent review (`launched-2026-10-13T0646Z`; one context, also its delta check of `3c52519` and its check of the
PR body) and `record-25-reviewer-01`'s launch-time identity (`launched-2026-10-13T0700Z`). It resolves closure 176's
`record-25-factcheck-01` and `secret-output-followups-second-review-01` and closure 175's `record-25-reviewer-01` to those identities,
annotates the review workflow `wf_844015fc-9e9` (closure 176's text cites the older convention; record 25's reviewer suggested the
note), and pre-registers `sentry-value-scrubber-pr-01` (E19's design, implementation and review, and any fix they lead to),
`record-26-factcheck-01` and `record-27-reviewer-01`. `record-26-reviewer-01` (closure 176) covers this record's reviewer. No context
gains source, reconciliation or judging eligibility; every earlier identity and adverse history is retained. This record's launches
under `sentry-value-scrubber-pr-01` (the design workflow `wf_90ae5e9c-de0`, three contexts; the first review workflow
`wf_c08be321-99a`, thirteen; the delta reviewer `ae31331869c7cec1a`, one context over six rounds and a final check; the design checks
`wf_13b2a427-187`, two; the second review workflow `wf_0f0826ee-035`, twenty-three contexts launched by the cutoff, twenty-one of them
reported, of twenty-five planned) and under `record-26-factcheck-01` and `record-26-reviewer-01` are registered as actual by record
27's closure.

## Founder actions this record needs

1. **#1281's release with #1297** (new; yours; asked in the chat at about 17:31Z): reply "go" to start Plan item 1's first three steps
   once #1297's second review is complete, its last four refuters having reported (the reservation; the fold of #1297 into #1281's
   branch; the merge of main that resolves #1281's todo conflict with another writer's #1306, so one paid round runs; Codex on the new
   head), after which the chief asks once more, naming #1281's new head, before the merge; or "hold". Merging deploys the backend. The
   relayed comments' hold stands until you say so; if either relayed comment was not yours, say so.
2. **The residual over-redaction** (optional): a weak secret equal to a protocol value, such as a check-in's `in_progress`, still
   replaces that value; the lesson records it as accepted, since production secrets are random and the path needs a misconfigured,
   word-like one. Say so if you want values preserved too: a further design and review round.
3. **Sentry search** (carried from records 24 and 25, recommended): if Sentry is configured on the API service, search it two ways.
   Events whose stack frames show a `settings` variable (coverage, precompute or facts-backfill errors): any such event stored every
   secret, so rotate them and delete the events (rotating `SECRET_KEY` signs every user out). Events with a `_require_internal_token`
   frame or on an `/internal/` route: rotate `INTERNAL_JOB_TOKEN` together with the header the Cloud Scheduler jobs send, and delete
   the events. #1238 stops events of the first kind; #1281, once merged, stops the second and stops sending frame locals at all, and
   #1297 withholds each secret's value on every channel.
4. **#1238's merge** (optional; carried from record 24): if you merged it yourself, nothing to do; telling the chief closes the
   question.
5. **The spending note** (carried from record 22): if "spending more" was meant for the DeepSeek provider authority as well, say so in
   your own words and the chief writes the ledger event; otherwise nothing changes.
6. **Squash default** (optional, recommended; carried from record 20): Settings → General → Pull Requests → "Allow squash merging" →
   "Default commit message": "Pull request title and description".
7. **Custody step A** (optional, recommended; carried from record 20): send the prepared relay (`DECISIONS-20.md`'s appendix) once to
   the custody side; if you agree, also tell the chief, in your own words, "If the answer is outcome B, I adopt record 16's form (b)
   for R1".

Record 25's founder action 3 (Codex credits) is resolved for now: Codex reviewed every head of #1297 and #1281's `3c52519` from 11:35Z
on; it reopens if Codex answers with its usage-limit reply again.
