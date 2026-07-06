import api from '@/lib/api/client'

export interface Usage {
  summaries_used: number
  summaries_limit: number | null
  is_pro: boolean
  month: string
  /** Copilot Q&A questions used this month. */
  qa_used: number
  /** PRO fair-use soft cap on Copilot questions per month. */
  qa_limit: number
  /** FREE "taste" of Copilot (roadmap 2.2): lifetime grounded questions spent so far. */
  copilot_free_taste_used: number
  /** FREE plan's lifetime taste allowance (0 for PRO, which is unlimited via qa_limit). */
  copilot_free_taste_total: number
  /** Multi-Period Analysis generations this month (fresh AI narratives only; cached re-serves are free). */
  analysis_used: number
  /** PRO fair-use soft cap on fresh analysis generations per month. */
  analysis_limit: number
}

export interface SubscriptionStatus {
  is_pro: boolean
  stripe_customer_id: string | null
  stripe_subscription_id: string | null
  subscription_status: string | null
  plan: string
  status: string | null
  trial_end: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
}

// Subscription APIs
export const getUsage = async (): Promise<Usage> => {
  const response = await api.get('/api/subscriptions/usage')
  return response.data
}

export const getSubscriptionStatus = async (): Promise<SubscriptionStatus> => {
  const response = await api.get('/api/subscriptions/subscription')
  return response.data
}

export const createCheckoutSession = async (priceId: string): Promise<{ url: string }> => {
  const response = await api.post('/api/subscriptions/create-checkout-session', null, {
    params: { price_id: priceId }
  })
  return response.data
}

export const createPortalSession = async (): Promise<{ url: string }> => {
  const response = await api.post('/api/subscriptions/create-portal-session')
  return response.data
}
