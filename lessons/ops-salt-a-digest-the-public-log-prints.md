# Salt every digest a public log prints over private fields: a hash of guessable values names them

Date: 2026-11-03 (PB-02, #1955)   Area: ops / privacy

**Context**: PB-02's operator command printed `manifest_sha256`, a plain SHA-256 of the private manifest's canonical
JSON, in every report, so in the public Ops log. Every field under it could be guessed: a stock reason ("Private beta
tester", as in the runbook's example), the founder's id, sequential account ids and the fingerprint of a candidate
address, with the report printing the action, cohort, review date and entry count beside it. The final review's privacy
lens rebuilt a one-account manifest (the runbook's own mistaken-grant and date-move steps make them) from the public
fields and a list of 200 candidate addresses, and recovered the tester's address and account id in 3.8 s on one Python
core. A digest is a hash, not a secret: published over guessable values, it confirms each guess.

**Rule**:
- Before a digest, checksum or fingerprint of private data reaches a public log, a workflow input or a pull request,
  put at least 128 bits of secret randomness inside what is hashed (a salt kept with the private data), or key it
  (an HMAC with a secret from the private store). Without one, treat the digest as the data.
- Make the salt required by the format that carries it, and make a published example's salt a placeholder the format
  refuses, so a copied example cannot run with a public salt.

**Gate** (partly): the complimentary-access manifest's `salt` is required (32 to 128 lower-case hex characters) and
inside the canonical form; `backend/tests/unit/test_complimentary_access_service.py::test_the_digest_covers_a_secret_salt_so_its_public_copy_names_no_one`
fails if it leaves the digest, and `::test_the_runbooks_example_manifest_runs_once_its_salt_is_drawn` if the runbook's
example would run as written. Another digest of private data in a public output is review-checked.

**Evidence**: the final review of `037dc992` on #1955 (privacy lens); the salt landed with mutation proofs in the
PR body; `lessons/ops-never-echo-environment-values.md` for values themselves.
