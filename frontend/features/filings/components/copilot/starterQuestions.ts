// Broad, filing-type-aware example questions, shared by the Copilot empty state (AskCopilotRail) and
// the end-of-summary callout (AskFilingCallout). General-by-design (NN/g: broad prompts invite
// exploration; overly specific ones force users to adapt them).

const isTenQ = (filingType: string): boolean => /10-?q/i.test(filingType)

export function starterQuestions(filingType: string): string[] {
  if (isTenQ(filingType)) {
    return [
      'How did revenue and margins change this quarter?',
      'What are the top risks?',
      'What did management say about demand?',
      'Any changes to guidance?',
    ]
  }
  // 10-K (and any non-10-Q) defaults
  return [
    'What are the biggest risks this year?',
    'How did revenue and profitability trend?',
    'What is the company’s competitive position?',
    'What did management highlight in the MD&A?',
  ]
}
