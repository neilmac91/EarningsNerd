# Bounded triage: two open high-severity Dependabot alerts

Reviewed read-only on 2026-09-23 through the GitHub Dependabot alerts API for `neilmac91/EarningsNerd`. The query returned exactly two open high-severity alerts, both against `frontend/package-lock.json` on the default branch `main`. GitHub's live default-branch head was `ebdc4c44c5c6aa01c94587646a4c365f84fe26ec`; the local `origin/main` matched it, and its frontend dependency files were byte-identical to the review checkout.

## Result

Neither alert is a new production vulnerability introduced by release #949. Both describe `extract-zip@2.0.1` in the existing development-only Lighthouse CI chain. They were open before #949 merged, were included in that release's six-node high-severity npm audit result, and have no patched package version in GitHub's current advisory data.

No emergency application release is justified by the evidence. Keep both findings as a documented development-tool risk and recheck for an upstream patch during the next normal dependency-maintenance window. If the repository owner wants the GitHub banner cleared before a patch exists, dismiss both alerts together as vulnerable code not used/tooling-only, citing this reachability record. Do not apply npm's previously reported forced downgrade to `@lhci/cli@0.12.0` without separately validating the Lighthouse job.

## Exact alerts

| Alert | Advisory | Published / alert created | GitHub severity | Affected range / patch | What it permits |
|---|---|---|---|---|---|
| [#270](https://github.com/neilmac91/EarningsNerd/security/dependabot/270) | [GHSA-jmr9-qjv8-65gv](https://github.com/advisories/GHSA-jmr9-qjv8-65gv), CVE-2026-56876 | 2026-06-26 / 2026-08-12 | High; CVSS 3.1 8.1, CVSS 4.0 8.6 | `extract-zip <=2.0.1`; no first patched version | An archive-controlled symlink target can traverse outside the extraction directory, enabling arbitrary file read/write depending on caller behavior. |
| [#283](https://github.com/neilmac91/EarningsNerd/security/dependabot/283) | [GHSA-7pqw-9j4j-h8q3](https://github.com/advisories/GHSA-7pqw-9j4j-h8q3), CVE-2026-19693 | 2026-08-17 / 2026-09-08 | High; CVSS 3.1 8.1 | `extract-zip <=2.0.1`; no first patched version | A duplicate-name symlink followed by a regular archive entry can write through the symlink outside the destination. |

The advisories' EPSS fields are low rather than zero: `0.00391` at the 32.518th percentile for #270 and `0.0028` at the 20.559th percentile for #283. Severity remains real if hostile archives reach the extractor; the repository-specific reachability is what lowers current urgency.

## Dependency and execution path

The default-branch lock resolves this chain:

```text
devDependency @lhci/cli@0.15.1
  -> lighthouse@12.6.1
  -> puppeteer-core@24.43.1
  -> @puppeteer/browsers@2.13.2
  -> extract-zip@2.0.1
```

Every package in that chain is marked `dev: true` in `frontend/package-lock.json`. `extract-zip` is transitive; the repository does not import or invoke it directly. `@lhci/cli` is used by the advisory `lighthouse` GitHub Actions job. That job:

- installs dependencies with `npm ci`;
- installs Chrome separately with `browser-actions/setup-chrome@v2`;
- builds and starts the local Next application;
- runs LHCI against only `http://localhost:3000/` and `/pricing`.

There is no application route, browser bundle, backend runtime, uploaded user archive, or production data path to `extract-zip`. `puppeteer-core` does not bundle a browser, and this workflow supplies Chrome separately. The vulnerable extraction code could matter if this tooling path were changed to download or unpack an attacker-controlled browser/archive, or if its upstream download were compromised; that is the residual CI/supply-chain risk.

The existing CI audit deliberately runs `npm audit --omit=dev --audit-level=high` for production dependencies and tracks this LHCI chain separately. The September 14 retained audit reported zero production findings and six high package nodes, all development-only, from these two `extract-zip` advisories.

## Comparison with release #949

Release #949 merged as `ab7364dabf625b196f08ac608fefafe07d1515fc` on 2026-09-23. Both alert creation dates precede that merge by at least two weeks. The release audit at `outputs/overnight-2026-09-23/dependency-refresh/npm-audit-summary.md` records:

- the same six high-severity npm nodes and no critical, moderate, low, or informational findings;
- the same development-only chain ending in `extract-zip@2.0.1`;
- identical vulnerability objects between the #949 candidate and its `df6a7220` baseline;
- no introduction or version change to this chain from the dependency refresh.

Direct lock comparison confirms `@lhci/cli@0.15.1`, `lighthouse@12.6.1`, `puppeteer-core@24.43.1`, `@puppeteer/browsers@2.13.2`, and `extract-zip@2.0.1` at both the `df6a7220` base and #949 merge. The chain was initially added with the advisory Lighthouse job on 2026-06-13, before either alert was created. The September 14 resumption audit explicitly records two `extract-zip` advisories and zero production entries. The push banner is therefore surfacing retained known debt, not a regression from the prior release.

## Recommendation and trigger to revisit

Treat this as non-urgent, bounded development-tool exposure:

1. Do not issue a production hotfix or forced dependency downgrade for these alerts.
2. At the next normal dependency review, query both advisories for a non-null `first_patched_version` and test the smallest supported LHCI/Lighthouse update that removes the chain.
3. Until then, preserve the current controls: separately installed Chrome, local fixed LHCI URLs, no untrusted archive input, and production audit with development dependencies omitted only by explicit policy.
4. Escalate sooner if the CI job begins accepting an archive/browser URL from pull-request input, downloads browsers through `@puppeteer/browsers`, runs on a privileged self-hosted runner, or either advisory gains a patch or materially stronger exploitation evidence.

This triage did not dismiss alerts, update dependencies, install packages, create a pull request, or make provider calls.
