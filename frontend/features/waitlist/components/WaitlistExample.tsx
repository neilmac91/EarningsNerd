import { GuidanceCard } from '@/components/ui/GuidanceCard'
import HeroExample from '@/features/marketing/components/HeroExample'
import { fetchExampleData } from '@/lib/serverApi'

export function WaitlistExamplePending() {
  return <GuidanceCard headingLevel="h2" title="Loading example…" description="You can explore the rest of the page while it loads." />
}

/** Public, cached example only; keep its fetch outside the signup form's boundary. */
export default async function WaitlistExample() {
  const example = await fetchExampleData()
  if (!example) {
    return <GuidanceCard headingLevel="h2" title="Example temporarily unavailable" description="You can still explore the rest of this page." />
  }
  return (
    <HeroExample
      example={example}
      ctaHref={`/filing/${example.filingId}`}
      ctaPlacement="waitlist_preview"
      ctaLabel="Read this filing summary"
    />
  )
}
