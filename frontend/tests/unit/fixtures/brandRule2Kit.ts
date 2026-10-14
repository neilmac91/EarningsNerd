/**
 * A companion to brandRule2Forms.tsx: a React utility exported under a type of its own. Rule 2 reads a callee's
 * bindings in its own file, so a utility typed over in another file is out of its reach (P520, a gap).
 */
import { Children, type ReactNode } from 'react'

export const typedOnly: (child: ReactNode) => ReactNode = Children.only
