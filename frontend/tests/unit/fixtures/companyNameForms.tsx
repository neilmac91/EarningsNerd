/**
 * Planted forms for companyNameDisplay.spec.ts (a served company name prints through formatCompanyName, E146): one
 * exported function per form, each marked in the comment before it. `flag` is a form the gate must name: one that
 * breaks the rule, or one it fails closed on (N50). `clean` is a look-alike that must pass. `gap` is a form the rule
 * forbids and the gate leaves to review (its header names it), so it must pass too, until the gate reaches it and the
 * mark flips. The spec reads this file in the same program as the app, so the checker reads the app's own types here,
 * and scores every form on every run: a change to the gate that loses a form, or catches a look-alike, fails there.
 * A top-level helper named for a form (N23Line) is that form's, so what the gate names inside it scores there.
 * Outside the scan roots. Sample companies only. A new form the rule can take joins it with its mark.
 */
import {
  Fragment,
  createContext,
  createElement,
  useContext,
  useDeferredValue,
  useMemo,
  useReducer,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from 'react'
import type { Metadata } from 'next'
import Link from 'next/link'
import { Bar } from 'recharts'
import { toast } from 'sonner'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge, DataTable, Notice } from '@/components/ui'
import { formatCompanyName, formatCompanyName as titleCase } from '@/lib/formatCompanyName'
import * as Names from '@/lib/formatCompanyName'
import analytics from '@/lib/analytics'
import { CompanyIdentity } from '@/features/companies/components/CompanyIdentity'
import AskFilingCallout from '@/features/filings/components/copilot/AskFilingCallout'
import type { AnalysisCoverage, AnalysisDataset } from '@/features/analysis/api/analysis-api'
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'
import type { Company } from '@/features/companies/api/companies-api'
import type { ContactSubmission } from '@/features/contact/api/contact-api'
import type { Filing } from '@/features/filings/api/filings-api'
import type { NotificationItem } from '@/features/notifications/api/notifications-api'
import type { FullTextSearchHit } from '@/features/search/api/search-api'
import type { WatchlistItem } from '@/features/watchlist/api/watchlist-api'
import type { ChartExportHeader } from '@/features/analysis/lib/chartExport'
import type { RedlineSource } from '@/features/filing-redlines/lib/filingPair'
import type { SourceIdentity } from '@/features/research-evidence-packs/lib/evidenceLedger'
import type { SampleFact } from '@/features/financial-refresh-review/lib/refreshReview'
import type { ExampleData } from '@/lib/serverApi'
import { displayNameOf, labelsOf, lengthOf, nameOf } from './companyNameKit'
import { shortNameOf } from './companyNameKit2'

/** A view model of this file's own, so its fields are the app's own (declared outside an API module). */
interface LineView {
  ticker: string
  company_name: string
}

/** A same-file component whose prop is a company-name field: the app's own, filled by its callers. */
function NameRow({ companyName }: { companyName: string }) {
  return <p>{companyName}</p>
}

const EventContext = createContext<CalendarEvent | null>(null)
const shout = (ev: CalendarEvent) => ev.company_name
const keepSource = (source: RedlineSource) => source
const shown = (ev: CalendarEvent) => formatCompanyName(ev.company_name)
const fmt = formatCompanyName

// The rule broken: a served name printed raw (A), or one of the app's own fields filled with one (B).

/** N01 flag: a served `company_name` as an element's child, the notification bell's line. */
export function N01({ item }: { item: NotificationItem }) {
  return <span>{item.company_name}</span>
}

/** N02 flag: an optional read with a fallback, the analysis page's coverage line. */
export function N02({ coverage, ticker }: { coverage?: AnalysisCoverage; ticker: string }) {
  return <span>{coverage?.company_name || ticker}</span>
}

/** N03 flag: a company's `name`. */
export function N03({ company }: { company: Company }) {
  return <h2>{company.name}</h2>
}

/** N04 flag: a filing's company read through an optional chain. */
export function N04({ filing }: { filing: Filing }) {
  return <p>{filing.company?.name}</p>
}

/** N05 flag: a filing's company read through `!`. */
export function N05({ filing }: { filing: Filing }) {
  return <p>{filing.company!.name}</p>
}

/** N06 flag: a full-text search hit's `company`, with its fallback. */
export function N06({ hit }: { hit: FullTextSearchHit }) {
  return <span>{hit.company ?? 'Unknown filer'}</span>
}

/** N07 flag: a read by a literal key. */
export function N07({ ev }: { ev: CalendarEvent }) {
  return <span>{ev['company_name']}</span>
}

/** N08 flag: a destructured field. */
export function N08({ ev }: { ev: CalendarEvent }) {
  const { company_name } = ev
  return <span>{company_name}</span>
}

/** N09 flag: a destructured field under another name. */
export function N09({ ev }: { ev: CalendarEvent }) {
  const { company_name: label } = ev
  return <span>{label}</span>
}

/** N10 flag: a field destructured by a map callback's parameter. */
export function N10({ events }: { events: CalendarEvent[] }) {
  return <ul>{events.map(({ ticker, company_name }) => <li key={ticker}>{company_name}</li>)}</ul>
}

/** N11 flag: a field destructured two levels down in a component's props. */
export function N11({ company: { name } }: { company: Company }) {
  return <span>{name}</span>
}

/** N12 flag: a const that holds it. */
export function N12({ ev }: { ev: CalendarEvent }) {
  const name = ev.company_name
  return <span>{name}</span>
}

/** N13 flag: a template literal child. */
export function N13({ ev }: { ev: CalendarEvent }) {
  return <span>{`${ev.company_name} · ${ev.ticker}`}</span>
}

/** N14 flag: a concatenation. */
export function N14({ ev }: { ev: CalendarEvent }) {
  return <span>{ev.company_name + ' (' + ev.ticker + ')'}</span>
}

/** N15 flag: a method of the raw string. */
export function N15({ ev }: { ev: CalendarEvent }) {
  return <span>{ev.company_name.trim()}</span>
}

/** N16 flag: a global handed it. */
export function N16({ ev }: { ev: CalendarEvent }) {
  return <span>{String(ev.company_name)}</span>
}

/** N17 flag: a conditional's raw arm. */
export function N17({ ev, plain }: { ev: CalendarEvent; plain: boolean }) {
  return <span>{plain ? ev.company_name : formatCompanyName(ev.company_name)}</span>
}

/** N18 flag: the right of `&&`. */
export function N18({ ev }: { ev: CalendarEvent }) {
  return <span>{ev.ticker && ev.company_name}</span>
}

/** N19 flag: an imported component's children. */
export function N19({ ev }: { ev: CalendarEvent }) {
  return <Badge>{ev.company_name}</Badge>
}

/** N20 flag: React's Fragment's children. */
export function N20({ ev }: { ev: CalendarEvent }) {
  return <Fragment>{ev.company_name}</Fragment>
}

/** N21 flag: an imported component's text prop. */
export function N21({ ev }: { ev: CalendarEvent }) {
  return <Notice title={ev.company_name} />
}

/** N22 flag: a label built from it and handed to a component that prints it, the summary's ask label. */
export function N22({ filing }: { filing: Filing }) {
  const subjectName = filing.company?.ticker || filing.company?.name
  const subjectLabel = subjectName ? `${subjectName}’s ${filing.filing_type}` : `this ${filing.filing_type}`
  return <AskFilingCallout filingType={filing.filing_type} subjectLabel={subjectLabel} onAsk={() => undefined} />
}

/** N23's component, which prints a label it is handed. */
function N23Line({ label }: { label: string }) {
  return <p>{label}</p>
}

/** N23 flag: a same-file component's prop, printed where the component prints it. */
export function N23({ ev }: { ev: CalendarEvent }) {
  return <N23Line label={ev.company_name} />
}

/** N24's component, which passes its children through. */
function N24Pass({ children }: { children: ReactNode }) {
  return <>{children}</>
}

/** N24 flag: a same-file component that passes its children through. */
export function N24({ ev }: { ev: CalendarEvent }) {
  return <N24Pass>{ev.company_name}</N24Pass>
}

/** N25 flag: a same-file helper's return. */
export function N25({ ev }: { ev: CalendarEvent }) {
  return <span>{shout(ev)}</span>
}

/** N26 flag: useMemo's callback. */
export function N26({ ev }: { ev: CalendarEvent }) {
  const name = useMemo(() => ev.company_name, [ev])
  return <span>{name}</span>
}

/** N27 flag: a field's value. */
export function N27({ ev }: { ev: CalendarEvent }) {
  return <input readOnly value={ev.company_name} />
}

/** N28 flag: an option's label. */
export function N28({ ev }: { ev: CalendarEvent }) {
  return (
    <select defaultValue={ev.ticker}>
      <option value={ev.ticker} label={ev.company_name} />
    </select>
  )
}

/** N29 flag: an array child. */
export function N29({ ev }: { ev: CalendarEvent }) {
  return <span>{[ev.company_name]}</span>
}

/** N30 flag: an array joined into a line. */
export function N30({ ev }: { ev: CalendarEvent }) {
  return <span>{[ev.ticker, ev.company_name].join(' · ')}</span>
}

/** N31 flag: a column's render, which the table prints (a row the table takes: a picked type, as an interface is not). */
export function N31({ events }: { events: Array<Pick<CalendarEvent, 'ticker' | 'company_name'>> }) {
  return <DataTable rows={events} rowKey={(ev) => ev.ticker} columns={[{ key: 'name', header: 'Company', render: (ev) => ev.company_name }]} />
}

/** N32 flag: the landing example's data, which lib/serverApi.ts serves as the backend sends it. */
export function N32({ data }: { data: ExampleData }) {
  return <span>{data.companyName}</span>
}

/** N33 flag: an element held in a const, read where it is written. */
export function N33({ ev }: { ev: CalendarEvent }) {
  const line = <p>{ev.company_name}</p>
  return <div>{line}</div>
}

/** N34 flag: inner HTML. */
export function N34({ ev }: { ev: CalendarEvent }) {
  return <p dangerouslySetInnerHTML={{ __html: ev.company_name }} />
}

/** N35 flag: children given by a prop. */
export function N35({ ev }: { ev: CalendarEvent }) {
  // eslint-disable-next-line react/no-children-prop -- planted AST form: children given by a prop, which app code may not write.
  return <p children={ev.company_name} />
}

/** N36 flag: CompanyLogo's `name`, the calendar's mark. */
export function N36({ ev }: { ev: CalendarEvent }) {
  return <CompanyLogo decorative ticker={ev.ticker} name={ev.company_name} />
}

/** N37 flag: CompanyLogo's `name` through a fallback, the analysis page's mark. */
export function N37({ coverage, ticker }: { coverage?: AnalysisCoverage; ticker: string }) {
  return <CompanyLogo decorative ticker={ticker} name={coverage?.company_name || ticker} />
}

/** N38 flag: CompanyLogo's `name` through a const. */
export function N38({ data }: { data: ExampleData }) {
  const name = data.companyName
  return <CompanyLogo decorative ticker={data.ticker} name={name} />
}

/** N39 flag: a served company spread whole into CompanyLogo's props. */
export function N39({ company }: { company: Company }) {
  return <CompanyLogo decorative {...company} />
}

/** N40 flag: a same-file component's company-name prop filled with a served name. */
export function N40({ ev }: { ev: CalendarEvent }) {
  return <NameRow companyName={ev.company_name} />
}

/** N41 flag: a mapper that stops formatting, the redlines' source (placed by its return type). */
export function N41(filing: Filing): RedlineSource {
  return { filingId: filing.id, companyName: filing.company!.name, conformedName: filing.company!.name, ticker: filing.company!.ticker, reportDate: '', filingDate: '', accession: '', originalUrl: null }
}

/** N42 flag: a mapper that stops formatting through Object.freeze, the evidence ledger's identity. */
export function N42(filing: Filing): SourceIdentity {
  return Object.freeze({
    filingId: filing.id, companyId: filing.company!.id, companyName: filing.company!.name, conformedName: filing.company!.name, ticker: filing.company!.ticker,
    form: filing.filing_type, accession: filing.accession_number, reportDate: '', filedDate: '', originalUrl: null, fictional: false,
  })
}

/** N43 flag: a typed const filled with a served name, the chart export's header. */
export function N43(dataset: AnalysisDataset): ChartExportHeader {
  const header: ChartExportHeader = { company: dataset.company_name, ticker: dataset.ticker, title: 'Revenue', legend: [] }
  return header
}

/** N44 flag: an assignment to the app's own field. */
export function N44(dataset: AnalysisDataset, header: ChartExportHeader): ChartExportHeader {
  header.company = dataset.company_name
  return header
}

/** N45 flag: a logical assignment to it. */
export function N45(dataset: AnalysisDataset, header: { company?: string }): void {
  header.company ??= dataset.company_name
}

/** N46 flag: a served object spread into a view of the app's own. */
export function N46(ev: CalendarEvent): LineView {
  return { ...ev }
}

/** N47 flag: a literal the checker cannot place, a company-name key filled with a served name. */
export function N47(ev: CalendarEvent) {
  return { companyName: ev.company_name, ticker: ev.ticker }
}

/** N48 flag: `name` beside `ticker` in a literal the checker cannot place. */
export function N48(company: Company) {
  return { ticker: company.ticker, name: company.name }
}

/** N49 flag: a formatter of the file's own that returns the name unformatted. */
export function N49({ ev }: { ev: CalendarEvent }) {
  const label = (e: CalendarEvent) => e.company_name
  return <span>{label(ev)}</span>
}

/** N50 flag: fails closed, a prop the gate cannot tell never prints (the table's row key). */
export function N50({ events }: { events: Array<Pick<CalendarEvent, 'ticker' | 'company_name'>> }) {
  return <DataTable rows={events} rowKey={(ev) => ev.company_name} columns={[]} />
}

/** N51 flag: a page's title, which Next prints in the tab. */
export async function N51(company: Company): Promise<Metadata> {
  return { title: `${company.name} SEC filings | EarningsNerd` }
}

/** N52 flag: a social card's title. */
export function N52(company: Company): Metadata {
  return { openGraph: { title: company.name } }
}

/** N53 flag: a loop's destructuring, pushed into a list that prints. */
export function N53({ events }: { events: CalendarEvent[] }) {
  const names: string[] = []
  for (const { company_name } of events) names.push(company_name)
  return <p>{names.join(', ')}</p>
}

/** N54 flag: a context's value, typed as the API's. */
export function N54() {
  const ev = useContext(EventContext)
  return <span>{ev?.company_name}</span>
}

/** N55's component, which returns the name as text. */
function N55Name({ ev }: { ev: CalendarEvent }) {
  return ev.company_name
}

/** N55 flag: a same-file component that returns the served name as text. */
export function N55({ ev }: { ev: CalendarEvent }) {
  return (
    <p>
      <N55Name ev={ev} />
    </p>
  )
}

/** N56 flag: a view model filled where a parameter's type places the literal. */
export function N56(filing: Filing) {
  return keepSource({ filingId: filing.id, companyName: filing.company!.name, ticker: '', reportDate: '', filingDate: '', accession: '', originalUrl: null })
}

/** N57 flag: a view model filled in a literal that `satisfies` places. */
export function N57(filing: Filing) {
  return { filingId: filing.id, companyName: filing.company!.name, ticker: '', reportDate: '', filingDate: '', accession: '', originalUrl: null } satisfies RedlineSource
}

/** N58 flag: fails closed, an imported function handed the name, whose return is no name (its length). */
export function N58({ ev }: { ev: CalendarEvent }) {
  return <span>{lengthOf(ev.company_name)}</span>
}

// Look-alikes that print the display form, or keep the raw name where it is data.

/** N59 clean: the display form. */
export function N59({ ev }: { ev: CalendarEvent }) {
  return <span>{formatCompanyName(ev.company_name)}</span>
}

/** N60 clean: the formatter imported under another name. */
export function N60({ ev }: { ev: CalendarEvent }) {
  return <span>{titleCase(ev.company_name)}</span>
}

/** N61 clean: the formatter read from the module's namespace. */
export function N61({ ev }: { ev: CalendarEvent }) {
  return <span>{Names.formatCompanyName(ev.company_name)}</span>
}

/** N62 clean: the formatter held in a same-file const. */
export function N62({ ev }: { ev: CalendarEvent }) {
  return <span>{fmt(ev.company_name)}</span>
}

/** N63 clean: the display form with the ticker as its fallback. */
export function N63({ coverage, ticker }: { coverage?: AnalysisCoverage; ticker: string }) {
  const name = formatCompanyName(coverage?.company_name) || ticker
  return (
    <span>
      <CompanyLogo decorative ticker={ticker} name={name} />
      {name}
    </span>
  )
}

/** N64 clean: the display form in a template literal. */
export function N64({ ev }: { ev: CalendarEvent }) {
  return <span>{`${formatCompanyName(ev.company_name)} · ${ev.ticker}`}</span>
}

/** N65 clean: a same-file helper that formats. */
export function N65({ ev }: { ev: CalendarEvent }) {
  return <span>{shown(ev)}</span>
}

/** N66 clean: a key, an href and a data attribute keep the raw name. */
export function N66({ ev }: { ev: CalendarEvent }) {
  return (
    <Link key={ev.company_name} href={`/search?q=${encodeURIComponent(ev.company_name)}`} data-company={ev.company_name}>
      {ev.ticker}
    </Link>
  )
}

/** N67 clean: a title attribute that quotes the filing, and an aria-label, which are not printed text. */
export function N67({ ev }: { ev: CalendarEvent }) {
  return (
    <span title={ev.company_name} aria-label={`Open ${ev.company_name}`}>
      {ev.ticker}
    </span>
  )
}

/** N68 clean: an analytics property. */
export function N68({ company }: { company: Company }) {
  return (
    <button type="button" onClick={() => analytics.companyViewed(company.ticker, company.name)}>
      {company.ticker}
    </button>
  )
}

/** N69 clean: a cache row typed as the API's own type holds the name as the API serves it. */
export function N69(company: Company): WatchlistItem {
  return { id: -1, company_id: company.id, created_at: '', company: { id: company.id, ticker: company.ticker, name: company.name } }
}

/** N70 clean: a CSV keeps the raw name. */
export function N70({ ev }: { ev: CalendarEvent }) {
  const csv = ['Company', ev.company_name].join(',')
  return <a href={`data:text/csv,${encodeURIComponent(csv)}`}>Download CSV</a>
}

/** N71 clean: a comparison. */
export function N71({ ev, other }: { ev: CalendarEvent; other: string }) {
  return <span>{ev.company_name === other ? 'Same company' : 'Another company'}</span>
}

/** N72 clean: a field of the app's own, formatted where it was filled. */
export function N72({ source }: { source: RedlineSource }) {
  return <p>{source.companyName}</p>
}

/** N73 clean: a company-name prop printed inside its component, filled by its callers. */
export function N73() {
  return <NameRow companyName="Sample Industries" />
}

/** N74 clean: CompanyLogo's `name` written by hand. */
export function N74() {
  return <CompanyLogo decorative ticker="SMPL" name="Sample Industries Inc." />
}

/** N75 clean: a field of the app's own filled by hand, a fictional example. */
export function N75(): RedlineSource {
  return { filingId: null, companyName: 'Harbor Vale Industries', ticker: 'Fictional company', reportDate: '', filingDate: '', accession: '', originalUrl: null }
}

/** N76 clean: a person's name, which is no company's (its type declares no ticker). */
export function N76({ submission }: { submission: ContactSubmission }) {
  return <span>{submission.name}</span>
}

/** N77 clean: a company handed whole to a component that formats it. */
export function N77({ company }: { company: Company }) {
  return <CompanyIdentity company={company} latest={null} />
}

/** N78 clean: the ticker. */
export function N78({ ev }: { ev: CalendarEvent }) {
  return <span>{ev.ticker}</span>
}

/** N79 clean: the display form handed to a company-name prop. */
export function N79({ ev }: { ev: CalendarEvent }) {
  return <NameRow companyName={formatCompanyName(ev.company_name)} />
}

/** N80 clean: a data payload whose type has an index signature, as analytics' properties. */
export function N80(ev: CalendarEvent): Record<string, unknown> {
  return { company_name: ev.company_name, ticker: ev.ticker }
}

/** N81 clean: `name` with no `ticker` beside it, a breadcrumb's. */
export function N81(company: Company) {
  return { position: 1, name: company.name }
}

/** N82 clean: an API row filled from another API row keeps the served name. */
export function N82(ev: CalendarEvent): CalendarEvent {
  return { ...ev, company_name: ev.company_name }
}

/** N83 clean: a field named for a company that holds no name, read where its fills are written by hand. */
export function N83({ fact }: { fact: SampleFact }) {
  return <span>{fact.company}</span>
}

/** N84 clean: a page's title and description in the display form. */
export function N84(company: Company): Metadata {
  const name = formatCompanyName(company.name)
  return { title: `${name} SEC filings | EarningsNerd`, description: `${name} filings from SEC EDGAR.` }
}

/** N85's component, which never prints the children it is handed. */
function N85Drop({ children }: { children?: ReactNode }) {
  return <td>{children ? 'Listed' : null}</td>
}

/** N85 clean: a same-file component that never prints the children it is handed. */
export function N85({ ev }: { ev: CalendarEvent }) {
  return <N85Drop>{ev.company_name}</N85Drop>
}

// A name handed back across modules or kept in React's state: the gate follows another module's function to what it
// hands back, and React's state to where it gives the name back.

/** N86 flag: a name another module's function hands back as a plain string. */
export function N86({ ev }: { ev: CalendarEvent }) {
  return <span>{nameOf(ev)}</span>
}

/** N89 flag: React state, its initial value a served name. */
export function N89({ ev }: { ev: CalendarEvent }) {
  const [name] = useState(ev.company_name)
  return <span>{name}</span>
}

/** N103 flag: a name handed back through two modules (a helper that trims another module's). */
export function N103({ ev }: { ev: CalendarEvent }) {
  return <span>{shortNameOf(ev)}</span>
}

/** N104 clean: another module's function that hands back the display form. */
export function N104({ ev }: { ev: CalendarEvent }) {
  return <span>{displayNameOf(ev)}</span>
}

/** N105 flag: a state's setter handed a served name after the state is made. */
export function N105({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useState('')
  return (
    <button type="button" onClick={() => setName(ev.company_name)}>
      {name}
    </button>
  )
}

/** N106 flag: a state's setter handed an updater that returns a served name. */
export function N106({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useState('')
  return (
    <button type="button" onClick={() => setName(() => ev.company_name)}>
      {name}
    </button>
  )
}

/** N107 flag: a ref that keeps a served name. */
export function N107({ ev }: { ev: CalendarEvent }) {
  const ref = useRef(ev.company_name)
  // eslint-disable-next-line react-hooks/refs -- planted AST form: a ref read while rendering, which app code may not write.
  return <span>{ref.current}</span>
}

/** N108 flag: a reducer's initial argument, a served name. */
export function N108({ ev }: { ev: CalendarEvent }) {
  const [name] = useReducer((current: string, next: string) => next, ev.company_name)
  return <span>{name}</span>
}

/** N116 flag: React state whose initializer returns a served name. */
export function N116({ ev }: { ev: CalendarEvent }) {
  const [name] = useState(() => ev.company_name)
  return <span>{name}</span>
}

/** N114 flag: a reducer's dispatcher handed a served name, which the reducer gives back as the state. */
export function N114({ ev }: { ev: CalendarEvent }) {
  const [name, dispatch] = useReducer((_current: string, next: string) => next, '')
  return (
    <button type="button" onClick={() => dispatch(ev.company_name)}>
      {name}
    </button>
  )
}

/** N115 flag: a ref's `current` set to a served name after the ref is made. */
export function N115({ ev }: { ev: CalendarEvent }) {
  const ref = useRef('')
  // eslint-disable-next-line react-hooks/refs -- planted AST form: a ref written while rendering, which app code may not write.
  ref.current = ev.company_name
  // eslint-disable-next-line react-hooks/refs -- planted AST form: a ref read while rendering, which app code may not write.
  return <span>{ref.current}</span>
}

/** N109 flag: a deferred value of a served name. */
export function N109({ ev }: { ev: CalendarEvent }) {
  const name = useDeferredValue(ev.company_name)
  return <span>{name}</span>
}

/** N110 flag: an external store's snapshot that returns a served name. */
export function N110({ ev }: { ev: CalendarEvent }) {
  const name = useSyncExternalStore(() => () => {}, () => ev.company_name)
  return <span>{name}</span>
}

/** N111 clean: React's state that keeps the display form, or the object the name is served on, read by its type where
    it prints. */
export function N111({ ev }: { ev: CalendarEvent }) {
  const [name] = useState(formatCompanyName(ev.company_name))
  const [event] = useState(ev)
  return (
    <span>
      {name} · {formatCompanyName(event.company_name)}
    </span>
  )
}

// Forms the rule forbids that the gate leaves to review, each named in the spec's header.

/** N87 gap: a prop typed as a plain string, filled in another module. */
export function N87({ label }: { label: string }) {
  return <span>{label}</span>
}

/** N88 gap: an indexed access type, which carries no field. */
export function N88({ value }: { value: CalendarEvent['company_name'] }) {
  return <span>{value}</span>
}

/** N90 gap: a name served under another field. */
export function N90({ filer }: { filer: { ticker: string; issuer: string } }) {
  return <span>{filer.issuer}</span>
}

/** N91 gap: a read by a key the scan cannot read. */
export function N91({ ev, key }: { ev: CalendarEvent; key: 'company_name' | 'ticker' }) {
  return <span>{ev[key]}</span>
}

/** N92 gap: the display form shouted again. */
export function N92({ ev }: { ev: CalendarEvent }) {
  return <span>{formatCompanyName(ev.company_name).toUpperCase()}</span>
}

/** N93 gap: React's element call, which app code may not write (earningsnerd/elements-built-with-jsx). */
export function N93({ ev }: { ev: CalendarEvent }) {
  return createElement('span', null, ev.company_name)
}

/** N94 gap: a piece of the name read by index from what a call hands back. */
export function N94({ ev }: { ev: CalendarEvent }) {
  return <span>{ev.company_name.split(' ')[0]}</span>
}

/** N95 gap: a name read from a type that declares no field for it (an index signature). */
export function N95({ row }: { row: Record<string, string> }) {
  return <span>{row.company_name}</span>
}

/** N96 flag: a `name` prop of a component the scan cannot read, which prints it (a chart series' name, in its tooltip). */
export function N96({ ev }: { ev: CalendarEvent }) {
  return <Bar dataKey="eps_estimate" name={ev.company_name} />
}

/** N97 flag: the app's own copy of the served name, kept as data, printed. */
export function N97({ source }: { source: SourceIdentity }) {
  return <p>{source.conformedName}</p>
}

/** N98 clean: the served name kept as data beside the display form, in a field of the app's own made for it. */
export function N98(filing: Filing): Pick<SourceIdentity, 'companyName' | 'conformedName'> {
  return { companyName: formatCompanyName(filing.company!.name), conformedName: filing.company!.name }
}

/** N99 clean: a download's record, a data payload typed with an index signature, carrying the served name. */
export function N99({ conformedName, ...source }: SourceIdentity): Record<string, unknown> {
  return { ...source, companyName: conformedName }
}

/** N100 gap: text a call puts on the screen outside JSX, a toast's message. */
export function N100({ ev }: { ev: CalendarEvent }) {
  toast.success(`${ev.company_name} added to your watchlist`)
  return null
}

/** N101 gap: text a call puts on the screen outside JSX, the tab's title. */
export function N101({ ev }: { ev: CalendarEvent }) {
  document.title = `${ev.company_name} · EarningsNerd`
  return null
}

/** N102 gap: a component the scan cannot read that prints a row's field by key, a DataTable column with no render. */
export function N102({ events }: { events: CalendarEvent[] }) {
  return <DataTable rows={events} rowKey={(row) => row.ticker} columns={[{ key: 'company_name', header: 'Company' }]} />
}

/** N112's component, handed a state's setter under a type of its own. */
function N112Pick({ ev, onPick }: { ev: CalendarEvent; onPick: (name: string) => void }) {
  return (
    <button type="button" onClick={() => onPick(ev.company_name)}>
      Pick
    </button>
  )
}

/** N112 gap: a state's setter handed on to a component, and called there. */
export function N112({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useState('')
  return (
    <>
      <N112Pick ev={ev} onPick={setName} />
      <span>{name}</span>
    </>
  )
}

/** N113 gap: a name inside an object another module's function hands back. */
export function N113({ ev }: { ev: CalendarEvent }) {
  return <span>{labelsOf(ev).title}</span>
}
