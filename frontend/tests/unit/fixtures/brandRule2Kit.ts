/**
 * A companion to brandRule2Forms.tsx, for two forms rule 2 leaves to review, since it reads a callee's bindings and a
 * className's classes in their own file: a React utility exported under a type of its own (P520), and the count
 * control's recipe rebuilt in another file's helper (P533). And one it reads, since its type is React's own: a
 * utility exported as possibly undefined (P534).
 */
import { Children, type ReactNode } from 'react'

export const typedOnly: (child: ReactNode) => ReactNode = Children.only

export const maybeOnly: typeof Children.only | undefined = Children.only

export const quietLinkClass = (): string => 'text-text-secondary-light hover:text-brand-strong'
