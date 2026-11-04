# In the turn that merges to main or re-runs a main job, read #1848 first: a release window holds both

Date: 2026-11-04 · Area: ops / release

**Context.** On 2026-11-04 the founder approved a bounded screenshot sequence: set up, verify, enable. Each step is
an Ops run that binds the exact SHA it was dispatched on.
- At 13:21 UTC root posted the window on #1848 (6631725489): "keep main stable at `aee41fa` ... Avoid all main merges
  during the window because even records-only CI blocks Ops; work on PR branches may continue."
- At 13:46 root dispatched provisioning run 41841164865, which waited for the founder's exact-run approval.
- At 13:56 #2009 merged to main (`8e712d806`). It changed backend and browser tests, docs and records, and
  deployed nothing. Its merge turn read its own checks, reviews and Codex receipts and main's push runs. It did not
  read #1848: `ops-read-main-and-every-slot-claim-before-a-backend-merge.md` reads slot claims before a backend merge,
  and #2009 was not one.
- The merge voided the waiting run: its approval binds the dispatched SHA, and its check refuses once main moves.
  Root cancelled it at 13:59. No cloud provisioning ran (14:00, 6632592300).
- At 14:17 the same session re-ran main's failed `backend-tests` job (run 41842721758, attempt 2). At 14:21 root asked,
  on #2009 (6633067809), to keep the failed result and to hold main merges and main-CI re-runs during the window. At
  14:42 the session posted a verification on #2009 that called main green from the re-run. It had not read the 14:21
  comment: neither #1848 nor that comment reached it as a notification until 17:06.

**Rule.**
1. In the turn that merges anything to main, a tests-only, docs-only or records-only merge included, read the comments
   posted on #1848 since the last release you have read, and the comments on the pull request you merge. A release
   window, a freeze, an Ops slot or a slot claim holds the merge until its owner posts the release.
2. A re-run of a job on main is main activity too: Ops waits for main's runs, and the result it leaves is evidence.
   During a hold, do not re-run a main job. Investigate the failure locally and report it on the pull request.
3. Before posting a verification on a merged pull request, read the comments posted on it and on #1848 since the merge.
   A request addressed to the merging session is answered there, not overtaken by the verification.
4. A notification is not the channel: comments on #1848 and on a merged pull request can reach the session hours late
   or not at all. Read them where they are posted.

**Gate.** Review-checked. No check on a pull request runs at the merge call, and a window lives in a comment, so no
check can see it at that moment. The rule lives in the merge turn's reads, beside
`ops-read-main-and-every-slot-claim-before-a-backend-merge.md` and `ops-read-the-reviews-in-the-turn-that-merges.md`.

**Evidence.**
- #1848: the window 6631725489 (13:21), root's report of the merge 6632592300 (14:00), and the session's
  acknowledgement 6636990408 (17:09).
- #2009: root's request 6633067809 (14:21) and the session's verification 6633556334 (14:42).
- Runs 41841164865 (provisioning, cancelled at 13:59) and 41842721758 (main on `8e712d806`: attempt 1 failed at
  14:15, attempt 2 started at 14:17).
- #1957, 6636582830: root's account of why the merge voided the approval check.
