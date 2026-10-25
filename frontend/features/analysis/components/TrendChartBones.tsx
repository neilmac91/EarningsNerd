/**
 * The spec renderer's loading state (spec §3.9 `loading`, G4; E200): bones in the shape of a trend chart, its gridlines
 * and its bars, as DESIGN_SYSTEM.md §11 asks of a view that loads. A plot waiting for its font shows them in its own
 * box, from its own plan (TrendChartPlot), and the grid waiting for the renderer's chunk shows four cards of them at the
 * card's height (TrendCharts' next/dynamic `loading`). Bones are `Skeleton`s, so a reduced-motion reader gets them
 * still. This module rides the route's own chunk, so it names nothing of the renderer's.
 */
import { Card, Skeleton } from '@/components/ui'
import type { ChartLayout } from '@/features/analysis/lib/charts/layout'

/** The geometry the bones take, in the plot's own px: its box, its plot rect's sides, each panel's band, its slots. */
export interface BonesPlan {
  width: number
  height: number
  plotLeft: number
  plotRight: number
  panels: { top: number; height: number }[]
  slots: number
  barWidth: number
}

/** A desktop card's annual plot (spec §3.7, 502 px wide and CARD_HEIGHT tall), for the grid before the renderer has a
 *  plan; layout.ts stays out of this chunk, so trend-charts-v2.spec.tsx ties the height to it. */
export const CARD_BONES: BonesPlan = { width: 502, height: 320, plotLeft: 48, plotRight: 494, panels: [{ top: 24, height: 244 }], slots: 8, barWidth: 24 }

/** A bar's height in its panel, a fraction cycled over the slots: bones read as bars, never as data. */
const BAR_SHAPE = [0.55, 0.7, 0.45, 0.8, 0.6, 0.75, 0.5, 0.85]
/** Gridlines a panel: its top, two between, and its baseline, each this many px. */
const GRIDLINES = 4
const GRIDLINE = 2

export const bonesPlan = (layout: ChartLayout): BonesPlan => ({
  width: layout.width,
  height: layout.height,
  plotLeft: layout.plotLeft,
  plotRight: layout.plotRight,
  panels: layout.panels.map((box) => ({ top: box.top, height: box.height })),
  slots: Math.max(1, Math.round((layout.plotRight - layout.plotLeft) / layout.slot)),
  barWidth: layout.barWidth,
})

/** One bone at its place in the box: the place on a wrapper, since `Skeleton` sets its own `relative`. */
function Bone({ left, width, top, height }: { left: string; width: string; top: string; height: string }) {
  return (
    <div className="absolute" style={{ left, width, top, height }}>
      <Skeleton className="h-full w-full" />
    </div>
  )
}

/** A plot's bones, laid over its box in percent of the plan, so a box of any width keeps their shape. */
export function ChartBones({ plan }: { plan: BonesPlan }) {
  const x = (px: number) => `${(px / plan.width) * 100}%`
  const y = (px: number) => `${(px / plan.height) * 100}%`
  const slot = (plan.plotRight - plan.plotLeft) / plan.slots
  return (
    <div aria-hidden="true" data-chart-bones className="pointer-events-none absolute inset-0">
      {plan.panels.map((panel, p) => (
        <div key={p}>
          {Array.from({ length: GRIDLINES }, (_, line) => (
            <Bone key={`grid${line}`} left={x(plan.plotLeft)} width={x(plan.plotRight - plan.plotLeft)}
              top={y(panel.top + (panel.height * line) / (GRIDLINES - 1) - 1)} height={y(GRIDLINE)} />
          ))}
          {Array.from({ length: plan.slots }, (_, index) => {
            const height = panel.height * BAR_SHAPE[index % BAR_SHAPE.length]
            return (
              <Bone key={`bar${index}`} left={x(plan.plotLeft + slot * (index + 0.5) - plan.barWidth / 2)} width={x(plan.barWidth)}
                top={y(panel.top + panel.height - height)} height={y(height)} />
            )
          })}
        </div>
      ))}
    </div>
  )
}

/** The grid of four cards while the renderer's chunk loads: each card's header, a two-line legend and its 320 px plot
 *  (spec §3.9). One status names the wait; the bones are hidden from assistive technology. */
export function TrendChartsSkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label="Loading charts" className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {Array.from({ length: 4 }, (_, card) => (
        <Card key={card} className="p-cap-5">
          <div aria-hidden="true" className="mb-3 flex flex-col">
            <Skeleton className="my-0.5 h-4 w-40" />
            <Skeleton className="mt-1.5 h-3 w-56" />
            <Skeleton className="mt-2.5 h-3 w-3/4" />
            <Skeleton className="mt-2 h-3 w-1/2" />
          </div>
          <div className="relative" style={{ height: CARD_BONES.height }}>
            <ChartBones plan={CARD_BONES} />
          </div>
        </Card>
      ))}
      <span className="sr-only">Loading charts…</span>
    </div>
  )
}
