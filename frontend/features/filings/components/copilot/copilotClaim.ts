// The one claim Ask this Filing makes about its answers, shared by the rail's empty state (AskCopilotRail),
// the end-of-summary callout (AskFilingCallout) and the coachmark (CopilotCoachmark), so the three cannot
// drift apart. It says only what the answer card shows: an answer can ship an uncited figure, or a
// not-disclosed verdict with no citation (backend copilot_service.py), so no surface promises that every
// answer is cited or grounded (D-034; gates: copilotClaim.spec.tsx, brandCopyRules.spec.ts rule 1).
export const COPILOT_CLAIM = 'Answers come from this filing, with cited passages you can check.'
