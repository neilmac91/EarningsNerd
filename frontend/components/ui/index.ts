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
// A plan's monthly usage as a bar, sage to warning at 80% and error at 100% (E196): the dashboard and pricing pages.
export { UsageMeter, usageMeterFill, type UsageMeterProps } from './UsageMeter'
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
// The chart kit: its tokens (the series, CHART_FONT, chartTheme) serve every chart, the analysis engine's too;
// the prop factories and ChartTooltip serve the Recharts charts (filing fundamentals, peers). E195 removed what
// nothing called.
export {
  CHART_SERIES, CHART_FONT, seriesColor, chartTheme,
  gridProps, xAxisProps, yAxisProps, barCursorProps,
  ChartTooltip,
  type ChartTheme, type ChartTooltipProps,
} from './Chart'
export { cx } from './cx'
