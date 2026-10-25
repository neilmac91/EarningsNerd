/**
 * A formatted change figure (formatGrowth, formatTableGrowth). "n/m" keeps its visible abbreviation, which the legend
 * defines, and is announced in words: read as text it is "n slash m". Callers sit inside a positioned box, so the
 * sr-only words stay clipped where they are.
 */
export default function GrowthText({ text }: { text: string }) {
  if (text !== 'n/m') return <>{text}</>
  return <><span aria-hidden="true">n/m</span><span className="sr-only">not meaningful</span></>
}
