'use client'
/**
 * One trend chart's plot under the spec renderer, and the ways to read it (docs/design/analysis-trend-charts-spec-
 * 2026-10.md §3.7 A7, §3.9, §3.13; DESIGN_SYSTEM.md §10; E193). The plot scrolls inside its card's viewport, a named
 * region and Tab stop only while it overflows, and opens at the newest period, the one the legend and the metrics table
 * quote, behind A7's sticky gutter, which repeats the y axis once the plot's own has scrolled away.
 *
 * One values stop reads the chart a period at a time: a slider over the periods whose value text is the period's
 * readout (lib/charts/readout.ts), so a screen reader speaks it on focus and on every move. It is a transparent layer
 * laid over the viewport, after it in the Tab order: the pointer passes through it to the plot, its brand ring rings the
 * viewport whatever the plot's scroll, and a touch screen reader finds it anywhere on the chart. Left/Right (Down/Up) step a
 * period, Home/End jump to the oldest and newest, and a step past either end says so in a status line. It starts at the
 * newest period and keeps its period when focus leaves. Hover, a tap, or the keyboard paints the period's column wash
 * across the plot and shows its tooltip; pointing at a period takes over from the keyboard without moving focus or the
 * scroll, and the next key resumes the keyboard's own period. The tooltip stays while the pointer rests on it, and
 * Escape dismisses it before it collapses an expanded card (WCAG 1.4.13).
 *
 * Until its font has loaded (G4) the plot's box holds bones from its own plan, its gridlines and bars (§3.9 `loading`),
 * and the plot replaces them with a fade (DESIGN_SYSTEM.md §11, skeleton→content; E200).
 *
 * The wash, the gutter and the tooltip sit outside the plot's node (plotRef), whose SVG is what the PNG export
 * serialises, so none of them reaches the image (§3.11 rule 4). They paint in DOM order without a z-index: the wash
 * under the plot, the gutter over it, the tooltip over both and outside the viewport, so 200% text never clips it.
 */
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type RefObject } from 'react'
import { cx } from '@/components/ui'
import { useContentIn } from '@/hooks/useContentIn'
import { useOverflowRegion } from '@/hooks/useOverflowRegion'
import { columnOf, gutterCover, gutterCuts, slotAt, type ChartLayout } from '@/features/analysis/lib/charts/layout'
import type { ChartModel, ChartView } from '@/features/analysis/lib/charts/model'
import type { PeriodReadout } from '@/features/analysis/lib/charts/readout'
import type { ChartTokens } from '@/features/analysis/lib/charts/theme'
import { LegendSwatch } from './chartMarks'
import { bonesPlan, ChartBones } from './TrendChartBones'
import TrendChartSvg, { GutterOverlay } from './TrendChartSvg'

const STEP: Record<string, number> = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1 }
/** A press that moves less than this is a tap; more is the start of a swipe that scrolls the plot. */
const TAP_SLOP = 10

type Owner = 'keyboard' | 'pointer' | null

const focusVisible = (element: Element) => {
  try {
    return element.matches(':focus-visible')
  } catch {
    return true
  }
}

export default function TrendChartPlot({ model, layout, readouts, tokens, fontReady, uid, view, plotRef, onWidth }: {
  model: ChartModel
  layout: ChartLayout
  readouts: PeriodReadout[]
  tokens: ChartTokens
  /** Spec G4: the plot paints once its font has loaded; until then the stage holds the plot's box. */
  fontReady: boolean
  uid: string
  view: ChartView
  /** The node the PNG export serialises: the plot's box, holding the chart's SVG alone. */
  plotRef: RefObject<HTMLDivElement>
  /** The viewport's whole-pixel width, the width the plan is laid out at. */
  onWidth: (width: number) => void
}) {
  const cellRef = useRef<HTMLDivElement>(null)
  const viewportRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const tipRef = useRef<HTMLDivElement>(null)
  const { overflowing, regionProps } = useOverflowRegion(viewportRef, {
    label: `${model.title} chart. Scroll horizontally to view all periods.`,
  })
  const last = model.periods.length - 1
  // The keyboard's period, by key within its window: a new window (the period picker) starts again at the newest.
  const windowKey = model.periods.map((period) => period.key).join(' ')
  const [keyboard, setKeyboard] = useState<{ window: string; period: string } | null>(null)
  const found = keyboard?.window === windowKey ? model.periods.findIndex((period) => period.key === keyboard.period) : -1
  const keyIndex = found < 0 ? last : found
  const [hover, setHover] = useState<number | null>(null)
  const [owner, setOwner] = useState<Owner>(null)
  const [pinned, setPinned] = useState(false)
  const [scrollLeft, setScrollLeft] = useState(0)
  const [edge, setEdge] = useState('')
  const reveal = useRef(false)
  // The status line's end-of-range word, set a frame after it is cleared; a later key or a blur cancels it.
  const edgeFrame = useRef<number | null>(null)
  const tap = useRef<{ id: number; x: number; y: number } | null>(null)
  const contentIn = useContentIn(!fontReady)
  const active = owner === 'keyboard' ? keyIndex : owner === 'pointer' && hover != null ? Math.min(hover, last) : null
  const readout = active == null ? null : readouts[active]
  const gutter = overflowing && scrollLeft > 0 && fontReady
  // What the sticky gutter covers: the plot's own gutter, and the column a scroll leaves cut at its edge.
  const cover = gutter ? gutterCover(layout, scrollLeft) : layout.plotLeft

  // The plan follows the viewport's own width (never the SVG's, which would feed back), in whole pixels so the PNG
  // export draws the plot at the size it has on screen. A viewport not laid out yet (width 0) keeps the default.
  useLayoutEffect(() => {
    const viewport = viewportRef.current
    if (!viewport) return
    const measure = () => {
      const measured = Math.floor(viewport.clientWidth)
      if (measured > 0) onWidth(measured)
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    observer.observe(viewport)
    return () => observer.disconnect()
  }, [view, onWidth])

  // The sticky gutter follows the scroll. A scroll event arrives a frame late (and never in jsdom), so a scroll made
  // here syncs it at once.
  const syncScroll = () => {
    const viewport = viewportRef.current
    if (viewport) setScrollLeft(viewport.scrollLeft)
  }

  // Open at the newest period when a view or window starts to overflow: on first layout, after expanding or collapsing
  // (spec §3.10), whether or not the other view overflowed, and for a new window. Never on a resize or zoom, which would
  // lose the reader's place: a plot that overflows is planned at its minimum width, so a resize changes none of these.
  useLayoutEffect(() => {
    const viewport = viewportRef.current
    if (!viewport || !overflowing) return
    viewport.scrollLeft = viewport.scrollWidth
    syncScroll()
    // The view, the window and the overflow alone: never the layout or its width.
  }, [view, windowKey, overflowing])

  /** The period under a pointer (layout.ts slotAt), none where the sticky gutter or the plot's own gutter is. */
  const indexAt = (clientX: number) => {
    const viewport = viewportRef.current
    const stage = stageRef.current
    if (!viewport || !stage || clientX - viewport.getBoundingClientRect().left < cover) return null
    return slotAt(layout, clientX - stage.getBoundingClientRect().left)
  }

  /** The tooltip flush beside its column, inside the viewport's visible width: right of it, else left, else over it.
   *  Flush, so a pointer can cross from the column onto it without passing over another period (WCAG 1.4.13). */
  const placeTip = () => {
    const tip = tipRef.current
    const viewport = viewportRef.current
    if (!tip || !viewport || active == null) return
    const width = viewport.clientWidth
    const column = columnOf(layout, model.periods[active].key)
    const x = column.left - viewport.scrollLeft
    tip.style.maxWidth = `${width}px`
    const tipWidth = tip.offsetWidth
    let left = x + column.width
    if (left + tipWidth > width) left = x - tipWidth
    if (left < 0) left = Math.max(0, Math.min(width - tipWidth, x + (column.width - tipWidth) / 2))
    tip.style.left = `${Math.round(left)}px`
  }

  // A keyboard move or keyboard focus brings its column into the visible plot, right of the gutter; a pointer never
  // scrolls the chart. Then the tooltip takes its place.
  useLayoutEffect(() => {
    const viewport = viewportRef.current
    if (active == null || !viewport) return
    if (owner === 'keyboard' && reveal.current) {
      reveal.current = false
      const column = columnOf(layout, model.periods[active].key)
      if (column.left < viewport.scrollLeft + layout.plotLeft || column.left + column.width > viewport.scrollLeft + viewport.clientWidth) {
        viewport.scrollLeft = column.left + column.width / 2 - (layout.plotLeft + viewport.clientWidth) / 2
        syncScroll()
      }
    }
    placeTip()
  })

  const cancelEdge = () => {
    if (edgeFrame.current != null) cancelAnimationFrame(edgeFrame.current)
    edgeFrame.current = null
    setEdge('')
  }

  const dismiss = () => {
    setOwner(null)
    setPinned(false)
  }

  // A pointer's tooltip closes on Escape wherever focus is, ahead of the card's collapse, and a tapped one when the
  // reader presses anywhere outside the chart.
  useEffect(() => {
    if (owner !== 'pointer') return
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape' || event.defaultPrevented) return
      event.preventDefault()
      dismiss()
    }
    const away = (event: globalThis.PointerEvent) => {
      if (pinned && !cellRef.current?.contains(event.target as Node)) dismiss()
    }
    window.addEventListener('keydown', escape, true)
    document.addEventListener('pointerdown', away)
    return () => {
      window.removeEventListener('keydown', escape, true)
      document.removeEventListener('pointerdown', away)
    }
  }, [owner, pinned])

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      if (owner) {
        event.preventDefault()
        dismiss()
      }
      return
    }
    const to = event.key === 'Home' ? 0 : event.key === 'End' ? last : event.key in STEP ? keyIndex + STEP[event.key] : null
    if (to == null) return
    event.preventDefault()
    const next = Math.max(0, Math.min(last, to))
    setKeyboard({ window: windowKey, period: model.periods[next].key })
    setOwner('keyboard')
    setPinned(false)
    reveal.current = true
    // A step past either end changes no value, so the slider says nothing: the status line does, fresh each press.
    cancelEdge()
    if (next !== to) {
      const message = to < 0 ? 'Oldest period.' : 'Newest period.'
      edgeFrame.current = requestAnimationFrame(() => setEdge(message))
    }
  }

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'touch' || pinned) return
    // The tooltip is hoverable: resting on it keeps its period (WCAG 1.4.13).
    if (tipRef.current?.contains(event.target as Node)) return
    const index = indexAt(event.clientX)
    setHover(index)
    setOwner((current) => (index != null ? 'pointer' : current === 'pointer' ? null : current))
  }

  const onPointerLeave = (event: PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'touch' || pinned) return
    setOwner((current) => (current === 'pointer' ? null : current))
  }

  // A tap pins its period's tooltip and a second tap on it unpins it; a swipe that scrolls the plot pins nothing.
  const onPointerUp = (event: PointerEvent<HTMLDivElement>) => {
    const start = tap.current
    tap.current = null
    if (!start || start.id !== event.pointerId || Math.hypot(event.clientX - start.x, event.clientY - start.y) >= TAP_SLOP) return
    if (tipRef.current?.contains(event.target as Node)) return
    const index = indexAt(event.clientX)
    if (index == null || (pinned && owner === 'pointer' && hover === index)) {
      dismiss()
      return
    }
    setHover(index)
    setOwner('pointer')
    setPinned(true)
  }

  const column = active == null ? null : columnOf(layout, model.periods[active].key)
  return (
    <div ref={cellRef} className="relative min-w-0" onPointerMove={onPointerMove} onPointerLeave={onPointerLeave} onPointerUp={onPointerUp}
      onPointerDown={(event) => { tap.current = event.pointerType === 'mouse' ? null : { id: event.pointerId, x: event.clientX, y: event.clientY } }}
      onPointerCancel={() => { tap.current = null }}>
      {/* The overflow region's props, its role written as the literal the dialog gate can read (dialogAllowlist.spec.ts). */}
      <div ref={viewportRef} data-analysis-chart-scroll role={regionProps.role ? 'region' : undefined} tabIndex={regionProps.tabIndex}
        aria-label={regionProps['aria-label']} onScroll={(event) => { setScrollLeft(event.currentTarget.scrollLeft); placeTip() }}
        className="overflow-x-auto rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
        <div ref={stageRef} className="relative grid" style={{ width: layout.width, height: layout.height }}>
          {column && (
            <div aria-hidden="true" data-chart-wash className="pointer-events-none absolute top-0"
              style={{ left: column.left, width: column.width, height: layout.height, background: tokens.cursor }} />
          )}
          {!fontReady && <ChartBones plan={bonesPlan(layout)} />}
          <div ref={plotRef} data-analysis-chart={model.title} className={cx('relative col-start-1 row-start-1', contentIn)} style={{ width: layout.width, height: layout.height }}>
            {fontReady && <TrendChartSvg model={model} layout={layout} tokens={tokens} label={`${model.title} chart`} uid={uid} />}
          </div>
          {gutter && (
            <div aria-hidden="true" data-chart-gutter className="pointer-events-none sticky left-0 col-start-1 row-start-1 self-start justify-self-start">
              <GutterOverlay model={model} layout={layout} tokens={tokens} cover={cover} cuts={gutterCuts(layout, scrollLeft, cover)} />
            </div>
          )}
        </div>
      </div>
      <div role="slider" tabIndex={0} data-chart-values aria-label={`${model.title} chart values`}
        aria-valuemin={0} aria-valuemax={last} aria-valuenow={keyIndex} aria-valuetext={readouts[keyIndex]?.announcement}
        aria-orientation="horizontal" onKeyDown={onKeyDown}
        onFocus={(event) => {
          if (!focusVisible(event.currentTarget)) return
          setOwner('keyboard')
          reveal.current = true
        }}
        onBlur={() => {
          setOwner((current) => (current === 'keyboard' ? null : current))
          cancelEdge()
        }}
        className="pointer-events-none absolute inset-0 rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark" />
      {readout && (
        <div ref={tipRef} aria-hidden="true" data-chart-tooltip
          className="absolute rounded-xl border border-border-light bg-panel-light px-3 py-2.5 shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
          style={{ top: layout.panels[0]?.top ?? 0, width: 'max-content' }}>
          <p className="font-data text-xs" style={{ color: tokens.note }}>{readout.header}</p>
          <ul className="mt-1.5 space-y-1">
            {readout.rows.map((row) => (
              <li key={row.seriesKey} className="flex flex-wrap items-center gap-x-1.5 text-xs">
                <LegendSwatch item={row} tokens={tokens} />
                <span style={{ color: tokens.name }}>{row.label}</span>
                <span className="font-data">
                  <span style={{ color: tokens.figure }}>{row.figure}</span>
                  {row.calculated && <span style={{ color: tokens.note }}> · Calculated</span>}
                  {row.note && <span style={{ color: tokens.note }}> ({row.note})</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p role="status" className="sr-only">{edge}</p>
    </div>
  )
}
