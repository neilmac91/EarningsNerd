# Mutation proofs run on committed state only: `git checkout --` restores HEAD, not your edit

Date: 2026-09-08 · Area: ops / verification

**Context.** A mutation proof (drop a filter, run the suite, restore with
`git checkout -- <file>`) was run while the file under mutation still carried an uncommitted
feature edit. The restore put back the committed version, silently discarding the edit; the next
commit then shipped the test and docs for a flag the script no longer had, and only the suite run
after the commit exposed it (`KeyError: 'accessions'`).

**Rule.** Before any mutation proof, `git status --short` must show the mutated files clean
(the feature commit exists). Mutate, run, restore, and confirm `git diff --stat` is empty. Never
restore with `git checkout --` (or `git restore`) on a file that has uncommitted work; if a
mutation is needed mid-edit, commit first or restore from a copied backup of the working file.
A suite run that fails after a restore is read before the next commit, not after.

**Evidence.** #766 (W3-9b): the `--accessions` filter was re-applied and the commit amended before
push; `tasks/todo.md` W3-9b section.
