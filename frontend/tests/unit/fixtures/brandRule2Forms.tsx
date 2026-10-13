/**
 * Planted forms for brandCopyRules.spec.ts rule 2 (sage never colours a number, D-030): one component per
 * form, each marked by its trailing comment. `flag` is a form rule 2 must name: one that breaks the rule,
 * or one the gate fails closed on, such as a lookup fed a number (P12) or a variant it cannot read (P87).
 * `clean` is a look-alike that must pass. `gap` is a form the rule forbids and the gate leaves to review
 * (its header names it), so it must pass too, until the gate reaches it and the mark flips. The spec reads
 * this file in the same program as the app and scores every form on every run, so a change to the gate
 * that loses a form, or catches a look-alike, fails there. Outside the scan roots: rule 2's app scan never
 * reads it. A new form the rule can take joins it with its mark.
 */
import React, { Children, type ReactNode, useCallback, useMemo, useState } from 'react'
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
export function P28({ y }: { y: string }) { return <span className="text-brand-strong">FY{y}</span> } // gap
export function P29({ rows }: { rows: string[] }) { return <ul className="text-brand-strong">{rows.map((r) => <li key={r}>Step 1</li>)}</ul> } // flag
export function P30({ rows }: { rows: { n: number }[] }) { return <p className="text-brand-strong">{rows.map((r) => { return r.n })}</p> } // flag
function Outer({ children }: { children: ReactNode }) { return <SageText>{children}</SageText> }
export function P31({ n }: { n: number }) { return <Outer>{n}</Outer> } // flag
export function P32({ n }: { n: number }) { return <p className="text-brand-strong">Upgrade <Button>Get {n} more</Button></p> } // clean
export function P33({ n }: { n: number }) { return <p className="text-brand-strong">New <Badge>{n}</Badge></p> } // clean
export function P34() { return <a className="text-brand-strong">Open the 10-K for FY2025</a> } // flag
export function P35({ n }: { n: number }) { return <span className="text-text-secondary-light group-hover:text-brand-strong">{n}</span> } // clean
export function P36({ n }: { n: number }) { return <span tabIndex={0} className="text-text-secondary-light focus-visible:text-brand-strong">{n}</span> } // flag
export function P37({ n }: { n: number }) { return <button disabled className="text-text-secondary-light disabled:text-brand-strong">{n}</button> } // flag
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
// An index name held in a string ("S&P 500"), as a fiscal year is in P28 (review-checked).
export function P117({ index }: { index: string }) { return <span className="text-brand-strong">Covering the {index}</span> } // gap
// An index name written in words, with no digit to read (review-checked).
export function P118() { return <span className="text-brand-strong">Covering the Dow Jones</span> } // gap
// A same-file class const wherever it stands in the className, and through the consts it is built from.
const SAGE_119 = 'text-brand-strong'
const QUIET_119 = 'text-text-secondary-light'
export function P119({ n, on }: { n: number; on: boolean }) { return <span className={on ? SAGE_119 : QUIET_119}>{n}</span> } // flag
export function P120({ n, on }: { n: number; on: boolean }) { return <span className={cx('font-semibold', on && SAGE_119)}>{n}</span> } // flag
const HOT_121 = `${SAGE_119} font-semibold`
export function P121({ n }: { n: number }) { return <span className={HOT_121}>{n}</span> } // flag
const MUTED_122 = 'text-text-tertiary-light'
export function P122({ n, on }: { n: number; on: boolean }) { return <span className={on ? QUIET_119 : MUTED_122}>{n}</span> } // clean
// A const read by a key is read whole: the scan cannot know the key, and fails closed.
const TONE_123 = { hot: 'text-brand-strong', quiet: 'text-text-secondary-light' }
export function P123({ n, tone }: { n: number; tone: keyof typeof TONE_123 }) { return <span className={TONE_123[tone]}>{n}</span> } // flag
// A map callback's element over a literal array of strings, the array in a const or written inline.
const LABELS_124 = ['Step 2']
export function P124() { return <p>{LABELS_124.map((label) => <span key={label} className="text-brand-strong">{label}</span>)}</p> } // flag
export function P125() { return <p>{['Revenue', 'Margin'].map((label) => <span key={label} className="text-brand-strong">{label}</span>)}</p> } // clean
export function P126() { return <p>{['Q1', 'Q2'].map((q) => <span key={q} className="text-brand-strong">{q}</span>)}</p> } // flag
// A form whose code is a bare number, named as a form; the bare number stays a count (P128).
export function P127() { return <span className="text-brand-strong">Form 4</span> } // clean
export function P128() { return <span className="text-brand-strong">4</span> } // flag
// A shadowing binding is not the mapped element: the inner destructured label is a prop's string.
const LABELS_129 = ['Step 2']
export function P129({ rows }: { rows: { label: string }[] }) { return <p>{LABELS_129.map((label) => <b key={label}>{rows.map(({ label }) => <span key={label} className="text-brand-strong">{label}</span>)}</b>)}</p> } // clean
// A literal array's element however the map callback takes it: destructured, renamed, a tuple's member, a
// field at depth, destructured in the callback's body; the array through a call that keeps its members, and
// through a spread.
const STEPS_130 = [{ step: 'Step 2', meta: { step: 'Step 3' } }]
export function P130() { return <p>{STEPS_130.map(({ step }) => <span key={step} className="text-brand-strong">{step}</span>)}</p> } // flag
export function P131() { return <p>{STEPS_130.map(({ step: s }) => <span key={s} className="text-brand-strong">{s}</span>)}</p> } // flag
const PAIRS_132 = [['Q1', 'Revenue']]
export function P132() { return <p>{PAIRS_132.map(([q]) => <span key={q} className="text-brand-strong">{q}</span>)}</p> } // flag
export function P133() { return <p>{STEPS_130.map((item) => <span key={item.step} className="text-brand-strong">{item.meta.step}</span>)}</p> } // flag
export function P134() { return <p>{STEPS_130.map((item) => { const { step } = item; return <span key={step} className="text-brand-strong">{step}</span> })}</p> } // flag
const LABELS_135 = ['Step 2', 'Step 3']
export function P135() { return <p>{LABELS_135.slice(0, 1).map((label) => <span key={label} className="text-brand-strong">{label}</span>)}</p> } // flag
export function P136() { return <p>{[...LABELS_135, 'Margin'].map((label) => <span key={label} className="text-brand-strong">{label}</span>)}</p> } // flag
// A same-file const read by a field or an index; a key the scan cannot read may be any member, so all are read.
const CONFIG_137 = { step: 'Step 2', name: 'Revenue' }
export function P137() { return <span className="text-brand-strong">{CONFIG_137.step}</span> } // flag
export function P138() { return <span className="text-brand-strong">{LABELS_135[0]}</span> } // flag
export function P139({ i }: { i: number }) { return <span className="text-brand-strong">{LABELS_135[i]}</span> } // flag
// A template's substitutions render with it, written inline or held in a const.
export function P140() { return <p>{LABELS_135.map((label) => <span key={label} className="text-brand-strong">{`Go to ${label}`}</span>)}</p> } // flag
const STEP_141 = 'Step 2'
export function P141() { const label = `Go to ${STEP_141}`; return <span className="text-brand-strong">{label}</span> } // flag
// Look-alikes: words destructured from a literal array, a const's word field, a prop's array (runtime data, not a
// literal), and words read by a key the scan cannot read.
const WORDS_142 = [{ name: 'Revenue' }, { name: 'Margin' }]
export function P142() { return <p>{WORDS_142.map(({ name }) => <span key={name} className="text-brand-strong">{name}</span>)}</p> } // clean
export function P143() { return <span className="text-brand-strong">{CONFIG_137.name}</span> } // clean
export function P144({ rows }: { rows: { label: string }[] }) { return <p>{rows.map(({ label }) => <span key={label} className="text-brand-strong">{label}</span>)}</p> } // clean
const NAMES_145 = ['Revenue', 'Margin']
export function P145({ i }: { i: number }) { return <span className="text-brand-strong">{NAMES_145[i]}</span> } // clean
// A class that is no const: destructured from a class map read by a key, with a fallback (the dashboard's
// What-changed chip), destructured by a field and renamed, and a map callback's element's class field.
const TONE_146 = { up: { cls: 'text-brand-strong' }, down: { cls: 'text-text-secondary-light' } }
export function P146({ n, dir }: { n: number; dir: 'up' | 'down' }) { const { cls } = TONE_146[dir] ?? TONE_146.down; return <span className={`rounded-full ${cls}`}>{n}</span> } // flag
export function P147({ n }: { n: number }) { const { cls: tone } = TONE_146.up; return <span className={tone}>{n}</span> } // flag
const CHIPS_148 = [{ cls: 'text-brand-strong', quiet: 'text-text-secondary-light' }]
export function P148({ n }: { n: number }) { return <p>{CHIPS_148.map((chip) => <span key={chip.cls} className={chip.cls}>{n}</span>)}</p> } // flag
// Look-alikes: the same reads selecting a class that is not sage.
export function P149({ n }: { n: number }) { const { cls } = TONE_146.down; return <span className={cls}>{n}</span> } // clean
export function P150({ n }: { n: number }) { return <p>{CHIPS_148.map((chip) => <span key={chip.quiet} className={chip.quiet}>{n}</span>)}</p> } // clean
// A value the server sends as text (a formatted delta) renders as a name would: no digit or type to read.
export function P151({ display }: { display: string }) { return <span className="text-brand-strong">{display}</span> } // gap
// A const that holds a member or a keyed read of a literal, read by a field or destructured (the admin badges'
// `const config = MAP[status] ?? MAP.x; const { className } = config`).
const STEPS_152 = [{ step: 'Step 2' }]
export function P152() { const first = STEPS_152[0]; return <span className="text-brand-strong">{first.step}</span> } // flag
const STATUS_153 = { live: { cls: 'text-brand-strong' }, quiet: { cls: 'text-text-secondary-light' } }
export function P153({ n, s }: { n: number; s: 'live' | 'quiet' }) { const config = STATUS_153[s] ?? STATUS_153.quiet; const { cls } = config; return <span className={cls}>{n}</span> } // flag
// A nested map over an element's field; an index into an array with a spread, which may land on any member, so
// the gate fails closed; an object spread; a shorthand property.
const GROUPS_154 = [{ items: ['Step 2'] }]
export function P154() { return <div>{GROUPS_154.map((g, i) => <p key={i}>{g.items.map((it) => <span key={it} className="text-brand-strong">{it}</span>)}</p>)}</div> } // flag
const ALL_155 = [...LABELS_135, 'Margin']
export function P155() { return <span className="text-brand-strong">{ALL_155[2]}</span> } // flag
const COPY_156 = { ...CONFIG_137, title: 'Overview' }
export function P156() { return <span className="text-brand-strong">{COPY_156.step}</span> } // flag
const STEP_157 = 'Step 2'
const COPY_157 = { STEP_157 }
export function P157() { return <span className="text-brand-strong">{COPY_157.STEP_157}</span> } // flag
// Look-alikes: words through the same chains.
export function P158() { const first = WORDS_142[0]; return <span className="text-brand-strong">{first.name}</span> } // clean
const GROUPS_159 = [{ items: ['Revenue', 'Margin'] }]
export function P159() { return <div>{GROUPS_159.map((g, i) => <p key={i}>{g.items.map((it) => <span key={it} className="text-brand-strong">{it}</span>)}</p>)}</div> } // clean
// A conditional written in a literal's field is read as written: the scan cannot tie it to the element's other
// fields (a plan's button variant and its label), so it stays review-checked.
const PLANS_160 = [{ cta: Math.random() > 0.5 ? 'Start 7-day trial' : 'Upgrade' }]
export function P160() { return <p>{PLANS_160.map((plan) => <span key={plan.cta} className="text-brand-strong">{plan.cta}</span>)}</p> } // gap
// The review of c9bd846: a parameter takes the values the file binds it to. A map's callback held in a name, not
// written inline (P161, the review's own form), however the name holds it: a function declaration, a function
// expression, a literal object's field or method, a wrapper, either branch of a conditional; destructuring its
// element; and named under a sage parent, a literal's text or a number's type.
const LABELS_161 = ['Step 2']
const WORDS_161 = ['Revenue']
const STEPS_161 = [{ step: 'Step 2' }]
export function P161() { const render = (label: string) => <span key={label} className="text-brand-strong">{label}</span>; return <p>{LABELS_161.map(render)}</p> } // flag
export function P162() { function render(label: string) { return <span key={label} className="text-brand-strong">{label}</span> } return <p>{LABELS_161.map(render)}</p> } // flag
export function P163() { const render = function (label: string) { return <span key={label} className="text-brand-strong">{label}</span> }; return <p>{LABELS_161.map(render)}</p> } // flag
export function P164() { const R = { chip: (label: string) => <span key={label} className="text-brand-strong">{label}</span> }; return <p>{LABELS_161.map(R.chip)}</p> } // flag
export function P165() { const R = { chip(label: string) { return <span key={label} className="text-brand-strong">{label}</span> } }; return <p>{LABELS_161.map(R.chip)}</p> } // flag
export function P166() { const render = useCallback((label: string) => <span key={label} className="text-brand-strong">{label}</span>, []); return <p>{LABELS_161.map(render)}</p> } // flag
export function P167({ on }: { on: boolean }) { const a = (label: string) => <span key={label} className="text-brand-strong">{label}</span>; const b = (label: string) => <span key={label}>{label}</span>; return <p>{LABELS_161.map(on ? a : b)}</p> } // flag
export function P168() { const render = ({ step }: { step: string }) => <span key={step} className="text-brand-strong">{step}</span>; return <p>{STEPS_161.map(render)}</p> } // flag
export function P169() { const render = (label: string) => <span key={label}>{label}</span>; return <p className="text-brand-strong">{LABELS_161.map(render)}</p> } // flag
export function P170({ rows }: { rows: number[] }) { const render = (n: number) => <span key={n}>{n}</span>; return <p className="text-brand-strong">{rows.map(render)}</p> } // flag
export function P171() { const R = { chip: (label: string) => <span key={label} className="text-brand-strong">{label}</span> }; return <p>{LABELS_161.map(R['chip'])}</p> } // flag
// Look-alikes: a named callback over words, over a prop's array (runtime data), and one whose index it never
// renders; the same callback mapped over two arrays of words.
export function P172() { const render = (label: string) => <span key={label} className="text-brand-strong">{label}</span>; return <p>{WORDS_161.map(render)}</p> } // clean
export function P173({ rows }: { rows: { label: string }[] }) { const render = ({ label }: { label: string }) => <span key={label} className="text-brand-strong">{label}</span>; return <p>{rows.map(render)}</p> } // clean
export function P174() { const render = (label: string, i: number) => <span key={i} className="text-brand-strong">{label}</span>; return <p>{WORDS_161.map(render)}</p> } // clean
export function P175() { const render = (label: string) => <span key={label} className="text-brand-strong">{label}</span>; return <p>{WORDS_161.map(render)}{['Margin'].map(render)}</p> } // clean
// The other array methods that hand a callback its members (flatMap, forEach, reduce's second parameter), and
// Array.from's mapper.
export function P176() { return <p>{LABELS_161.flatMap((label) => [<span key={label} className="text-brand-strong">{label}</span>])}</p> } // flag
export function P177() { const out: ReactNode[] = []; LABELS_161.forEach((label) => { out.push(<span key={label} className="text-brand-strong">{label}</span>) }); return <p>{out}</p> } // flag
export function P178() { return <p>{LABELS_161.reduce<ReactNode[]>((all, label) => [...all, <span key={label} className="text-brand-strong">{label}</span>], [])}</p> } // flag
export function P179() { return <p>{Array.from(LABELS_161, (label) => <span key={label} className="text-brand-strong">{label}</span>)}</p> } // flag
// A function called by name: its parameters take the call's arguments, in place, through a callback that calls
// it and a helper that calls another; a rest parameter takes the arguments from its place on, and a spread
// argument may fill any place after it.
export function P180() { const chip = (text: string) => <span className="text-brand-strong">{text}</span>; return <p>{chip('Step 2')}</p> } // flag
export function P181() { const render = (label: string) => <span key={label} className="text-brand-strong">{label}</span>; return <p>{LABELS_161.map((l) => render(l))}</p> } // flag
export function P182() { const inner = (t: string) => <span className="text-brand-strong">{t}</span>; const outer = (t: string) => inner(t); return <p>{outer('Step 2')}</p> } // flag
export function P183() { const chips = (...labels: string[]) => <p>{labels.map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p>; return chips('Step 2') } // flag
export function P184() { const chip = (text: string) => <span className="text-brand-strong">{text}</span>; return chip(...(LABELS_161 as [string])) } // flag
// Look-alikes: a call with words, the sage one of two helpers that share a parameter's name called with words, a
// helper never called, and a recursion that ends.
export function P185() { const chip = (text: string) => <span className="text-brand-strong">{text}</span>; return <p>{chip('Revenue')}</p> } // clean
export function P186() { const a = (label: string) => <span className="text-brand-strong">{label}</span>; const b = (label: string) => <span className="text-text-secondary-light">{label}</span>; return <p>{a('Revenue')}{b('Step 2')}</p> } // clean
export function P187() { const chip = (text: string) => <span className="text-brand-strong">{text}</span>; return <p>{typeof chip}</p> } // clean
export function P188() { const walk = (t: string): ReactNode => (t.length > 9 ? <span className="text-brand-strong">{t}</span> : walk(`${t}!`)); return <p>{walk('Revenue')}</p> } // clean
// A recursive callback ends, and is read. A parameter the file binds at several calls takes every call's value:
// the call under sage passes words and the other a digit, so the gate fails closed.
type Node189 = { label: string; kids: Node189[] }
const TREE_189: Node189[] = [{ label: 'Step 2', kids: [] }]
export function P189() { const render = (n: Node189): ReactNode => <li key={n.label} className="text-brand-strong">{n.label}{n.kids.map(render)}</li>; return <ul>{TREE_189.map(render)}</ul> } // flag
export function P190() { const label = (t: string) => <span>{t}</span>; return <><p className="text-brand-strong">{label('Revenue')}</p><p className="text-text-secondary-light">{label('Q3')}</p></> } // flag
// A call renders what its same-file function returns: under a sage parent, a literal argument's text and a
// template built from an object's number.
export function P191() { const label = (t: string) => <span>{t}</span>; return <p className="text-brand-strong">{label('Q3')}</p> } // flag
export function P192() { const label = (t: string) => <span>{t}</span>; return <p className="text-brand-strong">{label('Revenue')}</p> } // clean
export function P193({ item }: { item: { count: number } }) { const caption = (f: { count: number }) => `${f.count} filings`; return <span className="text-brand-strong">{caption(item)}</span> } // flag
// A default stands beside what the binding takes: a parameter's and a destructured name's.
export function P194() { const chip = (text = 'Step 2') => <span className="text-brand-strong">{text}</span>; return <p>{chip()}</p> } // flag
export function P195({ item }: { item: { step?: string } }) { const { step = 'Step 2' } = item; return <span className="text-brand-strong">{step}</span> } // flag
// A variable takes every value the file assigns it: a text, JSX held for a sage control's label, a class.
export function P196({ on }: { on: boolean }) { let label = 'Revenue'; if (on) label = 'Step 2'; return <span className="text-brand-strong">{label}</span> } // flag
export function P197({ n, on }: { n: number; on: boolean }) { let label = <span>Saved</span>; if (on) label = <span>See <span className="text-text-secondary-light">{n}</span></span>; return <Link className="text-brand-strong" href="/x">{label}</Link> } // flag
export function P198({ n }: { n: number }) { let cls = 'text-text-secondary-light'; if (n > 9) cls = 'text-brand-strong'; return <span className={cls}>{n}</span> } // flag
// A class reaches an element through a helper's parameter, or its default; a helper given a quiet class passes.
export function P199({ n }: { n: number }) { const pill = (tone: string) => <span className={tone}>{n}</span>; return pill('text-brand-strong') } // flag
export function P200({ n }: { n: number }) { const pill = (tone = 'text-brand-strong') => <span className={tone}>{n}</span>; return pill() } // flag
export function P201({ n }: { n: number }) { const pill = (tone: string) => <span className={tone}>{n}</span>; return pill('text-text-secondary-light') } // clean
// A sage control holds its count in a span of its own ink through a helper it calls or a callback it maps with.
export function P202() { const label = (t: string) => <span>See <span className="text-text-secondary-light">{t}</span></span>; return <Link className="text-brand-strong" href="/x">{label('3 filings')}</Link> } // flag
export function P203({ rows }: { rows: { n: number }[] }) { const render = (r: { n: number }) => <span key={r.n} className="text-text-secondary-light">{r.n}</span>; return <Link className="text-brand-strong" href="/x">See {rows.map(render)}</Link> } // flag
// A loop's variable: a for…of one takes the array's members, a for…in one the object's keys.
export function P204() { const out: ReactNode[] = []; for (const label of LABELS_161) out.push(<span key={label} className="text-brand-strong">{label}</span>); return <p>{out}</p> } // flag
export function P205() { const out: ReactNode[] = []; for (const label of WORDS_161) out.push(<span key={label} className="text-brand-strong">{label}</span>); return <p>{out}</p> } // clean
export function P206() { const out: ReactNode[] = []; for (const k in { Q1: 1 }) out.push(<span key={k} className="text-brand-strong">{k}</span>); return <p>{out}</p> } // flag
// A member a call returns (find, at), an object's values, entries (a shorthand's included) and keys, and what a
// map returns: indexed, a conditional it returns, joined.
const OBJ_207 = { a: 'Q1', b: 'Q2' }
const KEYS_207 = { Q1: 'Revenue' }
export function P207({ k }: { k: string }) { const s = STEPS_161.find((x) => x.step === k); return <span className="text-brand-strong">{s?.step}</span> } // flag
export function P208() { return <span className="text-brand-strong">{LABELS_161.at(0)}</span> } // flag
export function P209() { return <p>{Object.values(OBJ_207).map((v) => <span key={v} className="text-brand-strong">{v}</span>)}</p> } // flag
export function P210() { return <p>{Object.entries(OBJ_207).map(([k, v]) => <span key={k} className="text-brand-strong">{v}</span>)}</p> } // flag
export function P211() { const q = 'Q1'; return <p>{Object.entries({ q }).map(([k, v]) => <span key={k} className="text-brand-strong">{v}</span>)}</p> } // flag
export function P212() { return <p>{Object.keys(KEYS_207).map((k) => <span key={k} className="text-brand-strong">{k}</span>)}</p> } // flag
export function P213({ k }: { k: string }) { return <span className="text-brand-strong">{Object.values(OBJ_207).find((v) => v === k)}</span> } // flag
export function P214() { const labels = STEPS_161.map((s) => s.step); return <span className="text-brand-strong">{labels[0]}</span> } // flag
const FLAGGED_215 = [{ on: true, step: 'Step 2' }]
export function P215() { const labels = FLAGGED_215.map((s) => (s.on ? s.step : 'Overview')); return <span className="text-brand-strong">{labels[0]}</span> } // flag
export function P216() { return <span className="text-brand-strong">{STEPS_161.map((s) => s.step).join(' · ')}</span> } // flag
// A join, an array rendered whole, a Set and Array.from keep their members; a computed key may name any property;
// a non-null assertion reads through.
export function P217() { return <span className="text-brand-strong">{LABELS_161.join(', ')}</span> } // flag
export function P218() { return <span className="text-brand-strong">{LABELS_161}</span> } // flag
export function P219() { return <span className="text-brand-strong">{['Q1', 'Q2']}</span> } // flag
export function P220() { return <p>{[...new Set(LABELS_161)].map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P221() { return <p>{Array.from(LABELS_161).map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P222({ k }: { k: 'a' }) { const { [k]: v } = OBJ_207; return <span className="text-brand-strong">{v}</span> } // flag
export function P223() { return <span className="text-brand-strong">{STEPS_161[0]!.step}</span> } // flag
// Look-alikes: words joined, rendered whole.
export function P224() { return <span className="text-brand-strong">{WORDS_161.join(', ')}</span> } // clean
export function P225() { return <span className="text-brand-strong">{WORDS_161}</span> } // clean
// An array of numbers renders every one's digits, whole or joined; one of names does not.
export function P226({ counts }: { counts: number[] }) { return <span className="text-brand-strong">{counts}</span> } // flag
export function P227({ counts }: { counts: number[] }) { return <span className="text-brand-strong">{counts.join(', ')}</span> } // flag
export function P228({ names }: { names: string[] }) { return <span className="text-brand-strong">{names.join(', ')}</span> } // clean
// A component renders a const's digits in the ink it inherits, inside a sage parent.
function Caption229() { const s = 'Step 2'; return <>{s}</> }
export function P229() { return <span className="text-brand-strong"><Caption229 /></span> } // flag
// What a function returns or a variable holds is reported where it is rendered, not where it is written: the
// helper and the consts sit on lines of their own (a text under a sage parent, a count a sage control holds).
const label234 = (t: string) => <span>{t}</span>
export function P234() { return <p className="text-brand-strong">{label234('Q3')}</p> } // flag
const SEE_235 = <span>See 3 filings</span>
export function P235() { return <p className="text-brand-strong">{SEE_235}</p> } // flag
const SEE_236 = <span>See <span className="text-text-secondary-light">3</span> filings</span>
export function P236() { return <Link className="text-brand-strong" href="/x">{SEE_236}</Link> } // flag
// The lens on this round's draft: a component renders what a same-file helper returns in the ink it inherits; a
// number handed to a parameter typed wider than a number (ReactNode, `string | number`), read by the type of what
// each call passes, mapped over numbers, or destructured from an object; a function that hands a parameter to itself
// at several calls ends in time; a value held in what a call returns (useMemo, a helper); a destructuring assignment
// and a callback a variable is reassigned; and JSX handed to a helper, a label's text, a value, a count control's.
function Cap237() { const label = (t: string) => <>{t}</>; return <>{label('Q3')}</> }
export function P237() { return <span className="text-brand-strong"><Cap237 /></span> } // flag
function Cap238() { const label = (t: string) => t; return <>{label('Q3')}</> }
export function P238() { return <span className="text-brand-strong"><Cap238 /></span> } // flag
function Cap239() { const label = (t: string) => <>{t}</>; return <>{label('Revenue')}</> }
export function P239() { return <span className="text-brand-strong"><Cap239 /></span> } // clean
export function P240({ n }: { n: number }) { const chip = (v: ReactNode) => <span className="text-brand-strong">{v}</span>; return chip(n) } // flag
export function P241({ n }: { n: number }) { const chip = (v: string | number) => <span className="text-brand-strong">{v}</span>; return chip(n + 1) } // flag
export function P242({ counts }: { counts: number[] }) { const render = (v: ReactNode) => <span className="text-brand-strong">{v}</span>; return <p>{counts.map(render)}</p> } // flag
export function P243({ n }: { n: number }) { const chip = ({ v }: { v: ReactNode }) => <span className="text-brand-strong">{v}</span>; return chip({ v: n }) } // flag
export function P244({ name }: { name: string }) { const chip = (v: ReactNode) => <span className="text-brand-strong">{v}</span>; return chip(name) } // clean
export function P245() { const walk = (t: string, d: number): ReactNode => (d > 3 ? <span className="text-brand-strong">{t}</span> : <>{walk(t, d + 1)}{walk(t, d + 2)}{walk(t, d + 3)}{walk(t, d + 4)}</>); return walk('Q3', 0) } // flag
export function P246() { const walk = (t: string, d: number): ReactNode => (d > 3 ? <span className="text-brand-strong">{t}</span> : <>{walk(t, d + 1)}{walk(t, d + 2)}{walk(t, d + 3)}{walk(t, d + 4)}</>); return walk('Revenue', 0) } // clean
export function P247() { const labels = useMemo(() => ['Step 2'], []); return <p>{labels.map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P248() { const build = () => ['Step 2']; const ls = build(); return <span className="text-brand-strong">{ls[0]}</span> } // flag
export function P249() { const build = () => ['Step 2']; return <span className="text-brand-strong">{build()[0]}</span> } // flag
export function P250() { const labels = useMemo(() => ['Revenue'], []); return <p>{labels.map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // clean
export function P251({ on }: { on: boolean }) { let label = 'Revenue'; if (on) [label] = LABELS_161; return <span className="text-brand-strong">{label}</span> } // flag
export function P252({ on }: { on: boolean }) { let label = 'Revenue'; if (on) ({ step: label } = STEPS_161[0]); return <span className="text-brand-strong">{label}</span> } // flag
export function P253({ on }: { on: boolean }) { let render = (l: string) => <span key={l}>{l}</span>; if (on) render = (l: string) => <span key={l} className="text-brand-strong">{l}</span>; return <p>{LABELS_161.map(render)}</p> } // flag
export function P254() { const wrap = (c: ReactNode) => <span className="text-brand-strong">{c}</span>; return wrap(<b>Step 2</b>) } // flag
export function P255({ n }: { n: number }) { const wrap = (c: ReactNode) => <span className="text-brand-strong">{c}</span>; return wrap(<b>{n}</b>) } // flag
export function P256({ n }: { n: number }) { const control = (label: ReactNode) => <Link className="text-brand-strong" href="/x">{label}</Link>; return control(<span>See <span className="text-text-secondary-light">{n}</span></span>) } // flag
export function P257() { const wrap = (c: ReactNode) => <span className="text-brand-strong">{c}</span>; return wrap(<b>Revenue</b>) } // clean
// Look-alikes beside the loop, the default and the reassignment above: words.
export function P258() { const out: ReactNode[] = []; for (const k in { Revenue: 1 }) out.push(<span key={k} className="text-brand-strong">{k}</span>); return <p>{out}</p> } // clean
export function P259() { const chip = (text = 'Revenue') => <span className="text-brand-strong">{text}</span>; return <p>{chip()}</p> } // clean
export function P260({ on }: { on: boolean }) { let label = 'Revenue'; if (on) label = 'Margin'; return <span className="text-brand-strong">{label}</span> } // clean
// Codex's review of f00c4be: a control held as JSX and rendered under a sage parent rests in that sage, which the
// count control check read only where the control is written. The family: each way the file's bindings carry a
// control to where it is rendered, and a component that renders one in the ink it inherits, reported where it is
// rendered.
export function P261({ n }: { n: number }) { const action = <button>See <span className="text-text-secondary-light">{n}</span></button>; return <div className="text-brand-strong">{action}</div> } // flag
const ACTION_262 = <button>See <span className="text-text-secondary-light">3</span> filings</button>
export function P262() { return <div className="text-brand-strong">{ACTION_262}</div> } // flag
export function P263({ rows }: { rows: number[] }) { const render = (k: number) => <button key={k}>See <span className="text-text-secondary-light">{k}</span></button>; return <div className="text-brand-strong">{rows.map(render)}</div> } // flag
export function P264({ n }: { n: number }) { const action = useMemo(() => <button>See <span className="text-text-secondary-light">{n}</span></button>, [n]); return <div className="text-brand-strong">{action}</div> } // flag
export function P265({ n, on }: { n: number; on: boolean }) { const action = on ? <button>See <span className="text-text-secondary-light">{n}</span></button> : null; return <div className="text-brand-strong">{action}</div> } // flag
export function P266({ n }: { n: number }) { const actions = { see: <button>See <span className="text-text-secondary-light">{n}</span></button> }; return <div className="text-brand-strong">{actions.see}</div> } // flag
export function P267({ n }: { n: number }) { const items = [<button key="a">See <span className="text-text-secondary-light">{n}</span></button>]; return <div className="text-brand-strong">{items}</div> } // flag
export function P268({ n, on }: { n: number; on: boolean }) { let action: ReactNode = null; if (on) action = <button>See <span className="text-text-secondary-light">{n}</span></button>; return <div className="text-brand-strong">{action}</div> } // flag
export function P269({ n }: { n: number }) { const action = <button>See <span className="text-text-secondary-light">{n}</span></button>; return <div className="text-brand-strong"><p>{action}</p></div> } // flag
export function P270({ n }: { n: number }) { const wrap = (c: ReactNode) => <div className="text-brand-strong">{c}</div>; return wrap(<button>See <span className="text-text-secondary-light">{n}</span></button>) } // flag
export function P271({ n }: { n: number }) { const inner = <button>See <span className="text-text-secondary-light">{n}</span></button>; const outer = <p>{inner}</p>; return <div className="text-brand-strong">{outer}</div> } // flag
export function P272({ n }: { n: number }) { const action = <button>See <span className="text-text-secondary-light">{n}</span></button>; const box = <div className="text-brand-strong">{action}</div>; return box } // flag
export function P273({ n }: { n: number }) { const action = <a href="/x">See <span className="text-text-secondary-light">{n}</span></a>; return <div className="text-brand-strong">{action}</div> } // flag
export function P274({ n }: { n: number }) { const action = <><button>See <span className="text-text-secondary-light">{n}</span></button></>; return <div className="text-brand-strong">{action}</div> } // flag
export function P275({ n }: { n: number }) { const action = <button>See <span className="text-text-secondary-light">{n}</span></button>; const { a } = { a: action }; return <div className="text-brand-strong">{a}</div> } // flag
export function P276({ n }: { n: number }) { const label = <span className="text-text-secondary-light">{n}</span>; const action = <button>See {label}</button>; return <div className="text-brand-strong">{action}</div> } // flag
export function P277({ rows }: { rows: number[] }) { const items = rows.map((k) => <button key={k}>See <span className="text-text-secondary-light">{k}</span></button>); return <div className="text-brand-strong">{items}</div> } // flag
export function P278({ n, on }: { n: number; on: boolean }) { const action = <button>See <span className="text-text-secondary-light">{n}</span></button>; return <div className="text-brand-strong">{on && action}</div> } // flag
function Sage279({ children }: { children: ReactNode }) { return <div className="text-brand-strong">{children}</div> }
export function P279({ n }: { n: number }) { const action = <button>See <span className="text-text-secondary-light">{n}</span></button>; return <Sage279>{action}</Sage279> } // flag
export function P280({ rows }: { rows: number[] }) { const render = useCallback((k: number) => <button key={k}>See <span className="text-text-secondary-light">{k}</span></button>, []); return <div className="text-brand-strong">{rows.map(render)}</div> } // flag
function Action281({ n }: { n: number }) { return <button>See <span className="text-text-secondary-light">{n}</span></button> }
export function P281({ n }: { n: number }) { return <div className="text-brand-strong"><Action281 n={n} /></div> } // flag
export function P282({ n }: { n: number }) { const c = <Action281 n={n} />; return <div className="text-brand-strong">{c}</div> } // flag
function Action283({ className, n }: { className?: string; n: number }) { return <button className={className}>See <span className="text-text-secondary-light">{n}</span></button> }
export function P283({ n }: { n: number }) { return <Action283 className="text-brand-strong" n={n} /> } // flag
function Action284({ n }: { n: number }) { const a = <button>See <span className="text-text-secondary-light">{n}</span></button>; return <>{a}</> }
export function P284({ n }: { n: number }) { return <div className="text-brand-strong"><Action284 n={n} /></div> } // flag
function Outer285({ n }: { n: number }) { return <p><Action281 n={n} /></p> }
export function P285({ n }: { n: number }) { return <div className="text-brand-strong"><Outer285 n={n} /></div> } // flag
// Look-alikes: the parent is not sage, or sage only under the pointer; an element between them sets its own ink; the
// control takes the recipe (its whole label in the ink) or holds no count; the held element is no control.
export function P286({ n }: { n: number }) { const action = <button>See <span className="text-text-secondary-light">{n}</span></button>; return <div className="text-text-primary-light">{action}</div> } // clean
export function P287({ n }: { n: number }) { const action = <button className="text-text-secondary-light">See {n}</button>; return <div className="text-brand-strong">{action}</div> } // clean
export function P288() { const action = <button>See <span className="text-text-secondary-light">all</span></button>; return <div className="text-brand-strong">{action}</div> } // clean
export function P289({ n }: { n: number }) { const action = <button>See <span className="text-text-secondary-light">{n}</span></button>; return <div className="hover:text-brand-strong">{action}</div> } // clean
export function P290({ n }: { n: number }) { const action = <button>See <span className="text-text-secondary-light">{n}</span></button>; return <div className="text-brand-strong"><p className="text-text-primary-light">{action}</p></div> } // clean
export function P291({ n }: { n: number }) { const wrap = (c: ReactNode) => <div className="text-text-primary-light">{c}</div>; return wrap(<button>See <span className="text-text-secondary-light">{n}</span></button>) } // clean
export function P292({ n }: { n: number }) { return <div className="text-text-primary-light"><Action281 n={n} /></div> } // clean
export function P293({ n }: { n: number }) { const action = <span>See <span className="text-text-secondary-light">{n}</span></span>; return <div className="text-brand-strong">{action}</div> } // clean
function Action294({ n }: { n: number }) { return <button className="text-text-secondary-light">See {n}</button> }
export function P294({ n }: { n: number }) { return <div className="text-brand-strong"><Action294 n={n} /></div> } // clean
export function P295({ n }: { n: number }) { return <Action283 className="text-text-primary-light" n={n} /> } // clean
export function P296({ n }: { n: number }) { const c = <Action281 n={n} />; return <div className="text-text-primary-light">{c}</div> } // clean
// The re-review of c9bd846: a rest element in a binding pattern holds what the others leave. It is read as the whole
// it is taken from, an object's other properties by the key asked for, so an array's rest fails closed on the
// members before its place (P303).
export function P297() { const [, ...rest] = ['Revenue', 'Step 2']; return <span className="text-brand-strong">{rest}</span> } // flag
export function P298() { const [, ...rest] = ['Revenue', 'Step 2']; return <p>{rest.map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P299() { const [, ...rest] = ['Revenue', 'Step 2']; return <span className="text-brand-strong">{rest[0]}</span> } // flag
export function P300() { const { title, ...others } = { title: 'Overview', step: 'Step 2' }; return <span className="text-brand-strong">{title}{others.step}</span> } // flag
export function P301() { const chip = ([, ...rest]: string[]) => <span className="text-brand-strong">{rest}</span>; return chip(['Revenue', 'Step 2']) } // flag
export function P302() { for (const [, ...rest] of [['Revenue', 'Step 2']]) return <span className="text-brand-strong">{rest}</span>; return null } // flag
export function P303() { const [first, ...rest] = ['Step 2', 'Revenue']; return <><span>{first}</span><span className="text-brand-strong">{rest}</span></> } // flag
export function P304() { const [, ...rest] = ['Revenue', 'Margin']; return <span className="text-brand-strong">{rest}</span> } // clean
export function P305() { const { step, ...others } = { step: 'Step 2', title: 'Overview' }; return <><span>{step}</span><span className="text-brand-strong">{others.title}</span></> } // clean
// The lens on that fix: a component given an onClick is a control at its use site and may render one of its own; a
// component's control under an element of its own ink is not the parent's; a sage className the component never
// applies is no ink of its; two components that render each other are read the same whichever the scan meets first
// (the clean form, written before the two, makes the scan meet the outer one first, the order in which a summary read
// mid-cycle used to be kept); and an element written in a prop or a handler renders where the component puts it, or
// not at all.
function Wrap307({ n, onClick, children }: { n: number; onClick?: () => void; children?: ReactNode }) { return <button onClick={onClick}>{children} <span className="text-text-secondary-light">{n}</span></button> }
export function P307({ n }: { n: number }) { return <div className="text-brand-strong"><Wrap307 n={n} onClick={() => {}}>See</Wrap307></div> } // flag
export function P308({ n }: { n: number }) { const a = <Wrap307 n={n} onClick={() => {}}>See</Wrap307>; return <div className="text-brand-strong">{a}</div> } // flag
function Shell309({ n }: { n: number }) { return <p className="text-text-primary-light"><button>See <span className="text-text-secondary-light">{n}</span></button></p> }
export function P309({ n }: { n: number }) { return <div className="text-brand-strong"><Shell309 n={n} /></div> } // clean
function Ignores310({ n }: { className?: string; n: number }) { return <button>See <span className="text-text-secondary-light">{n}</span></button> }
export function P310({ n }: { n: number }) { return <Ignores310 className="text-brand-strong" n={n} /> } // clean
export function P311({ n }: { n: number }) { return <div className="text-text-primary-light"><Ring311 d={1} n={n} /></div> } // clean
function Ring311({ d, n }: { d: number; n: number }): ReactNode { return <div>{d ? <Round311 d={d - 1} n={n} /> : <button>See <span className="text-text-secondary-light">{n}</span></button>}</div> }
function Round311({ d, n }: { d: number; n: number }): ReactNode { return <p><Ring311 d={d} n={n} /></p> }
export function P312({ n }: { n: number }) { return <div className="text-brand-strong"><Round311 d={2} n={n} /></div> } // flag
export function P313({ n }: { n: number }) { return <div className="text-text-primary-light"><Ring313 d={1} n={n} /></div> } // clean
function Ring313({ d, n }: { d: number; n: number }): ReactNode { return <div>{d ? <Round313 d={d - 1} n={n} /> : n}</div> }
function Round313({ d, n }: { d: number; n: number }): ReactNode { return <p><Ring313 d={d} n={n} /></p> }
export function P314({ n }: { n: number }) { return <div className="text-brand-strong"><Round313 d={2} n={n} /></div> } // flag
function Tip315({ content, children }: { content: ReactNode; children: ReactNode }) { return <span title="tip">{children}{content ? null : null}</span> }
export function P315({ n }: { n: number }) { return <Link className="text-brand-strong" href="/x"><Tip315 content={<button>See <span className="text-text-secondary-light">{n}</span></button>}>Coverage</Tip315></Link> } // clean
export function P316({ n }: { n: number }) { return <div className="text-brand-strong" onMouseEnter={() => { const a = <button>See <span className="text-text-secondary-light">{n}</span></button>; void a }}>Coverage</div> } // clean
// Out of the file's own calls, and so review-checked: a value handed to a component as a prop (JSX binds its
// props, which the component check reads only for children and className), a count control handed as one, a
// hook's state, and a callback handed through another function's parameter.
export function P230() { return <Chip230 label="Step 2" /> } function Chip230({ label }: { label: string }) { return <span className="text-brand-strong">{label}</span> } // gap
export function P231() { return <p>{LABELS_161.map((l) => <Chip231 key={l} label={l} />)}</p> } function Chip231({ label }: { label: string }) { return <span className="text-brand-strong">{label}</span> } // gap
export function P232() { const [label] = useState('Step 2'); return <span className="text-brand-strong">{label}</span> } // gap
export function P233() { const list = (render: (s: string) => ReactNode) => LABELS_161.map(render); return <p>{list((s) => <span key={s} className="text-brand-strong">{s}</span>)}</p> } // gap
export function P306({ n }: { n: number }) { return <Panel306 action={<button>See <span className="text-text-secondary-light">{n}</span></button>} /> } function Panel306({ action }: { action: ReactNode }) { return <div className="text-brand-strong">{action}</div> } // gap
// A className given where a component is used, out of reach two more ways: handed to an element below the one the
// component returns, or never applied, its ink then masking the sage the component inherits.
export function P317({ n }: { n: number }) { return <Deep317 className="text-brand-strong" n={n} /> } function Deep317({ className, n }: { className?: string; n: number }) { return <div><span className={className}>{n}</span></div> } // gap
export function P318({ n }: { n: number }) { return <div className="text-brand-strong"><Ignores310 className="text-text-primary-light" n={n} /></div> } // gap
// Codex's review of f5526d3: JSX normalised by React's Children.toArray (P319, the review's own form) was unread. The
// family: the calls that keep what they are given or add to it (Children.toArray, concat, flat, by either name React
// gives Children), the callbacks Children.map and forEach bind, a count control carried through such a call, and a
// list a call makes rendered whole.
export function P319({ n }: { n: number }) { const kids = Children.toArray([<span key="n">{n}</span>]); return <div className="text-brand-strong">{kids}</div> } // flag
export function P320() { return <p>{Children.toArray(LABELS_161).map((l) => <span key={String(l)} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P321() { return <span className="text-brand-strong">{React.Children.toArray(LABELS_161)}</span> } // flag
export function P322() { return <p>{Children.map(LABELS_161, (l) => <span key={String(l)} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P323() { const out: ReactNode[] = []; Children.forEach(LABELS_161, (l) => { out.push(<span key={String(l)} className="text-brand-strong">{l}</span>) }); return <p>{out}</p> } // flag
export function P324() { return <p>{WORDS_161.concat(LABELS_161).map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P325() { return <p>{WORDS_161.concat(['Margin']).map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // clean
export function P326() { return <p>{WORDS_161.concat('Q3').map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P327() { return <p>{[WORDS_161, LABELS_161].flat().map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P328() { return <p>{[WORDS_161, ['Margin']].flat().map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // clean
export function P329() { return <span className="text-brand-strong">{LABELS_161.slice(0)}</span> } // flag
export function P330() { return <span className="text-brand-strong">{WORDS_161.concat(['Margin'])}</span> } // clean
export function P331({ n }: { n: number }) { const actions = Children.toArray([<button key="a">See <span className="text-text-secondary-light">{n}</span></button>]); return <div className="text-brand-strong">{actions}</div> } // flag
// Codex's review of d3f1522: React's other child-preserving helper, Children.only, returns what it is given (P332, the
// review's own form); by its React. name rendered inline; a count control through it; and a look-alike over a word.
export function P332({ n }: { n: number }) { const child = Children.only(<span>{n}</span>); return <div className="text-brand-strong">{child}</div> } // flag
export function P333() { return <span className="text-brand-strong">{React.Children.only(<b>Step 2</b>)}</span> } // flag
export function P334() { const child = Children.only(<b>Revenue</b>); return <div className="text-brand-strong">{child}</div> } // clean
export function P335({ n }: { n: number }) { const action = Children.only(<button>See <span className="text-text-secondary-light">{n}</span></button>); return <div className="text-brand-strong">{action}</div> } // flag
