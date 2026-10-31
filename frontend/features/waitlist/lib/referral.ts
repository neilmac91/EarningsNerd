/**
 * Spots a waitlist signup moves up for each person who joins with their referral link: REFERRAL_BONUS in
 * backend/app/services/waitlist_service.py, which calculate_waitlist_position applies. Mirrored for the
 * referral sentence on the waitlist success card; tests/unit/planLimitsLockstep.spec.ts fails when the two
 * differ or when copy types the number by hand.
 */
export const REFERRAL_BONUS = 5
