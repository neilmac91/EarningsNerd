import { Badge, Card } from '@/components/ui'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { FCF_DEFINITION, needsSourceCheck, qualityReasons } from '@/features/analysis/lib/provenance'

export default function SourcesMethods({ dataset }: { dataset: AnalysisDataset }) {
  const points = dataset.series.flatMap((series) => series.points.map((point) => ({ ...point, label: series.label })))
  const comparisons = dataset.series.flatMap((series) => [
    ...series.points.flatMap((point) => {
      const qoq = dataset.mode === 'quarterly' && point.qoq != null
      return (qoq ? point.qoq : point.yoy) == null ? [] : [{ label: `${series.label} ${qoq ? 'QoQ' : 'YoY'} growth`, period: point.period, provenance: qoq ? point.qoq_provenance : point.yoy_provenance, reconciled: qoq ? point.qoq_reconciled : point.yoy_reconciled }]
    }),
    ...(series.cagr == null && series.window_pp == null ? [] : [{ label: `${series.label} window change`, period: series.cagr_window ?? series.window_pp_range ?? dataset.period_key, provenance: series.percent ? series.window_pp_provenance : series.cagr_provenance, reconciled: series.percent ? series.window_pp_reconciled : series.cagr_reconciled }]),
  ])
  const issues = [...points, ...comparisons].filter(needsSourceCheck)
  const missing = points.filter((point) => point.value == null)
  const unknown = points.filter((point) => point.value != null && (!point.provenance || point.provenance.validation === 'unavailable'))
  const calculated = points.some((point) => point.provenance?.method === 'calculated' || (!point.provenance && point.derived))
  return (
    <Card as="section" className="p-4">
      <details>
        <summary className="cursor-pointer rounded text-sm font-medium text-text-primary-light focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-text-primary-dark dark:focus-visible:shadow-ring-brand-dark">
          Sources &amp; methods <span className="font-normal text-text-secondary-light dark:text-text-secondary-dark">· SEC filings{calculated ? ' · includes calculated figures' : ''}</span>
          {issues.length > 0 && <span className="ml-2"><Badge variant="warning">{issues.length} source {issues.length === 1 ? 'check' : 'checks'} needed</Badge></span>}
        </summary>
        <div className="mt-3 space-y-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          <p>Select a figure in the metrics table to inspect its source, reporting period and calculation. † marks a calculated figure; it is not an error warning. Growth and ratios are calculated from the same source inputs.</p>
          <p>Quarterly cash flows may be calculated by subtracting earlier year-to-date totals. Fourth-quarter flow figures may be calculated from annual totals less the first nine months. Earnings per share uses a reported quarterly figure; it is not subtracted from annual EPS.</p>
          <p>{FCF_DEFINITION}</p>
          <p>Missing values are unavailable in this dataset, not zero. Growth is unavailable when its comparison period or compatible inputs are missing.</p>
          {(missing.length > 0 || unknown.length > 0) && <p>{missing.length} values unavailable · {unknown.length} populated values without detailed validation. Missing validation is not a claim that a figure passed checks.</p>}
          {issues.length > 0 && <ul className="list-disc space-y-1 pl-5">{issues.map((point, index) => <li key={index}>{point.label}, {point.period}: {qualityReasons(point).join(' ')}</li>)}</ul>}
          <p>{dataset.data_as_of ? `Source data as of ${dataset.data_as_of}.` : 'Source refresh time is unavailable.'} Source matching and automated checks do not constitute an audit of the company’s accounts.</p>
          {dataset.snapshot_id && <details><summary className="cursor-pointer rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Report reference</summary><p className="font-data break-all text-xs">{dataset.dataset_version} · {dataset.snapshot_id}</p></details>}
        </div>
      </details>
    </Card>
  )
}
