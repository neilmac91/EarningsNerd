/**
 * Horizontal "or" divider between the social buttons and the email form.
 */
export default function AuthDivider({ label = 'or' }: { label?: string }) {
  return (
    <div className="my-6 flex items-center gap-3">
      <div className="h-px flex-1 bg-border-light dark:bg-border-dark" />
      <span className="text-xs font-medium text-text-tertiary-light dark:text-text-tertiary-dark">
        {label}
      </span>
      <div className="h-px flex-1 bg-border-light dark:bg-border-dark" />
    </div>
  )
}
