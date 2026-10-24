import api from '@/lib/api/client'

export interface LegalOperator {
  legal_name: string
  postal_address: string
  country: string
  contact_email: string
}

export interface LegalReadiness {
  collection_available: boolean
  checkout_available: boolean
  marketing_available: boolean
  terms_version: string
  eligibility_version: string
  operator: LegalOperator | null
}

export interface AccountAgreement {
  adult_eligible: true
  terms_accepted: true
  terms_version: string
  eligibility_version: string
}

/** No storage or query cache: each mounted collection surface reads the current release decision. */
export async function getLegalReadiness(signal?: AbortSignal): Promise<LegalReadiness> {
  const { data } = await api.get<LegalReadiness>('/api/legal/readiness', { signal })
  if (!data || typeof data.collection_available !== 'boolean' ||
      typeof data.checkout_available !== 'boolean' || typeof data.marketing_available !== 'boolean' ||
      typeof data.terms_version !== 'string' || !data.terms_version ||
      typeof data.eligibility_version !== 'string' || !data.eligibility_version ||
      ((data.collection_available || data.checkout_available || data.marketing_available) && data.operator === null) ||
      (data.operator !== null && (!data.operator ||
        !['legal_name', 'postal_address', 'country', 'contact_email'].every(
          (key) => typeof data.operator?.[key as keyof LegalOperator] === 'string' &&
            Boolean(data.operator[key as keyof LegalOperator].trim()),
        )))) {
    throw new Error('Availability could not be checked.')
  }
  return data
}
