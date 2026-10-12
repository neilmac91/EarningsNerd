import { needsSourceCheck, qualityReasons, sourceUrl, type QualityValue } from '@/features/analysis/lib/provenance'

/** Small disclosure shared by the filing-scoped and peer-series surfaces. */
export default function SourceChecks({ values }: { values: (QualityValue & { label: string; source_url?: string | null })[] }) {
  const issues = values.filter(needsSourceCheck)
  const unavailable = values.filter((value) => value.provenance?.validation === 'unavailable')
  const unknown = values.some((value) => !value.provenance || value.provenance.validation === 'unavailable')
  return (
    <details className="mt-3 text-xs text-text-secondary-light dark:text-text-secondary-dark">
      <summary className="cursor-pointer rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Sources &amp; checks</summary>
      <div className="mt-2 space-y-2">
        <p>Figures come from SEC filings; some may be calculated. Source checks describe the data, not an audit of the company’s accounts.</p>
        {unknown && <p>Detailed validation is unavailable for some saved figures. No verification claim is made for them.</p>}
        {issues.map((value, index) => <p key={index}>{value.label}: {qualityReasons(value).join(' ')}</p>)}
        {unavailable.map((value, index) => <p key={`unavailable-${index}`}>{value.label}: unavailable. {qualityReasons(value).join(' ')}</p>)}
        {values.map((value, index) => {
          const href = sourceUrl(value.source_url ?? value.provenance?.source_url)
          return href ? <p key={index}><a href={href} target="_blank" rel="noopener noreferrer" className="rounded text-brand-strong underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark">{value.label} · original SEC filing</a></p> : null
        })}
      </div>
    </details>
  )
}
