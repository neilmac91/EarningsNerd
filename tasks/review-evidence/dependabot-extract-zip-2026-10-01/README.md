# Dependabot alerts #283 and #270: extract-zip triage (item I, 2026-10-01)

**Inputs.** The alert identities come from the founder-authorized `gh api …/dependabot/alerts?state=open` read, posted on PR #1029 as comment 5931431002. Both alerts are high severity, cover `extract-zip <= 2.0.1`, are dev scope in `frontend/package-lock.json`, and have no patched version (`patched: null`).

| Alert | GHSA | Advisory |
| --- | --- | --- |
| #283 | GHSA-7pqw-9j4j-h8q3 | Arbitrary file writes through symlink archive entries. A symlink and a later same-name file write outside the destination. |
| #270 | GHSA-jmr9-qjv8-65gv | Unvalidated symlink path traversal (e.g. `../../../../etc/passwd`). |

**Versions, from npm on 2026-10-01.** `extract-zip` latest is 2.0.1, so no fixed release exists. `@lhci/cli` latest is 0.15.1, and it pins `lighthouse: 12.6.1` exactly.

**Dependency chain, from `frontend/package-lock.json` on main.** Every link is `dev: true`:

`@lhci/cli` 0.15.1 (root devDependency) → `lighthouse` 12.6.1 → `puppeteer-core` 24.43.1 → `@puppeteer/browsers` 2.13.2 → `extract-zip` 2.0.1 (the only instance)

## Reachability

- **Not in the app.**
  - No app code under `frontend/` imports `extract-zip`, `@puppeteer/browsers` or puppeteer.
  - All are dev dependencies, so none are in the production bundle.
- **Not run in CI.**
  - `extract-zip` is used only by `@puppeteer/browsers` when it downloads and unpacks a browser archive.
  - The only consumer of this chain is the advisory `lighthouse` job in `.github/workflows/ci.yml` (`continue-on-error: true`, not a required check). That job installs Chrome with `browser-actions/setup-chrome@v2` and runs `npx lhci autorun` with `lighthouserc.json`, which launches the installed Chrome. No `@puppeteer/browsers` download is configured.
- **Exploitation needs a malicious zip** containing symlink entries to be extracted, and this pipeline never extracts any zip through this path.

## Fix options

| Option | Assessment |
| --- | --- |
| Upgrade `extract-zip` | Not possible. No patched version exists. |
| Upgrade `@lhci/cli` | Already on the latest (0.15.1). It pins lighthouse 12.6.1. |
| Override `@puppeteer/browsers` to 3.x | 3.x replaces `extract-zip` with `modern-tar`. But it is a cross-major override underneath `puppeteer-core` 24, which expects the 2.x API, and lighthouse 13 (`puppeteer-core` ^25.9.0) is not supported by `@lhci/cli` 0.15.1. This is a major-upgrade path, which the decision holds. |
| Dismiss the alerts | Excluded by the decision. |

## Disposition

**Hold, with no change.** No narrow fix exists. The vulnerable code is not reachable in the shipped app or in the CI path.

**Re-check trigger.** Act on the first of:
- a patched `extract-zip`; or
- an `@lhci/cli` release on lighthouse 13 or later, which drops `extract-zip` through `@puppeteer/browsers` 3.x and `modern-tar`.

**Until then:** do not add a `@puppeteer/browsers install` step to CI, and do not unpack untrusted archives with this toolchain.
