import localFont from 'next/font/local'

// One genuine italic face for promotional phrases; shared Inter and the wordmark keep their roles.
const brandItalic = localFont({
  src: '../../../scripts/brand/fonts/Inter-Variable-Italic-latin.woff2',
  weight: '100 900',
  style: 'italic',
  display: 'swap',
  variable: '--font-hero-italic',
  adjustFontFallback: false,
})

/** C5 promotional emphasis. The containing heading isolates its paint below neighboring glyphs. */
export default function BrandEmphasis({ children, trailingPeriod = false }: {
  children: string
  trailingPeriod?: boolean
}) {
  return (
    <span className={trailingPeriod ? 'en-hero-emphasis-group' : undefined}>
      <span className={`en-mark ${brandItalic.variable} en-hero-emphasis`}>{children}</span>{trailingPeriod ? '.' : null}
    </span>
  )
}
