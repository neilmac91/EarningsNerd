import type { Metadata } from 'next'
import ResearchEvidencePacks from '@/features/research-evidence-packs/components/ResearchEvidencePacks'

export const metadata: Metadata = {
  title: 'Research evidence packs prototype | EarningsNerd',
  description: 'Keep filing evidence separate from interpretation and review it before reuse.',
  robots: { index: false, follow: false },
}
export default function ResearchEvidencePacksPage() {
  return <ResearchEvidencePacks />
}
