import React from 'react'
import { QuestionIcon } from '@/lib/icons'

interface EmptyStateProps {
  label: string
  message?: string
}

export function EmptyState({ label, message }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="bg-panel-light dark:bg-white/5 p-4 rounded-full mb-4">
        <QuestionIcon className="h-8 w-8 text-text-secondary-light dark:text-text-secondary-dark" />
      </div>
      <h3 className="text-lg font-medium text-text-primary-light dark:text-text-primary-dark">No {label} Found</h3>
      <p className="text-text-secondary-light dark:text-text-secondary-dark max-w-sm mt-2">
        {message || "The AI couldn't extract this specific section from the filing. This usually means the company didn't report it in standard format."}
      </p>
    </div>
  )
}
