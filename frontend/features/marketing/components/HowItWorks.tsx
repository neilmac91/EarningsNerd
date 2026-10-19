import FormCodeText from '@/features/marketing/components/FormCodeText'
import { FileTextIcon, LightningIcon, MagnifyingGlassIcon } from '@/lib/icons'

const STEPS = [
  {
    number: '01',
    title: 'Search a company',
    description: 'Any company with a ticker on SEC EDGAR, by name or ticker.',
    icon: MagnifyingGlassIcon,
  },
  {
    number: '02',
    title: 'Pick a filing',
    description: 'A 10-K, 10-Q or 20-F. We fetch it from SEC EDGAR.',
    icon: FileTextIcon,
  },
  {
    number: '03',
    title: 'Read the summary',
    description: 'Up to nine parts, written by the AI from the filing’s own text and XBRL, in the same order for every filing.',
    // The design repeats file-text here; the lightning glyph is the pre-redesign choice for
    // "get the summary" and keeps the three tiles distinct.
    icon: LightningIcon,
  },
] as const

/**
 * The compact three-step "how it works" row: icon tile, step number in the data face, title and
 * one line of description, each form code in it one unbroken run. It owns no section of its own;
 * SummaryContents renders it beneath the contents list in its ruled row, so headings here are h3
 * under that row's h2.
 */
export default function HowItWorks() {
  return (
    <ol className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {STEPS.map((step) => {
        const Icon = step.icon
        return (
          <li key={step.number} className="flex items-start gap-3.5">
            <span
              aria-hidden="true"
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-weak text-brand-strong dark:bg-brand-weak-dark dark:text-brand-strong-dark"
            >
              <Icon className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <div className="font-data text-data-xs text-text-secondary-light dark:text-text-secondary-dark">
                {step.number}
              </div>
              <h3 className="mt-0.5 text-base leading-6">{step.title}</h3>
              <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                <FormCodeText text={step.description} />
              </p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
