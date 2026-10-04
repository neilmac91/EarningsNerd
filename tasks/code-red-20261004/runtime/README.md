# CODE RED runtime directory (chief-designated)

Fresh runtime/handback root for the 4 October 2026 Fable chief takeover, separate from the immutable
founder package (`earningsnerd-code-red-fable-chief-20261004.zip`,
SHA-256 `e5316f506477144051b77f64dde240124e5f4a8571017c79d83dc76ba7e7661c`, not committed).

- `TAKEOVER.md` — chief identity, observed runtime, package verification, snapshot, ledger status.
- `control/` — ledger access statement, append-only exclusion successors, appointments, repository snapshot.
- `dispatch/` — CEO-bound dispatch manifests and bounded assignment prompts for delegated workers.
- `handbacks/<officer>/` — worker outputs; one writer per output path; never edited after return. Chief-authored
  handbacks (e.g. the CTO envelope) may be revised in place only with a `CORRECTION-NN.md` beside them
  recording both hashes and the superseding commit.
- `CHECKPOINT.md` — durable checkpoint before compaction / session end.

Officer packets refer to `runtime/handbacks/<officer>/`; in this repository that path is
`tasks/code-red-20261004/runtime/handbacks/<officer>/`. Nothing here is a dossier, quality
acceptance, capacity admission, cohort readout, spend lock or release authorization.
