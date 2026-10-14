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
import * as React from 'react'
import * as R from 'react'
import { Children, cloneElement, cloneElement as clone, createElement, isValidElement, type ReactElement, type ReactNode, useCallback, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { Badge, Button, buttonVariants, countControlClass, countControlClass as tally, type BadgeVariant } from '@/components/ui'
import { cx } from '@/components/ui/cx'
import Link from 'next/link'
import { ArrowRightIcon } from '@/lib/icons'
import type { FeedbackRecord } from '@/features/admin/api/admin-api'
import type { AnalysisInflection, AnalysisPoint } from '@/features/analysis/api/analysis-api'
import type { CalendarRangeResult } from '@/features/calendar/api/calendar-api'
import type { Company } from '@/features/companies/api/companies-api'
import type { WhatChanged, WhatChangedItem } from '@/features/dashboard/api/dashboard-api'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'
import type { Filing } from '@/features/filings/api/filings-api'
import type { ExampleEvidence } from '@/lib/serverApi'
import type { RenderedBlock, RenderedMetricRow } from '@/features/summaries/api/summaries-api'
import type { MetricItem, NormalizedFact, PerAdsValue, RiskFactor } from '@/types/summary'
import { maybeOnly, quietLinkClass, typedOnly } from './brandRule2Kit'

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
// A control that turns sage only under the pointer (the count control's recipe), with its count in a span.
export function P94({ n }: { n: number }) { return <a href="/x" className={countControlClass('link')}>See <span className="text-text-tertiary-light">{n}</span></a> } // clean
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
// Codex's review of f5526d3: JSX that Children.toArray normalizes before it renders under a sage parent, which rule 2
// did not follow. The family: React's child utilities, named through the checker (Children.toArray, whose members a
// child that is no array joins, Children.only, Children.map and forEach, and cloneElement); a component that reaches
// its children through them, a binding, a helper or a useMemo, or renders them inside a control, which makes it one
// where it is used; an array or a list rendered whole; and an array or an object the file fills after it is made.
export function P319({ n }: { n: number }) { const kids = Children.toArray([<span key="a">{n}</span>]); return <span className="text-brand-strong">{kids}</span> } // flag
export function P320() { return <span className="text-brand-strong">{Children.toArray([<span key="a">Step 2</span>])}</span> } // flag
export function P321({ n }: { n: number }) { return <span className="text-brand-strong">{React.Children.toArray(<span>{n}</span>)}</span> } // flag
export function P322({ n }: { n: number }) { return <span className="text-brand-strong">{Children.only(<span>{n}</span>)}</span> } // flag
export function P323({ n }: { n: number }) { return <span className="text-brand-strong">{Children.map([<span key="a">{n}</span>], (c) => <b>{c}</b>)}</span> } // flag
export function P324({ n }: { n: number }) { const kids = Children.toArray([<span key="a">{n}</span>]); return <span className="text-brand-strong">{kids[0]}</span> } // flag
export function P325({ n }: { n: number }) { const kids = Children.toArray([<button key="a">See <span className="text-text-secondary-light">{n}</span></button>]); return <div className="text-brand-strong">{kids}</div> } // flag
export function P326({ n }: { n: number }) { const out: ReactNode[] = []; Children.forEach([<b key="a">{n}</b>], (c) => { out.push(c) }); return <div className="text-brand-strong">{out}</div> } // flag
// The review of 439e2762: a utility the checker types as React's however the call reaches it (an aliased import, a
// destructured method), and the child Children.map hands its callback when it is given one that is no array.
export function P384({ n }: { n: number }) { const el = <span>{n}</span>; return <span className="text-brand-strong">{clone(el)}</span> } // flag
export function P385({ n }: { n: number }) { const { toArray } = Children; return <span className="text-brand-strong">{toArray([<span key="a">{n}</span>])}</span> } // flag
export function P386({ n }: { n: number }) { return <span className="text-brand-strong">{Children.map(n, (c: ReactNode) => <b>{c}</b>)}</span> } // flag
// Look-alikes: a member in an ink of its own; words; a Children that is not React's (a prop of that name, whose
// toArray the scan cannot read); a portal, whose content renders under the document's body, not the sage parent.
export function P327({ n }: { n: number }) { const kids = Children.toArray([<span key="a" className="text-text-secondary-light">{n}</span>]); return <span className="text-brand-strong">{kids}</span> } // clean
export function P328() { const kids = Children.toArray(['Revenue', <b key="b">Margin</b>]); return <span className="text-brand-strong">{kids}</span> } // clean
export function P329({ Children }: { Children: { toArray: (c: ReactNode) => string[] } }) { return <span className="text-brand-strong">{Children.toArray(<b>Step 2</b>)}</span> } // clean
export function P330({ n }: { n: number }) { return <div className="text-brand-strong">{createPortal(<span>{n}</span>, document.body)}</div> } // clean
// cloneElement renders the element it clones, or the children it hands the clone (from its third argument, or its
// props) in that element's place; one whose props give it a className of its own is not read as the element it
// clones (P372, P390), and a clone of an element the scan cannot read renders them in the ink it inherits (P389).
// createElement renders the children it hands the element it makes in the ink it inherits (P391).
export function P331({ n }: { n: number }) { const el = <span>{n}</span>; return <span className="text-brand-strong">{cloneElement(el)}</span> } // flag
export function P332() { return <span className="text-brand-strong">{cloneElement(<span />, undefined, 'Step 2')}</span> } // flag
export function P333({ n }: { n: number }) { return <span className="text-brand-strong">{cloneElement(<span className="text-text-secondary-light" />, undefined, n)}</span> } // clean
export function P334({ n }: { n: number }) { return <span className="text-brand-strong">{cloneElement(<span>{n}</span>, undefined, 'Revenue')}</span> } // clean
export function P372({ n }: { n: number }) { return <span className="text-brand-strong">{cloneElement(<span>{n}</span>, { className: 'text-text-secondary-light' })}</span> } // clean
export function P387() { return <span className="text-brand-strong">{cloneElement(<span />, { children: 'Step 2' })}</span> } // flag
export function P388({ n }: { n: number }) { return <span className="text-brand-strong">{cloneElement(<span>{n}</span>, { children: 'Revenue' })}</span> } // clean
export function P389({ n, icon }: { n: number; icon: ReactElement }) { return <span className="text-brand-strong">{cloneElement(icon, undefined, n)}</span> } // flag
export function P390({ n }: { n: number }) { return <span className="text-brand-strong">{cloneElement(<span />, { className: 'text-text-secondary-light' }, n)}</span> } // clean
export function P391() { return <span className="text-brand-strong">{createElement('span', null, 'Step 2')}</span> } // flag
// A clone handed children of its own, by its props or its arguments, renders them, not the element's own text.
export function P421() { return <span className="text-brand-strong">{cloneElement(<span>Step 2</span>, { children: 'Revenue' })}</span> } // clean
export function P422() { return <span className="text-brand-strong">{cloneElement(<span>Step 2</span>, undefined, 'Revenue')}</span> } // clean
// The review of 3629f7f3: children handed by a shorthand in a clone's props (a const's, and a component's own), and a
// list of them spread into a clone's arguments.
export function P424() { const children = 'Step 2'; return <span className="text-brand-strong">{cloneElement(<span />, { children })}</span> } // flag
function Sage425({ children }: { children: ReactNode }) { return <span className="text-brand-strong">{cloneElement(<b />, { children })}</span> }
export function P425({ n }: { n: number }) { return <Sage425>{n}</Sage425> } // flag
export function P426() { const kids = ['Q1']; return <span className="text-brand-strong">{cloneElement(<span />, undefined, ...kids)}</span> } // flag
// A component's children reached through React's utilities, a binding, a helper or a useMemo, rendered in sage.
function Sage335({ children }: { children: ReactNode }) { return <div>{Children.toArray(children).map((c, i) => <span key={i} className="text-brand-strong">{c}</span>)}</div> }
export function P335({ n }: { n: number }) { return <Sage335>{n}</Sage335> } // flag
function Sage336({ children }: { children: ReactNode }) { const items = Children.toArray(children); return <div className="text-brand-strong">{items}</div> }
export function P336({ n }: { n: number }) { return <Sage336>{n}</Sage336> } // flag
function Sage337({ children }: { children: ReactElement }) { return <span className="text-brand-strong">{Children.only(children)}</span> }
export function P337({ n }: { n: number }) { return <Sage337><span>{n}</span></Sage337> } // flag
function Sage338({ children }: { children: ReactNode }) { const items = children; return <div className="text-brand-strong">{items}</div> }
export function P338({ n }: { n: number }) { return <Sage338>{n}</Sage338> } // flag
function Sage339({ children }: { children: ReactNode }) { const [first] = Children.toArray(children); return <div className="text-brand-strong">{first}</div> }
export function P339({ n }: { n: number }) { return <Sage339>{n}</Sage339> } // flag
function Sage340({ children }: { children: ReactNode }) { const items = useMemo(() => Children.toArray(children), [children]); return <div className="text-brand-strong">{items}</div> }
export function P340({ n }: { n: number }) { return <Sage340>{n}</Sage340> } // flag
function Sage341(props: { children: ReactNode }) { const { children: kids } = props; return <span className="text-brand-strong">{kids}</span> }
export function P341({ n }: { n: number }) { return <Sage341>{n}</Sage341> } // flag
function Sage342({ children }: { children: ReactElement }) { return <span className="text-brand-strong">{cloneElement(children)}</span> }
export function P342({ n }: { n: number }) { return <Sage342><span>{n}</span></Sage342> } // flag
// The review of 439e2762: the children through Children.map held in a const (the canonical isValidElement idiom), a
// list's map held, forEach filling an array, a helper's parameter, an index into a list of them, a list call, and an
// array of children mapped as one; f5526d3's walk lost each.
function Sage392({ children }: { children: ReactNode }) { const items = Children.map(children, (c) => (isValidElement(c) ? cloneElement(c) : c)); return <div className="text-brand-strong">{items}</div> }
export function P392({ n }: { n: number }) { return <Sage392>{n}</Sage392> } // flag
function Sage393({ children }: { children: ReactNode }) { const items = Children.toArray(children).map((c) => c); return <div className="text-brand-strong">{items}</div> }
export function P393({ n }: { n: number }) { return <Sage393>{n}</Sage393> } // flag
function Sage394({ children }: { children: ReactNode }) { const out: ReactNode[] = []; Children.forEach(children, (c) => { out.push(<li key="a">{c}</li>) }); return <ul className="text-brand-strong">{out}</ul> }
export function P394({ n }: { n: number }) { return <Sage394>{n}</Sage394> } // flag
function Sage395({ children }: { children: ReactNode }) { const wrap = (c: ReactNode) => <span className="text-brand-strong">{c}</span>; return <div>{wrap(children)}</div> }
export function P395({ n }: { n: number }) { return <Sage395>{n}</Sage395> } // flag
function Sage396({ children }: { children: ReactNode }) { const items = Children.toArray(children); return <div className="text-brand-strong">{items[0]}</div> }
export function P396({ n }: { n: number }) { return <Sage396>{n}</Sage396> } // flag
function Sage397({ children }: { children: ReactNode }) { return <div className="text-brand-strong">{Children.toArray(children).slice(0, 2)}</div> }
export function P397({ n }: { n: number }) { return <Sage397>{n}</Sage397> } // flag
function Sage398({ children }: { children: ReactNode[] }) { return <div>{children.map((c, i) => <span key={i} className="text-brand-strong">{c}</span>)}</div> }
export function P398({ n }: { n: number }) { return <Sage398>{n}{' filings'}</Sage398> } // flag
// A slot chosen by a key the scan cannot read may be the children, and children a component defaults render where
// its children do, in the ink it inherits (f5526d3 stopped at the children's name, past the default).
function Slot417({ slot, ...props }: { slot: 'children' | 'label'; children: ReactNode; label: ReactNode }) { return <div className="text-brand-strong">{props[slot]}</div> }
export function P417({ n }: { n: number }) { return <Slot417 slot="children" label="Revenue">{n}</Slot417> } // flag
function Steps418({ children = 'Step 2' }: { children?: ReactNode }) { return <>{children}</> }
export function P418() { return <span className="text-brand-strong"><Steps418 /></span> } // flag
// A fallback rendered beside the children is read as well as them; and a compound component that renders each
// child's own children (a tab's content) renders the children it is given.
function Pick419({ open, children }: { open: boolean; children: ReactNode }) { return <>{open ? children : <b>Step 2</b>}</> }
export function P419() { return <span className="text-brand-strong"><Pick419 open={false}>Revenue</Pick419></span> } // flag
function Tab420({ children }: { label: string; children: ReactNode }) { return <>{children}</> }
function Tabs420({ children }: { children: ReactNode }) { return <div className="text-brand-strong">{Children.toArray(children).map((tab) => (isValidElement<{ children: ReactNode }>(tab) ? tab.props.children : null))}</div> }
export function P420({ n }: { n: number }) { return <Tabs420><Tab420 label="Revenue">{n}</Tab420></Tabs420> } // flag
// Children a component joins as text render where the join does (the review of 3629f7f3).
function Join427({ children }: { children: string[] }) { return <span className="text-brand-strong">{children.join(', ')}</span> }
export function P427() { return <Join427>{['Q1']}</Join427> } // flag
// Look-alikes: two of those paths in an ink of the component's own, inside a sage parent (f5526d3 read both as
// passing the parent's sage through).
function Own343({ children }: { children: ReactNode }) { return <div>{Children.toArray(children).map((c, i) => <span key={i} className="text-text-secondary-light">{c}</span>)}</div> }
export function P343({ n }: { n: number }) { return <div className="text-brand-strong"><Own343>{n}</Own343></div> } // clean
function Own344({ children }: { children: ReactNode }) { const items = useMemo(() => Children.toArray(children), [children]); return <div className="text-text-secondary-light">{items}</div> }
export function P344({ n }: { n: number }) { return <div className="text-brand-strong"><Own344>{n}</Own344></div> } // clean
// A component whose path to its children the scan cannot read (a clone given a className) passes the ink it inherits
// through, so it fails closed on the number its children carry inside a sage parent.
function Clone399({ children }: { children: ReactElement }) { return cloneElement(children, { className: 'text-text-secondary-light' }) }
export function P399({ n }: { n: number }) { return <span className="text-brand-strong"><Clone399><span>{n}</span></Clone399></span> } // flag
// A component that renders its children inside a control is a control where it is used, its children the label:
// a count they hold in an ink of their own while it rests in sage breaks the count control. And a control a
// component renders in the ink it inherits, reached through an array, a clone's children or Children.only.
function Act345({ children }: { children: ReactNode }) { return <button type="button">{children}</button> }
export function P345({ n }: { n: number }) { return <div className="text-brand-strong"><Act345>See <span className="text-text-secondary-light">{n}</span></Act345></div> } // flag
function Nav346({ children }: { children: ReactNode }) { return <nav>{Children.map(children, (c) => <a href="/x">{c}</a>)}</nav> }
export function P346({ n }: { n: number }) { return <div className="text-brand-strong"><Nav346><span className="text-text-secondary-light">{n}</span></Nav346></div> } // flag
function Sage347({ children }: { children: ReactNode }) { return <button type="button" className="text-brand-strong">{children}</button> }
export function P347({ n }: { n: number }) { return <Sage347>See <span className="text-text-secondary-light">{n}</span></Sage347> } // flag
function Outer348({ children }: { children: ReactNode }) { return <Act345>{children}</Act345> }
export function P348({ n }: { n: number }) { return <div className="text-brand-strong"><Outer348>See <span className="text-text-secondary-light">{n}</span></Outer348></div> } // flag
function Acts373({ n }: { n: number }) { return <>{[<button key="a">See <span className="text-text-secondary-light">{n}</span></button>]}</> }
export function P373({ n }: { n: number }) { return <div className="text-brand-strong"><Acts373 n={n} /></div> } // flag
function Acts374({ n }: { n: number }) { return <>{cloneElement(<div />, undefined, <button>See <span className="text-text-secondary-light">{n}</span></button>)}</> }
export function P374({ n }: { n: number }) { return <div className="text-brand-strong"><Acts374 n={n} /></div> } // flag
function Acts375({ n }: { n: number }) { return <>{Children.only(<button>See <span className="text-text-secondary-light">{n}</span></button>)}</> }
export function P375({ n }: { n: number }) { return <div className="text-brand-strong"><Acts375 n={n} /></div> } // flag
// The children reach the control through Children.map held in a const, or a helper handed them.
function Acts400({ children }: { children: ReactNode }) { const items = Children.map(children, (c) => <button type="button">{c}</button>); return <div>{items}</div> }
export function P400({ n }: { n: number }) { return <div className="text-brand-strong"><Acts400><span className="text-text-secondary-light">{n}</span></Acts400></div> } // flag
function Acts401({ children }: { children: ReactNode }) { const renderButton = (c: ReactNode) => <button type="button">{c}</button>; return <div>{renderButton(children)}</div> }
export function P401({ n }: { n: number }) { return <div className="text-brand-strong"><Acts401>See <span className="text-text-secondary-light">{n}</span></Acts401></div> } // flag
// Look-alikes: the component's control rests in an ink of its own; the children render beside the control, not in
// it; the parent turns sage only under the pointer.
function Own349({ children }: { children: ReactNode }) { return <button type="button" className="text-text-secondary-light">{children}</button> }
export function P349({ n }: { n: number }) { return <div className="text-brand-strong"><Own349>See <span className="text-text-tertiary-light">{n}</span></Own349></div> } // clean
function Tip350({ children }: { children: ReactNode }) { return <span><button type="button">i</button><span role="tooltip">{children}</span></span> }
export function P350({ n }: { n: number }) { return <div className="text-brand-strong"><Tip350>Coverage <span className="text-text-secondary-light">{n}</span></Tip350></div> } // clean
export function P351({ n }: { n: number }) { return <div className="hover:text-brand-strong"><Act345>See <span className="text-text-secondary-light">{n}</span></Act345></div> } // clean
// A row's field named children, rendered inside a link, is no child of the component's: its children render beside it.
function Menu402({ items, children }: { items: { href: string; children: string }[]; children: ReactNode }) { return <nav>{children}{items.map((i) => <a key={i.href} href={i.href}>{i.children}</a>)}</nav> }
export function P402({ n }: { n: number }) { return <div className="text-brand-strong"><Menu402 items={[]}>Plan <span className="text-text-secondary-light">{n}</span></Menu402></div> } // clean
// An array, or a list a call keeps, rendered whole renders every member: a value an element in it carries, a
// member's digits, and what a join joins.
const QUARTERS_353 = ['Q1', 'Q2']
export function P352({ n }: { n: number }) { const items = [<b key="a">{n}</b>]; return <div className="text-brand-strong">{items}</div> } // flag
export function P353() { return <span className="text-brand-strong">{QUARTERS_353.filter(Boolean)}</span> } // flag
export function P354() { return <span className="text-brand-strong">{Object.values({ first: 'Q1' })}</span> } // flag
export function P355() { return <span className="text-brand-strong">{[...new Set(QUARTERS_353)]}</span> } // flag
export function P356({ n }: { n: number }) { const items = [<b key="a">{n}</b>]; return <span className="text-brand-strong">{items.find(Boolean)}</span> } // flag
export function P357({ n }: { n: number }) { return <span className="text-brand-strong">{[n, 'filings'].join(' ')}</span> } // flag
// A component that renders a list in the ink it inherits, inside a sage parent; concat, which keeps its receiver's
// members and adds its arguments'.
function List403() { return <>{QUARTERS_353.slice(0, 1)}</> }
export function P403() { return <span className="text-brand-strong"><List403 /></span> } // flag
export function P404() { const labels = ['Revenue']; return <span className="text-brand-strong">{labels.concat('Q1')}</span> } // flag
// Look-alikes: a member in an ink of its own; words.
export function P358({ n }: { n: number }) { const items = [<b key="a" className="text-text-secondary-light">{n}</b>]; return <div className="text-brand-strong">{items}</div> } // clean
export function P359() { return <span className="text-brand-strong">{['Revenue', 'Margin'].slice(0, 1)}</span> } // clean
export function P405() { return <span className="text-brand-strong">{['Revenue'].concat(['Margin'])}</span> } // clean
// A string's concat keeps the text it is called on.
export function P423() { const year = 'FY2025'; return <span className="text-brand-strong">{year.concat(' revenue')}</span> } // flag
// d3f1522c's forms for the same review, kept: a callback bound through Children.toArray, Children.map and forEach over
// a held list, React.Children read whole, concat's members and a value it is given, and flat, with two look-alikes;
// then a field read off a member flat opens, and a flat list rendered whole.
export function P439() { return <p>{Children.toArray(LABELS_161).map((l) => <span key={String(l)} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P440() { return <span className="text-brand-strong">{React.Children.toArray(LABELS_161)}</span> } // flag
export function P441() { return <p>{Children.map(LABELS_161, (l) => <span key={String(l)} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P442() { const out: ReactNode[] = []; Children.forEach(LABELS_161, (l) => { out.push(<span key={String(l)} className="text-brand-strong">{l}</span>) }); return <p>{out}</p> } // flag
export function P443() { return <p>{WORDS_161.concat(LABELS_161).map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P444() { return <p>{WORDS_161.concat('Q3').map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P445() { return <p>{[WORDS_161, LABELS_161].flat().map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P446() { return <p>{WORDS_161.concat(['Margin']).map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // clean
export function P447() { return <p>{[WORDS_161, ['Margin']].flat().map((l) => <span key={l} className="text-brand-strong">{l}</span>)}</p> } // clean
export function P448() { const rows = [[{ label: 'Q1' }]]; return <p>{rows.flat().map((r) => <span key={r.label} className="text-brand-strong">{r.label}</span>)}</p> } // flag
export function P449() { return <span className="text-brand-strong">{[WORDS_161, LABELS_161].flat()}</span> } // flag
// The rest of the array methods that keep their receiver's members, listed from the language: toSpliced's inserts,
// the value `with` and `fill` give, splice's and copyWithin's return; look-alikes whose index or range is no member;
// and fill as a put, its value and never its range.
export function P450() { return <span className="text-brand-strong">{WORDS_161.toSpliced(1, 0, 'Q3')}</span> } // flag
export function P451() { return <span className="text-brand-strong">{WORDS_161.with(0, 'Q3')}</span> } // flag
export function P452() { return <span className="text-brand-strong">{new Array<string>(1).fill('Q3')}</span> } // flag
export function P453() { return <span className="text-brand-strong">{WORDS_161.with(0, 'Margin')}</span> } // clean
export function P454() { return <span className="text-brand-strong">{[...WORDS_161].fill('Margin', 0, 1)}</span> } // clean
export function P455() { const removed = [...LABELS_161].splice(0, 1); return <span className="text-brand-strong">{removed}</span> } // flag
export function P456() { return <span className="text-brand-strong">{[...LABELS_161].copyWithin(0, 0)}</span> } // flag
export function P457() { const slots = new Array<string>(2); slots.fill('Q3'); return <span className="text-brand-strong">{slots}</span> } // flag
export function P458() { const slots = ['Revenue']; slots.fill('Margin', 0, 1); return <span className="text-brand-strong">{slots}</span> } // clean
// The array methods that return one of their receiver's members: pop and shift, read as any member.
export function P459() { const out = [...LABELS_161]; return <span className="text-brand-strong">{out.pop()}</span> } // flag
export function P460() { return <span className="text-brand-strong">{[...LABELS_161].shift()}</span> } // flag
// 1dd291dd's forms for Codex's review of d3f1522c: Children.only, held (P461, the review's own form), by its React.
// name rendered inline, a count control through it, and a look-alike over a word.
export function P461({ n }: { n: number }) { const child = Children.only(<span>{n}</span>); return <div className="text-brand-strong">{child}</div> } // flag
export function P462() { return <span className="text-brand-strong">{React.Children.only(<b>Step 2</b>)}</span> } // flag
export function P463() { const child = Children.only(<b>Revenue</b>); return <div className="text-brand-strong">{child}</div> } // clean
export function P464({ n }: { n: number }) { const action = Children.only(<button>See <span className="text-text-secondary-light">{n}</span></button>); return <div className="text-brand-strong">{action}</div> } // flag
// Codex's review of 1dd291dd: Children reached through a name held for it, and a helper destructured from it (P385's
// form for only); the checker names both.
export function P465({ n }: { n: number }) { const Kids = Children; return <span className="text-brand-strong">{Kids.toArray(<span>{n}</span>)}</span> } // flag
export function P466({ n }: { n: number }) { const { only } = Children; return <span className="text-brand-strong">{only(<span>{n}</span>)}</span> } // flag
// c00788f's forms for Codex's review of 1dd291d (its P336 to P345): React's Children helpers reached by another
// spelling, an alias (P467, the review's own form) and a helper destructured from it (P468), with a same-file object
// that shares the name, which is not React's (P469). The family: an alias, a destructured helper (renamed too), a
// helper held in a const, a namespace import, the callbacks the aliased map and forEach bind, a count control through
// an alias, and a look-alike over a word.
export function P467({ n }: { n: number }) { const Kids = Children; const kids = Kids.toArray([<span key="n">{n}</span>]); return <div className="text-brand-strong">{kids}</div> } // flag
export function P468({ n }: { n: number }) { const { only } = Children; const child = only(<span>{n}</span>); return <div className="text-brand-strong">{child}</div> } // flag
export function P469({ n }: { n: number }) { const Children = { only: (child: ReactNode) => (child ? <b>Revenue</b> : null) }; return <div className="text-brand-strong">{Children.only(<span>{n}</span>)}</div> } // clean
export function P470() { const { toArray: list } = React.Children; return <span className="text-brand-strong">{list(LABELS_161)}</span> } // flag
export function P471() { const one = Children.only; return <span className="text-brand-strong">{one(<b>Step 2</b>)}</span> } // flag
export function P472() { return <span className="text-brand-strong">{R.Children.toArray(LABELS_161)}</span> } // flag
export function P473() { const Kids = Children; return <p>{Kids.map(LABELS_161, (l) => <span key={String(l)} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P474() { const { forEach } = Children; const out: ReactNode[] = []; forEach(LABELS_161, (l) => { out.push(<span key={String(l)} className="text-brand-strong">{l}</span>) }); return <p>{out}</p> } // flag
export function P475({ n }: { n: number }) { const Kids = Children; const action = Kids.only(<button>See <span className="text-text-secondary-light">{n}</span></button>); return <div className="text-brand-strong">{action}</div> } // flag
export function P476() { const { only } = Children; const child = only(<b>Revenue</b>); return <div className="text-brand-strong">{child}</div> } // clean
// 4e44658's forms for Codex's review of c00788f (its P346 to P350): Children destructured from React itself (P477, the
// review's own form), a nested pattern, a const holding the namespace, the callbacks an alias binds, and a look-alike
// destructured from a same-file object of the same shape.
export function P477({ n }: { n: number }) { const { Children: Kids } = React; const child = Kids.only(<span>{n}</span>); return <div className="text-brand-strong">{child}</div> } // flag
export function P478() { const { Children: { toArray } } = React; return <span className="text-brand-strong">{toArray(LABELS_161)}</span> } // flag
export function P479({ n }: { n: number }) { const Lib = R; const kids = Lib.Children.toArray([<span key="n">{n}</span>]); return <div className="text-brand-strong">{kids}</div> } // flag
export function P480({ n }: { n: number }) { const { Children: Kids } = { Children: { only: (child: ReactNode) => (child ? <b>Revenue</b> : null) } }; return <div className="text-brand-strong">{Kids.only(<span>{n}</span>)}</div> } // clean
export function P481() { const { Children: Kids } = React; return <p>{Kids.map(LABELS_161, (l) => <span key={String(l)} className="text-brand-strong">{l}</span>)}</p> } // flag
// Codex's review of 4e44658: React's Children reached through a key, `React['Children']` held (P482, the review's
// own form), a utility called through keys, destructured from it, a namespace's, the callbacks its map binds, and a
// look-alike read through a key from a same-file object of the same shape.
export function P482({ n }: { n: number }) { const Kids = React['Children']; return <div className="text-brand-strong">{Kids.only(<span>{n}</span>)}</div> } // flag
export function P483({ n }: { n: number }) { return <div className="text-brand-strong">{React['Children']['only'](<span>{n}</span>)}</div> } // flag
export function P484({ n }: { n: number }) { const { only } = React['Children']; return <div className="text-brand-strong">{only(<span>{n}</span>)}</div> } // flag
export function P485() { return <span className="text-brand-strong">{R['Children'].toArray(LABELS_161)}</span> } // flag
export function P486() { const Kids = React['Children']; return <p>{Kids.map(LABELS_161, (l) => <span key={String(l)} className="text-brand-strong">{l}</span>)}</p> } // flag
export function P487({ n }: { n: number }) { const Kids = { Children: { only: (child: ReactNode) => (child ? <b>Revenue</b> : null) } }['Children']; return <div className="text-brand-strong">{Kids.only(<span>{n}</span>)}</div> } // clean
// React's child utilities however else a call reaches them: every call's callee is asked of the checker, so a utility
// held in an object (P488), returned by a function (P489), handed as a parameter (P490), bound (P491), called through
// a key written or held (P492, P493), or held under a name of its own (P494, and cloneElement, P495) is React's, while
// a same-file object of the same shape (P496) and a same-file method of the same name called through a key (P497)
// are not.
export function P488({ n }: { n: number }) { const lib = { Children }; return <div className="text-brand-strong">{lib.Children.only(<span>{n}</span>)}</div> } // flag
export function P489({ n }: { n: number }) { const kids = () => Children; return <div className="text-brand-strong">{kids().only(<span>{n}</span>)}</div> } // flag
export function P490({ n }: { n: number }) { const run = (C: typeof Children) => C.only(<span>{n}</span>); return <div className="text-brand-strong">{run(Children)}</div> } // flag
export function P491({ n }: { n: number }) { const one = Children.only.bind(Children); return <div className="text-brand-strong">{one(<span>{n}</span>)}</div> } // flag
export function P492({ n }: { n: number }) { return <div className="text-brand-strong">{Children['only'](<span>{n}</span>)}</div> } // flag
export function P493({ n }: { n: number }) { const key = 'only'; return <div className="text-brand-strong">{Children[key](<span>{n}</span>)}</div> } // flag
export function P494({ n }: { n: number }) { const helpers = { first: Children.only }; return <div className="text-brand-strong">{helpers.first(<span>{n}</span>)}</div> } // flag
export function P495({ n }: { n: number }) { const helpers = { copy: cloneElement }; return <div className="text-brand-strong">{helpers.copy(<span>{n}</span>)}</div> } // flag
export function P496({ n }: { n: number }) { const lib = { Children: { only: (child: ReactNode) => (child ? <b>Revenue</b> : null) } }; return <div className="text-brand-strong">{lib.Children.only(<span>{n}</span>)}</div> } // clean
export function P497({ n }: { n: number }) { const table = { only(child: ReactNode) { return child ? <b>Revenue</b> : null } }; return <div className="text-brand-strong">{table['only'](<span>{n}</span>)}</div> } // clean
// A method the scan names by what follows the dot (an array's, Object's, a push), called through a key instead: the
// call is read as one the scan does not know.
export function P498() { return <span className="text-brand-strong">{LABELS_161['slice'](0)}</span> } // gap
// A callee that may be undefined: the checker's type of the callee is asked without its undefined, so an optional
// call reaches the utility (P499, P500); and a same-file function typed as React's utility is read as it, which fails
// closed (P501).
export function P499({ n }: { n: number }) { const one = n > 0 ? Children.only : undefined; return <div className="text-brand-strong">{one?.(<span>{n}</span>)}</div> } // flag
export function P500({ n }: { n: number }) { const lib: { only?: typeof Children.only } = { only: Children.only }; return <div className="text-brand-strong">{lib.only?.(<span>{n}</span>)}</div> } // flag
export function P501({ n }: { n: number }) { const mine: typeof Children.only = ((child: ReactNode) => (child ? <b>Revenue</b> : null)) as never; return <div className="text-brand-strong">{mine(<span>{n}</span>)}</div> } // flag
// A React utility called through call, apply or Reflect.apply: what is called is lib's, so the children it is handed
// are unread.
export function P502({ n }: { n: number }) { return <div className="text-brand-strong">{Children.only.call(null, <span>{n}</span>)}</div> } // gap
export function P503({ n }: { n: number }) { return <div className="text-brand-strong">{Children.only.apply(null, [<span key="n">{n}</span>])}</div> } // gap
export function P504({ n }: { n: number }) { return <div className="text-brand-strong">{Reflect.apply(Children.only, null, [<span key="n">{n}</span>])}</div> } // gap
// What the file puts in an array or an object after making it: a push, a splice's inserts, an index or a field it
// sets, through a field chain or a key the scan cannot read, a className built that way, a count control, an
// index into an array a push filled, which may land on any member, and a conditional put there, read as code.
export function P360({ n }: { n: number }) { const out: ReactNode[] = []; out.push(<b key="a">{n}</b>); return <div className="text-brand-strong">{out}</div> } // flag
export function P361() { const out: string[] = []; out.push('Q1'); return <div className="text-brand-strong">{out}</div> } // flag
export function P362() { const out = ['Revenue']; out.splice(0, 0, 'Q1'); return <div className="text-brand-strong">{out}</div> } // flag
export function P363() { const out: string[] = []; out[0] = 'Q1'; return <div className="text-brand-strong">{out}</div> } // flag
export function P364() { const row: { label?: string } = {}; row.label = 'Q1'; return <div className="text-brand-strong">{row.label}</div> } // flag
export function P365() { const o = { items: [] as string[] }; o.items.push('Q1'); return <span className="text-brand-strong">{o.items}</span> } // flag
export function P366({ k }: { k: string }) { const groups: Record<string, string[]> = {}; groups[k] = []; groups[k].push('Q1'); return <span className="text-brand-strong">{Object.values(groups)}</span> } // flag
export function P367({ n }: { n: number }) { const cls = ['font-semibold']; cls.push('text-brand-strong'); return <span className={cls.join(' ')}>{n}</span> } // flag
export function P368({ n }: { n: number }) { const actions: ReactNode[] = []; actions.push(<button key="a">See <span className="text-text-secondary-light">{n}</span></button>); return <div className="text-brand-strong">{actions}</div> } // flag
export function P376() { const out = ['Revenue']; out.push('Q1'); return <span className="text-brand-strong">{out[1]}</span> } // flag
export function P380({ on }: { on: boolean }) { const out: string[] = []; out.push(on ? 'Q1' : 'Revenue'); return <div className="text-brand-strong">{out}</div> } // flag
export function P381({ on }: { on: boolean }) { const row: { label?: string } = {}; row.label = on ? 'Q1' : 'Revenue'; return <div className="text-brand-strong">{row.label}</div> } // flag
// The review of 439e2762: a className lookup filled by a key the scan cannot read (which crashed the walk), a field or
// an index a compound assignment sets, the fields Object.assign copies, a Set's add, and an unshift.
export function P406({ n, k }: { n: number; k: string }) { const cls: Record<string, string> = {}; cls[k] = 'text-brand-strong'; return <span className={cls[k]}>{n}</span> } // flag
export function P407() { const row: { label?: string } = {}; row.label ??= 'Q1'; return <div className="text-brand-strong">{row.label}</div> } // flag
export function P408() { const out: string[] = []; out[0] ||= 'Q1'; return <div className="text-brand-strong">{out}</div> } // flag
export function P409() { const row = { label: 'Revenue' }; row.label += ' Q1'; return <div className="text-brand-strong">{row.label}</div> } // flag
export function P410() { const row: { label?: string } = {}; Object.assign(row, { label: 'Q1' }); return <div className="text-brand-strong">{row.label}</div> } // flag
export function P411() { const seen = new Set<string>(); seen.add('Q1'); return <span className="text-brand-strong">{[...seen]}</span> } // flag
export function P412() { const out = ['Revenue']; out.unshift('Q1'); return <div className="text-brand-strong">{out}</div> } // flag
// The review of 3629f7f3: the fields Object.assign copies from a spread of sources, written there or held, and the
// object it returns; a field set through a cast; a conditional pushed, read through an index.
export function P428() { const row: { label?: string } = {}; Object.assign(row, ...[{ label: 'Q1' }]); return <div className="text-brand-strong">{row.label}</div> } // flag
export function P429() { const sources = [{ label: 'Q1' }]; const row: { label?: string } = {}; Object.assign(row, ...sources); return <div className="text-brand-strong">{row.label}</div> } // flag
export function P430() { const row = Object.assign({}, { label: 'Q1' }); return <div className="text-brand-strong">{row.label}</div> } // flag
export function P431() { const row = Object.assign({}, ...[{ label: 'Q1' }]); return <div className="text-brand-strong">{row.label}</div> } // flag
export function P432() { const row: { label?: string } = {}; (row as { label?: string }).label = 'Q1'; return <div className="text-brand-strong">{row.label}</div> } // flag
export function P433({ on }: { on: boolean }) { const out: string[] = []; out.push(on ? 'Q1' : 'Revenue'); return <div className="text-brand-strong">{out[0]}</div> } // flag
// Look-alikes: words pushed; a splice that only removes; words set on a field.
export function P369() { const out: string[] = []; out.push('Revenue'); return <div className="text-brand-strong">{out}</div> } // clean
export function P370() { const out = ['Revenue', 'Margin']; out.splice(0, 1); return <div className="text-brand-strong">{out}</div> } // clean
export function P371() { const row: { label?: string } = {}; row.label = 'Revenue'; return <div className="text-brand-strong">{row.label}</div> } // clean
export function P413() { const row: { label?: string } = {}; Object.assign(row, { label: 'Revenue' }); return <div className="text-brand-strong">{row.label}</div> } // clean
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
// A clone's or a created element's own ink, out of reach: any className cloneElement's or createElement's props give
// it (the Slot pattern included; one that sets no ink leaves the number in the parent's sage), which the scan does not
// read, the children handed to a clone of an element that sets sage, which renders them in its ink where no sage
// parent's check reaches, and a created component's own ink (P434).
export function P377({ n }: { n: number }) { return <span>{cloneElement(<span>{n}</span>, { className: 'text-brand-strong' })}</span> } // gap
export function P378({ n }: { n: number }) { return <span>{cloneElement(<span className="text-brand-strong" />, undefined, n)}</span> } // gap
export function P379({ n }: { n: number }) { return <Slot379><span>{n}</span></Slot379> } function Slot379({ children }: { children: ReactElement }) { return cloneElement(children, { className: 'text-brand-strong' }) } // gap
export function P414({ n }: { n: number }) { return <span className="text-brand-strong">{cloneElement(<span>{n}</span>, { className: 'font-semibold' })}</span> } // gap
export function P415({ n }: { n: number }) { return <span>{createElement('span', { className: 'text-brand-strong' }, n)}</span> } // gap
function Sage434({ children }: { children: ReactNode }) { return <span className="text-brand-strong">{children}</span> }
export function P434({ n }: { n: number }) { return <div>{createElement(Sage434, null, n)}</div> } // gap
// The props a clone or a created element is given, held in a name or spread into the ones written in the call: the
// scan reads the props written there, so the children held props hand are unread, and a clone given them is read as
// the element it clones.
export function P435() { const props = { children: 'Q1' }; return <span className="text-brand-strong">{createElement('span', props)}</span> } // gap
export function P436() { const props = { children: 'Q1' }; return <span className="text-brand-strong">{cloneElement(<span>Revenue</span>, { ...props })}</span> } // gap
// What each of those fails closed on: a className held props give a clone, and a created component's own ink, are
// unread, so the children handed to either render in the sage around it.
export function P437({ n }: { n: number }) { const props = { className: 'text-text-secondary-light' }; return <span className="text-brand-strong">{cloneElement(<span />, props, n)}</span> } // flag
function Own438({ children }: { children: ReactNode }) { return <span className="text-text-secondary-light">{children}</span> }
export function P438({ n }: { n: number }) { return <span className="text-brand-strong">{createElement(Own438, null, n)}</span> } // flag
// What the file puts in an array through another name for it, an alias or a parameter it is handed to: the scan
// reads a value put in a name, not every name for the same array.
export function P382() { const out: string[] = []; const alias = out; alias.push('Q1'); return <div className="text-brand-strong">{out}</div> } // gap
export function P383() { const out: string[] = []; fill383(out); return <div className="text-brand-strong">{out}</div> } function fill383(list: string[]) { list.push('Q1') } // gap
// A value held in a Map: the scan reads what an array, a Set or an object holds, not a Map's entries.
export function P416() { const byKey = new Map<string, string>(); byKey.set('a', 'Q1'); return <span className="text-brand-strong">{[...byKey.values()]}</span> } // gap
// Codex's review of 133050c: a React utility held under a type of its own, which the checker reads as the
// annotation's, not React's declaration, so the callee is read through the one walk: a typed const (P505, the
// review's form), a cast (P506), a typed variable given one later (P507), typed destructuring (P508), a typed field
// (P509) or member (P510), a typed parameter handed one (P511) and a typed return (P512);
// cloneElement, Children.toArray and Children.map so held (P514 to P516); and Children.map held in a typed parameter
// and called with its callback written in place (P517). A same-file function under the same type (P518), and the
// typed parameter handed one (P519), are no utility.
export function P505({ n }: { n: number }) { const one: (child: ReactNode) => ReactNode = Children.only; return <div className="text-brand-strong">{one(<span>{n}</span>)}</div> } // flag
export function P506({ n }: { n: number }) { const one = Children.only as (child: ReactNode) => ReactNode; return <div className="text-brand-strong">{one(<span>{n}</span>)}</div> } // flag
export function P507({ n }: { n: number }) { let one: (child: ReactNode) => ReactNode = () => null; if (n > 0) one = Children.only; return <div className="text-brand-strong">{one(<span>{n}</span>)}</div> } // flag
export function P508({ n }: { n: number }) { const { only: one }: { only: (child: ReactNode) => ReactNode } = Children; return <div className="text-brand-strong">{one(<span>{n}</span>)}</div> } // flag
export function P509({ n }: { n: number }) { const kit: { one: (child: ReactNode) => ReactNode } = { one: Children.only }; return <div className="text-brand-strong">{kit.one(<span>{n}</span>)}</div> } // flag
export function P510({ n }: { n: number }) { const kit: [(child: ReactNode) => ReactNode] = [Children.only]; return <div className="text-brand-strong">{kit[0](<span>{n}</span>)}</div> } // flag
const apply511 = (f: (child: ReactNode) => ReactNode, child: ReactNode) => f(child)
export function P511({ n }: { n: number }) { return <div className="text-brand-strong">{apply511(Children.only, <span>{n}</span>)}</div> } // flag
const pick512 = (): ((child: ReactNode) => ReactNode) => Children.only
export function P512({ n }: { n: number }) { return <div className="text-brand-strong">{pick512()(<span>{n}</span>)}</div> } // flag
export function P514({ n }: { n: number }) { const copy: (element: ReactElement) => ReactElement = cloneElement; return <div className="text-brand-strong">{copy(<span>{n}</span>)}</div> } // flag
export function P515() { const list: (children: ReactNode) => ReactNode[] = Children.toArray; return <span className="text-brand-strong">{list(LABELS_161)}</span> } // flag
export function P516() { const each: (children: ReactNode, fn: (child: ReactNode) => ReactNode) => ReactNode = Children.map; return <p>{each(LABELS_161, (l) => <span className="text-brand-strong">{l}</span>)}</p> } // flag
export function P517() { const each = (m: (children: ReactNode, fn: (child: ReactNode) => ReactNode) => ReactNode) => m(LABELS_161, (l) => <span className="text-brand-strong">{l}</span>); return <p>{each(Children.map)}</p> } // flag
export function P518({ n }: { n: number }) { const one: (child: ReactNode) => ReactNode = (child) => (child ? <b>Revenue</b> : null); return <div className="text-brand-strong">{one(<span>{n}</span>)}</div> } // clean
export function P519({ n }: { n: number }) { const apply = (f: (child: ReactNode) => ReactNode, child: ReactNode) => f(child); return <div className="text-brand-strong">{apply((child) => (child ? <b>Revenue</b> : null), <span>{n}</span>)}</div> } // clean
// A callee typed as React's own utility is read through its type wherever it comes from, an optional one included
// (P534, from the companion module). A same-file helper handed a list and a callback hands the callback only what it
// calls it with, so only Children's map and forEach hand theirs their first argument's members (P535).
export function P534({ n }: { n: number }) { return <div className="text-brand-strong">{maybeOnly?.(<span>{n}</span>)}</div> } // flag
const apply535 = (values: number[], render: (label: string) => ReactNode) => (values.length ? render('Revenue') : null)
export function P535() { return <p>{apply535([1, 2], (label) => <span className="text-brand-strong">{label}</span>)}</p> } // clean
// Out of the walk, and so review-checked: a utility held under a type of its own in another file (P520), or in a
// class's field (P521).
export function P520({ n }: { n: number }) { return <div className="text-brand-strong">{typedOnly(<span>{n}</span>)}</div> } // gap
class Kit521 { one: (child: ReactNode) => ReactNode = Children.only }
export function P521({ n }: { n: number }) { return <div className="text-brand-strong">{new Kit521().one(<span>{n}</span>)}</div> } // gap
// The count control's one source (the chief designer's review of 4e44658): a control whose label carries a count and
// whose classes written in the file turn it sage under the pointer has rebuilt the recipe by hand, written inline
// (P522), held in a const (P523), for dark mode alone (P524), through group-hover (P525), on a disclosure's summary
// (P526) or with its count held in a variable (P527). One that composes countControlClass, written in place, held in a
// const or imported under another name (P528 to P530), one that turns sage under the pointer without a count (P531),
// and a count control that never turns sage (P532) are no copy.
export function P522({ n }: { n: number }) { return <button type="button" className="text-text-secondary-light hover:bg-brand-weak hover:text-brand-strong">Show {n}</button> } // flag
const QUIET523 = 'text-text-secondary-light underline-offset-4 hover:text-brand-strong hover:underline'
export function P523({ n }: { n: number }) { return <a href="/x" className={QUIET523}>See all {n}</a> } // flag
export function P524({ n }: { n: number }) { return <a href="/x" className="text-text-secondary-light dark:text-text-secondary-dark dark:hover:text-brand-strong-dark">See all {n}</a> } // flag
export function P525({ n }: { n: number }) { return <a href="/x" className="group text-text-secondary-light"><span className="group-hover:text-brand-strong">See all {n}</span></a> } // flag
export function P526({ n }: { n: number }) { return <details><summary className="cursor-pointer text-text-secondary-light hover:text-brand-strong">Show the {n} figures</summary></details> } // flag
export function P527({ n }: { n: number }) { const label = `See all ${n}`; return <a href="/x" className="text-text-secondary-light hover:text-brand-strong">{label}</a> } // flag
export function P528({ n }: { n: number }) { return <button type="button" className={cx('h-8 px-3 text-xs', countControlClass('button'))}>Show {n}</button> } // clean
export function P529({ n }: { n: number }) { const pick = countControlClass('link'); return <a href="/x" className={pick}>See all {n}</a> } // clean
export function P530({ n }: { n: number }) { return <a href="/x" className={tally('inline')}>See all {n}</a> } // clean
export function P531() { return <button type="button" className="text-text-secondary-light hover:text-brand-strong">Show more</button> } // clean
export function P532({ n }: { n: number }) { return <a href="/x" className="text-text-primary-light hover:underline">See all {n}</a> } // clean
// Out of a source scan's reach, and so review-checked: the recipe rebuilt in a helper of another file, whose classes
// the scan does not read (P533).
export function P533({ n }: { n: number }) { return <a href="/x" className={quietLinkClass()}>See all {n}</a> } // gap
// The round-twenty-five lens's copies: the recipe on the label, under the pointer (P536) or the control's group (P537);
// a same-file wrapper that holds it (P538) or takes it as its className's default (P539); and a class helper written as
// a function declaration, to the one-source check (P540) and to the ink check (P541). A hover fill, which recolours an
// icon and never the label (P542), an icon that turns sage beside a count that never does (P543) and a wrapper that
// composes the helper (P544) are no copy.
export function P536({ n }: { n: number }) { return <button type="button"><span className="text-text-secondary-light hover:text-brand-strong">Show {n}</span></button> } // flag
export function P537({ n }: { n: number }) { return <button type="button" className="group"><span className="text-text-secondary-light group-hover:text-brand-strong">+{n} more</span></button> } // flag
function More538({ children }: { children: ReactNode }) { return <button type="button" className="text-text-secondary-light hover:text-brand-strong">{children}</button> }
export function P538({ n }: { n: number }) { return <More538>Show {n}</More538> } // flag
function More539({ className = 'text-text-secondary-light hover:text-brand-strong', children }: { className?: string; children: ReactNode }) { return <button type="button" className={className}>{children}</button> }
export function P539({ n }: { n: number }) { return <More539>Show {n}</More539> } // flag
function quiet540() { return 'text-text-secondary-light hover:text-brand-strong' }
export function P540({ n }: { n: number }) { return <a href="/x" className={quiet540()}>See all {n}</a> } // flag
function sage541() { return 'text-brand-strong' }
export function P541({ n }: { n: number }) { return <span className={sage541()}>{n}</span> } // flag
export function P542({ n }: { n: number }) { return <button type="button" className="text-text-secondary-light hover:fill-brand-strong">Show {n}<svg aria-hidden="true" /></button> } // clean
export function P543({ n }: { n: number }) { return <a href="/x" className="group text-text-secondary-light">See all {n}<span aria-hidden="true" className="group-hover:text-brand-strong">→</span></a> } // clean
function Quiet544({ children }: { children: ReactNode }) { return <button type="button" className={countControlClass('button')}>{children}</button> }
export function P544({ n }: { n: number }) { return <Quiet544>Show {n}</Quiet544> } // clean
// Codex's review of 99f0380: a control whose label is a same-file component that renders its children in a span that
// turns sage under the pointer (P545, the review's own form) is a copy, read through the component's summary. A label
// component in the plain ink inside a control that composes the recipe (P546), and one that composes the recipe on the
// label itself (P547), are no copy.
function Label545({ children }: { children: ReactNode }) { return <span className="text-text-secondary-light hover:text-brand-strong">{children}</span> }
export function P545({ n }: { n: number }) { return <a href="/x"><Label545>See all {n}</Label545></a> } // flag
function Label546({ children }: { children: ReactNode }) { return <span className="font-medium">{children}</span> }
export function P546({ n }: { n: number }) { return <a href="/x" className={countControlClass('link')}><Label546>See all {n}</Label546></a> } // clean
function Label547({ children }: { children: ReactNode }) { return <span className={countControlClass('inline')}>{children}</span> }
export function P547({ n }: { n: number }) { return <a href="/x"><Label547>See all {n}</Label547></a> } // clean
// Codex's review of 63b7144: the same label component held in a name before it renders (P548, the review's own form)
// is read through the file's bindings; held in the plain ink inside a control that composes the recipe, it is no copy
// (P549).
export function P548({ n }: { n: number }) { const label = <Label545>See all {n}</Label545>; return <a href="/x">{label}</a> } // flag
export function P549({ n }: { n: number }) { const label = <Label546>See all {n}</Label546>; return <a href="/x" className={countControlClass('link')}>{label}</a> } // clean
// Codex's review of 2e946f7: the delegated label rendered through `&&` (P550) or held in an array (P551) is read through
// the containers on the way; through `&&` in the plain ink inside a control that composes the recipe, it is no copy (P552).
export function P550({ n, on }: { n: number; on: boolean }) { return <a href="/x">{on && <Label545>See all {n}</Label545>}</a> } // flag
export function P551({ n }: { n: number }) { const label = [<Label545 key="l">See all {n}</Label545>]; return <a href="/x">{label}</a> } // flag
export function P552({ n, on }: { n: number; on: boolean }) { return <a href="/x" className={countControlClass('link')}>{on && <Label546>See all {n}</Label546>}</a> } // clean
// The family of Codex's form (P545), round twenty-seven: the one-source check reads a control's label through the
// file's bindings. These copy the recipe: a label component that turns its children sage under the control's group
// (P553), its own count (P554, Codex's form on 820b5a0, held in a name in P571 and behind `&&` in P572; given children
// too, P576; inside another component, P580), or a number component it holds (P567); one that does it through a second
// component (P555), inside a wrapper's control (P556), by its className's default (P564) or mapped over its children
// (P565); one given hover-sage classes that it hands to the element holding its count, whether that element inherits
// its ink (P559), rests in one of its own (P568) or holds a number component (P582), and whether the classes are given
// inside another component (P581) or handed on to one that forwards them (P584); and a label span held in a const
// (P557), returned by a same-file function (P558), behind a conditional (P577), in a fragment (P578) or mapped (P579).
// These are no copy: a label component that never turns sage (P560), turns an icon sage beside its children (P561),
// turns a label without a count sage (P562), sets an ink of its own around the children inside its sage (P563), or
// holds its count in an ink of its own inside the element the forwarded classes reach (P569); one that renders its own
// count in the plain ink inside a control that composes the recipe (P573), or composes the recipe itself (P574); and
// one whose count sits in a return the forwarded classes do not reach (P583). A count handed to one as text in a prop
// of another name is the prop gap (P566); a className forwarded through a conditional return (P585) or a spread (P586),
// and an ink a label sets in one state only (P587), are gaps too. A ring of five label components, each rendering the
// next twice (P570), and a clique of six, each rendering the other five (P575), score in time: the walk reads each
// element's summary once.
function Label553({ children }: { children: ReactNode }) { return <span className="group-hover:text-brand-strong">{children}</span> }
export function P553({ n }: { n: number }) { return <a href="/x" className="group text-text-secondary-light"><Label553>See all {n}</Label553></a> } // flag
function Tally554({ n }: { n: number }) { return <span className="text-text-secondary-light hover:text-brand-strong">See all {n}</span> }
export function P554({ n }: { n: number }) { return <a href="/x"><Tally554 n={n} /></a> } // flag
function Outer555({ children }: { children: ReactNode }) { return <Label545>{children}</Label545> }
export function P555({ n }: { n: number }) { return <button type="button"><Outer555>Show {n}</Outer555></button> } // flag
function More556({ children }: { children: ReactNode }) { return <button type="button" className="text-text-secondary-light"><Label545>{children}</Label545></button> }
export function P556({ n }: { n: number }) { return <More556>Show {n}</More556> } // flag
export function P557({ n }: { n: number }) { const label = <span className="hover:text-brand-strong">See all {n}</span>; return <a href="/x">{label}</a> } // flag
function label558(n: number) { return <span className="text-text-secondary-light hover:text-brand-strong">Show {n}</span> }
export function P558({ n }: { n: number }) { return <button type="button">{label558(n)}</button> } // flag
function Tally559({ n, className }: { n: number; className?: string }) { return <span className={className}>See all {n}</span> }
export function P559({ n }: { n: number }) { return <a href="/x"><Tally559 n={n} className="hover:text-brand-strong" /></a> } // flag
function Plain560({ children }: { children: ReactNode }) { return <span className="tabular-nums">{children}</span> }
export function P560({ n }: { n: number }) { return <a href="/x"><Plain560>See all {n}</Plain560></a> } // clean
function Arrow561({ children }: { children: ReactNode }) { return <>{children}<span aria-hidden="true" className="group-hover:text-brand-strong">→</span></> }
export function P561({ n }: { n: number }) { return <a href="/x" className="group text-text-secondary-light"><Arrow561>See all {n}</Arrow561></a> } // clean
export function P562() { return <a href="/x"><Label545>See all</Label545></a> } // clean
function Frame563({ children }: { children: ReactNode }) { return <span className="hover:text-brand-strong"><span className="text-text-primary-light">{children}</span></span> }
export function P563({ n }: { n: number }) { return <a href="/x"><Frame563>See all {n}</Frame563></a> } // clean
function Label564({ className = 'hover:text-brand-strong', children }: { className?: string; children: ReactNode }) { return <span className={className}>{children}</span> }
export function P564({ n }: { n: number }) { return <a href="/x"><Label564>See all {n}</Label564></a> } // flag
function Label565({ children }: { children: ReactNode }) { return <>{Children.map(children, (child) => <span className="hover:text-brand-strong">{child}</span>)}</> }
export function P565({ n }: { n: number }) { return <a href="/x"><Label565>See all {n}</Label565></a> } // flag
function Text566({ text }: { text: string }) { return <span className="hover:text-brand-strong">{text}</span> }
export function P566({ n }: { n: number }) { return <a href="/x"><Text566 text={`See all ${n}`} /></a> } // gap
function Tally567({ n }: { n: number }) { return <span className="hover:text-brand-strong">See all <Count n={n} /></span> }
export function P567({ n }: { n: number }) { return <a href="/x"><Tally567 n={n} /></a> } // flag
function Tally568({ n, className }: { n: number; className?: string }) { return <span className={cx('text-text-secondary-light', className)}>See all {n}</span> }
export function P568({ n }: { n: number }) { return <a href="/x"><Tally568 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally569({ n, className }: { n: number; className?: string }) { return <span className={cx('text-text-secondary-light', className)}>See all <b className="text-text-primary-light">{n}</b></span> }
export function P569({ n }: { n: number }) { return <a href="/x"><Tally569 n={n} className="hover:text-brand-strong" /></a> } // clean
function Ring570a({ children, k }: { children: ReactNode; k: number }) { return k > 0 ? <span className="text-text-secondary-light"><Ring570b k={k - 1}>{children}</Ring570b><Ring570b k={k - 1}>{children}</Ring570b></span> : <i className="hover:text-brand-strong">{children}</i> }
function Ring570b({ children, k }: { children: ReactNode; k: number }) { return k > 0 ? <span className="text-text-secondary-light"><Ring570c k={k - 1}>{children}</Ring570c><Ring570c k={k - 1}>{children}</Ring570c></span> : <i className="hover:text-brand-strong">{children}</i> }
function Ring570c({ children, k }: { children: ReactNode; k: number }) { return k > 0 ? <span className="text-text-secondary-light"><Ring570d k={k - 1}>{children}</Ring570d><Ring570d k={k - 1}>{children}</Ring570d></span> : <i className="hover:text-brand-strong">{children}</i> }
function Ring570d({ children, k }: { children: ReactNode; k: number }) { return k > 0 ? <span className="text-text-secondary-light"><Ring570e k={k - 1}>{children}</Ring570e><Ring570e k={k - 1}>{children}</Ring570e></span> : <i className="hover:text-brand-strong">{children}</i> }
function Ring570e({ children, k }: { children: ReactNode; k: number }) { return k > 0 ? <span className="text-text-secondary-light"><Ring570a k={k - 1}>{children}</Ring570a><Ring570a k={k - 1}>{children}</Ring570a></span> : <i className="hover:text-brand-strong">{children}</i> }
export function P570({ n }: { n: number }) { return <a href="/x"><Ring570a k={2}>See all {n}</Ring570a></a> } // flag
export function P571({ n }: { n: number }) { const label = <Tally554 n={n} />; return <a href="/x">{label}</a> } // flag
export function P572({ n, on }: { n: number; on: boolean }) { return <a href="/x">{on && <Tally554 n={n} />}</a> } // flag
function Plain573({ n }: { n: number }) { return <span className="font-medium">See all {n}</span> }
export function P573({ n }: { n: number }) { return <a href="/x" className={countControlClass('link')}><Plain573 n={n} /></a> } // clean
function Tally574({ n }: { n: number }) { return <span className={countControlClass('inline')}>See all {n}</span> }
export function P574({ n }: { n: number }) { return <a href="/x"><Tally574 n={n} /></a> } // clean
function Clique575a({ children, k }: { children: ReactNode; k: number }) { return k > 0 ? <span className="text-text-secondary-light"><Clique575b k={k - 1}>{children}</Clique575b><Clique575c k={k - 1}>{children}</Clique575c><Clique575d k={k - 1}>{children}</Clique575d><Clique575e k={k - 1}>{children}</Clique575e><Clique575f k={k - 1}>{children}</Clique575f></span> : <i className="hover:text-brand-strong">{children}</i> }
function Clique575b({ children, k }: { children: ReactNode; k: number }) { return k > 0 ? <span className="text-text-secondary-light"><Clique575a k={k - 1}>{children}</Clique575a><Clique575c k={k - 1}>{children}</Clique575c><Clique575d k={k - 1}>{children}</Clique575d><Clique575e k={k - 1}>{children}</Clique575e><Clique575f k={k - 1}>{children}</Clique575f></span> : <i className="hover:text-brand-strong">{children}</i> }
function Clique575c({ children, k }: { children: ReactNode; k: number }) { return k > 0 ? <span className="text-text-secondary-light"><Clique575a k={k - 1}>{children}</Clique575a><Clique575b k={k - 1}>{children}</Clique575b><Clique575d k={k - 1}>{children}</Clique575d><Clique575e k={k - 1}>{children}</Clique575e><Clique575f k={k - 1}>{children}</Clique575f></span> : <i className="hover:text-brand-strong">{children}</i> }
function Clique575d({ children, k }: { children: ReactNode; k: number }) { return k > 0 ? <span className="text-text-secondary-light"><Clique575a k={k - 1}>{children}</Clique575a><Clique575b k={k - 1}>{children}</Clique575b><Clique575c k={k - 1}>{children}</Clique575c><Clique575e k={k - 1}>{children}</Clique575e><Clique575f k={k - 1}>{children}</Clique575f></span> : <i className="hover:text-brand-strong">{children}</i> }
function Clique575e({ children, k }: { children: ReactNode; k: number }) { return k > 0 ? <span className="text-text-secondary-light"><Clique575a k={k - 1}>{children}</Clique575a><Clique575b k={k - 1}>{children}</Clique575b><Clique575c k={k - 1}>{children}</Clique575c><Clique575d k={k - 1}>{children}</Clique575d><Clique575f k={k - 1}>{children}</Clique575f></span> : <i className="hover:text-brand-strong">{children}</i> }
function Clique575f({ children, k }: { children: ReactNode; k: number }) { return k > 0 ? <span className="text-text-secondary-light"><Clique575a k={k - 1}>{children}</Clique575a><Clique575b k={k - 1}>{children}</Clique575b><Clique575c k={k - 1}>{children}</Clique575c><Clique575d k={k - 1}>{children}</Clique575d><Clique575e k={k - 1}>{children}</Clique575e></span> : <i className="hover:text-brand-strong">{children}</i> }
export function P575({ n }: { n: number }) { return <a href="/x"><Clique575a k={2}>See all {n}</Clique575a></a> } // flag
function Label576({ children, n }: { children: ReactNode; n: number }) { return <span className="hover:text-brand-strong">{children} {n}</span> }
export function P576({ n }: { n: number }) { return <a href="/x"><Label576 n={n}>See all</Label576></a> } // flag
export function P577({ n }: { n: number }) { return <a href="/x">{n ? <span className="hover:text-brand-strong">Show {n}</span> : null}</a> } // flag
export function P578({ n }: { n: number }) { return <a href="/x">{<><span className="hover:text-brand-strong">Show {n}</span></>}</a> } // flag
export function P579({ items }: { items: { count: number }[] }) { return <a href="/x">{items.map((i) => <span key={i.count} className="hover:text-brand-strong">{i.count}</span>)}</a> } // flag
function Box580({ n }: { n: number }) { return <span><Tally554 n={n} /></span> }
export function P580({ n }: { n: number }) { return <a href="/x"><Box580 n={n} /></a> } // flag
function Box581({ n }: { n: number }) { return <span className="text-text-primary-light"><Tally559 n={n} className="hover:text-brand-strong" /></span> }
export function P581({ n }: { n: number }) { return <a href="/x"><Box581 n={n} /></a> } // flag
function Tally582({ n, className }: { n: number; className?: string }) { return <span className={className}>See all <Count n={n} /></span> }
export function P582({ n }: { n: number }) { return <a href="/x"><Tally582 n={n} className="hover:text-brand-strong" /></a> } // flag
function Two583({ n, className }: { n: number; className?: string }) { if (n === 0) return <span className={className}>None</span>; return <span className="text-text-secondary-light">See all {n}</span> }
export function P583({ n }: { n: number }) { return <a href="/x"><Two583 n={n} className="hover:text-brand-strong" /></a> } // clean
function Outer584({ n, className }: { n: number; className?: string }) { return <Tally559 n={n} className={className} /> }
export function P584({ n }: { n: number }) { return <a href="/x"><Outer584 n={n} className="hover:text-brand-strong" /></a> } // flag
function Cond585({ n, className }: { n: number; className?: string }) { return n > 0 ? <span className={className}>See all {n}</span> : null }
export function P585({ n }: { n: number }) { return <a href="/x"><Cond585 n={n} className="hover:text-brand-strong" /></a> } // gap
function Rest586({ n, ...rest }: { n: number; className?: string }) { return <span {...rest}>See all {n}</span> }
export function P586({ n }: { n: number }) { return <a href="/x"><Rest586 n={n} className="hover:text-brand-strong" /></a> } // gap
function Dark587({ children }: { children: ReactNode }) { return <span className="hover:text-brand-strong"><span className="dark:text-text-primary-dark">{children}</span></span> }
export function P587({ n }: { n: number }) { return <a href="/x"><Dark587>See all {n}</Dark587></a> } // gap
// Codex's review of `b36e741`: the forwarded className under the name the props' destructuring gives it (P588), a
// same-file variable holding it (P589) or `props.className` (P590); one handed on to a nested component under such a name
// (P591); the props kept whole and destructured later (P594), through a variable holding them (P595), a rest of them (P596)
// or an object spreading them (P597); the name filled by an assignment, destructured (P598) or not (P599), through an
// array (P604), nested (P605) or with the props themselves taken through one (P606); and a same-file helper returning
// it, called in the className (P601) or held first (P602); the key read by a string (P607), a computed key (P608) or a
// same-file constant (P609); the props returned by a same-file function (P610); a helper that destructures the argument
// the file's calls hand it (P612); the name filled through a rest target, an array's (P613) or an object's (P614); the
// props taken through a declaration's array (P616) or Object.assign (P617); and a helper's parameter named for the
// className, handed it at the call (P622). A destructuring of something other than the props, declared (P592) or assigned
// (P600), a variable holding another string (P593), a helper returning one (P603), another key of the props (P611), a
// helper handed another object (P615), even beside a call handing it the props (P620), another object taken through a
// declaration's array (P618), a style map's `className` by a key (P619) or a field (P621), and a helper's parameter named
// for the className handed another string (P623), a helper handed the className it never returns (P624) and
// `Object.assign` with a style map's `className` after the props (P625), a rest helper returning another member (P628),
// a source that spreads the props and then sets its own `className` (P629) and a spread of sources with the style map
// last (P633) forward nothing; a same-file joiner handed the className (P627), `Object.assign` with the props after the
// style map (P626), a spread of sources with the props last (P630), a rest helper returning the member handed the
// className (P631) and a source that sets its own `className` and then spreads the props (P632) do.
// Codex's review of `69d1137`: an object's `className` key written as a same-file constant (P634), its value an alias of
// the props' className (P635) or the shorthand of the destructured prop (P638), and a rest helper returning its last
// member, handed the className last (P637), forward it; one handed the className first (P636), and the shorthand of a
// local string (P639), do not. Beside them, ahead of a review: a helper read twice, at each call (P640); a spread among
// a rest helper's arguments, which could leave the className first (P641) or last (P644), and one that cannot (P642,
// P643), a spread of an array literal opened to its members (P647, P648); a negative index in brackets, which names no
// member (P645); and the constant key in a destructuring (P646).
// Codex's review of `056a071`: a spread among the arguments before a rest parameter's own place, which can shift what
// the rest holds (P649), and an `at()` index with a fraction, which the runtime truncates (P650), forward the
// className; a fraction in brackets names no member (P651). Beside them, ahead of a review: a fixed parameter handed
// a spread before the props (P652) or the className (P655), and a last member read past an empty rest (P653) or one
// a spread could fill (P654).
// Ahead of a review, the rest of that family: a last member read through `length - 1` (P656, P657) or an index held
// by a constant (P658, P659); the rest taken apart by a destructuring, its first member (P660), its second (P661), a
// rest element's first (P662, P663) or the parameter's own pattern (P664); and a declaration's array destructuring,
// of the className (P665), of the props (P666) or of a style map's className (P667).
// Codex's review of `6ce9969`: a spread of a tuple of one, held in a const (P668) or returned by a call (P669), hands
// the className second, so a helper returning its first parameter forwards nothing; a spread of an empty tuple hands
// it first (P670), and one of a tuple with a rest element never does (P671). A same-file const typed as a tuple and
// holding an array literal is opened where it is spread, the props last (P672) or first (P673); a union of tuples is
// read by the lengths it allows (P674 could hand the className second, P675 never first).
// Codex's reviews of `36313a7` and `c04bb70`: a union of tuples with a length between its least and most that it never
// has hands the className second never (P676) and first when empty (P677); a `className` key nested in a helper's
// parameter pattern, handed the props in an array (P678); an alias of the rest, read at the call on the way though an
// unused call hands the className (P679, clean; P680, the className first); a rest tail read by an index, at that place
// alone (P681, clean; P682, the className there), through the tail's alias too (P685); and a binding's default, read at
// the steps below it, the props (P683) or a style map (P684).
// Codex's review of `ec660d9`, and its review of #1326's `582de56`: a union of tuples with a hole below an open member
// never hands the className second (P686), and one without the hole can (P687); a rest parameter aliased by a
// destructuring, read at the call on the way though an unused call hands the className (P688); a rest tail aliased by
// one, at the tail's place (P689, clean; P690, the className there); and a tuple const written into before it is
// spread (P691), which is not opened. Their root: a spread the layout cannot open hands its members at each place it
// could cover, an array's holding the className (P692) but not where the spread cannot reach (P693), a same-file
// joiner's wrapper (P694; P695, handed another class beside a call handing it the className) and Object.assign's spread
// sources (P698). Planting it found more of the same root, each a value read without the calls on its way: a
// destructured alias of the rest holding the props (P696, clean beside an unused call; P697, the props first), a
// className-keyed assignment read through an alias (P699), the props handed to a helper's parameter pattern (P700) and
// the props in a holder's field (P751); the shorthand of the rest in a holder (P752) and a holder's other field (P753)
// must pass.
// A routine lens on that round: a destructured name's own writes, through an alias (P762), its className-keyed one
// (P763), a helper's (P769) and the binding walk's (P770); a helper's returned holder, destructured (P758; P766, handed
// another class) or read by a field (P759; P767, a style map), inside a literal (P771; P772) or spread (P760); a helper
// called twice (P754) or a value assigned twice (P755), each read at its own call; a helper that calls itself (P756); a
// declaration met again at other steps on a sibling branch (P757); a tuple reordered in place (P761), and one typed as
// writable and never written, read by its length (P768); a helper's pattern handed a style map beside a call handing it
// the props (P764); and a spread of sources without the props (P765).
// Codex's review of `0e223cb`: a const array is opened by its elements while the file never writes into it nor
// reorders it in place, whatever its type, so a tuple's members keep their places (P775), an array's too (P777), and
// Object.assign's spread sources their order, the last winning (P776); one written onto by Object.assign (P774) or
// reordered by a shift (P778), as by the reverse before (P761), is laid out by its members. P654's spread now has a
// length the file decides at run time, so its last member stays one a spread could fill.
// A spread the file writes into keeps both readings: Object.assign's sources pushed into it hand the props (P779),
// and an array pushed into, spread after a first argument, cannot reach the first place (P780).
function Tally588({ n, className: cls }: { n: number; className?: string }) { return <span className={cls}>See all {n}</span> }
export function P588({ n }: { n: number }) { return <a href="/x"><Tally588 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally589({ n, className }: { n: number; className?: string }) { const cls = className; return <span className={cx(cls, 'font-medium')}>See all {n}</span> }
export function P589({ n }: { n: number }) { return <a href="/x"><Tally589 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally590(props: { n: number; className?: string }) { return <span className={props.className}>See all {props.n}</span> }
export function P590({ n }: { n: number }) { return <a href="/x"><Tally590 n={n} className="hover:text-brand-strong" /></a> } // flag
function Outer591({ n, className: cls }: { n: number; className?: string }) { return <Tally588 n={n} className={cls} /> }
export function P591({ n }: { n: number }) { return <a href="/x"><Outer591 n={n} className="hover:text-brand-strong" /></a> } // flag
const THEME592 = { className: 'font-medium' }
function Tally592({ n }: { n: number; className?: string }) { const { className: cls } = THEME592; return <span className={cls}>See all {n}</span> }
export function P592({ n }: { n: number }) { return <a href="/x"><Tally592 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally593({ n }: { n: number; className?: string }) { const cls = 'font-medium'; return <span className={cls}>See all {n}</span> }
export function P593({ n }: { n: number }) { return <a href="/x"><Tally593 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally594(props: { n: number; className?: string }) { const { className: cls } = props; return <span className={cls}>See all {props.n}</span> }
export function P594({ n }: { n: number }) { return <a href="/x"><Tally594 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally595(props: { n: number; className?: string }) { const p = props; const { className: cls } = p; return <span className={cls}>See all {p.n}</span> }
export function P595({ n }: { n: number }) { return <a href="/x"><Tally595 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally596({ n, ...rest }: { n: number; className?: string }) { const { className: cls } = rest; return <span className={cls}>See all {n}</span> }
export function P596({ n }: { n: number }) { return <a href="/x"><Tally596 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally597(props: { n: number; className?: string }) { const { className: cls } = { ...props }; return <span className={cls}>See all {props.n}</span> }
export function P597({ n }: { n: number }) { return <a href="/x"><Tally597 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally598(props: { n: number; className?: string }) { let cls: string | undefined; ({ className: cls } = props); return <span className={cls}>See all {props.n}</span> }
export function P598({ n }: { n: number }) { return <a href="/x"><Tally598 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally599(props: { n: number; className?: string }) { let cls = 'font-medium'; if (props.className) cls = props.className; return <span className={cls}>See all {props.n}</span> }
export function P599({ n }: { n: number }) { return <a href="/x"><Tally599 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally600({ n }: { n: number; className?: string }) { let cls = 'font-medium'; ({ className: cls } = THEME592); return <span className={cls}>See all {n}</span> }
export function P600({ n }: { n: number }) { return <a href="/x"><Tally600 n={n} className="hover:text-brand-strong" /></a> } // clean
function pick601(p: { className?: string }) { return p.className }
function Tally601(props: { n: number; className?: string }) { return <span className={pick601(props)}>See all {props.n}</span> }
export function P601({ n }: { n: number }) { return <a href="/x"><Tally601 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally602(props: { n: number; className?: string }) { const cls = pick601(props); return <span className={cls}>See all {props.n}</span> }
export function P602({ n }: { n: number }) { return <a href="/x"><Tally602 n={n} className="hover:text-brand-strong" /></a> } // flag
function fixed603() { return 'font-medium' }
function Tally603({ n }: { n: number; className?: string }) { return <span className={fixed603()}>See all {n}</span> }
export function P603({ n }: { n: number }) { return <a href="/x"><Tally603 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally604(props: { n: number; className?: string }) { let cls: string | undefined; [cls] = [props.className]; return <span className={cls}>See all {props.n}</span> }
export function P604({ n }: { n: number }) { return <a href="/x"><Tally604 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally605(props: { n: number; className?: string }) { let cls: string | undefined; [{ className: cls }] = [props]; return <span className={cls}>See all {props.n}</span> }
export function P605({ n }: { n: number }) { return <a href="/x"><Tally605 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally606(props: { n: number; className?: string }) { let p: { className?: string }; [p] = [props]; const { className: cls } = p; return <span className={cls}>See all {props.n}</span> }
export function P606({ n }: { n: number }) { return <a href="/x"><Tally606 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally607(props: { n: number; className?: string }) { return <span className={props['className']}>See all {props.n}</span> }
export function P607({ n }: { n: number }) { return <a href="/x"><Tally607 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally608(props: { n: number; className?: string }) { const { ['className']: cls } = props; return <span className={cls}>See all {props.n}</span> }
export function P608({ n }: { n: number }) { return <a href="/x"><Tally608 n={n} className="hover:text-brand-strong" /></a> } // flag
const KEY609 = 'className' as const
function Tally609(props: { n: number; className?: string }) { const cls = props[KEY609]; return <span className={cls}>See all {props.n}</span> }
export function P609({ n }: { n: number }) { return <a href="/x"><Tally609 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally610(props: { n: number; className?: string }) { const get = () => props; const { className: cls } = get(); return <span className={cls}>See all {props.n}</span> }
export function P610({ n }: { n: number }) { return <a href="/x"><Tally610 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally611(props: { n: number; className?: string; tone?: string }) { const cls = props['tone']; return <span className={cls}>See all {props.n}</span> }
export function P611({ n }: { n: number }) { return <a href="/x"><Tally611 n={n} className="hover:text-brand-strong" /></a> } // clean
function pick612(p: { className?: string }) { const { className: cls } = p; return cls }
function Tally612(props: { n: number; className?: string }) { return <span className={pick612(props)}>See all {props.n}</span> }
export function P612({ n }: { n: number }) { return <a href="/x"><Tally612 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally613(props: { n: number; className?: string }) { let rest: (string | undefined)[]; [...rest] = [props.className]; const cls = rest[0]; return <span className={cls}>See all {props.n}</span> }
export function P613({ n }: { n: number }) { return <a href="/x"><Tally613 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally614(props: { n: number; className?: string }) { let rest: { className?: string }; ({ ...rest } = props); const { className: cls } = rest; return <span className={cls}>See all {props.n}</span> }
export function P614({ n }: { n: number }) { return <a href="/x"><Tally614 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally615({ n }: { n: number; className?: string }) { return <span className={pick612(THEME592)}>See all {n}</span> }
export function P615({ n }: { n: number }) { return <a href="/x"><Tally615 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally616(props: { n: number; className?: string }) { const [p] = [props]; const { className: cls } = p; return <span className={cls}>See all {props.n}</span> }
export function P616({ n }: { n: number }) { return <a href="/x"><Tally616 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally617(props: { n: number; className?: string }) { const { className: cls } = Object.assign({}, props); return <span className={cls}>See all {props.n}</span> }
export function P617({ n }: { n: number }) { return <a href="/x"><Tally617 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally618({ n }: { n: number; className?: string }) { const [p] = [THEME592]; const { className: cls } = p; return <span className={cls}>See all {n}</span> }
export function P618({ n }: { n: number }) { return <a href="/x"><Tally618 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally619({ n }: { n: number; className?: string }) { return <span className={THEME592['className']}>See all {n}</span> }
export function P619({ n }: { n: number }) { return <a href="/x"><Tally619 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally620(props: { n: number; className?: string }) { void pick612(props); return <span className={pick612(THEME592)}>See all {props.n}</span> }
export function P620({ n }: { n: number }) { return <a href="/x"><Tally620 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally621({ n }: { n: number; className?: string }) { return <span className={THEME592.className}>See all {n}</span> }
export function P621({ n }: { n: number }) { return <a href="/x"><Tally621 n={n} className="hover:text-brand-strong" /></a> } // clean
function pass622(className?: string) { return className }
function Tally622(props: { n: number; className?: string }) { return <span className={pass622(props.className)}>See all {props.n}</span> }
export function P622({ n }: { n: number }) { return <a href="/x"><Tally622 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally623({ n }: { n: number; className?: string }) { return <span className={pass622('font-medium')}>See all {n}</span> }
export function P623({ n }: { n: number }) { return <a href="/x"><Tally623 n={n} className="hover:text-brand-strong" /></a> } // clean
function fixed624(_cls?: string) { return 'font-medium' }
function Tally624(props: { n: number; className?: string }) { return <span className={fixed624(props.className)}>See all {props.n}</span> }
export function P624({ n }: { n: number }) { return <a href="/x"><Tally624 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally625(props: { n: number; className?: string }) { return <span className={Object.assign({}, props, THEME592).className}>See all {props.n}</span> }
export function P625({ n }: { n: number }) { return <a href="/x"><Tally625 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally626(props: { n: number; className?: string }) { return <span className={Object.assign({}, THEME592, props).className}>See all {props.n}</span> }
export function P626({ n }: { n: number }) { return <a href="/x"><Tally626 n={n} className="hover:text-brand-strong" /></a> } // flag
function join627(...parts: Array<string | undefined>) { return parts.filter(Boolean).join(' ') }
function Tally627(props: { n: number; className?: string }) { return <span className={join627('font-medium', props.className)}>See all {props.n}</span> }
export function P627({ n }: { n: number }) { return <a href="/x"><Tally627 n={n} className="hover:text-brand-strong" /></a> } // flag
function first628(...parts: Array<string | undefined>) { return parts[0] }
function Tally628(props: { n: number; className?: string }) { return <span className={first628('font-medium', props.className)}>See all {props.n}</span> }
export function P628({ n }: { n: number }) { return <a href="/x"><Tally628 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally629(props: { n: number; className?: string }) { return <span className={Object.assign({}, { ...props, className: 'font-medium' }).className}>See all {props.n}</span> }
export function P629({ n }: { n: number }) { return <a href="/x"><Tally629 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally630(props: { n: number; className?: string }) { return <span className={Object.assign({}, ...[THEME592, props]).className}>See all {props.n}</span> }
export function P630({ n }: { n: number }) { return <a href="/x"><Tally630 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally631(props: { n: number; className?: string }) { return <span className={first628(props.className, 'font-medium')}>See all {props.n}</span> }
export function P631({ n }: { n: number }) { return <a href="/x"><Tally631 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally632(props: { n: number; className?: string }) { return <span className={Object.assign({}, { className: 'font-medium', ...props }).className}>See all {props.n}</span> }
export function P632({ n }: { n: number }) { return <a href="/x"><Tally632 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally633(props: { n: number; className?: string }) { return <span className={Object.assign({}, ...[props, THEME592]).className}>See all {props.n}</span> }
export function P633({ n }: { n: number }) { return <a href="/x"><Tally633 n={n} className="hover:text-brand-strong" /></a> } // clean
const KEY634 = 'className' as const
function Tally634(props: { n: number; className?: string }) { return <span className={Object.assign({}, { [KEY634]: props.className }).className}>See all {props.n}</span> }
export function P634({ n }: { n: number }) { return <a href="/x"><Tally634 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally635(props: { n: number; className?: string }) { const cls = props.className; return <span className={Object.assign({}, { className: cls }).className}>See all {props.n}</span> }
export function P635({ n }: { n: number }) { return <a href="/x"><Tally635 n={n} className="hover:text-brand-strong" /></a> } // flag
function last636(...parts: Array<string | undefined>) { return parts.at(-1) }
function Tally636(props: { n: number; className?: string }) { return <span className={last636(props.className, 'font-medium')}>See all {props.n}</span> }
export function P636({ n }: { n: number }) { return <a href="/x"><Tally636 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally637(props: { n: number; className?: string }) { return <span className={last636('font-medium', props.className)}>See all {props.n}</span> }
export function P637({ n }: { n: number }) { return <a href="/x"><Tally637 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally638({ n, className }: { n: number; className?: string }) { return <span className={Object.assign({}, { className }).className}>See all {n}</span> }
export function P638({ n }: { n: number }) { return <a href="/x"><Tally638 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally639({ n }: { n: number; className?: string }) { const className = 'font-medium'; return <span className={Object.assign({}, { className }).className}>See all {n}</span> }
export function P639({ n }: { n: number }) { return <a href="/x"><Tally639 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally640(props: { n: number; className?: string }) { return <span className={cx(pick612(THEME592), pick612(props))}>See all {props.n}</span> }
export function P640({ n }: { n: number }) { return <a href="/x"><Tally640 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally641(props: { n: number; className?: string }) { const more: string[] = []; return <span className={first628(...more, props.className)}>See all {props.n}</span> }
export function P641({ n }: { n: number }) { return <a href="/x"><Tally641 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally642(props: { n: number; className?: string }) { const more: string[] = []; return <span className={last636(props.className, ...more, 'font-medium')}>See all {props.n}</span> }
export function P642({ n }: { n: number }) { return <a href="/x"><Tally642 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally643(props: { n: number; className?: string }) { const more: string[] = []; return <span className={first628(...more, 'font-medium', props.className)}>See all {props.n}</span> }
export function P643({ n }: { n: number }) { return <a href="/x"><Tally643 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally644(props: { n: number; className?: string }) { const more: string[] = []; return <span className={last636('font-medium', ...more, props.className)}>See all {props.n}</span> }
export function P644({ n }: { n: number }) { return <a href="/x"><Tally644 n={n} className="hover:text-brand-strong" /></a> } // flag
function none645(...parts: Array<string | undefined>) { return parts[-1] }
function Tally645(props: { n: number; className?: string }) { return <span className={none645(props.className)}>See all {props.n}</span> }
export function P645({ n }: { n: number }) { return <a href="/x"><Tally645 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally646(props: { n: number; className?: string }) { const { [KEY634]: cls } = props; return <span className={cls}>See all {props.n}</span> }
export function P646({ n }: { n: number }) { return <a href="/x"><Tally646 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally647(props: { n: number; className?: string }) { return <span className={first628(...['font-medium'], props.className)}>See all {props.n}</span> }
export function P647({ n }: { n: number }) { return <a href="/x"><Tally647 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally648(props: { n: number; className?: string }) { return <span className={last636(...['font-medium', props.className])}>See all {props.n}</span> }
export function P648({ n }: { n: number }) { return <a href="/x"><Tally648 n={n} className="hover:text-brand-strong" /></a> } // flag
const MORE649: [] | [string] = []
function first649(_head: string | undefined, ...parts: Array<string | undefined>) { return parts[0] }
function Tally649(props: { n: number; className?: string }) { return <span className={first649(...MORE649, 'font-medium', props.className)}>See all {props.n}</span> }
export function P649({ n }: { n: number }) { return <a href="/x"><Tally649 n={n} className="hover:text-brand-strong" /></a> } // flag
function half650(...parts: Array<string | undefined>) { return parts.at(0.5) }
function Tally650(props: { n: number; className?: string }) { return <span className={half650(props.className, 'font-medium')}>See all {props.n}</span> }
export function P650({ n }: { n: number }) { return <a href="/x"><Tally650 n={n} className="hover:text-brand-strong" /></a> } // flag
function none651(...parts: Array<string | undefined>) { return parts[0.5] }
function Tally651(props: { n: number; className?: string }) { return <span className={none651(props.className)}>See all {props.n}</span> }
export function P651({ n }: { n: number }) { return <a href="/x"><Tally651 n={n} className="hover:text-brand-strong" /></a> } // clean
const MORE652: [] | [{ className?: string }] = []
function pick652(p: { className?: string }, _tail?: unknown) { return p.className }
function Tally652(props: { n: number; className?: string }) { return <span className={pick652(...MORE652, props)}>See all {props.n}</span> }
export function P652({ n }: { n: number }) { return <a href="/x"><Tally652 n={n} className="hover:text-brand-strong" /></a> } // flag
function last653(_head: string | undefined, ...parts: Array<string | undefined>) { return parts.at(-1) }
function Tally653(props: { n: number; className?: string }) { return <span className={last653(props.className)}>See all {props.n}</span> }
export function P653({ n }: { n: number }) { return <a href="/x"><Tally653 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally654(props: { n: number; className?: string }) { const more: string[] = props.n > 0 ? ['font-semibold'] : []; return <span className={last653(...more, props.className)}>See all {props.n}</span> }
export function P654({ n }: { n: number }) { return <a href="/x"><Tally654 n={n} className="hover:text-brand-strong" /></a> } // flag
function pass655(className?: string, _tail?: unknown) { return className }
function Tally655(props: { n: number; className?: string }) { return <span className={pass655(...MORE649, props.className)}>See all {props.n}</span> }
export function P655({ n }: { n: number }) { return <a href="/x"><Tally655 n={n} className="hover:text-brand-strong" /></a> } // flag
function last656(...parts: Array<string | undefined>) { return parts[parts.length - 1] }
function Tally656(props: { n: number; className?: string }) { return <span className={last656(props.className, 'font-medium')}>See all {props.n}</span> }
export function P656({ n }: { n: number }) { return <a href="/x"><Tally656 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally657(props: { n: number; className?: string }) { return <span className={last656('font-medium', props.className)}>See all {props.n}</span> }
export function P657({ n }: { n: number }) { return <a href="/x"><Tally657 n={n} className="hover:text-brand-strong" /></a> } // flag
const LAST658 = -1
function last658(...parts: Array<string | undefined>) { return parts.at(LAST658) }
function Tally658(props: { n: number; className?: string }) { return <span className={last658(props.className, 'font-medium')}>See all {props.n}</span> }
export function P658({ n }: { n: number }) { return <a href="/x"><Tally658 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally659(props: { n: number; className?: string }) { return <span className={last658('font-medium', props.className)}>See all {props.n}</span> }
export function P659({ n }: { n: number }) { return <a href="/x"><Tally659 n={n} className="hover:text-brand-strong" /></a> } // flag
function head660(...parts: Array<string | undefined>) { const [h] = parts; return h }
function Tally660(props: { n: number; className?: string }) { return <span className={head660(props.className, 'font-medium')}>See all {props.n}</span> }
export function P660({ n }: { n: number }) { return <a href="/x"><Tally660 n={n} className="hover:text-brand-strong" /></a> } // flag
function second661(...parts: Array<string | undefined>) { const [, s] = parts; return s }
function Tally661(props: { n: number; className?: string }) { return <span className={second661(props.className, 'font-medium')}>See all {props.n}</span> }
export function P661({ n }: { n: number }) { return <a href="/x"><Tally661 n={n} className="hover:text-brand-strong" /></a> } // clean
function tail662(...parts: Array<string | undefined>) { const [, ...rest] = parts; return rest[0] }
function Tally662(props: { n: number; className?: string }) { return <span className={tail662('font-medium', props.className)}>See all {props.n}</span> }
export function P662({ n }: { n: number }) { return <a href="/x"><Tally662 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally663(props: { n: number; className?: string }) { return <span className={tail662(props.className, 'font-medium')}>See all {props.n}</span> }
export function P663({ n }: { n: number }) { return <a href="/x"><Tally663 n={n} className="hover:text-brand-strong" /></a> } // clean
function head664(...[h]: Array<string | undefined>) { return h }
function Tally664(props: { n: number; className?: string }) { return <span className={head664(props.className)}>See all {props.n}</span> }
export function P664({ n }: { n: number }) { return <a href="/x"><Tally664 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally665(props: { n: number; className?: string }) { const [cls] = [props.className]; return <span className={cls}>See all {props.n}</span> }
export function P665({ n }: { n: number }) { return <a href="/x"><Tally665 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally666(props: { n: number; className?: string }) { const [{ className: cls }] = [props]; return <span className={cls}>See all {props.n}</span> }
export function P666({ n }: { n: number }) { return <a href="/x"><Tally666 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally667({ n }: { n: number; className?: string }) { const [cls] = [THEME592.className]; return <span className={cls}>See all {n}</span> }
export function P667({ n }: { n: number }) { return <a href="/x"><Tally667 n={n} className="hover:text-brand-strong" /></a> } // clean
const PREFIX668: readonly [string] = ['font-medium']
function first668(head?: string, ..._rest: Array<string | undefined>) { return head }
function Tally668(props: { n: number; className?: string }) { return <span className={first668(...PREFIX668, props.className)}>See all {props.n}</span> }
export function P668({ n }: { n: number }) { return <a href="/x"><Tally668 n={n} className="hover:text-brand-strong" /></a> } // clean
function one669(): readonly [string] { return ['font-medium'] }
function Tally669(props: { n: number; className?: string }) { const pair = one669(); return <span className={first668(...pair, props.className)}>See all {props.n}</span> }
export function P669({ n }: { n: number }) { return <a href="/x"><Tally669 n={n} className="hover:text-brand-strong" /></a> } // clean
function none670(): readonly [] { return [] }
function Tally670(props: { n: number; className?: string }) { const none = none670(); return <span className={first668(...none, props.className)}>See all {props.n}</span> }
export function P670({ n }: { n: number }) { return <a href="/x"><Tally670 n={n} className="hover:text-brand-strong" /></a> } // flag
function some671(): [string, ...string[]] { return ['font-medium'] }
function Tally671(props: { n: number; className?: string }) { const some = some671(); return <span className={first668(...some, props.className)}>See all {props.n}</span> }
export function P671({ n }: { n: number }) { return <a href="/x"><Tally671 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally672(props: { n: number; className?: string }) { const sources = [THEME592, props] as const; return <span className={Object.assign({}, ...sources).className}>See all {props.n}</span> }
export function P672({ n }: { n: number }) { return <a href="/x"><Tally672 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally673(props: { n: number; className?: string }) { const sources = [props, THEME592] as const; return <span className={Object.assign({}, ...sources).className}>See all {props.n}</span> }
export function P673({ n }: { n: number }) { return <a href="/x"><Tally673 n={n} className="hover:text-brand-strong" /></a> } // clean
function maybe674(): [] | [string] { return [] }
function Tally674(props: { n: number; className?: string }) { const m = maybe674(); return <span className={first649(...m, 'font-medium', props.className)}>See all {props.n}</span> }
export function P674({ n }: { n: number }) { return <a href="/x"><Tally674 n={n} className="hover:text-brand-strong" /></a> } // flag
function oneOrTwo675(): [string] | [string, string] { return ['font-medium'] }
function Tally675(props: { n: number; className?: string }) { const m = oneOrTwo675(); return <span className={first668(...m, props.className)}>See all {props.n}</span> }
export function P675({ n }: { n: number }) { return <a href="/x"><Tally675 n={n} className="hover:text-brand-strong" /></a> } // clean
function pair676(): [] | [string, string] { return [] }
function second676(_a?: string, b?: string, ..._rest: Array<string | undefined>) { return b }
function Tally676(props: { n: number; className?: string }) { const m = pair676(); return <span className={second676(...m, props.className)}>See all {props.n}</span> }
export function P676({ n }: { n: number }) { return <a href="/x"><Tally676 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally677(props: { n: number; className?: string }) { const m = pair676(); return <span className={first668(...m, props.className)}>See all {props.n}</span> }
export function P677({ n }: { n: number }) { return <a href="/x"><Tally677 n={n} className="hover:text-brand-strong" /></a> } // flag
function pick678([{ className: cls }]: [{ className?: string }]) { return cls }
function Tally678(props: { n: number; className?: string }) { return <span className={pick678([props])}>See all {props.n}</span> }
export function P678({ n }: { n: number }) { return <a href="/x"><Tally678 n={n} className="hover:text-brand-strong" /></a> } // flag
function head679(...parts: Array<string | undefined>) { const all = parts; const [head] = all; return head }
function Tally679(props: { n: number; className?: string }) { void head679(props.className); return <span className={head679('font-medium', 'font-medium')}>See all {props.n}</span> }
export function P679({ n }: { n: number }) { return <a href="/x"><Tally679 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally680(props: { n: number; className?: string }) { return <span className={head679(props.className, 'font-medium')}>See all {props.n}</span> }
export function P680({ n }: { n: number }) { return <a href="/x"><Tally680 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally681(props: { n: number; className?: string }) { return <span className={tail662('font-medium', 'font-medium', props.className)}>See all {props.n}</span> }
export function P681({ n }: { n: number }) { return <a href="/x"><Tally681 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally682(props: { n: number; className?: string }) { return <span className={tail662('font-medium', props.className, 'font-medium')}>See all {props.n}</span> }
export function P682({ n }: { n: number }) { return <a href="/x"><Tally682 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally683(props: { n: number; className?: string }) { const [{ className: cls } = props] = [undefined]; return <span className={cls}>See all {props.n}</span> }
export function P683({ n }: { n: number }) { return <a href="/x"><Tally683 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally684({ n }: { n: number; className?: string }) { const [{ className: cls } = THEME592] = [undefined]; return <span className={cls}>See all {n}</span> }
export function P684({ n }: { n: number }) { return <a href="/x"><Tally684 n={n} className="hover:text-brand-strong" /></a> } // clean
function tail685(...parts: Array<string | undefined>) { const [, ...rest] = parts; const tail = rest; return tail[0] }
function Tally685(props: { n: number; className?: string }) { return <span className={tail685('font-medium', 'font-medium', props.className)}>See all {props.n}</span> }
export function P685({ n }: { n: number }) { return <a href="/x"><Tally685 n={n} className="hover:text-brand-strong" /></a> } // clean
function holes686(): [] | [string, string, ...string[]] { return [] }
function Tally686(props: { n: number; className?: string }) { const m = holes686(); return <span className={second676(...m, props.className)}>See all {props.n}</span> }
export function P686({ n }: { n: number }) { return <a href="/x"><Tally686 n={n} className="hover:text-brand-strong" /></a> } // clean
function holes687(): [] | [string, ...string[]] { return [] }
function Tally687(props: { n: number; className?: string }) { const m = holes687(); return <span className={second676(...m, props.className)}>See all {props.n}</span> }
export function P687({ n }: { n: number }) { return <a href="/x"><Tally687 n={n} className="hover:text-brand-strong" /></a> } // flag
function head688(...parts: Array<string | undefined>) { const [all] = [parts]; const [h] = all; return h }
function Tally688(props: { n: number; className?: string }) { void head688(props.className); return <span className={head688('font-medium', 'font-medium')}>See all {props.n}</span> }
export function P688({ n }: { n: number }) { return <a href="/x"><Tally688 n={n} className="hover:text-brand-strong" /></a> } // clean
function tail689(...parts: Array<string | undefined>) { const [, ...rest] = parts; const [tail] = [rest]; return tail[0] }
function Tally689(props: { n: number; className?: string }) { return <span className={tail689('font-medium', 'font-medium', props.className)}>See all {props.n}</span> }
export function P689({ n }: { n: number }) { return <a href="/x"><Tally689 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally690(props: { n: number; className?: string }) { return <span className={tail689('font-medium', props.className, 'font-medium')}>See all {props.n}</span> }
export function P690({ n }: { n: number }) { return <a href="/x"><Tally690 n={n} className="hover:text-brand-strong" /></a> } // flag
function first691(...parts: Array<string | undefined>) { return parts[0] }
function Tally691(props: { n: number; className?: string }) { const prefix: [string | undefined] = ['font-medium']; prefix[0] = props.className; return <span className={first691(...prefix)}>See all {props.n}</span> }
export function P691({ n }: { n: number }) { return <a href="/x"><Tally691 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally692(props: { n: number; className?: string }) { const parts: Array<string | undefined> = [props.className]; return <span className={first691(...parts)}>See all {props.n}</span> }
export function P692({ n }: { n: number }) { return <a href="/x"><Tally692 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally693(props: { n: number; className?: string }) { const parts: Array<string | undefined> = [props.className]; return <span className={first691('font-medium', ...parts)}>See all {props.n}</span> }
export function P693({ n }: { n: number }) { return <a href="/x"><Tally693 n={n} className="hover:text-brand-strong" /></a> } // clean
function join694(...parts: Array<string | undefined>) { return parts.filter(Boolean).join(' ') }
function withBase694(...parts: Array<string | undefined>) { return join694('font-medium', ...parts) }
function Tally694(props: { n: number; className?: string }) { return <span className={withBase694(props.className)}>See all {props.n}</span> }
export function P694({ n }: { n: number }) { return <a href="/x"><Tally694 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally695(props: { n: number; className?: string }) { void withBase694(props.className); return <span className={withBase694('font-semibold')}>See all {props.n}</span> }
export function P695({ n }: { n: number }) { return <a href="/x"><Tally695 n={n} className="hover:text-brand-strong" /></a> } // clean
function pick696(...parts: Array<{ className?: string }>) { const [all] = [parts]; const [p] = all; return p.className }
function Tally696(props: { n: number; className?: string }) { void pick696(props); return <span className={pick696(THEME592, THEME592)}>See all {props.n}</span> }
export function P696({ n }: { n: number }) { return <a href="/x"><Tally696 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally697(props: { n: number; className?: string }) { return <span className={pick696(props, THEME592)}>See all {props.n}</span> }
export function P697({ n }: { n: number }) { return <a href="/x"><Tally697 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally698(props: { n: number; className?: string }) { const sources = [THEME592, props]; return <span className={Object.assign({}, ...sources).className}>See all {props.n}</span> }
export function P698({ n }: { n: number }) { return <a href="/x"><Tally698 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally699(props: { n: number; className?: string }) { let cls: string | undefined; ({ className: cls } = props); const held = cls; return <span className={held}>See all {props.n}</span> }
export function P699({ n }: { n: number }) { return <a href="/x"><Tally699 n={n} className="hover:text-brand-strong" /></a> } // flag
function pick700([p]: [{ className?: string }]) { return p.className }
function Tally700(props: { n: number; className?: string }) { return <span className={pick700([props])}>See all {props.n}</span> }
export function P700({ n }: { n: number }) { return <a href="/x"><Tally700 n={n} className="hover:text-brand-strong" /></a> } // flag
// A figure field (the Copilot's links, D-030): a string the server or the model writes a figure into, read by the field
// the app's API types declare it as. Off the object (P701), by its name in brackets (P720), held (P702), destructured
// and renamed (P703), handed to a parameter (P704), mapped (P705), through `??` as the Copilot's locator wrote it
// (P706), a change's display (P707), a filing's excerpt (P708) and a public page's (P719); through its own method
// (P714, P716) or a formatter (P715); a hand-rolled locator under the pointer, a copy of the count control (P709); and
// a parameter destructured from what the call hands it (P713). A same-named field of the file's own type (P710),
// through a method too (P717), a call on one that returns a boolean, which renders nothing (P718), and a locator that
// composes the count control (P711) are no offence. One handed to a component's props stays the props gap (P712).
export function P701({ c }: { c: CopilotCitation }) { return <a href="/x" className="text-brand-strong">{c.section_ref}</a> } // flag
export function P702({ c }: { c: CopilotCitation }) { const ref = c.section_ref; return <span className="text-brand-strong">{ref}</span> } // flag
export function P703({ c }: { c: CopilotCitation }) { const { section_ref: ref } = c; return <span className="text-brand-strong">{ref}</span> } // flag
export function P704({ c }: { c: CopilotCitation }) { const locate = (label: string | null) => <span className="text-brand-strong">{label}</span>; return <p>{locate(c.section_ref)}</p> } // flag
export function P705({ cs }: { cs: CopilotCitation[] }) { return <ul>{cs.map((c) => <li key={String(c.n)} className="text-brand-strong">{c.section_ref}</li>)}</ul> } // flag
export function P706({ c }: { c: CopilotCitation }) { return <a href="/x" className="text-brand-strong">{c.section_ref ?? 'View in filing'} ↗</a> } // flag
export function P707({ item }: { item: WhatChangedItem }) { return <span className="text-brand-strong">{item.display}</span> } // flag
export function P708({ c }: { c: CopilotCitation }) { return <blockquote className="text-brand-strong">{c.excerpt}</blockquote> } // flag
export function P709({ c }: { c: CopilotCitation }) { return <a href="/x" className="text-text-secondary-light hover:text-brand-strong">{c.section_ref}</a> } // flag
export function P713({ c }: { c: CopilotCitation }) { const locate = ({ section_ref }: { section_ref: string | null }) => <span className="text-brand-strong">{section_ref}</span>; return <p>{locate(c)}</p> } // flag
export function P710() { const style = { display: 'Show all' }; return <span className="text-brand-strong">{style.display}</span> } // clean
export function P711({ c }: { c: CopilotCitation }) { return <a href="/x" className={cx('text-xs', countControlClass('link'))}>{c.section_ref}</a> } // clean
function Locator712({ label }: { label: string | null }) { return <span className="text-brand-strong">{label}</span> }
export function P712({ c }: { c: CopilotCitation }) { return <Locator712 label={c.section_ref} /> } // gap
export function P714({ c }: { c: CopilotCitation }) { return <span className="text-brand-strong">{c.section_ref?.trim()}</span> } // flag
export function P715({ c }: { c: CopilotCitation }) { return <span className="text-brand-strong">{String(c.excerpt)}</span> } // flag
export function P716({ item }: { item: WhatChangedItem }) { return <span className="text-brand-strong">{item.display.toUpperCase()}</span> } // flag
export function P717() { const own = { section_ref: 'Item 7' }; return <span className="text-brand-strong">{own.section_ref.trim()}</span> } // clean
export function P718({ c }: { c: CopilotCitation }) { return <span className="text-brand-strong">{c.excerpt.includes('margin') || 'No mention of margin'}</span> } // clean
export function P719({ e }: { e: ExampleEvidence }) { return <blockquote className="text-brand-strong">{e.excerpt}</blockquote> } // flag
export function P720({ c }: { c: CopilotCitation }) { return <a href="/x" className="text-brand-strong">{c['section_ref']}</a> } // flag
// A boolean a figure field's method returns renders nothing, read through `?.` too (P721); a risk's source_section_ref,
// declared in types/summary.ts (P722), and a metric row's change_display (P723) are figure fields.
export function P721({ c }: { c: CopilotCitation }) { return <span className="text-brand-strong">{c.section_ref?.startsWith('XBRL') || 'Passage'}</span> } // clean
export function P722({ r }: { r: RiskFactor }) { return <span className="text-brand-strong">{r.source_section_ref}</span> } // flag
export function P723({ m }: { m: RenderedMetricRow }) { return <span className="text-brand-strong">{m.change_display}</span> } // flag
// A link the app renders for markdown prints the prose's words, so its own classes rest in no sage: held under `a` as
// an arrow (P724) or a method (P726); sage only under the pointer is no copy (P725).
export function P724() { return { a: ({ children }: { children?: ReactNode }) => <a className="font-semibold text-brand-strong">{children}</a> } } // flag
export function P725() { return { a: ({ children }: { children?: ReactNode }) => <a className="font-semibold hover:text-brand-strong">{children}</a> } } // clean
export function P726() { return { a({ children }: { children?: ReactNode }) { return <a className="dark:text-brand-strong-dark">{children}</a> } } } // flag
// Every field the API types declare that can hold a string is a figure field or a word field. A metric row's
// formatted figure (P727, Codex's form on #1326), destructured (P728), its camelCase twin (P729), a growth that is a
// number or "nm" (P730), a date through its own method (P731), a period (P732), a number a reader reads as one (P733)
// and a headline written about the filing (P734) are figure fields. A ticker (P735), a person's message on a control
// that turns sage under the pointer (P736), a field whose literals carry no digit (P737) and one whose literal does,
// a name (P738), are word fields. A figure field copied into a component's own type is unread (P739).
export function P727({ m }: { m: MetricItem }) { return <span className="text-brand-strong">{m.current_period}</span> } // flag
export function P728({ m }: { m: MetricItem }) { const { prior_period: prior } = m; return <span className="text-brand-strong">{prior}</span> } // flag
export function P729({ f }: { f: NormalizedFact }) { return <span className="text-brand-strong">{f.currentPeriod}</span> } // flag
export function P730({ p }: { p: AnalysisPoint }) { return <span className="text-brand-strong">{p.yoy}</span> } // flag
export function P731({ f }: { f: Filing }) { return <time className="text-brand-strong">{f.filing_date.slice(0, 7)}</time> } // flag
export function P732({ p }: { p: AnalysisPoint }) { return <span className="text-brand-strong">{p.fiscal_period}</span> } // flag
export function P733({ c }: { c: Company }) { return <span className="text-brand-strong">CIK {c.cik}</span> } // flag
export function P734({ w }: { w: WhatChanged }) { return <p className="text-brand-strong">{w.headline}</p> } // flag
export function P735({ c }: { c: Company }) { return <span className="font-mono text-brand-strong">{c.ticker}</span> } // clean
export function P736({ f }: { f: FeedbackRecord }) { return <button type="button" className="text-left hover:text-brand-strong">{f.message}</button> } // clean
export function P737({ item }: { item: WhatChangedItem }) { return <span className="text-brand-strong">{item.direction}</span> } // clean
export function P738({ r }: { r: CalendarRangeResult }) { return <span className="text-brand-strong">{r.universe}</span> } // clean
export function P739({ row }: { row: { current_period: string } }) { return <span className="text-brand-strong">{row.current_period}</span> } // gap
// An element of a figure field that holds an array is a figure: a list's items mapped (P740), a table's cell indexed
// (P741) or mapped row by row (P742), the first item destructured past `??` (P743), an item looped over (P744), and the
// items joined (P748); and a per-ADS ratio's source, which the server writes a figure into (P745). An element of a word
// field's array (P746), a map over a figure array whose callback renders no figure (P747) and an element of a figure
// field's name that holds objects, not strings (P750), are no offence. One character of a figure field's text, a drop
// cap, is left to review (P749): it is a digit when the text begins with one.
export function P740({ b }: { b: RenderedBlock }) { return <ul>{b.items?.map((item) => <li key={item} className="text-brand-strong">{item}</li>)}</ul> } // flag
export function P741({ b }: { b: RenderedBlock }) { return <span className="text-brand-strong">{b.rows?.[0]?.[1]}</span> } // flag
export function P742({ b }: { b: RenderedBlock }) { return <table><tbody>{b.rows?.map((r, i) => <tr key={i}>{r.map((c) => <td key={c} className="text-brand-strong">{c}</td>)}</tr>)}</tbody></table> } // flag
export function P743({ b }: { b: RenderedBlock }) { const [first] = b.items ?? []; return <span className="text-brand-strong">{first}</span> } // flag
export function P744({ b }: { b: RenderedBlock }) { const out: ReactNode[] = []; for (const item of b.items ?? []) out.push(<li key={item} className="text-brand-strong">{item}</li>); return <ul>{out}</ul> } // flag
export function P745({ p }: { p: PerAdsValue }) { return <span className="text-brand-strong">{p.source}</span> } // flag
export function P746({ f }: { f: AnalysisInflection }) { return <ul>{f.concepts?.map((c) => <li key={c} className="text-brand-strong">{c}</li>)}</ul> } // clean
export function P747({ b }: { b: RenderedBlock }) { return <ul className="text-brand-strong">{b.items?.map((item) => <li key={item}>Item</li>)}</ul> } // clean
export function P748({ b }: { b: RenderedBlock }) { return <p className="text-brand-strong">{b.items?.join(' · ')}</p> } // flag
export function P749({ c }: { c: CopilotCitation }) { return <span className="text-brand-strong">{c.excerpt[0]}</span> } // gap
function name750(it: WhatChangedItem) { return it.label }
export function P750({ w }: { w: WhatChanged }) { return <ul>{w.items.map((it) => <li key={it.metric} className="text-brand-strong">{name750(it)}</li>)}</ul> } // clean
function Tally751(props: { n: number; className?: string }) { const p = props; const box = { p }; const [q] = [box.p]; return <span className={q.className}>See all {props.n}</span> }
export function P751({ n }: { n: number }) { return <a href="/x"><Tally751 n={n} className="hover:text-brand-strong" /></a> } // flag
function pick752(...parts: Array<{ className?: string }>) { const box = { parts }; const [p] = box.parts; return p.className }
function Tally752(props: { n: number; className?: string }) { void pick752(props); return <span className={pick752(THEME592)}>See all {props.n}</span> }
export function P752({ n }: { n: number }) { return <a href="/x"><Tally752 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally753({ n, ...rest }: { n: number; className?: string }) { const box = { p: THEME592, q: rest }; return <span className={box.p.className}>See all {n}</span> }
export function P753({ n }: { n: number }) { return <a href="/x"><Tally753 n={n} className="hover:text-brand-strong" /></a> } // clean
function get754(p: { className?: string }) { return p }
function Tally754(props: { n: number; className?: string }) { const both = [get754(THEME592), get754(props)]; return <span className={both[props.n].className}>See all {props.n}</span> }
export function P754({ n }: { n: number }) { return <a href="/x"><Tally754 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally755(props: { n: number; className?: string }) { let p = get754(THEME592); if (props.n) p = get754(props); return <span className={p.className}>See all {props.n}</span> }
export function P755({ n }: { n: number }) { return <a href="/x"><Tally755 n={n} className="hover:text-brand-strong" /></a> } // flag
function deep756(p: { className?: string }, d: number): { className?: string } { if (d > 0) return deep756(p, d - 1); return p }
function Tally756(props: { n: number; className?: string }) { return <span className={deep756(props, 2).className}>See all {props.n}</span> }
export function P756({ n }: { n: number }) { return <a href="/x"><Tally756 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally757(props: { n: number; className?: string }) { const box = { a: [THEME592], b: props.n > 0 ? [props] : [THEME592] }; const list = [box.a, box.b]; return <span className={list[props.n][0].className}>See all {props.n}</span> }
export function P757({ n }: { n: number }) { return <a href="/x"><Tally757 n={n} className="hover:text-brand-strong" /></a> } // flag
function wrap758(x?: string) { return [x] }
function Tally758(props: { n: number; className?: string }) { const [cls] = wrap758(props.className); return <span className={cls}>See all {props.n}</span> }
export function P758({ n }: { n: number }) { return <a href="/x"><Tally758 n={n} className="hover:text-brand-strong" /></a> } // flag
function box759(p: { className?: string }) { return { p: p } }
function Tally759(props: { n: number; className?: string }) { return <span className={box759(props).p.className}>See all {props.n}</span> }
export function P759({ n }: { n: number }) { return <a href="/x"><Tally759 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally760(props: { n: number; className?: string }) { return <span className={first691(...wrap758(props.className))}>See all {props.n}</span> }
export function P760({ n }: { n: number }) { return <a href="/x"><Tally760 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally761(props: { n: number; className?: string }) { const prefix: [string, string | undefined] = ['font-medium', props.className]; prefix.reverse(); return <span className={first691(...prefix)}>See all {props.n}</span> }
export function P761({ n }: { n: number }) { return <a href="/x"><Tally761 n={n} className="hover:text-brand-strong" /></a> } // flag
function first762(...parts: Array<string | undefined>) { let [t] = [parts]; if (parts.length > 1) [t] = [parts.slice(1)]; return t[0] }
function Tally762(props: { n: number; className?: string }) { return <span className={first762('font-medium', props.className)}>See all {props.n}</span> }
export function P762({ n }: { n: number }) { return <a href="/x"><Tally762 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally763(props: { n: number; className?: string }) { let { className: cls } = THEME592; if (props.n) cls = props.className ?? cls; return <span className={cls}>See all {props.n}</span> }
export function P763({ n }: { n: number }) { return <a href="/x"><Tally763 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally764(props: { n: number; className?: string }) { void pick700([props]); return <span className={pick700([THEME592])}>See all {props.n}</span> }
export function P764({ n }: { n: number }) { return <a href="/x"><Tally764 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally765({ n }: { n: number; className?: string }) { const sources = [THEME592]; return <span className={Object.assign({}, ...sources).className}>See all {n}</span> }
export function P765({ n }: { n: number }) { return <a href="/x"><Tally765 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally766(props: { n: number; className?: string }) { void wrap758(props.className); const [cls] = wrap758('font-medium'); return <span className={cls}>See all {props.n}</span> }
export function P766({ n }: { n: number }) { return <a href="/x"><Tally766 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally767(props: { n: number; className?: string }) { void box759(props); return <span className={box759(THEME592).p.className}>See all {props.n}</span> }
export function P767({ n }: { n: number }) { return <a href="/x"><Tally767 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally768(props: { n: number; className?: string }) { const prefix: [string] = ['font-medium']; return <span className={first691(...prefix, props.className)}>See all {props.n}</span> }
export function P768({ n }: { n: number }) { return <a href="/x"><Tally768 n={n} className="hover:text-brand-strong" /></a> } // clean
function pick769(...parts: Array<{ className?: string }>) { let [all]: [Array<{ className?: string }>] = [[THEME592]]; all = parts; const [p] = all; return p.className }
function Tally769(props: { n: number; className?: string }) { return <span className={pick769(props)}>See all {props.n}</span> }
export function P769({ n }: { n: number }) { return <a href="/x"><Tally769 n={n} className="hover:text-brand-strong" /></a> } // flag
const CONFIG770 = { label: 'Ready' }
export function P770({ n }: { n: number }) { let { label } = CONFIG770; if (n) label = 'See all 3'; return <span className="text-brand-strong">{label}</span> } // flag
function Tally771(props: { n: number; className?: string }) { const [[cls]] = [wrap758(props.className)]; return <span className={cls}>See all {props.n}</span> }
export function P771({ n }: { n: number }) { return <a href="/x"><Tally771 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally772(props: { n: number; className?: string }) { void wrap758(props.className); const [[cls]] = [wrap758('font-medium')]; return <span className={cls}>See all {props.n}</span> }
export function P772({ n }: { n: number }) { return <a href="/x"><Tally772 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally773(props: { n: number; className?: string }) { void pick769(props); return <span className={pick769(THEME592)}>See all {props.n}</span> }
export function P773({ n }: { n: number }) { return <a href="/x"><Tally773 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally774(props: { n: number; className?: string }) { const prefix = ['font-medium'] as const; Object.assign(prefix, [props.className]); return <span className={first691(...prefix)}>See all {props.n}</span> }
export function P774({ n }: { n: number }) { return <a href="/x"><Tally774 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally775(props: { n: number; className?: string }) { const parts: [string, string | undefined] = ['font-medium', props.className]; return <span className={first691(...parts)}>See all {props.n}</span> }
export function P775({ n }: { n: number }) { return <a href="/x"><Tally775 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally776(props: { n: number; className?: string }) { const sources = [props, THEME592]; return <span className={Object.assign({}, ...sources).className}>See all {props.n}</span> }
export function P776({ n }: { n: number }) { return <a href="/x"><Tally776 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally777(props: { n: number; className?: string }) { const parts: Array<string | undefined> = ['font-medium', props.className]; return <span className={first691(...parts)}>See all {props.n}</span> }
export function P777({ n }: { n: number }) { return <a href="/x"><Tally777 n={n} className="hover:text-brand-strong" /></a> } // clean
function Tally778(props: { n: number; className?: string }) { const parts: Array<string | undefined> = ['font-medium', props.className]; parts.shift(); return <span className={first691(...parts)}>See all {props.n}</span> }
export function P778({ n }: { n: number }) { return <a href="/x"><Tally778 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally779(props: { n: number; className?: string }) { const sources: Array<{ className?: string }> = [THEME592]; sources.push(props); return <span className={Object.assign({}, ...sources).className}>See all {props.n}</span> }
export function P779({ n }: { n: number }) { return <a href="/x"><Tally779 n={n} className="hover:text-brand-strong" /></a> } // flag
function Tally780(props: { n: number; className?: string }) { const parts: Array<string | undefined> = []; parts.push(props.className); return <span className={first691('font-medium', ...parts)}>See all {props.n}</span> }
export function P780({ n }: { n: number }) { return <a href="/x"><Tally780 n={n} className="hover:text-brand-strong" /></a> } // clean
