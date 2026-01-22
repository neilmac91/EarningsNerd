import React from 'react'
import { HelpCircle } from 'lucide-react'

interface EmptyStateProps {
  label: string
  message?: string
}

export function EmptyState({ label, message }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="bg-slate-100 p-4 rounded-full mb-4">
        <HelpCircle className="h-8 w-8 text-slate-400" />
      </div>
      <h3 className="text-lg font-medium text-slate-900">No {label} Found</h3>
      <p className="text-slate-500 max-w-sm mt-2">
        {message || "The AI couldn't extract this specific section from the filing. This usually means the company didn't report it in standard format."}
      </p>
    </div>
  )
}
