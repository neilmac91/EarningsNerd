# Data Compliance Implementation Checklist
## EarningsNerd - Quick Reference

**Last Updated**: January 22, 2026

This is a quick-reference checklist for implementing the full [Data Compliance Plan](DATA_COMPLIANCE_PLAN.md).

---

## Phase 1: Critical Fixes (Weeks 1-4) ⚠️ URGENT

### Week 1: Planning & Design
- [ ] Review full compliance plan with team
- [ ] Assign owners for each task
- [ ] Set up development branch for compliance work
- [ ] Design database cascade delete strategy
- [ ] Design user deletion confirmation flow
- [ ] Design data export format (JSON structure)
- [ ] Design cookie consent banner UI/UX
- [ ] Review with legal counsel (if available)

### Week 2: Core Endpoint Implementation
- [ ] **Backend**: Implement `DELETE /api/users/me` endpoint
  - [ ] Add confirmation email logic
  - [ ] Implement 24-hour grace period
  - [ ] Implement cascade delete for all user tables
  - [ ] Add third-party deletion notifications (Stripe, PostHog)
  - [ ] Add audit logging
  - [ ] Write unit tests
- [ ] **Backend**: Implement `GET /api/users/me/export` endpoint
  - [ ] Collect data from all user tables
  - [ ] Format as JSON (and optionally CSV)
  - [ ] Include: profile, searches, watchlist, summaries, usage
  - [ ] Write unit tests
- [ ] **Frontend**: Add "Delete Account" button in settings
  - [ ] Confirmation modal with warnings
  - [ ] Grace period cancellation option
  - [ ] Success/error messaging
- [ ] **Frontend**: Add "Export My Data" button in settings
  - [ ] Download/email options
  - [ ] Loading states
  - [ ] Success messaging

### Week 3: Cookie Consent & Analytics
- [ ] **Frontend**: Create `CookieConsent.tsx` component
  - [ ] Banner design (essential vs. analytics vs. functional)
  - [ ] LocalStorage consent tracking
  - [ ] "Change Preferences" link in footer
  - [ ] Respect "Do Not Track" header
- [ ] **Frontend**: Create `/cookie-policy` page (or expand privacy page)
  - [ ] Explain what cookies are used
  - [ ] Explain purpose of each cookie category
  - [ ] Link to manage preferences
- [ ] **Frontend**: Update `layout.tsx` to show banner on first visit
- [ ] **Frontend**: Update PostHog initialization in `providers.tsx`
  - [ ] Conditional initialization based on consent
  - [ ] Make session recording opt-in (separate from analytics)
  - [ ] Test consent flow end-to-end
- [ ] **Frontend**: Add preference toggle in settings for existing users

### Week 4: Privacy Policy Updates & QA
- [ ] **Frontend**: Update `/privacy/page.tsx` with:
  - [ ] Specific retention periods (replace "as long as necessary")
  - [ ] Legal basis for each data type (contract, consent, legitimate interest)
  - [ ] Add supervisory authority info for EU users
  - [ ] Add automated decision-making disclosure (if applicable)
  - [ ] Add international transfer safeguards (SCCs)
  - [ ] Add children's privacy clarification (under 13)
- [ ] **QA**: End-to-end testing
  - [ ] Test account deletion flow (with and without data)
  - [ ] Test data export completeness
  - [ ] Test cookie consent (accept, reject, change preferences)
  - [ ] Test PostHog doesn't load without consent
  - [ ] Test session recording opt-in
- [ ] **DevOps**: Deploy to staging
- [ ] **Team**: Final review before production
- [ ] **DevOps**: Deploy to production
- [ ] **Marketing**: Announce privacy improvements to users (optional)

---

## Phase 2: Data Retention (Weeks 5-8)

### Week 5: Retention Policy Documentation
- [ ] **Legal**: Finalize retention periods for each data type
- [ ] **Engineering**: Document retention policy (already created: `DATA_RETENTION_POLICY.md`)
- [ ] **Engineering**: Review database schema for retention requirements
- [ ] **Engineering**: Plan automated cleanup job architecture
  - [ ] Choose scheduler: Cron, Celery, or cloud scheduler
  - [ ] Define job frequency (daily at 2-3 AM UTC)
  - [ ] Plan failure notifications

### Week 6: Cleanup Job Implementation
- [ ] **Backend**: Create `/app/tasks/data_retention.py`
  - [ ] `cleanup_old_searches()` - Delete searches > 1 year old
  - [ ] `cleanup_old_contact_submissions()` - Delete submissions > 1 year old
  - [ ] `cleanup_old_waitlist()` - Delete unconverted waitlist > 1 year old
  - [ ] `cleanup_expired_tokens()` - Delete expired password reset/verification tokens
  - [ ] `cleanup_inactive_users()` - Delete users with no login in 2 years
  - [ ] Add logging for each cleanup operation
  - [ ] Add metrics/monitoring
- [ ] **Backend**: Create inactive user warning system
  - [ ] Email at 18 months inactivity: "Still there?"
  - [ ] Email at 22 months: "Account will be deleted soon"
  - [ ] Email at 23 months: "Final warning - 30 days to deletion"
  - [ ] Add `deletion_scheduled_at` column to users table
- [ ] **Backend**: Write unit tests for cleanup jobs
- [ ] **DevOps**: Set up scheduler (cron job or task queue)

### Week 7: IP Address Privacy Enhancement
- [ ] **Backend**: Update `contact.py` endpoint
  - [ ] Replace IP address storage with one-way hash
  - [ ] Use hash for rate limiting only
  - [ ] Remove raw IP from database schema (add migration)
- [ ] **Backend**: Migrate existing IP addresses
  - [ ] Hash existing IPs or delete if older than 7 days
  - [ ] Verify rate limiting still works with hashed IPs
- [ ] **QA**: Test contact form rate limiting with hashed IPs

### Week 8: Deployment & Monitoring
- [ ] **DevOps**: Deploy retention jobs to staging
- [ ] **QA**: Test cleanup jobs manually in staging
  - [ ] Verify correct data is deleted
  - [ ] Verify related data integrity (no orphans)
  - [ ] Check job logs and metrics
- [ ] **DevOps**: Deploy to production
- [ ] **Monitoring**: Set up alerts for job failures
- [ ] **Week 1 Post-Deploy**: Monitor cleanup job execution
  - [ ] Check logs daily for errors
  - [ ] Verify expected deletion counts
  - [ ] Verify no user complaints about unexpected deletions

---

## Phase 3: Legal & Documentation (Weeks 9-12)

### Week 9-10: Data Processing Agreements
- [ ] **Legal/Procurement**: Request DPA from **Resend**
  - [ ] Send email to Resend support requesting DPA
  - [ ] Review DPA for GDPR compliance (SCCs, data deletion terms)
  - [ ] Sign and file DPA
- [ ] **Legal/Procurement**: Request DPA from **PostHog**
  - [ ] Check if EU data hosting is needed
  - [ ] Review DPA, ensure GDPR compliance
  - [ ] Sign and file DPA
- [ ] **Legal/Procurement**: Request DPA from **Sentry**
  - [ ] Review DPA for data deletion/anonymization terms
  - [ ] Sign and file DPA
- [ ] **Legal/Procurement**: Review **Stripe** DPA
  - [ ] Should already exist (standard with Stripe)
  - [ ] Verify it covers GDPR requirements
  - [ ] File for records
- [ ] **Legal/Procurement**: Review **Google Gemini** terms
  - [ ] Check if PII is sent to Gemini (should be no)
  - [ ] Review data processing terms if EU users' queries go to AI
  - [ ] Document findings
- [ ] **Engineering**: Create `/DATA_PROCESSING_AGREEMENTS.md`
  - [ ] List all third-party processors
  - [ ] Link to DPA documents (or note "on file")
  - [ ] Include contact info for each processor
  - [ ] Note data flows to each processor

### Week 11: Privacy Impact Assessment (DPIA)
- [ ] **Legal/Engineering**: Conduct DPIA (Data Protection Impact Assessment)
  - [ ] Identify all processing activities
  - [ ] Assess necessity and proportionality
  - [ ] Identify risks to user privacy
  - [ ] Document mitigations
  - [ ] Consider consulting external privacy expert if budget allows
- [ ] **Engineering**: Implement any mitigations identified in DPIA
- [ ] **Legal**: Document DPIA findings
- [ ] **Legal**: Determine if DPIA needs to be submitted to supervisory authority (usually not unless high risk)

### Week 12: Incident Response & Final Audit
- [ ] **Security/Engineering**: Create `INCIDENT_RESPONSE_PLAN.md`
  - [ ] Define data breach detection procedures
  - [ ] Define escalation process
  - [ ] Define containment procedures
  - [ ] Define notification procedures (72 hours for GDPR)
  - [ ] Define user communication templates
  - [ ] Define post-mortem process
- [ ] **Engineering**: Implement breach notification system (basic)
  - [ ] Email template for user notification
  - [ ] Admin alert system
  - [ ] Incident logging
- [ ] **Team**: Conduct compliance training
  - [ ] Review privacy policy with support team
  - [ ] Review deletion/export request process
  - [ ] Review incident response plan
  - [ ] Q&A session
- [ ] **Security/Legal**: Final compliance audit
  - [ ] Verify all Phase 1 implementations working
  - [ ] Verify all Phase 2 cleanup jobs running
  - [ ] Verify all DPAs obtained
  - [ ] Verify privacy policy updated
  - [ ] Create compliance checklist report
- [ ] **Management**: Sign off on compliance implementation

---

## Ongoing: Maintenance & Monitoring

### Daily (Automated)
- [ ] Monitor cleanup job execution (logs)
- [ ] Monitor user deletion requests (queue)
- [ ] Monitor data export requests (queue)

### Weekly
- [ ] Review deletion/export request metrics
- [ ] Review cookie consent acceptance rates
- [ ] Check for failed cleanup jobs

### Monthly
- [ ] Review data retention compliance (sample audit)
- [ ] Review third-party processor security reports
- [ ] Check for regulatory updates

### Quarterly
- [ ] Full privacy policy review
- [ ] Data collection audit (any new data points?)
- [ ] Third-party processor review (any new processors?)
- [ ] User rights request review (access, delete, export)
- [ ] Update compliance documentation as needed

### Annually
- [ ] Full DPIA review and update
- [ ] Privacy policy major review and update
- [ ] Data retention policy review
- [ ] Security penetration test
- [ ] Compliance training refresh
- [ ] Regulatory landscape review (new laws?)

---

## Quick Reference: File Changes Required

### Backend Files to Create
```
/backend/app/routers/users.py (modify - add delete/export endpoints)
/backend/app/tasks/data_retention.py (new - cleanup jobs)
/backend/app/tasks/scheduler.py (new - job scheduler)
/backend/app/security/breach_notification.py (new - incident response)
```

### Frontend Files to Create/Modify
```
/frontend/app/components/CookieConsent.tsx (new)
/frontend/app/cookie-policy/page.tsx (new or expand privacy page)
/frontend/app/layout.tsx (modify - add cookie banner)
/frontend/app/providers.tsx (modify - conditional PostHog)
/frontend/app/privacy/page.tsx (modify - update policy)
/frontend/app/account/settings/page.tsx (modify - add delete/export buttons)
```

### Documentation Files
```
/DATA_COMPLIANCE_PLAN.md (created ✓)
/DATA_RETENTION_POLICY.md (created ✓)
/DATA_PROCESSING_AGREEMENTS.md (create in Phase 3)
/INCIDENT_RESPONSE_PLAN.md (create in Phase 3)
/README.md (update - add compliance section)
```

### Database Migrations
```
- Add: users.deletion_scheduled_at (timestamp, nullable)
- Modify: contact_submissions.ip_address → ip_hash (if switching to hashing)
- Add: audit_logs table (if not exists) for deletion tracking
```

---

## Priority Matrix

| Priority | Task | Impact | Effort | Timeline |
|----------|------|--------|--------|----------|
| 🔴 CRITICAL | User deletion endpoint | High | Medium | Week 2 |
| 🔴 CRITICAL | Data export endpoint | High | Medium | Week 2 |
| 🔴 CRITICAL | Cookie consent banner | High | Low | Week 3 |
| 🟡 HIGH | Privacy policy updates | Medium | Low | Week 4 |
| 🟡 HIGH | PostHog opt-in | Medium | Low | Week 3 |
| 🟡 HIGH | Data retention jobs | Medium | High | Week 6-7 |
| 🟡 HIGH | DPA collection | Medium | Low | Week 9-10 |
| 🟢 MEDIUM | IP hashing | Low | Medium | Week 7 |
| 🟢 MEDIUM | DPIA | Low | High | Week 11 |
| 🟢 MEDIUM | Incident response plan | Low | Medium | Week 12 |

---

## Success Criteria

### Phase 1 Complete When:
- [x] Users can delete their account via UI
- [x] Users can export all their data via UI
- [x] Cookie consent banner shows on first visit
- [x] PostHog doesn't load without consent
- [x] Privacy policy has specific retention periods
- [x] All changes deployed to production

### Phase 2 Complete When:
- [x] Automated cleanup jobs running daily
- [x] Inactive users receive warning emails
- [x] Old data is automatically deleted per schedule
- [x] IP addresses are hashed (not stored raw)
- [x] No manual intervention needed for retention

### Phase 3 Complete When:
- [x] All DPAs obtained and documented
- [x] DPIA conducted and documented
- [x] Incident response plan created
- [x] Team trained on compliance processes
- [x] Final audit completed and passed

---

## Resources & Contacts

**Internal**:
- Engineering Lead: [Name]
- Legal Counsel: [Name/Firm]
- Privacy Officer: [Name or TBD]

**External**:
- Resend Support: [support@resend.com]
- PostHog Support: [support@posthog.com]
- Sentry Support: [support@sentry.io]
- Stripe Support: [dashboard for tickets]

**Regulatory Resources**:
- GDPR Info: https://gdpr-info.eu/
- CCPA Resource Center: https://oag.ca.gov/privacy/ccpa
- IAPP (Privacy Professionals): https://iapp.org/

---

## Notes & Considerations

**Budget Considerations**:
- Legal review: $2,000-$5,000 (recommended)
- DPIA consulting: $3,000-$10,000 (optional, can do internally)
- PostHog EU hosting: Check pricing if needed
- Development time: ~200-250 hours total

**Risk Mitigation**:
- Start with Phase 1 immediately (highest compliance risk)
- Can parallelize some Phase 2 and 3 work
- If budget is tight, skip external DPIA consulting and do internally
- If time is tight, focus on deletion/export endpoints first (most critical)

**User Communication**:
- Announce privacy improvements via email (optional but good for trust)
- Update changelog/blog with compliance enhancements
- Highlight new data control features in onboarding

---

**Document Status**: Ready for Implementation
**Next Step**: Review with team and assign task owners
