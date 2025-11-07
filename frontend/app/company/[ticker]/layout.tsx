import { generateMetadata as genMeta } from './metadata'

export async function generateMetadata({ params }: { params: { ticker: string } }) {
  return genMeta({ params })
}

export default function CompanyLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}

