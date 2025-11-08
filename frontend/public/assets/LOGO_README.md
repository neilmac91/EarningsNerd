# EarningsNerd Logo Assets

This directory contains the official EarningsNerd logo assets in various formats and color modes.

## Logo Files

### Full Logo (Icon + Wordmark)
- `earningsnerd-logo-light.svg` - Light mode version
- `earningsnerd-logo-dark.svg` - Dark mode version

### Icon Only
- `earningsnerd-icon-light.svg` - Light mode icon
- `earningsnerd-icon-dark.svg` - Dark mode icon

## Design Specifications

### Colors
- **Base**: Deep navy/charcoal (#0f172a) or slate-100 (#f1f5f9)
- **Primary Accent**: Teal (#14b8a6 dark, #0f766e light)
- **Secondary Accent**: Amber (#f59e0b dark, #d97706 light)

### Typography
- **Font**: Inter (or system sans-serif fallback)
- **"Earnings"**: Uppercase, semibold (600), tracking-wider
- **"Nerd"**: Title case, bold (700), gradient fill

### Icon Concept
The icon features a chart/data line forming the letter "E", symbolizing:
- Data-driven insights
- Financial analysis
- Upward trends (earnings growth)
- Intelligence and precision

## Usage

### React Components

#### Full Logo
```tsx
import EarningsNerdLogo from '@/components/EarningsNerdLogo'

<EarningsNerdLogo variant="full" mode="auto" iconClassName="h-12 w-12" />
```

#### Icon Only
```tsx
import EarningsNerdLogoIcon from '@/components/EarningsNerdLogoIcon'

<EarningsNerdLogoIcon mode="dark" className="h-8 w-8" />
```

### Props

**EarningsNerdLogo:**
- `variant`: `'full' | 'icon-only'` (default: `'full'`)
- `mode`: `'light' | 'dark' | 'auto'` (default: `'auto'`)
- `className`: Additional CSS classes

**EarningsNerdLogoIcon:**
- `mode`: `'light' | 'dark' | 'auto'` (default: `'auto'`)
- `className`: Additional CSS classes (default: `'h-8 w-8'`)

### Standalone SVG Files

The SVG files can be used directly in HTML or converted to PNG:

```html
<img src="/assets/earningsnerd-logo-dark.svg" alt="EarningsNerd" />
```

## Favicon

To use the icon as a favicon, convert `earningsnerd-icon-dark.svg` to PNG formats:
- 16x16px (favicon.ico)
- 32x32px (favicon.ico)
- 180x180px (apple-touch-icon)

## Brand Guidelines

- Maintain clear space around the logo (minimum 1x icon height)
- Use dark mode logo on dark backgrounds
- Use light mode logo on light backgrounds
- Do not distort or rotate the logo
- Maintain aspect ratio when scaling

