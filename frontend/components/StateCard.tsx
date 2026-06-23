'use client'

import { AlertCircle, CheckCircle2, Info } from 'lucide-react'

type StateCardProps = {
  variant?: 'error' | 'info' | 'success'
  title: string
  message: string
  action?: React.ReactNode
}

const VARIANT_STYLES = {
  error: {
    wrapper: 'border-error-light/30 bg-error-light/10 text-error-light dark:border-error-dark/40 dark:bg-error-dark/10 dark:text-error-dark',
    icon: 'text-error-light dark:text-error-dark',
  },
  info: {
    wrapper: 'border-info-light/30 bg-info-light/10 text-info-light dark:border-info-dark/40 dark:bg-info-dark/10 dark:text-info-dark',
    icon: 'text-info-light dark:text-info-dark',
  },
  success: {
    wrapper: 'border-success-light/30 bg-success-light/10 text-success-light dark:border-success-dark/40 dark:bg-success-dark/10 dark:text-success-dark',
    icon: 'text-success-light dark:text-success-dark',
  },
}

const VARIANT_ICONS = {
  error: AlertCircle,
  info: Info,
  success: CheckCircle2,
}

export default function StateCard({ variant = 'info', title, message, action }: StateCardProps) {
  const styles = VARIANT_STYLES[variant]
  const Icon = VARIANT_ICONS[variant]

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
