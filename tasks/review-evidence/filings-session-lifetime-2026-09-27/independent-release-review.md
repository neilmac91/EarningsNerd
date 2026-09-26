# Pool-lifetime release evidence review

Reviewed 2026-09-27 against clean branch head
`f1eceae500d8745927ed9ad38018610c1aa00ac3` and main
`5554bc87495dbb76e70ab10e32236260936080e8`.

The rebased branch has exactly three changed files. Their bytes are identical to both the
pre-rebase implementation commit `f39ce9d4aa0cbbeae4a4ddf01f3f6db4c8aaa1c2` and the mutation
receipt's earlier implementation commit `0a542f54681ae52600baea6eb9efa98c0b7b2ca8`:

- `backend/app/routers/filings.py`: `bbeeb56775ae98953b4e3f63cfd2554f7928879eaab131256df572b39233136d`
- `backend/app/services/filing_history_service.py`: `b6df9882d7f5e4c3e844195f820c1d7292de94666ec27932440be587f75787aa`
- `backend/tests/unit/test_filings_endpoint_db_first.py`: `016246d97d642dd12ae00064396b7d2b800ace110e4b8669c8f08895355df59c`

## Release-evidence correction

`full-gate.txt` is a complete passing gate on pre-rebase commit `f39ce9d4`: Ruff passed and
pytest reports `3730 passed, 40 warnings in 151.21s`. It supports the unchanged three-file code
bytes, but it is not an exact-head receipt for `f1eceae5`.

`standalone-full-gate.txt` names exact head `f1eceae5`, but its retained output currently ends at
65 percent with no pytest summary or command exit. It cannot support an exact-head full-gate claim
in the PR body unless it is replaced or completed with terminal evidence.

The mutation receipt remains internally consistent for the router mutation: the synthetic fault
produced one named failure, restoration produced `21 passed`, and its restored router hash equals
the current head. Because the receipt names `0a542f5`, the PR body should either state the verified
byte identity across `0a542f5`, `f39ce9d4`, and `f1eceae5`, or use a refreshed receipt tied to the
rebased head.

No code finding arose from this evidence review. The release-body issue is limited to accurately
describing which commit each raw gate proves.
