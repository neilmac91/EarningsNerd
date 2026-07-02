// TODO(design-system-v2): Button and Input are NOT exported here yet. The repo's
// pre-existing ./Button (buttonVariants + primary/secondary/tertiary) and ./Input
// (inputClasses string constant) predate the v2 spec and have 20+/8 importers.
// The v2.1 pack ships port-ready primitives (buttonVariants(), tertiary alias,
// inputClasses(), Textarea/Select) — the port runs as its own PR per MIGRATION
// v2.1 §d; until then import the existing ones by path.
export { Badge, type BadgeProps, type BadgeVariant } from './Badge'
export { Card, CardHeader, CardTitle, CardBody, CardFooter, type CardProps } from './Card'
export { DataTable, type DataTableProps, type Column, type CellTone, type SortState, type Density } from './DataTable'
export { Skeleton, SkeletonText, SkeletonStat } from './Skeleton'
// v2.1: ui/StateCard renamed → GuidanceCard (collision with the app's own
// components/StateCard.tsx notice card; one letter from StatCard the KPI tile).
export { GuidanceCard, type GuidanceCardProps, type GuidanceCardVariant } from './GuidanceCard'
export {
  // v2.1: Direction is now the app's vocabulary ('up' | 'down' | 'flat' —
  // interchangeable with lib/financialTone.ts); direction() removed (derive
  // with the app's directionOf). Sparkline renamed → TrendSparkline (the app
  // owns components/charts/Sparkline.tsx with different props).
  CHART_SERIES, CHART_FONT, seriesColor, chartTheme, directionTone, directionTextTone,
  gridProps, xAxisProps, yAxisProps, crosshairProps, zeroLineProps, refLineProps, lineProps,
  ChartTooltip, TrendSparkline,
  type ChartTheme, type Direction, type ChartTooltipProps, type TrendSparklineProps,
} from './Chart'
export { cx } from './cx'
