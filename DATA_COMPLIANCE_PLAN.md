# Data Handling Compliance Plan
## EarningsNerd - EU & North American Markets

**Last Updated**: January 22, 2026
**Version**: 1.0
**Status**: Implementation Required

---

## Executive Summary

EarningsNerd is an AI-powered SEC filing analysis platform that collects and processes user data including email addresses, names, passwords, search history, watchlists, and behavioral analytics. This plan addresses compliance requirements for:

- **European Union**: GDPR (General Data Protection Regulation)
- **North America**: CCPA/CPRA (California), PIPEDA (Canada), CAN-SPAM Act

### Current Compliance Status

**Strengths**:
- ✅ Privacy Policy exists and is accessible
- ✅ Security Policy documents practices
- ✅ Strong authentication (bcrypt password hashing, JWT)
- ✅ TLS encryption in transit
- ✅ Rate limiting on sensitive endpoints
- ✅ No PCI data storage (Stripe handles payments)
- ✅ Third-party services disclosed

**Critical Gaps**:
- ❌ No user data deletion endpoint (GDPR Art. 17)
- ❌ No data export/portability endpoint (GDPR Art. 20)
- ❌ No cookie consent management (GDPR Art. 7)
- ❌ PostHog session recording defaults ON (should be opt-in)
- ❌ No documented data retention schedule
- ❌ IP address logging may be excessive

---

## 1. Data Collection Inventory

### 1.1 Personal Data Collected

| Data Type | Collection Point | Storage Location | Legal Basis | Sensitivity |
|-----------|------------------|------------------|-------------|-------------|
| Email address | Registration, Waitlist, Contact | `users.email`, `waitlist_signups.email`, `contact_submissions.email` | Contract/Consent | High |
| Full name | Registration (optional), Waitlist | `users.full_name`, `waitlist_signups.name` | Contract/Consent | Medium |
| Password (hashed) | Registration | `users.hashed_password` | Contract | Critical |
| IP address | Contact form, Rate limiting | `contact_submissions.ip_address`, Logs | Legitimate interest | Medium |
| Stripe Customer ID | Payment processing | `users.stripe_customer_id` | Contract | Medium |
| Stripe Subscription ID | Subscription management | `users.stripe_subscription_id` | Contract | Medium |

### 1.2 Behavioral & Usage Data

| Data Type | Collection Point | Storage Location | Retention |
|-----------|------------------|------------------|-----------|
| Search history | Company searches | `user_searches` | Indefinite ⚠️ |
| Watchlist items | User watchlist | `watchlist` | Until user deletes |
| Saved summaries | Save feature | `saved_summaries` | Until user deletes |
| Usage metrics | Summary generation | `user_usage` | Monthly aggregation |
| Page views & events | PostHog analytics | PostHog (external) | PostHog policy |
| Session recordings | PostHog (if enabled) | PostHog (external) | PostHog policy |
| Error logs | Sentry | Sentry (external) | Sentry policy |

### 1.3 Third-Party Data Processors

| Processor | Purpose | Data Shared | Location | DPA Required |
|-----------|---------|-------------|----------|--------------|
| **Stripe** | Payment processing | Email, customer ID, subscription data | USA | Yes ✅ |
| **Resend** | Email delivery | Email, name, message content | USA | Yes ⚠️ |
| **PostHog** | Analytics | User ID, email, page views, events, sessions | USA/EU options | Yes ⚠️ |
| **Sentry** | Error tracking | Stack traces, user context | USA | Yes ⚠️ |
| **Google Gemini** | AI summaries | SEC filing content (no PII) | USA | Check ⚠️ |
| **SEC EDGAR** | Filing data | Company ticker queries (no PII) | USA | No |

**Action Required**: Obtain and document Data Processing Agreements (DPAs) from all marked processors.

---

## 2. Legal Requirements by Jurisdiction

### 2.1 European Union (GDPR)

**Applicability**: Yes - if any EU residents use the service

**Key Obligations**:

1. **Lawful Basis for Processing** (Art. 6)
   - Contract: User account, authentication, service delivery
   - Consent: Analytics, marketing emails, session recording
   - Legitimate interest: Fraud prevention, security

2. **Data Subject Rights** (Art. 12-23)
   - ✅ Right to access (Privacy policy states this)
   - ❌ Right to erasure (NOT IMPLEMENTED)
   - ❌ Right to data portability (NOT IMPLEMENTED)
   - ⚠️ Right to object (Partially via account settings)
   - ⚠️ Right to restrict processing (NOT IMPLEMENTED)
   - ⚠️ Right to rectification (Can update profile, but no formal process)

3. **Consent Requirements** (Art. 7)
   - ❌ Cookie consent banner (MISSING)
   - ❌ Explicit opt-in for session recording (Currently opt-out)
   - ⚠️ Clear consent for analytics (PostHog runs by default)

4. **Data Protection by Design** (Art. 25)
   - ✅ Password hashing
   - ✅ TLS encryption
   - ✅ Rate limiting
   - ⚠️ Data minimization (Some unnecessary data collected)
   - ❌ Automated data retention enforcement

5. **Breach Notification** (Art. 33-34)
   - ⚠️ Process documented in security policy but no technical implementation
   - Required: 72-hour notification to supervisory authority
   - Required: User notification if high risk

6. **Data Transfers** (Art. 44-50)
   - All third-party processors are US-based
   - Required: Standard Contractual Clauses (SCCs) or adequacy decision
   - Action: Verify DPAs include EU-approved SCCs

### 2.2 California (CCPA/CPRA)

**Applicability**: Yes - if serving California residents

**Key Obligations**:

1. **Privacy Notice** (§1798.100)
   - ✅ Categories of personal information collected (disclosed)
   - ✅ Purposes for use (disclosed)
   - ⚠️ Sources of information (should be more explicit)

2. **Consumer Rights**
   - Right to know (similar to GDPR access)
   - ❌ Right to delete (NOT IMPLEMENTED)
   - ❌ Right to correct (NOT IMPLEMENTED)
   - Right to opt-out of sale (N/A - no data sales)
   - ⚠️ Right to limit sensitive data use (Should clarify)

3. **"Do Not Sell My Personal Information"**
   - No data sales occurring (good)
   - Sharing with PostHog/Sentry may require disclosure

### 2.3 Canada (PIPEDA)

**Applicability**: Yes - if serving Canadian users

**Key Obligations**:

1. **Consent** (Schedule 1, Clause 4.3)
   - ✅ Privacy policy accessible
   - ⚠️ Consent should be more explicit for analytics

2. **Limiting Collection** (Clause 4.4)
   - ⚠️ IP address collection may be excessive
   - ⚠️ Indefinite search history retention questionable

3. **Individual Access** (Clause 4.9)
   - ❌ No formal access request process

### 2.4 CAN-SPAM Act (US Email Marketing)

**Applicability**: Yes - transactional and marketing emails

**Current Compliance**:
- ✅ Resend handles technical requirements
- ⚠️ Ensure unsubscribe links in marketing emails (check Resend config)
- ✅ From address is legitimate
- ⚠️ Verify physical address in email footers

---

## 3. Critical Compliance Gaps & Remediation

### Priority 1: CRITICAL (Implement Immediately)

#### Gap 1: No User Data Deletion Endpoint
**Violation**: GDPR Art. 17, CCPA §1798.105
**Risk**: High - regulators can fine up to €20M or 4% of revenue
**Timeline**: 2 weeks

**Implementation**:
```
Endpoint: DELETE /api/users/me
Authentication: Required (JWT)
Process:
1. Verify user identity
2. Send confirmation email with deletion link
3. Wait 24-hour grace period
4. Delete from tables:
   - users (cascade should handle related records)
   - user_searches
   - saved_summaries
   - watchlist
   - user_usage
5. Notify third parties (Stripe, PostHog) to delete
6. Log deletion in audit trail
7. Send final confirmation email
```

**Files to modify**:
- `/backend/app/routers/users.py` (add delete endpoint)
- `/backend/app/models/user.py` (ensure cascade deletes configured)
- `/frontend/app/dashboard/settings/page.tsx` (add delete account button)

---

#### Gap 2: No Data Portability Endpoint
**Violation**: GDPR Art. 20
**Risk**: High
**Timeline**: 2 weeks

**Implementation**:
```
Endpoint: GET /api/users/me/export
Authentication: Required (JWT)
Format: JSON (default) or CSV (query param)
Data included:
- User profile (email, name, created_at)
- Search history (all searches with timestamps)
- Watchlist items
- Saved summaries (with metadata)
- Usage statistics
- Account settings
Response: Downloadable file or email link
```

**Files to modify**:
- `/backend/app/routers/users.py` (add export endpoint)
- `/frontend/app/dashboard/settings/page.tsx` (add export button)

---

#### Gap 3: Cookie Consent Management
**Violation**: GDPR Art. 7, ePrivacy Directive
**Risk**: High
**Timeline**: 1 week

**Implementation**:
```
Component: CookieConsentBanner
Location: Root layout (show on first visit)
Options:
- Essential cookies (always on): Authentication, security
- Analytics cookies (opt-in): PostHog
- Functional cookies (opt-in): Preferences

Storage: localStorage.cookieConsent = {
  essential: true,
  analytics: false,
  functional: false,
  timestamp: Date
}

Behavior:
- Block PostHog initialization until consent granted
- Respect "Do Not Track" browser header
- Allow users to change preferences later (link in footer)
```

**Files to create**:
- `/frontend/app/components/CookieConsent.tsx`
- `/frontend/app/cookie-policy/page.tsx` (or expand privacy page)

**Files to modify**:
- `/frontend/app/layout.tsx` (add CookieConsent)
- `/frontend/app/providers.tsx` (conditional PostHog init)

---

#### Gap 4: PostHog Session Recording Opt-In
**Violation**: GDPR Art. 7 (consent), Privacy best practices
**Risk**: Medium-High
**Timeline**: 1 week

**Current Code** (`/frontend/app/providers.tsx`):
```typescript
posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY!, {
  // Session recording is ON by default
  session_recording: {
    maskAllInputs: true,
    maskTextSelector: '[data-mask], input[type="password"]'
  }
})
```

**Required Change**:
```typescript
posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY!, {
  session_recording: {
    recordingEnabled: cookieConsent.analytics && cookieConsent.sessionRecording,
    maskAllInputs: true,
    maskTextSelector: '[data-mask], input[type="password"]'
  }
})
```

Add separate consent option for session recording (more invasive than analytics).

---

### Priority 2: HIGH (Implement Within 1 Month)

#### Gap 5: Data Retention Schedule
**Violation**: GDPR Art. 5(e) (storage limitation)
**Risk**: Medium
**Timeline**: 2 weeks planning + 2 weeks implementation

**Proposed Retention Policy**:

| Data Type | Retention Period | Deletion Method |
|-----------|------------------|-----------------|
| Active user accounts | Until user deletes or 2 years of inactivity | Automated job |
| Inactive user accounts | 2 years from last login | Automated job + email warning |
| Search history | 1 year from search date | Automated job |
| Contact form submissions | 1 year from submission | Automated job |
| Waitlist signups (unconverted) | 1 year from signup | Automated job |
| Saved summaries | Until user deletes | Manual only |
| Watchlist items | Until user deletes | Manual only |
| Audit logs | 3 years (compliance requirement) | Automated job |
| Stripe data | 7 years (tax/legal requirement) | Stripe handles |

**Implementation**:
```python
# New file: /backend/app/tasks/data_retention.py
# Scheduled job (run daily via cron or Celery)

async def cleanup_expired_data():
    # Delete inactive users (2 years no login)
    await cleanup_inactive_users()

    # Delete old search history (1 year)
    await cleanup_old_searches()

    # Delete old contact submissions (1 year)
    await cleanup_old_contact_submissions()

    # Delete old waitlist (1 year unconverted)
    await cleanup_old_waitlist()
```

**Files to create**:
- `/backend/app/tasks/data_retention.py`
- `/backend/app/tasks/scheduler.py` (if not exists)
- `DATA_RETENTION_POLICY.md` (documentation)

---

#### Gap 6: IP Address Collection Justification
**Violation**: GDPR Art. 5(c) (data minimization)
**Risk**: Medium
**Timeline**: 1 week

**Current**: IP addresses stored in `contact_submissions.ip_address` indefinitely

**Options**:
1. **Remove IP collection entirely** (if not needed for fraud prevention)
2. **Hash IP addresses** before storage (one-way, for rate limiting only)
3. **Delete IPs after 7 days** (keep only for immediate spam prevention)

**Recommendation**: Hash IPs with salt, use for rate limiting only, don't store raw IPs.

---

#### Gap 7: Data Processing Agreements (DPAs)
**Violation**: GDPR Art. 28
**Risk**: Medium (regulatory, not technical)
**Timeline**: 2 weeks (legal/procurement)

**Action Items**:
1. Request DPA from Resend (email service)
2. Request DPA from PostHog (analytics) - ensure EU hosting option if needed
3. Request DPA from Sentry (error tracking)
4. Review Stripe DPA (should already have one)
5. Review Google Gemini terms for data processing
6. Document all DPAs in `/DATA_PROCESSING_AGREEMENTS.md`

---

### Priority 3: MEDIUM (Implement Within 3 Months)

#### Gap 8: Formal Access Request Process
**Current**: Privacy policy says users can email for data access
**Better**: Self-service portal

**Implementation**:
- Combine with Gap 2 (data export endpoint)
- Add "Download My Data" button in account settings
- Provides immediate export (better UX than email request)

---

#### Gap 9: Privacy Impact Assessment (DPIA)
**Requirement**: GDPR Art. 35 (if high risk processing)

**Needed?**: Likely YES due to:
- Large-scale user tracking (PostHog)
- Session recording (behavioral monitoring)
- Automated decision-making (AI summaries may qualify)

**Action**: Conduct formal DPIA and document findings

---

#### Gap 10: Breach Notification Mechanism
**Current**: Security policy mentions incident response but no technical process

**Implementation**:
```
1. Detection: Sentry alerts + monitoring
2. Assessment: Is PII affected? How many users?
3. Containment: Patch vulnerability
4. Notification:
   - Log to audit trail
   - Notify affected users via email (within 72 hours)
   - Notify supervisory authority if GDPR applies
   - Public disclosure if required
5. Post-mortem: Document and improve
```

**Files to create**:
- `/backend/app/security/breach_notification.py`
- `INCIDENT_RESPONSE_PLAN.md`

---

## 4. Enhanced Privacy Policy Updates

**File**: `/frontend/app/privacy/page.tsx`

**Required Additions**:

1. **Legal Basis for Processing** (GDPR requirement)
   - Add section explaining why each data type is collected
   - Example: "We process your email address based on contract (to provide service)"

2. **Specific Retention Periods** (Currently says "as long as necessary")
   - Replace with specific timelines from Gap 5

3. **Supervisory Authority Info** (GDPR Art. 77)
   - Add: "If you are in the EU, you have the right to lodge a complaint with your supervisory authority"
   - Link to list of EU DPAs

4. **Automated Decision-Making** (GDPR Art. 22)
   - If AI summaries constitute automated decision-making, disclose
   - Right to human review if decisions affect users

5. **International Transfers**
   - Clarify that data may be transferred to US
   - Explain safeguards (SCCs, adequacy decisions)

6. **Children's Data**
   - Current policy says "under 18" - GDPR is 16, COPPA is 13
   - Clarify: "We do not knowingly collect data from children under 13"

---

## 5. Technical Implementation Roadmap

### Phase 1: Critical Fixes (Weeks 1-4)

**Week 1**:
- [ ] Design user deletion endpoint logic
- [ ] Design data export endpoint logic
- [ ] Create cookie consent banner component
- [ ] Plan database cascade delete strategy

**Week 2**:
- [ ] Implement DELETE /api/users/me endpoint
- [ ] Implement GET /api/users/me/export endpoint
- [ ] Add account deletion UI in settings
- [ ] Add data export UI in settings
- [ ] Test deletion cascade

**Week 3**:
- [ ] Implement cookie consent banner
- [ ] Update PostHog initialization to respect consent
- [ ] Make session recording opt-in only
- [ ] Add cookie policy page
- [ ] Test consent flow

**Week 4**:
- [ ] Update privacy policy with specific retention periods
- [ ] Add legal basis for processing section
- [ ] Add supervisory authority info
- [ ] QA all changes end-to-end

### Phase 2: Data Retention (Weeks 5-8)

**Week 5-6**:
- [ ] Document data retention schedule
- [ ] Create data retention cleanup jobs
- [ ] Set up scheduler (cron or Celery)
- [ ] Test cleanup jobs in staging

**Week 7**:
- [ ] Hash IP addresses instead of storing plaintext
- [ ] Update contact form to use hashed IPs
- [ ] Migrate existing IP data

**Week 8**:
- [ ] Deploy retention jobs to production
- [ ] Monitor for issues
- [ ] Send email warnings before auto-deletion

### Phase 3: Legal & Documentation (Weeks 9-12)

**Week 9-10**:
- [ ] Request DPAs from all third-party processors
- [ ] Review and sign DPAs
- [ ] Document DPAs in repo

**Week 11**:
- [ ] Conduct Privacy Impact Assessment (DPIA)
- [ ] Document DPIA findings
- [ ] Implement any mitigations identified

**Week 12**:
- [ ] Create incident response plan
- [ ] Create breach notification system
- [ ] Train team on compliance processes
- [ ] Final compliance audit

---

## 6. Ongoing Compliance Processes

### Quarterly Reviews
- [ ] Review third-party processor security reports
- [ ] Audit data collection practices for changes
- [ ] Review and update privacy policy if services change
- [ ] Check for new regulations

### Annual Activities
- [ ] Full privacy policy review and update
- [ ] Security penetration testing
- [ ] Data retention policy effectiveness review
- [ ] Training refresh for team

### Continuous Monitoring
- Sentry alerts for security issues
- Monitor data breach news for third-party processors
- Track regulatory changes (GDPR, CCPA, etc.)

---

## 7. Cost & Resource Estimates

### Development Time
- Phase 1 (Critical): 80-100 hours (2-3 developer-weeks)
- Phase 2 (Retention): 40-60 hours (1-2 developer-weeks)
- Phase 3 (Legal): 20-30 hours + external legal review

### External Costs
- Legal review of privacy policy: $2,000-$5,000
- DPIA consulting (if needed): $3,000-$10,000
- DPA negotiations: Usually free with processors
- Compliance tools (optional): $100-$500/month

### Third-Party Service Changes
- PostHog EU hosting (if needed): May have pricing differences
- No other service changes required

---

## 8. Risk Assessment

### High Risk (Immediate Action Required)
1. **No deletion endpoint**: Direct GDPR violation, fines possible
2. **No data export**: Direct GDPR violation, fines possible
3. **No cookie consent**: ePrivacy Directive violation, common enforcement

### Medium Risk (Address Soon)
1. **Indefinite data retention**: GDPR Art. 5 violation if challenged
2. **No DPAs**: GDPR Art. 28 violation, regulatory issue
3. **IP address storage**: May be excessive under GDPR minimization

### Low Risk (Best Practices)
1. **No formal DPIA**: Required only if "high risk" (debatable)
2. **Breach notification process**: Only issue if breach occurs
3. **Privacy policy details**: Current policy is acceptable, enhancements improve compliance

---

## 9. Testing & Validation Plan

### User Deletion Testing
```
Test Cases:
1. Delete user with no data → Success
2. Delete user with searches, watchlist, summaries → All deleted
3. Delete user with active subscription → Stripe notified, subscription cancelled
4. Verify cascade deletes work for all foreign keys
5. Verify deletion audit log created
6. Verify confirmation emails sent
7. Test grace period cancellation
```

### Data Export Testing
```
Test Cases:
1. Export with minimal data → Correct JSON/CSV
2. Export with full data (all tables) → Complete export
3. Verify all sensitive data included
4. Verify export doesn't include other users' data
5. Test download link expiration
```

### Cookie Consent Testing
```
Test Cases:
1. First visit → Banner shows
2. Accept all → PostHog loads, session recording enabled
3. Reject analytics → PostHog doesn't load
4. Change preferences later → Settings persist
5. "Do Not Track" browser header → Respect preference
```

---

## 10. Success Metrics

### Compliance Metrics
- [ ] 100% of GDPR critical rights implemented (access, delete, portability)
- [ ] Cookie consent rate > 60% (industry average)
- [ ] Data deletion requests processed within 30 days (target: 1 day)
- [ ] Data export requests fulfilled within 1 day (target: instant)

### User Trust Metrics
- [ ] Privacy policy views (track engagement)
- [ ] Account deletion rate < 2% (excluding deletions for other reasons)
- [ ] Zero regulatory complaints or fines

### Technical Metrics
- [ ] Data retention jobs run successfully 100% of time
- [ ] Cascade deletes work without orphaned records
- [ ] Export endpoint performance < 5 seconds for typical user

---

## 11. Appendices

### A. Regulatory References
- **GDPR**: https://gdpr-info.eu/
- **CCPA/CPRA**: https://oag.ca.gov/privacy/ccpa
- **PIPEDA**: https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/
- **CAN-SPAM**: https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business

### B. Key Definitions
- **Personal Data**: Any information relating to an identified or identifiable person
- **Data Controller**: Entity that determines purposes and means of processing (EarningsNerd)
- **Data Processor**: Entity that processes data on behalf of controller (Stripe, Resend, etc.)
- **Data Subject**: Individual whose data is being processed (users)

### C. Contact Information
- **Privacy Inquiries**: privacy@earningsnerd.com (update in privacy policy)
- **Security Issues**: security@earningsnerd.com (update in security policy)
- **Data Protection Officer** (if appointed): TBD

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-22 | Compliance Team | Initial compliance plan |

**Next Review Date**: 2026-04-22 (3 months)

---

## Implementation Sign-Off

- [ ] Plan reviewed by engineering lead
- [ ] Plan reviewed by legal counsel
- [ ] Budget approved
- [ ] Timeline approved
- [ ] Implementation started

**Status**: AWAITING APPROVAL
