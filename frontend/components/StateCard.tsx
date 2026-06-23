'use client'

import { CheckCircleIcon, InfoIcon, WarningCircleIcon } from '@/lib/icons'

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
    wrapper: 'border-brand-light/30 bg-brand-weak text-brand-strong dark:border-brand-dark/30 dark:bg-brand-dark/10 dark:text-brand-strong-dark',
    icon: 'text-brand-strong dark:text-brand-strong-dark',
  },
  success: {
    wrapper: 'border-success-light/30 bg-success-light/10 text-success-light dark:border-success-dark/40 dark:bg-success-dark/10 dark:text-success-dark',
    icon: 'text-success-light dark:text-success-dark',
  },
}

const VARIANT_ICONS = {
  error: WarningCircleIcon,
  info: InfoIcon,
  success: CheckCircleIcon,
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
