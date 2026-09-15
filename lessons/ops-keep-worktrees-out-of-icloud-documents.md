# Keep worktrees, virtual environments and bytecode caches out of iCloud-synced Documents

Date: 2026-09-15   Area: ops

**Context**: The agent workspace lives under `~/Documents/Codex/…`, which is an iCloud Drive
file-provider domain (`com.apple.file-provider-domain-id` on `~/Documents`). Its `work/` directory
holds about 1,800 entries including several virtual environments and bytecode caches. With
`fileproviderd` at 140 percent CPU and `bird` syncing, plain `ls`, `grep`, `cat` and `git`
commands inside the workspace stalled past 60 to 120 seconds while the same commands elsewhere
returned instantly; earlier sessions saw the same symptom as "lazy-import stalls" and worked
around it with a fresh `PYTHONPYCACHEPREFIX`.

**Rule**: Put new worktrees, virtual environments, caches and test databases outside iCloud
(`~/Codex-local/` is the current location; record any new one in the handover). When a shell
command in the workspace hangs, check `ps -Ao pid,pcpu,comm -r | head` for `fileproviderd`/`bird`
before suspecting the repository or the tooling, and read files with the Read tool rather than
piping them through the shell. Moving or excluding the existing workspace from iCloud is a
founder decision; do not change sync settings.

**Evidence**: `ps` on 2026-09-15 (`fileproviderd` 144.6 percent CPU, `bird` 19 percent); `ls -la@
~/Documents` attributes; `lessons/test-fresh-bytecode-prefix-before-trusting-local-timing.md`.
