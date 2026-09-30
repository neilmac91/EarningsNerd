# PR 966 hosted default-build audit

- PR head: `5440fff0398b5d40a363c8f28968f60a4943848e`
- Hosted workflow run: `36285942076`
- Tested synthetic merge: `2b210f4fe46d2b6297ee299510b8f81d93764e04`
- Merge relationship recorded by checkout: `Merge 5440fff0398b5d40a363c8f28968f60a4943848e into 537bf59b923922d2215ae1399920756e014bd4e5`

The hosted E2E job `108526617448` independently ran the repository default `npm run build`, which invoked `next build` with Next.js 16.3.5 and Turbopack. It compiled successfully in 16.4 seconds, generated 27 of 27 static pages, and subsequently brought `next start` to ready state.

The hosted Lighthouse job `108526617374` independently ran the same default build. It compiled successfully in 16.2 seconds, generated 27 of 27 static pages, and then used `npm run start` for the audit.

Raw logs are retained outside the repository under workspace `outputs/takeover-2026-09-26/landing-claims/active-analysis-copy-final/`. Their exact hashes bind that external retention location:

- `hosted-e2e.log` — SHA-256 `6878db3910dba6a41612658f26b86439316ce5292ccbb51f07f0f292f6afb7a3`
- `hosted-lighthouse.log` — SHA-256 `41211189344754b62caea6ac1db42edcb3778c5188f76a77cebc365e94ca110c`
- `hosted-frontend-tests.log` — SHA-256 `9a58791d8bc2930a6c416dd86395e32bcea45e99a4a39339f4c072ba6e255e54`

This confirms two actual hosted default Turbopack production builds of the synthetic merge containing the exact PR head. The conclusion does not rely on the green frontend-tests job, which did not run the production build. It establishes build compatibility only; it does not establish UI copy quality or resolve the separately tracked backend cached-warning persistence issue.
