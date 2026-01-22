import api from '@/lib/api/client'

export interface Usage {
  summaries_used: number
  summaries_limit: number | null
  is_pro: boolean
  month: string
}

export interface SubscriptionStatus {
  is_pro: boolean
  stripe_customer_id: string | null
  stripe_subscription_id: string | null
  subscription_status: string | null
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
