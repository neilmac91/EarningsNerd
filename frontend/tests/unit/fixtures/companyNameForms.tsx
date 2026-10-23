/**
 * Planted forms for companyNameDisplay.spec.ts (a served company name prints through formatCompanyName, E146): one
 * exported function per form, each marked in the comment before it. `flag` is a form the gate must name: one that
 * breaks the rule, or one it fails closed on (N50). `clean` is a look-alike that must pass. `gap` is a form the rule
 * forbids and the gate leaves to review (its header names it), so it must pass too, until the gate reaches it and the
 * mark flips. The spec reads this file in the same program as the app, so the checker reads the app's own types here,
 * and scores every form on every run: a change to the gate that loses a form, or catches a look-alike, fails there.
 * A top-level helper named for a form (N23Line) is that form's, so what the gate names inside it scores there.
 * Forms that need a module of their own (a module's default export, a component another module renders) live in
 * companyNameRendered/, scored with these, each the statement its comment marks. Outside the scan roots. Sample
 * companies only. A new form the rule can take joins it with its mark.
 */
import {
  Component,
  Fragment,
  createContext,
  createElement,
  forwardRef,
  lazy,
  useActionState,
  useContext,
  useDeferredValue,
  useImperativeHandle,
  useMemo,
  useOptimistic,
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
import {
  aliasedNameOf,
  chosenNameOf,
  displayNameOf,
  keepLatest,
  labelsOf,
  latestEvent,
  latestRow,
  lengthOf,
  nameFromEvent,
  nameOf,
  namesOf,
  pickFirst,
} from './companyNameKit'
import { shortNameOf } from './companyNameKit2'
import { rawKey, rowLine as RowLine, rowName, Rows, shownLine as ShownLine } from './companyNameRendered/rows'

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
// hands back, and React's state to where it gives the name back, a setter or a dispatcher followed as a value.

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

/** N112's component, handed a state's setter under a type of its own. */
function N112Pick({ ev, onPick }: { ev: CalendarEvent; onPick: (name: string) => void }) {
  return (
    <button type="button" onClick={() => onPick(ev.company_name)}>
      Pick
    </button>
  )
}

/** N112 flag: a state's setter handed on to a same-file component, and called there. */
export function N112({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useState('')
  return (
    <>
      <N112Pick ev={ev} onPick={setName} />
      <span>{name}</span>
    </>
  )
}

/** N117 flag: a state's pair kept whole, its setter read by index and handed a served name. */
export function N117({ ev }: { ev: CalendarEvent }) {
  const name = useState('')
  return (
    <button type="button" onClick={() => name[1](ev.company_name)}>
      {name[0]}
    </button>
  )
}

/** N118 flag: a reducer's pair kept whole, its dispatcher read by index and handed a served name. */
export function N118({ ev }: { ev: CalendarEvent }) {
  const name = useReducer((_current: string, next: string) => next, '')
  return (
    <button type="button" onClick={() => name[1](ev.company_name)}>
      {name[0]}
    </button>
  )
}

/** N119 flag: a state's setter held by another name. */
export function N119({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useState('')
  const pick = setName
  return (
    <button type="button" onClick={() => pick(ev.company_name)}>
      {name}
    </button>
  )
}

/** N120 flag: a state's setter put in an object and called through it. */
export function N120({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useState('')
  const actions = { setName }
  return (
    <button type="button" onClick={() => actions.setName(ev.company_name)}>
      {name}
    </button>
  )
}

/** N121's hook, which hands back a state's pair. */
function useN121Name() {
  return useState('')
}

/** N121 flag: a custom hook's setter handed a served name, and its state printed. */
export function N121({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useN121Name()
  return (
    <button type="button" onClick={() => setName(ev.company_name)}>
      {name}
    </button>
  )
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

/** N123 clean: a served name handed to one state's setter, and another state printed. */
export function N123({ ev }: { ev: CalendarEvent }) {
  const [query] = useState('')
  const [, setPicked] = useState('')
  return (
    <button type="button" onClick={() => setPicked(ev.company_name)}>
      {query}
    </button>
  )
}

/** N124 flag: another module's reducer, which gives back the action it is dispatched (a served name). */
export function N124({ ev }: { ev: CalendarEvent }) {
  const [name, dispatch] = useReducer(keepLatest, '')
  return (
    <button type="button" onClick={() => dispatch(ev.company_name)}>
      {name}
    </button>
  )
}

/** N125 flag: another module's reducer, which hands back the served name of the event it is dispatched. */
export function N125({ ev }: { ev: CalendarEvent }) {
  const [name, dispatch] = useReducer(nameFromEvent, '')
  return (
    <button type="button" onClick={() => dispatch(ev)}>
      {name}
    </button>
  )
}

/** N126 flag: another module's helper that hands back a served name, handed to an array's map. */
export function N126({ events }: { events: CalendarEvent[] }) {
  return <span>{events.map(nameOf).join(', ')}</span>
}

/** N127's helper, which calls the function it is handed. */
function N127Apply(read: (ev: CalendarEvent) => string, ev: CalendarEvent): string {
  return read(ev)
}

/** N127 flag: another module's helper that hands back a served name, handed to a same-file function that calls it. */
export function N127({ ev }: { ev: CalendarEvent }) {
  return <span>{N127Apply(nameOf, ev)}</span>
}

/** N128 clean: another module's reducer dispatched the display form, and another module's display-form helper handed
    to an array's map. */
export function N128({ ev, events }: { ev: CalendarEvent; events: CalendarEvent[] }) {
  const [name, dispatch] = useReducer(keepLatest, '')
  return (
    <button type="button" onClick={() => dispatch(formatCompanyName(ev.company_name))}>
      {name} · {events.map(displayNameOf).join(', ')}
    </button>
  )
}

/** N129 flag: another module's overloaded helper, exported through a const alias, which hands back a served name. */
export function N129({ ev }: { ev: CalendarEvent }) {
  return <span>{aliasedNameOf(ev)}</span>
}

/** N130 flag: another module's helper chosen by a conditional, one arm of which hands back a served name. */
export function N130({ ev }: { ev: CalendarEvent }) {
  return <span>{chosenNameOf(ev)}</span>
}

/** N131 flag: a state's setter called through Function.prototype's call. */
export function N131({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useState('')
  return (
    <button type="button" onClick={() => setName.call(null, ev.company_name)}>
      {name}
    </button>
  )
}

/** N132 flag: a state's setter bound to a served name, the bound setter the click's handler. */
export function N132({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useState('')
  return (
    <button type="button" onClick={setName.bind(null, ev.company_name)}>
      {name}
    </button>
  )
}

/** N133 flag: a reducer's dispatcher called through Function.prototype's apply. */
export function N133({ ev }: { ev: CalendarEvent }) {
  const [name, dispatch] = useReducer((_current: string, next: string) => next, '')
  return (
    <button type="button" onClick={() => dispatch.apply(null, [ev.company_name])}>
      {name}
    </button>
  )
}

/** N134's helper, which prints the name it is handed. */
function N134Line(name: string) {
  return <span>{name}</span>
}

/** N134 flag: a same-file function called through Function.prototype's call. */
export function N134({ ev }: { ev: CalendarEvent }) {
  return N134Line.call(null, ev.company_name)
}

/** N135 flag: another module's helper that hands back a served name, called through Function.prototype's call. */
export function N135({ ev }: { ev: CalendarEvent }) {
  return <span>{nameOf.call(null, ev)}</span>
}

/** N136's helper, which prints its second argument alone. */
function N136Label(_prefix: string, name: string) {
  return <span>{name}</span>
}

/** N136 flag: a same-file function bound with one argument, so a later call's argument lands on the parameter after it. */
export function N136({ ev }: { ev: CalendarEvent }) {
  const label = N136Label.bind(null, 'Company: ')
  return label(ev.company_name)
}

/** N137 clean: a setter called through call, and another bound, each handed the display form. */
export function N137({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useState('')
  const [title, setTitle] = useState('')
  return (
    <button type="button" onClick={setTitle.bind(null, formatCompanyName(ev.company_name))} onFocus={() => setName.call(null, formatCompanyName(ev.company_name))}>
      {name} · {title}
    </button>
  )
}

/** N138 flag: a state's setter called through Reflect.apply. */
export function N138({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useState('')
  return (
    <button type="button" onClick={() => Reflect.apply(setName, null, [ev.company_name])}>
      {name}
    </button>
  )
}

/** N142 flag: a served name an object literal's getter hands back, read as the getter's property. */
export function N142({ ev }: { ev: CalendarEvent }) {
  const row = {
    get label() {
      return ev.company_name
    },
  }
  return <span>{row.label}</span>
}

/** N143 flag: an object literal's getter that hands back a served name, held under a declared type, so the checker
    places the read on the type's property and the value holds the name. */
export function N143({ ev }: { ev: CalendarEvent }) {
  const row: { label: string } = {
    get label() {
      return ev.company_name
    },
  }
  return <span>{row.label}</span>
}

/** N144 flag: a getter that hands back a served name its object holds under another key, read through `this`. */
export function N144({ ev }: { ev: CalendarEvent }) {
  const row = {
    raw: ev.company_name,
    get label() {
      return this.raw
    },
  }
  return <span>{row.label}</span>
}

/** N145 flag: a method that puts a served name on its object through `this`, read back by a getter. */
export function N145({ ev }: { ev: CalendarEvent }) {
  const row = {
    raw: '',
    keep(name: string) {
      this.raw = name
    },
    get label() {
      return this.raw
    },
  }
  row.keep(ev.company_name)
  return <span>{row.label}</span>
}

/** N146 flag: a property Object.defineProperty defines with a getter that hands back a served name. */
export function N146({ ev }: { ev: CalendarEvent }) {
  const row: { label?: string } = {}
  Object.defineProperty(row, 'label', { get: () => ev.company_name })
  return <span>{row.label}</span>
}

/** N147 flag: a property Object.defineProperties defines with a getter, written as a method, that hands back a served
    name. */
export function N147({ ev }: { ev: CalendarEvent }) {
  const row: { label?: string } = {}
  Object.defineProperties(row, {
    label: {
      get() {
        return ev.company_name
      },
    },
  })
  return <span>{row.label}</span>
}

/** N148 flag: a property Object.create defines with a value descriptor that holds a served name. */
export function N148({ ev }: { ev: CalendarEvent }) {
  const row: { label: string } = Object.create(null, { label: { value: ev.company_name } })
  return <span>{row.label}</span>
}

/** N149 flag: a property Reflect.defineProperty defines with a value descriptor that holds a served name. */
export function N149({ ev }: { ev: CalendarEvent }) {
  const row: { label?: string } = {}
  Reflect.defineProperty(row, 'label', { value: ev.company_name })
  return <span>{row.label}</span>
}

/** N150 flag: a served name Reflect.set puts on an object, read by name. */
export function N150({ ev }: { ev: CalendarEvent }) {
  const row: { label?: string } = {}
  Reflect.set(row, 'label', ev.company_name)
  return <span>{row.label}</span>
}

/** N151 flag: another module's object's getter that hands back a served name, read as its property. */
export function N151() {
  return <span>{latestEvent.name}</span>
}

/** N152's class, whose getter hands back a served name. */
class N152View {
  ev: CalendarEvent

  constructor(ev: CalendarEvent) {
    this.ev = ev
  }

  get label() {
    return this.ev.company_name
  }
}

/** N152 flag: a class's getter that hands back a served name, read as its property. */
export function N152({ ev }: { ev: CalendarEvent }) {
  return <span>{new N152View(ev).label}</span>
}

/** N153 flag: a field of the app's own filled by a getter that hands back a served name. */
export function N153(filing: Filing): Pick<SourceIdentity, 'companyName'> {
  return {
    get companyName() {
      return filing.company!.name
    },
  }
}

/** N154's class, whose getter hands back the display form. */
class N154View {
  ev: CalendarEvent

  constructor(ev: CalendarEvent) {
    this.ev = ev
  }

  get label() {
    return formatCompanyName(this.ev.company_name)
  }
}

/** N154 clean: a getter, a getter reading through `this`, a property Object.defineProperty defines and a class's
    getter, each handing back the display form beside a served name, and Reflect.get reading the display form. */
export function N154({ ev }: { ev: CalendarEvent }) {
  const row: Record<string, string> = {
    get title() {
      return formatCompanyName(ev.company_name)
    },
  }
  Object.defineProperty(row, 'shown', { get: () => formatCompanyName(ev.company_name) })
  const kept = {
    raw: ev.company_name,
    shown: formatCompanyName(ev.company_name),
    get line() {
      return this.shown
    },
  }
  return (
    <span>
      {row.title} {row.shown} {kept.line} {new N154View(ev).label} {Reflect.get(kept, 'shown')}
    </span>
  )
}

/** N158 flag: a served name a Map is constructed with, read by its key. */
export function N158({ ev }: { ev: CalendarEvent }) {
  const names = new Map([['current', ev.company_name]])
  return <span>{names.get('current')}</span>
}

/** N159 flag: a served name a Set is constructed with, read by spreading the Set. */
export function N159({ ev }: { ev: CalendarEvent }) {
  const names = new Set([ev.company_name])
  return <span>{[...names].join(', ')}</span>
}

/** N160 flag: a served name Object.fromEntries puts under a key, read by that key. */
export function N160({ ev }: { ev: CalendarEvent }) {
  const labels = Object.fromEntries([['label', ev.company_name]])
  return <span>{labels.label}</span>
}

/** N161 flag: a served name a Set's add puts in after the Set is made, read through Array.from. */
export function N161({ ev }: { ev: CalendarEvent }) {
  const names = new Set<string>()
  names.add(ev.company_name)
  return <span>{Array.from(names).join(', ')}</span>
}

/** N162 flag: a served name an Array is constructed with, read by index. */
export function N162({ ev }: { ev: CalendarEvent }) {
  const names = new Array<string>(ev.company_name)
  return <span>{names[0]}</span>
}

/** N163 flag: a served name a WeakMap is constructed with under an object key, read by that key. */
export function N163({ ev }: { ev: CalendarEvent }) {
  const names = new WeakMap([[ev, ev.company_name]])
  return <span>{names.get(ev)}</span>
}

/** N164 flag: a Map constructed from pairs the scan does not see written (Object.entries), read by a key. */
export function N164({ ev }: { ev: CalendarEvent }) {
  const names = new Map(Object.entries({ label: ev.company_name }))
  return <span>{names.get('label')}</span>
}

/** N165 clean: a Map and Object.fromEntries holding a served name under one key and the display form under another,
    read under the display form's key, and a Set of display forms. */
export function N165({ ev }: { ev: CalendarEvent }) {
  const shown = formatCompanyName(ev.company_name)
  const names = new Map([
    ['raw', ev.company_name],
    ['shown', shown],
  ])
  const labels = Object.fromEntries([
    ['raw', ev.company_name],
    ['shown', shown],
  ])
  const display = new Set([shown])
  return (
    <span>
      {names.get('shown')} {labels.shown} {[...display].join(', ')}
    </span>
  )
}

/** N167 clean: React's append idiom, a state's updater spreading the state it is handed, given the display form. */
export function N167({ ev }: { ev: CalendarEvent }) {
  const [names, setNames] = useState<string[]>([])
  return (
    <button type="button" onClick={() => setNames((prev) => [...prev, formatCompanyName(ev.company_name)])}>
      {names.join(', ')}
    </button>
  )
}

/** N168 flag: React's append idiom given a served name. */
export function N168({ ev }: { ev: CalendarEvent }) {
  const [names, setNames] = useState<string[]>([])
  return (
    <button type="button" onClick={() => setNames((prev) => [...prev, ev.company_name])}>
      {names.join(', ')}
    </button>
  )
}

/** N169 flag: an object literal's method that appends a served name to an array it keeps on `this`. */
export function N169({ ev }: { ev: CalendarEvent }) {
  const list = {
    items: [] as string[],
    add(name: string) {
      this.items = [...this.items, name]
    },
  }
  list.add(ev.company_name)
  return <span>{list.items.join(', ')}</span>
}

/** N170 flag: a getter that hands back an object holding its own object by name, a served name read through it. */
export function N170({ ev }: { ev: CalendarEvent }) {
  const row = {
    raw: ev.company_name,
    get parent(): { child: { raw: string } } {
      return { child: row }
    },
  }
  return <span>{row.parent.child.raw}</span>
}

/** N171 flag: a Map's values() iterated, a served name among them. */
export function N171({ ev }: { ev: CalendarEvent }) {
  const names = new Map([['current', ev.company_name]])
  return <span>{[...names.values()].join(', ')}</span>
}

/** N172 flag: a Map's entries() iterated as pairs, a served name the pair's value. */
export function N172({ ev }: { ev: CalendarEvent }) {
  const names = new Map([['current', ev.company_name]])
  return <span>{Array.from(names.entries(), ([, name]) => name).join(', ')}</span>
}

/** N180 flag: React's optimistic state, its setter handed a served name. */
export function N180({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useOptimistic('')
  return (
    <button type="button" onClick={() => setName(ev.company_name)}>
      {name}
    </button>
  )
}

/** N181 flag: React's optimistic state with an update function, which appends each value its setter is handed. */
export function N181({ ev }: { ev: CalendarEvent }) {
  const [names, addName] = useOptimistic<string[], string>([], (current, next) => [...current, next])
  return (
    <button type="button" onClick={() => addName(ev.company_name)}>
      {names.join(', ')}
    </button>
  )
}

/** N182 flag: React's action state, its action handed a served name through its dispatcher and giving it back. */
export function N182({ ev }: { ev: CalendarEvent }) {
  const [name, act] = useActionState((_current: string, next: string) => next, '')
  return (
    <button type="button" onClick={() => act(ev.company_name)}>
      {name}
    </button>
  )
}

/** N183 clean: React's optimistic and action state, each handed the display form. */
export function N183({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useOptimistic('')
  const [title, act] = useActionState((_current: string, next: string) => next, '')
  return (
    <button type="button" onClick={() => setName(formatCompanyName(ev.company_name))} onFocus={() => act(formatCompanyName(ev.company_name))}>
      {name} · {title}
    </button>
  )
}

// A served object handed whole to a type of the app's own, whose fields the gate reads as the display form.

/** N185 flag: a served object assigned whole to a view of the app's own by a declared type (Codex's form). */
export function N185({ ev }: { ev: CalendarEvent }) {
  const view: LineView = ev
  return <span>{view.company_name}</span>
}

/** N186 flag: a served object assigned to a `let` declared as the view. */
export function N186({ events }: { events: CalendarEvent[] }) {
  let view: LineView | undefined
  for (const ev of events) view = ev
  return <span>{view?.company_name}</span>
}

/** N187's helper, whose parameter is the view. */
function N187Text(view: LineView) {
  return view.company_name
}

/** N187 flag: a served object handed to a parameter typed as the view. */
export function N187({ ev }: { ev: CalendarEvent }) {
  return <span>{N187Text(ev)}</span>
}

/** N188's helper, whose return type is the view. */
function N188View(ev: CalendarEvent): LineView {
  return ev
}

/** N188 flag: a served object returned as the view. */
export function N188({ ev }: { ev: CalendarEvent }) {
  return <span>{N188View(ev).company_name}</span>
}

/** N189 flag: a callback that returns a served object as the view, by its declared return type. */
export function N189({ events }: { events: CalendarEvent[] }) {
  return (
    <ul>
      {events
        .map((e): LineView => e)
        .map((view) => (
          <li key={view.ticker}>{view.company_name}</li>
        ))}
    </ul>
  )
}

/** N190's component, whose prop is the view. */
function N190Line({ view }: { view: LineView }) {
  return <p>{view.company_name}</p>
}

/** N190 flag: a served object handed to a component's prop typed as the view. */
export function N190({ ev }: { ev: CalendarEvent }) {
  return <N190Line view={ev} />
}

/** N191 flag: served objects assigned to an array of views, by its elements. */
export function N191({ events }: { events: CalendarEvent[] }) {
  const views: LineView[] = events
  return (
    <ul>
      {views.map((view) => (
        <li key={view.ticker}>{view.company_name}</li>
      ))}
    </ul>
  )
}

/** N192's row, whose member is the view. */
interface N192Row {
  view: LineView
}

/** N192 flag: a served object as an object literal's member, placed by a type whose member is the view. */
export function N192({ ev }: { ev: CalendarEvent }) {
  const row: N192Row = { view: ev }
  return <span>{row.view.company_name}</span>
}

/** N193 flag: a served object asserted to be the view. */
export function N193({ ev }: { ev: CalendarEvent }) {
  const view = ev as LineView
  return <span>{view.company_name}</span>
}

/** N194 flag: a served object as the default of a destructured prop typed as the view. */
export function N194({ ev, view = ev }: { ev: CalendarEvent; view?: LineView }) {
  return <span>{view.company_name}</span>
}

/** N195 flag: a served object put in React state typed as the view, through its setter. */
export function N195({ ev }: { ev: CalendarEvent }) {
  const [view, setView] = useState<LineView | null>(null)
  return (
    <button type="button" onClick={() => setView(ev)}>
      {view?.company_name}
    </button>
  )
}

/** N196's helper, a generic whose parameter is constrained to the view. */
function N196Text<T extends LineView>(view: T) {
  return view.company_name
}

/** N196 flag: a served object handed to a generic constrained to the view, which infers the served type for the call. */
export function N196({ ev }: { ev: CalendarEvent }) {
  return <span>{N196Text(ev)}</span>
}

/** N197 flag: a map of served objects assigned to a map of views, by its type arguments. */
export function N197({ byTicker }: { byTicker: Map<string, CalendarEvent> }) {
  const views: ReadonlyMap<string, LineView> = byTicker
  return <span>{views.get('AAPL')?.company_name}</span>
}

/** N198's helper, which hands back the served object. */
function N198Raw(ev: CalendarEvent) {
  return ev
}

/** N198 flag: a function that hands back a served object assigned to a function typed to return the view. */
export function N198({ ev }: { ev: CalendarEvent }) {
  const viewOf: (e: CalendarEvent) => LineView = N198Raw
  return <span>{viewOf(ev).company_name}</span>
}

/** N199 flag: a served object in props spread into a component, under the prop typed as the view. */
export function N199({ ev }: { ev: CalendarEvent }) {
  const props = { view: ev }
  return <N190Line {...props} />
}

/** N200 flag: a served object spread into an object literal under a member typed as the view. */
export function N200({ ev }: { ev: CalendarEvent }) {
  const wrapped = { view: ev }
  const row: N192Row = { ...wrapped }
  return <span>{row.view.company_name}</span>
}

/** N201 flag: served objects spread into an array of views. */
export function N201({ events }: { events: CalendarEvent[] }) {
  const views: LineView[] = [...events]
  return (
    <ul>
      {views.map((view) => (
        <li key={view.ticker}>{view.company_name}</li>
      ))}
    </ul>
  )
}

/** N202's generator, typed to yield the view. */
function* N202Views(events: CalendarEvent[]): Generator<LineView> {
  for (const ev of events) yield ev
}

/** N202 flag: served objects yielded by a generator typed to yield the view. */
export function N202({ events }: { events: CalendarEvent[] }) {
  return (
    <ul>
      {[...N202Views(events)].map((view) => (
        <li key={view.ticker}>{view.company_name}</li>
      ))}
    </ul>
  )
}

/** N203 flag: a served object in a class component's field typed as the view. */
export class N203 extends Component<{ ev: CalendarEvent }> {
  view: LineView = this.props.ev

  render() {
    return <span>{this.view.company_name}</span>
  }
}

/** N204 flag: a served object's members copied onto the view by Object.assign. */
export function N204({ ev }: { ev: CalendarEvent }) {
  const view: LineView = { ticker: '', company_name: '' }
  Object.assign(view, ev)
  return <span>{view.company_name}</span>
}

/** N210 flag: a record of served objects assigned to a record of views, by its index signature. */
export function N210({ byTicker }: { byTicker: Record<string, CalendarEvent> }) {
  const views: Record<string, LineView> = byTicker
  return <span>{views.AAPL?.company_name}</span>
}

/** N211's helper, whose rest parameter takes views. */
function N211Texts(...views: LineView[]) {
  return views.map((view) => view.company_name).join(', ')
}

/** N211 flag: served objects spread into a rest parameter of views. */
export function N211({ events }: { events: CalendarEvent[] }) {
  return <span>{N211Texts(...events)}</span>
}

/** N205 clean: the view built from a served object's spread, its name formatted over the spread. */
export function N205({ ev }: { ev: CalendarEvent }) {
  const view: LineView = { ...ev, company_name: formatCompanyName(ev.company_name) }
  return <span>{view.company_name}</span>
}

/** N206's mapper, which builds the view with the display form. */
function N206View(ev: CalendarEvent): LineView {
  return { ticker: ev.ticker, company_name: formatCompanyName(ev.company_name) }
}

/** N206 clean: a view the app's own mapper builds, handed whole to places typed as the view. */
export function N206({ ev }: { ev: CalendarEvent }) {
  const view: LineView = N206View(ev)
  const views: LineView[] = [view]
  return (
    <>
      <N190Line view={view} />
      <span>{views.map((v) => v.ticker).join(', ')}</span>
    </>
  )
}

/** N207's helper, a generic with no constraint. */
function N207Keep<T>(value: T): T {
  return value
}

/** N207 clean: a served object kept under its own type, through a generic with no constraint, formatted where it
    prints. */
export function N207({ ev }: { ev: CalendarEvent }) {
  const raw: CalendarEvent = N207Keep(ev)
  return <span>{formatCompanyName(raw.company_name)}</span>
}

// Components another module renders, and functions handed to one: their forms in tests/unit/fixtures/companyNameRendered/.

/** N218's render site: another module's component of a lowercase name, rendered under an alias. */
export function N218Use({ ev }: { ev: CalendarEvent }) {
  return <RowLine ev={ev} />
}

/** N219's render site: another module's component held as an object's member. */
export function N219Use({ ev }: { ev: CalendarEvent }) {
  return <Rows.line ev={ev} />
}

/** N220 flag: another module's function that hands back a served name, handed to a DataTable column's render, which
    prints what it returns. */
export function N220({ events }: { events: CalendarEvent[] }) {
  return <DataTable rows={events} rowKey={(ev) => ev.ticker} columns={[{ key: 'name', header: 'Company', render: rowName }]} />
}

/** N222's render site: another module's component that returns the display form. */
export function N222Use({ ev }: { ev: CalendarEvent }) {
  return <ShownLine ev={ev} />
}

/** N223's call site: another module's helper that hands back a served name, called for a key. */
export function N223Use({ events }: { events: CalendarEvent[] }) {
  return (
    <ul>
      {events.map((ev) => (
        <li key={rawKey(ev)}>{ev.ticker}</li>
      ))}
    </ul>
  )
}

/** N224's component, another module's loaded lazily through a promise's then. */
const N224Line = lazy(() => import('./companyNameRendered/rows').then((m) => ({ default: m.lazyLine })))

/** N224's render site. */
export function N224Use({ ev }: { ev: CalendarEvent }) {
  return <N224Line ev={ev} />
}

// Components that return an iterable, and classes whose constructor declares a company-name field.

/** N225 flag: a component that returns an array holding a served name, whose items React renders as text. */
export function N225({ ev }: { ev: CalendarEvent }) {
  return [ev.company_name]
}

/** N226 flag: a component that returns a Set holding a served name, an iterable React renders. */
export function N226({ ev }: { ev: CalendarEvent }) {
  return new Set([ev.company_name])
}

/** N227 flag: a component that returns arrays nested in an array, a served name among their items. */
export function N227({ ev }: { ev: CalendarEvent }) {
  return [[ev.ticker, ev.company_name]]
}

/** N228 flag: a component that returns the array an array's map builds from served names. */
export function N228({ events }: { events: CalendarEvent[] }) {
  return events.map((e) => e.company_name)
}

/** N229 flag: another module's function that hands back an array holding a served name, rendered as a child. */
export function N229({ ev }: { ev: CalendarEvent }) {
  return <span>{namesOf(ev)}</span>
}

/** N230 clean: a component that returns an array of the display form and a ticker. */
export function N230({ ev }: { ev: CalendarEvent }) {
  return [formatCompanyName(ev.company_name), ev.ticker]
}

/** N232's class of the app's own, whose constructor's parameter property is a company-name field. */
class N232View {
  constructor(public company_name: string) {}
}

/** N232 flag: a served name handed to a constructor's parameter property, a field of the app's own, then printed. */
export function N232({ ev }: { ev: CalendarEvent }) {
  const view = new N232View(ev.company_name)
  return <span>{view.company_name}</span>
}

/** N233's base class, whose constructor's parameter property is a company-name field. */
class N233Base {
  constructor(readonly companyName: string) {}
}

/** N233's view, which fills its base's parameter property through super. */
class N233View extends N233Base {
  constructor(ev: CalendarEvent) {
    super(ev.company_name)
  }
}

/** N233 flag: a served name a subclass hands its base's parameter property through super. */
export function N233({ ev }: { ev: CalendarEvent }) {
  return <span>{new N233View(ev).companyName}</span>
}

/** N234 flag: a served object assigned whole to a class of the app's own whose parameter property is a company-name
    field. */
export function N234({ ev }: { ev: CalendarEvent }) {
  const view: N232View = ev
  return <span>{view.company_name}</span>
}

/** N235 clean: the display form handed to a constructor's parameter property. */
export function N235({ ev }: { ev: CalendarEvent }) {
  const view = new N232View(formatCompanyName(ev.company_name))
  return <span>{view.company_name}</span>
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

/** N122 gap: a state's setter handed to another module's function, and called there. */
export function N122({ events }: { events: CalendarEvent[] }) {
  const [name, setName] = useState('')
  return (
    <button type="button" onClick={() => pickFirst(events, setName)}>
      {name}
    </button>
  )
}

/** N139 gap: a utility known by its name, an array's map, called through Function.prototype's call. */
export function N139({ events }: { events: CalendarEvent[] }) {
  return <span>{Array.prototype.map.call(events, (e: CalendarEvent) => e.company_name).join(', ')}</span>
}

/** N140 gap: a served name copied into a class component's field, printed through `this`. */
export class N140 extends Component<{ ev: CalendarEvent }> {
  label = this.props.ev.company_name

  render() {
    return <span>{this.label}</span>
  }
}

/** N141 gap: a served name put in a class component's state, printed through `this`. */
export class N141 extends Component<{ ev: CalendarEvent }, { label: string }> {
  state = { label: '' }

  render() {
    return (
      <button type="button" onClick={() => this.setState({ label: this.props.ev.company_name })}>
        {this.state.label}
      </button>
    )
  }
}

/** N155 gap: a served name an assignment hands an object literal's setter, which keeps it through `this` for a getter
    of another name. */
export function N155({ ev }: { ev: CalendarEvent }) {
  const row = {
    raw: '',
    set label(name: string) {
      this.raw = name
    },
    get shown() {
      return this.raw
    },
  }
  row.label = ev.company_name
  return <span>{row.shown}</span>
}

/** N156 gap: a served name a Proxy's get trap hands back. */
export function N156({ ev }: { ev: CalendarEvent }) {
  const row = new Proxy<Record<string, string>>({}, { get: () => ev.company_name })
  return <span>{row.label}</span>
}

/** N157's object type, whose getter hands back the object itself. */
interface N157Row {
  raw: string
  readonly self: N157Row
}

/** N157 gap: an object literal's `this` handed on whole, by a getter that hands back its own object. */
export function N157({ ev }: { ev: CalendarEvent }) {
  const row: N157Row = {
    raw: ev.company_name,
    get self() {
      return this
    },
  }
  return <span>{row.self.raw}</span>
}

/** N166 gap: a Map's entries iterated as `[key, value]` pairs, a served name the pair's value. */
export function N166({ ev }: { ev: CalendarEvent }) {
  const names = new Map([['current', ev.company_name]])
  return (
    <ul>
      {Array.from(names, ([key, name]) => (
        <li key={key}>{name}</li>
      ))}
    </ul>
  )
}

/** N173 gap: a served name a promise's `then` hands a state's setter. */
export function N173({ ev }: { ev: CalendarEvent }) {
  const [name, setName] = useState('')
  return (
    <button type="button" onClick={() => Promise.resolve(ev.company_name).then(setName)}>
      {name}
    </button>
  )
}

/** N174's generator, which yields a served name. */
function* N174Names(ev: CalendarEvent) {
  yield ev.company_name
}

/** N174 gap: a served name a generator yields, read by spreading what it gives. */
export function N174({ ev }: { ev: CalendarEvent }) {
  return <span>{[...N174Names(ev)].join(', ')}</span>
}

/** N175 gap: another module's getter that hands back a served name, read through a type that declares the property. */
export function N175() {
  return <span>{latestRow.name}</span>
}

/** N176 gap: a property descriptor's getter that reads `this`, which the reading binds to the descriptor. */
export function N176({ ev }: { ev: CalendarEvent }) {
  const row: { raw: string; label?: string } = { raw: ev.company_name }
  Object.defineProperty(row, 'label', {
    get() {
      return this.raw
    },
  })
  return <span>{row.label}</span>
}

/** N177 gap: a served name a Map holds as a key, read through keys(). */
export function N177({ ev }: { ev: CalendarEvent }) {
  const counts = new Map([[ev.company_name, 1]])
  return <span>{[...counts.keys()].join(', ')}</span>
}

/** N178 gap: a served name read from a value typed `any`, which declares no field for it. */
export function N178({ row }: { row: any }) {
  return <span>{row.company_name}</span>
}

/** N184's child, which hands its parent's ref an object holding a served name. */
const N184Child = forwardRef<{ label: string }, { ev: CalendarEvent }>(function N184Child({ ev }, ref) {
  useImperativeHandle(ref, () => ({ label: ev.company_name }))
  return null
})

/** N184 gap: a served name a child hands its parent's ref through useImperativeHandle, which the parent reads in a
    handler and keeps in state. */
export function N184({ ev }: { ev: CalendarEvent }) {
  const ref = useRef<{ label: string }>(null)
  const [name, setName] = useState('')
  return (
    <>
      <N184Child ev={ev} ref={ref} />
      <button type="button" onClick={() => setName(ref.current?.label ?? '')}>
        {name}
      </button>
    </>
  )
}

/** N179 gap: a reducer's dispatcher handed to another module's function, and called there. */
export function N179({ events }: { events: CalendarEvent[] }) {
  const [name, dispatch] = useReducer(keepLatest, '')
  return (
    <button type="button" onClick={() => pickFirst(events, dispatch)}>
      {name}
    </button>
  )
}

/** N113 gap: a name inside an object another module's function hands back. */
export function N113({ ev }: { ev: CalendarEvent }) {
  return <span>{labelsOf(ev).title}</span>
}

/** N208 gap: a served object cast to the view through `unknown`, which declares no field. */
export function N208({ ev }: { ev: CalendarEvent }) {
  const view = ev as unknown as LineView
  return <span>{view.company_name}</span>
}

/** N209 gap: a served object's copy through JSON, which the checker types `any`, assigned to the view. */
export function N209({ ev }: { ev: CalendarEvent }) {
  const view: LineView = JSON.parse(JSON.stringify(ev))
  return <span>{view.company_name}</span>
}

/** N231 gap: a component that returns a Map, which React renders as [key, value] pairs, a served name a value. */
export function N231({ ev }: { ev: CalendarEvent }) {
  return new Map([['name', ev.company_name]])
}
