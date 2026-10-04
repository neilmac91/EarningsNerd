# Durable checkpoint — CODE RED chief session (updated 2026-10-04T20:08:53Z)

Chief: `https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8` (runtime-reported model `claude-fable-5-1`).
Package: `earningsnerd-code-red-fable-chief-20261004.zip` SHA-256
`e5316f506477144051b77f64dde240124e5f4a8571017c79d83dc76ba7e7661c`. Main: `100fb7d6bdaf62590af19964d39c2ed732062210`.
Branch `claude/vigilant-goodall-633yx3`; first PR [neilmac91/EarningsNerd#1086](https://github.com/neilmac91/EarningsNerd/pull/1086) merged to main as
`0ad56621c9a160e809e4f35dd8087a00694de4d6` (first checkpoint commit `6cd23c3cb7032284a913ed88df08e9a58e90569d`); this revision is the second tasks-only PR
from the branch restarted at that main. Tasks-only: no code, workflow, test or production change.

## Deliverables and exact hashes (SHA-256)

| Path (under `tasks/code-red-20261004/runtime/`) | SHA-256 | Status |
|---|---|---|
| `README.md` | `2bd9fbd9b5c33e713df04cf1cb8b2de1345a5083c81da1a5fc61548301455325` | recorded (revision exception added after review nit R1) |
| `TAKEOVER.md` | `7fcb32c92c7793deacfb90c8af86db73edf0b63083d5f75d018c0b73b30013b1` | recorded (snapshot heading: observed 14:21Z, recorded 14:31Z) |
| `control/LEDGER-ACCESS.md` | `c4e3559714712292676872ca7dc637da7ae6c7ca9e3f54cdf5bf95cb552787e0` | successor ledger designated 17:39Z; **event 1 (wording correction) 20:04Z**, document SHA-256 `beef4ca0…`; paid dispatch still HELD, 0 reservations |
| `control/DECISIONS-02.md` | `6765004905aa39c91207fe695bcaad24f9ca9835d6dd915deb170efc86d549b8` | post-Astra decision set D1–D9 + refuter appendices A/B |
| `control/DECISIONS-03.md` | `7143c767914a7820ff4301d07fd1c22348b57b834d7c4eb82f1d68e7dd7980b0` | R1 bootstrap handover response; corrections to record 02 (D1 wording, D2 unit, D3/D6 telemetry) |
| `control/PRODUCTION-CONFIG-OBSERVATION-20261004.md` | `ea3689c8744023f9b627c2e0e51622bb01b7fa70382f1a70c8fac59f17c3564d` | two read-only Ops describes; no SEC budget override anywhere; one process per instance observed |
| `control/source-context-exclusion-136.json` | `f6c065fd30650547e6cdb597faca44138ccd54bc50e5d9ab63b9883c61862f9a` | 136 entries (chief added) |
| `control/source-context-exclusion-137.json` | `3f04115827cc22e0588af212eb86737dcf3c183a51118ac6443020eb6530b00f` | 141 entries (4 CPO workflow agents + COO subagent added) |
| `control/source-context-exclusion-138.json` | `a6c81a93490c89e0a9abc68c8b9bd8a4a61f49440b5f222284ff92477c9f091a` | 143 entries (two PR-review contexts added) |
| `control/source-context-exclusion-139.json` | `7c2ced05a266915920f589e4256106ad69ada639a85eacbf0d0319b7f04d9955` | 146 entries (two refuters + decisions-PR reviewer added) |
| `control/source-context-exclusion-140.json` | `37c6520da8d32d236f6acfe90484404e48c2526987d634b0d869116bf4906d31` | 151 entries (fresh source-only H20 planner + decisions-03 review contexts) |
| `control/APPOINTMENTS.json` | `9918c28eb00ae20cd550151e87657c95fb94cccae221444aa5b24e3396109921` | actual identities recorded; refuters, successor ledger, next assignments added |
| `control/REPOSITORY-SNAPSHOT.json` | `a0666c424912e25b8dab6a689494d04dbe9507cc3bd7fdeb684a0734118741e9` | observed 14:21Z |
| `control/SPEND-POLICY-STATEMENT.md` | `2a2122c5a727a0190c7ca999c241c8ff4ab2008a476ca64707a82e87e9dafa0e` | provider spend field HOLD |
| `dispatch/CPO-COORDINATOR-01.json` | `1fbbc3e057be56bea74676c9c906684412dd07e919f9023bc9226278294c640e` | dispatched, complete |
| `dispatch/CTO-ENVELOPE-HANDBACK-01.json` | `681a3526575f4e6e5abddde2f788d48215579d2467e59d81d6c20852ac41f58d` | isolated launch denied; chief authored |
| `dispatch/CTO-ENVELOPE-HANDBACK-ASSIGNMENT.md` | `13dcf2c78ebeab70f5bd9a8cb84dd4a5faafcc66a42e656d2a557310ff9abe76` | prompt kept for a real isolated session |
| `dispatch/COO-ENVELOPE-DISPOSITION-01.json` | `c09327b8d5a1a767d2e43ad8ada70983e66a228bdc5a9c6f111fa2e98e59499f` | dispatched, complete (binds CTO revision-1 hashes) |
| `handbacks/cto/R1-STATUS.md` | `fb3d032e41f460ed7e45e39de5bca4a84aeb0061438b490421b98de8018e29b7` | BLOCKED_SOURCE_OWNED_PACKING; bounded allowance granted (DECISIONS-02 D2) |
| `handbacks/cto/envelope/CURRENT-BETA-OPERATING-ENVELOPE-HANDBACK.md` | `58ef902d0339ba812e859a764575f53828f60588b8104bf9318d79c69b0a967e` | rev 3; delivered; six rows qualified by two refuters (DECISIONS-02 App. A/B); next revision owner CTO |
| `handbacks/cto/envelope/CURRENT-BETA-OPERATING-ENVELOPE-BOUNDS.json` | `5ee84009c08f8ecf107174376f67c34084f9461b162fdbc5864e718f4ce3c8fd` | rev 3; 58 bounds |
| `handbacks/cto/envelope/CORRECTION-01.md` | `d3383d37bb7faf89824b40872a88c0687d896ff7cfbc4cfa70d9853362332625` | rev 1 → rev 2 chain |
| `handbacks/cto/envelope/CORRECTION-02.md` | `d7ffd463c59049dacb629fb1482dd94d724f0e910a1b7f23bf01870bc0fa77b0` | rev 2 → rev 3 chain (independent PR review nits) |
| `handbacks/cpo/claude-result/R1-R2-ADMISSION-STATUS.json` | `1244a8ed2d09a4c47d7b6676c61697c762e7047ee50bb451ef3ce5648e2103a1` | administrative complete; not admitted |
| `handbacks/cpo/claude-result/PROCESS-HANDBACK.md` | `74b780511b9249d32ee207cc7ed0988340aa169ce3d72dd13622c91041ed12ab` | two verifier passes: administrative pass |
| `handbacks/coo/CURRENT-BETA-OPERATING-ENVELOPE-DISPOSITION.md` | `d30bdd50125ae304ad5c4fd1c6559326d3767c0f17c1ca7ec41d895ab6fc13be` | HOLD, 8 named items; item 8 answered (D9), COO decides closure |
| `handbacks/cfo/QUEUED.md` | `2648d2782d79bd4998f4a34cd3cc6ad76e57a0dde9fe01f29bcd71896805bd26` | worker not launched |

## Decisions taken by the chief

1. Takeover accepted at 14:26Z; Astra retired; existing component owners preserved (PR1085 owner pushed `583e828d` at 14:03Z; untouched).
2. Officers appointed with actual identities in `control/APPOINTMENTS.json`; three lanes kept (quality, beta operations, existing product owners).
3. R1 worker not launched (entry condition absent); status recorded; founder-dependent item named.
4. CPO coordinator dispatched (USD 0); disclosed read-only `git status` deviation accepted as having no effect; outputs unchanged by revision.
5. CTO handback authored in the chief context after the classifier denied the isolated workflow; revision 2 corrects three placeholder fields; determination unchanged.
6. COO disposition dispatched; HOLD accepted. Items routed: founder — Slice B policy numbers (optional path to close the SEC aggregate-rate gap by configuration); CEO — live ledger access; CTO/CEO — provider account limits and egress identity (read-only, not dispatched).
7. *(Superseded by decision 12: window 06:00–08:00 UTC, Routine fires 08:10Z.)* **Next observation authorized (COO/CEO integrator decision):** one bounded read-only Ops `capacity-readout` over the Monday 2026-10-05 06:00–07:00 UTC job-overlap window, dispatched after 07:05 UTC through the existing `ops.yml` operation, receipt handed to COO. No new load, no DeepSeek call. A one-shot reminder into this session is the mechanism; if it does not fire, the next chief dispatches it from this record.
8. Paid dispatch held (live ledger inaccessible at the time). Superseded by decision 9.
9. **Successor spend ledger designated** (17:39Z, `DECISIONS-02.md` D1): private artifact "CODE RED Spend Ledger", document SHA-256 `53e8486800e193277c5be5c14a786cfeff90d3b4fa212be1c044c7343fea9f78`; chief sole writer; 0 reservations; paid dispatch still HELD. URL kept out of the public repository (D5).
10. **R1 bounded allowance** (D2): 3 focused hours of local founder-side refinement by a fresh source-only planner; USD 0; engineering-safe return; planner identity registered before any executive read.
11. **SEC budgets as risk reduction** (D3): CTO draft PR, held unready, sets `SEC_RATE_LIMIT_PER_SECOND=1` and `EDGAR_RATE_LIMIT_PER_SEC=1` on every process (second bucket found by the refuters and verified in edgartools 5.58.0 source); every scheduled overlap ≤ 10 req/s sustained; all-active 20 and first-second 3 per process (15 at Monday 07:00) honestly not bounded; numbers are the founder's. **Execution: the commit of that change was denied by the platform classifier (Production Deploy); patch handed to the founder; no draft PR opened.**
12. **Monday readout window** 06:00–08:00 UTC, Routine fires 08:10Z (D4).
13. **Records privacy, forward-only** (D5); **provisional stop conditions** (D6); provider limits recorded as published (D7); egress identity moot for the SEC cap (D8).
14. **COO item 8 answered** by two isolated refuters (D9, Appendices A/B): no arithmetic error; six qualifications accepted; B07/B08 now observed (one process per instance) from the Ops read.
15. **R1 planner registered** (`DECISIONS-03.md`, closure 140): Astra's fresh source-only H20 planner is a known source-role context; `BLOCKED_BEFORE_REFINEMENT`; 0/0/0; 170 of 180 minutes remain; refinement waits on the founder's local custody recovery (17/21 bootstrap files cloud-only).
16. **Scope confirmed, D2 unit corrected:** H20-only packing/closure refinement on the frozen H20 input set; "27" counts remaining programme dossiers, not H20 items; no expansion of the allowance.
17. **Record-02 corrections from Astra verified and applied:** D1 wording → ledger event 1 (document `beef4ca0…`, no balance change); D3/D6 → `rate_limit_hits` counts only recognised SEC 429s on backoff paths, so a flat counter proves nothing and a rise stays a stop signal; founder's patch wording revised (SHA-256 `21322a05…`).

## Retained holds and counts (unchanged)

3/30 dossiers (H28/H29/H30); 27 remaining = 54 briefs + 27 reconciliations; H20 24/19/5; candidate HOLD; E7 90+30 not admitted; E8 separate; 5 reporting groups + 1 capacity decision; 0/2 weekly readouts; PR1074/1070/1035/1009 held; invitations, flags, pricing, new load/jobs, E09 implementation (incl. dormant code), Copilot iterations, broad generation all held. Source-engineering timebox not reset; balance unknown here.

## Spend, mutations and deviations

- DeepSeek calls 0; USD 0.000000; reservations 0; ledger writes 1 (event 1, wording correction, no balance change; document SHA-256 `beef4ca0b2973db9f00503e0bbbf3ae2ad816def51c0f53820c41e51431be3fa`). Recorded cumulative usage reused from the snapshot (2,356 calls / USD 4.331765; USD 12.570771 conditional under the USD 15 authority). PR1086 CI: `eval-baseline` skipped (no AI-relevant change) → no paid job.
- External mutations by the chief: branch pushes, PR #1086 (merged) and this PR (GitHub, as the founder's account); Vercel previews of the unchanged frontend; two read-only `ops.yml` dispatches (`describe-service` run 37220896634, `describe-jobs` run 37220898225); the private ledger artifact publish; the Monday Routine update. No cloud-config, production, provider or flag action.
- Classifier denials: the CTO isolated workflow launch; one Bash read of two `docs/DEPLOYMENT.md` schedule sections. A third: the `git commit` of the CTO per-process SEC budget change (Production Deploy). None pursued through another route. (The two refuters read those schedule lines in their own isolated contexts as part of their assigned scope; the chief relies on their reports, not on a re-read.)
- Worker deviations (all disclosed, read-only, no mutation): CPO coordinator ran `git status --short`; COO worker ran `git status --porcelain | head -0`; the decisions-PR reviewer composed one command line containing a `pip download` of edgartools with output discarded (a possible outbound index request through the proxy; nothing used, nothing written).
- Chief defect (commit `3238c5d7`): the checkpoint hash table was regenerated with a column slip (hashes written into the status column; two handback rows kept revision-2 hashes); rebuilt from a clean definition in the next commit.
- Chief defect: CTO handback revision 1 left three placeholders unrendered; found by the COO worker; corrected in revision 2 (`CORRECTION-01.md`).
- Scratchpad absolute paths in the dispatch manifests are provenance for package inputs identified by SHA-256; the package hash plus the relative package path identify the bytes once the session's scratchpad is gone.

## Review record for PR #1086 and scheduled follow-up

- Independent read-only review of head `0cf48204d2fd0b20575020ac651ad50e85884b71` by an isolated subagent
  (registered in `control/source-context-exclusion-138.json`, together with the delta reviewer launched after that record): **no blocker**; 82 `file:line` anchors and
  24 SHA-256 values checked; eight nits (R1–R8). Dispositions: R2–R6 → CTO handback revision 3
  (`CORRECTION-02.md`); R1 → README exception sentence; R7 → todo wording; R8 → TAKEOVER heading now
  distinguishes observed (14:21Z) from recorded (14:31Z) time; the COO disposition's "all eight jobs
  verified" attribution to the repository snapshot JSON is a chief-noted slip: that fact is reused from the
  package `CURRENT-SNAPSHOT.md` (worker output left unedited); README row added to the table above.
- Required checks on `0cf48204`: backend-tests, frontend-tests, e2e-tests, migrations-postgres, lighthouse,
  secret-scan all success; eval-baseline skipped (no AI-relevant change, no paid call); review-gate skipped
  while draft. The corrected head is re-reviewed on its delta before the `Review override:` line is bound.
- Monday capacity-readout reminder: one-shot Routine `trig_01QEr6wQnjqtMG4FdqLce2qT`, updated to fire
  2026-10-05T08:10:00Z into this session for the 06:00–08:00 UTC window (D4; cancel with that id if the
  founder prefers to dispatch manually).

## Review record for PR #1088 (decision record 02)

- Head `9c505289950f0027636b9d77571f54d8fbd53ffa` reviewed by an isolated read-only subagent (registered in
  `control/source-context-exclusion-139.json` as the decisions-PR reviewer): **NO BLOCKER**; 27 `file:line`
  anchors checked, 0 mismatched; 27 SHA-256 values checked, 0 mismatched; exclusion-139 chain and counts
  verified; no ledger URL, credential, path or placeholder in the diff; no capacity/hold/spend admission.
  Six should-fix items and three nits, all accepted and fixed in the following commit: (1) "nine slots /
  171" → ten processes / 190 (2 instances + 8 jobs) in D3 and the observation record; (2) Appendix A's
  "no non-`tasks/` change since `100fb7d6`" → the 24 frontend/lessons files, none a cited anchor; (3) the
  five-process overlap relabelled Monday 07:00 UTC; (4) decision 7 marked superseded and the Routine fire
  time corrected to 08:10Z; (5) stale APPOINTMENTS fields (CTO status/deliverable, chief role, CFO
  worker) updated; (6) burst semantics: edgartools' pyrate-limiter bucket is a sliding window, not a
  start-full token bucket (verified in pyrate-limiter 4.3.0 `InMemoryBucket.put` in the local venv), so
  the first-second ceiling is 29 per process at the defaults and 3 per process / 15 at Monday 07:00 under
  the D3 pin — D3, the observation record, the founder's patch and its gate updated; (7) "four rows and
  §5"; (8) todo narrative bullet; (9) env names of torn-down integrations withheld (D5). The reviewer
  disclosed one deviation (a `pip download` command line with discarded output; nothing used).
- Delta `9c505289..6bc54a44` re-reviewed by the same context: **NO BLOCKER bound to `6bc54a44`**; all nine
  prior findings verified fixed in the committed blobs; 25 hashes / 0 mismatched; one minor should-fix
  (decision 11 burst wording) and four nits (founder item 2 wording, todo owner, execution-note addendum,
  Appendix A footnote) fixed in the following commit, which is re-checked before the `Review override:`
  line is bound.
- Delta `6bc54a44..0c0a1872` re-checked by the same context: **NO BLOCKER bound to `0c0a1872`**; findings 10–14
  verified fixed; 25 hashes / 0 mismatched; one nit (this bullet's count of its nits), fixed here. The final
  head's one-word delta is checked by the same context and recorded in the PR body with the override line.
- D3 patch gate (founder's patch, not this PR): first full backend run — ruff and bandit clean, pytest
  2305 passed / 1 failed: `tests/unit/test_data_completeness.py::test_backfill_deploy_restores_only_its_scheduled_entrypoint`
  pins the backfill-facts env token, so the patch now updates that token; targeted tests pass after the
  fix; the full re-run result is reported in the session.

## Founder-dependent items (precise; nothing blocks today's work)

1. Custody (DECISIONS-03): materialise the cloud-only files under the H20 planner bootstrap directory (17 of 21) and the predecessor planning directory (7 of 48) on the local machine, verify retained hashes, release clean approved inputs to the registered planner; the planner then runs within the 170 remaining minutes and returns counts, hashes, status and minutes.
2. Policy numbers (D3): confirm or change the per-process budgets (1 + 1 on every process) in the handed-over patch (SHA-256 `21322a05…`) before any PR carrying it is marked ready; marking ready needs a chief reservation (~USD 0.01 `copilot-eval`).
3. Ledger: closed — successor designated (decision 9); event 1 written (decision 17). Any paid action still needs a reservation written there first.

## Next executable action and stop condition

Next: (1) independent review of this PR's head, `Review override:` line bound to the final head, merge when green (tasks-only; no paid job); (2) founder: custody recovery and the D3 patch decision; (3) Monday 2026-10-05T08:10Z Routine dispatches the 06:00–08:00 UTC `capacity-readout`, receipt to COO; (4) on the planner's return, the chief sets `R1-STATUS.md` and records minutes. Stop condition unchanged: no capacity admission, invitation, flag, new load, E09 implementation or paid dispatch without a reservation in the successor ledger.
