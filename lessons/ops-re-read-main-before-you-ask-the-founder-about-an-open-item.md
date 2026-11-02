# Re-read main and the item's row before you ask the founder about an open item; another session may have closed it

Date: 2026-11-02 · Area: ops / records

**Context.** On 2026-11-02 a session began E283 on a branch cut from main the day before, mapped it with a read-only
workflow over that tree, and then asked the founder two design questions about the settings page's Delete account
card. Main had moved: another session had merged E283 as #1932 (Card's danger tone, the confirmation in Notice's
error tint, a border-colour gate) and E284 as #1936. A worker restart and a change of date sat between the branch and
the questions. The founder answered questions whose previews described the confirmation as it stood before #1932
(4.32:1 in dark) and offered an outline #1932 had already shipped, so a second question was needed to ask what to do
about the merged work (D-076).

**Rule.** Before you put a question to the founder about an open item, and again after a worker restart or a change of
date: `git fetch origin main`, grep main's `tasks/todo.md` for the item's row, and run `git log origin/main
--grep=<item>` for a merge. If the row is gone or a merged pull request names the item, read that pull request first,
then ask only what it left open and say what it already did.

**Evidence.** #1932 (`99f9d970`) and #1936 (`1cbafa08`), merged before the questions; D-076 in
`docs/brand/decisions-log.md`, which records the stale previews.
