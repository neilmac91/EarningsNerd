import RegisterForm from '@/features/auth/components/RegisterForm'
import { resolveAccessMode } from '@/features/marketing/lib/access'
import { fetchSignupConfig } from '@/lib/serverApi'

/**
 * The signup page follows the backend's registration gate the same way the landing page and the
 * header CTA do (hourly ISR read of /api/auth/registration; unreachable backend = invite mode).
 * In invite-only mode an uninvited visitor is not offered the social buttons, because the backend
 * refuses to create an account from a social sign-in without an invite.
 */
export default async function RegisterPage() {
  const accessMode = resolveAccessMode(await fetchSignupConfig())
  return <RegisterForm inviteOnly={accessMode === 'invite'} />
}
