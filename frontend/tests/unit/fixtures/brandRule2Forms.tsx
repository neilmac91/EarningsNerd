/**
 * Planted forms for brandCopyRules.spec.ts rule 2 (sage never colours a number, D-030): one component per
 * form, each marked by its trailing comment. `flag` breaks the rule, so rule 2 must name its line; `clean`
 * is a look-alike that must pass; `gap` is a form the rule forbids and the gate leaves to review (its
 * header names it), so it must pass too, until the gate reaches it and the mark flips. The spec reads this
 * file in the same program as the app and scores every form on every run, so a change to the gate that
 * loses a form, or catches a look-alike, fails there. Outside the scan roots: rule 2's app scan never
 * reads it. A new form the rule can take joins it with its mark.
 */
import { Children, type ReactNode } from 'react'
import { Badge, Button, buttonVariants, type BadgeVariant } from '@/components/ui'
import { cx } from '@/components/ui/cx'
import Link from 'next/link'
import { ArrowRightIcon } from '@/lib/icons'

const SAGE_LINK = 'text-brand-strong hover:underline'
export function P01({ n }: { n: number }) { return <a className={SAGE_LINK}>{n}</a> } // flag
export function P02({ n }: { n: number }) { return <span className="text-brand-strong/80">{n}</span> } // flag
export function P03({ n, on }: { n: number; on: boolean }) { return <button aria-pressed={on} className="text-text-secondary-light aria-pressed:text-brand-strong">{n}</button> } // flag
export function P04({ n }: { n: number }) { return <a aria-current="page" className="text-text-secondary-light aria-[current=page]:text-brand-strong">{n}</a> } // flag
export function P05({ n }: { n: number }) { return <button data-state="active" className="text-text-secondary-light data-[state=active]:text-brand-strong">{n}</button> } // flag
export function P06({ rows }: { rows: { v: number }[] }) { return <ul className="text-brand-strong">{rows.map((r) => { return <li key={r.v}>{r.v}</li> })}</ul> } // flag
function Count({ n }: { n: number }) { return <>{n}</> }
export function P07({ n }: { n: number }) { return <span className="text-brand-strong"><Count n={n} /></span> } // flag
function SageText({ children }: { children: ReactNode }) { return <span className="text-brand-strong">{children}</span> }
export function P08({ n }: { n: number }) { return <SageText>{n}</SageText> } // flag
export function P09({ n }: { n: number }) { return <Button variant="secondary">Load {n} more</Button> } // flag
export function P10({ n }: { n: number }) { return <Badge variant="brand">{n}</Badge> } // flag
export function P11() { return <a className="text-brand-strong">Open the 10-K</a> } // clean
const labelFor = (i: number) => ['Revenue', 'Margin'][i]
export function P12({ i }: { i: number }) { return <span className="text-brand-strong">{labelFor(i)}</span> } // flag
export function P13({ count }: { count: number }) { return <span className="text-brand-strong">[{count}]</span> } // clean
export function P14({ n }: { n: number }) { return <span className="text-brand-strong">{n}</span> } // flag
export function P15({ n }: { n: number }) { return <span className="text-brand-strong">{n.toFixed(1)}%</span> } // flag
export function P16({ d }: { d: Date }) { return <span className="text-brand-strong">{d.toLocaleDateString()}</span> } // gap
export function P17({ n }: { n: number }) { return <span className={cx('font-semibold', 'text-brand-strong')}>{n}</span> } // flag
export function P18({ n, a }: { n: number; a: boolean }) { return <span className={a ? 'text-brand-strong' : 'text-text-secondary-light'}>{n}</span> } // flag
export function P19({ n }: { n: number }) { return <span className="text-brand-strong">{n > 0 ? `${n} new` : 'None'}</span> } // flag
export function P20({ items }: { items: string[] }) { return <span className="text-brand-strong">{items.length}</span> } // flag
export function P21({ n }: { n: number }) { return <span className="text-brand-strong">{String(n)}</span> } // flag
export function P22({ n }: { n: number }) { return <span className="text-brand-strong">Step {n + 1}</span> } // flag
export function P23({ n }: { n: number }) { return <span className="dark:text-brand-strong-dark text-text-secondary-light">{n}</span> } // flag
export function P24({ n }: { n: number }) { return <span className="!text-brand-strong">{n}</span> } // flag
export function P25({ n }: { n: number }) { return <svg><text className="fill-brand-strong">{n}</text></svg> } // flag
export function P26({ n }: { n: number }) { return <span className="text-brand-strong">{n}<sup>†</sup></span> } // flag
export function P27({ n }: { n: number }) { const label = `${n} filings`; return <span className="text-brand-strong">{label}</span> } // flag
export function P28({ y }: { y: string }) { return <span className="text-brand-strong">FY{y}</span> } // clean
export function P29({ rows }: { rows: string[] }) { return <ul className="text-brand-strong">{rows.map((r) => <li key={r}>Step 1</li>)}</ul> } // flag
export function P30({ rows }: { rows: { n: number }[] }) { return <p className="text-brand-strong">{rows.map((r) => { return r.n })}</p> } // flag
function Outer({ children }: { children: ReactNode }) { return <SageText>{children}</SageText> }
export function P31({ n }: { n: number }) { return <Outer>{n}</Outer> } // flag
export function P32({ n }: { n: number }) { return <p className="text-brand-strong">Upgrade <Button>Get {n} more</Button></p> } // clean
export function P33({ n }: { n: number }) { return <p className="text-brand-strong">New <Badge>{n}</Badge></p> } // clean
export function P34() { return <a className="text-brand-strong">Open the 10-K for FY2025</a> } // flag
export function P35({ n }: { n: number }) { return <span className="text-text-secondary-light group-hover:text-brand-strong">{n}</span> } // clean
export function P36({ n }: { n: number }) { return <span className="text-text-secondary-light focus-visible:text-brand-strong">{n}</span> } // flag
export function P37({ n }: { n: number }) { return <button className="text-text-secondary-light disabled:text-brand-strong">{n}</button> } // flag
export function P38({ n }: { n: number }) { return <span className="text-text-secondary-light [&:hover]:text-brand-strong">{n}</span> } // clean
export function P39({ n }: { n: number }) { return <SageText><span className="text-text-secondary-light">{n}</span></SageText> } // clean
function Quiet({ n }: { n: number }) { return <span className="text-text-secondary-light">{n}</span> }
export function P40({ n }: { n: number }) { return <span className="text-brand-strong"><Quiet n={n} /></span> } // clean
export function P41({ n }: { n: number }) { return <a className={buttonVariants({ variant: 'ghost' })}>See {n}</a> } // flag
export function P42({ n, hot }: { n: number; hot: boolean }) { return <Badge variant={hot ? 'brand' : 'neutral'}>{n}</Badge> } // flag
export function P43({ n }: { n: number }) { return <Badge variant="pro">{n} seats</Badge> } // flag
export function P44({ n }: { n: number }) { return <Badge variant="solid">{n}</Badge> } // clean
export function P45({ n }: { n: number }) { return <span className="text-brand-strong"><a href="https://example.com">{n}</a></span> } // flag
export function P46({ url }: { url: string }) { return <a className="text-brand-strong" href={url}>{url}</a> } // clean
export function P47({ n }: { n: number }) { return <span className="text-text-secondary-light hover:text-brand-strong">{n}</span> } // clean
function Cite({ n }: { n: number }) { return <>{`[${n}]`}</> }
export function P48({ n }: { n: number }) { return <span className="text-brand-strong"><Cite n={n} /></span> } // clean
export function P49({ count }: { count: number }) { return <p className="text-brand-strong">{count && <b>new</b>}</p> } // flag
export function P50({ n }: { n: number }) { return <span className="text-brand-strong"><SageText>{'Total'}</SageText> {n > 1 ? 'many' : 'one'}</span> } // clean

// The review of 88f801c: a component given sage at its call site that renders a number prop (3).
function Tally({ n, className }: { n: number; className?: string }) { return <span className={className}>{n}</span> }
export function P51({ n }: { n: number }) { return <Tally className="text-brand-strong" n={n} /> } // flag
export function P52({ n }: { n: number }) { return <Tally className="text-brand-strong" n={n}></Tally> } // flag
function QuietTally({ n, className }: { n: number; className?: string }) { return <span className={className}>Total <b className="text-text-primary-light">{n}</b></span> }
export function P53({ n }: { n: number }) { return <QuietTally className="text-brand-strong" n={n} /> } // clean
// A comparison renders a boolean, never a number (4).
export function P54({ items }: { items: string[] }) { return <Link className="text-brand-strong" href="/x">View{items.length > 0 && <ArrowRightIcon className="h-4 w-4" />}</Link> } // clean
export function P55({ count }: { count: number }) { return <p className="text-brand-strong">{count > 0 && 'New'}</p> } // clean
export function P56({ count }: { count: number }) { return <p className="text-brand-strong">{count === 1 ? 'one' : 'many'}</p> } // clean
export function P57({ count }: { count: number }) { return <p className="text-brand-strong">{count || 'none'}</p> } // flag
export function P58({ n }: { n: number }) { return <p className="text-brand-strong">{n > 0 && <span>{n} new</span>}</p> } // flag
// A component whose children path the walk cannot trace is transparent (5).
function Field({ children: content }: { children: ReactNode }) { return <div>{content}</div> }
export function P59({ n }: { n: number }) { return <p className="text-brand-strong"><Field>{n}</Field></p> } // flag
// A size or an inherited colour is not an ink (6).
export function P60({ n }: { n: number }) { return <a className="text-brand-strong"><span className="text-[10px]">{n}</span></a> } // flag
export function P61({ n }: { n: number }) { return <p className="text-brand-strong"><span className="text-inherit">{n}</span></p> } // flag
export function P62({ n }: { n: number }) { return <p className="text-brand-strong"><span className="text-current">{n}</span></p> } // flag
// A link can rest visited, and an element can rest as the fragment's target (7).
export function P63({ n }: { n: number }) { return <a href="/x" className="text-text-secondary-light visited:text-brand-strong">{n}</a> } // flag
export function P64({ n }: { n: number }) { return <section id="x" className="text-text-secondary-light target:text-brand-strong">{n}</section> } // flag
// A sage control never holds its count in an ink of its own (the count control, 2).
export function P65({ n }: { n: number }) { return <Link className="text-brand-strong" href="/x">See all <span className="text-text-secondary-light">{n}</span> companies</Link> } // flag
export function P66({ n }: { n: number }) { return <Button variant="secondary">See <span className="text-text-secondary-light">{n}</span></Button> } // flag
export function P67({ n }: { n: number }) { return <button className="text-brand-strong">Resend <span className="text-text-secondary-light">in {n}s</span></button> } // flag
export function P68() { return <button className="text-brand-strong">Retry <span className="text-text-secondary-light">now</span></button> } // clean
export function P69({ i }: { i: number }) { return <a href="#s" className="text-text-secondary-light hover:text-brand-strong"><span className="text-text-tertiary-light">{String(i + 1).padStart(2, '0')}</span> Overview</a> } // clean
export function P70({ n }: { n: number }) { return <p className="text-brand-strong">Step <span className="text-text-primary-light">{n}</span></p> } // clean
// A plural or possessive form code is a name too ("Compare 10-Ks").
export function P71() { return <a className="text-brand-strong">Compare 10-Ks and 10-Qs</a> } // clean
// The count control's label held in a const, as cc2df56 held the feed's (2).
export function P72({ n }: { n: number }) { const seeAll = <span>See all <span className="text-text-secondary-light">{n}</span> companies</span>; return <Link className="text-brand-strong" href="/x">{seeAll}</Link> } // flag
// A const another function declares under the same name is not this one's (localInitializer, via the checker).
export function P73({ n }: { n: number }) { const caption = `${n} filings`; return <span className="text-text-secondary-light">{caption}</span> } // clean
export function P74() { const caption = 'Coverage'; return <span className="text-brand-strong">{caption}</span> } // clean
// The review of 97aa784: a chained &&, a size with a line-height, other operators, an unreadable variant, the
// call-site check, a prop that is not the label, children handed to a callback, and the forms it named as gaps.
// A chained && whose first operand is a number renders a 0.
export function P75({ n, on }: { n: number; on: boolean }) { return <p className="text-brand-strong">{n && on && <b>new</b>}</p> } // flag
export function P76({ n, on }: { n: number; on: boolean }) { return <p className="text-brand-strong">{n && on && 'New'}</p> } // flag
export function P77({ n, on }: { n: number; on: boolean }) { return <p className="text-brand-strong">{on && n && <b>new</b>}</p> } // flag
// A predicate fed a number on the left of && renders nothing.
const isVisible = (k: number) => k > 2
export function P78({ n }: { n: number }) { return <p className="text-brand-strong">{isVisible(n) && 'New'}</p> } // clean
// A theme size with a line-height modifier is a size, not an ink.
export function P79({ n }: { n: number }) { return <a className="text-brand-strong"><span className="text-sm/6">{n}</span></a> } // flag
export function P80({ n }: { n: number }) { return <a className="text-brand-strong"><span className="text-xs/[1.1]">{n}</span></a> } // flag
// The other operators, and a bigint.
export function P81({ a }: { a: string | null }) { return <p className="text-brand-strong">{a ?? 0}</p> } // flag
export function P82({ x }: { x: string }) { return <p className="text-brand-strong">{x || 0}</p> } // flag
export function P83({ n }: { n: number }) { return <p className="text-brand-strong">{n && n}</p> } // flag
export function P84({ n }: { n: number }) { return <p className="text-brand-strong">{n - 1 > 0 && 'More'}</p> } // clean
export function P85({ n }: { n: number }) { return <p className="text-brand-strong">{n > 0 && n}</p> } // flag
export function P86({ b }: { b: bigint }) { return <p className="text-brand-strong">{b}</p> } // flag
// An unreadable variant beside a literal one.
export function P87({ n, v }: { n: number; v?: BadgeVariant }) { return <Badge variant={v ?? 'neutral'}>{n}</Badge> } // flag
// Sage given where a component is used that puts the className beside its number, not around it.
function Stat({ label, value, className }: { label: string; value: number; className?: string }) { return <div><span className={className}>{label}</span> <b>{value}</b></div> }
export function P88({ n }: { n: number }) { return <Stat className="text-brand-strong" label="Total" value={n} /> } // clean
// A component with its own ink that the call site's className joins (cx joins and does not merge, so CSS
// order decides which ink wins: review-checked).
function Num({ n, className }: { n: number; className?: string }) { return <span className={cx('text-text-secondary-light', className)}>{n}</span> }
export function P89({ n }: { n: number }) { return <Num className="text-brand-strong" n={n} /> } // gap
// A neutral Badge's count inside a sage link.
export function P90({ n }: { n: number }) { return <Link className="text-brand-strong" href="/x">Inbox <Badge>{n}</Badge></Link> } // flag
// JSX handed to a prop (a tooltip's content) inside a sage control is not the label.
function Tip({ content, children }: { content: ReactNode; children: ReactNode }) { return <span>{children}<span role="tooltip" className="sr-only">{content}</span></span> }
export function P91({ n }: { n: number }) { return <Link className="text-brand-strong" href="/x"><Tip content={<span className="text-text-secondary-light">{n} filings</span>}>Coverage</Tip></Link> } // clean
// The label const declared inside a callback.
export function P92({ rows }: { rows: { n: number }[] }) { return <ul>{rows.map((r) => { const label = <span className="text-text-secondary-light">{r.n}</span>; return <li key={r.n}><Link className="text-brand-strong" href="/x">See {label}</Link></li> })}</ul> } // flag
// A control that turns sage on focus, with its count in a span.
export function P93({ n }: { n: number }) { return <button className="text-text-secondary-light focus-visible:text-brand-strong">Show <span className="text-text-tertiary-light">{n}</span></button> } // flag
// A control that turns sage only under the pointer, with its count in a span.
export function P94({ n }: { n: number }) { return <a href="/x" className="text-text-secondary-light hover:text-brand-strong">See <span className="text-text-tertiary-light">{n}</span></a> } // clean
// An icon given sage.
export function P95() { return <ArrowRightIcon className="h-4 w-4 text-brand-strong" /> } // clean
// Children held in a const inside a component that renders them in sage.
function SageBody({ children }: { children: ReactNode }) { const body = <span className="text-brand-strong">{children}</span>; return <div>{body}</div> }
export function P96({ n }: { n: number }) { return <SageBody>{n}</SageBody> } // flag
// A count a component renders in its own ink inside a sage control (review-checked).
function CountLabel({ n }: { n: number }) { return <>See all <span className="text-text-secondary-light">{n}</span></> }
export function P97({ n }: { n: number }) { return <Link className="text-brand-strong" href="/x"><CountLabel n={n} /></Link> } // gap
// A sage disclosure summary holding its count in a span.
export function P98({ n }: { n: number }) { return <details><summary className="text-brand-strong">Show <span className="text-text-secondary-light">{n}</span> sources</summary></details> } // flag
// A citation bracket in a span of its own inside a sage control.
export function P99({ n }: { n: number }) { return <button className="text-brand-strong">Sources <span className="text-text-secondary-light">[{n}]</span></button> } // clean
// Children handed to Children.map and rendered in an ink of the component's own.
function Quietly({ children }: { children: ReactNode }) { return <ul>{Children.map(children, (c) => <li className="text-text-secondary-light">{c}</li>)}</ul> }
export function P100({ n }: { n: number }) { return <p className="text-brand-strong"><Quietly>{n}</Quietly></p> } // clean
// A number in an attribute is not rendered text.
export function P101({ n }: { n: number }) { return <a className="text-brand-strong" title={`${n} filings`} href="/x">Filings</a> } // clean
// One label const held by two controls.
export function P102({ n }: { n: number }) { const c = <span className="text-text-secondary-light">{n}</span>; return <><Link className="text-brand-strong" href="/a">A {c}</Link><Link className="text-brand-strong" href="/b">B {c}</Link></> } // flag
// Sage handed to a component through a prop other than className (review-checked).
function Pill({ n, tone }: { n: number; tone: string }) { return <span className={tone}>{n}</span> }
export function P103({ n }: { n: number }) { return <Pill tone="text-brand-strong" n={n} /> } // gap
// A click handler's body is not the control's label.
declare function notify(node: ReactNode): void
export function P104({ n }: { n: number }) { const onSave = () => notify(<span className="text-text-secondary-light">{n} saved</span>); return <button className="text-brand-strong" onClick={onSave}>Save</button> } // clean
// A theme size with a line-height modifier outside a control.
export function P105({ n }: { n: number }) { return <p className="text-brand-strong"><span className="text-sm/6">{n}</span></p> } // flag
// A chained || stays read.
export function P106({ n, m }: { n: number; m: number }) { return <p className="text-brand-strong">{n || m || 'none'}</p> } // flag
// A const resolved through the checker: declared after its use, read inside a callback or an inner function,
// and an alias of an alias.
export function P107({ n }: { n: number }) { return <span className={LATE}>{n}</span> } // flag
export function P108({ rows }: { rows: { n: number }[] }) { return <ul>{rows.map((r) => <li key={r.n} className={SAGE}>{r.n}</li>)}</ul> } // flag
export function P109({ n }: { n: number }) { const label = `${n} filings`; const inner = () => <span className="text-brand-strong">{label}</span>; return inner() } // flag
export function P110({ n }: { n: number }) { const seeAll = <span>See all <span className="text-text-secondary-light">{n}</span></span>; const wrap = seeAll; return <Link className="text-brand-strong" href="/x">{wrap}</Link> } // flag
export function P111() { return <ul className="text-brand-strong">{STEPS.map((s) => <li key={s.k}>{s.k}</li>)}</ul> } // flag
const SAGE = 'text-brand-strong'
const LATE = 'text-brand-strong font-semibold'
const STEPS = [{ k: 'Step 2' }, { k: 'Step 3' }]
// A control that inherits its sage from the element around it, holding its count in a span.
export function P112({ n }: { n: number }) { return <p className="text-brand-strong">Read <Link href="/x">see all <span className="text-text-secondary-light">{n}</span></Link></p> } // flag
// A label a helper function builds from the count: read as a call fed a number, as a formatter is.
const renderLabel = (k: number) => <span>See all <span className="text-text-secondary-light">{k}</span></span>
export function P113({ n }: { n: number }) { return <Link className="text-brand-strong" href="/x">{renderLabel(n)}</Link> } // flag
// A const's own text where it is rendered.
export function P114() { const step = 'Step 2'; return <span className="text-brand-strong">{step}</span> } // flag
// `undefined` takes the component's default variant (Badge's neutral).
export function P115({ n, hot }: { n: number; hot: boolean }) { return <Badge variant={hot ? 'solid' : undefined}>{n}</Badge> } // clean
// A component whose className lands inside a fragment, beside its number.
function Frag({ n, className }: { n: number; className?: string }) { return <><span className={className}>Total</span> {n}</> }
export function P116({ n }: { n: number }) { return <Frag className="text-brand-strong" n={n} /> } // clean
