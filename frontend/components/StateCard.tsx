'use client'

import { AlertCircle, Info } from 'lucide-react'

type StateCardProps = {
  variant?: 'error' | 'info'
  title: string
  message: string
  action?: React.ReactNode
}

const VARIANT_STYLES = {
  error: {
    wrapper: 'border-red-200 bg-red-50 text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200',
    icon: 'text-red-600 dark:text-red-300',
  },
  info: {
    wrapper: 'border-gray-200 bg-white text-slate-700 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200',
    icon: 'text-slate-500 dark:text-slate-300',
  },
}

export default function StateCard({ variant = 'info', title, message, action }: StateCardProps) {
  const styles = VARIANT_STYLES[variant]
  const Icon = variant === 'error' ? AlertCircle : Info

  return (
    <div className={`rounded-2xl border p-4 sm:p-6 ${styles.wrapper}`}>
      <div className="flex items-start gap-3">
        <Icon className={`mt-0.5 h-5 w-5 ${styles.icon}`} />
        <div className="flex-1 space-y-2">
          <p className="text-sm font-semibold">{title}</p>
          <p className="text-sm leading-relaxed text-current/80">{message}</p>
          {action && <div className="pt-2">{action}</div>}
        </div>
      </div>
    </div>
  )
}
