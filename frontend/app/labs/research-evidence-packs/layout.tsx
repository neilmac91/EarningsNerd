import { notFound } from 'next/navigation'
import { ENABLE_RESEARCH_EVIDENCE_PACKS } from '@/lib/featureFlags'

export default function ResearchEvidencePacksLayout({ children }: { children: React.ReactNode }) {
  if (!ENABLE_RESEARCH_EVIDENCE_PACKS) notFound()
  return <>{children}</>
}
