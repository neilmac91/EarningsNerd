---
name: web-design-guidelines
description: Audit UI code against web interface design standards
version: 1.0.0
author: vercel
source: https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines
allowed-tools:
  - WebFetch
  - Read
  - Grep
  - Glob
---

# Web Design Guidelines

This skill audits UI code for compliance with Vercel's Web Interface Guidelines. Use it when users request design reviews like "check my site against best practices" or "audit my UI design."

## Workflow

1. **Fetch Guidelines** - Retrieve the latest guidelines from the source
2. **Analyze Code** - Examine specified files against the rules
3. **Report Findings** - Deliver results in `file:line` format

## Invocation

Trigger this skill when users ask:
- "Review my UI against best practices"
- "Check my design implementation"
- "Audit my frontend code"
- "Does my UI follow design guidelines?"

## Guidelines Source

Fetch the latest guidelines from:
```
https://raw.githubusercontent.com/vercel/web-interface-guidelines/main/README.md
```

## Review Process

### Step 1: Fetch Current Guidelines

Use WebFetch to retrieve the latest guidelines document.

### Step 2: Identify Files to Review

If the user doesn't specify files, check common UI locations:
- `app/**/*.tsx`
- `components/**/*.tsx`
- `features/**/*.tsx`
- `pages/**/*.tsx`

### Step 3: Analyze Against Guidelines

Check for common issues:

**Layout & Spacing**
- Consistent spacing scale usage
- Proper use of flexbox/grid
- Responsive breakpoint handling

**Typography**
- Font size hierarchy
- Line height consistency
- Text color contrast

**Colors & Theming**
- Design token usage
- Dark mode support
- Accessible color contrast (WCAG AA minimum)

**Components**
- Consistent button styling
- Form input patterns
- Loading state handling
- Error state display

**Accessibility**
- Semantic HTML elements
- ARIA attributes where needed
- Keyboard navigation support
- Focus indicators

**Performance**
- Image optimization (next/image)
- Font loading strategy
- CSS-in-JS patterns

### Step 4: Report Findings

Format findings as:
```
<file>:<line> - <issue description>
```

Example output:
```
components/Button.tsx:15 - Missing focus-visible outline for keyboard users
components/Card.tsx:32 - Hardcoded color value instead of design token
app/dashboard/page.tsx:45 - Missing loading state for async data
```

## Key Guidelines Summary

### Do
- Use design tokens for colors, spacing, typography
- Implement keyboard navigation
- Provide loading and error states
- Use semantic HTML elements
- Support dark mode
- Optimize images with next/image

### Don't
- Hardcode color values
- Ignore focus states
- Use div for interactive elements
- Skip alt text on images
- Forget mobile responsiveness
- Use px for font sizes (use rem)

## Example Review Request

User: "Review my Button component against design guidelines"

Response:
```
Reviewing components/ui/Button.tsx against Web Interface Guidelines...

Findings:
- components/ui/Button.tsx:12 - Consider adding focus-visible styles for keyboard accessibility
- components/ui/Button.tsx:18 - Use design token 'var(--color-primary)' instead of hardcoded '#0070f3'
- components/ui/Button.tsx:25 - Add disabled state styling

Recommendations:
1. Add 'focus-visible:ring-2 focus-visible:ring-offset-2' for keyboard focus
2. Replace hardcoded colors with CSS variables or Tailwind theme values
3. Implement 'disabled:opacity-50 disabled:cursor-not-allowed' for disabled state
```
