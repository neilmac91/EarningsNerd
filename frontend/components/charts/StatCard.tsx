import clsx from 'clsx'
import { ReactNode } from 'react'

interface StatCardProps {
  label: string
  value: string
  subtext?: ReactNode
  accent?: 'primary' | 'muted'
}

export const StatCard = ({ label, value, subtext, accent = 'primary' }: StatCardProps) => (
  <div
    className={clsx(
      'rounded-lg border bg-white p-4 shadow-sm',
      accent === 'primary' ? 'border-slate-200' : 'border-slate-100'
    )}
  >
    <p className="text-sm font-medium text-slate-500">{label}</p>
    <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    {subtext ? <div className="mt-2 text-xs text-slate-500">{subtext}</div> : null}
  </div>
)

export default StatCard
