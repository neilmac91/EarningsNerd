export { Button, buttonVariants, type ButtonProps, type ButtonVariant, type ButtonSize, type ButtonVariantsOptions } from './Button'
export { Badge, type BadgeProps, type BadgeVariant } from './Badge'
export {
  Input, Textarea, Select, inputClasses,
  type InputProps, type TextareaProps, type SelectProps, type InputClassesOptions,
} from './Input'
export { Card, CardHeader, CardTitle, CardBody, CardFooter, type CardProps } from './Card'
export { Notice, type NoticeProps, type NoticeVariant } from './Notice'
export { Switch, type SwitchProps } from './Switch'
// v3: the ONE dialog primitive (DS-04) — the dialog role ships only through Modal
// (plus the documented copilot sheets; gated by tests/unit/dialogAllowlist.spec.ts).
export { Modal, ModalHeader, ModalBody, ModalFooter, type ModalProps, type ModalHeaderProps } from './Modal'
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
  gridProps, xAxisProps, yAxisProps, crosshairProps, barCursorProps, zeroLineProps, refLineProps, lineProps,
  AxisSeriesTag, ChartTooltip, TrendSparkline,
  type ChartTheme, type Direction, type ChartTooltipProps, type TrendSparklineProps,
} from './Chart'
export { cx } from './cx'
