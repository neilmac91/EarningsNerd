# Hand over to a fresh session when the harness refuses the conversation, not the action

Date: 2026-10-09 · Area: ops / agent operations

**Context.** The CODE RED chief session (records 01–20) lost its shell at about 21:40Z on
2026-10-09: a Claude Code safety check separate from the auto-mode classifier refused an edit, then
every shell command (`date` included), then every message to its review agents (about 22:05Z) and,
after a container restart, every workflow start or resume. Its message said it was reacting to
earlier conversation content and would keep refusing until the conversation ended. File reads and
GitHub reads and writes still worked, so the session finished merging its records PR, but it could
not commit, test, publish the ledger, re-bind its reviewer or redo a design workflow two restarts had
wiped. Every retry cost time and bought nothing; the work resumed only once the founder started a
fresh session with a written handover brief (`tasks/code-red-20261004/runtime/control/DECISIONS-21.md`).

**Rule.** When a refusal names the conversation rather than the action ("blocked ... because of
earlier conversation content"), do not retry, reword or route around it. In that same turn:

1. Stop issuing commands; finish only what still works and is already in flight (GitHub writes,
   reads, messages).
2. Write the handover for a fresh session, in the chat and in the committed records if a records
   write is still possible: the current heads and PR numbers, the private-store hashes and sizes
   (never the links), the open reservations, every trigger bound to the dying session (so the
   successor deletes and re-arms them), the exact actions that were refused with their times, and
   the work lost with any surviving artifacts.
3. Ask the founder to start the fresh session with that brief. The successor registers itself in a
   new append-only closure before launching anything and discloses the predecessor's block, the
   lost work and its own first denials in its first record.

**Evidence.** `tasks/code-red-20261004/runtime/control/DECISIONS-21.md` (the block, the restarts,
the handover and the takeover); PR neilmac91/EarningsNerd#1167's description (the final head left
unbound); `tasks/code-red-20261004/runtime/control/source-context-exclusion-172.json` (the successor's
registration).
