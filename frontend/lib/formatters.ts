import type { RiskFactor } from '@/types/summary'

const evidenceKeys = ['excerpt', 'text', 'quote', 'source', 'reference', 'tag', 'xbrl_tag', 'xbrlTag', 'citation']

export const renderMarkdownValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return ''
  }
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    const items = value
      .map((item) => {
        const rendered = renderMarkdownValue(item)
        return rendered ? `- ${rendered}` : ''
      })
      .filter(Boolean)
    return items.join('\n')
  }
  if (typeof value === 'object') {
    return Object.entries(value)
      .map(([key, val]) => {
        const formattedKey = key
          .replace(/_/g, ' ')
          .replace(/\b\w/g, (char) => char.toUpperCase())
        const rendered = renderMarkdownValue(val)
        if (!rendered) {
          return ''
        }
        if (typeof val === 'object' && val !== null) {
          return `${formattedKey}:\n${rendered}`
        }
        return `${formattedKey}: ${rendered}`
      })
      .filter(Boolean)
      .join('\n')
  }
  return String(value)
}

export const getAccordionContent = (value: unknown): string | null => {
  if (value === null || value === undefined) {
    return null
  }

  const rendered = renderMarkdownValue(value)
  if (!rendered) {
    return null
  }

  return rendered.trim().length > 0 ? rendered : null
}

export const formatEvidence = (value: unknown): string => {
  if (!value) return ''
  if (Array.isArray(value)) {
    const parts = value.map((item) => formatEvidence(item)).filter(Boolean)
    return parts.join('; ')
  }
  if (typeof value === 'object') {
    const parts: string[] = []
    evidenceKeys.forEach((key) => {
      if (value && typeof value === 'object' && key in value) {
        const part = formatEvidence((value as Record<string, unknown>)[key])
        if (part) {
          parts.push(part)
        }
      }
    })
    if (parts.length === 0 && 'value' in (value as Record<string, unknown>)) {
      const fallback = formatEvidence((value as Record<string, unknown>).value)
      if (fallback) {
        parts.push(fallback)
      }
    }
    return parts.join(' | ')
  }
  if (typeof value === 'string') {
    return value.trim()
  }
  return String(value).trim()
}

export const normalizeRisk = (risk: unknown): RiskFactor | null => {
  if (!risk || typeof risk !== 'object') {
    return null
  }

  const riskObj = risk as Record<string, unknown>
  const title = typeof riskObj.title === 'string' ? riskObj.title.trim() : null
  const description = typeof riskObj.description === 'string' ? riskObj.description.trim() : null
  const summaryCandidate =
    (typeof riskObj.summary === 'string' && riskObj.summary.trim()) ||
    (description && description) ||
    (title && title) ||
    ''

  if (!summaryCandidate) {
    return null
  }

  const supportingEvidence = formatEvidence(
    riskObj.supporting_evidence ?? riskObj.supportingEvidence ?? riskObj.evidence ?? riskObj.source
  )

  if (!supportingEvidence) {
    return null
  }

  return {
    summary: summaryCandidate,
    supporting_evidence: supportingEvidence,
    title: title || null,
    description: description || null,
  }
}
