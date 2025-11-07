import { Metadata } from 'next'

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  // In a real app, you'd fetch filing data here
  return {
    title: 'SEC Filing Summary | EarningsNerd',
    description: 'AI-powered summary of SEC filing with financial highlights, risk factors, and management insights.',
    openGraph: {
      title: 'SEC Filing Summary | EarningsNerd',
      description: 'AI-powered summary of SEC filing with financial highlights and insights.',
      type: 'website',
    },
  }
}

export default function FilingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}

