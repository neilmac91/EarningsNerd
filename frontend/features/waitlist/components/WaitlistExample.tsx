import { GuidanceCard } from '@/components/ui/GuidanceCard'
import HeroExample from '@/features/marketing/components/HeroExample'
import { fetchExampleData } from '@/lib/serverApi'

export function WaitlistExamplePending() {
  return <GuidanceCard title="Loading example…" description="You can join the waitlist while the example loads." />
}

/** Public, cached example only; keep its fetch outside the signup form's boundary. */
export default async function WaitlistExample() {
  const example = await fetchExampleData()
  if (!example) {
    return <GuidanceCard title="Example temporarily unavailable" description="You can still join the waitlist for early access." />
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
