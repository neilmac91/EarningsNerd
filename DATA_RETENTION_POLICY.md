# Data Retention Policy
## EarningsNerd

**Effective Date**: January 22, 2026
**Policy Owner**: Engineering & Legal Teams
**Review Frequency**: Annual

---

## 1. Purpose

This policy defines how long EarningsNerd retains user data and the procedures for secure deletion. This policy ensures compliance with:
- GDPR Article 5(e) - Storage Limitation
- CCPA/CPRA data minimization requirements
- PIPEDA Principle 4.5 - Limiting Use, Disclosure, and Retention

---

## 2. Retention Schedules

### 2.1 User Account Data

| Data Type | Retention Period | Deletion Trigger | Automated |
|-----------|------------------|------------------|-----------|
| Email address | Account lifetime + 30 days after deletion request | User deletion or 2 years inactivity | Yes |
| Hashed password | Account lifetime | User deletion or 2 years inactivity | Yes |
| Full name | Account lifetime | User deletion or 2 years inactivity | Yes |
| Profile settings | Account lifetime | User deletion or 2 years inactivity | Yes |
| Account creation date | Account lifetime + 7 years (audit) | 7 years after account deletion | Yes |
| Last login timestamp | Account lifetime | User deletion or 2 years inactivity | Yes |

**Inactivity Definition**: No login for 24 consecutive months

**Inactivity Warning Process**:
1. Email warning at 18 months of inactivity
2. Email warning at 22 months of inactivity
3. Final email warning at 23 months of inactivity
4. Automatic deletion at 24 months if no response

### 2.2 Authentication & Security Data

| Data Type | Retention Period | Deletion Trigger | Automated |
|-----------|------------------|------------------|-----------|
| JWT tokens | Until expiration (24 hours) | Token expiry | Yes |
| Password reset tokens | Until expiration (1 hour) | Token expiry | Yes |
| Email verification tokens | Until expiration (24 hours) | Token expiry or verification | Yes |
| Failed login attempts | 7 days | Rolling 7-day window | Yes |
| Security audit logs | 3 years | 3 years from event | Yes |

### 2.3 User-Generated Content

| Data Type | Retention Period | Deletion Trigger | Automated |
|-----------|------------------|------------------|-----------|
| Search history | 1 year | 1 year from search date OR user deletion | Yes |
| Saved summaries | Until user deletes | Manual deletion by user OR account deletion | Partial |
| Watchlist items | Until user deletes | Manual deletion by user OR account deletion | Partial |
| Custom notes (if added) | Until user deletes | Manual deletion by user OR account deletion | Partial |

**Note**: User-generated content is deleted when:
1. User manually deletes the item, OR
2. User deletes entire account, OR
3. Account is auto-deleted due to inactivity

### 2.4 Usage & Analytics Data

| Data Type | Retention Period | Deletion Trigger | Automated |
|-----------|------------------|------------------|-----------|
| Monthly usage counts | Current billing cycle + 12 months | 12 months after billing cycle | Yes |
| API request logs | 90 days | 90 days from request | Yes |
| PostHog analytics events | Per PostHog policy (configurable) | PostHog retention setting | Via PostHog |
| PostHog session recordings | 30 days (if user opted in) | 30 days OR user deletion | Via PostHog |
| Sentry error logs | 90 days | 90 days OR user deletion | Via Sentry |

**PostHog Configuration**: Set retention to 90 days maximum for all events

**User Deletion Impact**: When user deletes account, send deletion request to:
- PostHog (delete user profile and associated events)
- Sentry (anonymize user in error logs)

### 2.5 Communication Data

| Data Type | Retention Period | Deletion Trigger | Automated |
|-----------|------------------|------------------|-----------|
| Contact form submissions | 1 year | 1 year from submission date | Yes |
| Support ticket emails | 2 years | 2 years from ticket closure | Yes |
| Marketing email subscriptions | Until unsubscribe | User unsubscribe OR account deletion | Yes |
| Transactional email logs (Resend) | 30 days | Resend automatic deletion | Via Resend |

### 2.6 Waitlist Data

| Data Type | Retention Period | Deletion Trigger | Automated |
|-----------|------------------|------------------|-----------|
| Waitlist signups (unconverted) | 1 year | 1 year from signup OR manual deletion | Yes |
| Waitlist signups (converted to user) | Merged into user account | Account deletion | Yes |
| Referral codes | 1 year from last activity | 1 year inactive OR user deletion | Yes |
| Referral tracking data | 1 year | 1 year from referral event | Yes |

**Conversion Definition**: User signs up for account using waitlist email

### 2.7 Payment & Billing Data

| Data Type | Retention Period | Deletion Trigger | Automated |
|-----------|------------------|------------------|-----------|
| Stripe Customer ID | Account lifetime + 7 years | 7 years after account deletion | No (legal hold) |
| Stripe Subscription ID | Subscription lifetime + 7 years | 7 years after subscription end | No (legal hold) |
| Billing history | 7 years (tax requirement) | 7 years from transaction | No (legal hold) |
| Payment method details | N/A (stored by Stripe only) | Immediate (Stripe handles) | Via Stripe |
| Invoice records | 7 years (tax requirement) | 7 years from invoice date | No (legal hold) |

**Legal Requirement**: Payment data retained for 7 years per US tax law (IRS) and general accounting standards

**Important**: Payment card details are NEVER stored in EarningsNerd database (Stripe PCI-DSS handles)

### 2.8 IP Addresses & Technical Data

| Data Type | Retention Period | Deletion Trigger | Automated |
|-----------|------------------|------------------|-----------|
| IP addresses (hashed, rate limiting) | 7 days | 7 days from request | Yes |
| IP addresses (contact form) | **TO BE REMOVED** | Immediate (hash instead) | Implementation pending |
| Browser fingerprints | N/A (not collected) | N/A | N/A |
| Device identifiers | N/A (not collected) | N/A | N/A |

**Planned Change**: Replace IP address storage with one-way hashing for privacy

---

## 3. Data Deletion Procedures

### 3.1 User-Initiated Deletion

**Endpoint**: `DELETE /api/users/me`

**Process**:
1. User requests account deletion via settings page
2. System sends confirmation email with unique deletion link
3. User clicks confirmation link (24-hour grace period)
4. System begins deletion process:
   - Deletes from `users` table (triggers cascade)
   - Deletes from `user_searches` table
   - Deletes from `saved_summaries` table
   - Deletes from `watchlist` table
   - Deletes from `user_usage` table
   - Notifies Stripe to delete customer (or mark as deleted)
   - Notifies PostHog to delete user profile
   - Anonymizes user in Sentry error logs
5. System logs deletion in audit trail (anonymized)
6. System sends final confirmation email
7. Deletion completes within 30 days (per GDPR requirement)

**Grace Period**: User can cancel deletion within 24 hours of confirmation

### 3.2 Automated Deletion (Inactivity)

**Schedule**: Daily job at 2:00 AM UTC

**Query**:
```sql
SELECT id, email FROM users
WHERE last_login_at < NOW() - INTERVAL '2 years'
AND deletion_scheduled_at IS NULL;
```

**Process**:
1. Identify inactive accounts (24 months no login)
2. Send final warning email: "Your account will be deleted in 7 days"
3. Set `deletion_scheduled_at = NOW() + 7 days`
4. Wait 7 days
5. If no login occurs, proceed with deletion (same as user-initiated)

**Override**: User login resets `last_login_at` and cancels scheduled deletion

### 3.3 Automated Data Cleanup Jobs

**Schedule**: Daily at 3:00 AM UTC

**Jobs**:

1. **Old Search History Cleanup**
   ```sql
   DELETE FROM user_searches
   WHERE created_at < NOW() - INTERVAL '1 year';
   ```

2. **Old Contact Submissions Cleanup**
   ```sql
   DELETE FROM contact_submissions
   WHERE created_at < NOW() - INTERVAL '1 year';
   ```

3. **Old Waitlist Cleanup** (unconverted only)
   ```sql
   DELETE FROM waitlist_signups
   WHERE created_at < NOW() - INTERVAL '1 year'
   AND email NOT IN (SELECT email FROM users);
   ```

4. **Expired Tokens Cleanup**
   ```sql
   DELETE FROM password_reset_tokens
   WHERE expires_at < NOW();

   DELETE FROM email_verification_tokens
   WHERE expires_at < NOW();
   ```

5. **Old Audit Logs Cleanup**
   ```sql
   DELETE FROM audit_logs
   WHERE created_at < NOW() - INTERVAL '3 years';
   ```

### 3.4 Third-Party Data Deletion

When user account is deleted, send deletion requests to:

**Stripe**:
```python
stripe.Customer.delete(user.stripe_customer_id)
# OR mark as deleted and schedule purge after 7 years
```

**PostHog**:
```python
posthog.capture(
    distinct_id=user.id,
    event='$delete',
    properties={'$delete': True}
)
```

**Sentry**:
```python
# Anonymize user in existing error logs
# (Sentry doesn't support full deletion, anonymize instead)
```

**Resend**:
- Automatically deletes email logs after 30 days (no action needed)
- Remove from email lists/audiences if applicable

---

## 4. Data Retention Exceptions

### 4.1 Legal Hold

Data retention schedules are suspended if:
- Active litigation or legal investigation
- Regulatory inquiry or audit
- Suspected fraud or security incident under investigation

**Process**: Legal team notifies engineering to place hold on specific user accounts

### 4.2 Compliance & Audit Requirements

Some data MUST be retained longer than standard schedule:
- **Tax records**: 7 years (IRS requirement)
- **Payment transactions**: 7 years (financial regulations)
- **Security audit logs**: 3 years (compliance best practice)

### 4.3 Anonymized Data

Data that has been fully anonymized (no PII linkable) may be retained indefinitely for:
- Product analytics
- Business intelligence
- Research and development

**Anonymization Requirements**:
- Remove all direct identifiers (name, email, user ID)
- Remove all indirect identifiers (IP, unique device IDs)
- Aggregate to prevent re-identification
- No way to link back to individual

---

## 5. User Rights & Data Access

### 5.1 Right to Access (GDPR Art. 15, CCPA)

Users can view their data at any time:
- Profile settings: `/account/settings`
- Search history: `/account/history`
- Saved summaries: `/dashboard/saved`
- Watchlist: `/dashboard/watchlist`

**Data Export**: Users can download all their data via `GET /api/users/me/export`

### 5.2 Right to Rectification (GDPR Art. 16)

Users can update their data:
- Email: Account settings (requires verification)
- Name: Account settings
- Password: Account settings
- Preferences: Account settings

### 5.3 Right to Erasure (GDPR Art. 17, CCPA)

Users can delete their account at any time via `DELETE /api/users/me` (see section 3.1)

### 5.4 Right to Restriction (GDPR Art. 18)

Users can request processing restriction by contacting privacy@earningsnerd.com

---

## 6. Data Minimization Practices

### 6.1 Collection Minimization

**Only collect data that is**:
- Necessary for service delivery
- Required for legal compliance
- Explicitly consented to by user

**Examples**:
- ✅ Email: Required for account and communication
- ✅ Password: Required for authentication
- ❌ Phone number: NOT collected (not necessary)
- ❌ Physical address: NOT collected (not necessary)
- ⚠️ IP address: Minimized (hash for rate limiting only)

### 6.2 Storage Minimization

**Practices**:
- Hash sensitive data when exact value not needed (e.g., IPs)
- Aggregate usage data where possible (monthly totals vs. individual events)
- Delete immediately after purpose fulfilled (e.g., expired tokens)
- Use shortest retention period feasible

### 6.3 Regular Audits

**Quarterly Review**:
- [ ] Review all data collection points
- [ ] Verify retention periods are followed
- [ ] Check for data that can be deleted early
- [ ] Identify new data being collected

---

## 7. Backup & Archive Retention

### 7.1 Database Backups

**Schedule**: Daily incremental, weekly full backup

**Retention**:
- Daily backups: 7 days
- Weekly backups: 4 weeks
- Monthly backups: 12 months

**Deleted Data in Backups**: Deleted user data may persist in backups during retention period but:
- Backups are encrypted
- Backups are access-restricted
- Backups are not used for operational purposes
- User data in backups is effectively "frozen" and inaccessible

**Post-Retention**: Backups are securely deleted after retention period

### 7.2 Disaster Recovery

In event of data restoration from backup:
- Re-apply deletions that occurred after backup date
- Verify deleted users are not restored
- Audit restored data for compliance

---

## 8. Monitoring & Compliance

### 8.1 Automated Monitoring

**Daily Checks**:
- Cleanup jobs completed successfully
- No failed deletions
- Backup retention within limits

**Weekly Checks**:
- Inactive account identification
- Warning emails sent successfully
- Third-party deletion requests acknowledged

**Monthly Checks**:
- Retention policy adherence (sample audits)
- Data volume trends
- Unusual retention patterns

### 8.2 Compliance Reporting

**Quarterly Report** (to management):
- Number of user deletion requests processed
- Number of inactive accounts deleted
- Data volume by category
- Compliance incidents (if any)

**Annual Report**:
- Full retention policy effectiveness review
- Recommendations for policy updates
- Regulatory changes impact assessment

---

## 9. Roles & Responsibilities

| Role | Responsibility |
|------|---------------|
| **Engineering Team** | Implement and maintain automated deletion jobs, ensure cascade deletes work |
| **Legal Team** | Define retention periods, handle legal holds, review policy annually |
| **Customer Support** | Process user deletion requests, verify identity, handle exceptions |
| **Security Team** | Audit deletion processes, ensure secure deletion, monitor compliance |
| **Product Team** | Ensure new features comply with retention policy |

---

## 10. Policy Changes

**Version History**:

| Version | Date | Changes | Approved By |
|---------|------|---------|-------------|
| 1.0 | 2026-01-22 | Initial policy creation | Pending |

**Review Schedule**: Annual review on January 22 each year

**Change Process**:
1. Proposed changes reviewed by Legal and Engineering
2. Privacy impact assessed
3. User notification if retention periods change
4. Privacy policy updated to reflect changes

---

## 11. Contact & Questions

For questions about this policy:
- **Privacy Team**: privacy@earningsnerd.com
- **Data Protection Officer** (if appointed): TBD

For user data requests:
- **Account Deletion**: Use in-app settings or email privacy@earningsnerd.com
- **Data Export**: Use in-app settings or email privacy@earningsnerd.com
- **Other Requests**: privacy@earningsnerd.com

---

**Document Status**: DRAFT - Pending Implementation

**Implementation Blockers**:
- [ ] Automated deletion jobs not yet implemented
- [ ] User deletion endpoint not yet implemented
- [ ] Third-party deletion integration not yet implemented
- [ ] Cleanup job scheduler not yet configured

**Target Implementation Date**: March 31, 2026
