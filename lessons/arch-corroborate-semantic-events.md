# Corroborate a semantic event; never derive it from a regulatory category alone

Date: 2026-07-04   Area: arch

**Context**: The calendar showed BIIB as "reported 7/1" (real date 7/29) because ingest treated ANY 8-K carrying Item 2.02 as an earnings release. Item 2.02 ("Results of Operations and Financial Condition") also covers pre-announcements, delivery/production numbers, and royalty-trust distribution notices — a regulatory category was silently treated as a semantic event. Worse, the unguarded flip was terminal (reported rows are never overwritten), so one false positive froze the row wrong AND discarded the later genuine 8-K.

**Rule**: (a) Never derive a semantic event from a regulatory category alone — require an independent corroborating signal (here: timing plausibility vs the fiscal quarter and the expected date). (b) When a state transition is terminal, the guard belongs ON the transition, shipped WITH the feature — reconciliation added "after launch" arrives after the data is already poisoned. (c) For market-wide sweeps, prefer flip-only over insert: acting only on entities you already track bounds the blast radius of a misclassified signal.

**Evidence**: 8-K Item 2.02; BIIB shown "reported 7/1" vs real 7/29; pre-announcements (BIIB), delivery/production numbers (TSLA), royalty-trust distribution notices (MVO).
