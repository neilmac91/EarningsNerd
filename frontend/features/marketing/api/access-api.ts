import api from '@/lib/api/client'
import type { SignupConfig } from '@/lib/serverApi'

/**
 * The registration gate for client pages: the same payload `lib/serverApi.fetchSignupConfig` reads
 * on the server for the landing page, validated the same way, so a client page's account CTA
 * follows the one access decision in `features/marketing/lib/access.ts`. An unknown mode resolves
 * to null and the caller fails closed to the invite copy.
 */
export const getRegistrationConfig = async (): Promise<SignupConfig | null> => {
  const { data } = await api.get<{ mode?: unknown; beta_promo_enabled?: unknown }>('/api/auth/registration')
  if (!data || (data.mode !== 'public' && data.mode !== 'invite_only')) return null
  return { mode: data.mode, beta_promo_enabled: data.beta_promo_enabled === true }
}
