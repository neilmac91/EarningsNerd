'use client'

/* =============================================================================
   DataTable — components/ui/DataTable.tsx
   -----------------------------------------------------------------------------
   Financial table wiring:
     - numeric columns render in the data face + tabular-nums (no jitter),
     - per-cell tone maps to the gain/loss/flat DATA colors — never the brand,
     - row hover BRIGHTENS,
     - built-in system states: loading (shimmer skeleton rows that preserve
       column layout), empty, error — pass your own nodes or use the defaults,
     - optional sortable headers: real <button>s with aria-sort + the brand
       focus ring (pass `sortable` on the column and `sort`/`onSort` on the table),
     - density: 'comfortable' (default, py-2.5) | 'compact' — 4px-grid row
       padding + 12px text (the micro-annotation floor; never smaller), with
       skeleton rows matched to each rhythm so loading doesn't jump,
     - stickyHeader: thead sticks within the scroll container on an opaque
       panel surface with a token hairline underneath (no shadow). Uses
       border-separate so the hairline sticks with the header; the row
       hairlines live on the cells, which renders identically.
     - stickyFirstColumn: the first column (both header and body cells)
       sticks to the left of the scroll container on an opaque panel
       surface with a token hairline on its right edge, so a wide financial
       table can scroll horizontally without losing the row label. Body
       cells retain an opaque fill on hover; a translucent replacement
       would expose the values scrolling beneath the label. Composes cleanly
       with stickyHeader — the header's first cell (the "corner") gets a
       higher z-index than both plain sticky-header cells and the sticky
       column's body cells, so it is never overlapped by either. With snapColumns,
       release the sticky label when it cannot fit beside one whole period;
       the label then scrolls with the table and has its own snap stop.
============================================================================= */

import { useLayoutEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useContentIn } from '../../hooks/useContentIn'
import { useOverflowRegion } from '../../hooks/useOverflowRegion'
import { cx } from './cx'
import { Skeleton } from './Skeleton'

export type CellTone = 'gain' | 'loss' | 'flat'

export type Density = 'comfortable' | 'compact'

/* Row rhythm per density. Compact stays on the 4px grid (py-1 = 4px) and
   drops cell text to 12px — the floor. Skeleton bar + padding sum to the same
   row height as a real row (12 + 6·2 = 24px = 4 + 16 + 4) so loading ⇄ loaded
   doesn't shift the layout. */
const DENSITY: Record<Density, { text: string; headerY: string; cellY: string; skelY: string; skelBar: string }> = {
  comfortable: { text: 'text-sm', headerY: 'py-2', cellY: 'py-2.5', skelY: 'py-3.5', skelBar: 'h-3.5' },
  compact: { text: 'text-xs', headerY: 'py-1', cellY: 'py-1', skelY: 'py-1.5', skelBar: 'h-3' },
}

const TONE: Record<CellTone, string> = {
  // -text variants: the 600-level green/red are graphic-only (3:1) — text needs the 700s on cream
  gain: 'font-semibold text-gain-text dark:text-gain-dark',
  loss: 'font-semibold text-loss-text dark:text-loss-dark',
  flat: 'text-flat-light dark:text-flat-dark',
}

export interface Column<T> {
  key: string
  header: ReactNode
  align?: 'left' | 'right'
  /** Money / % / tickers — data face + tabular-nums. */
  numeric?: boolean
  render?: (row: T) => ReactNode
  /** Map a row to gain/loss/flat coloring for this cell. */
  tone?: (row: T) => CellTone | undefined
  /** Header becomes a sort button (needs `onSort` on the table). */
  sortable?: boolean
  /** Render the body cell as a semantic row header. Opt-in; unrelated tables retain td cells. */
  rowHeader?: boolean
  /** Extra classes for this column's header and body cells (an inset that sets prose apart from figures). */
  className?: string
}

export interface SortState {
  key: string
  dir: 'asc' | 'desc'
}

export interface DataTableProps<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T, index: number) => string
  loading?: boolean
  skeletonRows?: number
  /** Current sort — sorted header shows ▲/▼ and sets aria-sort. */
  sort?: SortState
  onSort?: (key: string) => void
  empty?: ReactNode
  error?: ReactNode
  /** Row rhythm — 'compact' for dense financial screens. Default 'comfortable'. */
  density?: Density
  /** Header sticks to the top of the nearest scroll container (give the wrapper a height via `className`). */
  stickyHeader?: boolean
  /** First column sticks to the left of the scroll container — keeps the row label visible on
   *  a wide, horizontally-scrolling table. Composes with stickyHeader. */
  stickyFirstColumn?: boolean
  /** Accessible summary, rendered sr-only. */
  caption?: string
  /** Fixed layout uses explicit CSS widths (including rem or responsive CSS variables). */
  layout?: 'auto' | 'fixed'
  colWidths?: readonly string[]
  /** Narrow horizontal insets for dense, fixed-width columns; independent of row density. */
  cellPadding?: 'standard' | 'compact'
  /** Opt-in, named keyboard scroll region; child controls retain their own keys.
   *  startAtEndOnMobile also limits the hint to phones with earlier columns off-screen. */
  scrollRegion?: { label: string; hint?: string; startAtEndOnMobile?: boolean }
  /** Equal data columns after the optional sticky label column snap to their full width. */
  snapColumns?: boolean
  /** 'top': body cells align to the top, so a figure shares its row label's first line, and header cells to the
   *  bottom, so one- and two-line labels sit on the rule together. Default 'middle' (the browser's). */
  verticalAlign?: 'middle' | 'top'
  /** 'well': the figures sit on their own sheet inside the panel (platinum white / near-black, the `well` tokens) with
   *  the stronger `rule` hairlines, while the heading row and the row-label column keep the panel surface and its inks;
   *  a hovered row strengthens its two rules instead of changing its fill, so no text pair changes contrast under the
   *  pointer and the sticky label stays opaque. Default 'panel'. */
  surface?: 'panel' | 'well'
  /** Keep the column headings in view while the page scrolls past a tall table. CSS cannot stick a header to the page
   *  from inside the horizontal scroll container, so an aria-hidden copy of the heading row rides a zero-height sticky
   *  rail under the site header (--site-header-h) and follows the table's scrollLeft. The real <thead> stays the one
   *  screen readers read. Needs layout="fixed". */
  pageHeader?: boolean
  className?: string
}

const ROW_BORDER = 'border-t border-border-light dark:border-border-dark'

/** The page heading rail's height on <html> while it shows (pageHeader); app/globals.css adds it to scroll-padding-top. */
export const TABLE_RAIL_HEIGHT_PROPERTY = '--table-rail-h'

// The figure sheet (surface="well"): the figures sit on the sheet; the heading row and the row-label column keep the
// panel surface and the panel's own inks, so the frame of labels reads slightly apart from the data it labels.
const WELL = {
  // The frame wraps the scroll container rather than bordering it, so the scrollport and the container's box stay
  // one (snap stops, the sticky inset and focus scrolling all measure the container's own box). Its rule is an
  // outline, drawn outside that box: a border would inset the container, whose 16px corners would then overhang the
  // frame's 15px inner curve by a sliver of sheet beside the panel-coloured heading row.
  frame: 'rounded-xl outline outline-1 outline-rule-light bg-well-light dark:outline-rule-dark dark:bg-well-dark',
  edge: 'bg-panel-light dark:bg-panel-dark',
  rowBorder: 'border-t border-rule-light dark:border-rule-dark',
  labelCol: 'border-r border-rule-light dark:border-rule-dark',
  head: 'text-left text-xs uppercase tracking-eyebrow text-text-secondary-light dark:text-text-secondary-dark',
  row: '[&:hover>*]:border-t-rule-strong-light dark:[&:hover>*]:border-t-rule-strong-dark [&:hover+tr>*]:border-t-rule-strong-light dark:[&:hover+tr>*]:border-t-rule-strong-dark',
}

const STICKY_TH =
  // Opaque token surface + token hairline — collapsed borders don't stick, so the
  // table switches to border-separate and the th carries its own bottom border.
  // z-index is applied separately (headerZIndex below) so exactly one z-* utility is ever
  // present per cell — mixing z-10 here with a per-cell override is a Tailwind ordering trap
  // (utility precedence follows generated-stylesheet order, not the HTML class attribute order).
  'sticky top-0 bg-panel-light dark:bg-panel-dark border-b border-border-light dark:border-border-dark'

// First-column sticky treatment, shared by header and body cells (see the file-header note).
// z-index is likewise applied separately per cell (headerZIndex / bodyZIndex below).
const STICKY_COL_BASE =
  'sticky left-0 bg-panel-light dark:bg-panel-dark border-r border-border-light dark:border-border-dark'

// Exactly one z-index decision per cell: the "corner" (sticky header × sticky first column)
// must beat both an ordinary sticky-header sibling and a sticky-column body cell scrolling
// under it; a plain sticky header cell or a plain sticky first-column cell only needs to beat
// unstickied siblings at the default stacking level.
const headerZIndex = (isFirstCol: boolean, stickyHeader: boolean): string | undefined =>
  isFirstCol && stickyHeader ? 'z-20' : isFirstCol || stickyHeader ? 'z-10' : undefined
const bodyZIndex = (isFirstCol: boolean): string | undefined => (isFirstCol ? 'z-[5]' : undefined)
const nearestColumn = (stops: number[], position: number) => stops.reduce((best, stop, index) =>
  Math.abs(stop - position) < Math.abs(stops[best] - position) ? index : best, 0)

export function DataTable<T extends Record<string, unknown>>({
  columns,
  rows,
  rowKey,
  loading = false,
  skeletonRows = 4,
  sort,
  onSort,
  empty,
  error,
  density = 'comfortable',
  stickyHeader = false,
  stickyFirstColumn = false,
  caption,
  layout = 'auto',
  colWidths,
  cellPadding = 'standard',
  scrollRegion,
  snapColumns = false,
  verticalAlign = 'middle',
  surface = 'panel',
  pageHeader = false,
  className,
}: DataTableProps<T>) {
  const colSpan = columns.length
  const well = surface === 'well'
  const stickyColBase = well ? cx('sticky left-0', WELL.edge, WELL.labelCol) : STICKY_COL_BASE
  // On the sheet the row-label column keeps the panel surface and its rule whether it sticks or, released on a narrow
  // screen, scrolls with the figures.
  const wellLabel = (colIndex: number, column: Column<T>, stuck: boolean) =>
    well && !stuck && colIndex === 0 && (stickyFirstColumn || !!column.rowHeader) ? cx(WELL.edge, WELL.labelCol) : undefined
  const rowBorderClass = well ? WELL.rowBorder : ROW_BORDER
  const showRows = !loading && !error && rows.length > 0
  const d = DENSITY[density]
  const inset = cellPadding === 'compact' ? 'px-px md:px-1' : 'px-3'
  const scrollRef = useRef<HTMLDivElement>(null)
  const tableRef = useRef<HTMLTableElement>(null)
  const geometry = useRef({ step: 0, labelWidth: 0, viewportWidth: 0, inset: 0, range: 0, stops: [] as number[], column: 0 })
  const initialized = useRef(false)
  const [mobileHint, setMobileHint] = useState<'absent' | 'hidden' | 'visible'>('absent')
  const [stickyFits, setStickyFits] = useState(true)
  const stickyColumn = stickyFirstColumn && (!snapColumns || stickyFits)
  const hintId = useId()
  const fixedWidth = layout === 'fixed' && colWidths?.length === columns.length
    ? `max(100%, calc(${colWidths.join(' + ')}))` : undefined
  const startAtEndOnMobile = scrollRegion?.startAtEndOnMobile
  const hasScrollRegion = !!scrollRegion
  const { overflowing: overflows, regionProps } = useOverflowRegion(scrollRef, {
    enabled: hasScrollRegion,
    label: scrollRegion?.label,
    describedBy: scrollRegion?.hint && (!startAtEndOnMobile || mobileHint === 'visible') ? hintId : undefined,
  })
  const renderHint = !!scrollRegion?.hint && overflows && (!startAtEndOnMobile || mobileHint !== 'absent')
  const showHint = renderHint && (!startAtEndOnMobile || mobileHint === 'visible')

  useLayoutEffect(() => {
    const scroll = scrollRef.current
    const table = tableRef.current
    if (!scroll || !table || (!snapColumns && !hasScrollRegion)) return
    const dimensions = () => {
      const headers = table.tHead?.rows[0]?.cells
      return {
        headers,
        labelWidth: stickyFirstColumn ? headers?.[0]?.getBoundingClientRect().width ?? 0 : 0,
        step: headers?.[stickyFirstColumn ? 1 : 0]?.getBoundingClientRect().width ?? 0,
        viewportWidth: scroll.clientWidth,
      }
    }
    const rememberColumn = () => {
      const current = geometry.current
      const { step, labelWidth, viewportWidth } = dimensions()
      // Native snapping can emit scroll before ResizeObserver reports enlarged text.
      // Keep the prior column until its old stops have been replaced by this geometry.
      if (step === current.step && labelWidth === current.labelWidth && viewportWidth === current.viewportWidth) {
        current.column = nearestColumn(current.stops, scroll.scrollLeft)
      }
      setMobileHint(!window.matchMedia('(max-width: 639px)').matches ? 'absent'
        : scroll.scrollLeft > 1 ? 'visible' : 'hidden')
    }
    const measure = () => {
      const previous = geometry.current
      // Remove the old pad before measuring: resize and text-size changes must never compound it.
      if (snapColumns) scroll.style.paddingInlineEnd = '0px'
      const { headers, labelWidth, step, viewportWidth } = dimensions()
      if (!step || !scroll.clientWidth) return
      const fits = scroll.clientWidth >= labelWidth + step
      setStickyFits(fits)
      const insetWidth = stickyFirstColumn && (!snapColumns || fits) ? labelWidth : 0
      const range = Math.max(0, scroll.scrollWidth - scroll.clientWidth)
      // The unstuck label has its own stop; period stops then start after its width.
      const firstStop = labelWidth - insetWidth
      // The range ends on a whole stop: past the first period's stop, a whole number of periods; short of it (a
      // table that overflows by less than its unstuck label, one period under enlarged text), that stop itself,
      // never a point inside the label.
      const pad = !snapColumns || range === 0 ? 0
        : range < firstStop ? firstStop - range : (step - (range - firstStop) % step) % step
      if (snapColumns) {
        scroll.style.paddingInlineEnd = `${pad}px`
        scroll.style.scrollPaddingInlineStart = `${insetWidth}px`
      }
      const wholeRange = range + pad
      const stops = Array.from(headers ?? [], (_, index) => Math.min(wholeRange,
        index === 0 ? 0 : Math.max(0, firstStop + (index - Number(stickyFirstColumn)) * step)))
      geometry.current = { step, labelWidth, viewportWidth, inset: insetWidth, range: wholeRange, stops, column: previous.column }
      const newest = !initialized.current && startAtEndOnMobile && window.matchMedia('(max-width: 639px)').matches
      if (snapColumns) scroll.scrollLeft = newest ? wholeRange : stops[Math.min(previous.column, stops.length - 1)] ?? 0
      rememberColumn()
      initialized.current = true
    }
    measure()
    const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(measure)
    observer?.observe(scroll)
    observer?.observe(table)
    scroll.addEventListener('scroll', rememberColumn)
    window.addEventListener('resize', measure)
    return () => {
      observer?.disconnect()
      scroll.removeEventListener('scroll', rememberColumn)
      window.removeEventListener('resize', measure)
      scroll.style.paddingInlineEnd = ''
      scroll.style.scrollPaddingInlineStart = ''
    }
  }, [snapColumns, stickyFirstColumn, stickyFits, fixedWidth, startAtEndOnMobile, hasScrollRegion])

  // Page heading rail (pageHeader): the heading row's measured widths, the table's scrollLeft, shown only while the
  // real <thead> has passed under the site header and some of the table is still below it. Its copy of the headings
  // mounts only while it shows, so the page holds no second set of heading text until a reader needs one; scrolling
  // writes styles, and React renders only when the rail appears or goes.
  const railRef = useRef<HTMLDivElement>(null)
  const railBarRef = useRef<HTMLDivElement>(null)
  const railTrackRef = useRef<HTMLDivElement>(null)
  const frameRef = useRef<HTMLDivElement>(null)
  const [railWidths, setRailWidths] = useState<number[]>([])
  const [railShown, setRailShown] = useState(false)
  const railOn = pageHeader && layout === 'fixed'
  const followRail = () => {
    const scroll = scrollRef.current
    const bar = railBarRef.current
    const track = railTrackRef.current
    if (!scroll || !bar || !track) return
    bar.style.width = `${(frameRef.current ?? scroll).offsetWidth}px`
    track.style.transform = `translateX(${-scroll.scrollLeft}px)`
  }
  useLayoutEffect(() => {
    const scroll = scrollRef.current
    const table = tableRef.current
    const rail = railRef.current
    if (!railOn || !scroll || !table || !rail) return
    let frame = 0
    const show = () => {
      frame = 0
      const head = table.tHead?.getBoundingClientRect()
      const whole = table.getBoundingClientRect()
      const line = parseFloat(getComputedStyle(rail).top) || 0
      // Stuck at the line: under an ancestor that clips overflow (the landing demo's mockup frame, a locked preview)
      // that box is the rail's scroll container, so it never sticks to the page and must not show or reserve padding.
      const stuck = Math.abs(rail.getBoundingClientRect().top - line) < 1
      setRailShown(!!head && stuck && head.top < line - 0.5 && whole.bottom > line + head.height)
    }
    const queue = () => { if (!frame) frame = requestAnimationFrame(show) }
    const measure = () => {
      const widths = Array.from(table.tHead?.rows[0]?.cells ?? [], (cell) => cell.getBoundingClientRect().width)
      setRailWidths((prev) => prev.length === widths.length && prev.every((w, i) => Math.abs(w - widths[i]) < 0.01) ? prev : widths)
      followRail()
      queue()
    }
    measure()
    const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(measure)
    observer?.observe(scroll)
    observer?.observe(table)
    scroll.addEventListener('scroll', followRail, { passive: true })
    window.addEventListener('scroll', queue, { passive: true })
    window.addEventListener('resize', queue)
    return () => {
      observer?.disconnect()
      scroll.removeEventListener('scroll', followRail)
      window.removeEventListener('scroll', queue)
      window.removeEventListener('resize', queue)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [railOn])
  // The rail's copy has just mounted (or its widths changed): place it before paint.
  useLayoutEffect(() => { if (railShown) followRail() }, [railShown, railWidths])
  // While the rail shows it covers the strip under the site header, so it publishes its height on <html>
  // (TABLE_RAIL_HEIGHT_PROPERTY) for the page's scroll padding: a figure reached by Tab or Shift+Tab, or scrolled into
  // view, lands below the rail, never under it (WCAG 2.2 SC 2.4.11). Measured on every reflow; cleared when it goes.
  useLayoutEffect(() => {
    const bar = railBarRef.current
    if (!railShown || !bar) return
    const root = document.documentElement
    const measure = () => root.style.setProperty(TABLE_RAIL_HEIGHT_PROPERTY, `${Math.ceil(bar.getBoundingClientRect().height)}px`)
    measure()
    // The rail can appear after a focus scroll that aligned a figure under the header alone (a row taller than the
    // heading row, reached while the rail was hidden): bring that figure out from under it, now the padding counts it.
    const focused = document.activeElement
    if (focused instanceof HTMLElement && scrollRef.current?.contains(focused) && focused.getBoundingClientRect().top < bar.getBoundingClientRect().bottom) {
      focused.scrollIntoView({ block: 'nearest', inline: 'nearest' })
    }
    const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(measure)
    observer?.observe(bar)
    return () => {
      observer?.disconnect()
      root.style.removeProperty(TABLE_RAIL_HEIGHT_PROPERTY)
    }
  }, [railShown])
  const frame = (node: ReactNode) => (well ? <div ref={frameRef} className={WELL.frame}>{node}</div> : node)
  const headClass = well ? WELL.head : 'text-left text-xs uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-tertiary-dark'
  const railCell = (c: Column<T>, index: number, corner: boolean) => (
    <div
      key={c.key}
      style={{ width: railWidths[index], flex: 'none' }}
      className={cx(
        inset, d.headerY, 'flex flex-col font-semibold',
        verticalAlign === 'top' ? 'justify-end' : 'justify-center',
        c.className,
        c.align === 'right' && 'items-end text-right',
        corner && (well ? 'border-r border-rule-light dark:border-rule-dark' : 'border-r border-border-light dark:border-border-dark'),
      )}
    >
      {c.header}
    </div>
  )

  // Skeleton→content handoff: when `loading` flips false, whatever replaces the
  // skeleton rows (data, empty, error) crossfades in; tables that never load
  // don't animate on first paint (hooks/useContentIn).
  const enterClass = useContentIn(loading)

  // Row hairlines sit on the cells (renders identically to tr borders) so they
  // survive border-separate. With a sticky header the th's border-b already
  // draws the first hairline — the first body row skips its border-t.
  const rowBorder = (i: number) => (stickyHeader && i === 0 ? undefined : rowBorderClass)

  return (
    <>
    {renderHint && <p id={hintId} aria-hidden={!showHint || undefined} className={cx('mb-2 text-xs text-text-secondary-light dark:text-text-secondary-dark', !showHint && 'invisible')}>{scrollRegion!.hint}</p>}
    {railOn && (
      <div ref={railRef} aria-hidden="true" data-table-header-rail className="pointer-events-none sticky top-[var(--site-header-h,4rem)] z-sticky h-0 print:hidden">
        {railShown && <div
          ref={railBarRef}
          // The bar takes the pointer: passed through, a click on a heading the reader sees would open the figure
          // hidden under it. A horizontal wheel over it still moves the table it copies.
          onWheel={(event) => { if (event.deltaX && scrollRef.current) scrollRef.current.scrollLeft += event.deltaX }}
          className={cx(
            'pointer-events-auto flex overflow-hidden', headClass, d.text,
            well ? cx('outline outline-1 outline-rule-light dark:outline-rule-dark', WELL.edge) : 'border-b border-border-light bg-panel-light dark:border-border-dark dark:bg-panel-dark',
          )}
        >
          {stickyColumn && railCell(columns[0], 0, true)}
          <div className="relative min-w-0 flex-1 overflow-hidden">
            <div ref={railTrackRef} className="flex w-max">
              {columns.map((c, index) => (stickyColumn && index === 0 ? null : railCell(c, index, false)))}
            </div>
          </div>
        </div>}
      </div>
    )}
    {frame(
    <div
      ref={scrollRef}
      {...regionProps}
      className={cx(
        (scrollRegion || snapColumns) && 'relative',
        well && 'rounded-xl',
        stickyHeader ? 'overflow-auto' : 'overflow-x-auto',
        scrollRegion && (well ? '' : 'rounded'),
        scrollRegion && 'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
        snapColumns && 'snap-x snap-mandatory',
        className,
      )}
      onKeyDown={scrollRegion ? (event) => {
        if (event.target !== event.currentTarget || event.altKey || event.ctrlKey || event.metaKey) return
        const scroll = event.currentTarget
        const step = geometry.current.step || scroll.clientWidth
        if (!step) return
        const range = Math.max(0, scroll.scrollWidth - scroll.clientWidth)
        const stops = [...new Set(geometry.current.stops)]
        const pageSize = Math.max(step, scroll.clientWidth - geometry.current.inset)
        const target = event.key === 'ArrowRight' ? stops.find(stop => stop > scroll.scrollLeft + 1) ?? range
          : event.key === 'ArrowLeft' ? stops.findLast(stop => stop < scroll.scrollLeft - 1) ?? 0
            : event.key === 'PageDown' ? stops.find(stop => stop >= scroll.scrollLeft + pageSize) ?? range
              : event.key === 'PageUp' ? stops.findLast(stop => stop <= scroll.scrollLeft - pageSize) ?? 0
                : event.key === 'Home' ? 0 : event.key === 'End' ? range : undefined
        if (target == null) return
        event.preventDefault()
        scroll.scrollLeft = Math.max(0, Math.min(target, range))
        geometry.current.column = nearestColumn(geometry.current.stops, scroll.scrollLeft)
      } : undefined}
      onFocusCapture={snapColumns ? (event) => {
        if (event.target === event.currentTarget) return
        const cell = (event.target as HTMLElement).closest('td, th')
        const scroll = event.currentTarget
        const { step, inset: stickyWidth, stops } = geometry.current
        if (!cell || !scroll.contains(cell) || !step || (cell === cell.parentElement?.firstElementChild && stickyColumn)) return
        const bounds = cell.getBoundingClientRect()
        const viewport = scroll.getBoundingClientRect()
        // Choose an actual snap stop that contains the whole cell. Native focus scrolling
        // alone may snap again and put the control back beneath the label or past the edge.
        const first = scroll.scrollLeft + bounds.right - viewport.right
        const last = scroll.scrollLeft + bounds.left - viewport.left - stickyWidth
        if (bounds.left < viewport.left + stickyWidth - 1 || bounds.right > viewport.right + 1) {
          const available = stops.filter(stop => stop >= first - 1 && stop <= last + 1)
          const target = bounds.left < viewport.left + stickyWidth ? available.at(-1) : available[0]
          if (target != null) {
            scroll.scrollLeft = target
            geometry.current.column = stops.indexOf(target)
          }
        }
      } : undefined}
    >
      <table
        ref={tableRef}
        style={fixedWidth ? { width: fixedWidth } : undefined}
        className={cx(
          'w-full',
          layout === 'fixed' && 'table-fixed',
          d.text,
          stickyHeader || stickyFirstColumn ? 'border-separate border-spacing-0' : 'border-collapse'
        )}
        aria-busy={loading || undefined}
      >
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        {layout === 'fixed' && colWidths && <colgroup>{colWidths.map((width, index) => <col key={columns[index]?.key ?? index} style={{ width }} />)}</colgroup>}
        <thead>
          {/* 12px uppercase metric-label header — eyebrow tracking 0.08em (--track-eyebrow), matching .markdown-body th */}
          <tr className={headClass}>
            {columns.map((c, colIndex) => {
              const sorted = sort && sort.key === c.key ? sort.dir : undefined
              const isFirstCol = colIndex === 0 && stickyColumn
              return (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={sorted === 'asc' ? 'ascending' : sorted === 'desc' ? 'descending' : undefined}
                  className={cx(
                    inset, 'font-semibold',
                    snapColumns && !isFirstCol && 'snap-start',
                    d.headerY,
                    verticalAlign === 'top' && 'align-bottom',
                    c.className,
                    c.align === 'right' && 'text-right',
                    stickyHeader && STICKY_TH,
                    well && WELL.edge,
                    isFirstCol && stickyColBase,
                    wellLabel(colIndex, c, isFirstCol),
                    headerZIndex(isFirstCol, stickyHeader)
                  )}
                >
                  {c.sortable && onSort ? (
                    <button
                      type="button"
                      onClick={() => onSort(c.key)}
                      className={cx(
                        'inline-flex items-center gap-1 rounded uppercase tracking-eyebrow',
                        // On the sheet the heading rests in secondary, which dark primary all but meets (1.05:1).
                        well ? 'hover:text-text-primary-light dark:hover:text-white' : 'hover:text-text-primary-light dark:hover:text-text-primary-dark',
                        'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
                        c.align === 'right' && 'flex-row-reverse',
                      )}
                    >
                      {c.header}
                      <span
                        aria-hidden="true"
                        className={cx(
                          // eslint-disable-next-line no-restricted-syntax -- aria-hidden sort glyph, not type (DS-08 exemption)
                          'text-[9px] leading-none',
                          sorted ? 'text-brand-strong dark:text-brand-strong-dark' : 'opacity-40',
                        )}
                      >
                        {sorted === 'asc' ? '▲' : '▼'}
                      </span>
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody className={enterClass}>
          {loading
            ? Array.from({ length: skeletonRows }).map((_, r) => (
                <tr key={r}>
                  {columns.map((c, colIndex) => {
                    // Skeleton rows keep the same sticky first-column treatment as real rows, so
                    // a loading table scrolled right doesn't snap the label column into place
                    // when data lands.
                    const isFirstCol = colIndex === 0 && stickyColumn
                    return (
                      <td
                        key={c.key}
                        className={cx(
                          inset,
                          d.skelY,
                          rowBorder(r),
                          isFirstCol && stickyColBase,
                          wellLabel(colIndex, c, isFirstCol),
                          bodyZIndex(isFirstCol)
                        )}
                      >
                        <Skeleton className={cx(d.skelBar, c.align === 'right' ? 'ml-auto w-14' : 'w-24')} />
                      </td>
                    )
                  })}
                </tr>
              ))
            : null}

          {!loading && error ? (
            <tr>
              <td colSpan={colSpan} className={cx('px-3 py-6', rowBorder(0))}>
                {error}
              </td>
            </tr>
          ) : null}

          {!loading && !error && rows.length === 0 ? (
            <tr>
              <td colSpan={colSpan} className={cx('px-3 py-6', rowBorder(0))}>
                {empty ?? (
                  <p className="text-center text-sm text-text-tertiary-light dark:text-text-tertiary-dark">
                    No results.
                  </p>
                )}
              </td>
            </tr>
          ) : null}

          {showRows
            ? rows.map((row, i) => (
                <tr
                  key={rowKey(row, i)}
                  // Light sticky labels brighten with the row; dark labels keep their opaque
                  // panel fill. Replacing that fill with the row's translucent white tint
                  // would let horizontally scrolled values show through the sticky label.
                  className={well ? WELL.row : 'group transition-colors hover:bg-white dark:hover:bg-white/[0.03]'}
                >
                  {columns.map((c, colIndex) => {
                    const tone = c.tone?.(row)
                    const isFirstCol = colIndex === 0 && stickyColumn
                    const Cell = c.rowHeader ? 'th' : 'td'
                    return (
                      <Cell
                        key={c.key}
                        scope={c.rowHeader ? 'row' : undefined}
                        className={cx(
                          inset,
                          c.rowHeader && cx('font-normal', c.align !== 'right' && 'text-left'),
                          snapColumns && !isFirstCol && 'snap-start',
                          (snapColumns || verticalAlign === 'top') && 'align-top',
                          c.className,
                          d.cellY,
                          rowBorder(i),
                          c.align === 'right' && 'text-right',
                          c.numeric && 'font-data tabular-nums',
                          tone && TONE[tone],
                          isFirstCol && (well ? stickyColBase : cx(STICKY_COL_BASE, 'group-hover:bg-white dark:group-hover:bg-panel-dark')),
                          wellLabel(colIndex, c, isFirstCol),
                          bodyZIndex(isFirstCol)
                        )}
                      >
                        {c.render ? c.render(row) : (row[c.key] as ReactNode)}
                      </Cell>
                    )
                  })}
                </tr>
              ))
            : null}
        </tbody>
      </table>
    </div>
    )}
    </>
  )
}
