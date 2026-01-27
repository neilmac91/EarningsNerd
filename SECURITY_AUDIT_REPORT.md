# EarningsNerd Security Audit Report
## Dependabot Vulnerability Resolution Plan

**Date:** 2026-01-27
**Repository:** neilmac91/EarningsNerd
**Auditor:** Claude Security Analysis
**Status:** Action Required

---

## Executive Summary

| Metric | Count |
|--------|-------|
| **Total Vulnerabilities** | 31 |
| **Critical** | 0 |
| **High** | 12 |
| **Moderate** | 17 |
| **Low** | 2 |
| **Frontend (npm)** | 27 |
| **Backend (Python)** | 4 |

### Key Findings

1. **Next.js DoS Vulnerability (HIGH)** - Production-impacting, patch available with minor version bump
2. **python-jose Algorithm Confusion (HIGH)** - Cryptographic vulnerability affecting JWT handling
3. **python-multipart DoS (HIGH)** - FastAPI form handling vulnerability
4. **vercel CLI Transitive Dependencies (HIGH)** - Dev-only, multiple nested vulnerabilities
5. **lodash Prototype Pollution (MODERATE)** - Direct dependency, fix available

### Estimated Resolution Time

| Tier | Vulnerabilities | Est. Time |
|------|-----------------|-----------|
| Tier 1 (Immediate) | 4 | 1-2 hours |
| Tier 2 (Urgent) | 5 | 2-3 hours |
| Tier 3 (Planned) | 15 | 4-6 hours |
| Tier 4 (Monitor) | 7 | N/A |

**Total Estimated Effort:** 7-11 hours (can be done incrementally)

---

## Phase 1: Vulnerability Catalog

### Frontend Vulnerabilities (npm)

| # | Package | Severity | CVE/GHSA | Current | Target | Direct | Component |
|---|---------|----------|----------|---------|--------|--------|-----------|
| 1 | next | High | GHSA-mwv6-3258-q52c | 14.2.33 | 14.2.35 | Yes | Production |
| 2 | next | High | GHSA-5j59-xgg2-r9c4 | 14.2.33 | 14.2.35 | Yes | Production |
| 3 | eslint-config-next | High | via glob | 14.2.33 | 16.1.5 | Yes | Dev |
| 4 | glob | High | GHSA-5j98-mcp5-4vw2 | 10.x | 10.5.0 | No | Dev |
| 5 | tar | High | GHSA-8qq5-rm4j-mr97 | ≤7.5.3 | 7.6.0+ | No | Dev |
| 6 | tar | High | GHSA-r6q2-hw4h-h46w | ≤7.5.3 | 7.6.0+ | No | Dev |
| 7 | path-to-regexp | High | GHSA-9wv6-86v2-598j | 4.x-6.2.x | 6.3.0 | No | Dev |
| 8 | @vercel/fun | High | via tar | * | N/A | No | Dev |
| 9 | @vercel/node | High | via esbuild, path-to-regexp | >=2.3.1 | N/A | No | Dev |
| 10 | @vercel/remix-builder | High | via path-to-regexp | >=5.2.4 | N/A | No | Dev |
| 11 | lodash | Moderate | GHSA-xxjr-mmjv-4gpg | 4.17.21 | 4.17.23 | Yes | Production |
| 12 | undici | Moderate | GHSA-c76h-2ccp-4975 | <5.28.5 | 6.23.0 | No | Dev |
| 13 | undici | Moderate | GHSA-g9mf-h72j-4rw9 | <6.23.0 | 6.23.0 | No | Dev |
| 14 | undici | Low | GHSA-cxrh-j4jr-qwg3 | <5.29.0 | 6.23.0 | No | Dev |
| 15 | esbuild | Moderate | GHSA-67mh-4wv8-2f99 | ≤0.24.2 | 0.25.0+ | No | Dev |
| 16 | js-yaml | Moderate | GHSA-mh29-5h37-fv8m | 4.0.0-4.1.0 | 4.1.1 | No | Build |
| 17 | mdast-util-to-hast | Moderate | GHSA-4fh9-h7wg-q85m | 13.0.0-13.2.0 | 13.2.1 | No | Build |
| 18 | diff | Low | GHSA-73rr-hh4g-fpgx | <4.0.4 | 4.0.4+ | No | Dev |
| 19 | tsx | Moderate | via esbuild | 3.13-4.19.2 | N/A | No | Dev |
| 20 | @vercel/backends | Moderate | via @vercel/cervel | ≤0.0.18 | N/A | No | Dev |
| 21 | @vercel/blob | Moderate | via undici | various | N/A | No | Dev |
| 22 | @vercel/cervel | Moderate | via tsx | ≤0.0.8 | N/A | No | Dev |
| 23 | @vercel/elysia | Moderate | via @vercel/node | ≤0.1.16 | N/A | No | Dev |
| 24 | @vercel/express | Moderate | via @vercel/cervel | ≤0.1.23 | N/A | No | Dev |
| 25 | @vercel/fastify | Moderate | via @vercel/node | ≤0.1.19 | N/A | No | Dev |
| 26 | @vercel/h3 | Moderate | via @vercel/node | ≤0.1.25 | N/A | No | Dev |
| 27 | @vercel/hono | Moderate | via @vercel/node | ≤0.2.19 | N/A | No | Dev |

### Backend Vulnerabilities (Python)

| # | Package | Severity | CVE | Current | Target | Direct | Component |
|---|---------|----------|-----|---------|--------|--------|-----------|
| 28 | python-jose | High | CVE-2024-33663 | 3.3.0 | 3.5.0 | Yes | Auth/JWT |
| 29 | python-jose | Moderate | CVE-2024-33664 | 3.3.0 | 3.5.0 | Yes | Auth/JWT |
| 30 | python-multipart | High | CVE-2024-53981 | 0.0.6 | 0.0.22 | Yes | API/Forms |
| 31 | python-multipart | Moderate | CVE-2024-24762 | 0.0.6 | 0.0.22 | Yes | API/Forms |

### Packages NOT Affected (Verified Safe)

| Package | Reason |
|---------|--------|
| weasyprint==60.1 | CVE-2024-28184 only affects versions 61.0-61.1 |
| redis==5.0.1 | CVE-2025-49844 affects Redis server, not Python client |
| arelle-release | No known CVEs found |
| lxml>=5.2.2 | Using version with XXE protections |

---

## Phase 2: Risk Assessment & Prioritization

### Prioritization Matrix

| Factor | Weight | Description |
|--------|--------|-------------|
| Severity (CVSS) | 35% | Critical=10, High=8, Medium=5, Low=2 |
| Exploitability | 25% | Active exploits=10, PoC exists=7, Theoretical=3 |
| Exposure | 20% | Public-facing=10, Internal=5, Dev-only=2 |
| Fix Complexity | 20% | Drop-in=10, Minor changes=6, Breaking=2 |

### Vulnerability Scores and Tiers

| Vulnerability | Severity | Exploit | Exposure | Fix | **Score** | **Tier** |
|---------------|----------|---------|----------|-----|-----------|----------|
| next DoS (GHSA-mwv6) | 8 | 7 | 10 | 10 | **8.55** | **Tier 1** |
| next DoS (GHSA-5j59) | 8 | 7 | 10 | 10 | **8.55** | **Tier 1** |
| python-jose (CVE-2024-33663) | 8 | 7 | 10 | 10 | **8.55** | **Tier 1** |
| python-multipart (CVE-2024-53981) | 8 | 7 | 10 | 10 | **8.55** | **Tier 1** |
| lodash Prototype Pollution | 5 | 3 | 10 | 10 | **6.60** | **Tier 2** |
| python-jose DoS (CVE-2024-33664) | 5 | 5 | 10 | 10 | **7.00** | **Tier 2** |
| python-multipart ReDoS | 5 | 5 | 10 | 10 | **7.00** | **Tier 2** |
| js-yaml Prototype Pollution | 5 | 3 | 5 | 10 | **5.30** | **Tier 3** |
| mdast-util-to-hast XSS | 5 | 3 | 5 | 10 | **5.30** | **Tier 3** |
| eslint-config-next (glob) | 8 | 3 | 2 | 2 | **4.15** | **Tier 3** |
| vercel transitive deps | 8 | 3 | 2 | 2 | **4.15** | **Tier 3** |
| undici vulnerabilities | 5 | 3 | 2 | 6 | **3.85** | **Tier 4** |
| esbuild dev server | 5 | 3 | 2 | 6 | **3.85** | **Tier 4** |
| diff DoS | 2 | 3 | 2 | 10 | **3.65** | **Tier 4** |

### Tier Summary

- **Tier 1 (Immediate - Fix within 24-48 hours):** 4 vulnerabilities
  - next DoS vulnerabilities (production web server)
  - python-jose algorithm confusion (authentication)
  - python-multipart DoS (API layer)

- **Tier 2 (Urgent - Fix within 1 week):** 3 vulnerabilities
  - lodash prototype pollution
  - python-jose JWT bomb
  - python-multipart ReDoS

- **Tier 3 (Planned - Fix in next sprint):** 4 vulnerabilities
  - js-yaml prototype pollution
  - mdast-util-to-hast unsanitized class
  - eslint-config-next major upgrade
  - vercel CLI transitive dependencies

- **Tier 4 (Monitor - Low urgency):** ~20 vulnerabilities
  - All dev-only transitive dependencies
  - Low-severity issues with limited exposure

---

## Phase 3: Resolution Strategies

### Strategy Summary by Package

| Package | Strategy | Risk Level | Breaking Changes |
|---------|----------|------------|------------------|
| next | Direct upgrade (patch) | Low | None |
| python-jose | Direct upgrade (minor) | Low | None |
| python-multipart | Direct upgrade (patch) | Low | None |
| lodash | Direct upgrade (patch) | Low | None |
| js-yaml | Transitive - auto-resolved | Low | None |
| mdast-util-to-hast | Transitive - auto-resolved | Low | None |
| eslint-config-next | Major upgrade | Medium | ESLint config changes |
| vercel | Upgrade to latest | Medium | CLI behavior changes |

### Detailed Resolution for Each Tier

#### Tier 1 Resolutions

**1. Next.js (14.2.33 → 14.2.35)**
- Type: Direct upgrade (patch version)
- Breaking changes: None
- Risk: Very Low
- Verification: Build test + smoke test

**2. python-jose (3.3.0 → 3.5.0)**
- Type: Direct upgrade (minor version)
- Breaking changes: None expected
- Risk: Low
- Verification: Run auth tests

**3. python-multipart (0.0.6 → 0.0.22)**
- Type: Direct upgrade (patch series)
- Breaking changes: None
- Risk: Very Low
- Verification: Run API tests

#### Tier 2 Resolutions

**4. lodash (4.17.21 → 4.17.23)**
- Type: Direct upgrade (patch version)
- Breaking changes: None
- Risk: Very Low
- Verification: Build test

#### Tier 3 Resolutions

**5. eslint-config-next (14.2.33 → 16.1.5)**
- Type: Major upgrade
- Breaking changes: Possible ESLint rule changes
- Risk: Medium
- Mitigation: Review lint output, update eslintrc if needed
- Alternative: Accept risk for dev dependency

**6. vercel CLI (48.9.0 → 50.6.0)**
- Type: Major upgrade
- Breaking changes: Possible CLI behavior changes
- Risk: Medium
- Note: Dev dependency only, doesn't affect production

---

## Phase 4: Implementation Plan

### Pre-Flight Checklist

```bash
# 1. Create security fix branch
git checkout -b security/dependabot-fixes

# 2. Backup lock files
cp frontend/package-lock.json frontend/package-lock.json.backup
cp backend/requirements.txt backend/requirements.txt.backup

# 3. Verify current state
cd frontend && npm audit --json > /tmp/npm-audit-before.json
```

### Tier 1 Fixes (Execute Immediately)

#### Fix 1: Next.js DoS Vulnerabilities

```bash
# Alert: GHSA-mwv6-3258-q52c, GHSA-5j59-xgg2-r9c4
# Severity: HIGH (CVSS 7.5)
# Current: next@14.2.33 → Target: next@14.2.35

cd /home/user/EarningsNerd/frontend

# Execute fix
npm install next@14.2.35

# Verify fix
npm ls next
npm audit --json | grep -A5 '"next"'

# Test
npm run build
npm run test
```

#### Fix 2: python-jose Algorithm Confusion

```bash
# Alert: CVE-2024-33663, CVE-2024-33664
# Severity: HIGH (Algorithm Confusion), MODERATE (JWT Bomb)
# Current: python-jose==3.3.0 → Target: python-jose==3.5.0

cd /home/user/EarningsNerd/backend

# Update requirements.txt
sed -i 's/python-jose\[cryptography\]==3.3.0/python-jose[cryptography]>=3.5.0/' requirements.txt

# Install updated package
pip install "python-jose[cryptography]>=3.5.0"

# Verify
pip show python-jose | grep Version

# Test
pytest tests/ -k "auth or jwt or token"
```

#### Fix 3: python-multipart DoS

```bash
# Alert: CVE-2024-53981, CVE-2024-24762
# Severity: HIGH (CVSS 7.5)
# Current: python-multipart==0.0.6 → Target: python-multipart>=0.0.18

cd /home/user/EarningsNerd/backend

# Update requirements.txt
sed -i 's/python-multipart==0.0.6/python-multipart>=0.0.18/' requirements.txt

# Install updated package
pip install "python-multipart>=0.0.18"

# Verify
pip show python-multipart | grep Version

# Test
pytest tests/ -k "upload or form or multipart"
```

### Tier 2 Fixes

#### Fix 4: lodash Prototype Pollution

```bash
# Alert: GHSA-xxjr-mmjv-4gpg
# Severity: MODERATE (CVSS 6.5)
# Current: lodash@4.17.21 → Target: lodash@4.17.23

cd /home/user/EarningsNerd/frontend

# Execute fix
npm install lodash@4.17.23

# Verify fix
npm ls lodash

# Test
npm run build
npm run test
```

### Tier 3 Fixes

#### Fix 5: Auto-resolve Transitive Dependencies

```bash
# These vulnerabilities may auto-resolve with npm update
cd /home/user/EarningsNerd/frontend

# Update all packages to latest compatible versions
npm update

# Check remaining vulnerabilities
npm audit

# If js-yaml and mdast-util-to-hast still vulnerable:
npm update js-yaml mdast-util-to-hast
```

#### Fix 6: eslint-config-next (Optional - Breaking)

```bash
# Alert: GHSA-5j98-mcp5-4vw2 (via glob)
# Severity: HIGH (but dev-only)
# Current: eslint-config-next@14.2.33 → Target: eslint-config-next@16.1.5

# ⚠️ WARNING: This is a major version upgrade
# May require ESLint configuration changes

cd /home/user/EarningsNerd/frontend

# Check what will change
npm info eslint-config-next@16.1.5 peerDependencies

# Execute upgrade (if comfortable with potential lint changes)
npm install eslint-config-next@16.1.5

# Test lint
npm run lint

# If lint errors occur, review and update .eslintrc.json accordingly
```

#### Fix 7: vercel CLI (Optional - Dev Tool)

```bash
# Alert: Multiple transitive vulnerabilities
# Severity: HIGH (dev-only)
# Current: vercel@48.9.0 → Target: vercel@50.6.0

cd /home/user/EarningsNerd/frontend

# This is a dev dependency - low risk but may change CLI behavior
npm install vercel@50.6.0 --save-dev

# Test deployment workflow
npx vercel whoami
npx vercel build
```

### Post-Fix Verification

```bash
# 1. Run full audit
cd /home/user/EarningsNerd/frontend
npm audit

# 2. Run all tests
npm run test
npm run build

# 3. Backend verification
cd /home/user/EarningsNerd/backend
pytest

# 4. E2E tests (if time permits)
cd /home/user/EarningsNerd/frontend
npm run test:e2e
```

### Rollback Procedures

```bash
# If issues arise, restore from backup

# Frontend rollback
cd /home/user/EarningsNerd/frontend
cp package-lock.json.backup package-lock.json
npm ci

# Backend rollback
cd /home/user/EarningsNerd/backend
cp requirements.txt.backup requirements.txt
pip install -r requirements.txt
```

---

## Phase 5: Implementation Checklist

### Tier 1 (Immediate Priority)

- [ ] **Pre-flight**
  - [ ] Create feature branch `security/dependabot-fixes`
  - [ ] Backup `package-lock.json` and `requirements.txt`
  - [ ] Run initial `npm audit` and save baseline

- [ ] **Fix 1: Next.js**
  - [ ] Run `npm install next@14.2.35`
  - [ ] Verify with `npm ls next`
  - [ ] Run `npm run build`
  - [ ] Run `npm run test`
  - [ ] Commit: "fix(security): upgrade next.js to 14.2.35 (GHSA-mwv6, GHSA-5j59)"

- [ ] **Fix 2: python-jose**
  - [ ] Update `requirements.txt` to `python-jose[cryptography]>=3.5.0`
  - [ ] Run `pip install -r requirements.txt`
  - [ ] Verify with `pip show python-jose`
  - [ ] Run `pytest tests/`
  - [ ] Commit: "fix(security): upgrade python-jose to 3.5.0 (CVE-2024-33663)"

- [ ] **Fix 3: python-multipart**
  - [ ] Update `requirements.txt` to `python-multipart>=0.0.18`
  - [ ] Run `pip install -r requirements.txt`
  - [ ] Verify with `pip show python-multipart`
  - [ ] Run `pytest tests/`
  - [ ] Commit: "fix(security): upgrade python-multipart to 0.0.18+ (CVE-2024-53981)"

### Tier 2 (Within 1 Week)

- [ ] **Fix 4: lodash**
  - [ ] Run `npm install lodash@4.17.23`
  - [ ] Run `npm run build && npm run test`
  - [ ] Commit: "fix(security): upgrade lodash to 4.17.23 (GHSA-xxjr)"

### Tier 3 (Next Sprint)

- [ ] **Fix 5: Transitive dependencies**
  - [ ] Run `npm update` to auto-resolve
  - [ ] Verify `npm audit` improvements

- [ ] **Fix 6: eslint-config-next** (optional)
  - [ ] Review breaking changes
  - [ ] Test lint configuration
  - [ ] Update if acceptable

- [ ] **Fix 7: vercel CLI** (optional)
  - [ ] Review changelog for behavior changes
  - [ ] Test deployment workflow

### Final Steps

- [ ] Run `npm audit` - confirm 0 high/critical in production deps
- [ ] Run full test suite (unit + e2e)
- [ ] Run production build
- [ ] Create Pull Request with security fixes
- [ ] Deploy to staging environment
- [ ] Verify staging functionality
- [ ] Deploy to production

---

## Automation Recommendations

### 1. Dependabot Configuration

Create `.github/dependabot.yml`:

```yaml
version: 2
updates:
  # Frontend (npm)
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    groups:
      security-patches:
        applies-to: security-updates
        patterns:
          - "*"
    labels:
      - "dependencies"
      - "security"
    commit-message:
      prefix: "fix(deps):"

  # Backend (pip)
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
      - "security"
    commit-message:
      prefix: "fix(deps):"
```

### 2. CI Security Scanning

Add to `.github/workflows/ci.yml`:

```yaml
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run npm audit
        run: |
          cd frontend
          npm ci
          npm audit --audit-level=high
        continue-on-error: true

      - name: Run pip-audit
        run: |
          pip install pip-audit
          cd backend
          pip-audit -r requirements.txt
        continue-on-error: true

      - name: Upload audit results
        uses: github/codeql-action/upload-sarif@v3
        if: always()
```

### 3. Pre-commit Hooks

Add security checks to development workflow:

```bash
# .husky/pre-push
npm audit --audit-level=high
```

### 4. Scheduled Security Reviews

Set calendar reminder for:
- Weekly: Review Dependabot PRs
- Monthly: Full `npm audit` and `pip-audit` review
- Quarterly: Evaluate major dependency upgrades

---

## Risk Acceptance Notes

### Accepted Risks (Tier 4 - Monitoring)

The following vulnerabilities are accepted with monitoring:

1. **vercel CLI transitive dependencies** - Dev tool only, no production impact
2. **diff package DoS** - Low severity, limited attack surface
3. **esbuild dev server** - Only affects local development

### Justification

These are development-only dependencies that:
- Do not ship to production
- Require local access to exploit
- Have limited practical impact

### Monitoring Plan

- Subscribe to GitHub Security Advisories for affected packages
- Re-evaluate quarterly or when CVE status changes

---

## Appendix: Vulnerability Details

### CVE-2024-33663 (python-jose)

**Summary:** Algorithm confusion with OpenSSH ECDSA keys allows cryptographic bypass.

**Impact:** An attacker could potentially forge JWT tokens by exploiting key format confusion.

**CVSS:** 6.5 (Medium) - Network accessible, no authentication required

**Remediation:** Upgrade to python-jose >= 3.4.0

### CVE-2024-53981 (python-multipart)

**Summary:** Boundary parsing DoS via excessive logging and CPU consumption.

**Impact:** Attackers can send malformed multipart requests to stall the event loop.

**CVSS:** 7.5 (High) - Network accessible, no authentication required

**Remediation:** Upgrade to python-multipart >= 0.0.18

### GHSA-mwv6-3258-q52c (Next.js)

**Summary:** Denial of Service with Server Components via malicious payloads.

**Impact:** Attackers can crash Next.js servers by sending crafted requests.

**CVSS:** 7.5 (High) - Network accessible, no authentication required

**Remediation:** Upgrade to next >= 14.2.34

---

*Report generated by Claude Security Analysis*
*Last updated: 2026-01-27*
