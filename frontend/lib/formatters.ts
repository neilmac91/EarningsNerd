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

export interface ExecutiveSnapshot {
  headline: string | null
  keyPoints: string[]
  tone: string | null
  sourceSectionRef: string | null
}

const asTrimmedString = (v: unknown): string | null =>
  typeof v === 'string' && v.trim() ? v.trim() : null

// Parse the model's executive_snapshot object into its KNOWN fields (schema:
// openai_service.py:269-277). Returns null for strings, arrays, or objects with no recognizable
// content (headline + key_points) so callers fall back to the legacy markdown path. This replaces
// renderMarkdownValue for the snapshot, killing the "Headline:/Key Points:/Tone:/Source Section
// Ref:" field-name leak.
export const parseExecutiveSnapshot = (value: unknown): ExecutiveSnapshot | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const obj = value as Record<string, unknown>
  const headline = asTrimmedString(obj.headline)
  const keyPoints = Array.isArray(obj.key_points)
    ? obj.key_points.map(asTrimmedString).filter((p): p is string => Boolean(p))
    : []
  if (headline === null && keyPoints.length === 0) return null
  return {
    headline,
    keyPoints,
    tone: asTrimmedString(obj.tone),
    sourceSectionRef: asTrimmedString(obj.source_section_ref),
  }
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

  const sourceUrl =
    typeof riskObj.source_url === 'string' && riskObj.source_url.trim()
      ? riskObj.source_url.trim()
      : null
  const sourceSectionRef =
    typeof riskObj.source_section_ref === 'string' && riskObj.source_section_ref.trim()
      ? riskObj.source_section_ref.trim()
      : null

  return {
    summary: summaryCandidate,
    supporting_evidence: supportingEvidence,
    title: title || null,
    description: description || null,
    source_url: sourceUrl,
    source_verified: typeof riskObj.source_verified === 'boolean' ? riskObj.source_verified : null,
    source_section_ref: sourceSectionRef,
  }
}
