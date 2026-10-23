import { Skeleton } from '@/components/ui'
import { ENABLE_APPLE_SIGNIN, TURNSTILE_ENABLED } from '@/lib/featureFlags'

function FieldBone({ multiline = false }: { multiline?: boolean }) {
  return <div className="space-y-2">
    <Skeleton className="h-5 w-28" />
    <Skeleton className={multiline ? 'h-40 w-full' : 'h-11 w-full'} />
  </div>
}

/** Destination-shaped bones reserve the form's space without mounting fields or CAPTCHA. */
export function CollectionLoading({ surface }: { surface: 'contact' | 'waitlist' }) {
  const contact = surface === 'contact'
  const label = contact ? 'Checking contact availability' : 'Checking waitlist availability'
  return <div role="status" aria-label={label} className={contact
    ? 'space-y-6 rounded-2xl border border-border-light bg-panel-light p-cap-8 shadow-e3 dark:border-white/10 dark:bg-panel-dark dark:shadow-none'
    : 'space-y-4 rounded-xl border border-border-light bg-panel-light p-cap-6 shadow-e1 dark:border-border-dark dark:bg-panel-dark dark:shadow-none'}>
    <span className="sr-only">{label}</span>
    <FieldBone />
    <FieldBone />
    {contact && <>
      <FieldBone />
      <FieldBone multiline />
      <Skeleton className="h-5 w-48" />
    </>}
    {TURNSTILE_ENABLED && <Skeleton className="h-16 w-full" />}
    <Skeleton className="h-11 w-full" />
  </div>
}

export function RegistrationLoading({ invited, emailVisible, socialOffered }: { invited: boolean; emailVisible: boolean; socialOffered: boolean }) {
  return <div role="status" aria-label="Checking registration availability" className="mt-8 space-y-6">
    <span className="sr-only">Checking registration availability</span>
    {invited && <Skeleton className="h-24 w-full rounded-xl" />}
    <div className="space-y-3">
      <Skeleton className="h-5 w-40" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
    {socialOffered && <div className="space-y-3">
      {ENABLE_APPLE_SIGNIN && <Skeleton className="h-11 w-full" />}
      <Skeleton className="h-11 w-full" />
      <Skeleton className="mx-auto h-5 w-20" />
    </div>}
    {emailVisible && <div className="space-y-4">
      <FieldBone />
      <FieldBone />
      <FieldBone />
      <Skeleton className="h-10 w-full" />
      {TURNSTILE_ENABLED && <Skeleton className="h-16 w-full" />}
    </div>}
    <Skeleton className="h-11 w-full" />
  </div>
}
