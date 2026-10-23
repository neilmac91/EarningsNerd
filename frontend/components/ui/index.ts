export { Button, buttonVariants, primaryUnavailableClass, secondaryUnavailableClass, type ButtonProps, type ButtonVariant, type ButtonSize, type ButtonVariantsOptions } from './Button'
export { Badge, type BadgeProps, type BadgeStatusVariant, type BadgeVariant } from './Badge'
// The count control (D-030): a control whose label carries a count rests in the ink, sage under the pointer.
export { countControlClass, type CountControlKind } from './countControl'
export {
  Input, Textarea, Select, FieldSpinner, inputClasses, fieldUnavailableClass,
  type InputProps, type TextareaProps, type SelectProps, type InputClassesOptions, type FieldDensity,
} from './Input'
// v3.1: the one single-choice toggle group (calendar view + filings form filter).
export { SegmentedControl, MAX_SEGMENTS, type SegmentedControlProps, type SegmentedOption, type SegmentedControlSize } from './SegmentedControl'
export { Card, CardHeader, CardTitle, CardBody, CardFooter, type CardProps } from './Card'
export { Notice, type NoticeProps, type NoticeVariant } from './Notice'
export { Switch, type SwitchProps } from './Switch'
export { Checkbox, type CheckboxProps } from './Checkbox'
// v3: the ONE dialog primitive (DS-04) — the dialog role ships only through Modal
// (plus the documented copilot sheets; gated by tests/unit/dialogAllowlist.spec.ts).
export { Modal, ModalHeader, ModalBody, ModalFooter, type ModalProps, type ModalHeaderProps } from './Modal'
export { DataTable, type DataTableProps, type Column, type CellTone, type SortState, type Density } from './DataTable'
export { Skeleton, SkeletonText, SkeletonStat } from './Skeleton'
// A value the page does not have: the missing-value token, aria-hidden, beside words for assistive tech (E88).
export { MissingValue, type MissingValueProps } from './MissingValue'
// v2.1: ui/StateCard renamed → GuidanceCard (collision with the app's own
// components/StateCard.tsx notice card; one letter from StatCard the KPI tile).
export { GuidanceCard, type GuidanceCardProps, type GuidanceCardVariant } from './GuidanceCard'
// The brand device's margin and in-text marker (DESIGN.md › Graphic device): the landing's evidence row and
// the filing page's Risks section, around passages the server located (D-044).
export { MarkedCopy, EnRef } from './MarkedCopy'
// The marked copy's measure (its margin gives way below it), outside the 'use client' module for server components.
export { markedBlockInsetClass, markedRowInsetClass } from './markedCopyLayout'
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
