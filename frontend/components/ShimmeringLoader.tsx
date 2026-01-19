import { clsx } from 'clsx'

interface ShimmeringLoaderProps extends React.HTMLAttributes<HTMLElement> {
  as?: React.ElementType
}

export function ShimmeringLoader({
  as: Component = 'div',
  className,
  ...props
}: ShimmeringLoaderProps) {
  return (
    <Component
      className={clsx(
        className,
        'relative overflow-hidden rounded-lg bg-panel-light dark:bg-panel-dark'
      )}
      {...props}
    >
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-background-light/30 dark:via-background-dark/30 to-transparent" />
    </Component>
  )
}
